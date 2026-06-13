"""Create a parent Epic + child Bug tickets in Jira from a CSV file.

Reads jira_tickets_t0001.csv (or any compatible JIRA ticket CSV), creates a
single parent Epic titled "Fix All Code Security Scan Issues" in the target
project, then creates each row as a Bug linked to that Epic with structured
filterable labels.

Usage (from repo root):

    # Dry run — preview without creating anything
    uv run --project .cursor/tools/jira_tool python \\
        .cursor/tools/jira_tool/create_tickets_from_csv.py \\
        --csv remediation/security_remediation/extracted_files/jira_tickets_t0001.csv \\
        --project IEA \\
        --dry-run

    # Live run — creates Epic + all child Bugs
    uv run --project .cursor/tools/jira_tool python \\
        .cursor/tools/jira_tool/create_tickets_from_csv.py \\
        --csv remediation/security_remediation/extracted_files/jira_tickets_t0001.csv \\
        --project IEA

    # Re-run with an existing parent (skips Epic creation)
    uv run --project .cursor/tools/jira_tool python \\
        .cursor/tools/jira_tool/create_tickets_from_csv.py \\
        --csv remediation/security_remediation/extracted_files/jira_tickets_t0001.csv \\
        --project IEA \\
        --skip-parent IEA-101
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time
import warnings
from pathlib import Path
from typing import Optional

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

# Allow running from repo root without installing as package
sys.path.insert(0, str(Path(__file__).parent))
from jira_tool.client import JiraClient  # noqa: E402


# ── constants ────────────────────────────────────────────────────────────────

PARENT_TITLE = "Fix All Code Security Scan Issues"
STATIC_LABEL = "midas-security-remediation"
RATE_LIMIT_SLEEP = 0.5  # seconds between API calls
REPORT_PATH = Path("remediation/security_remediation/extracted_files/jira_tickets_created.md")


# ── label helpers ─────────────────────────────────────────────────────────────

def _normalise(value: str) -> str:
    """Lowercase and replace underscores/spaces with hyphens."""
    return value.strip().lower().replace("_", "-").replace(" ", "-")


def _build_labels(row: dict) -> list[str]:
    """Build the full set of filterable labels for a child ticket row."""
    labels = [STATIC_LABEL]

    priority = row.get("priority", "").strip()
    if priority:
        labels.append(f"priority-{_normalise(priority)}")

    owner = row.get("owner_team", "").strip()
    if owner:
        labels.append(f"owner-{_normalise(owner)}")

    effort = row.get("effort_estimate", "").strip()
    if effort:
        labels.append(f"effort-{_normalise(effort)}")

    complexity = row.get("complexity", "").strip()
    if complexity:
        labels.append(f"complexity-{_normalise(complexity)}")

    group = row.get("parent_group", "").strip()
    if group:
        labels.append(f"group-{_normalise(group)}")

    return labels


def _build_description(row: dict) -> str:
    """Compose the ticket description from CSV fields."""
    parts = []
    if row.get("description", "").strip():
        parts.append(row["description"].strip())
    if row.get("root_cause", "").strip():
        parts.append(f"Root cause:\n{row['root_cause'].strip()}")
    if row.get("files_to_change", "").strip():
        parts.append(f"Files to change:\n{row['files_to_change'].strip()}")
    if row.get("validation_steps", "").strip():
        parts.append(f"Validation:\n{row['validation_steps'].strip()}")
    return "\n\n".join(parts) if parts else ""


# ── table helpers ──────────────────────────────────────────────────────────────

def _truncate(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    return text[: width - 3] + "..."


def _format_table(rows: list[dict], truncate_title: int = 80) -> str:
    """Render a markdown table from a list of row dicts."""
    headers = ["Jira Key", "Parent Key", "Type", "Priority", "Group", "Owner", "Effort", "Title"]
    col_keys = ["jira_key", "parent_key", "type", "priority", "group", "owner", "effort", "title"]

    # Calculate column widths
    widths = [len(h) for h in headers]
    for r in rows:
        for i, k in enumerate(col_keys):
            val = r.get(k, "")
            if k == "title":
                val = _truncate(val, truncate_title)
            widths[i] = max(widths[i], len(val))

    def _row_str(values: list[str]) -> str:
        cells = []
        for i, (v, w) in enumerate(zip(values, widths)):
            if col_keys[i] == "title":
                v = _truncate(v, truncate_title)
            cells.append(v.ljust(w))
        return "| " + " | ".join(cells) + " |"

    sep = "| " + " | ".join("-" * w for w in widths) + " |"
    lines = [_row_str(headers), sep]
    for r in rows:
        lines.append(_row_str([r.get(k, "") for k in col_keys]))
    return "\n".join(lines)


# ── main logic ─────────────────────────────────────────────────────────────────

def run(
    csv_path: str,
    project: str,
    dry_run: bool,
    skip_parent: Optional[str],
    parent_title: str,
) -> None:
    # ── read CSV ──────────────────────────────────────────────────────────────
    csv_file = Path(csv_path)
    if not csv_file.is_file():
        print(f"[ERROR] CSV not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    with open(csv_file, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # Strip whitespace from all values
    rows = [{k: (v or "").strip() for k, v in row.items()} for row in rows]
    # Drop rows with no title (e.g. blank trailing rows)
    rows = [r for r in rows if r.get("title", "").strip()]

    print(f"[INFO] Loaded {len(rows)} ticket rows from {csv_path}")

    if dry_run:
        print("[DRY RUN] No tickets will be created.\n")
    else:
        # Build client from env vars
        for var in ("JIRA_URL", "JIRA_EMAIL", "JIRA_API_TOKEN"):
            if not os.environ.get(var):
                print(f"[ERROR] Missing env var: {var}", file=sys.stderr)
                sys.exit(1)
        client = JiraClient(
            url=os.environ["JIRA_URL"],
            email=os.environ["JIRA_EMAIL"],
            api_token=os.environ["JIRA_API_TOKEN"],
        )

    # ── create / resolve parent Epic ──────────────────────────────────────────
    table_rows: list[dict] = []
    parent_key: Optional[str] = None

    if skip_parent:
        parent_key = skip_parent
        print(f"[INFO] Using existing parent Epic: {parent_key}")
        table_rows.append({
            "jira_key": parent_key,
            "parent_key": "\u2014",
            "type": "Epic",
            "priority": "\u2014",
            "group": "\u2014",
            "owner": "\u2014",
            "effort": "\u2014",
            "title": parent_title,
        })
    else:
        if dry_run:
            parent_key = f"{project}-DRY"
            print(f"[DRY RUN] Would create Epic: '{parent_title}' in {project}")
            table_rows.append({
                "jira_key": parent_key,
                "parent_key": "\u2014",
                "type": "Epic",
                "priority": "\u2014",
                "group": "\u2014",
                "owner": "\u2014",
                "effort": "\u2014",
                "title": parent_title,
            })
        else:
            print(f"[INFO] Creating parent Epic: '{parent_title}' ...")
            epic = client.create_epic(
                project=project,
                summary=parent_title,
                description=(
                    "Parent Epic tracking all MIDAS code security scan remediation tickets. "
                    "Child tickets were generated from the ISG Fortify Developer Workbook and "
                    "supplementary ISG scan reports (container, IaC, OSS)."
                ),
                labels=[STATIC_LABEL],
            )
            parent_key = epic["key"]
            print(f"[OK] Epic created: {parent_key}")
            table_rows.append({
                "jira_key": parent_key,
                "parent_key": "\u2014",
                "type": "Epic",
                "priority": "\u2014",
                "group": "\u2014",
                "owner": "\u2014",
                "effort": "\u2014",
                "title": parent_title,
            })
            time.sleep(RATE_LIMIT_SLEEP)

    # ── create child tickets ───────────────────────────────────────────────────
    created = 0
    skipped = 0

    for i, row in enumerate(rows, start=1):
        title = row.get("title", "").strip()
        if not title:
            print(f"[SKIP] Row {i}: empty title — skipping")
            skipped += 1
            continue

        priority = row.get("priority", "").strip() or None
        issue_type = row.get("issue_type", "Bug").strip() or "Bug"
        labels = _build_labels(row)
        description = _build_description(row)

        group_label = _normalise(row.get("parent_group", "")) or "\u2014"
        owner_label = row.get("owner_team", "\u2014").strip() or "\u2014"
        effort_label = row.get("effort_estimate", "\u2014").strip() or "\u2014"

        if dry_run:
            print(f"[DRY RUN] {i:3d}/{len(rows)}  [{issue_type}] [{priority}] {title[:70]}")
            print(f"           labels: {', '.join(labels)}")
            table_rows.append({
                "jira_key": f"DRY-{i:03d}",
                "parent_key": parent_key or "\u2014",
                "type": issue_type,
                "priority": priority or "\u2014",
                "group": group_label,
                "owner": owner_label,
                "effort": effort_label,
                "title": title,
            })
            created += 1
            continue

        try:
            ticket = client.create_ticket(
                project=project,
                summary=title,
                description=description or None,
                issue_type=issue_type,
                priority=priority,
                labels=labels,
                parent_key=parent_key,
            )
            jira_key = ticket["key"]
            print(f"[OK] {i:3d}/{len(rows)}  {jira_key}  {title[:60]}")
            table_rows.append({
                "jira_key": jira_key,
                "parent_key": parent_key or "\u2014",
                "type": issue_type,
                "priority": priority or "\u2014",
                "group": group_label,
                "owner": owner_label,
                "effort": effort_label,
                "title": title,
            })
            created += 1
        except Exception as exc:  # noqa: BLE001
            print(f"[SKIP] {i:3d}/{len(rows)}  ERROR: {exc}")
            skipped += 1

        time.sleep(RATE_LIMIT_SLEEP)

    # ── output report ─────────────────────────────────────────────────────────
    print()
    mode_tag = "[DRY RUN] " if dry_run else ""
    print(f"{mode_tag}Created: 1 Epic + {created} Bugs ({skipped} skipped)")

    # Full table (no title truncation for saved file)
    full_table = _format_table(table_rows, truncate_title=200)
    terminal_table = _format_table(table_rows, truncate_title=80)

    print()
    print(terminal_table)

    if not dry_run:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            f.write(f"# Jira Tickets Created\n\n")
            f.write(f"Parent Epic: **{parent_key}** — {parent_title}\n\n")
            f.write(f"Created: 1 Epic + {created} Bugs ({skipped} skipped)\n\n")
            f.write(full_table)
            f.write("\n")
        print(f"\nReport saved → {REPORT_PATH}")
    else:
        print(f"\n[DRY RUN] Report would be saved to → {REPORT_PATH}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="create_tickets_from_csv",
        description="Create a parent Epic + child Bug tickets in Jira from a CSV.",
    )
    parser.add_argument(
        "--csv", required=True,
        help="Path to the jira tickets CSV (e.g. remediation/.../jira_tickets_t0001.csv).",
    )
    parser.add_argument(
        "--project", required=True,
        help="Jira project key (e.g. IEA).",
    )
    parser.add_argument(
        "--dry-run", action="store_true", dest="dry_run",
        help="Preview all tickets without creating anything in Jira.",
    )
    parser.add_argument(
        "--skip-parent", default=None, dest="skip_parent", metavar="EPIC_KEY",
        help="Re-use an existing Epic key instead of creating a new one (e.g. IEA-101).",
    )
    parser.add_argument(
        "--parent-title", default=PARENT_TITLE, dest="parent_title",
        help=f'Override the parent Epic title (default: "{PARENT_TITLE}").',
    )
    args = parser.parse_args()

    run(
        csv_path=args.csv,
        project=args.project,
        dry_run=args.dry_run,
        skip_parent=args.skip_parent,
        parent_title=args.parent_title,
    )


if __name__ == "__main__":
    main()
