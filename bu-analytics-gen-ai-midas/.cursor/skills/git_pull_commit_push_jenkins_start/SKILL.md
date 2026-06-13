---
name: kt-git-pull-commit-push-jenkins-start
description: Pulls the latest changes, reads staged/working-tree diffs, summarizes what changed, proposes a concise imperative commit message, waits for explicit user approval (or an alternate message), then commits and pushes with the repo's git config. On successful push, triggers the MIDAS Jenkins deploy pipeline, waits for it to start, watches until a terminal build state (**mandatory** auto-approval of every in-pipeline manual approval / input step via `watch` + `--OK_DELETE_MODIFY`), and on finish delivers a **traffic-light summary table** plus either root cause of any failure or aggregate build stats (`jenkins_tools.py stats`). Does **not** by default fix code and re-run until green; for that loop use [`jp_pull_commit_push_run_pipeline_watch_debug_fix_repeat`](../jp_pull_commit_push_run_pipeline_watch_debug_fix_repeat/SKILL.md). On any git error or merge conflict, stops immediately and reports root cause (and a conflict table) without attempting a fix unless the user explicitly asks. Use when the user mentions kt_git_pull_commit_push_jenkins_start, wants to pull-commit-push-then-deploy from the current folder, asks to ship after committing, or asks for a commit title followed by a Jenkins run with live progress and end-of-run stats.
---

# kt_git_pull_commit_push_jenkins_start — Pull, commit, push, then trigger + watch Jenkins with stats

This skill is the **git + deploy** extension of
[`git_pull_commit_push`](../git_pull_commit_push/SKILL.md). Sections 1-8 behave
identically to that skill. Sections 9-12 add the Jenkins deploy run.

## Gold standard (bot-led git operations)

Automations must **never** guess commit text from filenames alone, **never** run `git commit` or `git push` before **explicit user approval**, **never** attempt to resolve merge conflicts or other git errors automatically, and must make the next step obvious for a human reviewer.

| Principle | Requirement |
|-----------|-------------|
| **Pull first** | Always run `git pull` (fast-forward/merge per repo config) **before** proposing a commit, so the local branch is up to date with the tracked remote. |
| **Understand** | Use `git status`, `git diff`, and `git diff --cached` so the message reflects **actual** additions, removals, and intent. |
| **Explain briefly** | Before the proposed subject, give a **short** plain-language summary (a few bullets or sentences) of *what* changed so the developer trusts the message matches the diff. |
| **One clear ask** | Show the **proposed first line** (and optional body if used). Ask whether to **proceed as-is** or **paste an edited subject/body**. |
| **Execute only after OK** | Run `git commit` / `git push` only after the user approves or supplies the final text. |
| **Stop on error** | On **any** git failure (pull, merge conflict, commit, push), **stop immediately**, report the **root cause verbatim**, and **do not attempt a fix** unless the user explicitly asks. |
| **Report** | After push, give a compact handoff (subject, SHA, branch, remote, outcome). |
| **Jenkins is the release path** | After a clean push, trigger the **MIDAS deploy pipeline** via `.cursor/tools/jenkins_tools.py` (never `terraform apply` or `helm upgrade` from the laptop). **Always** watch until **SUCCESS** / **FAILURE** / **ABORTED**. **Mandatory:** auto-approve **every** Jenkins manual approval / input step (`watch` with `--OK_DELETE_MODIFY` when `REQUIRE_MANUAL_APPROVAL=true`) — do **not** leave the pipeline blocked waiting at Jenkins. Finish with a **traffic-light summary table** plus stats or failure RCA. |
| **Safety gate for mutations** | Every Jenkins-mutating command (`trigger`, `abort`, `approve`, `enable`, `disable`, and `watch`'s auto-approve branch) is protected by the CLI's global **`--OK_DELETE_MODIFY`** flag. Only pass the flag after the user has given *explicit* consent for that specific mutation in the current conversation turn. Without the flag the CLI exits with code 2 before touching Jenkins. |

## When to apply

Use when the user invokes **kt_git_pull_commit_push_jenkins_start** or asks to
**pull, commit, push, then deploy through Jenkins** with a **suggested commit
title**, a **live pipeline run**, and a **short handoff report with stats**.
Operate from the **git repository root** that contains the workspace or the
path the user specifies.

## Preconditions

1. Resolve the target repo: `git rev-parse --show-toplevel` from the relevant working directory (or user-provided path).
2. Confirm the current branch and upstream: `git rev-parse --abbrev-ref HEAD`, `git status -sb`, `git remote -v`.
3. If there is **nothing to commit** after the pull (clean index and no staged/unstaged changes that the user intends to include), say so and ask the user whether they still want to trigger the deploy pipeline **without** a new commit — do **not** create an empty commit and do **not** trigger silently.
4. Ensure `JENKINS_USER` and `JENKINS_API_TOKEN` are loaded. At the start of every Jenkins invocation in this skill, run `source ~/.zshrc 2>/dev/null || true`. If credentials are still missing, tell the user to run `python3 .cursor/tools/jenkins_tools.py setup` and **stop**.

## Workflow

### 1. Pull latest from the tracked remote

- Run `git pull` (using the repo's default strategy; do **not** force `--rebase` or `--no-rebase` unless the user asks).
- If the pull succeeds and there are **no conflicts**, continue to step 2.
- **If the pull fails** (e.g. detached HEAD, no upstream configured, auth failure, network error, non-fast-forward with local commits, etc.):
  1. **Stop.** Do not run any further git or Jenkins commands.
  2. Report the **exact error output** from git.
  3. State the **root cause** in one short sentence (e.g. "no upstream branch configured", "authentication failed", "local changes would be overwritten", "diverged history needs rebase/merge decision").
  4. **Do not offer or perform a fix.** Ask the user whether they want you to attempt a remediation, and **wait** for explicit instruction.

#### 1a. Merge conflicts from `git pull`

- Detect conflicts: `git status --porcelain` lines starting with `UU`, `AA`, `DD`, `AU`, `UA`, `DU`, `UD`.
- **Stop immediately.** Do not run `git add`, `git commit`, `git merge --abort`, `git rebase --abort`, `jenkins_tools.py trigger`, or any other recovery / release command.
- Produce a **conflict table** with one row per conflicted file. Use this exact shape (columns may be extended only if the user asks):

| # | Path | Conflict type | Ours (HEAD) | Theirs (incoming) | Base (common ancestor) | Suggested action (for user to choose) |
|---|------|---------------|-------------|-------------------|------------------------|---------------------------------------|
| 1 | `path/to/file` | `both modified` / `both added` / `deleted by us` / `deleted by them` / ... | short description of local change | short description of incoming change | short description of common-ancestor content (or "N/A" if no base) | e.g. "keep ours", "keep theirs", "manual merge", "delete file" - **do not execute** |

  - Populate "Conflict type" from `git status` porcelain codes (`UU` = both modified, `AA` = both added, `DU` = deleted by us but modified by them, etc.).
  - Populate "Ours", "Theirs", and "Base" from `git show :2:<path>`, `git show :3:<path>`, `git show :1:<path>` (or `git diff --ours` / `git diff --theirs` summaries for brevity). Keep each cell to **one short line**.
  - After the table, state: *"Conflicts detected. I have not resolved them, and I have not started the Jenkins pipeline. Tell me how you want to proceed (e.g. which side wins per file, abort the merge/rebase, or hand off to you) and I will only act on your explicit instruction."*

### 2. Inspect and understand changes

- Run `git status` and, as needed, `git diff` / `git diff --cached` to understand what will be committed.
- If changes are **unstaged** and the user expects a full commit, **stage** what belongs in this commit (`git add` with explicit paths - avoid `git add .` unless the user wants everything).
- Internally note: touched paths, behavior vs docs-only, and whether multiple unrelated concerns are mixed (if so, recommend **splitting** commits or ask which scope to include).

### 3. Brief summary for the developer

- After reading the diff, output a **concise** summary (not the commit message): what was added/changed and why it matters, so the developer can sanity-check before approving.
- Keep it proportional to the diff (small change → one sentence; larger → short bullets).

### 4. Propose the commit message

- **Subject:** one line, **≤ ~72 characters**, **imperative mood**, specific, scoped when it helps (e.g. `deploy: widen eks-midas-deploy IAM for EKS API` or `docs(scripts): index deploy/scripts and IAM validator`).
- Base the subject on **actual diffs**, not file names alone.
- **Body (optional):** add only if the user asks, supplies one, or a short bullet body materially helps reviewers (multi-file or non-obvious intent). Separate body from subject with a blank line; keep bullets tight.

### 5. Confirm with the user

- Present, in order: (1) **summary of changes**, (2) **proposed subject** (and body if any), (3) a clear note that **after a successful push the MIDAS Jenkins deploy pipeline will be triggered, watched until it finishes, and every in-pipeline manual approval / input step will be auto-approved** (`watch` + `--OK_DELETE_MODIFY`), and (4) that the final handoff includes a **traffic-light summary** plus detailed stats.
- Ask clearly: **Use this message, commit + push, and then run the Jenkins deploy?** — or — **Reply with your edited subject (and body if needed), and confirm whether to also run the Jenkins deploy.**
- Also ask the user to confirm the **target environment** for the Jenkins run (default `dev`; never assume `uat` / `prod`).
- **Wait for explicit approval** or the user's **final** message text before running `git commit`.

### 6. Commit using existing configuration

- Do **not** override `user.name` / `user.email` unless the user asks.
- Commit with the **approved** subject as the first line. Use the approved body if provided.
- Single-line: `git commit -m "approved subject line"`. Multi-line: `git commit -m "subject" -m "body"` or a heredoc / temp file if the body is long - prefer clarity over cleverness.
- **If the commit fails** (pre-commit hook, nothing staged, signing error, etc.):
  1. **Stop.** Do not retry, amend, or bypass hooks (`--no-verify`). Do **not** trigger Jenkins.
  2. Report the **exact error output**.
  3. State the **root cause** in one sentence.
  4. **Wait** for the user to decide the next step.

### 7. Push using current remote and branch

- Read upstream: `git status -sb` and/or `git rev-parse --abbrev-ref HEAD` and `git remote -v`.
- Push with the repo's normal workflow, typically **`git push`** (uses configured `push.default` and upstream). If no upstream exists, use `git push -u origin <branch>` **only** when that matches how this repo is used - prefer the same pattern the user or repo already uses.
- **If push fails** (auth, permissions, protected branch, non-fast-forward because remote moved again, etc.):
  1. **Stop.** Do **not** `--force`, `--force-with-lease`, retry with different flags, or run another `git pull`. Do **not** trigger Jenkins.
  2. Report the **exact error output** from git.
  3. State the **root cause** in one short sentence.
  4. **Wait** for explicit user instruction before taking any further action.

### 8. Report the git phase (simple and concise)

Deliver a **short** post-push report:

| Section | Content |
|--------|---------|
| **Pull** | Result of `git pull` (up-to-date, fast-forwarded N commits, merge commit created, etc.) |
| **Subject used** | Final first line of the commit |
| **Commit** | Short SHA (`git rev-parse --short HEAD`) |
| **Branch** | Current branch name |
| **Remote** | Remote name and URL used for push (from `git remote get-url`) |
| **Push** | Success, or failure with one-line reason |
| **Notes** | Optional: unstaged leftovers, or "nothing else pending" |

Keep this part **under ~15 lines** unless the user asks for more detail. Then move straight to section 9.

### 9. Trigger the MIDAS Jenkins deploy pipeline

Only reached if **sections 1-7 all succeeded** (pull clean, commit made, push accepted) and the user approved the Jenkins run in section 5.

- Always load credentials first: `source ~/.zshrc 2>/dev/null || true`.
- `trigger` is a **Jenkins-mutating** command and is protected by the CLI's global **`--OK_DELETE_MODIFY`** safety gate. The user's "yes, commit + push + deploy" approval in section 5 IS the explicit consent required — pass the flag on the `trigger` call below. Without it the CLI exits with code 2 and **never reaches Jenkins**.
- Trigger using the canonical MIDAS deploy defaults. Use the target environment the user confirmed in section 5 (default `dev`):

```bash
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
- Immediately wait for the build to start. `wait-for-start` is **read-only** and does NOT need `--OK_DELETE_MODIFY`:

```bash
python3 .cursor/tools/jenkins_tools.py wait-for-start --timeout 300 --json
```

- If `wait-for-start` times out, **stop** and report the queue state (`queue`), do not retry silently.

### 10. Watch live, sample logs, auto-approve gates

**Requirement:** Do **not** end the deploy phase until the Jenkins build reaches a **terminal** state. With `REQUIRE_MANUAL_APPROVAL=true`, input gates exist by design — **you must auto-clear them** via `watch` + `--OK_DELETE_MODIFY`; running `watch` without that flag would stall at `"Approve deploy?"`.

Stream live progress using `watch --log-stats`. Always pass `--log-stats`
from this skill — on every poll interval it samples the console log,
parses simple counters, and prints a compact delta alongside stage
transitions so the user can see *what is actually happening* between
stage boundaries:

```
   📊  log=+142 lines (total 3204)  |  warning=+1 (5)  |  tf=+12 (198)  |  docker=+3 (17)
      ↳ recent ERROR-like lines:
        Error: creating IAM Role: AccessDenied: User arn:aws:...
```

The categories it counts (cumulative across the full log so far):
**error**, **warning**, **tf** (Terraform), **docker**, **helm**,
**kubectl**, **aws**. A delta is only printed when something changed
since the last poll, so quiet stages stay quiet.

`watch` itself is **read-only**, but its *auto-approve* behaviour is a
Jenkins mutation and is gated behind the same `--OK_DELETE_MODIFY` flag
as `trigger`. Pass the flag on the `watch` call below — it is the same
"yes, deploy" consent the user already gave in section 5. Without the
flag, `watch` still runs and narrates everything, but when the
`"Approve deploy?"` gate appears it will **only warn** about the pending
gate instead of clearing it, and the pipeline will hang there.

Do **not** invoke `approve` in parallel with `watch`, and **do not** try
to pre-approve before the gate exists. When a gate is hit and approved,
narrate the single line `watch` prints, e.g. *"Auto-approved `Approve
deploy?`"*.

```bash
python3 .cursor/tools/jenkins_tools.py --OK_DELETE_MODIFY \
  watch --log-stats --interval 15
```

- Watching must continue until the build **ends** (SUCCESS / FAILURE / ABORTED). Do not exit early on a transient error line — elevated `error=+N` counters during a running stage are a *signal*, not a terminal condition, and `watch` will report the real outcome when the build finishes.
- If the watch is interrupted (user Ctrl-C, network blip), **do not** re-trigger the pipeline. Report the build URL and ask the user whether to resume watching (with the same `--OK_DELETE_MODIFY watch --log-stats --build N` command) or stop.
- If the CLI ever exits non-zero while the Jenkins build itself is still running (rare — usually a VPN blip), re-run the same `--OK_DELETE_MODIFY watch --log-stats --build N` to resume; do **not** treat that as a pipeline failure.

### 11. End-of-run outcome

When `watch` returns, determine the build outcome from the last line it printed
(`SUCCESS`, `FAILURE`, `ABORTED`, etc.) and from the `status` command:

```bash
python3 .cursor/tools/jenkins_tools.py status --json
```

**11a. On `SUCCESS`:**

1. Confirm to the user: *"✅ Pipeline #N completed successfully."*
2. Gather compact stats for the handoff:

   ```bash
   python3 .cursor/tools/jenkins_tools.py stats --build <N> --history 5 --json
   ```

   Use `--history 5` so the user also sees the recent success-rate context.
   If the pipeline is chatty and stats output is large, also capture a
   human-rendered version:

   ```bash
   python3 .cursor/tools/jenkins_tools.py stats --build <N> --history 5
   ```

3. Render the key numbers in the post-run report (section 12): total duration
   vs estimate, slowest stage, artifact count, test summary (if any), and the
   recent success rate. These come directly from the JSON returned by the
   `stats` command — do **not** invent numbers.

**11b. On `FAILURE` / `UNSTABLE` / `ABORTED`:**

1. State clearly: *"❌ Pipeline #N finished with result `<RESULT>`. Investigating root cause..."*
2. Fetch the failed-stage log and the build info:

   ```bash
   python3 .cursor/tools/jenkins_tools.py logs --build <N> --failed-stage
   python3 .cursor/tools/jenkins_tools.py build-info --build <N> --json
   ```

3. Identify the root cause from the earliest distinctive error line in the
   failed stage (typical signatures: Terraform `Error:`, Helm `Error:`,
   `CommandException`, AWS API `AccessDenied`, `ImagePullBackOff`, a
   non-zero `exit code N`, or the first ERROR/FATAL line). Quote at most
   2-4 lines verbatim.
4. Also pull `stats` for the failed build so the user sees which stage died and how long it had been running:

   ```bash
   python3 .cursor/tools/jenkins_tools.py stats --build <N> --json
   ```

5. **Do not** re-trigger, abort-and-retry, or modify any infra / code on
   your own initiative. Offer next steps: (a) hand off to the user, (b) ask
   whether to re-trigger after a fix, or (c) view full logs. For **fix → commit → push → re-run until green**, switch to [`jp_pull_commit_push_run_pipeline_watch_debug_fix_repeat`](../jp_pull_commit_push_run_pipeline_watch_debug_fix_repeat/SKILL.md) or obtain explicit user approval for each new pipeline run after a fix.

### 12. Combined post-run report

Deliver a single compact report that covers both the git phase and the
Jenkins phase. Keep it **≤ ~25 lines** unless the user asks for more.

**Always begin section 12 with a concise traffic-light summary table** (🟢 OK / 🟡 warning / 🔴 failed). Example rows:

| Area | Light | Notes |
|------|-------|--------|
| Git pull / push | 🟢 / 🔴 | |
| Jenkins build | 🟢 / 🔴 | SUCCESS vs FAILURE / ABORTED |
| Manual approvals | 🟢 / 🔴 | auto-approved K gate(s); 🔴 only if pipeline hung |
| Tests / stats | 🟢 / 🟡 | optional row from `stats` |

Then the detailed ASCII report:

```
╔══════════════════════════════════════════════════════════════╗
║  GIT + JENKINS DEPLOY REPORT                    [DATE/TIME]  ║
╚══════════════════════════════════════════════════════════════╝

▸ GIT
  Pull      : <up-to-date | fast-forwarded N commits | merge commit>
  Subject   : <final commit subject>
  Commit    : <short SHA>
  Branch    : <branch>
  Remote    : <remote-name>  <remote-url>
  Push      : ✅ SUCCESS  |  ❌ <one-line reason>

▸ JENKINS
  Build     : #N
  URL       : <build url>
  Result    : ✅ SUCCESS | ❌ FAILURE | 🚫 ABORTED
  Duration  : <Xm Ys>   (est. <Am Bs>, <pct>% of estimate)
  Slowest   : <stage name>  (<Zs>)
  Artifacts : <count>
  Tests     : <total> total — pass <P> / fail <F> / skipped <S>   (or "no report")
  Approvals : Auto-approved <K> gate(s) | no approval gate
  Log       : <total lines>  |  err=<E>  warn=<W>  tf=<T>  docker=<D>  helm=<H>  kubectl=<K>  aws=<A>
  History   : <success>/<analysed> succeeded in last 5 (<rate>%)

▸ FAILURE ROOT CAUSE  (omit on SUCCESS)
  Stage  : <failed stage name>
  Error  : <1-3 quoted lines from failed-stage log>

▸ NEXT STEPS
  □ <actionable item — e.g. investigate, re-trigger, approve manually>
```

## Error-handling contract (applies to every step)

- **Never auto-fix git errors.** Merge conflicts, hook failures, auth errors, divergent history, detached HEAD, missing upstream, etc. are **always** reported and handed back to the user.
- **Never run destructive git commands** on your own initiative: `git reset --hard`, `git clean -fd`, `git checkout -- <file>`, `git merge --abort`, `git rebase --abort`, `git push --force*`, `git commit --amend` after push, hook bypass.
- **Never re-trigger a failed Jenkins build** on your own initiative. A failed pipeline is a **signal**, not a task to retry silently.
- **Never skip the watch** — a deploy run without live watching defeats the point of this skill.
- **Never approve a pending input** via a separate `approve` call while `watch` is already running (`watch` owns auto-approval when `--OK_DELETE_MODIFY` is set). Only fall back to `approve --OK_DELETE_MODIFY` if `watch` exits before the gate is cleared AND the user explicitly asks.
- **Only pass `--OK_DELETE_MODIFY` on commands the user has just approved in this turn.** Section 5 covers the initial `trigger` and `watch`. For any *new* mutation (a follow-up `abort`, a separate `approve`, an `enable` / `disable`) you must re-confirm with the user before adding the flag.
- **Root cause statements** (git or Jenkins) must be a single short sentence derived from the tool's own output, not a guess.
- If the user explicitly asks you to resolve an error or re-run ("go ahead and rebase", "re-trigger the pipeline"), then — and only then — proceed with a narrowly scoped action and report each command you run.

## Guardrails

- **Secrets**: If diffs contain obvious secrets (API keys, passwords), **do not** commit; warn the user and remove or rotate first.
- **Scope**: Only commit/push what the user agreed to; do not bundle unrelated work without confirmation.
- **No** `git push --force` to shared default branches unless explicitly requested.
- **Never trigger a `prod` deployment** without an **explicit** confirmation from the user of the exact word `prod` in their latest message. Assume `dev` otherwise.
- **No laptop-driven AWS mutations** (`terraform apply`, `helm upgrade`, `kubectl apply`) as a substitute for the pipeline — follow `.cursor/rules/jenkins.mdc`.
- **One build at a time.** Before triggering, run `status` and `queue`; if another build of this job is already in progress or queued, ask the user whether to wait or abort the other before starting a new one.

## Related skills

- [`git_pull_commit_push`](../git_pull_commit_push/SKILL.md) — the git-only base flow.
- [`jp_pull_commit_push_run_pipeline_watch_debug_fix_repeat`](../jp_pull_commit_push_run_pipeline_watch_debug_fix_repeat/SKILL.md) — same git + deploy flow with **fix → re-run until SUCCESS** and traffic-light reporting.
- [`jenkins_run`](../jenkins_run/SKILL.md) — trigger + watch + stats without a git commit (use when code is already pushed).
- [`jenkins`](../jenkins/SKILL.md) — the natural-language interface to every `jenkins_tools.py` command.
