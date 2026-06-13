"""Jira API client wrapping the `jira` library.

All public methods return plain Python dicts/lists so they can be serialised
to JSON by the CLI layer without extra processing.

Authentication: API-token (email + token) — the only method supported.
Set the following environment variables before running any command:

    JIRA_URL        https://yourorg.atlassian.net
    JIRA_EMAIL      you@example.com
    JIRA_API_TOKEN  <token from id.atlassian.com>

Or pass --url / --email / --token flags to the CLI.
"""
from __future__ import annotations

import os
import re
from typing import Any, Optional

from jira import JIRA, Issue
from jira.exceptions import JIRAError


# ── helpers ──────────────────────────────────────────────────────────────────

def _safe(value: Any, *attrs: str) -> Optional[str]:
    """Safely walk a chain of attribute accesses, returning None on any miss."""
    cur = value
    for attr in attrs:
        if cur is None:
            return None
        cur = getattr(cur, attr, None)
    return str(cur) if cur is not None else None


def _adf_to_text(node: Any) -> str:
    """Convert an Atlassian Document Format (ADF) node tree to plain text."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        node_type = node.get("type", "")
        content = node.get("content", [])
        text = node.get("text", "")
        if text:
            return text
        parts = [_adf_to_text(c) for c in content]
        sep = "\n" if node_type in ("doc", "paragraph", "bulletList", "orderedList", "listItem", "heading") else ""
        return sep.join(p for p in parts if p)
    return ""


def _description_text(issue: Issue) -> Optional[str]:
    """Extract description as plain text from either ADF or legacy string format."""
    raw = getattr(issue.fields, "description", None)
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw.strip() or None
    if isinstance(raw, dict):
        return _adf_to_text(raw).strip() or None
    return str(raw)


def _ticket_dict(issue: Issue, jira_url: str) -> dict:
    """Convert a JIRA Issue object to a serialisable dict."""
    fields = issue.fields
    labels = list(getattr(fields, "labels", []) or [])
    components = [c.name for c in (getattr(fields, "components", []) or [])]

    # Story points — field name varies per instance
    story_points: Optional[float] = None
    for sp_field in ("story_points", "customfield_10016", "customfield_10028"):
        val = getattr(fields, sp_field, None)
        if val is not None:
            try:
                story_points = float(val)
                break
            except (TypeError, ValueError):
                pass

    # Sprint
    sprint_name: Optional[str] = None
    for sprint_field in ("sprint", "customfield_10020"):
        raw_sprint = getattr(fields, sprint_field, None)
        if raw_sprint:
            if isinstance(raw_sprint, list) and raw_sprint:
                raw_sprint = raw_sprint[-1]
            sprint_name = _safe(raw_sprint, "name") or str(raw_sprint)
            break

    # Epic
    epic_key: Optional[str] = None
    epic_name: Optional[str] = None
    for epic_link_field in ("epic", "customfield_10014"):
        raw_epic = getattr(fields, epic_link_field, None)
        if raw_epic:
            if hasattr(raw_epic, "key"):
                epic_key = raw_epic.key
                epic_name = _safe(raw_epic.fields, "summary") if hasattr(raw_epic, "fields") else None
            elif isinstance(raw_epic, str):
                epic_key = raw_epic
            break

    subtasks = [st.key for st in (getattr(fields, "subtasks", []) or [])]
    linked = [
        f"{li.type.name}: {li.inwardIssue.key if hasattr(li, 'inwardIssue') else li.outwardIssue.key}"
        for li in (getattr(fields, "issuelinks", []) or [])
        if hasattr(li, "inwardIssue") or hasattr(li, "outwardIssue")
    ]

    return {
        "key": issue.key,
        "summary": _safe(fields, "summary") or "",
        "status": _safe(fields, "status", "name") or "",
        "issue_type": _safe(fields, "issuetype", "name") or "",
        "priority": _safe(fields, "priority", "name"),
        "assignee": _safe(fields, "assignee", "displayName"),
        "reporter": _safe(fields, "reporter", "displayName"),
        "created": _safe(fields, "created"),
        "updated": _safe(fields, "updated"),
        "labels": labels,
        "components": components,
        "sprint": sprint_name,
        "epic_key": epic_key,
        "epic_name": epic_name,
        "story_points": story_points,
        "url": f"{jira_url.rstrip('/')}/browse/{issue.key}",
        "description": _description_text(issue),
        "subtasks": subtasks,
        "linked_issues": linked,
        "comments": [],
    }


# ── JiraClient ────────────────────────────────────────────────────────────────

class JiraClient:
    """Thin wrapper around `jira.JIRA` exposing agent-friendly operations.

    Args:
        url: Jira base URL (e.g. https://yourorg.atlassian.net).
        email: Atlassian account email for basic-auth API-token login.
        api_token: API token from id.atlassian.com.
    """

    def __init__(self, url: str, email: str, api_token: str) -> None:
        self._url = url.rstrip("/")
        self._jira = JIRA(
            server=self._url,
            basic_auth=(email, api_token),
            options={"verify": False, "server": self._url},
            timeout=15,
            max_retries=0,
            get_server_info=False,
        )

    # ── Factory ──────────────────────────────────────────────────────────────

    @staticmethod
    def from_env() -> "JiraClient":
        """Build a JiraClient from JIRA_URL / JIRA_EMAIL / JIRA_API_TOKEN env vars.

        Raises:
            EnvironmentError: If any required env var is missing.
        """
        missing = [v for v in ("JIRA_URL", "JIRA_EMAIL", "JIRA_API_TOKEN") if not os.environ.get(v)]
        if missing:
            raise EnvironmentError(
                f"Missing required environment variables: {', '.join(missing)}\n"
                "Set JIRA_URL, JIRA_EMAIL, and JIRA_API_TOKEN before running."
            )
        return JiraClient(
            url=os.environ["JIRA_URL"],
            email=os.environ["JIRA_EMAIL"],
            api_token=os.environ["JIRA_API_TOKEN"],
        )

    # ── Ticket — read ─────────────────────────────────────────────────────────

    def get_ticket(self, key: str) -> dict:
        """Fetch full details for a single ticket by key.

        Args:
            key: Jira issue key, e.g. ``PROJ-42``.

        Returns:
            Dict with all ticket fields including description and comments.

        Raises:
            JIRAError: If the ticket does not exist or is not accessible.
        """
        issue = self._jira.issue(key)
        result = _ticket_dict(issue, self._url)
        comments = []
        for c in self._jira.comments(issue):
            body = c.body if isinstance(c.body, str) else _adf_to_text(c.body)
            comments.append({
                "id": c.id,
                "author": _safe(c, "author", "displayName") or "",
                "created": str(c.created),
                "body": body.strip(),
            })
        result["comments"] = comments
        return result

    def search_tickets(
        self,
        jql: str,
        max_results: int = 50,
        fields: Optional[list[str]] = None,
    ) -> list[dict]:
        """Run a JQL query and return matching tickets.

        Args:
            jql: Jira Query Language string, e.g. ``project=PROJ AND status=Open``.
            max_results: Maximum number of results (default 50, max 100).
            fields: Optional list of field names to include. Fetches all by default.

        Returns:
            List of ticket dicts.
        """
        max_results = min(max_results, 100)
        issues = self._jira.search_issues(
            jql,
            maxResults=max_results,
            fields=",".join(fields) if fields else None,
        )
        return [_ticket_dict(i, self._url) for i in issues]

    def get_tickets_by_user(
        self,
        username: str,
        project: Optional[str] = None,
        status: Optional[str] = None,
        max_results: int = 50,
    ) -> list[dict]:
        """List tickets assigned to a user, optionally filtered by project and status.

        Args:
            username: Jira display name, email, or account ID.
            project: Optional project key to restrict results.
            status: Optional status name filter (e.g. ``In Progress``).
            max_results: Maximum results to return (default 50).

        Returns:
            List of ticket dicts sorted by updated date descending.
        """
        clauses = [f'assignee = "{username}"']
        if project:
            clauses.append(f"project = {project}")
        if status:
            clauses.append(f'status = "{status}"')
        clauses.append("ORDER BY updated DESC")
        jql = " AND ".join(clauses[:-1]) + " " + clauses[-1]
        return self.search_tickets(jql, max_results=max_results)

    def find_tickets_by_board(
        self,
        board_id_or_name: str,
        sprint: Optional[str] = None,
        status: Optional[str] = None,
        max_results: int = 50,
    ) -> list[dict]:
        """Fetch tickets for a board, optionally scoped to a sprint.

        Args:
            board_id_or_name: Numeric board ID or a substring of the board name.
            sprint: Sprint name substring or ``active`` / ``latest``. Defaults to active sprint.
            status: Optional status filter (e.g. ``To Do``).
            max_results: Maximum results (default 50).

        Returns:
            List of ticket dicts.
        """
        board = self._resolve_board(board_id_or_name)
        sprint_obj = self._resolve_sprint(board["id"], sprint or "active")
        sprint_id = sprint_obj["id"] if sprint_obj else None

        if sprint_id:
            issues = self._jira.search_issues(
                f"sprint = {sprint_id}" + (f' AND status = "{status}"' if status else ""),
                maxResults=max_results,
            )
        else:
            issues = self._jira.search_issues(
                f"board = {board['id']}" + (f' AND status = "{status}"' if status else ""),
                maxResults=max_results,
            )
        return [_ticket_dict(i, self._url) for i in issues]

    # ── Ticket — write ────────────────────────────────────────────────────────

    def create_ticket(
        self,
        project: str,
        summary: str,
        description: Optional[str] = None,
        issue_type: str = "Bug",
        priority: Optional[str] = None,
        assignee: Optional[str] = None,
        labels: Optional[list[str]] = None,
        components: Optional[list[str]] = None,
        epic_key: Optional[str] = None,
        story_points: Optional[float] = None,
        sprint_id: Optional[int] = None,
        parent_key: Optional[str] = None,
        custom_fields: Optional[dict] = None,
    ) -> dict:
        """Create a new Jira ticket.

        Args:
            project: Project key (e.g. ``PROJ``).
            summary: One-line ticket title.
            description: Optional long-form description (plain text).
            issue_type: Issue type name (default ``Bug``).
            priority: Priority name (e.g. ``High``).
            assignee: Assignee account ID or email.
            labels: List of label strings.
            components: List of component name strings.
            epic_key: Key of parent epic (e.g. ``PROJ-10``).
            story_points: Numeric story point estimate.
            sprint_id: Numeric sprint ID to add the ticket to.
            parent_key: Parent issue key for sub-tasks.
            custom_fields: Dict of ``{customfield_XXXXX: value}`` overrides.

        Returns:
            Dict representation of the newly created ticket.

        Raises:
            JIRAError: On API error (e.g. invalid project, missing required field).
        """
        fields: dict[str, Any] = {
            "project": {"key": project},
            "summary": summary,
            "issuetype": {"name": issue_type},
        }
        if description:
            fields["description"] = description
        if priority:
            fields["priority"] = {"name": priority}
        if assignee:
            fields["assignee"] = {"accountId": assignee} if re.match(r"^[0-9a-f]{24,}$", assignee) else {"name": assignee}
        if labels:
            fields["labels"] = labels
        if components:
            fields["components"] = [{"name": c} for c in components]
        if parent_key:
            fields["parent"] = {"key": parent_key}

        # Epic link — try customfield_10014 first (classic), then parent (next-gen)
        if epic_key and not parent_key:
            fields["customfield_10014"] = epic_key

        # Story points
        if story_points is not None:
            for sp_field in ("customfield_10016", "customfield_10028", "story_points"):
                fields[sp_field] = story_points

        # Sprint
        if sprint_id is not None:
            fields["customfield_10020"] = {"id": sprint_id}

        if custom_fields:
            fields.update(custom_fields)

        issue = self._jira.create_issue(fields=fields)
        return _ticket_dict(issue, self._url)

    def update_ticket(
        self,
        key: str,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        priority: Optional[str] = None,
        assignee: Optional[str] = None,
        labels: Optional[list[str]] = None,
        components: Optional[list[str]] = None,
        story_points: Optional[float] = None,
        custom_fields: Optional[dict] = None,
    ) -> dict:
        """Update fields on an existing ticket.

        Only the provided (non-None) fields are updated. Omitted fields are left
        as-is.

        Args:
            key: Issue key to update (e.g. ``PROJ-42``).
            summary: New summary string.
            description: New description string (replaces existing).
            priority: New priority name (e.g. ``Critical``).
            assignee: New assignee account ID or email. Pass empty string to unassign.
            labels: Full replacement list of labels.
            components: Full replacement list of component names.
            story_points: New story point value.
            custom_fields: Dict of ``{customfield_XXXXX: value}`` overrides.

        Returns:
            Updated ticket dict.
        """
        issue = self._jira.issue(key)
        update: dict[str, Any] = {}
        if summary is not None:
            update["summary"] = summary
        if description is not None:
            update["description"] = description
        if priority is not None:
            update["priority"] = {"name": priority}
        if assignee is not None:
            if assignee == "":
                update["assignee"] = None
            elif re.match(r"^[0-9a-f]{24,}$", assignee):
                update["assignee"] = {"accountId": assignee}
            else:
                update["assignee"] = {"name": assignee}
        if labels is not None:
            update["labels"] = labels
        if components is not None:
            update["components"] = [{"name": c} for c in components]
        if story_points is not None:
            for sp_field in ("customfield_10016", "customfield_10028", "story_points"):
                update[sp_field] = story_points
        if custom_fields:
            update.update(custom_fields)

        issue.update(fields=update)
        return _ticket_dict(self._jira.issue(key), self._url)

    def transition_ticket(self, key: str, transition: str) -> dict:
        """Move a ticket to a new status via a workflow transition.

        Args:
            key: Issue key (e.g. ``PROJ-42``).
            transition: Transition name or ID (e.g. ``In Progress``, ``Done``).

        Returns:
            Updated ticket dict after the transition.

        Raises:
            ValueError: If the transition name is not found for the issue.
        """
        issue = self._jira.issue(key)
        transitions = self._jira.transitions(issue)
        matched = next(
            (t for t in transitions if t["name"].lower() == transition.lower() or t["id"] == transition),
            None,
        )
        if not matched:
            available = [t["name"] for t in transitions]
            raise ValueError(
                f"Transition '{transition}' not found for {key}. "
                f"Available: {available}"
            )
        self._jira.transition_issue(issue, matched["id"])
        return _ticket_dict(self._jira.issue(key), self._url)

    def add_comment(self, key: str, body: str) -> dict:
        """Add a comment to a ticket.

        Args:
            key: Issue key (e.g. ``PROJ-42``).
            body: Comment text.

        Returns:
            Dict with ``id``, ``author``, ``created``, ``body``.
        """
        comment = self._jira.add_comment(key, body)
        return {
            "id": comment.id,
            "author": _safe(comment, "author", "displayName") or "",
            "created": str(comment.created),
            "body": body,
        }

    def assign_ticket(self, key: str, account_id: str) -> dict:
        """Assign a ticket to a user.

        Args:
            key: Issue key.
            account_id: Assignee account ID (pass empty string to unassign).

        Returns:
            Updated ticket dict.
        """
        self._jira.assign_issue(key, account_id or None)
        return _ticket_dict(self._jira.issue(key), self._url)

    def link_tickets(self, from_key: str, to_key: str, link_type: str = "relates to") -> dict:
        """Create an issue link between two tickets.

        Args:
            from_key: Source issue key.
            to_key: Target issue key.
            link_type: Link type name (e.g. ``relates to``, ``blocks``, ``is blocked by``).

        Returns:
            Dict with ``from_key``, ``to_key``, ``link_type``.
        """
        self._jira.create_issue_link(link_type, from_key, to_key)
        return {"from_key": from_key, "to_key": to_key, "link_type": link_type}

    def delete_ticket(self, key: str) -> dict:
        """Delete a ticket permanently.

        Args:
            key: Issue key to delete.

        Returns:
            Dict with ``deleted: true`` and the ``key``.

        Raises:
            JIRAError: If the issue cannot be deleted (e.g. insufficient permission).
        """
        self._jira.issue(key).delete()
        return {"deleted": True, "key": key}

    # ── Epic ──────────────────────────────────────────────────────────────────

    def create_epic(
        self,
        project: str,
        summary: str,
        description: Optional[str] = None,
        assignee: Optional[str] = None,
        labels: Optional[list[str]] = None,
        custom_fields: Optional[dict] = None,
    ) -> dict:
        """Create a new epic.

        Args:
            project: Project key.
            summary: Epic title.
            description: Optional long description.
            assignee: Optional assignee account ID.
            labels: Optional list of labels.
            custom_fields: Optional additional custom fields.

        Returns:
            Dict representation of the new epic.
        """
        return self.create_ticket(
            project=project,
            summary=summary,
            description=description,
            issue_type="Epic",
            assignee=assignee,
            labels=labels,
            custom_fields=custom_fields,
        )

    def get_epics(self, project: str, max_results: int = 50) -> list[dict]:
        """List all epics in a project.

        Args:
            project: Project key.
            max_results: Maximum results (default 50).

        Returns:
            List of epic dicts.
        """
        return self.search_tickets(
            f"project = {project} AND issuetype = Epic ORDER BY created DESC",
            max_results=max_results,
        )

    def get_epic_tickets(self, epic_key: str, max_results: int = 50) -> list[dict]:
        """List all tickets belonging to a specific epic.

        Args:
            epic_key: Epic issue key (e.g. ``PROJ-10``).
            max_results: Maximum results (default 50).

        Returns:
            List of ticket dicts.
        """
        return self.search_tickets(
            f'"Epic Link" = {epic_key} OR parentEpic = {epic_key} ORDER BY created DESC',
            max_results=max_results,
        )

    # ── Board ─────────────────────────────────────────────────────────────────

    def list_boards(self, project: Optional[str] = None, max_results: int = 50) -> list[dict]:
        """List Jira boards, optionally filtered by project.

        Args:
            project: Optional project key to filter boards.
            max_results: Maximum boards to return (default 50).

        Returns:
            List of board dicts with ``id``, ``name``, ``type``, ``project_key``.
        """
        boards = self._jira.boards(projectKeyOrID=project, maxResults=max_results)
        return [
            {
                "id": b.id,
                "name": b.name,
                "type": getattr(b, "type", None),
                "project_key": _safe(b, "location", "projectKey"),
            }
            for b in boards
        ]

    def get_board(self, board_id_or_name: str) -> dict:
        """Get details for a single board.

        Args:
            board_id_or_name: Numeric board ID or board name substring.

        Returns:
            Board dict.
        """
        return self._resolve_board(board_id_or_name)

    # ── Sprint ────────────────────────────────────────────────────────────────

    def list_sprints(
        self,
        board_id_or_name: str,
        state: Optional[str] = None,
        max_results: int = 25,
    ) -> list[dict]:
        """List sprints for a board.

        Args:
            board_id_or_name: Numeric board ID or board name substring.
            state: Optional filter — ``active``, ``future``, or ``closed``.
            max_results: Maximum results (default 25).

        Returns:
            List of sprint dicts.
        """
        board = self._resolve_board(board_id_or_name)
        sprints = self._jira.sprints(board["id"], state=state, maxResults=max_results)
        return [
            {
                "id": s.id,
                "name": s.name,
                "state": s.state,
                "start_date": getattr(s, "startDate", None),
                "end_date": getattr(s, "endDate", None),
                "goal": getattr(s, "goal", None),
            }
            for s in sprints
        ]

    def add_to_sprint(self, sprint_id: int, issue_keys: list[str]) -> dict:
        """Move one or more tickets into a sprint.

        Args:
            sprint_id: Numeric sprint ID.
            issue_keys: List of issue keys to add (e.g. ``["PROJ-1", "PROJ-2"]``).

        Returns:
            Dict with ``sprint_id`` and ``added`` list.
        """
        self._jira.add_issues_to_sprint(sprint_id, issue_keys)
        return {"sprint_id": sprint_id, "added": issue_keys}

    # ── Users ─────────────────────────────────────────────────────────────────

    def find_users(self, query: str, max_results: int = 20) -> list[dict]:
        """Search for Jira users by name or email.

        Args:
            query: Search string matched against display name and email.
            max_results: Maximum results (default 20).

        Returns:
            List of user dicts with ``account_id``, ``display_name``, ``email``, ``active``.
        """
        users = self._jira.search_users(query, maxResults=max_results)
        return [
            {
                "account_id": u.accountId,
                "display_name": u.displayName,
                "email": getattr(u, "emailAddress", None),
                "active": getattr(u, "active", True),
            }
            for u in users
        ]

    def get_current_user(self) -> dict:
        """Return details for the authenticated user.

        Returns:
            User dict.
        """
        myself = self._jira.myself()
        return {
            "account_id": myself.get("accountId", ""),
            "display_name": myself.get("displayName", ""),
            "email": myself.get("emailAddress", ""),
            "active": myself.get("active", True),
        }

    # ── Projects ──────────────────────────────────────────────────────────────

    def list_projects(self) -> list[dict]:
        """List all Jira projects accessible to the authenticated user.

        Returns:
            List of project dicts with ``key``, ``name``, ``id``.
        """
        projects = self._jira.projects()
        return [
            {"key": p.key, "name": p.name, "id": p.id}
            for p in projects
        ]

    def get_project(self, key: str) -> dict:
        """Get details for a single project.

        Args:
            key: Project key (e.g. ``PROJ``).

        Returns:
            Project dict with key, name, id, lead, and description.
        """
        proj = self._jira.project(key)
        return {
            "key": proj.key,
            "name": proj.name,
            "id": proj.id,
            "lead": _safe(proj, "lead", "displayName"),
            "description": getattr(proj, "description", None),
            "project_type": getattr(proj, "projectTypeKey", None),
            "url": f"{self._url}/jira/software/projects/{proj.key}",
        }

    # ── Subtask ───────────────────────────────────────────────────────────────

    def create_subtask(
        self,
        parent_key: str,
        summary: str,
        description: Optional[str] = None,
        assignee: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> dict:
        """Create a sub-task under a parent ticket.

        Args:
            parent_key: Parent issue key.
            summary: Sub-task title.
            description: Optional description.
            assignee: Optional assignee account ID.
            priority: Optional priority name.

        Returns:
            Newly created sub-task dict.
        """
        issue = self._jira.issue(parent_key)
        project_key = issue.fields.project.key
        return self.create_ticket(
            project=project_key,
            summary=summary,
            description=description,
            issue_type="Sub-task",
            assignee=assignee,
            priority=priority,
            parent_key=parent_key,
        )

    # ── Label & component helpers ─────────────────────────────────────────────

    def add_labels(self, key: str, labels: list[str]) -> dict:
        """Append labels to a ticket without removing existing ones.

        Args:
            key: Issue key.
            labels: Labels to add.

        Returns:
            Updated ticket dict.
        """
        issue = self._jira.issue(key)
        existing = list(getattr(issue.fields, "labels", []) or [])
        merged = list(dict.fromkeys(existing + labels))
        return self.update_ticket(key, labels=merged)

    def remove_labels(self, key: str, labels: list[str]) -> dict:
        """Remove specific labels from a ticket.

        Args:
            key: Issue key.
            labels: Labels to remove.

        Returns:
            Updated ticket dict.
        """
        issue = self._jira.issue(key)
        existing = list(getattr(issue.fields, "labels", []) or [])
        remaining = [l for l in existing if l not in labels]
        return self.update_ticket(key, labels=remaining)

    # ── Bulk operations ───────────────────────────────────────────────────────

    def bulk_update_tickets(
        self,
        keys: list[str],
        priority: Optional[str] = None,
        assignee: Optional[str] = None,
        labels: Optional[list[str]] = None,
    ) -> list[dict]:
        """Apply the same field update to multiple tickets.

        Args:
            keys: List of issue keys to update.
            priority: New priority for all tickets.
            assignee: New assignee for all tickets.
            labels: Full label replacement for all tickets.

        Returns:
            List of updated ticket dicts.
        """
        results = []
        for key in keys:
            results.append(
                self.update_ticket(key, priority=priority, assignee=assignee, labels=labels)
            )
        return results

    # ── Private helpers ───────────────────────────────────────────────────────

    def _resolve_board(self, board_id_or_name: str) -> dict:
        """Resolve a board by numeric ID or name substring.

        Args:
            board_id_or_name: Numeric ID string or name substring.

        Returns:
            Board dict with ``id``, ``name``, ``type``, ``project_key``.

        Raises:
            ValueError: If no matching board is found.
        """
        if board_id_or_name.isdigit():
            b = self._jira.board(int(board_id_or_name))
            return {
                "id": b.id,
                "name": b.name,
                "type": getattr(b, "type", None),
                "project_key": _safe(b, "location", "projectKey"),
            }
        boards = self._jira.boards(maxResults=100)
        for b in boards:
            if board_id_or_name.lower() in b.name.lower():
                return {
                    "id": b.id,
                    "name": b.name,
                    "type": getattr(b, "type", None),
                    "project_key": _safe(b, "location", "projectKey"),
                }
        raise ValueError(
            f"Board '{board_id_or_name}' not found. "
            f"Run 'jira-tool list-boards' to see available boards."
        )

    def _resolve_sprint(self, board_id: int, sprint_name: str) -> Optional[dict]:
        """Find a sprint by name or state keyword (``active``, ``latest``).

        Args:
            board_id: Numeric board ID.
            sprint_name: Sprint name substring, ``active``, or ``latest``.

        Returns:
            Sprint dict or None if not found.
        """
        state = "active" if sprint_name in ("active", "latest") else None
        try:
            sprints = self._jira.sprints(board_id, state=state, maxResults=50)
        except JIRAError:
            return None
        if not sprints:
            return None
        if sprint_name in ("active", "latest"):
            return {
                "id": sprints[0].id,
                "name": sprints[0].name,
                "state": sprints[0].state,
            }
        for s in sprints:
            if sprint_name.lower() in s.name.lower():
                return {
                    "id": s.id,
                    "name": s.name,
                    "state": s.state,
                }
        return None
