---
name: jp-pull-commit-push
description: Pulls the latest changes, emits a traffic-light status table (pull result, conflicts, working tree), stops with a conflict table if merge conflicts exist, otherwise summarizes diffs, auto-generates an imperative commit message, commits and pushes immediately WITHOUT asking for confirmation. No Jenkins. On any git error, stops immediately with root cause. Use when the user mentions jp_pull_commit_push, kt_jp_pull_commit_push, wants pull-commit-push with a traffic-light report, or the same flow as jp_pull_commit but including push.
---

# jp_pull_commit_push — Pull, traffic-light report, commit, push, stop

Same structure as [jp_pull_commit](../jp_pull_commit/SKILL.md), plus **`git push`**. Aligns with [kt_git_pull_commit_push](../git_pull_commit_push/SKILL.md) for push semantics and error handling. **No pipeline** (for Jenkins after push, use [git_pull_commit_push_jenkins_start](../git_pull_commit_push_jenkins_start/SKILL.md) or [jp_pull_commit_push_run_pipeline_watch_debug_fix_repeat](../jp_pull_commit_push_run_pipeline_watch_debug_fix_repeat/SKILL.md)).

## Gold standard

| Principle | Requirement |
|-----------|-------------|
| **Pull first** | Run `git pull` before proposing a commit. |
| **Traffic-light table** | After pull (before commit), output the **status table** in §2. |
| **Understand** | `git status`, `git diff`, `git diff --cached` for an accurate message. |
| **No confirmation question** | Generate the commit message from the actual diff and **immediately** commit + push. Do NOT ask the user to approve or confirm the message. |
| **Stop on error** | On pull failure, conflicts, commit failure, or push failure: **stop**, verbatim output + one-sentence root cause; **do not auto-fix** unless the user explicitly asks. |

## When to apply

Use when the user invokes **jp_pull_commit_push** / **kt_jp_pull_commit_push**, or asks for **jp_pull_commit plus push**. Repo root: `git rev-parse --show-toplevel` (or user path).

For **local commit only** (no push), use [jp_pull_commit](../jp_pull_commit/SKILL.md). For the same push behavior **without** the traffic-light table as a formal step, [kt_git_pull_commit_push](../git_pull_commit_push/SKILL.md) remains valid.

## Preconditions

1. Resolve repo root: `git rev-parse --show-toplevel`.
2. Branch and upstream: `git rev-parse --abbrev-ref HEAD`, `git status -sb`, `git remote -v`.
3. If **nothing to commit** after a successful pull, say so and **do not** empty-commit unless the user explicitly asks.

## Workflow

### 1. Pull latest

- Run `git pull` (repo default; do not force `--rebase` / `--no-rebase` unless the user asks).
- **If pull fails:** stop. Exact git output + one-sentence root cause; **wait** for instruction. Do not commit or push.

#### 1a. Merge conflicts after pull

- Detect: `git status --porcelain` (`UU`, `AA`, `DD`, `AU`, `UA`, `DU`, `UD`, etc.).
- **Stop immediately.** No `git add` / `git commit` / `git merge --abort` / `git rebase --abort` unless the user explicitly orders a scoped action.
- Output **§2 traffic-light table** with conflicts **🔴**, then the **conflict detail table** (same columns as [kt_git_pull_commit_push §1a](../git_pull_commit_push/SKILL.md)):

| # | Path | Conflict type | Ours (HEAD) | Theirs (incoming) | Base (common ancestor) | Suggested action (user chooses; do not execute) |
|---|------|---------------|-------------|-------------------|------------------------|--------------------------------------------------|

- After the table: *"Conflicts detected. Nothing was committed or pushed. Tell me how to proceed."*

### 2. Traffic-light status table (required after pull, before commit)

| Check | Light | Detail |
|-------|-------|--------|
| **Remote reach / `git pull`** | 🟢 / 🔴 | e.g. "Fast-forward 3 commits", "Already up to date", or one-line error |
| **Merge conflicts** | 🟢 None / 🔴 Present | Count or "none" |
| **Working tree vs index** | 🟢 / 🟡 / 🔴 | 🟢 clean; 🟡 unstaged only; 🔴 other (e.g. detached HEAD) |
| **Staged changes ready to commit** | 🟢 / 🟡 / 🔴 | 🟢 staged diff; 🟡 nothing staged; 🔴 N/A if conflicts |

If **🔴** on pull or conflicts, **do not commit or push**.

### 3. Inspect and stage

- `git status`, `git diff`, `git diff --cached`.
- Stage with explicit paths (`git add <paths>`). Avoid `git add .` unless the user wants everything.

### 4. Summary and most appropriate commit message

- Concise summary of the diff.
- **Subject:** ≤ ~72 characters, **imperative**, from **actual diffs**.
- **Body:** optional, only if it helps reviewers.

### 5. Commit and push (no confirmation)

- Stage the relevant files with explicit paths.
- **Immediately** run `git commit -m "..."` using the auto-generated subject from §4. Do **not** ask the user to approve or confirm the message first.
- Display the subject used in the §7 final report so the user can see what was committed.
- `git commit -m "..."` (no `--no-verify` unless the user asks).
- **If commit fails:** stop; exact output + root cause; **do not push**.

### 6. Push

- Upstream: `git status -sb`, `git rev-parse --abbrev-ref HEAD`, `git remote -v`.
- Typically **`git push`**. If no upstream, `git push -u origin <branch>` **only** when it matches repo practice.
- **If push fails:** **Stop.** Do not `--force` / `--force-with-lease`, do not retry with different flags, do not run another `git pull` without explicit user instruction. Report exact git output + one-sentence root cause; **wait**.

### 7. Final report

| Item | Value |
|------|--------|
| Pull | Outcome |
| Traffic lights | Recap |
| Commit | Short SHA, subject |
| Branch | Name |
| Remote | Name + URL used for push |
| Push | Success or one-line failure |

Keep the report compact (on the order of **~15 lines** total) unless the user asks for more.

## Error-handling contract

Same as [kt_git_pull_commit_push](../git_pull_commit_push/SKILL.md): no automatic conflict resolution; no destructive commands without explicit instruction; warn on secrets in diff; **no** `git push --force*` to shared default branches unless explicitly requested.

## Optional reference

[kt_buddy](../kt_buddy/SKILL.md).
