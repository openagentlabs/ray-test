# Langfuse S3 + LiteLLM Tracing — Troubleshooting & Resolution Guide

**Date resolved:** 2026-05-14  
**Environment:** `dev` (`midas-eks-aigtw-dev`)  
**Symptom:** LiteLLM calls produced no traces in Langfuse. Manual ingestion API calls returned HTTP 500.

---

## Summary of issues found

Three independent bugs blocked Langfuse ingestion end-to-end. All three had to be fixed together before traces appeared.

| # | Layer | Root cause | Fix |
|---|---|---|---|
| 1 | Helm values | Wrong S3 bucket names in `values-midas-dev.yaml` | Corrected to match actual bucket names |
| 2 | Terraform / IAM | `langfuse_s3_config_policy` pointed at log buckets, not Langfuse buckets | Updated `data.tf` to grant access to the correct ARNs |
| 3 | AWS Secrets Manager | Langfuse public/secret key secrets contained placeholder `PopulateMe` values | Populated with real project-level API keys via `aws secretsmanager put-secret-value` |

---

## Issue 1 — Wrong S3 bucket names in Helm values

### Symptom

Langfuse web pod logs contained:

```
NoSuchBucket: The specified bucket does not exist
Failed to upload events to blob storage, aborting event processing
Error: Failed to upload events to blob storage, aborting event processing
```

Every ingestion call returned **HTTP 500** because Langfuse could not write the event to S3 before processing it.

### Root cause

`deploy/ai_gateway/helm/langfuse/values-midas-dev.yaml` had bucket names that did not match the actual S3 buckets created by Terraform:

| Config value (wrong) | Actual bucket |
|---|---|
| `midas-aigtw-dev-langfuse-data` | `midas-eks-aigtw-dev-langfuse-data-bucket` |
| `midas-aigtw-dev-langfuse-media` | `midas-eks-aigtw-dev-langfuse-media-bucket` |

The Terraform resource names (in `deploy/ai_gateway/terraform/modules-midas/s3.tf`) use the `eks_cluster_name` variable as prefix and append `-bucket`, but the Helm values were hand-written with a shorter form.

### Fix

In `deploy/ai_gateway/helm/langfuse/values-midas-dev.yaml`, update the `s3` section:

```yaml
s3:
  deploy: false
  eventUpload:
    enabled: true
    bucket: "midas-eks-aigtw-dev-langfuse-data-bucket"   # was: midas-aigtw-dev-langfuse-data
    region: "us-east-1"
    forcePathStyle: false
  batchExport:
    enabled: true
    bucket: "midas-eks-aigtw-dev-langfuse-data-bucket"   # was: midas-aigtw-dev-langfuse-data
    region: "us-east-1"
    forcePathStyle: false
  mediaUpload:
    enabled: true
    bucket: "midas-eks-aigtw-dev-langfuse-media-bucket"  # was: midas-aigtw-dev-langfuse-media
    region: "us-east-1"
    forcePathStyle: false
```

**Deployment:** Commit and run **ORD4** (`ACTION=install`, `ENVIRONMENT=dev`).

### How to check

To verify the bucket names that actually exist:

```bash
aws s3 ls | grep langfuse
```

To verify what bucket names the running pod is using:

```bash
kubectl get deployment langfuse-web -n langfuse -o json \
  | python3 -c "import json,sys; d=json.load(sys.stdin); envs=d['spec']['template']['spec']['containers'][0]['env']; [print(e['name'],'=',e.get('value','')) for e in envs if 'BUCKET' in e['name'].upper()]"
```

---

## Issue 2 — IRSA role missing S3 permissions on Langfuse buckets

### Symptom

After fixing the bucket names, pod logs changed from `NoSuchBucket` to:

```
AccessDenied: User: arn:aws:sts::811391286931:assumed-role/exl-midas-eks-aigtw-dev-shr-langfuse/...
is not authorized to perform: s3:PutObject on resource:
"arn:aws:s3:::midas-eks-aigtw-dev-langfuse-data-bucket/..."
because no identity-based policy allows the s3:PutObject action
```

### Root cause

`deploy/ai_gateway/terraform/modules-midas/data.tf` — the `langfuse_s3_config_policy` IAM policy document listed the **log buckets** instead of the Langfuse data/media buckets:

```hcl
# WRONG — what it was before
data "aws_iam_policy_document" "langfuse_s3_config_policy" {
  statement {
    actions = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
    effect  = "Allow"
    resources = [
      "${aws_s3_bucket.exlerate_al_bucket.arn}/*",
      "${aws_s3_bucket.exlerate_log_bucket.arn}/*",
    ]
  }
}
```

The IRSA role `exl-midas-eks-aigtw-dev-shr-langfuse` had `AmazonS3ReadOnlyAccess` (managed policy) but no write permissions, and the custom policy `midas-eks-aigtw-dev-langfuse-s3-config-policy` was granting write to the wrong buckets.

### Fix

Update `deploy/ai_gateway/terraform/modules-midas/data.tf`:

```hcl
# CORRECT
data "aws_iam_policy_document" "langfuse_s3_config_policy" {
  statement {
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
    ]
    effect = "Allow"
    resources = [
      aws_s3_bucket.exlerate_langfuse_data_bucket.arn,
      "${aws_s3_bucket.exlerate_langfuse_data_bucket.arn}/*",
      aws_s3_bucket.exlerate_langfuse_media_bucket.arn,
      "${aws_s3_bucket.exlerate_langfuse_media_bucket.arn}/*",
    ]
  }
}
```

**Deployment:** Commit → run **ORD1** (`ACTION=apply`, `ENVIRONMENT=dev`, approve at gate) → then run **ORD4** again to restart pods so IRSA token is refreshed.

### How to check

Inspect the current policy document:

```bash
POLICY_ARN="arn:aws:iam::811391286931:policy/midas-eks-aigtw-dev-langfuse-s3-config-policy"
VERSION=$(aws iam get-policy --policy-arn $POLICY_ARN --query Policy.DefaultVersionId --output text)
aws iam get-policy-version --policy-arn $POLICY_ARN --version-id $VERSION \
  --query PolicyVersion.Document --output json
```

Expected: resources should reference `langfuse-data-bucket` and `langfuse-media-bucket`, **not** `log-bucket` or `access-log-bucket`.

---

## Issue 3 — Langfuse API keys not populated in Secrets Manager

### Symptom

LiteLLM was configured to send traces (callbacks set in `default-config-base.yaml`) but no traces appeared. The Langfuse host, public key, and secret key K8s secrets in the `litellm` namespace contained placeholder values (`PopulateMe`).

### Root cause

The AWS Secrets Manager secrets created by Terraform for Langfuse→LiteLLM integration had never been populated with real values:

| Secret name | State |
|---|---|
| `langfuse-public-key-midas-eks-aigtw-dev` | `PopulateMe` |
| `langfuse-secret-key-midas-eks-aigtw-dev` | `PopulateMe` |
| `langfuse-host-midas-eks-aigtw-dev` | `PopulateMe` |

These are **project-level** Langfuse API keys (not org-level). They are obtained from the Langfuse UI under **Settings → API Keys** and must be for the project whose traces you want to appear.

### Fix

Populate the secrets via AWS CLI:

```bash
CLUSTER="midas-eks-aigtw-dev"
REGION="us-east-1"

aws secretsmanager put-secret-value \
  --secret-id "langfuse-public-key-${CLUSTER}" \
  --secret-string "pk-lf-<your-project-public-key>" \
  --region $REGION

aws secretsmanager put-secret-value \
  --secret-id "langfuse-secret-key-${CLUSTER}" \
  --secret-string "sk-lf-<your-project-secret-key>" \
  --region $REGION

aws secretsmanager put-secret-value \
  --secret-id "langfuse-host-${CLUSTER}" \
  --secret-string "http://langfuse-web.langfuse.svc.cluster.local:3000" \
  --region $REGION
```

> **Important:** The host must be the **in-cluster DNS name** (`http://langfuse-web.langfuse.svc.cluster.local:3000`), not the external URL. LiteLLM runs inside the same cluster and uses cluster-internal DNS to avoid going out via the NLB.

Then sync the K8s secrets by running **ORD5** (`ACTION=install`, `ENVIRONMENT=dev`). ORD5 includes a "Sync Langfuse secrets from AWS SM" stage that patches the three K8s secrets in the `litellm` namespace before the Helm upgrade.

### How to check

```bash
# Verify the secret values are set (not PopulateMe)
aws secretsmanager get-secret-value \
  --secret-id langfuse-public-key-midas-eks-aigtw-dev \
  --query SecretString --output text

# Verify the K8s secret in litellm namespace
kubectl get secret langfuse-public-key -n litellm -o jsonpath='{.data.langfuse-public-key}' | base64 -d
```

---

## LiteLLM ↔ Langfuse wiring reference

### Where callbacks are configured

`deploy/ai_gateway/config/default-config-base.yaml` — the `success_callback` and `failure_callback` arrays must include `langfuse`:

```yaml
litellm_settings:
  success_callback: ["langfuse"]
  failure_callback: ["langfuse"]
```

### How credentials reach LiteLLM pods

The flow is: **AWS Secrets Manager → K8s Secrets (litellm namespace) → LiteLLM pod env vars**

| K8s Secret | Key | LiteLLM env var |
|---|---|---|
| `langfuse-public-key` | `langfuse-public-key` | `LANGFUSE_PUBLIC_KEY` |
| `langfuse-secret-key` | `langfuse-secret-key` | `LANGFUSE_SECRET_KEY` |
| `langfuse-host` | `langfuse-host` | `LANGFUSE_HOST` |

The K8s secrets are created by `deploy/ai_gateway/terraform/modules-midas/litellm_app_deps.tf` and synced by the ORD5 secret-sync pipeline stage.

---

## How to send a test trace manually

Use this to verify end-to-end ingestion without needing a LiteLLM call:

```bash
PK="pk-lf-<your-public-key>"
SK="sk-lf-<your-secret-key>"
HOST="https://exldecision-ai-dev-aigw-langfuse.exlservice.com"  # external URL for testing from laptop
TRACE_ID="test-$(date +%s)"

curl -sk -w "\nHTTP_STATUS:%{http_code}" \
  -X POST "${HOST}/api/public/ingestion" \
  -H "Content-Type: application/json" \
  -H "Authorization: Basic $(echo -n "${PK}:${SK}" | base64)" \
  -d "{
    \"batch\": [{
      \"id\": \"${TRACE_ID}-evt\",
      \"type\": \"trace-create\",
      \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%S.000Z)\",
      \"body\": {
        \"id\": \"${TRACE_ID}\",
        \"name\": \"manual-test\",
        \"input\": \"test input\",
        \"output\": \"test output\"
      }
    }]
  }"
```

**Expected response:** `HTTP 207` with `{"successes":[{"id":"...","status":201}],"errors":[]}`

Then open the Langfuse UI → **Traces** and search for your trace ID.

---

## Deployment order for a clean fix

When all three issues are present (new environment or after a reset), apply fixes in this order:

```
1. Populate AWS SM secrets (Issue 3) — no pipeline needed, just AWS CLI
2. Fix Helm values bucket names (Issue 1) — commit to git
3. Fix IAM policy (Issue 2) — commit to git
4. Run ORD1 (Terraform apply) — applies IAM policy change
5. Run ORD4 (Langfuse Helm install) — picks up correct bucket names + restarts pods
6. Run ORD5 (LiteLLM Helm install) — syncs K8s secrets from AWS SM + restarts LiteLLM pods
7. Send test trace (see above) — verify HTTP 207 with no errors
8. Check Langfuse UI for trace
```

---

## Diagnosing future S3 errors

### Step 1 — Check web pod logs

```bash
kubectl logs -n langfuse deployment/langfuse-web --tail=100 | grep -iE "error|bucket|s3|upload"
```

| Error message | Likely cause |
|---|---|
| `NoSuchBucket` | Bucket name in Helm values doesn't match actual bucket |
| `AccessDenied: s3:PutObject` | IRSA policy missing write permissions on the bucket |
| `InvalidAccessKeyId` | IRSA not wired correctly (service account / OIDC issue) |
| `NoCredentialProviders` | Pod not using IRSA; service account annotation missing |

### Step 2 — Verify bucket names match

```bash
# What Helm says
kubectl get deployment langfuse-web -n langfuse -o jsonpath='{.spec.template.spec.containers[0].env}' \
  | python3 -c "import json,sys; [print(e['name'],'=',e.get('value','')) for e in json.load(sys.stdin) if 'BUCKET' in e['name']]"

# What actually exists in S3
aws s3 ls | grep langfuse
```

### Step 3 — Verify IAM policy resources

```bash
aws iam get-policy-version \
  --policy-arn arn:aws:iam::811391286931:policy/midas-eks-aigtw-dev-langfuse-s3-config-policy \
  --version-id $(aws iam get-policy \
    --policy-arn arn:aws:iam::811391286931:policy/midas-eks-aigtw-dev-langfuse-s3-config-policy \
    --query Policy.DefaultVersionId --output text) \
  --query PolicyVersion.Document.Statement --output json
```

Expected resources: `midas-eks-aigtw-dev-langfuse-data-bucket` and `midas-eks-aigtw-dev-langfuse-media-bucket`.

---

## Related files

| File | Purpose |
|---|---|
| `deploy/ai_gateway/helm/langfuse/values-midas-dev.yaml` | Langfuse Helm values — bucket names live in the `s3:` section |
| `deploy/ai_gateway/terraform/modules-midas/data.tf` | `langfuse_s3_config_policy` IAM document — must reference the correct bucket ARNs |
| `deploy/ai_gateway/terraform/modules-midas/s3.tf` | Terraform source of truth for bucket names (`aws_s3_bucket.exlerate_langfuse_data_bucket`, `exlerate_langfuse_media_bucket`) |
| `deploy/ai_gateway/terraform/modules-midas/litellm_app_deps.tf` | K8s secrets for LiteLLM — maps SM secrets to pod env vars |
| `deploy/ai_gateway/config/default-config-base.yaml` | LiteLLM config — `success_callback`/`failure_callback` |
| `deploy/ai_gateway/jenkinsfiles/Jenkinsfile_ORD4_langfuse` | Langfuse Helm pipeline |
| `deploy/ai_gateway/jenkinsfiles/Jenkinsfile_ORD5_litellm` | LiteLLM Helm pipeline — includes Langfuse secret-sync stage |
| `deploy/ai_gateway/jenkinsfiles/Jenkinsfile_ORD1_terraform` | Terraform pipeline — needed when IAM policies change |
