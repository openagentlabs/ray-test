#!/usr/bin/env bash
# Validate deploy/ecs-app Terraform (fmt + init without remote backend + validate).
# Requires: terraform >= 1.1, valid AWS credentials (for provider init), network for providers.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}/ecs-app"

echo "==> terraform fmt -recursive -check"
terraform fmt -recursive -check

echo "==> terraform init -backend=false -input=false"
terraform init -backend=false -input=false

echo "==> terraform validate"
terraform validate

echo "OK: ecs-app Terraform validates."
