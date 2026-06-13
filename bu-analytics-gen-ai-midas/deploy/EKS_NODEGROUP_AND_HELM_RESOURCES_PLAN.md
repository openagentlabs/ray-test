# EKS node group + MIDAS Helm sizing (full plan and code inventory)

This document tracks **Terraform and Helm** under `deploy/ecs-app/` for the MIDAS EKS worker shape and backend pod sizing. **Frontend** and **graph** charts stay without CPU or memory requests in their default `values.yaml`.

---

## Goals

1. **Terraform:** EKS managed node group default **`["m6i.4xlarge"]`** (16 vCPU, 64 GiB RAM per instance), **two workers** by default (`eks_node_desired_size` = 2, **`eks_node_min_size` = 2** so the ASG cannot shrink below two identical workers), tunable via `eks_node_*` variables. `eks-node-scaling-checks.tf` asserts `min <= desired <= max` and the two-worker floor.
2. **Helm (backend):** Guaranteed QoS, **`resources.requests` == `resources.limits`**, default **`14600m` CPU** and **`53Gi` memory**, sized below typical node **Allocatable** so the pod schedules with slack for kube-system DaemonSets on the same node.
3. **Helm (frontend / graph):** **`resources: {}`**, scheduling uses node capacity.
4. **Application:** **`webConcurrency`** in `midas-api-backend-svc/values.yaml` (default **3**; override per env for SQLite-only or other experiments). Higher values increase per-process RAM; keep pod `resources` within the node Allocatable slack described in that chart.

---

## Terraform changes (inventory)

| File | Role |
|------|------|
| [`ecs-app/variables.tf`](ecs-app/variables.tf) | **`eks_node_instance_types`** default `["m6i.4xlarge"]`, **`eks_node_desired_size` / `min` / `max`**, descriptions aligned with backend Helm resources. |
| [`ecs-app/eks-node-scaling-checks.tf`](ecs-app/eks-node-scaling-checks.tf) | **`check`** blocks: `min <= desired <= max`, two-worker floor (`desired >= 2`, `min >= 2`). |
| [`ecs-app/eks.tf`](ecs-app/eks.tf) | Passes **`node_instance_types`**, scaling vars into **`module "eks"`**. |
| [`ecs-app/modules/eks/variables.tf`](ecs-app/modules/eks/variables.tf) | **`node_instance_types`** default `["m6i.4xlarge"]`; **`node_min_size`** default **2** (matches root). |
| [`ecs-app/modules/eks/main.tf`](ecs-app/modules/eks/main.tf) | **`aws_eks_node_group`**: `instance_types`, `scaling_config`, `disk_size`, `ami_type`. |
| [`ecs-app/modules/alb-nlb/main.tf`](ecs-app/modules/alb-nlb/main.tf) | ALB IP and NLB-to-ALB target group **health_check** uses locals (max API interval, timeouts, thresholds). |
| [`deploy/deploy_role/iam-policy/midas-deployer-policy-003`](deploy_role/iam-policy/midas-deployer-policy-003) | **`elasticloadbalancing:ModifyTargetGroup`** on **`ElbManageLoadBalancers`** so Jenkins Terraform can change TG health checks. |

**Out of scope:** `deploy/ai_gateway/` has its own Terraform and is not part of this `ecs-app` stack.

---

## Helm changes (inventory)

| Chart / file | Role |
|--------------|------|
| [`ecs-app/helm/midas-api-backend-svc/values.yaml`](ecs-app/helm/midas-api-backend-svc/values.yaml) | **`resources`:** `requests` and `limits` both **`14600m` CPU** and **`53Gi` memory** (Guaranteed QoS). Comments document node slack vs **m6i.4xlarge** Allocatable. |
| [`ecs-app/helm/midas-web-frontend-svc/values.yaml`](ecs-app/helm/midas-web-frontend-svc/values.yaml) | **`resources: {}`**. |
| [`ecs-app/helm/midas-graph-svc/values.yaml`](ecs-app/helm/midas-graph-svc/values.yaml) | **`resources: {}`**. |

**Release wiring:** [`ecs-app/helm/releases.yaml`](ecs-app/helm/releases.yaml) orders frontend, backend, graph.

---

## Capacity layout (two nodes)

- **Worker A:** Large **backend** pod (Guaranteed requests or limits).
- **Worker B:** **Frontend**, **graph**, and **cluster DaemonSets**. Frontend and graph do not declare requests in default values.

If **`kubectl describe node`** shows **Allocatable** lower than **`53Gi`** or **`14600m`**, reduce backend **`resources`** slightly in **`midas-api-backend-svc/values.yaml`** until the pod schedules.

---

## Operational rollout (not in Git)

### Requirement: `kubectl` only via AWS CLI + SSM + jumpbox

The EKS API is **private**. Prefer **`kubectl`** from the MIDAS jumpbox (authoritative EC2 id: **`i-0342e59b40cd01082`**, VPC **`vpc-0c4d673f3e95a93eb`**, region **`us-east-1`**, see [`.cursor/rules/solution/solution_const.mdc`](../.cursor/rules/solution/solution_const.mdc)).

| Requirement | Detail |
|---------------|--------|
| **AWS CLI** | Region **`us-east-1`**; principal needs **`ssm:StartSession`** (or **`send-command`**) and **`eks:DescribeCluster`** as applicable. |
| **SSM target** | Jumpbox **`i-0342e59b40cd01082`**. |
| **Kubeconfig** | **`aws eks update-kubeconfig --region us-east-1 --name midas-eks-dev`** (or your cluster name). |

Canonical debugging rules: **[`.cursor/rules/debuging/debug.mdc`](../.cursor/rules/debuging/debug.mdc)**.

### Troubleshooting: `NodeGroup already exists` (HTTP 409)

See [`deploy/ecs-app/RUNBOOK_EKS_NODE_GROUP_STATE_IMPORT.md`](ecs-app/RUNBOOK_EKS_NODE_GROUP_STATE_IMPORT.md). Jenkins **`deploy/Jenkinsfile_Deploy_App`** can auto-import when appropriate.

### Rollout steps (pipeline-first)

1. Merge and run the **Jenkins** deploy that applies **`deploy/ecs-app`** and Helm (see **`deploy/Jenkinsfile_Deploy_App`**).
2. From the jumpbox: **`kubectl get nodes -o wide`**, **`kubectl describe node`**, **`kubectl get pods -n midas-apps -o wide`**, confirm instance type **m6i.4xlarge** after node group refresh.

---

## Override knobs (per environment)

| Intent | Where |
|--------|-------|
| Instance type or count | Terraform **`-var`** or **tfvars**: **`eks_node_instance_types`**, **`eks_node_desired_size`**, **`eks_node_min_size`**, **`eks_node_max_size`**. |
| SQLite-only or low workers | Helm **`webConcurrency: 1`** for that env. |
| Tighter or softer backend reservations | **`midas-api-backend-svc/values.yaml`** **`resources`** only. |

---

## Repository verification

| Check | Result |
|-------|--------|
| **`deploy/ecs-app/tfvars/`** | No **`eks_node_*`** overrides in checked files, defaults come from **`variables.tf`**. |
| **`deploy/Jenkinsfile_Deploy_App`** | Uses **`-var-file=tfvars/${TENANT_ENV}.tfvars`**; does not set **`eks_node_instance_types`** inline unless you add it. |
| **`deploy/ai_gateway/`** | Separate stack, not this node group. |

---

## Document history

- Original plan for **r6i.2xlarge** and older Helm **7900m / 58Gi** sizing.
- Refreshed for **`m6i.4xlarge`**, backend **`14600m / 53Gi`**, **ALB health check** Terraform locals, deployer **`ModifyTargetGroup`**, jumpbox id aligned to **`solution_const.mdc`**, and **`.cursor/config/eks-cluster-config.md`** alignment.
