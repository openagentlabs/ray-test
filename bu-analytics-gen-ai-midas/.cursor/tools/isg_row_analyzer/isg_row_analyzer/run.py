"""
isg-row-analyzer — single-row context fetch and write-result patch.

Two modes:

  GET-CONTEXT (default):
    Read one row from the CSV by obv_id, resolve sink/source files in the repo,
    read code snippets (80 lines centred on the cited line), and print structured
    JSON to stdout.  The Cursor agent reads this output, reasons about the code,
    and produces a result JSON blob.

  WRITE-RESULT (--write-result '<json>'):
    Receive the agent's analysis JSON on the --write-result flag, atomically
    patch that one row in the CSV, and write an analysis_log/<uuid>.md file.

Exit codes:
  0  Success
  1  Row not found / file error / bad JSON in --write-result
  2  Usage / argument error
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import uuid
from pathlib import Path
from typing import Optional

# ── constants ─────────────────────────────────────────────────────────────────

SNIPPET_CONTEXT = 40  # lines before/after cited line (80-line window)

_SCANNER_PREFIX_RE = re.compile(
    r"^(?:local|Downloads|users)[^\\/]*[/\\](?:[^\\/]+[/\\])*",
    re.IGNORECASE,
)

# ── path helpers ──────────────────────────────────────────────────────────────

def _normalise_path(raw: str) -> str:
    if not raw:
        return ""
    p = raw.replace("\\", "/")
    p = _SCANNER_PREFIX_RE.sub("", p)
    p = p.lstrip("./")
    return p


def _resolve_file(raw: str, repo: Path) -> tuple[Optional[Path], str]:
    norm = _normalise_path(raw)
    if not norm:
        return None, norm
    candidate = repo / norm
    if candidate.is_file():
        return candidate, norm
    direct = Path(norm)
    if direct.is_absolute() and direct.is_file():
        return direct, norm
    return None, norm


def _read_snippet(file_path: Path, line_no: Optional[int], context: int = SNIPPET_CONTEXT) -> str:
    try:
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return f"[read error: {exc}]"
    if not lines:
        return "[empty file]"
    ln = max(1, line_no or 1)
    start = max(0, ln - context - 1)
    end = min(len(lines), ln + context)
    numbered = [f"{i + 1:>5} | {lines[i]}" for i in range(start, end)]
    return "\n".join(numbered)


def _safe_int(s: str) -> Optional[int]:
    try:
        return int(s.strip())
    except (ValueError, AttributeError):
        return None

# ── CSV helpers ───────────────────────────────────────────────────────────────

def _read_csv(path: Path) -> tuple[list[str], list[dict]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        if not fieldnames:
            raise ValueError(f"CSV has no header: {path}")
        rows = [dict(r) for r in reader]
    return fieldnames, rows


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    """Atomic write via tmp-rename."""
    # Ensure owner field is present
    if "owner" not in fieldnames:
        try:
            idx = fieldnames.index("acceptance_criteria")
            fieldnames = fieldnames[:idx + 1] + ["owner"] + fieldnames[idx + 1:]
        except ValueError:
            fieldnames = fieldnames + ["owner"]
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL, extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def _find_row(rows: list[dict], obv_id: str) -> Optional[dict]:
    for r in rows:
        if (r.get("obv_id") or "").strip() == obv_id.strip():
            return r
    return None


def _find_row_index(rows: list[dict], obv_id: str) -> int:
    for i, r in enumerate(rows):
        if (r.get("obv_id") or "").strip() == obv_id.strip():
            return i
    return -1

# ── get-context mode ──────────────────────────────────────────────────────────

def _get_context(csv_path: Path, obv_id: str, repo: Path) -> None:
    fieldnames, rows = _read_csv(csv_path)
    row = _find_row(rows, obv_id)
    if row is None:
        print(
            json.dumps({"error": f"Row '{obv_id}' not found in CSV: {csv_path}"}),
            file=sys.stderr,
        )
        sys.exit(1)

    sink_raw = row.get("sink_file") or ""
    src_raw = row.get("source_file") or ""
    sink_line = _safe_int(row.get("sink_line") or "")
    src_line = _safe_int(row.get("source_line") or "")

    sink_abs, sink_norm = _resolve_file(sink_raw, repo)
    src_abs, src_norm = _resolve_file(src_raw, repo)

    # Prefer sink for snippet
    if sink_abs and sink_line:
        snippet = _read_snippet(sink_abs, sink_line)
        snippet_path = sink_norm
        snippet_line = sink_line
        file_found = True
    elif src_abs and src_line:
        snippet = _read_snippet(src_abs, src_line)
        snippet_path = src_norm
        snippet_line = src_line
        file_found = True
    else:
        snippet = ""
        snippet_path = sink_norm or src_norm or "n/a"
        snippet_line = sink_line or src_line
        file_found = False

    # Also read full source file content if small enough (<=500 lines) for extra context
    full_file_content: Optional[str] = None
    primary_abs = sink_abs or src_abs
    if primary_abs:
        try:
            file_lines = primary_abs.read_text(encoding="utf-8", errors="replace").splitlines()
            if len(file_lines) <= 500:
                full_file_content = "\n".join(
                    f"{i + 1:>5} | {l}" for i, l in enumerate(file_lines)
                )
        except OSError:
            pass

    output = {
        "obv_id": obv_id,
        "fortify_priority": (row.get("fortify_priority") or "").strip(),
        "category": (row.get("category") or "").strip(),
        "sink_file": sink_norm,
        "sink_line": sink_line,
        "source_file": src_norm,
        "source_line": src_line,
        "file_found": file_found,
        "snippet_file": snippet_path,
        "snippet_around_line": snippet_line,
        "snippet": snippet,
        "full_file_content": full_file_content,
        "abstract": (row.get("abstract") or "").strip(),
        "explanation": (row.get("explanation") or "").strip(),
        "recommendation": (row.get("recommendation") or "").strip(),
        "existing_analysis_id": (row.get("analysis_id") or "").strip(),
        "existing_issue_state": (row.get("issue_state") or "").strip(),
        "instructions": (
            "You are the Cursor AI agent. Read the code snippet and full_file_content above. "
            "Reason about the actual code to produce a grounded analysis. "
            "Then call isg-row-analyzer --write-result with a JSON blob containing these keys: "
            "root_cause, remediation_plan, validation, acceptance_criteria, "
            "resolution_owner (AI_AGENT or H_REQ), owner (Software or DevOps), "
            "complexity (LOW|MID|HIGH|MAX), human_fix_hours, cursor_fix_hours, hybrid_fix_hours. "
            "Do NOT produce template or boilerplate text — ground every statement in the actual code shown."
        ),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))

# ── write-result mode ─────────────────────────────────────────────────────────

_REQUIRED_RESULT_FIELDS = {
    "root_cause",
    "remediation_plan",
    "validation",
    "acceptance_criteria",
    "resolution_owner",
    "owner",
    "complexity",
    "human_fix_hours",
    "cursor_fix_hours",
    "hybrid_fix_hours",
}


def _write_result(csv_path: Path, obv_id: str, repo: Path, result_json: str, log_dir: Path) -> None:
    try:
        result = json.loads(result_json)
    except json.JSONDecodeError as exc:
        print(f"[ERROR] --write-result value is not valid JSON: {exc}", file=sys.stderr)
        sys.exit(1)

    missing = _REQUIRED_RESULT_FIELDS - set(result.keys())
    if missing:
        print(
            f"[ERROR] --write-result JSON is missing required fields: {sorted(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)

    fieldnames, rows = _read_csv(csv_path)
    idx = _find_row_index(rows, obv_id)
    if idx == -1:
        print(f"[ERROR] Row '{obv_id}' not found in CSV: {csv_path}", file=sys.stderr)
        sys.exit(1)

    row = dict(rows[idx])
    priority = (row.get("fortify_priority") or "").strip()
    cat = (row.get("category") or "").strip()
    sink_raw = row.get("sink_file") or ""
    src_raw = row.get("source_file") or ""
    sink_line = row.get("sink_line") or ""
    src_line = row.get("source_line") or ""
    _, sink_norm = _resolve_file(sink_raw, repo)
    _, src_norm = _resolve_file(src_raw, repo)

    aid = str(uuid.uuid4())
    log_dir.mkdir(parents=True, exist_ok=True)
    log_rel = f".cursor/scratch/analysis_log/{aid}.md"

    root_cause = result["root_cause"]
    remediation_plan = result["remediation_plan"]
    validation = result["validation"]
    acceptance_criteria = result["acceptance_criteria"]
    resolution_owner = result["resolution_owner"]
    team_owner = result["owner"]
    complexity = result["complexity"]
    human_hours = str(result.get("human_fix_hours", ""))
    cursor_hours = str(result.get("cursor_fix_hours", ""))
    hybrid_hours = str(result.get("hybrid_fix_hours", ""))

    # Write markdown log
    md_lines = [
        f"# Analysis log — {obv_id}",
        "",
        f"- **analysis_id:** `{aid}`",
        f"- **Fortify priority:** {priority}",
        f"- **Category:** {cat}",
        f"- **Sink:** `{sink_norm}` line {sink_line}",
        f"- **Source:** `{src_norm}` line {src_line}",
        "",
        "## Root cause",
        root_cause,
        "",
        "## Remediation plan",
        remediation_plan,
        "",
        "## Validation",
        validation,
        "",
        "## Acceptance criteria",
        acceptance_criteria,
        "",
        "## Disposition",
        f"- **resolution_owner:** {resolution_owner}",
        f"- **owner (team):** {team_owner}",
        f"- **complexity:** {complexity}",
        f"- **human_fix_hours:** {human_hours}",
        f"- **cursor_fix_hours:** {cursor_hours}",
        f"- **hybrid_fix_hours:** {hybrid_hours}",
        "",
        "---",
        "_Generated by isg-row-analyzer (agent-driven per-row analysis)._",
    ]
    (log_dir / f"{aid}.md").write_text("\n".join(md_lines), encoding="utf-8")

    # Patch row in CSV
    row["analysis_id"] = aid
    row["analysis_log_file"] = log_rel
    row["root_cause"] = root_cause
    row["remediation_plan"] = remediation_plan
    row["validation"] = validation
    row["acceptance_criteria"] = acceptance_criteria
    row["resolution_owner"] = resolution_owner
    row["owner"] = team_owner
    row["complexity"] = complexity
    row["human_fix_hours"] = human_hours
    row["cursor_fix_hours"] = cursor_hours
    row["hybrid_fix_hours"] = hybrid_hours
    row["issue_state"] = "ANALYZED"
    row["issue_resolve_progress"] = "Agent-driven per-row analysis: code read by Cursor agent."
    row["working_log"] = log_rel
    rows[idx] = row

    _write_csv(csv_path, fieldnames, rows)

    print(json.dumps({
        "status": "ok",
        "obv_id": obv_id,
        "analysis_id": aid,
        "log_file": log_rel,
    }, ensure_ascii=False, indent=2))

# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="isg-row-analyzer",
        description=(
            "Single-row context fetch (default) or write-result patch for "
            "agent-driven Fortify analysis."
        ),
    )
    parser.add_argument(
        "--csv",
        required=True,
        metavar="CSV_PATH",
        help="Path to workbook_issues.csv",
    )
    parser.add_argument(
        "--obv-id",
        required=True,
        metavar="OBV_ID",
        help="The obv_id value to operate on (e.g. OBV0042)",
    )
    parser.add_argument(
        "--repo",
        default=".",
        metavar="REPO_ROOT",
        help="Repo root for resolving sink/source paths (default: .)",
    )
    parser.add_argument(
        "--write-result",
        metavar="JSON",
        help=(
            "JSON blob with analysis result fields. When provided, patches the row "
            "in the CSV and writes the analysis_log file. Omit to run in get-context mode."
        ),
    )
    parser.add_argument(
        "--log-dir",
        default=".cursor/scratch/analysis_log",
        metavar="LOG_DIR",
        help="Directory for analysis_log/*.md files (default: .cursor/scratch/analysis_log)",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv).expanduser().resolve()
    repo = Path(args.repo).expanduser().resolve()
    log_dir = Path(args.log_dir).expanduser()
    if not log_dir.is_absolute():
        log_dir = repo / log_dir

    if not csv_path.is_file():
        print(f"[ERROR] CSV not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    if args.write_result is not None:
        _write_result(csv_path, args.obv_id, repo, args.write_result, log_dir)
    else:
        _get_context(csv_path, args.obv_id, repo)
