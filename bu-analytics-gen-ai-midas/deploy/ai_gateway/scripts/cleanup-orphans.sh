#!/usr/bin/env bash
# cleanup-orphans.sh — destroy AI Gateway AWS resources that exist in account
# 811391286931 but are not tracked in any Terraform state (orphans created by
# build #10 of midas-ai-gateway-tf-deploy-ORD1 before the S3 backend bug was
# fixed). Safe to run only because:
#   - the account is dev (ns-ai-midas-dev-use1-dev)
#   - no application traffic depends on these resources yet
#   - everything we delete carries `midas-aigtw-dev` or `midas-eks-aigtw-dev`
#     in its name; SHARED resources (VPC, subnets, jumpbox) are NEVER touched
#
# AUTH MODEL: same as deploy/ai_gateway/scripts/populate-secrets.sh — trusts
# `aws sso login --profile midas-dev`, hard-stops if not in account 811391286931.
#
# Usage:
#   ./deploy/ai_gateway/scripts/cleanup-orphans.sh [--dry-run] [--yes] \
#       [--cluster midas-eks-aigtw-dev] [--env dev]
#
# Flags:
#   --dry-run   list everything that would be deleted; no mutations
#   --yes       skip the typed-confirmation prompt (for ci / automation)
#   --cluster   override eks_cluster_name (default: midas-eks-aigtw-dev)
#   --env       override environment short name (default: dev)
# `set -u` removed deliberately: this script iterates many arrays that are commonly empty
# (e.g. RDS_INSTANCES, REDIS_RG when a previous cleanup partially succeeded). Under `set -u`
# bash 3.2 raises "unbound variable" on `"${ARR[@]}"` for empty arrays, which would abort
# cleanup mid-run. We rely on explicit array-length checks instead.
set -eo pipefail

EXPECTED_ACCOUNT_ID="811391286931"
DEFAULT_REGION="us-east-1"
CLUSTER="midas-eks-aigtw-dev"
ENV_SHORT="dev"
DRY_RUN=false
ASSUME_YES=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=true; shift ;;
    --yes)     ASSUME_YES=true; shift ;;
    --cluster) CLUSTER="$2"; shift 2 ;;
    --env)     ENV_SHORT="$2"; shift 2 ;;
    -h|--help) sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "ERROR: unknown arg $1" >&2; exit 2 ;;
  esac
done

REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-$DEFAULT_REGION}}"
POOL_NAME="midas-aigtw-${ENV_SHORT}-user-pool"
DOMAIN_NAME="midas-aigtw-${ENV_SHORT}-${ENV_SHORT}"

say() { printf '[cleanup] %s\n' "$*"; }
die() { printf '[cleanup][ERROR] %s\n' "$*" >&2; exit 1; }
run() {
  if $DRY_RUN; then
    printf '[cleanup][DRY-RUN] %s\n' "$*"
  else
    eval "$@" || say "WARN: command failed (continuing): $*"
  fi
}

# -------- safety: confirm AWS account ----------------------------------------
command -v aws >/dev/null 2>&1 || die "aws CLI not on PATH"
WHO_JSON="$(aws sts get-caller-identity --output json 2>&1)" || \
  die "aws sts get-caller-identity failed (run \`aws sso login --profile midas-dev\`):\n$WHO_JSON"
ACTUAL_ACCOUNT="$(printf '%s' "$WHO_JSON" | python3 -c "import json,sys;print(json.load(sys.stdin)['Account'])")"
[[ "$ACTUAL_ACCOUNT" == "$EXPECTED_ACCOUNT_ID" ]] || \
  die "auth is for account $ACTUAL_ACCOUNT, expected $EXPECTED_ACCOUNT_ID. Refusing to delete."
say "AWS auth OK: account=$ACTUAL_ACCOUNT region=$REGION"
say "Cluster: $CLUSTER  env: $ENV_SHORT  user-pool: $POOL_NAME  domain: $DOMAIN_NAME"

# -------- discovery ----------------------------------------------------------
say ""
say "==== Discovery ===="

EKS_EXISTS=""
aws eks describe-cluster --name "$CLUSTER" --region "$REGION" >/dev/null 2>&1 && EKS_EXISTS=yes
say "EKS cluster $CLUSTER: ${EKS_EXISTS:-absent}"

NODE_GROUPS=()
if [[ -n "$EKS_EXISTS" ]]; then
  while IFS= read -r ng; do [[ -n "$ng" ]] && NODE_GROUPS+=("$ng"); done < <(aws eks list-nodegroups --cluster-name "$CLUSTER" --region "$REGION" --query 'nodegroups[]' --output text 2>/dev/null | tr '\t' '\n')
  say "  node groups: ${NODE_GROUPS[*]:-<none>}"
fi

RDS_INSTANCES=()
while IFS= read -r _line; do [[ -n "$_line" ]] && RDS_INSTANCES+=("$_line"); done < <(aws rds describe-db-instances --region "$REGION" --query "DBInstances[?contains(DBInstanceIdentifier, '${CLUSTER}')].DBInstanceIdentifier" --output text | tr '\t' '\n' | grep .)
say "RDS instances: ${RDS_INSTANCES[*]:-<none>}"

REDIS_RG=()
while IFS= read -r _line; do [[ -n "$_line" ]] && REDIS_RG+=("$_line"); done < <(aws elasticache describe-replication-groups --region "$REGION" --query "ReplicationGroups[?contains(ReplicationGroupId, '${CLUSTER}') || contains(ReplicationGroupId, 'midas-aigtw')].ReplicationGroupId" --output text | tr '\t' '\n' | grep .)
say "ElastiCache replication groups: ${REDIS_RG[*]:-<none>}"

COGNITO_POOLS=()
while IFS= read -r _line; do [[ -n "$_line" ]] && COGNITO_POOLS+=("$_line"); done < <(aws cognito-idp list-user-pools --max-results 60 --region "$REGION" --query "UserPools[?Name=='${POOL_NAME}'].Id" --output text | tr '\t' '\n' | grep .)
say "Cognito user pools matching $POOL_NAME: ${COGNITO_POOLS[*]:-<none>}"

DOMAIN_POOL=""
DOMAIN_POOL=$(aws cognito-idp describe-user-pool-domain --domain "$DOMAIN_NAME" --region "$REGION" --query 'DomainDescription.UserPoolId' --output text 2>/dev/null || true)
[[ "$DOMAIN_POOL" == "None" ]] && DOMAIN_POOL=""
say "Cognito domain $DOMAIN_NAME attached to pool: ${DOMAIN_POOL:-<absent>}"

SECRETS=()
while IFS= read -r _line; do [[ -n "$_line" ]] && SECRETS+=("$_line"); done < <(aws secretsmanager list-secrets --region "$REGION" --query "SecretList[?contains(Name, '${CLUSTER}') || contains(Name, 'midas-aigtw')].Name" --output text | tr '\t' '\n' | grep .)
say "Secrets Manager secrets: ${#SECRETS[@]} found"
printf '   %s\n' "${SECRETS[@]:-<none>}" | head -25

SG_IDS=()
while IFS= read -r _line; do [[ -n "$_line" ]] && SG_IDS+=("$_line"); done < <(aws ec2 describe-security-groups --region "$REGION" --filters Name=vpc-id,Values=vpc-0c4d673f3e95a93eb --query "SecurityGroups[?contains(GroupName, '${CLUSTER}') || contains(GroupName, 'midas-aigtw') || contains(GroupName, 'midas-eks-aigtw')].GroupId" --output text | tr '\t' '\n' | grep .)
say "Security groups: ${SG_IDS[*]:-<none>}"

IAM_ROLES=()
while IFS= read -r _line; do [[ -n "$_line" ]] && IAM_ROLES+=("$_line"); done < <(aws iam list-roles --query "Roles[?contains(RoleName, '${CLUSTER}') || contains(RoleName, 'midas-aigtw')].RoleName" --output text | tr '\t' '\n' | grep .)
say "IAM roles: ${IAM_ROLES[*]:-<none>}"

IAM_POLICIES=()
while IFS= read -r _line; do [[ -n "$_line" ]] && IAM_POLICIES+=("$_line"); done < <(aws iam list-policies --scope Local --query "Policies[?contains(PolicyName, '${CLUSTER}') || contains(PolicyName, 'midas-aigtw')].Arn" --output text | tr '\t' '\n' | grep .)
say "IAM customer-managed policies: ${IAM_POLICIES[*]:-<none>}"

OIDC_PROVIDERS=()
while IFS= read -r _line; do [[ -n "$_line" ]] && OIDC_PROVIDERS+=("$_line"); done < <(aws iam list-open-id-connect-providers --query "OpenIDConnectProviderList[].Arn" --output text | tr '\t' '\n' | grep .)
EKS_OIDC_ARNS=()
if [[ -n "$EKS_EXISTS" ]]; then
  EKS_OIDC_URL=$(aws eks describe-cluster --name "$CLUSTER" --region "$REGION" --query 'cluster.identity.oidc.issuer' --output text 2>/dev/null | sed 's#https://##' || true)
  for arn in "${OIDC_PROVIDERS[@]:-}"; do
    [[ "$arn" == *"$EKS_OIDC_URL"* ]] && EKS_OIDC_ARNS+=("$arn")
  done
fi
say "EKS OIDC provider arns: ${EKS_OIDC_ARNS[*]:-<none>}"

KMS_ALIASES=()
while IFS= read -r _line; do [[ -n "$_line" ]] && KMS_ALIASES+=("$_line"); done < <(aws kms list-aliases --region "$REGION" --query "Aliases[?contains(AliasName, '${CLUSTER}') || contains(AliasName, 'midas-aigtw')].AliasName" --output text | tr '\t' '\n' | grep .)
say "KMS aliases: ${KMS_ALIASES[*]:-<none>}"

LOG_GROUPS=()
while IFS= read -r _line; do [[ -n "$_line" ]] && LOG_GROUPS+=("$_line"); done < <(aws logs describe-log-groups --region "$REGION" --query "logGroups[?contains(logGroupName, 'midas-aigtw') || contains(logGroupName, '${CLUSTER}')].logGroupName" --output text | tr '\t' '\n' | grep .)
say "CloudWatch log groups: ${LOG_GROUPS[*]:-<none>}"

ACM_CERT_ARNS=()
while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  arn=$(printf '%s' "$line" | awk '{print $1}')
  dom=$(printf '%s' "$line" | awk '{print $2}')
  if [[ "$dom" == *aigtw* || "$dom" == *midas-eks-aigtw* ]]; then
    ACM_CERT_ARNS+=("$arn")
  fi
done < <(aws acm list-certificates --region "$REGION" --query 'CertificateSummaryList[].[CertificateArn,DomainName]' --output text)
say "ACM certificates: ${ACM_CERT_ARNS[*]:-<none>}"

# EC2 Launch Templates (named exl-${cluster}-{ng,chng}-launch-template by upstream)
LAUNCH_TEMPLATES=()
while IFS= read -r _line; do [[ -n "$_line" ]] && LAUNCH_TEMPLATES+=("$_line"); done < <(aws ec2 describe-launch-templates --region "$REGION" --query "LaunchTemplates[?contains(LaunchTemplateName,'${CLUSTER}') || contains(LaunchTemplateName,'midas-aigtw')].LaunchTemplateName" --output text | tr '\t' '\n' | grep .)
say "EC2 Launch Templates: ${LAUNCH_TEMPLATES[*]:-<none>}"

# RDS DB subnet groups (upstream uses 'exlerate-db-subnet-group-${env}' — generic, not cluster-prefixed)
DB_SUBNET_GROUPS=()
while IFS= read -r _line; do [[ -n "$_line" ]] && DB_SUBNET_GROUPS+=("$_line"); done < <(aws rds describe-db-subnet-groups --region "$REGION" --query "DBSubnetGroups[?contains(DBSubnetGroupName,'exlerate-db-subnet-group-${ENV_SHORT}') || contains(DBSubnetGroupName,'${CLUSTER}')].DBSubnetGroupName" --output text | tr '\t' '\n' | grep .)
say "RDS DB subnet groups: ${DB_SUBNET_GROUPS[*]:-<none>}"

# ElastiCache subnet groups (upstream uses 'exlerate-redc-subnet-group-${env}')
EC_SUBNET_GROUPS=()
while IFS= read -r _line; do [[ -n "$_line" ]] && EC_SUBNET_GROUPS+=("$_line"); done < <(aws elasticache describe-cache-subnet-groups --region "$REGION" --query "CacheSubnetGroups[?contains(CacheSubnetGroupName,'exlerate-redc-subnet-group-${ENV_SHORT}') || contains(CacheSubnetGroupName,'${CLUSTER}')].CacheSubnetGroupName" --output text | tr '\t' '\n' | grep .)
say "ElastiCache subnet groups: ${EC_SUBNET_GROUPS[*]:-<none>}"

# ElastiCache users (upstream creates 'inference-user-${env}', 'langfuse-user-${env}', 'admin-user-${env}', and a default 'default')
EC_USERS=()
while IFS= read -r _line; do [[ -n "$_line" ]] && EC_USERS+=("$_line"); done < <(aws elasticache describe-users --region "$REGION" --query "Users[?UserId!='default' && (contains(UserId,'-${ENV_SHORT}') || contains(UserId,'${CLUSTER}'))].UserId" --output text | tr '\t' '\n' | grep .)
say "ElastiCache users: ${EC_USERS[*]:-<none>}"

# ElastiCache user groups
EC_USER_GROUPS=()
while IFS= read -r _line; do [[ -n "$_line" ]] && EC_USER_GROUPS+=("$_line"); done < <(aws elasticache describe-user-groups --region "$REGION" --query "UserGroups[?contains(UserGroupId,'-${ENV_SHORT}') || contains(UserGroupId,'${CLUSTER}')].UserGroupId" --output text | tr '\t' '\n' | grep .)
say "ElastiCache user groups: ${EC_USER_GROUPS[*]:-<none>}"

# S3 buckets (upstream creates '${cluster}-{access-log,log,langfuse-data,langfuse-media,ai-gateway-litellm-config-${region}}' buckets)
S3_BUCKETS=()
while IFS= read -r _line; do [[ -n "$_line" ]] && S3_BUCKETS+=("$_line"); done < <(aws s3api list-buckets --query "Buckets[?contains(Name,'${CLUSTER}') || contains(Name,'midas-aigtw')].Name" --output text | tr '\t' '\n' | grep .)
say "S3 buckets: ${S3_BUCKETS[*]:-<none>}"

# Extra dedicated secrets that don't carry the cluster name (e.g. jfrog-regcred is global per the upstream module)
EXTRA_SECRETS=()
for s in jfrog-regcred; do
  if aws secretsmanager describe-secret --secret-id "$s" --region "$REGION" >/dev/null 2>&1; then
    EXTRA_SECRETS+=("$s")
  fi
done
say "Extra fixed-name secrets: ${EXTRA_SECRETS[*]:-<none>}"

# ELBv2 NLBs/ALBs (must be deleted BEFORE custom SGs because their ENIs hold SG refs).
# NLBs default to deletion-protection ON in upstream Terraform, so disable it first.
LB_ARNS=()
while IFS= read -r _line; do [[ -n "$_line" ]] && LB_ARNS+=("$_line"); done < <(aws elbv2 describe-load-balancers --region "$REGION" --query "LoadBalancers[?contains(LoadBalancerName, '${CLUSTER}') || contains(LoadBalancerName, 'midas-aigtw')].LoadBalancerArn" --output text | tr '\t' '\n' | grep .)
say "ELBv2 load balancers: ${LB_ARNS[*]:-<none>}"

# -------- confirmation -------------------------------------------------------
if ! $DRY_RUN && ! $ASSUME_YES; then
  say ""
  read -r -p "Type 'DELETE' to proceed (or anything else to abort): " CONFIRM
  [[ "$CONFIRM" == "DELETE" ]] || die "aborted by operator"
fi

# -------- deletion order (deps first → owners last) --------------------------
say ""
say "==== Deletion ===="

# 1. EKS node groups → cluster (cluster delete blocks while NGs exist)
for ng in "${NODE_GROUPS[@]}"; do
  run "aws eks delete-nodegroup --cluster-name '$CLUSTER' --nodegroup-name '$ng' --region '$REGION' >/dev/null"
done
if [[ -n "$EKS_EXISTS" && ${#NODE_GROUPS[@]} -gt 0 ]] && ! $DRY_RUN; then
  for ng in "${NODE_GROUPS[@]}"; do
    say "waiting for nodegroup $ng to delete (~3 min) ..."
    aws eks wait nodegroup-deleted --cluster-name "$CLUSTER" --nodegroup-name "$ng" --region "$REGION" || true
  done
fi
if [[ -n "$EKS_EXISTS" ]]; then
  run "aws eks delete-cluster --name '$CLUSTER' --region '$REGION' >/dev/null"
fi

# 2. RDS instances (parallel; final snapshot skipped because skip_final_snapshot_flag=true)
for db in "${RDS_INSTANCES[@]}"; do
  run "aws rds delete-db-instance --db-instance-identifier '$db' --skip-final-snapshot --delete-automated-backups --region '$REGION' >/dev/null"
done

# 3. ElastiCache replication groups (parallel)
for rg in "${REDIS_RG[@]}"; do
  run "aws elasticache delete-replication-group --replication-group-id '$rg' --region '$REGION' >/dev/null"
done

# 3b. ELBv2 load balancers (disable deletion protection first; ENIs free in ~30-60s after delete)
for arn in "${LB_ARNS[@]}"; do
  run "aws elbv2 modify-load-balancer-attributes --load-balancer-arn '$arn' --attributes Key=deletion_protection.enabled,Value=false --region '$REGION' >/dev/null"
  run "aws elbv2 delete-load-balancer --load-balancer-arn '$arn' --region '$REGION' >/dev/null"
done

# 4. Cognito domain → users → pools
if [[ -n "$DOMAIN_POOL" ]]; then
  run "aws cognito-idp delete-user-pool-domain --domain '$DOMAIN_NAME' --user-pool-id '$DOMAIN_POOL' --region '$REGION' >/dev/null"
fi
for pool in "${COGNITO_POOLS[@]}"; do
  while IFS= read -r client_id; do
    [[ -z "$client_id" ]] && continue
    run "aws cognito-idp delete-user-pool-client --user-pool-id '$pool' --client-id '$client_id' --region '$REGION' >/dev/null"
  done < <(aws cognito-idp list-user-pool-clients --user-pool-id "$pool" --region "$REGION" --max-results 60 --query 'UserPoolClients[].ClientId' --output text 2>/dev/null | tr '\t' '\n')
  run "aws cognito-idp delete-user-pool --user-pool-id '$pool' --region '$REGION' >/dev/null"
done

# 5. Secrets — force delete (no recovery window so next apply can recreate same name)
for s in "${SECRETS[@]}"; do
  run "aws secretsmanager delete-secret --secret-id '$s' --force-delete-without-recovery --region '$REGION' >/dev/null"
done

# 6. wait for EKS / RDS / Redis to finish before SG deletion (SGs are referenced by these)
if ! $DRY_RUN; then
  if [[ -n "$EKS_EXISTS" ]]; then
    say "waiting for EKS cluster $CLUSTER to delete (~10-15 min) ..."
    aws eks wait cluster-deleted --name "$CLUSTER" --region "$REGION" || true
  fi
  for db in "${RDS_INSTANCES[@]}"; do
    say "waiting for RDS $db to delete (~5 min) ..."
    aws rds wait db-instance-deleted --db-instance-identifier "$db" --region "$REGION" || true
  done
  for rg in "${REDIS_RG[@]}"; do
    say "waiting for Redis $rg to delete (~10 min) ..."
    while aws elasticache describe-replication-groups --replication-group-id "$rg" --region "$REGION" >/dev/null 2>&1; do
      sleep 30
    done
  done
fi

# 7. CloudWatch log groups (left behind by EKS/RDS) — must come AFTER cluster delete
for lg in "${LOG_GROUPS[@]}"; do
  run "aws logs delete-log-group --log-group-name '$lg' --region '$REGION' >/dev/null"
done

# 8. Wait for NLB ENIs to release (NLB delete is async; ENIs hold SG refs for ~30-60s)
if ! $DRY_RUN && [[ ${#LB_ARNS[@]} -gt 0 ]]; then
  for i in $(seq 1 20); do
    SG_FILTER=$(IFS=,; echo "${SG_IDS[*]}")
    [[ -z "$SG_FILTER" ]] && break
    REM=$(aws ec2 describe-network-interfaces --region "$REGION" --filters "Name=group-id,Values=${SG_FILTER}" --query 'NetworkInterfaces[].NetworkInterfaceId' --output text 2>/dev/null | tr '\t\n' '  ' | xargs)
    [[ -z "$REM" ]] && { say "NLB ENIs released"; break; }
    say "[${i}/20] waiting for NLB ENIs to detach: $REM"
    sleep 30
  done
fi

# 9. Custom SGs (in dependency order: ALB SGs reference cluster SG; cluster SG self-refs)
#    Try one pass to revoke any cross-SG rules first, then delete.
for sgid in "${SG_IDS[@]}"; do
  while IFS= read -r rule_id; do
    [[ -z "$rule_id" ]] && continue
    run "aws ec2 revoke-security-group-ingress --group-id '$sgid' --security-group-rule-ids '$rule_id' --region '$REGION' >/dev/null"
  done < <(aws ec2 describe-security-group-rules --filters "Name=group-id,Values=${sgid}" --region "$REGION" --query 'SecurityGroupRules[?IsEgress==`false`].SecurityGroupRuleId' --output text 2>/dev/null | tr '\t' '\n')
done
for sgid in "${SG_IDS[@]}"; do
  run "aws ec2 delete-security-group --group-id '$sgid' --region '$REGION' >/dev/null"
done

# 10. EKS OIDC providers
for arn in "${EKS_OIDC_ARNS[@]}"; do
  run "aws iam delete-open-id-connect-provider --open-id-connect-provider-arn '$arn' >/dev/null"
done

# 11. IAM roles (detach managed + delete inline + then delete)
for role in "${IAM_ROLES[@]}"; do
  while IFS= read -r pa; do
    [[ -z "$pa" ]] && continue
    run "aws iam detach-role-policy --role-name '$role' --policy-arn '$pa' >/dev/null"
  done < <(aws iam list-attached-role-policies --role-name "$role" --query 'AttachedPolicies[].PolicyArn' --output text 2>/dev/null | tr '\t' '\n')
  while IFS= read -r ip; do
    [[ -z "$ip" ]] && continue
    run "aws iam delete-role-policy --role-name '$role' --policy-name '$ip' >/dev/null"
  done < <(aws iam list-role-policies --role-name "$role" --query 'PolicyNames[]' --output text 2>/dev/null | tr '\t' '\n')
  while IFS= read -r ip; do
    [[ -z "$ip" ]] && continue
    run "aws iam remove-role-from-instance-profile --instance-profile-name '$ip' --role-name '$role' >/dev/null"
    run "aws iam delete-instance-profile --instance-profile-name '$ip' >/dev/null"
  done < <(aws iam list-instance-profiles-for-role --role-name "$role" --query 'InstanceProfiles[].InstanceProfileName' --output text 2>/dev/null | tr '\t' '\n')
  run "aws iam delete-role --role-name '$role' >/dev/null"
done

# 12. IAM customer-managed policies (after roles, no longer attached)
for pa in "${IAM_POLICIES[@]}"; do
  while IFS= read -r v; do
    [[ -z "$v" || "$v" == "None" ]] && continue
    run "aws iam delete-policy-version --policy-arn '$pa' --version-id '$v' >/dev/null"
  done < <(aws iam list-policy-versions --policy-arn "$pa" --query 'Versions[?!IsDefaultVersion].VersionId' --output text 2>/dev/null | tr '\t' '\n')
  run "aws iam delete-policy --policy-arn '$pa' >/dev/null"
done

# 13. KMS aliases (and schedule deletion of underlying keys with 7-day window)
for alias in "${KMS_ALIASES[@]}"; do
  KEY_ID=$(aws kms list-aliases --region "$REGION" --query "Aliases[?AliasName=='${alias}'].TargetKeyId" --output text 2>/dev/null)
  run "aws kms delete-alias --alias-name '$alias' --region '$REGION' >/dev/null"
  if [[ -n "$KEY_ID" && "$KEY_ID" != "None" ]]; then
    run "aws kms schedule-key-deletion --key-id '$KEY_ID' --pending-window-in-days 7 --region '$REGION' >/dev/null"
  fi
done

# 14. ACM certs
for arn in "${ACM_CERT_ARNS[@]}"; do
  run "aws acm delete-certificate --certificate-arn '$arn' --region '$REGION' >/dev/null"
done

# 15. EC2 Launch Templates (no dependencies after node groups gone)
for lt in "${LAUNCH_TEMPLATES[@]}"; do
  run "aws ec2 delete-launch-template --launch-template-name '$lt' --region '$REGION' >/dev/null"
done

# 16. RDS DB subnet groups (after RDS instances gone)
for g in "${DB_SUBNET_GROUPS[@]}"; do
  run "aws rds delete-db-subnet-group --db-subnet-group-name '$g' --region '$REGION' >/dev/null"
done

# 17. ElastiCache user groups (must come before users)
for ug in "${EC_USER_GROUPS[@]}"; do
  run "aws elasticache delete-user-group --user-group-id '$ug' --region '$REGION' >/dev/null"
done
if ! $DRY_RUN; then
  for ug in "${EC_USER_GROUPS[@]}"; do
    while aws elasticache describe-user-groups --user-group-id "$ug" --region "$REGION" >/dev/null 2>&1; do sleep 10; done
  done
fi

# 18. ElastiCache users
for u in "${EC_USERS[@]}"; do
  run "aws elasticache delete-user --user-id '$u' --region '$REGION' >/dev/null"
done

# 19. ElastiCache subnet groups (after replication groups gone)
for g in "${EC_SUBNET_GROUPS[@]}"; do
  run "aws elasticache delete-cache-subnet-group --cache-subnet-group-name '$g' --region '$REGION' >/dev/null"
done

# 20. S3 buckets — empty (delete all object versions and delete-markers) then delete bucket.
#     Only touches buckets discovered by the name filter; SHARED buckets are not in this list.
for b in "${S3_BUCKETS[@]}"; do
  if $DRY_RUN; then
    say "[cleanup][DRY-RUN] would empty + delete s3://$b"
    continue
  fi
  say "emptying s3://$b ..."
  # delete object versions
  while IFS= read -r line; do
    key=$(printf '%s' "$line" | awk -F'\t' '{print $1}')
    ver=$(printf '%s' "$line" | awk -F'\t' '{print $2}')
    [[ -z "$key" || -z "$ver" ]] && continue
    aws s3api delete-object --bucket "$b" --key "$key" --version-id "$ver" >/dev/null 2>&1 || true
  done < <(aws s3api list-object-versions --bucket "$b" --query 'Versions[].[Key,VersionId]' --output text 2>/dev/null | grep -v '^None')
  # delete delete-markers
  while IFS= read -r line; do
    key=$(printf '%s' "$line" | awk -F'\t' '{print $1}')
    ver=$(printf '%s' "$line" | awk -F'\t' '{print $2}')
    [[ -z "$key" || -z "$ver" ]] && continue
    aws s3api delete-object --bucket "$b" --key "$key" --version-id "$ver" >/dev/null 2>&1 || true
  done < <(aws s3api list-object-versions --bucket "$b" --query 'DeleteMarkers[].[Key,VersionId]' --output text 2>/dev/null | grep -v '^None')
  run "aws s3api delete-bucket --bucket '$b' --region '$REGION' >/dev/null"
done

# 21. Extra fixed-name secrets (jfrog-regcred etc.)
for s in "${EXTRA_SECRETS[@]}"; do
  run "aws secretsmanager delete-secret --secret-id '$s' --force-delete-without-recovery --region '$REGION' >/dev/null"
done

# 22. STALE TF STATE — remove the bootstrap-prefix object so the next terragrunt apply
#     starts from an empty state. The bucket is SHARED (midas-dev-...-terraform-...);
#     we ONLY touch the 'aigtw/' prefix, which is exclusively ours per terragrunt.hcl.
TF_STATE_BUCKET="midas-dev-us-east-1-terraform-${EXPECTED_ACCOUNT_ID}"
TF_STATE_PREFIX="aigtw/"
if aws s3api head-bucket --bucket "$TF_STATE_BUCKET" >/dev/null 2>&1; then
  say "removing TF state objects under s3://$TF_STATE_BUCKET/$TF_STATE_PREFIX"
  if $DRY_RUN; then
    aws s3 ls "s3://$TF_STATE_BUCKET/$TF_STATE_PREFIX" --recursive 2>/dev/null | sed 's/^/  [cleanup][DRY-RUN] would delete: /'
  else
    # versioned bucket — wipe all versions and delete-markers under the prefix
    while IFS= read -r line; do
      key=$(printf '%s' "$line" | awk -F'\t' '{print $1}')
      ver=$(printf '%s' "$line" | awk -F'\t' '{print $2}')
      [[ -z "$key" || -z "$ver" ]] && continue
      aws s3api delete-object --bucket "$TF_STATE_BUCKET" --key "$key" --version-id "$ver" >/dev/null 2>&1 || true
    done < <(aws s3api list-object-versions --bucket "$TF_STATE_BUCKET" --prefix "$TF_STATE_PREFIX" --query 'Versions[].[Key,VersionId]' --output text 2>/dev/null | grep -v '^None')
    while IFS= read -r line; do
      key=$(printf '%s' "$line" | awk -F'\t' '{print $1}')
      ver=$(printf '%s' "$line" | awk -F'\t' '{print $2}')
      [[ -z "$key" || -z "$ver" ]] && continue
      aws s3api delete-object --bucket "$TF_STATE_BUCKET" --key "$key" --version-id "$ver" >/dev/null 2>&1 || true
    done < <(aws s3api list-object-versions --bucket "$TF_STATE_BUCKET" --prefix "$TF_STATE_PREFIX" --query 'DeleteMarkers[].[Key,VersionId]' --output text 2>/dev/null | grep -v '^None')
  fi
fi

say ""
say "==== Cleanup complete ===="
say "Re-trigger midas-ai-gateway-tf-deploy-ORD1 with TF_ACTION=apply now."
