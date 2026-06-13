# Runbook: EKS node group `ResourceInUseException` (409) on Terraform apply

## Root cause

Terraform tries **`CreateNodegroup`** for `module.eks.aws_eks_node_group.this`, but AWS already has a managed node group with the same **`cluster_name` + `node_group_name`**. That happens when:

- The node group exists in the account but **is not in the remote Terraform state** for this workspace (state drift, state key change, manual creation, or failed prior operation).

Terraform logs:

```text
Error: creating EKS Node Group (...): ... ResourceInUseException: NodeGroup already exists with name midas-eks-<env>-ng and cluster name midas-eks-<env>
```

## Fix

**Adopt** the existing node group into state with **`terraform import`** using the AWS provider ID format:

```text
<cluster_name>:<node_group_name>
```

Example for **`TENANT_ENV=dev`**:

```text
midas-eks-dev:midas-eks-dev-ng
```

Resource address:

```text
module.eks.aws_eks_node_group.this
```

### Jenkins (automatic)

[`deploy/Jenkinsfile_Deploy_App`](../Jenkinsfile_Deploy_App) runs the same **`aws eks describe-nodegroup`** check and **`terraform import`** **before** `terraform plan` when the group exists in AWS but not in state—matching the pattern used for the Kubernetes secret, frontend Secrets Manager secret, and ALB Helm release.

### Manual repair (same backend and vars as Jenkins)

From `deploy/ecs-app` after `terraform init` with the correct **S3 backend** (`bucket`, `key=app-deploy-omf-${TENANT_ENV}/${TENANT_ID}/terraform.tfstate`, `region`), run **`import`** with the **same** `-var-file` and `-var` arguments your environment uses for **`terraform plan`** (see Jenkinsfile). Example skeleton:

```bash
terraform import -input=false \
  -var-file=tfvars/midas-cross-network-db-access.tfvars \
  -var-file=tfvars/dev.tfvars \
  -var "aws_account_id=..." \
  -var "environment=dev" \
  -var "terraform_state_bucket=..." \
  -var "aws_region=us-east-1" \
  -var "alb_nlb_enabled=true" \
  'module.eks.aws_eks_node_group.this' \
  'midas-eks-dev:midas-eks-dev-ng'
```

Then run **`terraform plan`**; you should see **updates** to the node group (e.g. instance type) rather than **create**.

### kubectl verification (MIDAS requirement)

After apply, use **AWS CLI + SSM on the jumpbox** for **`kubectl`** (see [`.cursor/rules/debuging/debug.mdc`](../../.cursor/rules/debuging/debug.mdc)), not the private API from an unrestricted laptop path.
