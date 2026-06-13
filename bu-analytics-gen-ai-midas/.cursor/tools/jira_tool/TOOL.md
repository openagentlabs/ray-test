# jira-tool — Jira REST API CLI (`TOOL.md`)

> **uv project:** `.cursor/tools/jira_tool/`  
> **CLI entry point:** `jira-tool` (installed by `uv sync`)  
> **Library:** [`jira`](https://pypi.org/project/jira/) v3.10.5 (pycontribs/jira — production-stable, Jira-focused)  
> **Auth method:** API Token (email + token) — the only supported method  
> **Output format:** JSON to stdout for every successful command; `[ERROR] …` to stderr + exit code 1 on failure

---

## 1. Purpose and when to invoke

Use this tool when the AI agent needs to read from or write to Jira:

- Fetching a ticket, searching by JQL, or listing tickets for a user or board sprint
- Creating or editing tickets, epics, subtasks, or setting labels, components, story points
- Moving a ticket through a workflow transition (e.g. `Open → In Progress → Done`)
- Adding comments, assigning users, linking issues, or adding tickets to sprints
- Querying boards, sprints, users, and projects
- Bulk-updating multiple tickets at once

**Do NOT invoke** when the user only wants a static description of what Jira contains — read the output from a previous `search` or `get-ticket` call instead of re-fetching.

---

## 2. Prerequisites

### Install the tool (once per machine / venv)

```bash
uv sync --project .cursor/tools/jira_tool
```

### Set credentials (required before every run)

| Env var | Description |
|---|---|
| `JIRA_URL` | Jira base URL, e.g. `https://yourorg.atlassian.net` |
| `JIRA_EMAIL` | Atlassian account email (used as the HTTP Basic Auth username) |
| `JIRA_API_TOKEN` | API token from [id.atlassian.com](https://id.atlassian.com/manage-profile/security/api-tokens) |

Credentials can also be passed as `--url`, `--email`, `--token` flags on every command. Env vars are preferred.

**Never hard-code credentials in scripts or commit them to git.** Store them in the shell RC or AWS Secrets Manager.

---

## 3. Invocation examples

All commands run from the **repo root** using `uv run`:

```bash
# Verify auth
uv run --project .cursor/tools/jira_tool jira-tool whoami

# Fetch a ticket
uv run --project .cursor/tools/jira_tool jira-tool get-ticket --key PROJ-42

# JQL search
uv run --project .cursor/tools/jira_tool jira-tool search --jql "project=PROJ AND status='In Progress'"

# Tickets assigned to a user
uv run --project .cursor/tools/jira_tool jira-tool tickets-by-user --user "john.doe@example.com"

# Active sprint tickets on a board
uv run --project .cursor/tools/jira_tool jira-tool tickets-by-board --board "MIDAS Sprint Board"

# Create a Bug ticket
uv run --project .cursor/tools/jira_tool jira-tool create-ticket \
  --project PROJ --summary "Fix null pointer in auth service" \
  --type Bug --priority High --labels security,auth

# Update ticket priority and assignee
uv run --project .cursor/tools/jira_tool jira-tool update-ticket \
  --key PROJ-42 --priority Critical --assignee 5b10a2844c20165700ede21g

# Move ticket to In Progress
uv run --project .cursor/tools/jira_tool jira-tool transition \
  --key PROJ-42 --transition "In Progress"

# Add a comment
uv run --project .cursor/tools/jira_tool jira-tool add-comment \
  --key PROJ-42 --body "Root cause confirmed: missing null check at line 87."

# Link two tickets
uv run --project .cursor/tools/jira_tool jira-tool link-tickets \
  --from PROJ-42 --to PROJ-10 --link-type "blocks"

# Create an epic
uv run --project .cursor/tools/jira_tool jira-tool create-epic \
  --project PROJ --summary "Q3 Security Hardening Sprint"

# List epics
uv run --project .cursor/tools/jira_tool jira-tool list-epics --project PROJ

# List boards
uv run --project .cursor/tools/jira_tool jira-tool list-boards

# List active sprint
uv run --project .cursor/tools/jira_tool jira-tool list-sprints \
  --board "MIDAS Sprint Board" --state active

# Add ticket to sprint
uv run --project .cursor/tools/jira_tool jira-tool add-to-sprint \
  --sprint-id 42 --keys PROJ-1,PROJ-2

# Create a sub-task
uv run --project .cursor/tools/jira_tool jira-tool create-subtask \
  --parent PROJ-42 --summary "Write unit tests for auth fix"

# Find a user
uv run --project .cursor/tools/jira_tool jira-tool find-users --query "alice"

# Bulk-update multiple tickets
uv run --project .cursor/tools/jira_tool jira-tool bulk-update \
  --keys PROJ-1,PROJ-2,PROJ-3 --priority High
```

---

## 4. Flags / Inputs table

### Global auth flags (available on every subcommand)

| Flag | Env var fallback | Required | Description |
|---|---|---|---|
| `--url URL` | `JIRA_URL` | Yes | Jira base URL |
| `--email EMAIL` | `JIRA_EMAIL` | Yes | Atlassian account email |
| `--token TOKEN` | `JIRA_API_TOKEN` | Yes | API token |

### Subcommand flags

| Command | Required flags | Optional flags |
|---|---|---|
| `whoami` | — | auth |
| `get-ticket` | `--key` | auth |
| `search` | `--jql` | `--max-results N`, auth |
| `tickets-by-user` | `--user` | `--project`, `--status`, `--max-results`, auth |
| `tickets-by-board` | `--board` | `--sprint`, `--status`, `--max-results`, auth |
| `create-ticket` | `--project`, `--summary` | `--type`, `--priority`, `--assignee`, `--labels`, `--components`, `--epic-key`, `--story-points`, `--sprint-id`, `--parent`, `--custom-fields JSON`, auth |
| `update-ticket` | `--key` | `--summary`, `--description`, `--priority`, `--assignee`, `--labels`, `--components`, `--story-points`, `--custom-fields JSON`, auth |
| `transition` | `--key`, `--transition` | auth |
| `add-comment` | `--key`, `--body` | auth |
| `assign` | `--key`, `--account-id` | auth |
| `link-tickets` | `--from`, `--to` | `--link-type` (default: `relates to`), auth |
| `delete-ticket` | `--key` | auth |
| `add-labels` | `--key`, `--labels` | auth |
| `remove-labels` | `--key`, `--labels` | auth |
| `bulk-update` | `--keys` | `--priority`, `--assignee`, `--labels`, auth |
| `create-epic` | `--project`, `--summary` | `--description`, `--assignee`, `--labels`, `--custom-fields JSON`, auth |
| `list-epics` | `--project` | `--max-results`, auth |
| `epic-tickets` | `--epic-key` | `--max-results`, auth |
| `list-boards` | — | `--project`, `--max-results`, auth |
| `get-board` | `--board` | auth |
| `list-sprints` | `--board` | `--state (active\|future\|closed)`, `--max-results`, auth |
| `add-to-sprint` | `--sprint-id`, `--keys` | auth |
| `create-subtask` | `--parent`, `--summary` | `--description`, `--assignee`, `--priority`, auth |
| `find-users` | `--query` | `--max-results`, auth |
| `list-projects` | — | auth |
| `get-project` | `--project` | auth |

---

## 5. Internal functions table

| Module | Function | Description |
|---|---|---|
| `client.py` | `JiraClient.__init__` | Establishes `jira.JIRA` connection with email+token basic auth |
| `client.py` | `JiraClient.from_env()` | Factory that reads `JIRA_URL / JIRA_EMAIL / JIRA_API_TOKEN` |
| `client.py` | `JiraClient.get_ticket(key)` | Fetch full ticket + comments |
| `client.py` | `JiraClient.search_tickets(jql, …)` | JQL search returning list of ticket dicts |
| `client.py` | `JiraClient.get_tickets_by_user(username, …)` | Tickets assigned to a user |
| `client.py` | `JiraClient.find_tickets_by_board(board, …)` | Tickets on a board / sprint |
| `client.py` | `JiraClient.create_ticket(…)` | Create any issue type |
| `client.py` | `JiraClient.update_ticket(key, …)` | Partial update of ticket fields |
| `client.py` | `JiraClient.transition_ticket(key, transition)` | Move ticket through workflow |
| `client.py` | `JiraClient.add_comment(key, body)` | Post a comment |
| `client.py` | `JiraClient.assign_ticket(key, account_id)` | Assign / unassign a ticket |
| `client.py` | `JiraClient.link_tickets(from, to, link_type)` | Create issue link |
| `client.py` | `JiraClient.delete_ticket(key)` | Permanently delete issue |
| `client.py` | `JiraClient.add_labels(key, labels)` | Append labels without overwriting existing |
| `client.py` | `JiraClient.remove_labels(key, labels)` | Remove specific labels |
| `client.py` | `JiraClient.bulk_update_tickets(keys, …)` | Apply same update to multiple tickets |
| `client.py` | `JiraClient.create_epic(…)` | Create an Epic issue type |
| `client.py` | `JiraClient.get_epics(project)` | List all epics in a project |
| `client.py` | `JiraClient.get_epic_tickets(epic_key)` | List tickets under an epic |
| `client.py` | `JiraClient.list_boards(project)` | List boards |
| `client.py` | `JiraClient.get_board(board_id_or_name)` | Get a single board |
| `client.py` | `JiraClient.list_sprints(board, state)` | List sprints for a board |
| `client.py` | `JiraClient.add_to_sprint(sprint_id, keys)` | Move tickets into a sprint |
| `client.py` | `JiraClient.create_subtask(parent, summary, …)` | Create sub-task under parent |
| `client.py` | `JiraClient.find_users(query)` | Search users by name/email |
| `client.py` | `JiraClient.get_current_user()` | Whoami |
| `client.py` | `JiraClient.list_projects()` | All accessible projects |
| `client.py` | `JiraClient.get_project(key)` | Single project details |
| `client.py` | `_ticket_dict(issue, url)` | Convert `jira.Issue` → plain dict |
| `client.py` | `_adf_to_text(node)` | Recursively flatten ADF description to plain text |
| `client.py` | `_safe(obj, *attrs)` | Safe chained `getattr` returning `None` on miss |

---

## 6. Outputs (stdout, stderr, exit codes)

| Outcome | stdout | stderr | Exit code |
|---|---|---|---|
| Success | Pretty-printed JSON (object or array) | — | 0 |
| Missing credentials | — | `[ERROR] Missing Jira credentials: …` | 1 |
| API error (e.g. 404, 403) | — | `[ERROR] <JIRAError message>` | 1 |
| Invalid transition | — | `[ERROR] Transition 'X' not found … Available: […]` | 1 |
| Board not found | — | `[ERROR] Board 'X' not found. Run 'jira-tool list-boards'` | 1 |

**Successful ticket dict keys:** `key`, `summary`, `status`, `issue_type`, `priority`, `assignee`, `reporter`, `created`, `updated`, `labels`, `components`, `sprint`, `epic_key`, `epic_name`, `story_points`, `url`, `description`, `subtasks`, `linked_issues`, `comments`

---

## 7. Project-specific defaults reference

| Default | Value | Notes |
|---|---|---|
| `--max-results` | `50` | Hard ceiling of 100 |
| `--type` in `create-ticket` | `Bug` | Change to `Story`, `Task`, `Epic`, `Sub-task`, etc. |
| `--link-type` in `link-tickets` | `relates to` | Other common values: `blocks`, `is blocked by`, `clones`, `duplicates` |
| Sprint default in `tickets-by-board` | `active` | Fetches the active sprint |

---

## 8. Recommended agent workflow

### Read a ticket and draft a comment

```bash
# 1. Fetch the ticket
uv run --project .cursor/tools/jira_tool jira-tool get-ticket --key PROJ-42

# 2. Agent reads the JSON, drafts the comment text

# 3. Post the comment
uv run --project .cursor/tools/jira_tool jira-tool add-comment \
  --key PROJ-42 --body "Analysis complete. See remediation plan above."
```

### Create tickets from a CSV of findings

```bash
# For each finding row, call create-ticket
uv run --project .cursor/tools/jira_tool jira-tool create-ticket \
  --project SEC --summary "<finding_title>" \
  --type Bug --priority High --epic-key SEC-5 --labels security

# Then add to the active sprint
uv run --project .cursor/tools/jira_tool jira-tool add-to-sprint \
  --sprint-id <id> --keys SEC-100,SEC-101
```

### Diagnose and progress a ticket

```bash
# Check current status
uv run --project .cursor/tools/jira_tool jira-tool get-ticket --key PROJ-42

# Move to In Progress
uv run --project .cursor/tools/jira_tool jira-tool transition \
  --key PROJ-42 --transition "In Progress"

# Assign to the right engineer
uv run --project .cursor/tools/jira_tool jira-tool assign \
  --key PROJ-42 --account-id <account_id>
```

---

## 9. Related tools / next-step commands

| Tool / command | How it relates |
|---|---|
| `isg-jira-ticket-gen` (`.cursor/tools/isg_jira_ticket_gen/`) | Generates `jira_tickets.csv` — feed those rows into `jira-tool create-ticket` to push them live |
| `isg-list-findings` (`.cursor/tools/isg_list_findings/`) | Shows the Fortify CSV state before you create Jira tickets |
| `.cursor/tools/jenkins_tools.py` | Jenkins CI operations (separate system from Jira) |

---

## 10. Security notes

- **Never commit credentials** (`JIRA_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`) to git. Use shell RC exports or AWS Secrets Manager.
- API tokens are equivalent to passwords. Rotate them in [id.atlassian.com](https://id.atlassian.com) if compromised.
- `delete-ticket` is **irreversible** on most Jira instances. The agent must always confirm with the user before running it.
- `transition` to `Done` / `Closed` may trigger email notifications to watchers; confirm intent before calling.
- `bulk-update` applies the same change to all listed keys simultaneously — use with care in production projects.
- HTTPS is enforced (`verify=True` in the JIRA client). Never pass `--url http://…` for a non-TLS endpoint.
