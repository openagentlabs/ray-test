#!/usr/bin/env bash
# Build all images listed in deploy/ecs-app/docker/build-registry/images.yaml
# Usage: from repo root - IMAGE_TAG=abc123 ./deploy/scripts/ci/docker-build-matrix.sh
#
# Optional env vars:
#   IMAGE_TAG          - Docker image tag (default: latest)
#   ENVIRONMENT        - Deployment environment (default: dev). Used to resolve the
#                        frontend SM secret name: midas-{ENVIRONMENT}-{REGION}/frontend.
#   AWS_REGION         - AWS region (default: us-east-1).
#   FRONTEND_SM_SECRET - Override the full SM secret ID for frontend build args.
#                        Default: midas-{ENVIRONMENT}-{REGION}/frontend.
#   SKIP_FRONTEND_SECRETS - Set to true/1/yes to skip SM lookup (local builds without AWS).
#
# For the midas-web-frontend-svc image only, this script reads VITE_* values from
# AWS Secrets Manager and passes them as --build-arg so Vite bakes them into the
# JS bundle at build time (import.meta.env.VITE_*).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
MAP="deploy/ecs-app/docker/build-registry/images.yaml"
TAG="${IMAGE_TAG:-latest}"
REGION="${AWS_REGION:-us-east-1}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
FRONTEND_SM_SECRET="${FRONTEND_SM_SECRET:-midas-${ENVIRONMENT}-${REGION}/frontend}"

# yq for YAML parsing: use agent PATH if present, else cache a release binary from GitHub.
YQ="${ROOT}/.cache-ci/yq"
if command -v yq >/dev/null 2>&1; then
  YQ="$(command -v yq)"
elif [ ! -x "$YQ" ]; then
  mkdir -p "$(dirname "$YQ")"
  echo "Downloading yq for YAML parsing..."
  OS="$(uname -s | tr '[:upper:]' '[:lower:]')"   # linux | darwin
  ARCH="$(uname -m)"                                # x86_64 | aarch64 | arm64
  case "${OS}_${ARCH}" in
    linux_x86_64)   YQ_BINARY="yq_linux_amd64" ;;
    linux_aarch64)  YQ_BINARY="yq_linux_arm64" ;;
    darwin_x86_64)  YQ_BINARY="yq_darwin_amd64" ;;
    darwin_arm64)   YQ_BINARY="yq_darwin_arm64" ;;
    *)              echo "Unsupported platform ${OS}_${ARCH}" >&2; exit 1 ;;
  esac
  # GitHub / corporate proxies sometimes return 5xx (e.g. 504); retries reduce flaky CI.
  curl -fsSL --retry 5 --retry-delay 3 \
    "https://github.com/mikefarah/yq/releases/download/v4.44.3/${YQ_BINARY}" -o "$YQ"
  chmod +x "$YQ"
fi

# ---------------------------------------------------------------------------
# Read VITE_* build args from AWS Secrets Manager for the frontend image.
# midas-{env}-{region}/frontend holds all VITE_* keys set by Terraform.
# We do this once before the build loop so the lookup fails fast if creds
# or the secret are missing, rather than silently building an empty-config bundle.
# ---------------------------------------------------------------------------
FRONTEND_BUILD_ARGS=()

truthy() { case "${1:-}" in 1|true|TRUE|yes|YES) return 0 ;; *) return 1 ;; esac }

if truthy "${SKIP_FRONTEND_SECRETS:-false}"; then
  echo "=== SKIP_FRONTEND_SECRETS=true — building frontend without VITE_* args (local/test mode) ==="
else
  echo "=== Reading frontend VITE_* build args from SM: ${FRONTEND_SM_SECRET} ==="
  SM_JSON=$(aws secretsmanager get-secret-value \
    --secret-id "${FRONTEND_SM_SECRET}" \
    --region "${REGION}" \
    --query 'SecretString' \
    --output text 2>&1) || {
    echo "ERROR: Failed to read SM secret '${FRONTEND_SM_SECRET}'." >&2
    echo "  Ensure AWS credentials are active and the secret exists." >&2
    echo "  To skip (local builds): SKIP_FRONTEND_SECRETS=true" >&2
    exit 1
  }

  # Extract each VITE_* key and build the --build-arg list.
  # Validate required keys are present and non-empty before proceeding.
  REQUIRED_VITE_KEYS=(
    VITE_BASE_URL
    VITE_COGNITO_DOMAIN
    VITE_COGNITO_CLIENT_ID
    VITE_COGNITO_REDIRECT_URI
    VITE_COGNITO_LOGOUT_REDIRECT_URI
    VITE_COGNITO_SCOPES
  )

  missing_keys=()
  for key in "${REQUIRED_VITE_KEYS[@]}"; do
    val=$(python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('${key}',''))" <<< "$SM_JSON")
    if [ -z "$val" ]; then
      missing_keys+=("$key")
    else
      FRONTEND_BUILD_ARGS+=("--build-arg" "${key}=${val}")
      echo "    ${key} = ${val}"
    fi
  done

  if [ ${#missing_keys[@]} -gt 0 ]; then
    echo "ERROR: The following required VITE_* keys are missing or empty in SM secret '${FRONTEND_SM_SECRET}':" >&2
    printf '  - %s\n' "${missing_keys[@]}" >&2
    echo "  Populate them with:" >&2
    echo "    aws secretsmanager put-secret-value --secret-id ${FRONTEND_SM_SECRET} --secret-string '{...}'" >&2
    exit 1
  fi
  echo "    All ${#FRONTEND_BUILD_ARGS[@]} build args loaded."
fi

# ---------------------------------------------------------------------------
# Build loop
# ---------------------------------------------------------------------------
while IFS= read -r svc; do
  ctx=$("$YQ" e ".images[] | select(.service == \"$svc\") | .context" "$MAP")
  df=$("$YQ" e ".images[] | select(.service == \"$svc\") | .dockerfile" "$MAP")

  # Resolve build context directory (context "." means repo root)
  if [ "$ctx" = "." ]; then
    BUILD_CTX="${ROOT}"
  else
    BUILD_CTX="${ROOT}/${ctx}"
  fi

  # Resolve Dockerfile path - if context is ".", dockerfile is already relative to root
  if [ "$ctx" = "." ]; then
    DOCKERFILE="${ROOT}/${df}"
  else
    DOCKERFILE="${BUILD_CTX}/${df}"
  fi

  # The backend image bundles the local routing-tier gRPC client
  # (pod_manager/router.svc/client_py). Docker cannot reach that path from the
  # backend/ build context, so pre-build it into a wheel inside the backend
  # context here; backend/Dockerfile then installs backend/vendor/*.whl.
  #
  # The wheel is built inside a pinned python:3.12-slim container (the client
  # declares requires-python >=3.12) so the build does not depend on the CI
  # agent's host Python version. --no-deps keeps vendor/ to exactly the client
  # wheel; its runtime deps (grpcio, protobuf) resolve during the image build.
  if [ "$svc" = "midas-api-backend-svc" ]; then
    VENDOR_DIR="${ROOT}/backend/vendor"
    echo "=== building router-client wheel for backend image ==="
    echo "    source: pod_manager/router.svc/client_py"
    echo "    output: ${VENDOR_DIR}"
    rm -rf "${VENDOR_DIR}"
    mkdir -p "${VENDOR_DIR}"
    # Run as the host user so the wheel and setuptools' build/ side-effect tree
    # are owned by the CI agent user, not root. Root-owned artifacts left in the
    # bind-mounted workspace make Jenkins' pre-checkout workspace clean fail with
    # "Operation not permitted" (it can't chmod files it doesn't own).
    docker run --rm \
      --user "$(id -u):$(id -g)" \
      -v "${ROOT}:/src" \
      -w /src \
      python:3.12-slim \
      pip wheel --no-deps -w /src/backend/vendor /src/pod_manager/router.svc/client_py
    # Remove setuptools build artifacts written into the source tree by pip wheel.
    rm -rf "${ROOT}/pod_manager/router.svc/client_py/build" \
           "${ROOT}/pod_manager/router.svc/client_py"/*.egg-info
  fi

  echo "=== docker build: $svc ==="
  echo "    context:    ${BUILD_CTX}"
  echo "    dockerfile: ${DOCKERFILE}"

  # Inject VITE_* build args for the frontend image only.
  # Other images (backend, graph) do not use VITE_* vars.
  if [ "$svc" = "midas-web-frontend-svc" ] && [ ${#FRONTEND_BUILD_ARGS[@]} -gt 0 ]; then
    docker build -f "${DOCKERFILE}" -t "${svc}:${TAG}" "${FRONTEND_BUILD_ARGS[@]}" "${BUILD_CTX}"
  else
    docker build -f "${DOCKERFILE}" -t "${svc}:${TAG}" "${BUILD_CTX}"
  fi
done < <("$YQ" e '.images[].service' "$MAP")

echo "All images built with tag ${TAG}."
