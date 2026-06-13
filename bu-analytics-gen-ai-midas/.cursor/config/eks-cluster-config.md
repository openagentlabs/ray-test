# EKS cluster configuration (MIDAS - development)

Authoritative networking inputs for the **`module "eks"`** stack under **`deploy/ecs-app/`** (`deploy/ecs-app/modules/eks/`, registered in **`deploy/ecs-app/eks.tf`**). Region: **us-east-1** only.

## Purpose

- Private corporate VPC; **no public Kubernetes API** (`endpoint_public_access = false`).
- **Managed EC2 node group** (not Fargate) sized for **development** workloads.
- Deployed with the **`deploy/ecs-app/`** root (same state as the rest of the app stack; see `deploy/README.md`).

## Network (fixed / required)

| Item | Value | Notes |
|------|--------|--------|
| VPC | `vpc-0c4d673f3e95a93eb` | MIDAS DEV snapshot name tag: `aws03-811391286931-ins-ai-MIDAS-DEV-DEV-vpc` |
| Required subnet (user) | `subnet-04d9f5b09b2dc9425` | us-east-1c, SubnetGroup 1 - **must** appear in `cluster_subnet_ids` |
| Paired subnet (AWS requirement) | `subnet-05c4fce53e16da9bc` | us-east-1a, SubnetGroup 1 - **EKS managed node groups require subnets in ≥2 AZs** |

**You cannot deploy a managed node group with only one subnet.** Keep both subnets above in `cluster_subnet_ids` unless networking approves a different second AZ.

## Terraform variables (summary)

| Variable | Dev default / intent |
|----------|----------------------|
| `environment` | `dev` |
| `cluster_name_prefix` (`eks_cluster_name_prefix` at ecs-app root) | `midas-eks` → cluster name `midas-eks-dev` |
| `vpc_id` (`eks_vpc_id` at ecs-app root) | `vpc-0c4d673f3e95a93eb` |
| `cluster_subnet_ids` (`eks_cluster_subnet_ids` at ecs-app root) | `[subnet-05c4fce53e16da9bc, subnet-04d9f5b09b2dc9425]` |
| `node_subnet_ids` | Omit (defaults to same as cluster subnets) |
| `kubernetes_version` | `1.30` (adjust as supported by EKS; must match `deploy/ecs-app/modules/eks`) |
| `endpoint_public_access` | `false` (fixed in `deploy/ecs-app/modules/eks/main.tf`) |
| `node_instance_types` (via `eks_node_instance_types` at ecs-app root) | `["m6i.4xlarge"]` (16 vCPU, 64 GiB per worker) |
| `node_desired_size` / `min` / `max` | `2` / `1` / `4` |
| `node_disk_size` | `50` GiB |
| `node_capacity_type` | `ON_DEMAND` |
| `attach_ssm_policy_to_nodes` | `true` (SSM for troubleshooting) |

## AWS resources created by Terraform

- IAM: cluster role + node role (with `AmazonSSMManagedInstanceCore` optional).
- CloudWatch log group `/aws/eks/{cluster}/cluster` for control plane logs.
- `aws_eks_cluster` (private API only).
- `aws_eks_node_group` (managed, EC2).

EKS-managed **cluster security group** is used (no custom node SG in this template; avoids launch-template-only SG wiring on AWS provider v6).

## IAM for pipeline

Deployer policies: ten files `deploy/deploy_role/iam-policy/midas-deployer-policy-001` … `010` include EKS/RDS/ElastiCache/Secrets Manager statements (search for `Sid` e.g. `EksClusterAndNodeGroup`). Apply `deploy/deploy_role/` before `deploy/ecs-app/` so `midas-deployer-role` can create the cluster and node group.

## State backend

EKS resources use the **same** `deploy/ecs-app/` remote state as the rest of the app stack (`app-deploy-omf-<TENANT_ENV>/<TENANT_ID>/terraform.tfstate` in the pipeline).

## References

- Workspace VPC snapshot: `.cursor/rules/solution_const.mdc` (Section “us-east-1 MIDAS VPC”).
- Endpoint checks from a probe instance: `.cursor/skills/kt_check_endpoint_for_eks_node_attach/SKILL.md`.
