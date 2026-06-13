---
name: kt-jenkins-run
description: Standalone "run the MIDAS Jenkins deploy pipeline" skill. Triggers the pipeline with the canonical MIDAS deploy parameters (after confirming the target environment with the user), waits for the build to start, watches status live until a terminal result, and **mandatorily** auto-approves every in-pipeline manual approval / input step via `watch` + `--OK_DELETE_MODIFY` (never leave the pipeline blocked on Jenkins input). On completion, delivers a concise traffic-light summary table plus success stats or failure root cause. Does **not** by default re-trigger after FAILURE; for fix → commit → push → re-run until green, use [`jp_pull_commit_push_run_pipeline_watch_debug_fix_repeat`](../jp_pull_commit_push_run_pipeline_watch_debug_fix_repeat/SKILL.md) or obtain explicit user instruction to retry after a fix. Never mutates AWS from the laptop, and never invokes `approve` manually while `watch` is running (watch owns auto-approval). Use when the user mentions kt_jenkins_run, asks to "run the pipeline", "deploy to dev/uat", "kick off Jenkins", "start the build and watch it", or asks for a live deploy run with end-of-run stats — without a git commit beforehand.
---

# kt_jenkins_run — Trigger + watch + auto-approve + report

This skill is the **deploy-only** counterpart of
[`git_pull_commit_push_jenkins_start`](../git_pull_commit_push_jenkins_start/SKILL.md).
It does **not** commit or push code — use it when the code is already on the
branch Jenkins will deploy and you only want to run the pipeline end-to-end.

## Gold standard (bot-led Jenkins runs)

Automations must **never** trigger `prod` without explicit confirmation, **never** re-trigger a failed build on their own initiative, **never** attempt an AWS mutation from the laptop as a substitute for the pipeline, and must make the live state of the build and its final outcome obvious to the user.

| Principle | Requirement |
|-----------|-------------|
| **Pipeline is the release path** | All environment-changing work goes through the MIDAS deploy pipeline via `.cursor/tools/jenkins_tools.py`. No `terraform apply`, `helm upgrade`, or `kubectl apply` as a substitute. |
| **Confirm target env** | Always confirm the **exact** target environment (`dev`, `uat`, `prod`) with the user before `trigger`. Default to `dev` if they did not say. |
| **One build at a time** | Before triggering, check `status` and `queue`. If another build is already running or queued, ask whether to wait or abort it before starting a new one. |
| **Watch live** | A run without `watch` is invisible — always watch until the build ends (**SUCCESS** / **FAILURE** / **ABORTED**). If the CLI exits early while Jenkins is still running, resume `watch --build N`; verify with `status --json`. |
| **Mandatory manual approval (Jenkins)** | With `REQUIRE_MANUAL_APPROVAL=true`, the pipeline exposes human input steps (e.g. `Approve deploy?`). **Never leave the build waiting at those steps:** always pass `--OK_DELETE_MODIFY` on `watch` so pending inputs are **auto-approved when they appear**. Do **not** run `approve` in parallel with `watch`. Do **not** run `watch` without `--OK_DELETE_MODIFY` when the gate is enabled — the pipeline would hang. |
| **Auto-approve inside watch** | Same as above: `jenkins_tools.py watch` clears pending input steps only when `--OK_DELETE_MODIFY` is set. |
| **Safety gate for mutations** | Every Jenkins-mutating command (`trigger`, `abort`, `approve`, `enable`, `disable`, and `watch`'s auto-approve branch) is protected by the CLI's global **`--OK_DELETE_MODIFY`** flag. Only pass the flag after the user has given *explicit* consent for that specific mutation in the current conversation turn. Without the flag the CLI exits with code 2 before touching Jenkins. |
| **Stop on error, report root cause** | On failure, pull the failed-stage log and quote the earliest distinctive error line. **Do not** re-trigger on your own initiative (see below). |
| **Fix-until-green** | If the user wants automated fix → re-run loops (including git commit/push), use [`jp_pull_commit_push_run_pipeline_watch_debug_fix_repeat`](../jp_pull_commit_push_run_pipeline_watch_debug_fix_repeat/SKILL.md). If they only want deploy retries after they push a fix themselves, they must say so explicitly; then run this skill again after the push. |
| **Summarize on success** | On success, gather compact stats via `stats --history 5`, then render the traffic-light table + report (section 7). |

## When to apply

Use when the user invokes **kt_jenkins_run** or asks to **run / trigger /
kick off / deploy** the MIDAS pipeline and wants it **watched live until it
finishes** with a **clean success or a concrete root-cause report**, without
a preceding git commit.

## Preconditions

1. Run the skill from the repository root (so relative paths like `.cursor/tools/jenkins_tools.py` resolve).
2. Ensure credentials are loaded: `source ~/.zshrc 2>/dev/null || true`. If `JENKINS_USER` or `JENKINS_API_TOKEN` are still missing, tell the user to run `python3 .cursor/tools/jenkins_tools.py setup` and **stop**.
3. Confirm the **target environment** with the user (`dev` / `uat` / `prod`). Never assume `prod` — require the exact word `prod` in the user's latest message.
4. Check for in-flight work:

   ```bash
   python3 .cursor/tools/jenkins_tools.py status --json
   python3 .cursor/tools/jenkins_tools.py queue --json
   ```

   If a build is currently `BUILDING` or there are items in the queue, ask whether to **wait**, **abort**, or **cancel this request** before triggering.

## Workflow

### 1. Confirm the run with the user

- State, in one short paragraph, what is about to happen:
  *"I will trigger the MIDAS deploy pipeline for `<env>`, wait for it to start, then watch until it finishes. **Every** in-pipeline manual approval / input step will be **auto-approved** as soon as it appears (`watch` with `--OK_DELETE_MODIFY`); I will not leave the job waiting at Jenkins for a human. On success I will give you a **traffic-light summary table** plus compact stats; on failure I will show the root cause from the failed-stage log. I will **not** re-trigger after failure unless you ask or we switch to the JP fix-until-green skill. Both the `trigger` and the auto-approving `watch` need `--OK_DELETE_MODIFY` — your approval of this run is the consent I will use to pass that flag."*
- Also list the canonical parameters that will be sent (see table below) and ask whether to override any of them.
- **Wait for explicit approval** before running `trigger`.

### 2. Canonical MIDAS deploy parameters

Unless the user overrides something, use these defaults (aligned with the
`jenkins` skill's mapping table):

| Jenkins parameter | Default | Override only if... |
|---|---|---|
| `GIT_BRANCH` | `deployment/dev-jenkins` | User names a different branch |
| `ENVIRONMENT` | `dev` | User explicitly names `uat` or `prod` |
| `DEPLOY_ALB_NLB` | `true` | User says "skip ALB/NLB" |
| `ENABLE_HELM_DEPLOY` | `true` | User says "skip Helm" |
| `REQUIRE_MANUAL_APPROVAL` | `true` | User says "no approval" — **rare**, confirm twice |
| `ALB_NLB_HTTPS_CERT_ARN` | *(empty)* | User supplies a cert ARN |

### 3. Trigger

`trigger` is Jenkins-mutating and is protected by the CLI's global
**`--OK_DELETE_MODIFY`** safety gate. The user's approval of the run in
section 1 IS the explicit consent required — pass the flag on the
`trigger` call below. Without the flag the CLI exits with code 2 and
**never reaches Jenkins**.

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

- Print the queue URL returned by `trigger`.
- **If `trigger` fails** (4xx/5xx, job disabled, parameter rejected, etc.):
  1. **Stop.** Do not retry with different flags.
  2. Print the exact stderr from the CLI.
  3. State the root cause in one sentence (e.g. "Job is disabled — would need `--OK_DELETE_MODIFY enable` first", "Invalid parameter value for ENVIRONMENT", "SAFETY GATE: missing `--OK_DELETE_MODIFY`").
  4. Wait for user instruction.

### 4. Wait for the build to start

`wait-for-start` is **read-only** and does NOT need `--OK_DELETE_MODIFY`.

```bash
python3 .cursor/tools/jenkins_tools.py wait-for-start --timeout 300 --json
```

- Print the build number and URL returned.
- **If it times out:**
  1. **Stop.** Do not re-trigger.
  2. Print `queue --json` so the user can see why it is stuck.
  3. Ask whether to keep waiting, inspect the queue item, or give up.

### 5. Watch live, sample logs, auto-approve gates

Always run `watch` with `--log-stats` from this skill. On every poll
interval the CLI samples the console log, parses simple counters, and
prints a compact delta beside stage transitions so the user can see
what is happening between stage boundaries — not just *which* stage is
running, but *how much activity* is inside it:

```
   📊  log=+142 lines (total 3204)  |  warning=+1 (5)  |  tf=+12 (198)  |  docker=+3 (17)
      ↳ recent ERROR-like lines:
        Error: creating IAM Role: AccessDenied: User arn:aws:...
```

The categories it counts (cumulative across the full log so far):
**error**, **warning**, **tf** (Terraform), **docker**, **helm**,
**kubectl**, **aws**. A delta is only printed when something changed
since the last poll, so quiet stages stay quiet.

`jenkins_tools.py watch` detects pending pipeline input steps and, **only
when `--OK_DELETE_MODIFY` is passed**, auto-approves them the first time
they appear in each build — including the MIDAS `"Approve deploy?"` gate.
Without the flag, `watch` still runs and narrates everything, but a
detected gate is *reported* instead of *cleared* and the pipeline will
hang waiting for a human. The same "run this deploy" consent from
section 1 is the authority you use to pass the flag here.

**Do not** invoke `approve` in parallel, and **do not** try to
pre-approve before the gate exists.

```bash
python3 .cursor/tools/jenkins_tools.py --OK_DELETE_MODIFY \
  watch --log-stats --interval 15
```

- Narrate stage transitions as they stream in.
- When the auto-approval line appears (`Auto-approved <gate>`), note it to the user — this is the moment they care about.
- **Keep watching** until the build *ends*. A rising `error=+N` counter during a running stage is a **signal**, not a terminal condition — `watch` will emit the real SUCCESS / FAILURE / ABORTED outcome when the build actually finishes, and only then does section 6 apply.
- If the watch is interrupted (Ctrl-C, network blip) while the Jenkins build itself is still running, re-run the same `--OK_DELETE_MODIFY watch --log-stats --build N` to resume; do **not** re-trigger and do **not** treat the CLI exit as a pipeline failure.

### 6. End-of-run outcome

When `watch` returns, read the final status line it printed and corroborate
with:

```bash
python3 .cursor/tools/jenkins_tools.py status --json
```

#### 6a. SUCCESS

1. Confirm: *"✅ Pipeline #N completed successfully."*
2. Gather stats for the handoff:

   ```bash
   python3 .cursor/tools/jenkins_tools.py stats --build <N> --history 5 --json
   python3 .cursor/tools/jenkins_tools.py stats --build <N> --history 5
   ```

   Use the JSON form for parsing values into the report; the human form is a
   good transcript line for the user. Do **not** invent numbers — use what
   `stats` returns.

3. Render the report in section 7.

#### 6b. FAILURE / UNSTABLE / ABORTED

1. State: *"❌ Pipeline #N finished with result `<RESULT>`. Investigating root cause..."*
2. Pull the failed stage and structured build info:

   ```bash
   python3 .cursor/tools/jenkins_tools.py logs --build <N> --failed-stage
   python3 .cursor/tools/jenkins_tools.py build-info --build <N> --json
   python3 .cursor/tools/jenkins_tools.py stats --build <N> --json
   ```

3. Identify the root cause from the earliest distinctive error line in the
   failed stage. Typical signatures:
   - Terraform: `Error: <...>` (often followed by a resource address and message)
   - Helm / Kubernetes: `Error: <...>`, `ImagePullBackOff`, `CrashLoopBackOff`
   - AWS API: `AccessDenied`, `UnauthorizedOperation`, `ThrottlingException`
   - Shell: `exit code N`, `command not found`
   - First `ERROR` or `FATAL` line in the stage log
   Quote at most **2-4 lines verbatim** and attribute them to the failing stage.
4. **Do not** re-trigger, abort-and-retry, or modify code / infra on your own initiative. Offer next steps.

### 7. Post-run report

**Always begin with a concise traffic-light summary table** (🟢 OK / 🟡 warning / 🔴 failed). Example:

| Area | Light | Notes |
|------|-------|--------|
| Trigger / queue | 🟢 / 🔴 | queued and started vs blocked |
| Jenkins result | 🟢 / 🔴 | SUCCESS vs FAILURE / ABORTED |
| Manual approvals | 🟢 / 🔴 | auto-approved N gate(s); 🔴 only if skill violated (pipeline hung) |
| Stats / tests | 🟢 / 🟡 | all green vs failures / unstable tests |

Then deliver **one** compact ASCII report. Keep it **≤ ~22 lines** unless the user asks
for more detail.

```
╔══════════════════════════════════════════════════════════════╗
║  JENKINS DEPLOY REPORT                          [DATE/TIME]  ║
╚══════════════════════════════════════════════════════════════╝

▸ RUN
  Environment : <dev|uat|prod>
  Branch      : <GIT_BRANCH value>
  Build       : #N
  URL         : <build url>
  Result      : ✅ SUCCESS | ❌ FAILURE | 🚫 ABORTED

▸ STATS
  Duration    : <Xm Ys>   (est. <Am Bs>, <pct>% of estimate)
  Stages      : <total>  (<SUCCESS=..., FAILURE=..., NOT_EXECUTED=...>)
  Slowest     : <stage name>  (<Zs>)
  Artifacts   : <count>
  Tests       : <total> total — pass <P> / fail <F> / skipped <S>   (or "no report")
  Approvals   : Auto-approved <K> gate(s) | no approval gate
  Log         : <total lines>  |  err=<E>  warn=<W>  tf=<T>  docker=<D>  helm=<H>  kubectl=<K>  aws=<A>
  History     : <success>/<analysed> succeeded in last 5 (<rate>%)

▸ FAILURE ROOT CAUSE  (omit on SUCCESS)
  Stage   : <failed stage name>
  Error   :
    <1-3 quoted lines from the failed-stage log>

▸ NEXT STEPS
  □ <actionable item — e.g. investigate, re-trigger after fix, approve manually>
```

## Error-handling contract (applies to every step)

- **Never re-trigger** a failed, aborted, or timed-out build on your own initiative. A failure is a signal, not a task to retry silently.
- **Never call `approve`** separately while `watch` is running — `watch` owns auto-approval when `--OK_DELETE_MODIFY` is set. Only fall back to `approve --OK_DELETE_MODIFY` if `watch` exited before the gate cleared AND the user explicitly asks.
- **Never `abort` silently** — always confirm the action, use `--OK_DELETE_MODIFY abort`, and note the operation may take a few seconds to take effect.
- **Never disable / enable the job** as part of this skill unless the user explicitly asks. Both commands require `--OK_DELETE_MODIFY` and that consent must come from the user, not the skill.
- **Only add `--OK_DELETE_MODIFY`** to commands the user has explicitly approved in this turn. Section 1 covers the initial `trigger` and `watch`. Any *additional* mutation (a follow-up `abort`, `approve`, `enable`, `disable`) requires a fresh confirmation before the flag is added.
- **Never bypass the pipeline** with laptop `terraform apply` / `helm upgrade` / `kubectl apply` — follow `.cursor/rules/jenkins.mdc`.
- **Root cause statements** must be one short sentence derived from the CLI's own output (not a guess). A SAFETY GATE message is its own distinct root cause — report it literally.
- If the user explicitly asks to retry, approve, abort, enable, or disable, proceed with a narrowly scoped action — with the correct `--OK_DELETE_MODIFY` flag — and report each command you run.

## Guardrails

- **Prod gate:** Require the exact word `prod` in the user's latest message before setting `ENVIRONMENT=prod`. Otherwise default to `dev`.
- **Credential fallback:** On 401 / authentication errors, instruct the user to run `python3 .cursor/tools/jenkins_tools.py setup` — the wizard prompts for a fresh token and validates it live.
- **Network:** If the CLI reports it cannot reach `https://ucjenkinsdev.exlservice.com`, ask the user to confirm VPN / network and stop; do not keep retrying.
- **Quiet failures:** If `watch` exits with a non-zero code but the final status cannot be determined, run `status --json` once more before declaring `FAILURE`.

## Related skills

- [`jp_pull_commit_push_run_pipeline_watch_debug_fix_repeat`](../jp_pull_commit_push_run_pipeline_watch_debug_fix_repeat/SKILL.md) — commit + push + deploy with **fix → re-run until green** (and traffic-light reporting).
- [`git_pull_commit_push_jenkins_start`](../git_pull_commit_push_jenkins_start/SKILL.md) — commit + push **then** run this exact flow.
- [`git_pull_commit_push`](../git_pull_commit_push/SKILL.md) — git-only base flow (no Jenkins).
- [`jenkins`](../jenkins/SKILL.md) — natural-language interface to every `jenkins_tools.py` command.
