"""CLI coordinator for Phase-2A deep analysis.

Usage (from repo root):
    uv run --project .cursor/tools/isg_deep_analyzer isg-deep-analyzer \\
      --csv .cursor/scratch/extracted_files/workbook_issues.csv \\
      --repo . [--batch-size 20] [--priority Critical] [--force] [--log-dir PATH]

The tool processes each Fortify CSV row by:
  1. Splitting unanalyzed rows into batches.
  2. Running analyze_batch() directly (Python, in-process) for each batch.
     Each row resolver reads the actual sink/source file from the repo.
  3. Atomically rewriting the CSV with updated rows.
  4. Writing per-row analysis_log/<uuid>.md files.

All analysis reasoning is done in row_analyzer.py using the actual file content
read from disk — no LLM API calls required.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def _add_parent_to_path() -> None:
    """Ensure the package directory is importable when run via `python run_analysis.py`."""
    here = Path(__file__).resolve().parent.parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))


_add_parent_to_path()

from isg_deep_analyzer.csv_io import (  # noqa: E402
    count_empty_analysis_ids,
    merge_updated_rows,
    read_csv,
    results_from_json_file,
    results_to_json_file,
    rows_to_json_file,
    summary_table,
    write_csv,
)
from isg_deep_analyzer.row_analyzer import analyze_batch  # noqa: E402


PRIORITY_ORDER = ("Critical", "High", "Medium", "Low")


def _repo_root_from_arg(repo_arg: str) -> Path:
    p = Path(repo_arg).resolve()
    if not (p / ".git").is_dir():
        # Walk up looking for .git
        for anc in p.parents:
            if (anc / ".git").is_dir():
                return anc
    return p


def _chunk(lst: list, size: int) -> list[list]:
    return [lst[i: i + size] for i in range(0, len(lst), size)]


def _filter_rows(
    rows: list[dict],
    priority: str | None,
    force: bool,
) -> tuple[list[dict], list[dict]]:
    """Return (to_process, to_keep_unchanged)."""
    to_process: list[dict] = []
    to_keep: list[dict] = []
    for r in rows:
        pr = (r.get("fortify_priority") or "").strip()
        has_id = bool((r.get("analysis_id") or "").strip())
        if priority and pr != priority:
            to_keep.append(r)
            continue
        if has_id and not force:
            to_keep.append(r)
            continue
        to_process.append(r)
    return to_process, to_keep


def main() -> None:  # noqa: C901
    parser = argparse.ArgumentParser(
        description="ISG Deep Analyzer — Phase 2A code-grounded batch analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--csv", required=True, help="Path to workbook_issues.csv")
    parser.add_argument("--repo", default=".", help="Repo root (default: current dir)")
    parser.add_argument("--batch-size", type=int, default=20, help="Rows per batch (default 20)")
    parser.add_argument(
        "--priority",
        choices=list(PRIORITY_ORDER),
        default=None,
        help="Process only this priority level",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-analyze rows that already have analysis_id",
    )
    parser.add_argument(
        "--log-dir",
        default=None,
        help="Directory for analysis_log/*.md files (default: <repo>/.cursor/scratch/analysis_log)",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv).resolve()
    repo_root = _repo_root_from_arg(args.repo)
    log_dir = Path(args.log_dir).resolve() if args.log_dir else (
        repo_root / ".cursor/scratch/analysis_log"
    )
    run_log_path = csv_path.parent / "_deep_analysis_run.log"

    print(f"[isg-deep-analyzer] repo={repo_root}")
    print(f"[isg-deep-analyzer] csv={csv_path}")
    print(f"[isg-deep-analyzer] log_dir={log_dir}")

    if not csv_path.is_file():
        print(f"[ERROR] CSV not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    fieldnames, all_rows = read_csv(csv_path)
    print(f"[isg-deep-analyzer] loaded {len(all_rows)} rows from CSV")

    to_process, _kept = _filter_rows(all_rows, args.priority, args.force)

    if not to_process:
        print("[isg-deep-analyzer] Nothing to process (all rows already analyzed; use --force to re-run).")
        print(summary_table(all_rows))
        sys.exit(0)

    print(
        f"[isg-deep-analyzer] rows to analyze={len(to_process)} "
        f"(skipped already-done={len(all_rows) - len(to_process)})"
    )

    # Sort by priority order for deterministic processing
    priority_rank = {p: i for i, p in enumerate(PRIORITY_ORDER)}
    to_process.sort(key=lambda r: priority_rank.get((r.get("fortify_priority") or "").strip(), 99))

    batches = _chunk(to_process, args.batch_size)
    print(f"[isg-deep-analyzer] batches={len(batches)} batch_size={args.batch_size}")

    all_updated: list[dict] = []
    t0 = time.monotonic()

    for batch_idx, batch in enumerate(batches, start=1):
        batch_ids = [r.get("obv_id", "?") for r in batch]
        print(
            f"[isg-deep-analyzer] batch {batch_idx}/{len(batches)} "
            f"rows={len(batch)} ({batch_ids[0]}..{batch_ids[-1]})",
            flush=True,
        )
        updated = analyze_batch(batch, repo_root, log_dir)
        all_updated.extend(updated)

        # Incremental CSV write after each batch so progress is never lost
        merged = merge_updated_rows(all_rows, all_updated)
        write_csv(csv_path, fieldnames, merged)
        done_so_far = sum(1 for r in merged if (r.get("analysis_id") or "").strip())
        print(
            f"[isg-deep-analyzer] progress: {done_so_far}/{len(all_rows)} rows analyzed",
            flush=True,
        )

    elapsed = time.monotonic() - t0
    final_rows = merge_updated_rows(all_rows, all_updated)
    write_csv(csv_path, fieldnames, final_rows)

    remaining = count_empty_analysis_ids(final_rows)
    logs_present = sum(1 for r in final_rows if (r.get("analysis_id") or "").strip() and
                       (log_dir / f"{r['analysis_id']}.md").is_file())

    summary = summary_table(final_rows)
    print("\n[isg-deep-analyzer] COMPLETE")
    print(summary)
    print(
        f"\nrows_updated={len(all_updated)}"
        f"  rows_remaining={remaining}"
        f"  logs_present={logs_present}"
        f"  elapsed={elapsed:.1f}s"
    )

    run_log = (
        f"repo={repo_root}\n"
        f"csv={csv_path}\n"
        f"rows_total={len(final_rows)}\n"
        f"rows_updated={len(all_updated)}\n"
        f"rows_remaining={remaining}\n"
        f"logs_present={logs_present}\n"
        f"elapsed_s={elapsed:.1f}\n"
        f"log_dir={log_dir}\n"
        f"priority_filter={args.priority or 'all'}\n"
        f"force={args.force}\n"
    )
    run_log_path.write_text(run_log, encoding="utf-8")

    if remaining > 0:
        print(f"[WARNING] {remaining} rows still have no analysis_id — re-run to retry.", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
