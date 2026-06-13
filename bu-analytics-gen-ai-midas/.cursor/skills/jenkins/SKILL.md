---
name: jenkins
description: >-
  Natural-language interface to the MIDAS Jenkins pipeline. Translates plain
  English requests into the correct jenkins_tools.py command and
  parameters, executes it, formats the result, and reports errors clearly.
  Use when the user (or another skill/agent) wants to trigger a build, watch
  live progress, check status, approve a deployment, view logs, get failure
  details, list stages, abort a run, get detailed build info, or perform any
  other Jenkins pipeline operation using plain English.
  Trigger phrases: "start the pipeline", "deploy to dev", "watch the pipeline",
  "what is the build status", "show me the logs", "show me why it failed",
  "approve the deployment", "abort the build", "list the stages",
  "wait for the build to start", "detailed info on build 42",
  "show build history", "check the queue", "who am I in Jenkins",
  "set up Jenkins credentials", or any variation referencing Jenkins / pipeline.
---

# jenkins — Natural-language MIDAS Jenkins CLI

## When to apply

Invoke this skill whenever a user or agent uses **natural language** to interact
with the MIDAS Jenkins pipeline. You are responsible for:

1. Translating the intent to the correct `jenkins_tools.py` command
2. Resolving all required parameters from context or by asking one targeted question
3. Executing the command via the Shell tool
4. Formatting and presenting the output clearly
5. Detecting and explaining any errors

## Script location

```
.cursor/tools/jenkins_tools.py
```

Always invoke with:
```bash
source ~/.zshrc 2>/dev/null || true
python3 .cursor/tools/jenkins_tools.py <command> [flags]
```

The `source ~/.zshrc` ensures `JENKINS_USER` and `JENKINS_API_TOKEN` are loaded
in the current shell session. If credentials are missing after sourcing, direct
the user to run `setup` (see Credential setup below).

## Credential setup

If any command fails with a credential or 401 error:

1. Tell the user to run the interactive setup wizard:
   ```bash
   python3 .cursor/tools/jenkins_tools.py setup
   ```
2. This prompts for username + token, validates live, saves to `~/.zshrc`.
3. If the token has **expired**, the CLI will prompt for a new one on its own
   during `_connect` — no manual file editing needed.
4. Token creation URL:
   `https://ucjenkinsdev.exlservice.com/user/<username>/configure` → API Token → Add new Token

## Natural-language → command mapping

Use the table below to select the correct command. Choose the most specific
match. If genuinely ambiguous, ask **one** clarifying question.

| Natural-language trigger | Command | Key flags |
|--------------------------|---------|-----------|
| "start / trigger / kick off / run / deploy" | `trigger` | `--param ENVIRONMENT=<env>` + defaults below |
| "watch / monitor / follow progress / live status" | `watch` | `--interval N` (default 15s), `--build N` |
| "wait for it to start / let me know when it starts" | `wait-for-start` | `--timeout N`, `--queue-url URL` |
| "what is the status / is it running / how is the build" | `status` | `--build N` (optional) |
| "detailed info / full details / everything about build N" | `build-info` | `--build N` (optional) |
| "show / list the last N builds / build history" | `build-history` | `--count N` |
| "show / tail / get the logs" | `logs` | `--tail N`, `--follow`, `--failed-stage` |
| "why did it fail / show me the errors / failure logs" | `logs --failed-stage` | `--build N` (optional) |
| "what stages / show stages / pipeline progress" | `stages` | `--build N` (optional) |
| "approve / proceed / continue the deployment" | `approve` | `--build N` (optional) |
| "reject / abort the approval / deny" | `approve --abort-input` | |
| "abort / stop / cancel the build" | `abort` | `--build N` (optional) |
| "what's in the queue / pending builds" | `queue` | |
| "list parameters / what params does it take" | `parameters` | |
| "list jobs / what jobs exist" | `list-jobs` | `--path`, `--depth` |
| "show artifacts / download artifacts" | `artifacts` | `--download-dir DIR` |
| "who am I / Jenkins user" | `whoami` | |
| "server info / Jenkins version" | `server-info` | |
| "list nodes / agents" | `nodes` | |
| "list plugins / plugin updates" | `plugins` | `--updates-only` |
| "test results / tests" | `test-results` | `--build N` (optional) |
| "set up credentials / save token / first-time setup" | `setup` | `--shell-rc PATH` (optional) |
| "enable the job" | `enable` | |
| "disable the job" | `disable` | |

## MIDAS deploy pipeline — canonical parameters

When the user says "trigger" / "start" / "deploy", use these defaults unless
the user specifies otherwise:

| Jenkins Parameter | Default | Notes |
|-------------------|---------|-------|
| `GIT_BRANCH` | `deployment/dev-jenkins` | Override if user names a branch |
| `ENVIRONMENT` | `dev` | `dev` / `uat` / `prod` |
| `DEPLOY_ALB_NLB` | `true` | Always true unless user says otherwise |
| `ENABLE_HELM_DEPLOY` | `true` | Always true unless user says otherwise |
| `REQUIRE_MANUAL_APPROVAL` | `true` | Set `false` only if user explicitly says "no approval" |
| `ALB_NLB_HTTPS_CERT_ARN` | *(empty)* | Set only when user supplies a cert ARN |

Full trigger example:
```bash
python3 .cursor/tools/jenkins_tools.py trigger \
  --param GIT_BRANCH=deployment/dev-jenkins \
  --param ENVIRONMENT=dev \
  --param DEPLOY_ALB_NLB=true \
  --param ENABLE_HELM_DEPLOY=true \
  --param REQUIRE_MANUAL_APPROVAL=true \
  --param ALB_NLB_HTTPS_CERT_ARN=
```

## Workflow

### 1. Understand intent

Read the user's message and identify the target command from the mapping table.
Extract any parameters explicitly mentioned (build number, environment, branch,
log tail length, interval, etc.).

### 2. Resolve missing parameters

- `trigger`: if environment not mentioned, assume `dev`.
- `watch` / `status` / `logs` / `stages` / `build-info`: if no `--build`, omit
  the flag (CLI defaults to `lastBuild`).
- `logs`: default `--tail 100`; use `--failed-stage` when user asks "why did it
  fail" or "show errors".
- `watch`: default `--interval 15`.
- `wait-for-start`: default `--timeout 300`.
- `artifacts --download-dir`: ask for directory only when user wants to download.
- Do **not** ask about parameters that have clear defaults.

### 3. Execute

Run the command using the Shell tool. Always `source ~/.zshrc` first.

### 4. Format output

Present results clearly based on command:

- **trigger**: show the queue URL. Then immediately offer to run `wait-for-start`
  to block until the build begins, followed by `watch` for live progress.
- **watch**: narrate stage transitions as they stream in; when the build ends
  explain SUCCESS/FAILURE clearly. If failed, the CLI auto-prints failure logs —
  summarise the key error for the user.
- **wait-for-start**: show the build number and URL when it starts; offer to
  `watch` or `build-info`.
- **status**: render the enriched status block (build #, icon, stages table,
  triggered-by, parameters). The CLI now prints this in a formatted box.
- **build-info**: present the full structured output from the CLI. If the build
  failed, the CLI auto-appends failure logs — summarise the root cause.
- **build-history**: print the table as-is (the CLI renders it); add a one-line
  summary of the trend (e.g. "3 of last 5 succeeded").
- **logs**: print the header line + log lines. For `--failed-stage`, highlight
  the key error lines and explain what went wrong.
- **stages**: render as an indented tree with status icons
  (✅ SUCCESS, 🔄 IN_PROGRESS, ❌ FAILURE, ⏸ PAUSED, ⬜ NOT_EXECUTED).
- **approve**: confirm "Approved build #N — pipeline will continue."
- **abort**: confirm "Build #N aborted."
- **whoami**: show id and fullName.
- **queue**: list pending items or say "Queue is empty."
- **parameters**: render as a table (name | type | default | description).
- All other commands: present key/value pairs or tables as appropriate.

### 5. Recommended follow-up chain for a new deployment

After `trigger` — automatically offer this sequence:
1. `wait-for-start` to confirm the build started
2. `watch` to see live stage progress
3. If paused at approval gate: `approve`
4. If build fails: `build-info` or `logs --failed-stage` for root cause

### 6. Error handling

| Error type | What to tell the user |
|------------|----------------------|
| Missing credentials | "Run: `python3 .cursor/tools/jenkins_tools.py setup`" |
| 401 / Authentication failed | "Your Jenkins token has expired. Run `setup` again — the CLI will prompt for a new token." |
| Job not found | "Job path not found. Check: `https://ucjenkinsdev.exlservice.com/job/exlerate/job/exlerate-solutions/job/MIDAS/job/bu-analytics-gen-ai-midas-deploy-eks`" |
| Build not found | "Build #N not found. Use `build-history` to see available builds." |
| Trigger failed | Show exact CLI error. Suggest checking queue or whether the job is disabled (`status`). |
| No pending input | "Pipeline is not waiting for approval. Use `stages` to see current state." |
| Build not running (abort) | "Build #N is not running. Use `build-history` to find a running build." |
| Timeout (wait-for-start) | "Build never started within the timeout. Check the queue: `queue`" |
| Network / connection error | "Cannot reach Jenkins at `https://ucjenkinsdev.exlservice.com`. Check VPN / network." |
| Any other non-zero exit | Print stderr verbatim; suggest running the command manually for more detail. |

## Post-task report (when explicitly asked or after multi-step operations)

```
╔══════════════════════════════════════════════════════════════╗
║  JENKINS TASK REPORT                            [DATE/TIME]  ║
╚══════════════════════════════════════════════════════════════╝

▸ TASK
  One-line summary of the Jenkins operation performed.

▸ STATUS
  ✅ COMPLETE  |  ⚠️ PARTIAL  |  ❌ BLOCKED

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

▸ WHAT WAS DONE
  • [Action verb] - [what happened] - [build # / job / URL]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

▸ PIPELINE STATE
  Build   : #N
  Status  : BUILDING / SUCCESS / FAILURE / PAUSED
  URL     : https://...
  Stages  : [stage summary]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

▸ FAILURE ROOT CAUSE  (omit if build succeeded)
  Stage  : <failed stage name>
  Error  : <first error line from logs>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

▸ NEXT STEPS
  □ [Actionable item — e.g. Approve, fix error X, re-trigger]

══════════════════════════════════════════════════════════════
```

## Guardrails

- **Do not modify Jenkins pipeline code** (`deploy/Jenkinsfile`, `deploy/Jenkinsfile_*`, or equivalent job definitions) unless the user **explicitly** requests a pipeline change. This skill is for **running and inspecting** the pipeline via `jenkins_tools.py`, not for editing Groovy/pipeline files.
- **Never trigger a `prod` deployment** without explicitly confirming the
  environment with the user, even if they say "deploy everywhere".
- **Never disable the job** without asking "Are you sure you want to disable it?"
- **Never force-push or hard-reset** — this skill only controls Jenkins.
- **Never abort a build silently** — always confirm the action was successful
  and note that it may take a few seconds to take effect.
- If the user asks for something not supported by the CLI, say so clearly and
  provide the Jenkins UI URL:
  `https://ucjenkinsdev.exlservice.com/job/exlerate/job/exlerate-solutions/job/MIDAS/job/bu-analytics-gen-ai-midas-deploy-eks`
