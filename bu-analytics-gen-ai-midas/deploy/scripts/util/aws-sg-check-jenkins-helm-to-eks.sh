#!/usr/bin/env bash
# Read-only: traffic-light table for EKS cluster security group - TCP 443 from Jenkins/Helm CIDR.
# Uses AWS CLI credential chain (~/.aws/credentials, AWS_PROFILE). Configure keys with:
#   ./deploy/scripts/util/aws-credentials-setup.sh
#   export AWS_PROFILE=default
#   export AWS_REGION=us-east-1
#
# Usage (repo root):
#   ./deploy/scripts/util/aws-sg-check-jenkins-helm-to-eks.sh [--cluster midas-eks-dev] [--jenkins-cidr 10.90.12.0/22]
# Extra args are forwarded to the Python helper (see --help).

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
exec python3 "${ROOT}/deploy/scripts/util/aws-sg-traffic-checks.py" jenkins-eks "$@"
