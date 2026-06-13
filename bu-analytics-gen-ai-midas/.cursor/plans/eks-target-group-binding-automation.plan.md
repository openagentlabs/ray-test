# Plan: EKS pod registration for ALB target groups (frontend / backend / graph)

**Account / region:** `811391286931`, `us-east-1` (MIDAS dev as reference; same pattern for uat/prod with tfvars).  
**Goal:** Ensure the live EKS cluster **registers and unregisters pod IPs** on Terraform-managed ALB target groups `midas-<env>-alb-{fe,be,gr}-tg` as workloads scale and roll out.  
**Deliverable:** This document only (implementation is a separate change set).

---

## 1. Root cause (why targets stay empty today)

### 1.1 AWS does not attach pods to load balancers by magic

For `target_type = ip` ALB target groups, **Amazon EKS does not register pods**. The **AWS Load Balancer Controller** reconciles **`TargetGroupBinding`** (`elbv2.k8s.aws/v1beta1`) CRs: it watches **Service Endpoints** and calls `RegisterTargets` / `DeregisterTargets` on the ARN in `spec.targetGroupARN`.

Terraform already documents that intent:

```135:137:deploy/ecs-app/modules/alb-nlb/main.tf
# ALB Target Groups (target_type=ip; AWS LB Controller TargetGroupBinding
# manages pod IP registration automatically via Kubernetes Endpoints).
```

### 1.2 Terraform creates the target groups; it does not create the bindings

`deploy/ecs-app/alb-nlb.tf` provisions NLB + ALB + three IP target groups and exposes ARNs via outputs (`alb_frontend_target_group_arn`, `alb_backend_target_group_arn`, `alb_graph_target_group_arn`). It explicitly lists **manual** follow-up:

```5:8:deploy/ecs-app/alb-nlb.tf
# After terraform apply:
#   1. Install AWS Load Balancer Controller (see deploy/k8s/aws-load-balancer-controller/README.md)
#   2. Substitute TG ARNs from outputs into deploy/k8s/ingress/targetgroupbinding-*.yaml
#   3. kubectl apply -f deploy/k8s/ingress/
```

Nothing in the `alb-nlb` module applies Kubernetes resources for TargetGroupBindings.

### 1.3 Committed TargetGroupBinding manifests are not deployable as-is

All three files still use **placeholder** ARNs, e.g.:

```31:36:deploy/k8s/ingress/targetgroupbinding-frontend.yaml
spec:
  serviceRef:
    name: midas-web-frontend-svc
    port: 80
  targetGroupARN: "REPLACE_WITH_terraform_output_alb_frontend_target_group_arn"
  targetType: ip
```

If these were applied without substitution, the controller would not bind to the real TGs created in AWS.

### 1.4 Jenkins + Helm path never applies TargetGroupBindings

`deploy/Jenkinsfile_Deploy_App`:

- **Terraform apply** runs with `alb_nlb_enabled` from `DEPLOY_ALB_NLB` (creates TGs).
- **Outputs stage** writes `deploy/.ci/terraform-env.sh` with `ECR_URL_*`, `EKS_CLUSTER_NAME`, `SKIP_K8S_APP_SECRET_SYNC` — **not** the three ALB TG ARNs.
- **Helm deploy** runs `deploy/scripts/ci/helm-deploy-releases.sh`, which loops `deploy/ecs-app/helm/releases.yaml` (frontend, backend, graph charts only). There is **no** `kubectl apply` for `deploy/k8s/ingress/`.

`deploy/ecs-app/helm/releases.yaml` lists only the three application charts; no chart ships `TargetGroupBinding` resources (confirmed: no `TargetGroupBinding` / `elbv2` under `deploy/ecs-app/helm/`).

**Conclusion:** The operational gap is **missing (or non-reconciling) TargetGroupBinding objects + dependency on AWS Load Balancer Controller**, not broken Terraform TG definitions. ELB `describe-target-health` showing **zero targets** on all three app TGs is consistent with this gap.

### 1.5 AWS Load Balancer Controller may be missing or not IRSA-wired

Terraform **does** create IRSA IAM for the controller (`deploy/ecs-app/eks-alb-controller.tf`, output `eks_aws_load_balancer_controller_role_arn`). **Helm install of the controller** is still documented as an operator/jump-box step in `deploy/k8s/aws-load-balancer-controller/README.md`, not as a Jenkins stage.

If the controller is not installed, or the service account lacks the IRSA annotation, TargetGroupBinding CRs will not reconcile even after `kubectl apply`.

### 1.6 Service wiring is already correct (not the root cause)

Helm `Service` names and ports align with the TGB `serviceRef`:

| TGB `serviceRef` | Chart / Service | Port |
|------------------|-----------------|------|
| `midas-web-frontend-svc` : 80 | `midas-web-frontend-svc` | 80 → pod 8080 |
| `midas-api-backend-svc` : 8000 | `midas-api-backend-svc` | 8000 |
| `midas-graph-svc` : 8001 | `midas-graph-svc` | 8001 |

No change required here for registration **once** TGB + controller exist.

---

## 2. Target end state (definition of done)

| Check | Expected |
|-------|----------|
| Controller | `aws-load-balancer-controller` Deployment running in `kube-system` with IRSA annotation pointing at `eks_aws_load_balancer_controller_role_arn` output. |
| CRD | `kubectl get crd targetgroupbindings.elbv2.k8s.aws` exists. |
| Bindings | Three `TargetGroupBinding` objects in `midas-apps` referencing the **live** Terraform TG ARNs for the current environment. |
| AWS | `aws elbv2 describe-target-health` on each `midas-<env>-alb-{fe,be,gr}-tg` shows **registered IPs** when pods are Ready, and updates on rollout. |
| NLB → ALB | `midas-<env>-nlb-alb-tg` target (the ALB) becomes **healthy** once ALB default path returns a code inside the TG health matcher (after frontends register). |
| Traffic | `curl` via NLB port-forward to `/frontend/`, `/backend/health`, `/graph/health` returns non-503 when pods are healthy. |

---

## 3. Recommended approach (single coherent pipeline)

**Automate three things in order:** (A) ensure controller, (B) materialize TGB manifests with real ARNs per environment, (C) apply TGBs after Helm rollouts so Services exist.

### 3.1 Option comparison (brief)

| Option | Pros | Cons |
|--------|------|------|
| **A – Extend Jenkins + small script** (export TG ARNs to `terraform-env.sh`; `envsubst`/`kubectl apply` after Helm) | Minimal moving parts; uses existing outputs; no Terraform→EKS coupling at apply time | Jenkins must reach EKS API (already required for Helm). |
| **B – New Helm chart `midas-alb-tgb`** with values for three ARNs | Git-versioned manifests; `helm upgrade` with `--set` from Jenkins | New chart + wiring in `releases.yaml`; order vs app charts must be documented. |
| **C – `kubernetes_manifest` in Terraform for TGB** | Single apply | Requires cluster API + valid kubeconfig during **every** Terraform apply; duplicates pain already handled for `kubernetes_secret_v1.midas_app`. |

**Recommendation:** **Option A** (or B if you prefer all config in Helm). Option A matches how `terraform-env.sh` already carries Terraform outputs into the Helm stage.

### 3.2 Controller install (one-time or gated stage)

Pick one policy and document it in `deploy/README.md` / controller README:

1. **Operator-only (current):** Jump box Helm install; Jenkins assumes it exists — add a **pre-flight** in `helm-deploy-releases.sh` or a dedicated Jenkins stage: `kubectl -n kube-system get deploy aws-load-balancer-controller` → fail fast with a clear message if missing.  
2. **Pipeline-managed:** Add a Jenkins stage (after Terraform outputs, before or with Helm) that runs `helm upgrade --install aws-load-balancer-controller ...` using `terraform output -raw eks_aws_load_balancer_controller_role_arn`, `terraform output -raw eks_cluster_name`, and **VPC ID from Terraform variable/output** (replace hardcoded VPC in README example).

Until the controller is guaranteed, TGBs will never work.

### 3.3 Materialize TargetGroupBinding YAML (no committed secrets; ARNs are fine)

- Add **templates** under `deploy/k8s/ingress/` (e.g. `targetgroupbinding-frontend.yaml.tpl`) with placeholders `${ALB_FRONTEND_TARGET_GROUP_ARN}` **or** keep one set of files and substitute in CI with `envsubst` / `sed` from environment variables exported by Jenkins.
- **Do not** commit environment-specific ARNs into git; inject at deploy time.

### 3.4 Jenkins changes (`deploy/Jenkinsfile_Deploy_App`)

In the stage **“Terraform init - ecs-app (outputs only)”** (where `deploy/.ci/terraform-env.sh` is built), append (when `DEPLOY_ALB_NLB` is true or unconditionally with empty guard):

```bash
# Pseudocode — use terraform output -raw; empty string when alb_nlb_enabled=false
echo "export ALB_FRONTEND_TARGET_GROUP_ARN=$(terraform output -raw alb_frontend_target_group_arn)" >> "$OUT"
echo "export ALB_BACKEND_TARGET_GROUP_ARN=$(terraform output -raw alb_backend_target_group_arn)" >> "$OUT"
echo "export ALB_GRAPH_TARGET_GROUP_ARN=$(terraform output -raw alb_graph_target_group_arn)" >> "$OUT"
```

Handle `alb_nlb_enabled=false`: either omit exports or export empty and skip apply script.

### 3.5 New script: `deploy/scripts/ci/apply-target-group-bindings.sh`

Responsibilities:

1. `set -euo pipefail`; source `deploy/.ci/terraform-env.sh` (or accept env from caller).
2. If any ARN is empty, print **skipping** (NLB stack disabled) and exit 0.
3. Require `kubectl` + `aws eks update-kubeconfig` (caller already did this in Helm script — **reuse** same session: invoke from `helm-deploy-releases.sh` at end **or** chain from Jenkins after sourcing env).
4. Render three manifests from templates using the three `ALB_*_ARN` variables.
5. `kubectl apply -f -` (or `-k` if using kustomize) into `midas-apps`.
6. Optional: `kubectl wait --for=condition=ready` / poll `kubectl get targetgroupbinding -n midas-apps -o jsonpath='...'` until `SYNCED` or timeout; print `describe` on failure.

**Ordering relative to Helm:** Apply TGBs **after** Helm has created/updated `Service` objects and pods (current `helm-deploy-releases.sh` order). Applying TGB before Services exist can leave transient errors; controller should retry, but post-Helm is cleaner.

**Idempotency:** `kubectl apply` of the same TGB spec is idempotent; safe on every pipeline run.

### 3.6 Wire script into existing flow

**Minimal change:** At the end of `helm-deploy-releases.sh` (after successful Helm + optional rollout), call:

```bash
"${ROOT}/deploy/scripts/ci/apply-target-group-bindings.sh"
```

Pass through namespace from `releases.yaml` (`midas-apps`).

**Alternative:** Separate Jenkins stage **“Apply TargetGroupBindings”** after Helm — easier to skip independently for debugging.

### 3.7 RBAC and API version

- Confirm installed controller version supports `elbv2.k8s.aws/v1beta1` (current manifests). Upgrade CRD/apiVersion if you upgrade the controller chart past a breaking CRD version (check upstream release notes).
- Cluster role for the controller is bundled with the official Helm chart; no custom RBAC usually needed for TGB.

### 3.8 Documentation updates (same PR as code)

| File | Update |
|------|--------|
| `deploy/ecs-app/alb-nlb.tf` header comment | Replace “manual kubectl apply” with “automated via `apply-target-group-bindings.sh` from Jenkins” or “optional manual apply for break-glass”. |
| `deploy/k8s/aws-load-balancer-controller/README.md` | Fix stale line claiming Jenkins does not run Helm; clarify **controller** install is still operator vs pipeline per chosen policy; link to CI script. |
| `deploy/README.md` (optional §) | One paragraph: NLB path requires controller + TGB; CI applies TGB after Helm. |

---

## 4. Implementation phases (ordered checklist)

### Phase 0 – Preconditions (no code)

- [ ] From a host with EKS API access: confirm whether `aws-load-balancer-controller` exists and is healthy.
- [ ] `kubectl get targetgroupbinding -A` — confirm whether any TGBs exist today.
- [ ] `aws elbv2 describe-target-health` on the three ALB TGs — baseline (expect 0 targets until fixed).

### Phase 1 – Controller guarantee

- [ ] Decide operator-only vs pipeline Helm for `aws-load-balancer-controller`.
- [ ] If pipeline: add Jenkins stage or extend `helm-deploy-releases.sh` with pinned chart version, `clusterName`, `region=us-east-1`, `vpcId` from Terraform output/variable, IRSA role from `terraform output -raw eks_aws_load_balancer_controller_role_arn`.
- [ ] If operator-only: add strict pre-flight in CI that fails with actionable text when the Deployment is missing.

### Phase 2 – Templated manifests + apply script

- [ ] Add `.tpl` or envsubst-friendly YAML under `deploy/k8s/ingress/` (three resources: `midas-frontend-tgb`, `midas-backend-tgb`, `midas-graph-tgb`).
- [ ] Implement `deploy/scripts/ci/apply-target-group-bindings.sh` (render + `kubectl apply`, skip when ARNs empty, non-zero exit on apply failure).
- [ ] `chmod +x`; add `--help` / header comment listing required env vars.

### Phase 3 – Jenkins / Helm integration

- [ ] Extend Terraform outputs stage to export the three TG ARNs into `deploy/.ci/terraform-env.sh` (raw `terraform output`; handle `alb_nlb_enabled=false`).
- [ ] Invoke apply script after Helm in `helm-deploy-releases.sh` **or** add a Jenkins stage that sources `terraform-env.sh` and runs the script.
- [ ] When `ENABLE_HELM_DEPLOY` is false, skip TGB apply (or document that TGBs drift until next enabled run).

### Phase 4 – Verification

- [ ] Post-deploy: `kubectl get targetgroupbinding -n midas-apps` — all `SYNCED` (or equivalent ready condition for your controller version).
- [ ] `aws elbv2 describe-target-health` — non-zero healthy targets for each TG when pods are up.
- [ ] `curl` via SSM port-forward to NLB paths — not 503 (health matcher / default action satisfied).
- [ ] Rollout test: `kubectl rollout restart deployment/<frontend>` — observe target deregistration/reregistration in AWS console or CLI.

### Phase 5 – Hardening (optional same PR or fast follow)

- [ ] Add **read-only** CI check script that compares applied TGB ARN to `terraform output` (detect drift).
- [ ] Consider **Helm post-install** hook only if you move to Option B; avoid duplicating TGB in two systems.

---

## 5. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Jenkins agent cannot reach private EKS API | Already a requirement for Helm; TGB apply fails the same way — document network path (VPC / TGW). |
| `alb_nlb_enabled=false` but script applies | Guard on empty ARNs; exit 0 with message. |
| Controller chart upgrade breaks CRD | Pin chart version; read upstream migration notes before bumping. |
| Brief 503 during first bind | Apply TGB after Helm rollouts; accept short window or run `kubectl rollout status` before TGB apply (already partially true). |

---

## 6. Explicit non-goals (this plan)

- Changing ALB listener rules, health check paths, or Terraform SG rules (only if verification shows a **secondary** issue after targets register).
- Replacing NLB+ALB with Kubernetes `Ingress` auto-provisioned ALB (different architecture).
- Storing TG ARNs in Secrets Manager (unnecessary; Terraform outputs are sufficient for CI).

---

## 7. Summary

| Layer | Today | After implementation |
|-------|--------|----------------------|
| Terraform | Creates empty IP TGs | Unchanged (still source of truth for ARNs). |
| EKS | No reconciler for TGs | Controller + TGB reconcile pod IPs. |
| CI/CD | Helm only | Helm + rendered TGB apply (and optionally controller install / pre-flight). |
| Git | Placeholder TGB YAML | Templates + CI injection; no per-env ARN commits. |

**Root cause in one line:** Target group registration is owned by the **AWS Load Balancer Controller + TargetGroupBinding**, which are **outside** the current automated Terraform/Helm path and **not** applied with real ARNs—so the ALB target groups remain empty and traffic returns **503**.

When you are ready to implement, use this plan as the task breakdown; a separate change set can touch `Jenkinsfile_Deploy_App`, `helm-deploy-releases.sh`, new `apply-target-group-bindings.sh`, and `deploy/k8s/ingress/` templates only.
