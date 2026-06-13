---
name: jp-pull-commit
description: Pulls the latest changes, emits a traffic-light status table (pull result, conflicts, working tree), stops with a conflict table if merge conflicts exist, otherwise summarizes diffs, proposes an imperative commit message, waits for explicit user approval, commits locally only (no push, no Jenkins). On any git error before a successful commit, stops immediately with root cause. Use when the user mentions jp_pull_commit, kt_jp_pull_commit, wants pull then local commit without push, or a pre-push checkpoint commit.
---

# jp_pull_commit — Pull, traffic-light report, commit locally, stop

Fork of the [kt_git_pull_commit_push](../git_pull_commit_push/SKILL.md) workflow: **same pull and conflict discipline**, **same commit-message rules and user approval**, **no `git push`** and **no pipeline**.

## Gold standard (aligned with pull-commit-push)

| Principle | Requirement |
|-----------|-------------|
| **Pull first** | Run `git pull` before proposing a commit so the branch matches the tracked remote. |
| **Traffic-light table** | After pull (and before commit), output the **status table** in §2 so the user sees pass/fail at a glance. |
| **Understand** | Use `git status`, `git diff`, and `git diff --cached` so the message reflects actual changes. |
| **One clear ask** | Show proposed subject (and optional body). Ask to **proceed as-is** or **paste an edited message**. |
| **Execute only after OK** | Run `git commit` only after explicit user approval or the user's final message text. |
| **Stop on error** | On pull failure, conflicts, or commit failure: **stop**, report verbatim output, **do not auto-fix** unless the user explicitly asks. |
| **No push** | Do **not** run `git push`. End after a successful local commit (or after stop conditions). |

## When to apply

Use when the user invokes **jp_pull_commit** / **kt_jp_pull_commit**, or asks to **pull and commit locally without pushing**. Operate from `git rev-parse --show-toplevel` (or a user-provided repo path).

For **pull + commit + push** with the same traffic-light flow as this skill, use [jp_pull_commit_push](../jp_pull_commit_push/SKILL.md). For pull-commit-push without the formal traffic-light table, use [kt_git_pull_commit_push](../git_pull_commit_push/SKILL.md). For **pull + commit + push + Jenkins**, use [git_pull_commit_push_jenkins_start](../git_pull_commit_push_jenkins_start/SKILL.md) or [jp_pull_commit_push_run_pipeline_watch_debug_fix_repeat](../jp_pull_commit_push_run_pipeline_watch_debug_fix_repeat/SKILL.md).

## Preconditions

1. Resolve repo root: `git rev-parse --show-toplevel`.
2. Note branch and upstream: `git rev-parse --abbrev-ref HEAD`, `git status -sb`, `git remote -v`.
3. If there is **nothing to commit** after a successful pull (clean and no intended changes), report and **do not** create an empty commit unless the user explicitly asks.

## Workflow

### 1. Pull latest

- Run `git pull` (repo default merge/rebase; do not force `--rebase` / `--no-rebase` unless the user asks).
- **If pull fails:** stop. Print exact git stderr/stdout, one-sentence root cause, and **wait** for explicit instruction. Do not continue to commit.

#### 1a. Merge conflicts after pull

- Detect conflicts: `git status --porcelain` with `UU`, `AA`, `DD`, `AU`, `UA`, `DU`, `UD`, etc.
- **Stop immediately.** Do not `git add`, `git commit`, `git merge --abort`, or `git rebase --abort` unless the user explicitly orders a scoped action.
- Output the **traffic-light table** (§2) with conflicts **🔴**, then the **conflict detail table** (same columns as [kt_git_pull_commit_push §1a](../git_pull_commit_push/SKILL.md)):

| # | Path | Conflict type | Ours (HEAD) | Theirs (incoming) | Base (common ancestor) | Suggested action (user chooses; do not execute) |
|---|------|---------------|-------------|-------------------|------------------------|--------------------------------------------------|

- After the table: *"Conflicts detected. Nothing was committed. Tell me how to proceed (per file, abort merge/rebase, or you merge manually)."*

### 2. Traffic-light status table (required after pull, before commit)

Emit this table (one row per line; extend Notes only if needed):

| Check | Light | Detail |
|-------|-------|--------|
| **Remote reach / `git pull`** | 🟢 / 🔴 | e.g. "Fast-forward 3 commits", "Already up to date", or paste one-line error |
| **Merge conflicts** | 🟢 None / 🔴 Present | List count or "none" |
| **Working tree vs index** | 🟢 / 🟡 / 🔴 | 🟢 clean; 🟡 unstaged only; 🔴 other (e.g. detached HEAD) — brief note |
| **Staged changes ready to commit** | 🟢 / 🟡 / 🔴 | 🟢 staged diff exists; 🟡 nothing staged (unstaged only); 🔴 N/A if conflicts |

- **🟢** = OK to proceed toward commit (subject to staged content and user approval).
- **🟡** = needs attention (e.g. stage files before commit).
- **🔴** = stop (failed pull, conflicts, or blocking state).

If any row is **🔴** for conflicts or failed pull, **do not commit**.

### 3. Inspect and stage

- `git status`, `git diff`, `git diff --cached`.
- Stage what belongs in this commit with explicit paths (`git add <paths>`). Avoid `git add .` unless the user wants everything.

### 4. Summary and most appropriate commit message

- Short plain-language summary of the diff (bullets or sentences), proportional to change size.
- **Subject:** one line, ≤ ~72 characters, **imperative**, derived from **actual diffs** (not filenames alone).
- **Body:** optional; only if it materially helps reviewers; blank line after subject.

### 5. Confirm, then commit only

**Default (safest):**

- Ask: use this message for **local commit only** (no push), or reply with an edited subject/body.
- **Wait for explicit approval** or final message text.
- `git commit -m "..."` (or multi-line equivalent). Do not use `--no-verify` unless the user asks.

**Optional single-shot:** If the user **explicitly** asks to skip message review in the same request (e.g. "jp_pull_commit auto message" or "commit without asking"), still output §2 table and §4 summary plus the chosen subject in the report, then run `git commit` immediately after staging—**only** when pull succeeded with **no conflicts** and there is something staged.

- **If commit fails:** stop, show exact output, one-sentence root cause, wait for user.

### 6. Final report (no push)

Keep it short:

| Item | Value |
|------|--------|
| Pull | Outcome |
| Traffic lights | Brief recap (all 🟢 at end, or where it stopped) |
| Commit | Short SHA, subject line |
| Branch | Current branch |
| Push | **Skipped** (by design) |

## Error-handling contract

Same as [kt_git_pull_commit_push § Error-handling and Guardrails](../git_pull_commit_push/SKILL.md): no automatic conflict resolution, no destructive commands without explicit instruction, warn on secrets in diff, no force-push.

## Optional reference

Post-task debugging template: [kt_buddy](../kt_buddy/SKILL.md).
