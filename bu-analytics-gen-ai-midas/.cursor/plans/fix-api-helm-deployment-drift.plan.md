# Fix API Helm deployment drift (collaborative plan)

**Problem:** In cluster `midas-eks-dev`, `Deployment/midas-api-backend-svc` shows `containerPort: 80`, no `envFrom`, no `env` — it does not match the chart under [`deploy/ecs-app/helm/midas-api-backend-svc/`](../deploy/ecs-app/helm/midas-api-backend-svc/) (port **8000**, `secretRef: midas-app-secret`, `WEB_CONCURRENCY`, RDS env, etc.).

**Goal:** Live manifest matches chart; pods get secrets and correct port; optional verification script or docs updates in-repo.

---

## Roles

| Who | Responsibilities |
|-----|------------------|
| **You** | Refresh AWS SSO if needed; run Jenkins (or approve); run jumpbox SSM / `kubectl` / `helm` when the agent cannot reach the private EKS API; paste outputs if something fails. |
| **Agent (Cursor)** | Audit repo chart + deploy script vs docs; add or tighten validation scripts / README; suggest exact commands; after you run deploy, help interpret `kubectl`/`helm` output; small code/chart fixes only if gaps are found in-repo. |

---

## Phase A — Confirm drift (you + agent)

**You do:**

1. From jumpbox (SSM) or any host with working `kubectl` to `midas-eks-dev`:

```bash
kubectl get deploy midas-api-backend-svc -n midas-apps -o json | python3 -c "import sys,json; c=json.load(sys.stdin)['spec']['template']['spec']['containers'][0]; print('ports', c.get('ports')); print('envFrom', c.get('envFrom')); print('env', c.get('env'))"
helm list -n midas-apps
helm get manifest midas-api-backend -n midas-apps 2>/dev/null | grep -E 'containerPort|envFrom|midas-app-secret' | head -30
```

2. Paste the output into the chat (or confirm: still port 80 / null env).

**Agent does:** Compare your output to [`deploy/ecs-app/helm/midas-api-backend-svc/templates/deployment.yaml`](../deploy/ecs-app/helm/midas-api-backend-svc/templates/deployment.yaml) and [`helm-deploy-releases.sh`](../deploy/scripts/ci/helm-deploy-releases.sh); call out any mismatch (Helm revision vs live object).

---

## Phase B — Re-apply Helm (you; agent guides)

**Preferred:** Run the same pipeline that already deploys the frontend successfully — it must execute [`deploy/scripts/ci/helm-deploy-releases.sh`](../deploy/scripts/ci/helm-deploy-releases.sh) from a checkout that includes the current chart.

**You do:**

1. Ensure the Jenkins job checks out the branch that has the correct `midas-api-backend-svc` chart (e.g. `deployment/dev-jenkins` or your release branch).
2. Run **Deploy App** (or the stage that runs `helm-deploy-releases.sh`) with:
   - `EKS_CLUSTER_NAME=midas-eks-dev`
   - `IMAGE_TAG` and `ECR_URL_*` populated (same as Terraform/Jenkins env).
   - `BUILD_NUMBER` set so `rollout.suffix` updates the pod template.
3. If the stage **hangs on Helm wait**, capture the last 50 lines of the log; optionally re-run with `HELM_WAIT=false` / `HELM_ATOMIC=false` **only** to push manifests, then run `kubectl rollout status deployment/midas-api-backend-svc -n midas-apps --timeout=5m` manually from the jumpbox.

**Alternative (jumpbox):** Clone/sync repo to the jumpbox, `source deploy/.ci/terraform-env.sh` if available, then:

```bash
chmod +x deploy/scripts/ci/helm-deploy-releases.sh
export HELM_WAIT=true HELM_ATOMIC=false HELM_TIMEOUT=10m ROLLOUT_TIMEOUT=10m
./deploy/scripts/ci/helm-deploy-releases.sh
```

**Agent does:** If the script or Jenkinsfile is wrong or missing exports, propose a minimal repo fix (PR-sized).

---

## Phase C — Verify (you; agent interprets)

**You run:**

```bash
kubectl get deploy midas-api-backend-svc -n midas-apps -o json | python3 -c "import sys,json; c=json.load(sys.stdin)['spec']['template']['spec']['containers'][0]; print('ports', c.get('ports')); print('envFrom', c.get('envFrom')); print('env names', [e.get('name') for e in (c.get('env') or [])])"
kubectl get secret midas-app-secret -n midas-apps
kubectl exec deploy/midas-api-backend-svc -n midas-apps -- printenv WEB_CONCURRENCY AWS_RDS_POSTGRES_DB_NAME 2>/dev/null || true
```

**Success criteria:**

- `ports` include **8000** (not 80).
- `envFrom` references **`midas-app-secret`**.
- `env` lists **`WEB_CONCURRENCY`**, **`AWS_RDS_POSTGRES_DB_NAME`**, etc.
- `printenv WEB_CONCURRENCY` shows **`1`** (if chart default unchanged).

**Agent does:** If anything still wrong, map failure to next action (wrong release name, wrong namespace, webhook, IAM, etc.).

---

## Phase D — Hardening in-repo (agent; you review PR)

Optional follow-ups the agent can implement after you confirm Phase C:

- [ ] Extend [`.cursor/scripts/post-deploy-validate-eks.sh`](../.cursor/scripts/post-deploy-validate-eks.sh) (or add a sibling) to **fail** if API deploy has `containerPort != 8000` or missing `envFrom`.
- [ ] Short subsection in [`deploy/README.md`](../deploy/README.md): "Helm owns API Deployment; do not `kubectl apply` parallel manifests."

---

## Phase E — Process (you + team)

- [ ] Document in runbook: **only** `helm-deploy-releases.sh` (or equivalent Helm upgrade with same values) updates `midas-api-backend-svc`.
- [ ] Avoid one-off `kubectl apply -f` for this Deployment.

---

## Checklist (copy/paste progress)

- [ ] Phase A: drift confirmed (paste output once).
- [ ] Phase B: Helm upgrade / Jenkins run completed without blocking error.
- [ ] Phase C: Success criteria met.
- [ ] Phase D: Optional validation script / README (agent PR).
- [ ] Phase E: Runbook updated (your team).

---

## If stuck

| Symptom | Likely cause | Next step |
|--------|----------------|-----------|
| `helm upgrade` succeeds but deploy still 80 | Not same release/name/namespace | `helm list -a -n midas-apps`; match release name to `meta.helm.sh/release-name` on the deploy |
| `secret "midas-app-secret" not found` | SM sync failed | Check Jenkins log for `helm-deploy-releases.sh` SM pull; `aws secretsmanager get-secret-value` for `midas-dev-us-east-1/app` |
| Helm timeout | Pod not Ready | `kubectl describe pod`, `kubectl logs` (previous); fix app crash first |

When you are ready for the agent to **implement Phase D** or small script fixes, say **execute Phase D** or paste Phase A/B output for interpretation.
