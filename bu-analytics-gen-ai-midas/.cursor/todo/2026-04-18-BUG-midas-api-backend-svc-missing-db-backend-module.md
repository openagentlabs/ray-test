---
# ──────────────────────────────────────────────────────────────────────────────
# Jira-sync front matter (DevOps gold standard; safe to script-map into Jira)
# Keep keys stable — a sync tool can map these 1:1 to Jira fields.
# ──────────────────────────────────────────────────────────────────────────────
jira_project: MIDAS
issue_type: Bug
priority: Highest         # Jira: Highest (service-down in dev)
severity: Critical        # Jira: Sev1 equivalent — one of three services fully down
status: Open
resolution: Unresolved

summary: "midas-api-backend-svc CrashLoopBackOff: missing backend/app/models/_db_backend.py never committed (commit 11356184)"

# People
reporter: "Keith (keith334747 <keith334747@users.noreply.github.com>)"
owner:    "Keith (keith334747 <keith334747@users.noreply.github.com>)"   # ← ticket owner per user request
assignee: "saiyam268728 <saiyam268728@exlservice.com>"                   # ← author of the regression commit; to confirm on triage
watchers:
  - "Sahil Mulla <Sahil338946@exlservice.com>"       # previous SQLite↔Postgres migration author
  - "Saiyam-EXL <saiyam.arora@exlservice.com>"       # earlier guardrails/restore commits on same files
  - "MIDAS Platform / DevOps on-call"

# Classification
components:
  - "backend / api (midas-api-backend-svc)"
  - "helm chart: deploy/ecs-app/helm/midas-api-backend-svc"
  - "deploy pipeline: Jenkins deployment/dev-jenkins"
  - "eks/midas-apps namespace"
labels:
  - backend
  - python
  - import-error
  - module-not-found
  - deployment
  - regression
  - incomplete-commit
  - missing-file
  - crashloopbackoff
  - midas-api-backend-svc
  - postgres-migration
  - sqlite-fallback
  - seed-users
  - dev

# Versioning / environments
affects_versions:
  - "deployment/dev-jenkins @ 11356184 .. 13d78a2b (HEAD at time of report)"
  - "ECR image: midas-api-backend-svc@sha256:515847c2f0b716f3e25984dbc95c43c0dfd8d92f082d6644898134f18bbb9364 (pushed 2026-04-18T00:02:13Z)"
fix_versions:
  - "next midas-api-backend-svc image + next Jenkins deploy to dev"
environments:
  - "AWS us-east-1 / EKS cluster midas-dev / namespace midas-apps / deployment midas-api-backend-svc"
  - "VPC vpc-0c4d673f3e95a93eb (10.72.134.0/23), private-by-default"

# Timeline
reported_date: "2026-04-18"
regression_introduced_at: "2026-04-17 21:23:56 +0530 (commit 11356184)"
first_observed_in_cluster: "2026-04-18 (pod midas-api-backend-svc-c7f6dbd67-zlp5b, ≥9 restarts)"

# Traceability
related_commits:
  - "11356184edf369011c31807193b7056c59dd18ad  saiyam268728   2026-04-17 21:23:56  Added Postgres for all Sqllite db; SQL as fallback ; Default seeded user logins added   ← regression introduced"
  - "a1633978                                  Sahil Mulla    2026-04-13 23:29:27  Revert \"Migration from sqlite to postgres\"                                              (context)"
  - "71e12c2a                                  Sahil Mulla    2026-04-13 19:00:20  Migration from sqlite to postgres                                                        (context)"
  - "52c3cd5b                                  Sahil Mulla    2026-04-01 12:45:56  Migration from Sqlite to PostgreSQL and AWS S3.                                          (context)"
  - "44efbbef                                  Saiyam-EXL     2026-03-20 19:26:05  Force restore files from demo/V6                                                         (unrelated; models/ last known-good baseline, no _db_backend import)"
  - "6bb0ecff                                  Saiyam-EXL     2026-03-20 19:13:14  Devak and Himani Guardrails 1.0                                                          (unrelated; brief deletion, restored 13 min later)"
related_builds:
  - "Jenkins job: exlerate/exlerate-solutions/MIDAS/bu-analytics-gen-ai-midas-deploy-eks"
  - "Branch built: deployment/dev-jenkins"
related_services:
  - "midas-web-frontend-svc (HEALTHY — not affected)"
  - "midas-graph-svc (HEALTHY — not affected)"
related_infra:
  - "NLB, ALB, ALB listener rules /frontend|/backend|/graph, TargetGroupBindings — ALL HEALTHY; only backend TG has 0 registered targets because pod is never Ready"
---

# BUG — `midas-api-backend-svc` CrashLoopBackOff: `ModuleNotFoundError: No module named 'app.models._db_backend'`

> **TL;DR** — A single deployment-branch commit (`11356184`, author `saiyam268728`, 2026‑04‑17) added five **callers** of a helper module `app.models._db_backend` but forgot to `git add` the helper module itself. The module has never existed in any commit on any branch/tag/reflog. Every Jenkins image built on `deployment/dev-jenkins` since then crashes on import, holding the backend pod in `CrashLoopBackOff` and keeping ALB target group `midas-dev-alb-be-tg` at zero targets. **Frontend, graph, NLB, ALB, SGs, and TGBs are all healthy.** No deletion ever happened — this is an incomplete commit, not a regression from a deletion.

---

## 1. Issue type & classification (for Jira)

| Field | Value | Rationale |
|---|---|---|
| **Issue Type** | **Bug** | Defect producing an incorrect runtime state (`CrashLoopBackOff`) in a deployed environment. |
| **Priority** | **Highest** | Pipeline/infrastructure is green, but **1 of 3 MIDAS microservices is fully down** in `dev`; blocks integration testing. |
| **Severity** | **Sev 1 / Critical** | Service-down; pod never becomes `Ready`; ALB backend target group has 0 healthy targets. |
| **Sub-type (suggested)** | `Deployment defect — incomplete commit (missing source file)` | Helps a release-management dashboard distinguish from logic bugs. |
| **Environment impact** | `dev` (blocked), `uat`/`prod` (NOT promoted yet — will block promotion if unfixed). |
| **Regression?** | **Yes** — introduced by a single identifiable commit, reachable from `deployment/dev-jenkins`. |
| **User impact** | Any client calling `/backend/*` through the ALB receives a target-not-found / 502 from ALB after listener rule `prio=20` forwards to an empty target group. |

**If synced to Jira:** create as `MIDAS-<n> Bug` with `priority=Highest`, `severity=Sev1 (Critical)`, labels above. Link (`relates to`) to any existing Postgres-migration epic.

---

## 2. Summary (Jira `summary` field)

`midas-api-backend-svc CrashLoopBackOff in dev — backend/app/models/_db_backend.py was never committed (introduced by 11356184)`

---

## 3. Description

The MIDAS backend API pod `midas-api-backend-svc-c7f6dbd67-zlp5b` in the `midas-apps` namespace of the `midas-dev` EKS cluster is stuck in `CrashLoopBackOff` with **≥ 9 restarts** and container exit code **3**. Gunicorn boots, the worker fails to import the FastAPI application, the master exits, Kubernetes restarts the container, and the cycle repeats.

The failing import chain (verified in `kubectl logs <pod> --previous`) is:

1. `main.py` imports `upload_router`, `chat_router`, …
2. One of those imports `backend/app/models/user_database.py`
3. `user_database.py` **line 12** contains:
   ```python
   from app.models._db_backend import BACKEND, connect as _db_connect, coerce_datetime as _coerce_datetime
   ```
4. `app.models._db_backend` **does not exist** in the image (nor in the git tree).

`find /app/app/models/` inside the image (attempted via `kubectl exec`) could not be run because the container exits in < 1 s after start. Listing the working tree locally and sweeping every git ref confirmed the file is absent everywhere.

All surrounding infrastructure (NLB, ALB, listener rules, security groups, `TargetGroupBinding`, Kubernetes `Service`, `Endpoints`) is correctly configured — this bug is **purely application-code / release hygiene**, not infra.

---

## 4. Environment

| Dimension | Value |
|---|---|
| **AWS region** | `us-east-1` (MIDAS is single-region per `architecture.mdc`) |
| **AWS account** | MIDAS `dev` |
| **VPC** | `vpc-0c4d673f3e95a93eb` (10.72.134.0/23) — private-by-default |
| **EKS cluster** | `midas-dev` |
| **Namespace** | `midas-apps` |
| **Deployment** | `midas-api-backend-svc` (replicas=1) |
| **Pod** | `midas-api-backend-svc-c7f6dbd67-zlp5b` |
| **Pod IP** | `10.72.134.244` (listed under Service `notReadyAddresses`) |
| **Service** | `midas-api-backend-svc` → `ClusterIP 172.20.153.10:8000` |
| **ALB listener rule** | priority `20`, host-agnostic, path `/backend*` → `midas-dev-alb-be-tg` (HTTP:8000, `target_type=ip`) |
| **ALB target group** | `midas-dev-alb-be-tg` — **0 registered targets** (symptom, not root cause) |
| **NLB** | `midas-dev-nlb` :443 → `nlb_to_alb` TG → ALB :443 (healthy) |
| **Jenkins branch built** | `deployment/dev-jenkins` |
| **Container image** | `midas-api-backend-svc@sha256:515847c2f0b716f3e25984dbc95c43c0dfd8d92f082d6644898134f18bbb9364` (ECR, pushed 2026‑04‑18T00:02:13Z — confirmed latest) |

---

## 5. Steps to reproduce

1. Check out branch `deployment/dev-jenkins` at any commit from `11356184` onwards (up to current `HEAD` `13d78a2b`).
2. Run the MIDAS deploy pipeline (`bu-analytics-gen-ai-midas-deploy-eks`) with the standard `dev` parameters. Pipeline succeeds end-to-end (infra + image build + push + Helm deploy).
3. Watch the backend pod:
   ```bash
   kubectl -n midas-apps get pods -l app=midas-api-backend-svc
   ```
4. Pod enters `CrashLoopBackOff` within 60–90 s. `kubectl -n midas-apps logs <pod> --previous` shows the `ModuleNotFoundError` traceback.
5. ALB target group `midas-dev-alb-be-tg` stays at 0 registered targets because the pod never becomes `Ready` (there are no `TargetGroupBinding`-blocking probes left on this service — probes were already removed — so the gating factor is purely "pod process alive and listening").

---

## 6. Expected vs. actual

| | **Expected** | **Actual** |
|---|---|---|
| Pod phase | `Running`, `1/1 Ready` | `Running`, `0/1`, `CrashLoopBackOff`, ≥ 9 restarts |
| Container exit | 0 (stays up) | `3` (gunicorn master aborts after worker import failure) |
| Service `midas-api-backend-svc` endpoints | `addresses: [10.72.134.244:8000]` | `notReadyAddresses: [10.72.134.244:8000]` |
| ALB TG `midas-dev-alb-be-tg` | ≥ 1 healthy target | 0 registered targets |
| HTTP GET `https://<NLB>/backend/health` (once app has a `/health`) | 200 | 502 (ALB has no healthy backend in the TG) |

---

## 7. Root cause

### One-line root cause

**Commit `11356184` (author `saiyam268728`, 2026‑04‑17 21:23:56 +0530) added imports of `app.models._db_backend` to five files, but the module file itself was never `git add`-ed. It has never existed in any commit on any branch/tag/reflog.**

### Evidence chain (reproducible commands)

1. **File never existed in any commit, any ref:**
   ```bash
   git log --all --full-history -- backend/app/models/_db_backend.py   # no output
   git log --all --reflog --diff-filter=A --name-only | grep _db_backend   # no output
   # Sweep every commit's tree on every ref:
   for sha in $(git rev-list --all --reflog); do
     git show "$sha:backend/app/models/_db_backend.py" >/dev/null 2>&1 && echo "PRESENT in $sha"
   done    # no output = never present
   ```

2. **Pickaxe search for the broken import string identifies exactly one commit across all refs:**
   ```bash
   git log --all --reflog -S 'from app.models._db_backend' \
     --pretty=format:'%h %ad %an <%ae> %s' --date=iso
   # → 11356184 2026-04-17 21:23:56 +0530 saiyam268728 <saiyam268728@exlservice.com> \
   #     Added Postgres for all Sqllite db; SQL as fallback ; Default seeded user logins added
   ```

3. **That commit modifies 4 + adds 1 file, all referencing the missing module; none of them add the module:**
   ```bash
   git show --name-status 11356184 -- 'backend/app/models/*' 'backend/scripts/*'
   # M  backend/app/models/database.py
   # M  backend/app/models/model_evaluation_database.py
   # M  backend/app/models/project_database.py
   # M  backend/app/models/user_database.py
   # A  backend/scripts/seed_users.py
   ```

4. **The commit's own tree does not contain `_db_backend.py`:**
   ```bash
   git ls-tree -r 11356184 -- backend/app/models/
   # __init__.py  database.py  model_evaluation_database.py
   # project_database.py  schemas.py  user_database.py     ← no _db_backend.py
   ```

5. **Commit is reachable from the branch Jenkins builds:**
   ```bash
   git branch -a --contains 11356184
   #   deployment/dev-jenkins
   #   remotes/origin/deployment/dev-jenkins
   ```

6. **Runtime traceback (matches exactly):**
   ```
   File "/app/app/models/user_database.py", line 12, in <module>
     from app.models._db_backend import BACKEND, connect as _db_connect, coerce_datetime as _coerce_datetime
   ModuleNotFoundError: No module named 'app.models._db_backend'
   ```

### Ruled-out alternative causes (documented to close the investigation)

| Hypothesis | Verdict | Evidence |
|---|---|---|
| "File was deleted by someone" | ❌ Ruled out | `git log --all --diff-filter=D -- backend/app/models/_db_backend.py` returns empty; the only models/ deletion was `6bb0ecff` on 2026‑03‑20 which did NOT include `_db_backend.py` and which was itself fully reverted 13 minutes later by `44efbbef`. |
| "It's in the Docker image but missing from repo" | ❌ Ruled out | Dockerfile copies `backend/` as-is; ECR image `sha256:5158…9364` does not contain the file (pod crash itself is the proof). Nothing in `.dockerignore` or `.gitignore` hides it. |
| "Startup/liveness/readiness probe regression" | ❌ Ruled out | The `midas-api-backend-svc` Helm chart currently has **no probes** (removed earlier in commit `eb094c97`). Even with no probes, the pod still crashes on import. |
| "ALB / TGB / SG misconfiguration" | ❌ Ruled out | NLB → ALB → listener rule prio 20 → `midas-dev-alb-be-tg` chain and all SG ingress rules are correct. TGB `midas-backend-tgb` is `Ready`. Frontend and graph use the same pattern and are fully healthy. |
| "Postgres unreachable → app exits 3" | ❌ Ruled out | App never reaches any DB connection code. `ModuleNotFoundError` is thrown at import time, before any `connect()` call. |

---

## 8. Impact analysis

| Area | Impact | Detail |
|---|---|---|
| **Dev users / QA** | 🔴 Blocked | Any test exercising `/backend/*` fails at the ALB (0 targets). |
| **Pipeline health** | 🟢 OK | Jenkins builds succeed (Terraform + Helm both green); the failure is *post-deploy* inside the pod. The pipeline's `helm upgrade` reports success because the Deployment rolls out; `CrashLoopBackOff` shows only in `kubectl` afterwards. |
| **Data** | 🟢 No data loss | App never writes — it dies at import. RDS and S3 untouched. |
| **Security** | 🟢 No exposure | Private VPC only; no public endpoint. |
| **Promotion to UAT/Prod** | 🔴 Must not promote | Same branch → same image → same CrashLoopBackOff. |
| **Other services** | 🟢 Unaffected | `midas-web-frontend-svc` (IP `10.72.134.157:8080`) and `midas-graph-svc` (IP `10.72.134.20:8001`) are both `Ready` and serving traffic end-to-end through NLB → ALB. |

---

## 9. Fix plan (authoritative — smallest viable change)

> **Preferred fix = restore the missing file from the author's local working tree and commit it.** No rewrite, no band-aids, no ignoring the import.

### Phase A — Recover / reconstruct `_db_backend.py`

One of the following, in preference order:

1. **Ask `saiyam268728`** for the local `backend/app/models/_db_backend.py` file (still on their machine, since it compiles locally there). **Owner: ticket owner (Keith) to reach out; assignee: `saiyam268728`.**
2. If (1) is not possible within 24 h, **reconstruct** the module by reading every caller to derive the required public surface:
   - From `user_database.py`, `project_database.py`, `model_evaluation_database.py`, `database.py`, `scripts/seed_users.py` the module must export at least:
     - `BACKEND` — string/enum identifying the active backend (`"postgres"` | `"sqlite"`).
     - `connect(...)` — returns an open DB connection; used as `connect as _db_connect`.
     - `coerce_datetime(value)` — normaliser used as `coerce_datetime as _coerce_datetime`.
   - Implement the stated "Postgres primary, SQLite fallback" behaviour (that is literally the subject of commit `11356184`).
3. **Temporary safety-net (only if Phase A fully blocks)**: guard each caller with `try/except ImportError` and fall back to the pre-`11356184` SQLite path that was working on commit `a1633978`. This is **not** the preferred fix; it would silently hide a real architectural change (Postgres with SQLite fallback).

### Phase B — Ship the fix

| # | Action | Owner |
|---|---|---|
| B1 | Create branch `fix/MIDAS-<n>-db-backend-missing-module` off `deployment/dev-jenkins`. | assignee |
| B2 | Add `backend/app/models/_db_backend.py` (from Phase A). | assignee |
| B3 | Run `python -c "import app.models.user_database, app.models.project_database, app.models.model_evaluation_database, app.models.database"` locally inside the backend venv to prove imports succeed. | assignee |
| B4 | Run the container image build locally (`docker build -f backend/Dockerfile backend/`) and `docker run` it with just `python -c "import main"` to prove in-image import works. | assignee |
| B5 | Open PR → merge to `deployment/dev-jenkins`. | assignee + reviewer |
| B6 | Trigger MIDAS deploy pipeline to `dev` via `.cursor/tools/jenkins_tools.py --OK_DELETE_MODIFY trigger …` (per `.cursor/rules/jenkins.mdc` / `.cursor/skills/jenkins_run`). Do **not** `helm upgrade` from a laptop. | ticket owner |
| B7 | Watch with `watch --log-stats`, auto-approve the `Approve deploy?` gate. | ticket owner |
| B8 | Verify in cluster: `kubectl -n midas-apps get pods` shows `1/1 Ready`; `describe svc midas-api-backend-svc` shows the pod under `addresses`, not `notReadyAddresses`; AWS ELBv2 `describe-target-health midas-dev-alb-be-tg` shows 1 target `healthy`. | ticket owner |

### Phase C — Prevent recurrence (guardrails)

| # | Guardrail | Where it lives |
|---|---|---|
| C1 | Add a **pre-commit hook** that runs `python -m compileall backend/` (fast, catches missing imports in staged tree). | `.pre-commit-config.yaml` in repo root |
| C2 | Add a **CI stage** in the build pipeline (`deploy/Jenkinsfile_Build` → "Docker build") that, inside the built image, runs `python -c "import main"` as a smoke test **before** pushing to ECR. Fails the build loudly instead of pushing a broken image. | `deploy/Jenkinsfile_Build` |
| C3 | Add a **post-deploy Helm test hook** (`helm test`) that waits ≤ 90 s for the pod to become `Ready` and fails the pipeline if not. | `deploy/ecs-app/helm/midas-api-backend-svc/templates/test-*.yaml` + `deploy/Jenkinsfile_Deploy_App` |
| C4 | Optional: `ruff` / `pyflakes` rule F401/F821 in the same CI job. Flags *unresolved imports* at static-analysis time (`_db_backend` would have been flagged as "undefined module" before the commit ever merged). | repo-level `ruff.toml` |

Phase C is out of scope for the hot-fix ticket and should be filed as a linked **"Deployment hardening" follow-up story**.

---

## 10. Acceptance criteria

1. [ ] `backend/app/models/_db_backend.py` exists on `deployment/dev-jenkins`, exports at minimum `BACKEND`, `connect`, `coerce_datetime`, and passes `python -c "import app.models._db_backend"` inside the backend container.
2. [ ] `python -c "import main"` inside the built backend image exits 0 (smoke-test, pre-push).
3. [ ] After the next deploy pipeline run, `kubectl -n midas-apps get deploy midas-api-backend-svc` shows `AVAILABLE=1` and the underlying pod has `RESTARTS=0` over a 10-minute observation window.
4. [ ] `aws elbv2 describe-target-health --target-group-arn <midas-dev-alb-be-tg ARN>` returns exactly one target in `State=healthy`.
5. [ ] A GET through the NLB at `/backend/` returns a non-502 response (200 for a known route, or 404 from the app — both prove the target is reachable).
6. [ ] Guardrails C2 and C3 are either merged as part of this fix *or* filed as a linked follow-up ticket (link attached).

## 11. Definition of Done

- All acceptance criteria green.
- Fix deployed to `dev` via the Jenkins pipeline (no laptop-driven `helm upgrade` / `terraform apply` shortcuts).
- Jira ticket transitioned to `Resolved` with resolution `Fixed`, `fix_versions` set to the Jenkins build number, and the PR + build URLs pasted into the resolution comment.
- Retro bullet added to the next MIDAS weekly devops retro: *"incomplete commit (missing source file) silently passed CI because we do not run an in-image import smoke test"* → feeds guardrails C1–C4.

## 12. Rollback plan

- **Automatic safety**: pod already in `CrashLoopBackOff` **without** consuming traffic; no rollback needed to protect users.
- **If the fix makes things worse** (e.g. the reconstructed `_db_backend.py` introduces a new crash): revert the fix PR and the pipeline re-deploys the previous image, which is *exactly* the current broken state. There is no worse position than today, because backend is already 100% down.
- **DB rollback**: none required. No DML is ever executed because the app never reaches DB code.

## 13. Supporting evidence — copy-paste commands

```bash
# Confirm the module has never existed anywhere in git history:
git log --all --full-history -- backend/app/models/_db_backend.py
git log --all --reflog --diff-filter=A --name-only | grep _db_backend

# Pinpoint the commit that introduced the broken import:
git log --all --reflog -S 'from app.models._db_backend' \
  --pretty=format:'%h %ad %an <%ae> %s' --date=iso

# Prove the commit's own tree omits the module:
git ls-tree -r 11356184 -- backend/app/models/

# Read the broken import line at the point of regression:
git show 11356184:backend/app/models/user_database.py | sed -n '1,20p'

# In cluster — show the traceback:
aws ssm send-command --instance-ids i-04231b2a8a4d98b63 \
  --document-name AWS-RunShellScript \
  --parameters 'commands=[
    "sudo -iu ubuntu kubectl -n midas-apps logs $(sudo -iu ubuntu kubectl -n midas-apps get pod -l app=midas-api-backend-svc -o jsonpath=\"{.items[0].metadata.name}\") --previous --tail=80"
  ]' --region us-east-1
```

## 14. Links / attachments

| Link | Purpose |
|---|---|
| Architecture (Miro) | https://miro.com/app/board/uXjVGnrWh1o=/ |
| Jenkins job | https://ucjenkinsdev.exlservice.com/job/exlerate/job/exlerate-solutions/job/MIDAS/job/bu-analytics-gen-ai-midas-deploy-eks |
| Branch | `deployment/dev-jenkins` |
| Offending commit | `11356184edf369011c31807193b7056c59dd18ad` |
| ECR image digest | `sha256:515847c2f0b716f3e25984dbc95c43c0dfd8d92f082d6644898134f18bbb9364` |
| Prior agent transcript | [Incomplete commit investigation](9a04d8da-4aa9-44f5-bebb-1ed406786ff2) |
| Project rules | `.cursor/rules/architecture.mdc`, `.cursor/rules/jenkins.mdc` |

## 15. History / audit log (append-only)

| Date (IST) | Actor | Action |
|---|---|---|
| 2026-04-18 16:24 | Keith (reporter/owner) | Ticket created. Regression localised to commit `11356184`. Phase-A recovery plan drafted. No code changes made (per scoping rule "no app-code changes without explicit approval"). |
