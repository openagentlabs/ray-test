---
name: jp-pull-commit-push-run-pipeline-watch-debug-fix-repeat
description: Gold-standard pull → commit → push → Jenkins deploy loop with auto-retry on failure. Pulls the branch, detects and surfaces any merge conflicts (stops for human resolution), proposes and confirms a commit message, pushes, triggers and watches the MIDAS Jenkins pipeline live (mandatory auto-approval of every in-pipeline manual approval / input step via watch + --OK_DELETE_MODIFY), always watches status until the build reaches a terminal state, and on failure diagnoses root cause, proposes a fix, and either asks Y/N per iteration or applies fixes and re-runs until SUCCESS when the user gave upfront session consent ("until green" / "fix and rerun until working"). On SUCCESS or final exit, delivers a concise traffic-light summary table plus the detailed report. Uses .cursor/tools/jenkins_tools.py for all Jenkins operations. Use when the user mentions jp_pull_commit_push_run_pipeline_watch_debug_fix_repeat, wants to ship code and fix any pipeline failures in a loop, or asks for a "commit-push-deploy-fix" cycle.
---

# jp_pull_commit_push_run_pipeline_watch_debug_fix_repeat — Pull → Commit → Push → Deploy → Watch → Debug → Fix → Repeat

Gold-standard release cycle for MIDAS. Extends
[`kt_git_pull_commit_push_jenkins_start`](../git_pull_commit_push_jenkins_start/SKILL.md)
with a **debug-fix-repeat loop**: always watch to a **terminal** Jenkins result;
**mandatorily auto-approve** Jenkins manual approval / input steps via `watch`
with `--OK_DELETE_MODIFY`; on failure, diagnose, propose a fix, then either ask
**Y/N** each time or **iterate until green** when the user gave **session-wide**
consent. Finish with a **traffic-light table** plus the detailed report.

## Principles

| Principle | Requirement |
|-----------|-------------|
| **Pull first** | Always `git pull` before proposing a commit. |
| **Stop on conflict** | Merge conflicts → surface conflict table → stop. Do not guess at a resolution. |
| **No silent commits** | Propose commit message from actual diff. Wait for user approval (except iterations after session-wide fix consent — still no empty or guessed commits). |
| **Pipeline is the release path** | Never `terraform apply` / `helm upgrade` / `kubectl apply` from the laptop. Only `jenkins_tools.py`. |
| **Watch until done** | Always run `watch --log-stats` until the build ends (**SUCCESS** / **FAILURE** / **ABORTED**). Never exit early on transient log errors. If the CLI drops mid-run, resume with `watch --build N`; corroborate with `status --json`. |
| **Mandatory manual approval (Jenkins)** | The MIDAS deploy uses input gates when `REQUIRE_MANUAL_APPROVAL=true`. **You must not leave the pipeline waiting on a human at Jenkins:** always pass `--OK_DELETE_MODIFY` on `watch` so pending input steps (e.g. `Approve deploy?`) are **auto-approved as soon as they appear**. Do **not** call `approve` in parallel with `watch`. Do **not** trigger with manual approval required and then run `watch` without `--OK_DELETE_MODIFY`. |
| **Trigger parameters** | Keep `REQUIRE_MANUAL_APPROVAL=true` unless the user explicitly overrides — auto-approval is handled **inside** `watch`, not by disabling the gate in Jenkins. |
| **Stop on failure, propose fix** | On pipeline failure, diagnose root cause from failed-stage log, propose a concrete fix. |
| **Loop until green** | After a fix is applied, run **Phase A → Phase B** again until **SUCCESS** or stop condition. Default: ask **Y/N** before each fix. If the user explicitly grants **session-wide consent** (phrases like *fix and rerun until green*, *until the pipeline passes*, *keep fixing until it works*), treat that as approval to **apply proposed fixes and re-run without asking Y/N each time**, until SUCCESS or the max-iteration guardrail — still stop on git conflicts, credential failures, or SAFETY GATE errors until the user resolves them. |
| **User owns mutations** | Initial `trigger`, `watch` (auto-approve), `git commit`, and `git push` require explicit consent per [`git_pull_commit_push_jenkins_start`](../git_pull_commit_push_jenkins_start/SKILL.md) section 5 / this skill's A4. Re-triggers after failure require either per-iteration **Y** or the session-wide fix consent above. |

## When to apply

Invoke with **jp_pull_commit_push_run_pipeline_watch_debug_fix_repeat** or when the user asks to ship code and keep
fixing until Jenkins is green. Operate from the **git repository root**.

---

## Preconditions

### 0. AWS SSO authentication check (always first)

Before any git or Jenkins work, verify the `midas-dev` AWS SSO session is valid and not expired.

```bash
aws sts get-caller-identity --profile midas-dev 2>&1
```

**Interpret the result:**

| Output | Meaning | Action |
|--------|---------|--------|
| JSON with `UserId`, `Account`, `Arn` | Session valid ✅ | Continue to step 1 |
| `Error … Token … expired` / `InvalidClientTokenId` / `UnauthorizedException` / non-zero exit | Session expired or missing ❌ | Run SSO login (below), then re-verify |
| Any other error (network, profile not found) | Config problem ❌ | Stop, print exact error, ask user to fix |

**If login is needed:**

```bash
aws sso login --profile midas-dev
```

Wait for the command to complete (it opens the browser for the device-auth flow). Then re-run `aws sts get-caller-identity --profile midas-dev` to confirm the session is now valid. If it still fails, **stop** and report the exact error — do not proceed.

Print the authenticated identity before continuing:

```
🔐 AWS SSO  Account: <Account>  Role: <Arn>  ✅ authenticated
```

---

1. `git rev-parse --show-toplevel` — confirm repo root.
2. `git rev-parse --abbrev-ref HEAD` + `git status -sb` + `git remote -v` — confirm branch and upstream.
3. Load Jenkins credentials: `source ~/.zshrc 2>/dev/null || true`. If `JENKINS_USER` or `JENKINS_API_TOKEN` missing, tell the user to run `python3 .cursor/tools/jenkins_tools.py setup` and **stop**.
4. Check for in-flight Jenkins builds:
   ```bash
   python3 .cursor/tools/jenkins_tools.py status --json
   python3 .cursor/tools/jenkins_tools.py queue --json
   ```
   If a build is already `BUILDING` or queued, ask the user whether to wait, abort, or stop before proceeding.

---

## Loop structure

```
LOOP:
  Phase A  — Git: pull → detect conflicts → inspect diff → propose commit → confirm → commit → push
  Phase B  — Jenkins: trigger → wait-for-start → watch (mandatory auto-approve inputs) → outcome
  If SUCCESS  → traffic-light table + combined report → EXIT (done)
  If FAILURE  → diagnose root cause → propose fix
    If session-wide fix consent → apply fix → LOOP from Phase A (respect max iterations / duplicate RCA guard)
    Else → ask Y/N → If N → EXIT | If Y → apply fix → LOOP from Phase A
```

---

## Phase A — Git

### A1. Pull

```bash
git pull
```

- Clean pull → continue to A2.
- Pull fails (auth, no upstream, diverged, etc.) → **stop**, print exact error, state root cause in one sentence, ask user for instruction. Do not proceed.

#### A1a. Merge conflicts

Detect via `git status --porcelain` (lines `UU`, `AA`, `DD`, `AU`, `UA`, `DU`, `UD`).

**Stop immediately.** Render a conflict table:

| # | Path | Conflict type | Ours (HEAD) | Theirs (incoming) | Base | Suggested action |
|---|------|---------------|-------------|-------------------|------|-----------------|
| 1 | `path/to/file` | `both modified` | local change summary | incoming change summary | ancestor summary | keep ours / keep theirs / manual merge |

Populate Ours/Theirs/Base from `git show :2:<path>`, `git show :3:<path>`, `git show :1:<path>`. Keep cells to one short line.

After the table state: *"Conflicts detected. I have not resolved them. Tell me how you want to proceed and I will act only on your explicit instruction."*

Do **not** start Phase B.

### A2. Inspect changes

```bash
git status
git diff
git diff --cached
```

Stage unstaged files that belong in this commit using explicit paths (avoid `git add .` unless the user wants everything).

Note: secrets in diffs → **do not commit**, warn user.

### A3. Summary + commit proposal

- Output a **brief plain-language summary** of what changed (bullets for larger diffs, one sentence for small ones).
- Propose: one-line subject, ≤ 72 chars, imperative mood, scoped (e.g. `deploy: add Cognito OIDC config for Langfuse`).
- Subject must come from actual diff content, not filenames alone.

### A4. Confirm with user

Present:
1. Change summary
2. Proposed commit subject
3. Note: *"After push, the MIDAS Jenkins deploy pipeline will be triggered and watched until it finishes. **Every** in-pipeline manual approval / input step will be auto-approved (`watch` + `--OK_DELETE_MODIFY`). The final report includes a traffic-light summary."*
4. Confirm target environment (`dev` default; never assume `uat` / `prod`).
5. **Optional:** If the user asked to *fix and rerun until green* / *until the pipeline passes*, record **session-wide fix consent** so Phase B4b can loop without per-failure Y/N (still respect max iterations and duplicate-root-cause guardrails).

Ask: **"Use this message, commit + push, and run Jenkins deploy to `<env>`? Or reply with your edited subject."**

**Wait for explicit approval before running `git commit`.**

### A5. Commit

```bash
git commit -m "<approved subject>"
```

Failure → **stop**, print exact error, state root cause, wait for user.

### A6. Push

```bash
git push
```

Failure → **stop**, print exact error, state root cause in one sentence, wait for user. Do **not** `--force`.

### A6. Git phase report (compact, ≤ 15 lines)

| Field | Value |
|-------|-------|
| Pull | up-to-date / fast-forwarded N / merge commit |
| Subject | final commit subject |
| Commit | short SHA |
| Branch | branch name |
| Remote | remote name + URL |
| Push | ✅ SUCCESS / ❌ reason |

---

## Phase B — Jenkins

### B1. Trigger

```bash
source ~/.zshrc 2>/dev/null || true

python3 .cursor/tools/jenkins_tools.py --OK_DELETE_MODIFY trigger \
  --param GIT_BRANCH=deployment/dev-jenkins \
  --param ENVIRONMENT=<env> \
  --param DEPLOY_ALB_NLB=true \
  --param ENABLE_HELM_DEPLOY=true \
  --param REQUIRE_MANUAL_APPROVAL=true \
  --param ALB_NLB_HTTPS_CERT_ARN= \
  --json
```

Print the queue URL. On trigger failure → **stop**, print exact stderr, state root cause, wait for user.

### B2. Wait for build to start

```bash
python3 .cursor/tools/jenkins_tools.py wait-for-start --timeout 300 --json
```

Timeout → print `queue --json`, ask user whether to keep waiting or stop.

### B3. Watch live (auto-approve gates)

```bash
python3 .cursor/tools/jenkins_tools.py --OK_DELETE_MODIFY \
  watch --log-stats --interval 15
```

- Narrate stage transitions as they appear.
- When auto-approval fires, note it: *"Auto-approved `<gate name>`."*
- **Keep watching until the build ends.** A rising `error=+N` counter is a signal, not a terminal condition.
- If watch is interrupted (Ctrl-C / network blip) while the build is still running: re-run `--OK_DELETE_MODIFY watch --log-stats --build N` to resume. Do **not** re-trigger.

### B4. Outcome

```bash
python3 .cursor/tools/jenkins_tools.py status --json
```

#### B4a — SUCCESS

1. Confirm: *"✅ Pipeline #N completed successfully."*
2. Gather stats:
   ```bash
   python3 .cursor/tools/jenkins_tools.py stats --build <N> --history 5 --json
   python3 .cursor/tools/jenkins_tools.py stats --build <N> --history 5
   ```
3. Render the combined report (section "Combined report" below) and **exit the loop**.

#### B4b — FAILURE / UNSTABLE / ABORTED

1. State: *"❌ Pipeline #N finished with `<RESULT>`. Investigating root cause..."*
2. Pull diagnostics:
   ```bash
   python3 .cursor/tools/jenkins_tools.py logs --build <N> --failed-stage
   python3 .cursor/tools/jenkins_tools.py build-info --build <N> --json
   python3 .cursor/tools/jenkins_tools.py stats --build <N> --json
   ```
3. Identify the earliest distinctive error line in the failed stage (Terraform `Error:`, Helm `Error:`, `AccessDenied`, `ImagePullBackOff`, `exit code N`, first `ERROR`/`FATAL` line). Quote **2-4 lines verbatim**.
4. State root cause in **one sentence** derived from the log, not a guess.
5. Propose a **concrete, minimal fix** (e.g. "Add missing IAM action `eks:DescribeCluster` to the deployer policy at `deploy/.../iam.tf` line N", or "Correct the Docker image tag in `values-midas-dev.yaml`"). Be specific about file and change.
6. If **session-wide fix consent** is **not** in effect, ask the user:

   > **Root cause:** `<one sentence>`
   > **Proposed fix:** `<specific change>`
   > **Apply this fix and re-run the pipeline? [Y/N]**

   If session-wide consent **is** in effect, still output root cause + proposed fix for the transcript, then continue to step 7 without waiting.

7. **Wait for explicit Y or N** only when session-wide fix consent does **not** apply. Otherwise proceed to apply the fix and Phase A. In all cases honour **max iterations** and stop if the **same root cause** repeats twice (flag to user before repeating the same fix).

   - **N** → hand off: *"Understood. No further action taken. Here is the build URL for your reference: `<url>`."* → **exit**.
   - **Y** (or session-wide consent) → apply the fix (edit the relevant file(s)), then **go back to Phase A** for the next iteration.

---

## Combined post-run report (render on SUCCESS or final exit)

**Always start the handoff with a concise traffic-light summary table** (overall outcome + major areas). Use **🟢 OK**, **🟡 warning / partial**, **🔴 failed / blocked**. Example shape (adjust rows to match what happened):

| Area | Light | Notes |
|------|-------|--------|
| AWS SSO auth | 🟢 / 🔴 | valid session / login required or failed |
| Git (pull / push) | 🟢 / 🟡 / 🔴 | e.g. clean push vs conflict stopped |
| Jenkins build | 🟢 / 🔴 | SUCCESS vs FAILURE / ABORTED |
| Manual approvals | 🟢 / 🔴 | auto-approved N gate(s) vs hung (should never be 🔴 if skill followed) |
| Fix iterations | 🟢 / 🟡 | e.g. green on first try vs N fixes applied |

Then render the detailed ASCII report:

```
╔══════════════════════════════════════════════════════════════╗
║  jp_pull_commit_push_run_pipeline_watch_debug_fix_repeat     ║
║  DEPLOY REPORT                                  [DATE/TIME]  ║
╚══════════════════════════════════════════════════════════════╝

▸ AWS SSO
  Profile   : midas-dev
  Account   : <Account ID>
  Role      : <Arn>
  Status    : ✅ valid session | 🔄 re-authenticated | ❌ failed

▸ GIT  (iteration <N>)
  Pull      : <result>
  Subject   : <commit subject>
  Commit    : <short SHA>
  Branch    : <branch>
  Remote    : <remote> <url>
  Push      : ✅ SUCCESS | ❌ <reason>

▸ JENKINS
  Build     : #N
  URL       : <url>
  Result    : ✅ SUCCESS | ❌ FAILURE | 🚫 ABORTED
  Duration  : <Xm Ys>  (est. <Am Bs>)
  Slowest   : <stage>  (<Zs>)
  Approvals : auto-approved <K> gate(s) | no gate
  Log       : <lines>  err=<E>  warn=<W>  tf=<T>  docker=<D>  helm=<H>
  History   : <S>/<5> succeeded in last 5 builds (<rate>%)

▸ ITERATIONS
  Total loops   : <N>
  Fixes applied : <list of one-line fix summaries, or "none">

▸ FAILURE ROOT CAUSE  (omit on SUCCESS)
  Stage  : <failed stage>
  Error  : <1-3 quoted lines>

▸ NEXT STEPS
  □ <actionable item>
```

---

## Error-handling contract

- **Never auto-fix git errors.** Conflicts, hook failures, auth errors → always stop and hand back.
- **Never run destructive git commands**: `reset --hard`, `clean -fd`, `push --force*`, `merge --abort`, `rebase --abort`, hook bypass (`--no-verify`), `commit --amend` after push.
- **Never re-trigger without authorization.** Re-trigger only after **Y** on the proposed fix, or under **session-wide fix consent** (see Principles). Do not silently retry the same build without a code/config change when the failure was substantive.
- **Never approve a gate separately** while `watch` is running — `watch` owns auto-approval.
- **Never bypass the pipeline** (`terraform apply`, `helm upgrade`, `kubectl apply` from laptop).
- **Only pass `--OK_DELETE_MODIFY`** after explicit user consent. The initial consent in A4 covers the first `trigger`/`watch`; further `trigger`/`watch` pairs in the same loop reuse consent when the user approved session-wide fix-and-rerun, or after each explicit **Y**.
- **Never trigger `prod`** without the exact word `prod` in the user's latest message.
- **Secrets in diff** → do not commit; warn and stop.

## Guardrails

- Max iterations: if the loop has run **5 times without SUCCESS**, stop proactively and ask the user whether to continue. Summarise all fixes attempted so far.
- Each fix must be **narrowly scoped** — only touch what the root cause requires.
- If two consecutive failures have the **same root cause**, flag this to the user before proposing the same fix again (it may not have been applied correctly or the real cause is different).

## Related skills

- [`git_pull_commit_push_jenkins_start`](../git_pull_commit_push_jenkins_start/SKILL.md) — single-shot commit + deploy (no fix loop).
- [`jenkins_run`](../jenkins_run/SKILL.md) — deploy only, no git.
- [`git_pull_commit_push`](../git_pull_commit_push/SKILL.md) — git only, no Jenkins.
- [`jenkins`](../jenkins/SKILL.md) — natural-language interface to `jenkins_tools.py`.
