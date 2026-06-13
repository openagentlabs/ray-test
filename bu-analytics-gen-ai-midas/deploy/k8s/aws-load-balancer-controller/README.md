> **NOTE (as of commit 89d76bca):** The AWS Load Balancer Controller is now installed by
> **Terraform** (`deploy/ecs-app/eks-alb-controller-helm.tf`) and TargetGroupBindings are
> managed by `deploy/ecs-app/eks-tgb.tf`. The manual installation steps below are preserved
> for reference only — **do not run them manually on a Terraform-managed cluster**.

# AWS Load Balancer Controller (EKS) - internal ALB only

This directory documents installing the [AWS Load Balancer Controller](https://kubernetes-sigs.github.io/aws-load-balancer-controller/) after Terraform creates **IRSA** (see `deploy/ecs-app/eks-alb-controller.tf` and `deploy/ecs-app/modules/eks-alb-controller-iam/`).

## Policy (MIDAS)

- **Internal ALBs only:** every `Ingress` must use **`alb.ingress.kubernetes.io/scheme: internal`**. Do **not** deploy internet-facing ALBs from this pattern.
- **Subnets (TargetGroupBinding pattern):** the `alb-nlb` module specifies subnets explicitly in `aws_lb`; no subnet tagging is required for `TargetGroupBinding` usage. Subnet tags are only needed when using Ingress-based auto-discovery.
- **Who tags subnets:** if you ever switch to Ingress-based routing, coordinate with the network team before tagging shared subnets.

## How MIDAS uses this controller (TargetGroupBinding pattern)

MIDAS uses the **Terraform-managed static ALB + NLB** pattern (Option B1). The controller is **not** used to create or manage ALBs via `Ingress` objects. It is used only for `TargetGroupBinding` CRDs, which keep the ALB target groups (created by Terraform) in sync with live pod IPs as pods are created, replaced, or deleted.

```
Terraform creates: NLB → ALB → Target Groups (frontend/backend/graph)
Controller watches: Kubernetes Service Endpoints
Controller calls:   RegisterTargets / DeregisterTargets automatically
Result:             ALB target groups always contain current pod IPs
```

## Prerequisites

- `kubectl` configured against the cluster (e.g. jump box + `aws eks update-kubeconfig`).
- Terraform applied with `alb_nlb_enabled = true` so outputs exist (see `terraform output` in `deploy/ecs-app`).
- Helm 3.x on the machine running install (pre-installed on jumpbox via user_data).

## Step 1 — Get Terraform outputs

```bash
cd deploy/ecs-app
terraform output eks_aws_load_balancer_controller_role_arn
terraform output eks_cluster_name
terraform output alb_frontend_target_group_arn
terraform output alb_backend_target_group_arn
terraform output alb_graph_target_group_arn
terraform output alb_dns_name
terraform output nlb_dns_name
```

Keep these values; you will need the role ARN for Helm and the TG ARNs for the TargetGroupBinding manifests.

## Step 2 — Configure kubectl on the jumpbox

```bash
# Start an SSM shell session on the jumpbox
aws ssm start-session --target i-04231b2a8a4d98b63 --region us-east-1

# On the jumpbox — replace CLUSTER_NAME with the terraform output value
aws eks update-kubeconfig --name <CLUSTER_NAME> --region us-east-1
kubectl get nodes   # confirm cluster access
kubectl get ns      # confirm midas-apps namespace exists
```

## Step 3 — Install AWS Load Balancer Controller (Helm)

The pipeline **`Jenkinsfile_Deploy_App`** does **not** run Helm by default; run from the jumpbox or a trusted operator workstation.

```bash
helm repo add eks https://aws.github.io/eks-charts
helm repo update

# Replace ROLE_ARN and CLUSTER_NAME with terraform output values
helm upgrade --install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --create-namespace \
  --set clusterName=<CLUSTER_NAME> \
  --set serviceAccount.create=true \
  --set "serviceAccount.annotations.eks\.amazonaws\.com/role-arn=<ROLE_ARN>" \
  --set region=us-east-1 \
  --set vpcId=vpc-0c4d673f3e95a93eb \
  --set defaultTargetType=ip \
  --version 1.8.1
```

Pin the chart version to your change process; check [eks-charts releases](https://github.com/aws/eks-charts) for updates.

```bash
# Verify the controller is running
kubectl -n kube-system rollout status deploy/aws-load-balancer-controller
kubectl -n kube-system get pods -l app.kubernetes.io/name=aws-load-balancer-controller
```

## Step 4 — Verify the TargetGroupBinding CRD is available

```bash
kubectl get crd targetgroupbindings.elbv2.k8s.aws
# Must return the CRD before proceeding
```

## Step 5 — Apply TargetGroupBinding manifests

Edit `deploy/k8s/ingress/targetgroupbinding-*.yaml` and substitute the TG ARNs from Step 1:

```bash
# Edit each file - replace REPLACE_WITH_terraform_output_* with actual ARNs
vi deploy/k8s/ingress/targetgroupbinding-frontend.yaml
vi deploy/k8s/ingress/targetgroupbinding-backend.yaml
vi deploy/k8s/ingress/targetgroupbinding-graph.yaml

# Apply all three
kubectl apply -f deploy/k8s/ingress/ -n midas-apps
```

Verify the controller has reconciled and pods are registered:

```bash
kubectl get targetgroupbinding -n midas-apps
kubectl describe targetgroupbinding midas-frontend-tgb -n midas-apps
kubectl describe targetgroupbinding midas-backend-tgb -n midas-apps
kubectl describe targetgroupbinding midas-graph-tgb -n midas-apps

# Check ALB target health in AWS console or CLI
aws elbv2 describe-target-health \
  --target-group-arn <alb_frontend_target_group_arn> \
  --region us-east-1
```

## Step 6 — Test via SSM port-forward from laptop

```bash
# Get the NLB DNS name
NLB_DNS=$(cd deploy/ecs-app && terraform output -raw nlb_dns_name)
ALB_DNS=$(cd deploy/ecs-app && terraform output -raw alb_dns_name)

# Forward laptop:9080 → jumpbox → NLB:80
python3 deploy/scripts/util/aws-ssm-port-forward-frontend.py \
  --host "$NLB_DNS" --port 80 --local-port 9080

# In browser:
#   http://localhost:9080/frontend      → MIDAS frontend UI
#   http://localhost:9080/backend/health → {"status":"healthy",...}
#   http://localhost:9080/graph/health   → {"status":"ok",...}

# Forward directly to ALB (bypass NLB layer)
python3 deploy/scripts/util/aws-ssm-port-forward-frontend.py \
  --host "$ALB_DNS" --port 80 --local-port 9081

# In browser:
#   http://localhost:9081/frontend
#   http://localhost:9081/backend/health
#   http://localhost:9081/graph/health
```

## Acceptance criteria

| # | Test | Expected result |
|---|------|-----------------|
| 1 | `kubectl get targetgroupbinding -n midas-apps` | 3 bindings, all `SYNCED` |
| 2 | `aws elbv2 describe-target-health --target-group-arn <fe-tg-arn>` | At least 1 target `healthy` |
| 3 | `http://localhost:9080/frontend` (via NLB tunnel) | MIDAS React UI loads |
| 4 | `http://localhost:9080/backend/health` | `{"status":"healthy"}` HTTP 200 |
| 5 | `http://localhost:9080/graph/health` | `{"status":"ok"}` HTTP 200 |
| 6 | `http://localhost:9081/frontend` (direct ALB tunnel) | MIDAS React UI loads |
| 7 | `http://localhost:9081/backend/health` | HTTP 200 |
| 8 | `http://localhost:9081/graph/health` | HTTP 200 |

## Files

| File | Purpose |
|------|---------|
| `values-internal.yaml.example` | Helm values: IRSA role, cluster name, VPC, **internal-only** posture |
| `sample-ingressclass.yaml` | `IngressClass` for `ingress.k8s.aws/alb` (not used in TargetGroupBinding pattern) |
| `sample-ingress.yaml` | Example `Ingress` with `scheme: internal` (not used in TargetGroupBinding pattern) |
| `deploy/k8s/ingress/targetgroupbinding-frontend.yaml` | TGB for frontend service (port 80 → pod 8080) |
| `deploy/k8s/ingress/targetgroupbinding-backend.yaml` | TGB for backend service (port 8000) |
| `deploy/k8s/ingress/targetgroupbinding-graph.yaml` | TGB for graph service (port 8001) |
