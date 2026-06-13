"""List and summarise Fortify findings from the workbook CSV.

Prints a summary table and optional per-row detail. Supports filtering by
priority, owner (Software/DevOps), resolution_owner (AI_AGENT/H_REQ), and
issue_state. Read-only — does not modify the CSV.

Usage (from repo root):
    uv run --project .cursor/tools/isg_list_findings isg-list-findings
    uv run --project .cursor/tools/isg_list_findings isg-list-findings --priority Critical
    uv run --project .cursor/tools/isg_list_findings isg-list-findings --owner Software
    uv run --project .cursor/tools/isg_list_findings isg-list-findings --resolution-owner AI_AGENT
    uv run --project .cursor/tools/isg_list_findings isg-list-findings --state OPEN
    uv run --project .cursor/tools/isg_list_findings isg-list-findings --detail
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

PRIORITY_ORDER = ("Critical", "High", "Medium", "Low")


def _repo_root() -> Path:
    """Resolve MIDAS repo root (directory containing `.git`)."""
    here = Path(__file__).resolve()
    for anc in here.parents:
        if (anc / ".git").is_dir():
            return anc
    raise RuntimeError(f"Cannot resolve repo root from {here}")


def _summary_table(rows: list[dict[str, str]]) -> str:
    """Build a markdown priority-summary table from rows."""
    total = len(rows)
    analyzed = sum(1 for r in rows if (r.get("analysis_id") or "").strip())
    by_pri: Counter[str] = Counter()
    done_pri: Counter[str] = Counter()
    owner_pri: Counter[tuple[str, str]] = Counter()

    for r in rows:
        pr = (r.get("fortify_priority") or "Unknown").strip()
        by_pri[pr] += 1
        if (r.get("analysis_id") or "").strip():
            done_pri[pr] += 1
        ow = (r.get("owner") or "").strip()
        if ow:
            owner_pri[(pr, ow)] += 1

    lines = [
        "| Priority | Total | Analyzed | Remaining |",
        "|---|---|---|---|",
    ]
    for pr in PRIORITY_ORDER:
        if by_pri[pr]:
            rem = by_pri[pr] - done_pri[pr]
            lines.append(f"| {pr} | {by_pri[pr]} | {done_pri[pr]} | {rem} |")
    if by_pri["Unknown"]:
        lines.append(f"| Unknown | {by_pri['Unknown']} | {done_pri['Unknown']} | {by_pri['Unknown'] - done_pri['Unknown']} |")
    lines.append(f"| **TOTAL** | **{total}** | **{analyzed}** | **{total - analyzed}** |")
    return "\n".join(lines)


def _owner_table(rows: list[dict[str, str]]) -> str:
    """Build a markdown owner-breakdown table."""
    team_owner: Counter[str] = Counter((r.get("owner") or "").strip() for r in rows)
    res_owner: Counter[str] = Counter((r.get("resolution_owner") or "").strip() for r in rows)
    lines = [
        "\n**Team owner (Software vs DevOps):**",
        "| Owner | Count |",
        "|---|---|",
    ]
    for k, v in sorted(team_owner.items(), key=lambda x: -x[1]):
        lines.append(f"| {k or '(empty)'} | {v} |")
    lines += [
        "\n**Resolution owner (AI_AGENT vs H_REQ):**",
        "| resolution_owner | Count |",
        "|---|---|",
    ]
    for k, v in sorted(res_owner.items(), key=lambda x: -x[1]):
        lines.append(f"| {k or '(empty)'} | {v} |")
    return "\n".join(lines)


def main() -> None:
    """CLI entry point for isg-list-findings."""
    parser = argparse.ArgumentParser(
        description="List and summarise Fortify findings from the workbook CSV.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--csv",
        default=None,
        help="Path to workbook_issues.csv (default: .cursor/scratch/extracted_files/workbook_issues.csv)",
    )
    parser.add_argument(
        "--priority",
        choices=["Critical", "High", "Medium", "Low"],
        default=None,
        help="Filter to a single Fortify priority.",
    )
    parser.add_argument(
        "--owner",
        choices=["Software", "DevOps"],
        default=None,
        help="Filter by team owner field.",
    )
    parser.add_argument(
        "--resolution-owner",
        choices=["AI_AGENT", "H_REQ"],
        default=None,
        dest="resolution_owner",
        help="Filter by resolution_owner field.",
    )
    parser.add_argument(
        "--state",
        default=None,
        help="Filter by issue_state (e.g. OPEN, ANALYZED, RESOLVED).",
    )
    parser.add_argument(
        "--detail",
        action="store_true",
        help="Print per-row detail lines after the summary table.",
    )
    args = parser.parse_args()

    repo = _repo_root()
    csv_path = Path(args.csv).resolve() if args.csv else repo / ".cursor/scratch/extracted_files/workbook_issues.csv"

    if not csv_path.is_file():
        print(f"[ERROR] CSV not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        all_rows = list(csv.DictReader(f))

    # Apply filters
    filtered = all_rows
    if args.priority:
        filtered = [r for r in filtered if (r.get("fortify_priority") or "").strip() == args.priority]
    if args.owner:
        filtered = [r for r in filtered if (r.get("owner") or "").strip() == args.owner]
    if args.resolution_owner:
        filtered = [r for r in filtered if (r.get("resolution_owner") or "").strip() == args.resolution_owner]
    if args.state:
        filtered = [r for r in filtered if (r.get("issue_state") or "").strip().upper() == args.state.upper()]

    active_filters = [
        f for f in [
            f"priority={args.priority}" if args.priority else None,
            f"owner={args.owner}" if args.owner else None,
            f"resolution_owner={args.resolution_owner}" if args.resolution_owner else None,
            f"state={args.state}" if args.state else None,
        ] if f
    ]
    filter_str = "  filters: " + ", ".join(active_filters) if active_filters else "  no filters"
    print(f"csv: {csv_path}")
    print(f"total_rows={len(all_rows)}  matching={len(filtered)}{filter_str}\n")
    print(_summary_table(filtered))
    print(_owner_table(filtered))

    if args.detail:
        print("\n--- Detail ---")
        for r in filtered:
            print(
                f"{r.get('obv_id','?'):>9}  [{r.get('fortify_priority','?'):8}]"
                f"  owner={r.get('owner','?'):8}"
                f"  res={r.get('resolution_owner','?'):8}"
                f"  state={r.get('issue_state','?'):10}"
                f"  {(r.get('sink_file') or r.get('source_file') or 'n/a')[:80]}"
            )


if __name__ == "__main__":
    main()
