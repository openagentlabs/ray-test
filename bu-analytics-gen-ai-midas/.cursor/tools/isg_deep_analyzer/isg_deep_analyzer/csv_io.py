"""CSV read / atomic-write helpers for the deep analyzer."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


Row = dict[str, str]


def read_csv(path: Path) -> tuple[list[str], list[Row]]:
    """Read CSV with BOM-safe utf-8-sig encoding.

    Returns (fieldnames, rows).
    """
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        if not fieldnames:
            raise ValueError(f"CSV has no header: {path}")
        rows = [dict(r) for r in reader]
    return fieldnames, rows


def _ensure_owner_field(fieldnames: list[str]) -> list[str]:
    """Ensure 'owner' column is present after 'acceptance_criteria'; idempotent."""
    if "owner" in fieldnames:
        return fieldnames
    out = list(fieldnames)
    try:
        idx = out.index("acceptance_criteria")
        out.insert(idx + 1, "owner")
    except ValueError:
        out.append("owner")
    return out


def write_csv(path: Path, fieldnames: list[str], rows: list[Row]) -> None:
    """Atomically write CSV (utf-8, no BOM) via tmp-rename.

    Automatically adds 'owner' column after 'acceptance_criteria' if missing.
    """
    fieldnames = _ensure_owner_field(fieldnames)
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL, extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def merge_updated_rows(original_rows: list[Row], updates: list[Row]) -> list[Row]:
    """Merge a list of updated rows back into the original list by obv_id.

    Rows in *updates* replace the corresponding row in *original_rows*.
    Rows not in *updates* are kept unchanged.
    """
    index: dict[str, Row] = {r["obv_id"]: r for r in updates}
    return [index.get(r["obv_id"], r) for r in original_rows]


def rows_to_json_file(rows: list[Row], path: Path) -> None:
    """Serialise rows to a JSON file (for passing batches to subagents)."""
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def rows_from_json_file(path: Path) -> list[Row]:
    """Deserialise rows written by *rows_to_json_file*."""
    return json.loads(path.read_text(encoding="utf-8"))


def results_to_json_file(results: list[Row], path: Path) -> None:
    """Subagent writes its results here; coordinator reads them back."""
    path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


def results_from_json_file(path: Path) -> list[Row]:
    return json.loads(path.read_text(encoding="utf-8"))


def count_empty_analysis_ids(rows: list[Row]) -> int:
    return sum(1 for r in rows if not (r.get("analysis_id") or "").strip())


def summary_table(rows: list[Row]) -> str:
    """Return a text summary table of analysis state by priority."""
    from collections import Counter
    total = len(rows)
    done = sum(1 for r in rows if (r.get("analysis_id") or "").strip())
    by_pri: Counter[str] = Counter()
    done_pri: Counter[str] = Counter()
    for r in rows:
        pr = (r.get("fortify_priority") or "Unknown").strip()
        by_pri[pr] += 1
        if (r.get("analysis_id") or "").strip():
            done_pri[pr] += 1
    lines = [
        "| Priority | Total | Analyzed | Remaining |",
        "|----------|-------|----------|-----------|",
    ]
    for pr in ("Critical", "High", "Medium", "Low", "Unknown"):
        if by_pri[pr]:
            rem = by_pri[pr] - done_pri[pr]
            lines.append(f"| {pr} | {by_pri[pr]} | {done_pri[pr]} | {rem} |")
    lines.append(f"| **TOTAL** | **{total}** | **{done}** | **{total - done}** |")
    return "\n".join(lines)
