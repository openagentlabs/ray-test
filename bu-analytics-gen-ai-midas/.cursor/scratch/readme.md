# AI Gateway component — embedding strategy & developer guide

**Audience:** MIDAS architects, developers, SREs, and AI agents.
**Status:** Draft (lives in `.cursor/scratch/`); to be promoted to `docs/components/ai_gateway.md` (or similar) once approved.
**Last updated:** 2026-04-19

---

## 1. What is the AI Gateway?

The **AI Gateway** is an external component owned by the Unified-Cloud-DevOps team. It packages:

- **LiteLLM** — unified LLM proxy / router.
- **Langfuse** — LLM observability (tracing, evals, prompt management).
- **Custom code** (`exlerate_aigtw_c1_api`, NeMo Guardrails configs, scripts) — glue + control-plane API + safety policies.

Together it provides a private, observable, governed access path to LLMs for downstream applications.

| Field | Value |
|---|---|
| Upstream repository | `https://ucgithub.exlservice.com/Unified-Cloud-DevOps/bu-digital-exlerate-aigateway.git` |
| Tracked branch | `develop` |
| Mount point in MIDAS | `ai_gateway/` (top-level subfolder) |
| Embedding mechanism | **Git submodule** (pinned to a specific upstream commit SHA) |
| Owner of upstream code | Unified-Cloud-DevOps team (NOT the MIDAS team) |
| Owner of MIDAS-side wiring | MIDAS platform team |

---

## 2. Why a git submodule (and not subtree / vendoring / a separate clone)

| Mechanism | Code 100% separate | Deploy 100% separate | Pull upstream | Local edits never reach upstream | Pinned & reproducible | Verdict |
|---|---|---|---|---|---|---|
| **Submodule (chosen)** | ✅ own `.git` | ✅ AI Gateway brings its own `deploy/`, `helm/`, `infra/terraform/` inside the submodule | ✅ `git submodule update --remote` | ✅ pushes are explicit + we disable the push URL | ✅ pinned to a SHA | **Adopted** |
| Subtree | ❌ history merged into MIDAS | ⚠️ files become MIDAS files | ✅ | ✅ | ⚠️ | Rejected |
| Vendor / plain copy | ❌ no link upstream | ✅ | ❌ manual re-copy | ✅ | ⚠️ | Rejected |
| Gitignored separate clone | ✅ | ✅ | ✅ manual | ✅ | ❌ no pin | Rejected |

The **submodule** is the only mechanism that satisfies all five requirements simultaneously.

---

## 3. Isolation guarantees

The MIDAS repo treats `ai_gateway/` as an **opaque, read-only component**. The contract is:

1. **Code isolation.** `ai_gateway/` has its own git history. The MIDAS repo records only a single commit SHA pointer in `.gitmodules` + the submodule object. No upstream files are duplicated into MIDAS history.
2. **Deployment isolation.**
   - The MIDAS top-level `deploy/` Terraform / Helm **does not reference anything inside `ai_gateway/`**.
   - The AI Gateway brings its own `ai_gateway/deploy/`, `ai_gateway/helm/`, and `ai_gateway/infra/terraform/`. These are deployed by a **separate, dedicated Jenkins pipeline** (to be created) that operates *only* inside `ai_gateway/`.
   - The MIDAS Jenkins pipeline (`deploy/Jenkinsfile_Deploy_App` etc.) MUST NOT be modified to deploy the AI Gateway. They remain wholly separate release paths.
3. **Build isolation.** Docker image builds for the AI Gateway happen in its own pipeline, with its own ECR repos and tags. MIDAS image builds and AI Gateway image builds never share a build context.
4. **Configuration isolation.** AI Gateway secrets, IAM roles, and Kubernetes namespaces are owned by the AI Gateway pipeline. MIDAS does not provision them.
5. **Push isolation (the safety net).** The submodule's `origin` push URL is set to `DISABLED`, so any accidental `git push` from inside `ai_gateway/` fails immediately. Fetches are unaffected.

> **Rule of thumb:** if a change in MIDAS would require editing a file under `ai_gateway/`, you are doing it wrong. Either upstream that change to the AI Gateway repo, or surface a configuration knob the AI Gateway team can expose.

---

## 4. How developers work with the submodule

### 4.1 First-time clone (fresh laptop)

```bash
git clone <midas-repo-url> bu-analytics-gen-ai-midas
cd bu-analytics-gen-ai-midas
git submodule update --init --recursive
```

> If you already cloned without `--recurse-submodules`, just run the second line.

### 4.2 Refresh after `git pull`

When someone updates the pinned AI Gateway commit:

```bash
git pull
git submodule update --init --recursive
```

Check `git status` — if it shows `ai_gateway` as "modified", run the submodule update; do **not** `git add ai_gateway` to "fix" it without understanding why.

### 4.3 Verifying isolation locally

```bash
# Confirm the submodule is registered
git config --file .gitmodules --list

# Confirm the push URL is disabled
git -C ai_gateway remote -v
# Expected output:
#   origin  https://ucgithub.exlservice.com/Unified-Cloud-DevOps/bu-digital-exlerate-aigateway.git (fetch)
#   origin  DISABLED (push)
```

---

## 5. How to make local changes to the AI Gateway code (without affecting upstream)

There are valid reasons to make a temporary local change inside `ai_gateway/`:

- Debugging a deploy issue specific to the MIDAS environment.
- Trying a config tweak before requesting it upstream.
- Patching a hot bug while the upstream PR is in review.

**The push-URL disable + the workflow below ensure these never reach the upstream branch.**

### 5.1 Make the change

```bash
cd ai_gateway
git checkout -b local/<your-name>/<short-description>   # never push this branch
# edit files...
git status
git commit -am "local: <describe change>"
```

### 5.2 What just happened

- A local branch exists **only on your laptop** inside the submodule.
- `git push` would fail (push URL is `DISABLED`). You can verify: `git -C ai_gateway push` → should error with "DISABLED".
- The MIDAS repo now sees the submodule as "dirty" (HEAD moved off the pinned SHA). This is intentional and visible: `git status` from the MIDAS root shows `modified: ai_gateway (new commits)`.

### 5.3 Decide what to do with the change

| Goal | Action |
|---|---|
| Throwaway / debug | Stay on the local branch. When done, `git -C ai_gateway checkout <pinned-sha>` to restore the pinned state. |
| Want it permanently in MIDAS (not upstreamed) | **Avoid.** This silently forks the AI Gateway. Better: open a PR upstream and bump the pinned SHA after merge. If truly necessary, document the local patch in `docs/components/ai_gateway.md` and track it as an explicit deviation. |
| Want it upstream | Open a PR against the upstream repo via the GitHub UI (push from a fork, or ask the AI Gateway team to apply the patch). The MIDAS repo does NOT push to upstream. |

### 5.4 Re-pinning to upstream after your change is merged upstream

Once the upstream team merges your PR, follow §6 to pull the new upstream SHA into MIDAS.

---

## 6. How to pull upstream changes into MIDAS

This is the routine "bump the AI Gateway version" workflow. It is **fully supported by the current setup** because:

- The submodule's **fetch URL is intact** — only the *push* URL is `DISABLED`. `git fetch` and `git pull` from upstream work normally; only outbound pushes to the upstream owner are blocked.
- `.gitmodules` records `branch = develop`, so git knows which upstream branch this submodule tracks.
- The MIDAS index records the submodule as a single SHA pointer (mode `160000`). A "bump" is therefore just a one-line change in MIDAS history — clean, reviewable, revertible.
- Pulling never touches MIDAS-owned files. Their `deploy/`, `helm/`, `infra/` live inside the submodule and are not referenced by MIDAS top-level Terraform/Helm.

### 6.0 First-time bootstrap vs. routine refresh

| Situation | Command |
|---|---|
| Fresh clone of MIDAS (submodule never initialised on this laptop) | `git clone <midas-url> && cd <midas> && git submodule update --init --recursive` |
| You already cloned MIDAS without `--recurse-submodules` | `git submodule update --init --recursive` |
| Someone else bumped the pinned SHA on `main`/`develop` and you just `git pull`'d | `git submodule update --init --recursive` (this checks out the newly-pinned SHA inside `ai_gateway/`) |
| You want to pull the latest tip of upstream `develop` into your working copy and re-pin MIDAS | See §6.1 (one-liner) or §6.2 (manual, recommended) |

### 6.1 Method A — one-liner using the tracked branch

Use this when you trust the upstream branch and just want the latest tip:

```bash
# From the MIDAS repo root
git submodule update --remote --merge ai_gateway
git -C ai_gateway log --oneline -1                     # see what you got
git add ai_gateway
git commit -m "ai_gateway: bump to $(git -C ai_gateway rev-parse --short HEAD)"
git push                                               # pushes only the MIDAS pin update
```

How it works: `git submodule update --remote` reads `branch = develop` from `.gitmodules`, fetches that branch, and moves the submodule HEAD to its tip.

### 6.2 Method B — manual (recommended when you want to inspect before bumping)

Use this when you want to read upstream commits / diff first, or pin to a specific commit instead of the branch tip:

```bash
# 1. Fetch the latest from the upstream branch
cd ai_gateway
git fetch origin
git checkout develop                  # or the branch you track
git pull --ff-only origin develop

# 2. Inspect what changed (highly recommended)
git log --oneline <old-sha>..HEAD
git diff <old-sha>..HEAD              # full diff
git diff --stat <old-sha>..HEAD       # just the file-level summary

# (Optional) pin to a specific upstream commit instead of the branch tip:
git checkout <specific-upstream-sha>

# 3. Return to MIDAS root and commit the new pin
cd ..
git status                            # should show: modified: ai_gateway (new commits)
git add ai_gateway
git commit -m "ai_gateway: bump to <new-sha> (<short summary of upstream changes>)"
git push                              # pushes only the MIDAS pin update; nothing in ai_gateway is pushed
```

### 6.3 Why this has zero effect on the upstream owner

- `git fetch` / `git pull` are *read-only* against the upstream remote — they only download.
- `git push` from inside `ai_gateway/` is structurally blocked: the push URL is `DISABLED`, so the command fails with `'DISABLED' does not appear to be a git repository`.
- `git push` from MIDAS root only publishes MIDAS commits. Submodule commits are only pushed when `--recurse-submodules=on-demand|always` is passed — which we never do, and which would fail anyway because of the `DISABLED` push URL.
- The only thing your bump publishes to the world is the **one-line pointer change** in MIDAS — visible in MIDAS history as `Subproject commit <old> → <new>`.

### 6.4 What the reviewer of the MIDAS PR sees

The MIDAS commit diff for a bump is exactly:

```diff
-Subproject commit ed2d34625580f00621193db5f8171398b5c31f85
+Subproject commit <new-sha>
```

That is the entire MIDAS-side diff. Reviewers should:

1. Open the submodule diff in the GitHub UI (it links straight into the upstream repo's commit range), **or** locally run:

   ```bash
   git -C ai_gateway log --oneline <old-sha>..<new-sha>
   git -C ai_gateway diff <old-sha>..<new-sha>
   ```

2. Verify whether the upstream change requires a **coordinated MIDAS change** — see §6.6.
3. Approve the MIDAS PR only after both are satisfied.

### 6.5 Handling local edits sitting in the submodule before a pull

If you have uncommitted edits or a local branch inside `ai_gateway/` (per §5), shelve them before pulling so the pull is clean:

```bash
cd ai_gateway

# Option A: stash uncommitted edits
git stash push -u -m "local: pre-bump shelf"

# Option B: park a local branch and switch back to the tracked branch
git switch -c local/<your-name>/<short-description>     # creates branch from current HEAD
git switch develop

# Now pull as in §6.2
git pull --ff-only origin develop

# When done, decide:
#   - Re-apply your shelf:   git stash pop
#   - Discard your shelf:    git stash drop
#   - Cherry-pick from your parked branch: git cherry-pick <sha>
```

Reminder: any commits you make on a local branch inside the submodule cannot reach upstream — the push URL is `DISABLED`. This is the safety net that lets you experiment freely.

### 6.6 Coordinated MIDAS change recipe (when an upstream bump needs MIDAS-side work)

Sometimes an upstream change requires a parallel MIDAS update — e.g. a new env var the AI Gateway expects, a new IAM permission, a new Kubernetes secret. Do all of it on **one MIDAS PR**:

1. Bump the submodule (Method A or B above) but **do not commit yet** — keep the working tree dirty.
2. In the MIDAS-owned files (NOT inside `ai_gateway/`), make the matching changes (e.g. update a Helm values file owned by the future AI Gateway pipeline, add a Terraform variable, etc.). Per the isolation rule, never edit files under `ai_gateway/` — make the changes in MIDAS-owned territory.
3. Stage everything and commit together:

   ```bash
   git add ai_gateway <other MIDAS files>
   git commit -m "ai_gateway: bump to <new-sha> + MIDAS coordinated change (<what>)"
   ```

4. The reviewer now sees the bump and the MIDAS-side accommodation in a single, atomic PR.

### 6.7 If `--ff-only` fails

Means upstream history was rewritten, OR your local submodule has unpushed local commits, OR you have local edits on top of the pinned SHA. Investigate before doing anything destructive:

```bash
cd ai_gateway
git status                                # any uncommitted edits?
git log --oneline origin/develop..HEAD    # any local commits not on upstream?
git log --oneline HEAD..origin/develop    # any upstream commits we don't have?
```

- Local commits / edits → see §6.5 to shelve them, then retry.
- Genuine upstream history rewrite → coordinate with the upstream team (Unified-Cloud-DevOps); do **not** force-fetch or rewrite history yourself.

### 6.8 Verify after every pull

Always re-confirm the safety invariants after a pull, especially the first few times:

```bash
git -C ai_gateway remote -v
# Expected:
#   origin  https://ucgithub.exlservice.com/Unified-Cloud-DevOps/bu-digital-exlerate-aigateway.git (fetch)
#   origin  DISABLED                                                                                  (push)

git ls-files --stage ai_gateway
# Expected (mode 160000 = submodule gitlink):
#   160000 <new-sha> 0   ai_gateway

git submodule status
# Expected (no leading '-' or '+', meaning clean and at the recorded SHA):
#    <new-sha> ai_gateway (heads/develop)
```

If the push URL ever shows anything other than `DISABLED`, run `git -C ai_gateway remote set-url --push origin DISABLED` immediately, and find out who changed it.

---

## 7. Rollback

To roll the AI Gateway back to a previous pinned version:

```bash
cd ai_gateway
git checkout <previous-good-sha>
cd ..
git add ai_gateway
git commit -m "ai_gateway: rollback to <previous-good-sha> (<reason>)"
git push
```

---

## 8. Operational notes

- **Do not** add `ai_gateway/**` paths to MIDAS-owned `terraform`, `helm/`, `Jenkinsfile_*`, or any MIDAS deploy code. They live in their own world.
- **Do not** edit `ai_gateway/.gitmodules`-related files from the MIDAS root. The submodule manages its own remotes.
- **Do not** force-push from inside `ai_gateway/`. (You can't to upstream — push is disabled — but `git push --force` to any remote is forbidden by policy.)
- **Do** pull upstream regularly to avoid large catch-up bumps.
- **Do** add a CI check (future work) that fails the MIDAS build if the submodule has uncommitted local changes or has drifted from the recorded pinned SHA without an accompanying MIDAS commit.

---

## 9. Future work

- Create the dedicated Jenkins pipeline for AI Gateway deploy (separate from MIDAS pipelines).
- Add a CI guard in the MIDAS pipeline that asserts `git -C ai_gateway remote get-url --push origin == "DISABLED"`.
- Add a `.cursor/rules/ai_gateway.mdc` rule so AI agents in Cursor know never to edit files under `ai_gateway/` as part of MIDAS work.
- Periodically (monthly?) bump the pinned SHA to keep drift small.

---

## 10. Quick reference (cheat sheet)

| Task | Command |
|---|---|
| First clone | `git clone <midas> && cd <midas> && git submodule update --init --recursive` |
| Refresh after pull | `git submodule update --init --recursive` |
| See pinned SHA | `git -C ai_gateway rev-parse HEAD` |
| Pull upstream + re-pin | `cd ai_gateway && git fetch && git checkout develop && git pull --ff-only && cd .. && git add ai_gateway && git commit -m "ai_gateway: bump"` |
| Verify push is disabled | `git -C ai_gateway remote -v` (push URL must be `DISABLED`) |
| Rollback | `cd ai_gateway && git checkout <sha> && cd .. && git add ai_gateway && git commit` |
| Make a local-only patch | `cd ai_gateway && git checkout -b local/... && edit && git commit` |

---

## 11. Manual-input secrets (`deploy/ai_gateway/scripts/populate-secrets.sh`)

The upstream AI Gateway Terraform creates three Secrets Manager entries that **never get a value from Terraform**:

| Secret name (after MIDAS overlay) | Source of truth |
|---|---|
| `${cluster}-langfuse-ee-license` | Manual: bought from Langfuse, pasted in by a human (or fetched from corporate Vault by CI) |
| `langfuse-cognito-client-id-${cluster}` | The `id` of the `langfuse-observability-${env}` Cognito user-pool client created in the same TF run |
| `langfuse-cognito-client-secret-${cluster}` | The `client_secret` of that same Cognito client |

On a fresh deploy these secrets exist but have no current version, so any `data "aws_secretsmanager_secret_version"` that reads them aborts the apply with `couldn't find resource`.

### What the in-tree fork does for #2 and #3

`deploy/ai_gateway/terraform/modules-midas/secrets.tf` adds `aws_secretsmanager_secret_version.langfuse_cognito_client_{id,secret}` resources that source from the Cognito client outputs. Terraform fills these in itself — no human needed. `lifecycle.ignore_changes = [secret_string]` guards against churn if the client is ever rotated.

### What the script does for #1 (and as a safety-net for #2/#3)

`deploy/ai_gateway/scripts/populate-secrets.sh` is a **manual-step helper** that:

1. **Verifies you are authenticated to AWS account `811391286931`** via `aws sts get-caller-identity`. Refuses to run otherwise — protects against running it against the wrong account by accident.
2. **Discovers the Cognito user-pool by name** (tries `midas-aigtw-${env}-user-pool` first, then `${cluster}-user-pool`). If the pool exists, it also discovers the `langfuse-observability-${env}` client and reads its `ClientSecret`.
3. **Writes a placeholder for the EE license** (`REPLACE_ME-langfuse-ee-license-<epoch>`) unless `--ee-license-value '<real>'` is provided. Always logs that the placeholder must be replaced before UAT/PROD.
4. **Backfills the cognito client id/secret** if the Terraform fix above has not yet run — defensive only; on a healthy run those secrets already have values and the script will `SKIP` them.
5. **Idempotent.** By default it only writes when no current version exists. Use `--force` to overwrite.
6. Supports `--dry-run` to preview the API calls without making them.

### How the script handles SSO auth (and why)

We deliberately do **not** prompt for credentials inside the script. Instead we adopt the project-wide pattern from `deploy/scripts/util/aws-credentials-setup.sh`:

| Mode | What you do | What the script sees |
|---|---|---|
| **A. SSO (recommended)** | `aws sso login --profile midas-dev` once, then `export AWS_PROFILE=midas-dev` | `aws` CLI auto-resolves SSO tokens; `sts get-caller-identity` returns the `architects-ps` role in account `811391286931` |
| **B. STS keys (CI)** | `export AWS_ACCESS_KEY_ID=… AWS_SECRET_ACCESS_KEY=… AWS_SESSION_TOKEN=…` | `aws` uses env vars; account check still catches a wrong-account paste |

The script never reads `~/.aws/credentials` directly, never asks for keys interactively, and never writes credentials anywhere. This means:

- It works the same on a developer laptop and inside the Jenkins agent.
- It is safe to commit and run from any context — there is no path that would silently use the wrong identity.
- The only mandatory ENV var is the AWS region (defaults to `us-east-1` if unset; override with `AWS_REGION` or `AWS_DEFAULT_REGION`).

### Typical usage

```bash
# 1) From your laptop, authenticate via SSO once per ~8h
aws sso login --profile midas-dev
export AWS_PROFILE=midas-dev AWS_REGION=us-east-1

# 2) Preview what the script would do
./deploy/ai_gateway/scripts/populate-secrets.sh --dry-run

# 3) Populate with placeholders (dev only)
./deploy/ai_gateway/scripts/populate-secrets.sh

# 4) Populate the EE license with a real value (UAT / PROD)
./deploy/ai_gateway/scripts/populate-secrets.sh \
    --ee-license-value "$(security find-generic-password -s langfuse-ee -w)" \
    --force
```

### When to (re-)run

| Situation | Re-run? |
|---|---|
| First-ever deploy of an env | YES, before the first `terragrunt apply` (puts the EE license placeholder so the apply doesn't abort) |
| Real Langfuse EE license received | YES, with `--ee-license-value '<real>' --force` |
| Cognito user-pool client was rotated outside Terraform | YES, with `--force` (Terraform's `ignore_changes` will let the script's value win) |
| Terraform was re-applied and finished cleanly | NO (the in-tree-fork resources keep #2 and #3 fresh; #1 already has a value) |

### Where this lives in the deploy story

The script lives at `deploy/ai_gateway/scripts/`, parallel to other manual-step helpers in `deploy/scripts/util/`. It is intentionally not wired into a Jenkins stage today — it is a **human-runs-once** step that the SOP captures explicitly. Once the corporate Vault path for the Langfuse EE license is decided (M-7), the same script can be promoted to a CI step by passing `--ee-license-value` from a Vault lookup.


---

## License & SSO posture for MIDAS dev (no-license / no-Cognito-SSO mode)

**Status:** ACTIVE for `ns-ai-midas-dev-use1-dev` (account `811391286931`).
**Set in Step 30 of the SOP.**

### TL;DR

- We do **not** own a Langfuse EE license or a LiteLLM Enterprise license today.
- We **cannot** wire SSO end-to-end because we don't yet have the corporate IdP SAML metadata.
- Both apps support an OSS / no-SSO mode. We deploy in that mode for dev.

### Configuration that makes this work

| Component | Env var | Value | Effect |
|---|---|---|---|
| Langfuse | `LANGFUSE_EE_LICENSE_KEY` | `""` (empty) | OSS (MIT-licensed) mode. All CORE features. EE features disabled. |
| Langfuse | `AUTH_CUSTOM_*` | **unset** | Falls back to NextAuth credentials provider (local email + password against Postgres). |
| LiteLLM | `LITELLM_LICENSE` | `""` (empty) | Community / OSS proxy mode. Master-key auth only. |
| C1-API | `cognitoUserPoolId` / `cognitoAppClientId` | placeholder values from TF | Service starts; auth happens lazily per-request, so end-user calls would 401 until a real token issuer is wired (acceptable for dev deploy validation). |
| Cognito (AWS) | (infra) | created by TF, no SAML IdP, 0 users | Dormant. Apps don't reference it. No commercial license needed for AWS Cognito. |

### Where the empty-license values come from

- `langfuse-ee-license` Secrets Manager secret: created by TF with `secret_string = ""` and `lifecycle { ignore_changes = [secret_string] }`. Operator can override with `populate-secrets.sh --ee-license-value '<real>' --force` after M-7.
- `litellm-license` Secrets Manager secret: same pattern; default `secret_string = ""`.

### What FAILS without a license + Cognito (intentionally)

- Langfuse: project-level RBAC, audit logs, data retention policies, server-side data masking, UI customization, SCIM, Org-Management API. (Not needed for dev validation.)
- LiteLLM: SSO admin UI, audit logs, JWT-Auth, public-route ACLs, IP-based ACLs, custom Swagger branding, blocked-user lists, key rotations, advanced spend reports.
- All apps: end-user SSO sign-in.

### What WORKS without a license + Cognito

- Langfuse: ingest traces, view traces, prompt management (basic), local user accounts, datasets, evals (most), API keys.
- LiteLLM: full proxy (`/chat/completions`, `/embeddings`, `/images/generations`, etc.), master-key auth, model config, basic spend tracking, Langfuse callback for tracing.
- C1-API: service starts; `/health` endpoint OK.
- All AWS infra: EKS, RDS, Redis, S3, KMS, ALB, Bedrock — all unaffected.

### Promotion path (dev → uat → prod)

1. Procure a real Langfuse EE license → operator writes via `populate-secrets.sh --ee-license-value '<key>' --force`. No TF apply needed (`ignore_changes`).
2. Procure a real LiteLLM Enterprise license → write directly with `aws secretsmanager put-secret-value --secret-id litellm-license-<cluster> --secret-string '<key>'`. No TF apply needed.
3. Receive corporate SAML IdP metadata → re-add `AUTH_CUSTOM_*` env vars to `helm/langfuse/values-<env>.yaml`, set `var.enable_saml_identity_provider = true` in the env's `terragrunt.hcl`, populate `cognito-sso-credentials` secret with the SAML metadata XML, and re-deploy via Jenkins.

### Authoritative sources

- Langfuse: https://langfuse.com/self-hosting/license-key
- LiteLLM: https://docs.litellm.ai/docs/proxy/enterprise
- Investigation captured in: `.cursor/scratch/sop-capture-2026-04-19_1529.md` Step 30.
