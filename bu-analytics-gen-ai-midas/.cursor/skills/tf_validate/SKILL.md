---
name: kt-tf-validate
description: Validates MIDAS Terraform under deploy/ using Checkov via .cursor/scripts/tf_validate.py, then walks the user through fixing every finding one at a time. Verifies the Checkov CLI is installed (asking before installing). After rendering the report table, turns each failed check into a tracked todo, and for each item diagnoses the root cause, explains it plainly, proposes a concrete fix, and asks the user Y/N to apply it. Re-runs Checkov after every fix and continues until no violations remain, then chains into the git_pull_commit_push skill to pull/commit/push the remediation. Use when the user mentions kt_tf_validate, tf_validate, asks to validate/scan/fix the Terraform in deploy/, run Checkov, remediate IaC findings, or "check my Terraform and fix the issues then push".
---

# kt_tf_validate — Validate, fix, and ship MIDAS Terraform

Interactive Checkov driver for the MIDAS `deploy/` tree. Drives
[`.cursor/scripts/tf_validate.py`](../../scripts/tf_validate.py), renders a
markdown report of every finding, converts the findings into a todo list,
walks the user through each one with a **Y/N fix prompt**, re-validates
between fixes, and on a clean scan hands off to
[`git_pull_commit_push`](../git_pull_commit_push/SKILL.md) to pull, commit,
and push the remediation.

## When to apply

Use when the user invokes **kt_tf_validate** / **tf_validate**, or asks to:

- Validate / scan / check the Terraform in **`deploy/`**.
- Run **Checkov** against MIDAS IaC.
- Get a security / compliance / misconfiguration report and **fix** the
  findings iteratively.
- "Check my Terraform and push the fixes" — scan, remediate, then commit.

Scope: static analysis + guided remediation of Terraform source files
under `deploy/`. This skill **never** runs `terraform plan`,
`terraform apply`, `helm`, `kubectl`, or any AWS mutation. Infrastructure
promotion still goes through the MIDAS Jenkins pipelines per
`.cursor/rules/jenkins.mdc`; this skill stops at `git push`.

## Preconditions

1. Run from the repository root so `.cursor/scripts/tf_validate.py` and
   `deploy/` resolve.
2. Python 3.9+ on `PATH`.
3. `deploy/` (or the user-supplied `--path`) exists.
4. A clean working tree is **not** required — the remediation loop may
   introduce changes. Warn the user if there are unrelated local changes
   before proposing fixes so they can stage/stash them first.

## Workflow

### 1. Pre-flight: is Checkov installed?

Run a quick tool probe **before** invoking the scanner so the skill can
ask the user up-front instead of failing mid-scan:

```bash
command -v checkov >/dev/null 2>&1 && checkov --version || echo "MISSING"
```

- If the output starts with a version string: proceed to step 2.
- If it prints `MISSING` (or the command exits non-zero):
  1. Tell the user plainly: *"Checkov is not installed on this machine."*
  2. Offer both install paths:
     - **Preferred:** `brew install checkov`
     - **Fallback:** `python3 -m pip install checkov`
  3. **Ask the user**: *"Do you want me to install Checkov via Homebrew
     now so I can run the validation?"*
  4. **Wait for an explicit yes** before running any install command.
  5. On `yes`: run `brew install checkov` (or delegate to
     `tf_validate.py --install`) and verify with `checkov --version`.
  6. On `no`: stop the skill and return a one-line note that validation
     was skipped because the tool is missing. Do **not** attempt the scan.

### 2. Determine the scan path

Default scan path is the whole **`deploy/`** tree. If the user named a
sub-path (e.g. `deploy/ecs-app`, `deploy/deploy_role`), use that instead.

### 3. Run the scanner (JSON mode)

Always drive the script in `--json` mode — that is what the skill parses
to build the report **and** the remediation todo list.

```bash
python3 .cursor/scripts/tf_validate.py --path deploy --json
```

Interpret the exit code:

| Exit | Meaning | Skill action |
|------|---------|--------------|
| `0`  | No failed checks.             | Render "clean" report (step 4a); skip remediation; go to step 7. |
| `1`  | Failed checks found.          | Render "violations" report (step 4b); build the todo list (step 5). |
| `2`  | Operational error in Checkov. | Show the error payload verbatim, stop. |
| `3`  | Checkov not installed.        | Loop back to step 1 and re-ask to install. |

JSON payload shape:

```json
{
  "path": "/abs/path/to/deploy",
  "framework": "terraform",
  "summary": { "passed": 120, "failed": 7, "skipped": 0, "parsing_errors": 0 },
  "failed_checks": [
    {
      "check_id": "CKV_AWS_21",
      "check_name": "Ensure S3 bucket has versioning enabled",
      "severity": "MEDIUM",
      "resource": "aws_s3_bucket.logs",
      "file_path": "/deploy/ecs-app/modules/logs/main.tf",
      "file_line_range": [12, 18],
      "guideline": "https://docs.bridgecrew.io/docs/..."
    }
  ],
  "parsing_errors": []
}
```

### 4. Render the report

Render **one** compact markdown report. Use a table for the violations.

#### 4a. Clean scan

```markdown
## Terraform validation — Checkov

**Path:** `<scan_path>`
**Framework:** terraform
**Result:** ✅ No violations

| Passed | Failed | Skipped | Parsing errors |
|-------:|-------:|--------:|---------------:|
| 120    | 0      | 0       | 0              |
```

Skip ahead to **step 7 (Commit & push)** — but only if the user also
asked for a commit/push. Otherwise just deliver the clean report.

#### 4b. Violations found

```markdown
## Terraform validation — Checkov

**Path:** `<scan_path>`
**Framework:** terraform
**Result:** ❌ 7 failed check(s)

| Passed | Failed | Skipped | Parsing errors |
|-------:|-------:|--------:|---------------:|
| 120    | 7      | 0       | 0              |

### Failed checks

| # | Check ID   | Severity | Resource                 | File:Line                                 | Description                          |
|--:|------------|----------|--------------------------|-------------------------------------------|--------------------------------------|
| 1 | CKV_AWS_21 | MEDIUM   | aws_s3_bucket.logs       | deploy/ecs-app/modules/logs/main.tf:12    | Ensure S3 bucket has versioning      |
| 2 | CKV_AWS_18 | LOW      | aws_s3_bucket.logs       | deploy/ecs-app/modules/logs/main.tf:12    | Ensure S3 access logging             |
| … | …          | …        | …                        | …                                         | …                                    |
```

Formatting rules for the violations table:

- **Paths** in the `File:Line` column must be **relative to the repo
  root** — strip the absolute prefix returned by Checkov.
- **Severity** values come straight from Checkov (`CRITICAL`, `HIGH`,
  `MEDIUM`, `LOW`, `INFO`, or `N/A`).
- **Description** = `check_name` from the JSON payload, truncated at
  ~60 chars with an ellipsis so rows stay on one line.
- If there are **parsing errors**, add a second section titled
  **"Parsing errors"** listing each file path verbatim, **before** the
  failed-checks table. Parsing errors block remediation for that file —
  surface them first and ask the user whether to fix the syntax before
  continuing with the findings loop.
- If `failed_checks` is longer than ~25 rows, show the first 25 sorted
  by severity (CRITICAL → INFO) then `check_id`, and add a footer line:
  *"… N more violations — the remediation loop will walk all N."*

### 5. Build the remediation todo list

**Only when `failed_checks` is non-empty.** Immediately after rendering
the report, announce the plan in one sentence:

> *"I found N failed check(s). I'll walk through them one at a time —
> for each I'll explain the root cause and propose a concrete fix you
> can accept (Y) or skip (N)."*

Then create a tracked todo list with **one todo per failed check**, in
the same order as the report table (CRITICAL → INFO, then `check_id`):

- Todo `id`: stable string like `CKV_AWS_21__aws_s3_bucket_logs__line12`
  (check id + sanitized resource + line) so repeated findings with the
  same ID remain distinct.
- Todo `content`: `"<#>. <CKV_ID> <severity>: <check_name> — <resource>
  (<file:line>)"`.
- Todo `status`: `pending` for all, except the first one which starts
  `in_progress`.

Use the agent's task-list mechanism to own the list. The list is the
single source of truth for progress — update it as each item moves
through `in_progress → completed` / `cancelled`.

### 6. Remediation loop (one Y/N per finding)

For **each** todo, strictly in order, repeat this micro-workflow. Do not
batch multiple findings into a single question, and do not edit files
without explicit user approval for the current finding.

#### 6.1 Announce the current item

Flip the todo to `in_progress` (if not already) and print a short header:

```markdown
---

### Finding 3 of 7 · CKV_AWS_21 · MEDIUM

- **Resource:** `aws_s3_bucket.logs`
- **File:** `deploy/ecs-app/modules/logs/main.tf:12`
- **Check:** Ensure S3 bucket has versioning enabled
- **Guideline:** <guideline URL from JSON, if present>
```

#### 6.2 Diagnose the root cause

Open the file around the reported line range with the Read tool and
explain, in **2-4 sentences**, *why* Checkov flagged it. A good diagnosis
names:

1. The Terraform construct that is missing / mis-set (e.g. *"no
   `versioning` block on `aws_s3_bucket.logs`"*).
2. The MIDAS context that matters (tie in `.cursor/rules/solution_const.mdc`
   when relevant — e.g. private-by-default, KMS CMK, tagging, least
   privilege).
3. The concrete risk the check is guarding against.

Do **not** paste the entire Checkov guideline; keep it operator-readable.

#### 6.3 Propose exactly one fix

State the fix in one or two lines and show the **minimal** Terraform
diff you would apply (repo-relative path, real line numbers). Example:

```hcl
# deploy/ecs-app/modules/logs/main.tf
resource "aws_s3_bucket" "logs" {
  bucket = var.bucket_name
+ # versioning required by CKV_AWS_21
}
+
+resource "aws_s3_bucket_versioning" "logs" {
+  bucket = aws_s3_bucket.logs.id
+  versioning_configuration { status = "Enabled" }
+}
```

When a finding has multiple reasonable fixes (e.g. *"enable encryption
with AWS-managed key OR with a project KMS CMK"*), list them as a tiny
bulleted list **and** pick one as the default recommendation that
matches MIDAS conventions (prefer project KMS CMK, private access, least
privilege — see `solution_const.mdc`).

#### 6.4 Ask Y/N to apply

Ask a single, unambiguous question:

> *"Apply the fix above to `deploy/ecs-app/modules/logs/main.tf`? (Y/n,
> or `skip` to leave as-is, `stop` to end the remediation loop)"*

Accepted answers and what to do:

| Answer | Action |
|--------|--------|
| `Y` / `yes` / empty   | Apply the proposed edit with StrReplace / targeted edits. Then continue to 6.5. |
| `N` / `no` / `skip`   | Mark the todo `cancelled` with a note *"user declined"*. Move to the next item. |
| `stop` / `quit`       | Mark remaining todos `cancelled` *"user stopped remediation"*. Jump to step 7. |
| any other text        | Treat as a clarifying question, answer it, then re-ask the Y/N. |

Do **not** assume yes. Do **not** apply multiple fixes in one turn.

#### 6.5 Verify the fix (per-item re-scan)

Immediately after an applied edit, re-run Checkov, narrowed to the same
file/module when possible to keep it fast:

```bash
python3 .cursor/scripts/tf_validate.py \
  --path <file_or_module_dir> --json
```

- If the specific `check_id` for this finding is no longer in
  `failed_checks`: mark the todo `completed` ✅.
- If it is still present: show the residual output, tell the user
  *"that fix didn't clear the check"*, offer a revised fix **or** the
  option to revert the edit (`git checkout -- <file>`) and skip. Never
  silently stack more edits on top.
- If the re-scan reveals **new** findings introduced by the edit, add
  them to the end of the todo list so they are handled in turn.

Then advance: flip the next todo to `in_progress` and repeat from 6.1
until all todos are terminal (`completed` / `cancelled`).

#### 6.6 Progress cadence

Between items, give a short one-liner so the user sees momentum, e.g.
*"3/7 done · 1 skipped · 3 remaining."* Do not re-render the full table
each round.

### 7. Post-remediation: final validation

After the loop ends — either all items handled or the user stopped —
run one **full** scan to confirm the final state:

```bash
python3 .cursor/scripts/tf_validate.py --path deploy --json
```

Render a short recap (not the full table again):

```markdown
**Remediation recap**

| Fixed | Skipped | Remaining | Newly introduced |
|------:|--------:|----------:|-----------------:|
| 5     | 1       | 1         | 0                |
```

- If `Remaining == 0`: announce *"✅ All Checkov findings cleared."* and
  continue to step 8.
- If `Remaining > 0`: list the still-failing check IDs and ask
  *"Proceed to commit and push the fixes we applied, or stop here?"*
  Only continue to step 8 on an explicit **yes**.

### 8. Commit & push — hand off to `git_pull_commit_push`

Once the user is ready to ship the remediation, delegate to the
sibling skill [`git_pull_commit_push`](../git_pull_commit_push/SKILL.md)
for the git flow. Do **not** reinvent its logic here.

1. Tell the user: *"Handing off to `kt_git_pull_commit_push` to pull,
   commit, and push the remediation."*
2. Read that skill's `SKILL.md` and follow it verbatim for:
   - pulling the latest,
   - summarizing the staged/working-tree diff,
   - proposing an imperative commit title,
   - waiting for explicit user approval (or an alternate message),
   - committing and pushing.
3. Propose a default commit title in the form:
   `tf_validate: remediate <N> Checkov finding(s) under deploy/`
   (e.g. `tf_validate: remediate 5 Checkov finding(s) under deploy/`).
   Append a body listing the applied `check_id`s and files touched, one
   bullet per finding. The user can accept or override it per that
   skill's contract.
4. On any git error or merge conflict reported by `git_pull_commit_push`,
   **stop**, report the root cause, and do not attempt an automated fix
   unless the user explicitly asks.

This skill ends at `git push`. Environment promotion to dev/uat/prod
still goes through the MIDAS Jenkins pipelines (see
[`jenkins_run`](../jenkins_run/SKILL.md) /
[`git_pull_commit_push_jenkins_start`](../git_pull_commit_push_jenkins_start/SKILL.md))
— do **not** auto-trigger Jenkins from here.

## Optional follow-ups (only if the user asks)

- Focus the scan: `python3 .cursor/scripts/tf_validate.py --path deploy/ecs-app --json`
- Suppress a specific check: append `--skip-check CKV_AWS_<N>` (repeatable).
- Human CLI preview without the skill-rendered table:
  `python3 .cursor/scripts/tf_validate.py --path deploy`

Never auto-suggest `--skip-check` to make a scan pass — only use it when
the user explicitly asks to ignore a finding.

## Guardrails

- **One finding at a time.** Every edit must be gated by a Y/N prompt
  for the current todo. Never batch fixes across multiple findings in a
  single question.
- **Ask before installing.** Never run `brew install` or `pip install`
  without explicit user approval in the current turn.
- **Minimal, targeted edits.** Change only what the current finding
  requires. Prefer adding a focused resource (e.g. a
  `aws_s3_bucket_versioning` companion) over rewriting a module.
- **Respect `solution_const.mdc`.** Fixes must stay inside the MIDAS
  Terraform conventions (region `us-east-1`, private networking, KMS,
  least-privilege IAM, tagging). If a Checkov fix would violate those
  rules, pause and ask the user instead of applying it.
- **Stop on operational error** (script exit `2`): show the `error` /
  `stderr_tail` from the JSON payload and ask the user how to proceed.
- **No pipeline substitutes.** Do not run `terraform plan`,
  `terraform apply`, `helm`, `kubectl`, or AWS CLI mutations anywhere
  in this flow. Promotion goes through Jenkins per
  `.cursor/rules/jenkins.mdc`.
- **Hand-off fidelity.** The commit/push step is delegated to
  `git_pull_commit_push` — follow that skill verbatim rather than
  inlining git commands.

## Related

- Script: [`.cursor/scripts/tf_validate.py`](../../scripts/tf_validate.py)
- Rules: [`.cursor/rules/solution_const.mdc`](../../rules/solution_const.mdc),
  [`.cursor/rules/jenkins.mdc`](../../rules/jenkins.mdc),
  [`.cursor/rules/architecture.mdc`](../../rules/architecture.mdc)
- Sibling skills:
  [`tf_add_resource`](../tf_add_resource/SKILL.md) ·
  [`git_pull_commit_push`](../git_pull_commit_push/SKILL.md) ·
  [`git_pull_commit_push_jenkins_start`](../git_pull_commit_push_jenkins_start/SKILL.md) ·
  [`jenkins_run`](../jenkins_run/SKILL.md)
