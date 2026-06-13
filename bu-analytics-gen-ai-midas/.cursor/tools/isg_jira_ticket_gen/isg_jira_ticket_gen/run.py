"""CLI entry point for isg-jira-ticket-gen.

Consumes all four ISG scan sources and produces two output CSV files:

  all_findings_consolidated.csv  — one row per original finding (all sources),
                                    with a bug_id column back-filled after grouping.
  jira_tickets.csv               — one row per JIRA Bug ticket (grouped or residual),
                                    ready for import or manual creation in JIRA.

Usage (from repo root):
    uv run --project .cursor/tools/isg_jira_ticket_gen isg-jira-ticket-gen \\
      --fortify    .cursor/scratch/extracted_files/workbook_issues.csv \\
      --container  remediation/security_remediation/files_from_isg/20260506-061145_container_images.csv \\
      --iac        remediation/security_remediation/files_from_isg/20260506-061145_iac.csv \\
      --oss        remediation/security_remediation/files_from_isg/20260506-061145_oss_packages.csv \\
      --output-dir remediation/security_remediation/final_csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from isg_jira_ticket_gen.grouper import build_tickets
from isg_jira_ticket_gen.ticket_schema import ConsolidatedFinding, JiraTicket

# ---------------------------------------------------------------------------
# Column order for output CSVs
# ---------------------------------------------------------------------------

CONSOLIDATED_COLS = [
    "finding_id",
    "source",
    "severity",
    "category_or_policy",
    "file_or_resource",
    "vulnerability_or_policy_id",
    "description",
    "fix_version_or_recommendation",
    "bug_id",
]

TICKET_COLS = [
    "ticket_id",
    "parent_epic",
    "parent_group",
    "title",
    "issue_type",
    "priority",
    "owner_team",
    "effort_estimate",
    "complexity",
    "root_cause",
    "files_to_change",
    "findings_cleared_count",
    "findings_cleared_ids",
    "risk",
    "validation_steps",
    "is_grouped",
    "residual_file_line",
    "labels",
    "consolidated_finding_ids",
]


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _finding_to_dict(f: ConsolidatedFinding) -> dict:
    return {
        "finding_id": f.finding_id,
        "source": f.source,
        "severity": f.severity,
        "category_or_policy": f.category_or_policy,
        "file_or_resource": f.file_or_resource,
        "vulnerability_or_policy_id": f.vulnerability_or_policy_id,
        "description": f.description,
        "fix_version_or_recommendation": f.fix_version_or_recommendation,
        "bug_id": f.bug_id,
    }


def _ticket_to_dict(t: JiraTicket) -> dict:
    return {
        "ticket_id": t.ticket_id,
        "parent_epic": t.parent_epic,
        "parent_group": t.parent_group,
        "title": t.title,
        "issue_type": t.issue_type,
        "priority": t.priority,
        "owner_team": t.owner_team,
        "effort_estimate": t.effort_estimate,
        "complexity": t.complexity,
        "root_cause": t.root_cause,
        "files_to_change": t.files_to_change,
        "findings_cleared_count": t.findings_cleared_count,
        "findings_cleared_ids": t.findings_cleared_ids,
        "risk": t.risk,
        "validation_steps": t.validation_steps,
        "is_grouped": str(t.is_grouped).lower(),
        "residual_file_line": t.residual_file_line,
        "labels": t.labels,
        "consolidated_finding_ids": t.consolidated_finding_ids,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="isg-jira-ticket-gen",
        description=(
            "Generate a consolidated findings CSV and a JIRA-aligned Bug ticket CSV "
            "from all four ISG scan sources (Fortify workbook + container/IaC/OSS scans)."
        ),
    )
    parser.add_argument(
        "--fortify",
        required=True,
        metavar="PATH",
        help="Path to the analyzed Fortify workbook CSV (workbook_issues.csv).",
    )
    parser.add_argument(
        "--container",
        metavar="PATH",
        help="Path to the container_images CSV from ISG.",
    )
    parser.add_argument(
        "--iac",
        metavar="PATH",
        help="Path to the iac CSV from ISG.",
    )
    parser.add_argument(
        "--oss",
        metavar="PATH",
        help="Path to the oss_packages CSV from ISG.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        metavar="DIR",
        help="Output directory for all_findings_consolidated.csv and jira_tickets.csv.",
    )
    args = parser.parse_args()

    fortify_path = Path(args.fortify).expanduser().resolve()
    if not fortify_path.is_file():
        print(f"[ERROR] Fortify CSV not found: {fortify_path}", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output_dir).expanduser()

    try:
        all_findings, all_tickets, _ = build_tickets(
            fortify_csv=str(fortify_path),
            container_csv=args.container,
            iac_csv=args.iac,
            oss_csv=args.oss,
        )
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)

    consolidated_path = output_dir / "all_findings_consolidated.csv"
    tickets_path = output_dir / "jira_tickets.csv"

    _write_csv(
        consolidated_path,
        CONSOLIDATED_COLS,
        [_finding_to_dict(f) for f in all_findings],
    )
    _write_csv(
        tickets_path,
        TICKET_COLS,
        [_ticket_to_dict(t) for t in all_tickets],
    )

    grouped = sum(1 for t in all_tickets if t.is_grouped)
    residual = sum(1 for t in all_tickets if not t.is_grouped)

    print(f"[OK] Consolidated findings → {consolidated_path} ({len(all_findings)} rows)")
    print(
        f"[OK] JIRA tickets          → {tickets_path} "
        f"({len(all_tickets)} tickets: {grouped} grouped, {residual} residual)"
    )
    print(f"\nAll outputs in: {output_dir}")


if __name__ == "__main__":
    main()
