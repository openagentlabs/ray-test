#!/usr/bin/env python3
"""Build markdown ruff report (summary + detailed tables) for a make-local session folder."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from make_log_session import MAKE_LOGS_ROOT, REPO_ROOT


@dataclass(frozen=True)
class IssueRow:
    issue_id: int
    service_id: str
    rule_code: str
    file_path: str
    line: int
    column: int
    message: str
    severity_light: str
    doc_url: str


def _traffic_emoji(light: str) -> str:
    return {"green": "🟢", "amber": "🟡", "red": "🔴"}.get(light, "⚪")


def _service_light(issue_count: int, error_count: int, tool_error: bool) -> str:
    if tool_error:
        return "red"
    if issue_count == 0:
        return "green"
    if error_count > 0 or issue_count >= 10:
        return "red"
    return "amber"


def _issue_light(code: str) -> str:
    prefix = code.split()[0] if code else ""
    if prefix.startswith(("F", "E", "S", "B", "ASYNC")):
        return "red"
    if prefix.startswith(("I", "UP", "ANN")):
        return "amber"
    return "amber"


def _is_error_code(code: str) -> bool:
    return _issue_light(code) == "red"


def _rel_path(path_str: str) -> str:
    path = Path(path_str)
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _file_link(rel: str, line: int) -> str:
    return f"{rel}#L{line}"


def _load_service_json(session_dir: Path, service_id: str, stamp: str) -> tuple[list[dict[str, Any]], str]:
    json_path = session_dir / f"{service_id}_{stamp}.json"
    if not json_path.is_file():
        return [], f"missing {json_path.name}"
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [], f"invalid JSON: {exc}"
    if not isinstance(data, list):
        return [], "unexpected JSON shape"
    return data, ""


def _discover_stamp(session_dir: Path) -> str:
    for path in sorted(session_dir.glob("session_*.json")):
        try:
            meta = json.loads(path.read_text(encoding="utf-8"))
            stamp = str(meta.get("stamp", "")).strip()
            if stamp:
                return stamp
        except json.JSONDecodeError:
            continue
    name = session_dir.name
    if name.isdigit() and len(name) == 14:
        return name
    matches = list(session_dir.glob("*_*.json"))
    if matches:
        stem = matches[0].stem
        if "_" in stem:
            return stem.rsplit("_", 1)[-1]
    return name


def build_report(session_dir: Path, *, stamp: str | None = None) -> Path:
    session_dir = session_dir.resolve()
    if not session_dir.is_dir():
        raise FileNotFoundError(f"session directory not found: {session_dir}")

    stamp_value = stamp or _discover_stamp(session_dir)
    session_meta_path = session_dir / f"session_{stamp_value}.json"
    services: list[str] = []
    if session_meta_path.is_file():
        meta = json.loads(session_meta_path.read_text(encoding="utf-8"))
        services = [str(s["service_id"]) for s in meta.get("services", []) if s.get("service_id")]

    if not services:
        services = sorted({p.name.rsplit("_", 1)[0] for p in session_dir.glob(f"*_{stamp_value}.json")})

    issue_rows: list[IssueRow] = []
    summary_rows: list[tuple[str, str, int, int, int, str, str]] = []
    issue_id = 1

    for service_id in services:
        issues, tool_error = _load_service_json(session_dir, service_id, stamp_value)
        error_count = sum(1 for item in issues if _is_error_code(str(item.get("code", ""))))
        style_count = len(issues) - error_count
        light = _service_light(len(issues), error_count, bool(tool_error))
        summary_rows.append(
            (
                service_id,
                _traffic_emoji(light),
                len(issues),
                error_count,
                style_count,
                tool_error or "—",
                light,
            )
        )
        for item in issues:
            code = str(item.get("code", ""))
            loc = item.get("location") or {}
            line = int(loc.get("row") or 0)
            column = int(loc.get("column") or 0)
            rel = _rel_path(str(item.get("filename", "")))
            doc_url = str(item.get("url") or "")
            issue_rows.append(
                IssueRow(
                    issue_id=issue_id,
                    service_id=service_id,
                    rule_code=code,
                    file_path=rel,
                    line=line,
                    column=column,
                    message=str(item.get("message", "")).replace("|", "\\|"),
                    severity_light=_issue_light(code),
                    doc_url=doc_url,
                )
            )
            issue_id += 1

    total_issues = sum(r[2] for r in summary_rows)
    total_errors = sum(r[3] for r in summary_rows)
    overall_light = _service_light(total_issues, total_errors, False)
    report_path = session_dir / f"ruff-report_{stamp_value}.md"

    lines: list[str] = [
        f"# Make local — ruff report `{stamp_value}`",
        "",
        f"Session folder: `{session_dir.relative_to(REPO_ROOT).as_posix()}`",
        "",
        "## Summary",
        "",
        f"Overall: {_traffic_emoji(overall_light)} **{total_issues}** issue(s) "
        f"({total_errors} error-class, {total_issues - total_errors} style-class) "
        f"across **{len(summary_rows)}** Python service(s).",
        "",
        "| Service | Status | Issues | Errors | Style | Notes |",
        "| --- | :---: | ---: | ---: | ---: | --- |",
    ]
    for service_id, emoji, count, errors, style, note, _light in summary_rows:
        lines.append(f"| `{service_id}` | {emoji} | {count} | {errors} | {style} | {note} |")

    lines.extend(
        [
            "",
            "## Detailed findings",
            "",
        ]
    )
    if not issue_rows:
        lines.append("_No ruff issues recorded._")
    else:
        lines.extend(
            [
                "| ID | Status | Service | Rule | File | Line | Col | Message | Link |",
                "| ---: | :---: | --- | --- | --- | ---: | ---: | --- | --- |",
            ]
        )
        for row in issue_rows:
            loc_link = _file_link(row.file_path, row.line) if row.line else row.file_path
            rule_link = f"[{row.rule_code}]({row.doc_url})" if row.doc_url else row.rule_code
            file_cell = f"[`{row.file_path}`]({loc_link})" if row.file_path else "—"
            lines.append(
                f"| {row.issue_id} | {_traffic_emoji(row.severity_light)} | `{row.service_id}` | "
                f"{rule_link} | {file_cell} | {row.line or '—'} | {row.column or '—'} | "
                f"{row.message} | [{loc_link}]({loc_link}) |"
            )

    lines.extend(["", "## Artifacts", ""])
    for path in sorted(session_dir.iterdir()):
        if path.is_file():
            lines.append(f"- `{path.name}`")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--session-dir",
        type=Path,
        default=None,
        help="Session folder under .cursor/scratch/make-logs (default: latest).",
    )
    parser.add_argument("--stamp", default="", help="Optional session stamp override.")
    args = parser.parse_args()

    if args.session_dir is not None:
        session_dir = args.session_dir if args.session_dir.is_absolute() else REPO_ROOT / args.session_dir
    else:
        if not MAKE_LOGS_ROOT.is_dir():
            print("error: no make-logs directory yet.", file=sys.stderr)
            return 1
        candidates = sorted(
            (p for p in MAKE_LOGS_ROOT.iterdir() if p.is_dir()),
            key=lambda p: p.name,
            reverse=True,
        )
        if not candidates:
            print("error: no session folders found.", file=sys.stderr)
            return 1
        session_dir = candidates[0]

    try:
        report = build_report(session_dir, stamp=args.stamp or None)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"report: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
