#!/usr/bin/env bash
# Pre-deploy checks for EKS in deploy/ecs-app (see .cursor/validation/pre-deploy-eks-validation.md).
# Usage:
#   export AWS_REGION=us-east-1
#   export EKS_VPC_ID=vpc-0c4d673f3e95a93eb
#   export EKS_CLUSTER_SUBNET_IDS="subnet-aaa,subnet-bbb"
#   ./pre-deploy-validate-eks.sh
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
VPC_ID="${EKS_VPC_ID:-vpc-0c4d673f3e95a93eb}"
SUBNETS_CSV="${EKS_CLUSTER_SUBNET_IDS:-subnet-05c4fce53e16da9bc,subnet-04d9f5b09b2dc9425}"

echo "=== Pre-deploy EKS validation (region=${REGION}) ==="

echo "-- sts get-caller-identity"
aws sts get-caller-identity --output table

echo "-- describe VPC ${VPC_ID}"
aws ec2 describe-vpcs --region "${REGION}" --vpc-ids "${VPC_ID}" --query 'Vpcs[0].{State:State,Cidr:CidrBlock}' --output table

IFS=',' read -ra SUBNET_ARR <<< "${SUBNETS_CSV// /}"
AZS=()
for s in "${SUBNET_ARR[@]}"; do
  [[ -z "${s}" ]] && continue
  echo "-- describe subnet ${s}"
  out=$(aws ec2 describe-subnets --region "${REGION}" --subnet-ids "${s}" --query 'Subnets[0].{VpcId:VpcId,Az:AvailabilityZone,Cidr:CidrBlock}' --output text)
  echo "${out}"
  vid=$(echo "${out}" | awk '{print $1}')
  az=$(echo "${out}" | awk '{print $2}')
  if [[ "${vid}" != "${VPC_ID}" ]]; then
    echo "FAIL: subnet ${s} is in VPC ${vid}, expected ${VPC_ID}" >&2
    exit 1
  fi
  AZS+=("${az}")
done

echo "-- distinct AZ count (need >= 2 for managed node groups)"
uniq_az=$(printf '%s\n' "${AZS[@]}" | sort -u | wc -l | tr -d ' ')
echo "distinct AZs: ${uniq_az}"
if [[ "${uniq_az}" -lt 2 ]]; then
  echo "FAIL: need subnets in at least two Availability Zones." >&2
  exit 1
fi

echo "=== Pre-deploy validation PASSED ==="
