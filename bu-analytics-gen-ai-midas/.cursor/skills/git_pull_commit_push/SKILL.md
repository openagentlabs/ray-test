---
name: kt-git-pull-commit-push
description: Pulls the latest changes, reads staged/working-tree diffs, summarizes what changed, proposes a concise imperative commit message, waits for explicit user approval (or an alternate message), then commits and pushes with the repo's git config. On any error or merge conflict, stops immediately and reports root cause (and a conflict table) without attempting a fix unless the user explicitly asks. Use when the user mentions kt_git_pull_commit_push, wants to pull-commit-push from the current folder, or asks for a commit title before pushing.
---

# kt_git_pull_commit_push - Pull, understand, propose message, confirm, commit, push, report

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

## When to apply

Use when the user invokes **kt_git_pull_commit_push** or asks to **pull, commit, and push** with a **suggested commit title** and a **short handoff report**. Operate from the **git repository root** that contains the workspace or the path the user specifies.

## Preconditions

1. Resolve the target repo: `git rev-parse --show-toplevel` from the relevant working directory (or user-provided path).
2. Confirm the current branch and upstream: `git rev-parse --abbrev-ref HEAD`, `git status -sb`, `git remote -v`.
3. If there is **nothing to commit** after the pull (clean index and no staged/unstaged changes that the user intends to include), say so and **do not** create an empty commit unless the user explicitly asks.

## Workflow

### 1. Pull latest from the tracked remote

- Run `git pull` (using the repo's default strategy; do **not** force `--rebase` or `--no-rebase` unless the user asks).
- If the pull succeeds and there are **no conflicts**, continue to step 2.
- **If the pull fails** (e.g. detached HEAD, no upstream configured, auth failure, network error, non-fast-forward with local commits, etc.):
  1. **Stop.** Do not run any further git commands.
  2. Report the **exact error output** from git.
  3. State the **root cause** in one short sentence (e.g. "no upstream branch configured", "authentication failed", "local changes would be overwritten", "diverged history needs rebase/merge decision").
  4. **Do not offer or perform a fix.** Ask the user whether they want you to attempt a remediation, and **wait** for explicit instruction.

#### 1a. Merge conflicts from `git pull`

- Detect conflicts: `git status --porcelain` lines starting with `UU`, `AA`, `DD`, `AU`, `UA`, `DU`, `UD`.
- **Stop immediately.** Do not run `git add`, `git commit`, `git merge --abort`, `git rebase --abort`, or any other recovery command.
- Produce a **conflict table** with one row per conflicted file. Use this exact shape (columns may be extended only if the user asks):

| # | Path | Conflict type | Ours (HEAD) | Theirs (incoming) | Base (common ancestor) | Suggested action (for user to choose) |
|---|------|---------------|-------------|-------------------|------------------------|---------------------------------------|
| 1 | `path/to/file` | `both modified` / `both added` / `deleted by us` / `deleted by them` / ... | short description of local change | short description of incoming change | short description of common-ancestor content (or "N/A" if no base) | e.g. "keep ours", "keep theirs", "manual merge", "delete file" - **do not execute** |

  - Populate "Conflict type" from `git status` porcelain codes (`UU` = both modified, `AA` = both added, `DU` = deleted by us but modified by them, etc.).
  - Populate "Ours", "Theirs", and "Base" from `git show :2:<path>`, `git show :3:<path>`, `git show :1:<path>` (or `git diff --ours` / `git diff --theirs` summaries for brevity). Keep each cell to **one short line**.
  - After the table, state: *"Conflicts detected. I have not resolved them. Tell me how you want to proceed (e.g. which side wins per file, abort the merge/rebase, or hand off to you) and I will only act on your explicit instruction."*

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

- Present, in order: (1) **summary of changes**, (2) **proposed subject** (and body if any).
- Ask clearly: **Use this message and commit + push?** or **Reply with your edited subject (and body if needed).**
- **Wait for explicit approval** or the user's **final** message text before running `git commit`.

### 6. Commit using existing configuration

- Do **not** override `user.name` / `user.email` unless the user asks.
- Commit with the **approved** subject as the first line. Use the approved body if provided.
- Single-line: `git commit -m "approved subject line"`. Multi-line: `git commit -m "subject" -m "body"` or a heredoc / temp file if the body is long - prefer clarity over cleverness.
- **If the commit fails** (pre-commit hook, nothing staged, signing error, etc.):
  1. **Stop.** Do not retry, amend, or bypass hooks (`--no-verify`).
  2. Report the **exact error output**.
  3. State the **root cause** in one sentence.
  4. **Wait** for the user to decide the next step.

### 7. Push using current remote and branch

- Read upstream: `git status -sb` and/or `git rev-parse --abbrev-ref HEAD` and `git remote -v`.
- Push with the repo's normal workflow, typically **`git push`** (uses configured `push.default` and upstream). If no upstream exists, use `git push -u origin <branch>` **only** when that matches how this repo is used - prefer the same pattern the user or repo already uses.
- **If push fails** (auth, permissions, protected branch, non-fast-forward because remote moved again, etc.):
  1. **Stop.** Do **not** `--force`, `--force-with-lease`, retry with different flags, or run another `git pull`.
  2. Report the **exact error output** from git.
  3. State the **root cause** in one short sentence.
  4. **Wait** for explicit user instruction before taking any further action.

### 8. Report (simple and concise)

Deliver a **short** post-run report:

| Section | Content |
|--------|---------|
| **Pull** | Result of `git pull` (up-to-date, fast-forwarded N commits, merge commit created, etc.) |
| **Subject used** | Final first line of the commit |
| **Commit** | Short SHA (`git rev-parse --short HEAD`) |
| **Branch** | Current branch name |
| **Remote** | Remote name and URL used for push (from `git remote get-url`) |
| **Push** | Success, or failure with one-line reason |
| **Notes** | Optional: unstaged leftovers, or "nothing else pending" |

Keep the whole report **under ~15 lines** unless the user asks for more detail.

## Error-handling contract (applies to every step)

- **Never auto-fix.** Merge conflicts, hook failures, auth errors, divergent history, detached HEAD, missing upstream, etc. are **always** reported and handed back to the user.
- **Never run destructive commands** on your own initiative: `git reset --hard`, `git clean -fd`, `git checkout -- <file>`, `git merge --abort`, `git rebase --abort`, `git push --force*`, `git commit --amend` after push, hook bypass.
- **Root cause statement** must be a single short sentence derived from git's own output, not a guess.
- If the user explicitly asks you to resolve an error or conflict ("go ahead and keep ours", "abort the merge", "rebase onto main", etc.), then - and only then - proceed with a narrowly scoped action and report each command you run.

## Guardrails

- **Secrets**: If diffs contain obvious secrets (API keys, passwords), **do not** commit; warn the user and remove or rotate first.
- **Scope**: Only commit/push what the user agreed to; do not bundle unrelated work without confirmation.
- **No** `git push --force` to shared default branches unless explicitly requested.

## Optional reference

For a fuller post-task template after larger changes, see [kt_debug](../kt_debug/SKILL.md) in this repo.
