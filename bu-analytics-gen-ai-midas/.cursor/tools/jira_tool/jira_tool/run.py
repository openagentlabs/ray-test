"""CLI entry point for jira-tool.

A single CLI that exposes all Jira operations an AI agent may need.
Authentication is always via API token (email + token).

Credentials can be supplied as:
  1. Environment variables  JIRA_URL  JIRA_EMAIL  JIRA_API_TOKEN  (preferred)
  2. CLI flags              --url  --email  --token

All successful commands print a JSON object or array to stdout.
All errors print to stderr and exit with code 1.

Usage examples (from repo root):

  # --- auth / whoami ---
  uv run --project .cursor/tools/jira_tool jira-tool whoami

  # --- tickets ---
  uv run --project .cursor/tools/jira_tool jira-tool get-ticket --key PROJ-42
  uv run --project .cursor/tools/jira_tool jira-tool search --jql "project=PROJ AND status=Open"
  uv run --project .cursor/tools/jira_tool jira-tool tickets-by-user --user "john.doe@example.com"
  uv run --project .cursor/tools/jira_tool jira-tool tickets-by-board --board "MIDAS Sprint Board"
  uv run --project .cursor/tools/jira_tool jira-tool create-ticket --project PROJ --summary "Fix login bug" --type Bug --priority High
  uv run --project .cursor/tools/jira_tool jira-tool update-ticket --key PROJ-42 --priority Critical
  uv run --project .cursor/tools/jira_tool jira-tool transition --key PROJ-42 --transition "In Progress"
  uv run --project .cursor/tools/jira_tool jira-tool add-comment --key PROJ-42 --body "Root cause confirmed."
  uv run --project .cursor/tools/jira_tool jira-tool assign --key PROJ-42 --account-id 5b10a2844c20165700ede21g
  uv run --project .cursor/tools/jira_tool jira-tool link-tickets --from PROJ-42 --to PROJ-10 --link-type "blocks"
  uv run --project .cursor/tools/jira_tool jira-tool delete-ticket --key PROJ-99
  uv run --project .cursor/tools/jira_tool jira-tool add-labels --key PROJ-42 --labels security,high-priority
  uv run --project .cursor/tools/jira_tool jira-tool remove-labels --key PROJ-42 --labels stale
  uv run --project .cursor/tools/jira_tool jira-tool bulk-update --keys PROJ-1,PROJ-2,PROJ-3 --priority High

  # --- epics ---
  uv run --project .cursor/tools/jira_tool jira-tool create-epic --project PROJ --summary "Q3 Security Hardening"
  uv run --project .cursor/tools/jira_tool jira-tool list-epics --project PROJ
  uv run --project .cursor/tools/jira_tool jira-tool epic-tickets --epic-key PROJ-5

  # --- boards & sprints ---
  uv run --project .cursor/tools/jira_tool jira-tool list-boards
  uv run --project .cursor/tools/jira_tool jira-tool get-board --board "MIDAS Sprint Board"
  uv run --project .cursor/tools/jira_tool jira-tool list-sprints --board "MIDAS Sprint Board"
  uv run --project .cursor/tools/jira_tool jira-tool add-to-sprint --sprint-id 42 --keys PROJ-1,PROJ-2

  # --- subtasks ---
  uv run --project .cursor/tools/jira_tool jira-tool create-subtask --parent PROJ-42 --summary "Write unit tests"

  # --- users ---
  uv run --project .cursor/tools/jira_tool jira-tool find-users --query "alice"

  # --- projects ---
  uv run --project .cursor/tools/jira_tool jira-tool list-projects
  uv run --project .cursor/tools/jira_tool jira-tool get-project --project PROJ
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from typing import Optional

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

from jira_tool.client import JiraClient


# ── output helpers ─────────────────────────────────────────────────────────

def _ok(data: object) -> None:
    """Print data as pretty JSON and exit 0."""
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def _err(message: str) -> None:
    """Print an error message to stderr and exit 1."""
    print(f"[ERROR] {message}", file=sys.stderr)
    sys.exit(1)


# ── client factory ─────────────────────────────────────────────────────────

def _build_client(args: argparse.Namespace) -> JiraClient:
    """Build JiraClient from CLI flags or environment variables.

    Priority: explicit CLI flags > environment variables.

    Args:
        args: Parsed CLI namespace.

    Returns:
        Configured JiraClient.
    """
    url = getattr(args, "url", None) or os.environ.get("JIRA_URL", "")
    email = getattr(args, "email", None) or os.environ.get("JIRA_EMAIL", "")
    token = getattr(args, "token", None) or os.environ.get("JIRA_API_TOKEN", "")
    missing = [name for name, val in [("--url / JIRA_URL", url), ("--email / JIRA_EMAIL", email), ("--token / JIRA_API_TOKEN", token)] if not val]
    if missing:
        _err(
            f"Missing Jira credentials: {', '.join(missing)}\n"
            "  Set environment variables JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN\n"
            "  or pass --url, --email, --token flags."
        )
    return JiraClient(url=url, email=email, api_token=token)


# ── shared auth flags ──────────────────────────────────────────────────────

def _add_auth_args(parser: argparse.ArgumentParser) -> None:
    g = parser.add_argument_group("auth (overrides env vars)")
    g.add_argument("--url", metavar="URL", help="Jira base URL (overrides JIRA_URL)")
    g.add_argument("--email", metavar="EMAIL", help="Atlassian account email (overrides JIRA_EMAIL)")
    g.add_argument("--token", metavar="TOKEN", help="Jira API token (overrides JIRA_API_TOKEN)")


# ── subcommand handlers ─────────────────────────────────────────────────────

def _cmd_whoami(args: argparse.Namespace) -> None:
    _ok(_build_client(args).get_current_user())


def _cmd_get_ticket(args: argparse.Namespace) -> None:
    _ok(_build_client(args).get_ticket(args.key))


def _cmd_search(args: argparse.Namespace) -> None:
    _ok(_build_client(args).search_tickets(args.jql, max_results=args.max_results))


def _cmd_tickets_by_user(args: argparse.Namespace) -> None:
    _ok(_build_client(args).get_tickets_by_user(
        username=args.user,
        project=args.project,
        status=args.status,
        max_results=args.max_results,
    ))


def _cmd_tickets_by_board(args: argparse.Namespace) -> None:
    _ok(_build_client(args).find_tickets_by_board(
        board_id_or_name=args.board,
        sprint=args.sprint,
        status=args.status,
        max_results=args.max_results,
    ))


def _cmd_create_ticket(args: argparse.Namespace) -> None:
    labels = [l.strip() for l in args.labels.split(",")] if args.labels else None
    components = [c.strip() for c in args.components.split(",")] if args.components else None
    custom = json.loads(args.custom_fields) if args.custom_fields else None
    _ok(_build_client(args).create_ticket(
        project=args.project,
        summary=args.summary,
        description=args.description,
        issue_type=args.type,
        priority=args.priority,
        assignee=args.assignee,
        labels=labels,
        components=components,
        epic_key=args.epic_key,
        story_points=float(args.story_points) if args.story_points else None,
        sprint_id=int(args.sprint_id) if args.sprint_id else None,
        parent_key=args.parent,
        custom_fields=custom,
    ))


def _cmd_update_ticket(args: argparse.Namespace) -> None:
    labels = [l.strip() for l in args.labels.split(",")] if args.labels else None
    components = [c.strip() for c in args.components.split(",")] if args.components else None
    custom = json.loads(args.custom_fields) if args.custom_fields else None
    _ok(_build_client(args).update_ticket(
        key=args.key,
        summary=args.summary,
        description=args.description,
        priority=args.priority,
        assignee=args.assignee,
        labels=labels,
        components=components,
        story_points=float(args.story_points) if args.story_points else None,
        custom_fields=custom,
    ))


def _cmd_transition(args: argparse.Namespace) -> None:
    _ok(_build_client(args).transition_ticket(args.key, args.transition))


def _cmd_add_comment(args: argparse.Namespace) -> None:
    _ok(_build_client(args).add_comment(args.key, args.body))


def _cmd_assign(args: argparse.Namespace) -> None:
    _ok(_build_client(args).assign_ticket(args.key, args.account_id))


def _cmd_link_tickets(args: argparse.Namespace) -> None:
    _ok(_build_client(args).link_tickets(args.from_key, args.to_key, args.link_type))


def _cmd_delete_ticket(args: argparse.Namespace) -> None:
    _ok(_build_client(args).delete_ticket(args.key))


def _cmd_add_labels(args: argparse.Namespace) -> None:
    labels = [l.strip() for l in args.labels.split(",")]
    _ok(_build_client(args).add_labels(args.key, labels))


def _cmd_remove_labels(args: argparse.Namespace) -> None:
    labels = [l.strip() for l in args.labels.split(",")]
    _ok(_build_client(args).remove_labels(args.key, labels))


def _cmd_bulk_update(args: argparse.Namespace) -> None:
    keys = [k.strip() for k in args.keys.split(",")]
    labels = [l.strip() for l in args.labels.split(",")] if args.labels else None
    _ok(_build_client(args).bulk_update_tickets(
        keys=keys,
        priority=args.priority,
        assignee=args.assignee,
        labels=labels,
    ))


def _cmd_create_epic(args: argparse.Namespace) -> None:
    labels = [l.strip() for l in args.labels.split(",")] if args.labels else None
    custom = json.loads(args.custom_fields) if args.custom_fields else None
    _ok(_build_client(args).create_epic(
        project=args.project,
        summary=args.summary,
        description=args.description,
        assignee=args.assignee,
        labels=labels,
        custom_fields=custom,
    ))


def _cmd_list_epics(args: argparse.Namespace) -> None:
    _ok(_build_client(args).get_epics(args.project, max_results=args.max_results))


def _cmd_epic_tickets(args: argparse.Namespace) -> None:
    _ok(_build_client(args).get_epic_tickets(args.epic_key, max_results=args.max_results))


def _cmd_list_boards(args: argparse.Namespace) -> None:
    _ok(_build_client(args).list_boards(project=args.project, max_results=args.max_results))


def _cmd_get_board(args: argparse.Namespace) -> None:
    _ok(_build_client(args).get_board(args.board))


def _cmd_list_sprints(args: argparse.Namespace) -> None:
    _ok(_build_client(args).list_sprints(
        board_id_or_name=args.board,
        state=args.state,
        max_results=args.max_results,
    ))


def _cmd_add_to_sprint(args: argparse.Namespace) -> None:
    keys = [k.strip() for k in args.keys.split(",")]
    _ok(_build_client(args).add_to_sprint(sprint_id=int(args.sprint_id), issue_keys=keys))


def _cmd_create_subtask(args: argparse.Namespace) -> None:
    _ok(_build_client(args).create_subtask(
        parent_key=args.parent,
        summary=args.summary,
        description=args.description,
        assignee=args.assignee,
        priority=args.priority,
    ))


def _cmd_find_users(args: argparse.Namespace) -> None:
    _ok(_build_client(args).find_users(args.query, max_results=args.max_results))


def _cmd_list_projects(args: argparse.Namespace) -> None:
    _ok(_build_client(args).list_projects())


def _cmd_get_project(args: argparse.Namespace) -> None:
    _ok(_build_client(args).get_project(args.project))


# ── parser construction ────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jira-tool",
        description=(
            "AI-agent Jira CLI. Authenticate via JIRA_URL / JIRA_EMAIL / JIRA_API_TOKEN "
            "env vars or --url / --email / --token flags. All output is JSON."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    # ── whoami ──────────────────────────────────────────────────────────────
    p = sub.add_parser("whoami", help="Show the authenticated user.")
    _add_auth_args(p)
    p.set_defaults(func=_cmd_whoami)

    # ── get-ticket ──────────────────────────────────────────────────────────
    p = sub.add_parser("get-ticket", help="Get full details for a ticket by key.")
    _add_auth_args(p)
    p.add_argument("--key", required=True, help="Issue key (e.g. PROJ-42).")
    p.set_defaults(func=_cmd_get_ticket)

    # ── search ──────────────────────────────────────────────────────────────
    p = sub.add_parser("search", help="Run a JQL query and return matching tickets.")
    _add_auth_args(p)
    p.add_argument("--jql", required=True, help='JQL string e.g. "project=PROJ AND status=Open".')
    p.add_argument("--max-results", type=int, default=50, metavar="N", dest="max_results")
    p.set_defaults(func=_cmd_search)

    # ── tickets-by-user ─────────────────────────────────────────────────────
    p = sub.add_parser("tickets-by-user", help="List tickets assigned to a user.")
    _add_auth_args(p)
    p.add_argument("--user", required=True, help="Display name, email, or account ID.")
    p.add_argument("--project", default=None, help="Restrict to a project key.")
    p.add_argument("--status", default=None, help="Filter by status (e.g. 'In Progress').")
    p.add_argument("--max-results", type=int, default=50, dest="max_results")
    p.set_defaults(func=_cmd_tickets_by_user)

    # ── tickets-by-board ────────────────────────────────────────────────────
    p = sub.add_parser("tickets-by-board", help="List tickets for a board (active sprint by default).")
    _add_auth_args(p)
    p.add_argument("--board", required=True, help="Numeric board ID or name substring.")
    p.add_argument("--sprint", default=None, help="Sprint name substring, 'active', or 'latest'.")
    p.add_argument("--status", default=None, help="Filter by status.")
    p.add_argument("--max-results", type=int, default=50, dest="max_results")
    p.set_defaults(func=_cmd_tickets_by_board)

    # ── create-ticket ───────────────────────────────────────────────────────
    p = sub.add_parser("create-ticket", help="Create a new ticket.")
    _add_auth_args(p)
    p.add_argument("--project", required=True, help="Project key (e.g. PROJ).")
    p.add_argument("--summary", required=True, help="Ticket title.")
    p.add_argument("--description", default=None, help="Long description.")
    p.add_argument("--type", default="Bug", metavar="TYPE", help="Issue type (default: Bug).")
    p.add_argument("--priority", default=None, help="Priority name (e.g. High).")
    p.add_argument("--assignee", default=None, help="Assignee account ID or email.")
    p.add_argument("--labels", default=None, help="Comma-separated labels.")
    p.add_argument("--components", default=None, help="Comma-separated component names.")
    p.add_argument("--epic-key", default=None, dest="epic_key", help="Parent epic key.")
    p.add_argument("--story-points", default=None, dest="story_points", help="Story point estimate.")
    p.add_argument("--sprint-id", default=None, dest="sprint_id", help="Sprint ID to assign to.")
    p.add_argument("--parent", default=None, help="Parent issue key (for sub-tasks).")
    p.add_argument("--custom-fields", default=None, dest="custom_fields", metavar="JSON",
                   help='JSON dict of custom fields, e.g. \'{"customfield_10100":"value"}\'.')
    p.set_defaults(func=_cmd_create_ticket)

    # ── update-ticket ───────────────────────────────────────────────────────
    p = sub.add_parser("update-ticket", help="Update fields on an existing ticket.")
    _add_auth_args(p)
    p.add_argument("--key", required=True, help="Issue key.")
    p.add_argument("--summary", default=None)
    p.add_argument("--description", default=None)
    p.add_argument("--priority", default=None)
    p.add_argument("--assignee", default=None, help="Account ID, email, or empty string to unassign.")
    p.add_argument("--labels", default=None, help="Comma-separated full replacement label list.")
    p.add_argument("--components", default=None, help="Comma-separated full replacement component list.")
    p.add_argument("--story-points", default=None, dest="story_points")
    p.add_argument("--custom-fields", default=None, dest="custom_fields", metavar="JSON")
    p.set_defaults(func=_cmd_update_ticket)

    # ── transition ──────────────────────────────────────────────────────────
    p = sub.add_parser("transition", help="Move a ticket to a new status via a workflow transition.")
    _add_auth_args(p)
    p.add_argument("--key", required=True, help="Issue key.")
    p.add_argument("--transition", required=True, help="Transition name or ID (e.g. 'In Progress').")
    p.set_defaults(func=_cmd_transition)

    # ── add-comment ─────────────────────────────────────────────────────────
    p = sub.add_parser("add-comment", help="Add a comment to a ticket.")
    _add_auth_args(p)
    p.add_argument("--key", required=True, help="Issue key.")
    p.add_argument("--body", required=True, help="Comment text.")
    p.set_defaults(func=_cmd_add_comment)

    # ── assign ──────────────────────────────────────────────────────────────
    p = sub.add_parser("assign", help="Assign a ticket to a user.")
    _add_auth_args(p)
    p.add_argument("--key", required=True, help="Issue key.")
    p.add_argument("--account-id", required=True, dest="account_id",
                   help="Assignee account ID (empty string to unassign).")
    p.set_defaults(func=_cmd_assign)

    # ── link-tickets ────────────────────────────────────────────────────────
    p = sub.add_parser("link-tickets", help="Create an issue link between two tickets.")
    _add_auth_args(p)
    p.add_argument("--from", required=True, dest="from_key", help="Source issue key.")
    p.add_argument("--to", required=True, dest="to_key", help="Target issue key.")
    p.add_argument("--link-type", default="relates to", dest="link_type",
                   help="Link type (default: 'relates to').")
    p.set_defaults(func=_cmd_link_tickets)

    # ── delete-ticket ───────────────────────────────────────────────────────
    p = sub.add_parser("delete-ticket", help="Permanently delete a ticket.")
    _add_auth_args(p)
    p.add_argument("--key", required=True, help="Issue key.")
    p.set_defaults(func=_cmd_delete_ticket)

    # ── add-labels ──────────────────────────────────────────────────────────
    p = sub.add_parser("add-labels", help="Append labels to a ticket.")
    _add_auth_args(p)
    p.add_argument("--key", required=True)
    p.add_argument("--labels", required=True, help="Comma-separated labels to add.")
    p.set_defaults(func=_cmd_add_labels)

    # ── remove-labels ───────────────────────────────────────────────────────
    p = sub.add_parser("remove-labels", help="Remove specific labels from a ticket.")
    _add_auth_args(p)
    p.add_argument("--key", required=True)
    p.add_argument("--labels", required=True, help="Comma-separated labels to remove.")
    p.set_defaults(func=_cmd_remove_labels)

    # ── bulk-update ─────────────────────────────────────────────────────────
    p = sub.add_parser("bulk-update", help="Apply the same update to multiple tickets.")
    _add_auth_args(p)
    p.add_argument("--keys", required=True, help="Comma-separated issue keys.")
    p.add_argument("--priority", default=None)
    p.add_argument("--assignee", default=None)
    p.add_argument("--labels", default=None, help="Comma-separated full replacement labels.")
    p.set_defaults(func=_cmd_bulk_update)

    # ── create-epic ─────────────────────────────────────────────────────────
    p = sub.add_parser("create-epic", help="Create a new epic.")
    _add_auth_args(p)
    p.add_argument("--project", required=True, help="Project key.")
    p.add_argument("--summary", required=True, help="Epic title.")
    p.add_argument("--description", default=None)
    p.add_argument("--assignee", default=None)
    p.add_argument("--labels", default=None, help="Comma-separated labels.")
    p.add_argument("--custom-fields", default=None, dest="custom_fields", metavar="JSON")
    p.set_defaults(func=_cmd_create_epic)

    # ── list-epics ──────────────────────────────────────────────────────────
    p = sub.add_parser("list-epics", help="List all epics in a project.")
    _add_auth_args(p)
    p.add_argument("--project", required=True, help="Project key.")
    p.add_argument("--max-results", type=int, default=50, dest="max_results")
    p.set_defaults(func=_cmd_list_epics)

    # ── epic-tickets ────────────────────────────────────────────────────────
    p = sub.add_parser("epic-tickets", help="List all tickets under an epic.")
    _add_auth_args(p)
    p.add_argument("--epic-key", required=True, dest="epic_key", help="Epic issue key.")
    p.add_argument("--max-results", type=int, default=50, dest="max_results")
    p.set_defaults(func=_cmd_epic_tickets)

    # ── list-boards ─────────────────────────────────────────────────────────
    p = sub.add_parser("list-boards", help="List boards, optionally filtered by project.")
    _add_auth_args(p)
    p.add_argument("--project", default=None, help="Project key filter.")
    p.add_argument("--max-results", type=int, default=50, dest="max_results")
    p.set_defaults(func=_cmd_list_boards)

    # ── get-board ───────────────────────────────────────────────────────────
    p = sub.add_parser("get-board", help="Get details for a single board.")
    _add_auth_args(p)
    p.add_argument("--board", required=True, help="Numeric board ID or name substring.")
    p.set_defaults(func=_cmd_get_board)

    # ── list-sprints ────────────────────────────────────────────────────────
    p = sub.add_parser("list-sprints", help="List sprints for a board.")
    _add_auth_args(p)
    p.add_argument("--board", required=True, help="Numeric board ID or name substring.")
    p.add_argument("--state", default=None, choices=["active", "future", "closed"],
                   help="Filter by sprint state.")
    p.add_argument("--max-results", type=int, default=25, dest="max_results")
    p.set_defaults(func=_cmd_list_sprints)

    # ── add-to-sprint ───────────────────────────────────────────────────────
    p = sub.add_parser("add-to-sprint", help="Move tickets into a sprint.")
    _add_auth_args(p)
    p.add_argument("--sprint-id", required=True, dest="sprint_id", help="Numeric sprint ID.")
    p.add_argument("--keys", required=True, help="Comma-separated issue keys.")
    p.set_defaults(func=_cmd_add_to_sprint)

    # ── create-subtask ──────────────────────────────────────────────────────
    p = sub.add_parser("create-subtask", help="Create a sub-task under a parent ticket.")
    _add_auth_args(p)
    p.add_argument("--parent", required=True, help="Parent issue key.")
    p.add_argument("--summary", required=True, help="Sub-task title.")
    p.add_argument("--description", default=None)
    p.add_argument("--assignee", default=None)
    p.add_argument("--priority", default=None)
    p.set_defaults(func=_cmd_create_subtask)

    # ── find-users ──────────────────────────────────────────────────────────
    p = sub.add_parser("find-users", help="Search Jira users by name or email.")
    _add_auth_args(p)
    p.add_argument("--query", required=True, help="Search string.")
    p.add_argument("--max-results", type=int, default=20, dest="max_results")
    p.set_defaults(func=_cmd_find_users)

    # ── list-projects ───────────────────────────────────────────────────────
    p = sub.add_parser("list-projects", help="List all accessible Jira projects.")
    _add_auth_args(p)
    p.set_defaults(func=_cmd_list_projects)

    # ── get-project ─────────────────────────────────────────────────────────
    p = sub.add_parser("get-project", help="Get details for a single project.")
    _add_auth_args(p)
    p.add_argument("--project", required=True, help="Project key.")
    p.set_defaults(func=_cmd_get_project)

    return parser


# ── main ───────────────────────────────────────────────────────────────────

def main() -> None:
    """CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        _err(str(exc))


if __name__ == "__main__":
    main()
