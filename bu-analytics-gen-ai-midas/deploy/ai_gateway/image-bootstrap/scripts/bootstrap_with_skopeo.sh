#!/usr/bin/env bash
# MIDAS AI Gateway image bootstrap — laptop edition
#
# Mirrors every PUBLIC_REGISTRY image listed in deploy/ai_gateway/image-bootstrap/images.yaml
# into the corresponding MIDAS ECR repo, using `skopeo copy --multi-arch=all` so we get a
# linux/amd64 manifest matching the EKS node arch. No docker daemon needed — runs anywhere
# skopeo + AWS CLI are installed (mac via brew is the typical operator workstation).
#
# Why this exists: ORD2 (`midas-ai-gateway-image-bootstrap-ORD2`) is the canonical, repeatable
# Jenkins path. But it depends on (a) Python helper scripts that aren't written yet (todo t14),
# (b) Jenkins credential `netskope-proxy-url` (M-3), and (c) the dedicated cross-account role
# `EXLJenkinsAIGatewayCrossAccountRole-BU` (M-14). All three are PENDING. To unblock ORD3..ORD7
# right now, this script does a one-shot mirror from the operator laptop using SSO credentials.
#
# Usage:
#   AWS_PROFILE=midas-dev bash deploy/ai_gateway/image-bootstrap/scripts/bootstrap_with_skopeo.sh
# Or with a name filter:
#   IMAGE_FILTER=langfuse bash deploy/ai_gateway/image-bootstrap/scripts/bootstrap_with_skopeo.sh
#
# Idempotent: re-running on already-mirrored tags is a no-op (skopeo skips identical layers).

set -eo pipefail

# Hard guard: this script must only ever talk to the MIDAS dev account.
# Catches the case where the operator's AWS_PROFILE is pointing somewhere else.
EXPECTED_ACCT="811391286931"
REGION="us-east-1"
REGISTRY="${EXPECTED_ACCT}.dkr.ecr.${REGION}.amazonaws.com"
INVENTORY="${INVENTORY:-deploy/ai_gateway/image-bootstrap/images.yaml}"
FILTER="${IMAGE_FILTER:-}"

ACTUAL_ACCT="$(aws sts get-caller-identity --query Account --output text)"
if [[ "$ACTUAL_ACCT" != "$EXPECTED_ACCT" ]]; then
    echo "FATAL: connected to AWS account $ACTUAL_ACCT, expected $EXPECTED_ACCT (MIDAS dev). Set AWS_PROFILE." >&2
    exit 2
fi

for tool in skopeo aws yq; do
    command -v "$tool" >/dev/null 2>&1 || {
        echo "FATAL: '$tool' is not installed. brew install $tool" >&2
        exit 3
    }
done

echo "[bootstrap] Inventory: $INVENTORY"
echo "[bootstrap] Filter:    ${FILTER:-<none>}"
echo "[bootstrap] ECR:       $REGISTRY"

PW="$(aws ecr get-login-password --region "$REGION")"

# yq parses the inventory. We only handle public_registry entries here; from_source builds
# require a docker daemon + the MIDAS source tree and are deliberately delegated to ORD2 proper.
COUNT="$(yq '.images | length' "$INVENTORY")"
echo "[bootstrap] $COUNT image(s) declared in inventory"

ok=0; skipped=0; failed=0
for i in $(seq 0 $((COUNT-1))); do
    NAME="$(yq ".images[$i].name" "$INVENTORY")"
    TYPE="$(yq ".images[$i].source.type" "$INVENTORY")"

    if [[ -n "$FILTER" && "$NAME" != *"$FILTER"* ]]; then
        echo "[skip] $NAME (filter)"
        skipped=$((skipped+1)); continue
    fi
    if [[ "$TYPE" != "public_registry" ]]; then
        echo "[skip] $NAME (type=$TYPE — needs ORD2 with docker daemon)"
        skipped=$((skipped+1)); continue
    fi

    SRC_REG="$(yq ".images[$i].source.registry" "$INVENTORY")"
    SRC_REPO="$(yq ".images[$i].source.repository" "$INVENTORY")"
    SRC_TAG="$(yq ".images[$i].source.tag" "$INVENTORY")"
    DST_REPO="$(yq ".images[$i].target_ecr_repo" "$INVENTORY")"
    DST_TAG="$(yq ".images[$i].target_tag" "$INVENTORY")"

    SRC="docker://$SRC_REG/$SRC_REPO:$SRC_TAG"
    DST="docker://$REGISTRY/$DST_REPO:$DST_TAG"

    echo
    echo "[copy] $NAME"
    echo "       FROM $SRC"
    echo "       TO   $DST"

    # Create the target repo if missing (idempotent).
    if ! aws ecr describe-repositories --region "$REGION" --repository-names "$DST_REPO" >/dev/null 2>&1; then
        echo "       creating ECR repo $DST_REPO"
        aws ecr create-repository --region "$REGION" --repository-name "$DST_REPO" \
            --image-scanning-configuration scanOnPush=true \
            --encryption-configuration encryptionType=AES256 >/dev/null
    fi

    # --multi-arch=all so EKS nodes (amd64) get the right manifest from a multi-arch source.
    # --dest-creds: ECR. --src-creds: only set when the source registry needs auth
    # (public.ecr.aws, ghcr.io public images, docker.io anonymous all work without it).
    if skopeo copy --multi-arch=all --dest-creds "AWS:$PW" "$SRC" "$DST" 2>&1 | tail -8; then
        ok=$((ok+1))
        echo "       OK"
    else
        failed=$((failed+1))
        echo "       FAILED"
    fi
done

echo
echo "[bootstrap] DONE: ok=$ok skipped=$skipped failed=$failed"
exit $((failed > 0 ? 1 : 0))
