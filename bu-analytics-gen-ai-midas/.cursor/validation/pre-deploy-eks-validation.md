# Pre-deploy validation - EKS (`deploy/ecs-app/modules/eks/`)

Run **before** `terraform apply` on **`deploy/ecs-app/`** (includes `module "eks"`). If any **hard** check fails, **stop** and fix networking/IAM/config; do not apply.

## Config source of truth

Match every check below to `.cursor/config/eks-cluster-config.md` and root variables in `deploy/ecs-app/variables.tf` (optional overrides in `deploy/ecs-app/tfvars/*.tfvars`).

## 1. AWS identity and region (CLI)

| Step | Command / action | Pass criteria |
|------|------------------|---------------|
| Caller | `aws sts get-caller-identity` | Account ID matches workload account (e.g. `811391286931` for MIDAS dev). |
| Region | `echo $AWS_REGION` or `--region us-east-1` | **us-east-1** only. |

## 2. VPC

| Step | Command | Pass criteria |
|------|---------|---------------|
| Exists | `aws ec2 describe-vpcs --vpc-ids vpc-0c4d673f3e95a93eb` | Returns exactly one VPC; state `available`. |

## 3. Subnets (must match config)

For **each** subnet ID in `cluster_subnet_ids` (and node subnets if different):

| Step | Command | Pass criteria |
|------|---------|---------------|
| Membership | `aws ec2 describe-subnets --subnet-ids <id>` | `VpcId` = `vpc-0c4d673f3e95a93eb`. |
| AZ coverage | Collect `AvailabilityZone` for all subnet IDs | **At least two distinct AZs** (managed node group requirement). |
| Routing | Review with network team / `describe-route-tables` | Private workload subnets; egress aligns with TGW/corporate design (no ad-hoc IGW for this use case). |

## 4. EKS feasibility (documentation checks)

| Check | Pass criteria |
|-------|----------------|
| Private API only | Terraform has `endpoint_public_access = false`; kubectl/API access only from networks that can reach the private EKS endpoint (VPN, jump host, or interface endpoint if used). |
| Endpoints | Corporate VPC already has required interface endpoints for nodes/control plane per your network design (see historical probe docs under `docs/` if applicable). |
| IAM | `deploy/deploy_role` applied with ten policies (`midas-deployer-policy-001` … `010`); role can `PassRole` to roles named like `midas-eks-*-cluster` / `midas-eks-*-node`. |

## 5. Terraform hygiene

| Step | Pass criteria |
|------|----------------|
| `terraform fmt` | Clean under `deploy/ecs-app/` (including `modules/eks/`). |
| `terraform validate` | Succeeds (with `terraform init` and appropriate backend). |
| Variables | `terraform.tfvars` (not committed) defines `vpc_id`, `cluster_subnet_ids`, `environment`, `aws_account_id`, `terraform_state_bucket`. |

## Failure handling

If a hard check fails, record: failing check, command output (redacted), and required remediation. Do **not** apply Terraform until the environment matches this checklist.

## Automation

Run: `.cursor/scripts/pre-deploy-validate-eks.sh` (uses AWS CLI; optional env vars documented in the script).
