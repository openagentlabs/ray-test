"""CLI entry point for isg-scan-reader.

Validates and summarises ISG supplementary scan CSV files. Supports three
subcommands:

  validate   — validate one or more files; exit 1 on schema or data error
  summary    — validate + print a severity-breakdown table per file
  merge      — validate all three supplementary files and emit combined JSON

Usage (from repo root):
    uv run --project .cursor/tools/isg_scan_reader isg-scan-reader validate --file <PATH>
    uv run --project .cursor/tools/isg_scan_reader isg-scan-reader summary --file <PATH>
    uv run --project .cursor/tools/isg_scan_reader isg-scan-reader validate \\
        --file container_images.csv --file iac.csv --file oss_packages.csv
    uv run --project .cursor/tools/isg_scan_reader isg-scan-reader merge \\
        --container <path> --iac <path> --oss <path>
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from isg_scan_reader.models import CvePackageRow, IacRow, detect_schema


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_and_validate(path: Path) -> tuple[str, list[dict[str, Any]], list[str]]:
    """Load *path*, detect schema, validate every row with Pydantic.

    Returns:
        (scan_type, raw_rows_as_dicts, error_lines)

    error_lines is empty on success. On any Pydantic error the list contains
    human-readable `[FAIL] row N: <message>` strings.
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not path.is_file():
        raise ValueError(f"Not a regular file: {path}")

    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError("CSV has no header row.")
        headers = list(reader.fieldnames)
        raw_rows = list(reader)

    try:
        scan_type, ModelClass = detect_schema(headers)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    # Refine scan_type for oss vs container by filename heuristic
    stem = path.stem.lower()
    if scan_type == "container" and "oss" in stem:
        scan_type = "oss"

    errors: list[str] = []
    for idx, row in enumerate(raw_rows, start=2):  # row 1 = header
        try:
            ModelClass.model_validate(row)
        except ValidationError as exc:
            for err in exc.errors():
                field = ".".join(str(loc) for loc in err["loc"])
                msg = err["msg"]
                errors.append(f"[FAIL] row {idx}: {field} — {msg}")

    return scan_type, raw_rows, errors


def _severity_table(rows: list[dict[str, Any]], label: str, scan_type: str) -> str:
    """Return a markdown severity breakdown table for *rows*."""
    sev: Counter[str] = Counter()
    info_count = 0
    for row in rows:
        s = (row.get("Severity") or "").strip().upper()
        if scan_type == "iac" and not (row.get("Misconfigurations") or "").strip():
            info_count += 1
        elif s:
            sev[s] += 1
        else:
            sev["UNKNOWN"] += 1

    order = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"]
    lines = [
        f"### {label} ({sum(sev.values())} finding(s){', ' + str(info_count) + ' informational' if info_count else ''})",
        "",
        "| Severity | Count |",
        "|---|---|",
    ]
    for s in order:
        if sev[s]:
            lines.append(f"| {s} | {sev[s]} |")
    if info_count:
        lines.append(f"| _(informational / pass rows)_ | {info_count} |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Subcommand implementations
# ---------------------------------------------------------------------------

def cmd_validate(args: argparse.Namespace) -> int:
    """Validate one or more files. Print [PASS] / [FAIL] per file."""
    all_ok = True
    for raw_path in args.file:
        path = Path(raw_path).expanduser().resolve()
        try:
            scan_type, rows, errors = _load_and_validate(path)
        except (FileNotFoundError, ValueError) as exc:
            print(f"[FAIL] {path.name}: {exc}", file=sys.stderr)
            all_ok = False
            continue

        if errors:
            print(f"[FAIL] {path.name} ({scan_type}, {len(rows)} rows):", file=sys.stderr)
            for line in errors[:20]:
                print(f"  {line}", file=sys.stderr)
            if len(errors) > 20:
                print(f"  ... and {len(errors) - 20} more error(s).", file=sys.stderr)
            all_ok = False
        else:
            print(f"[PASS] {path.name} — {scan_type}, {len(rows)} rows, schema valid.")

    return 0 if all_ok else 1


def cmd_summary(args: argparse.Namespace) -> int:
    """Validate and print a severity breakdown table per file."""
    all_ok = True
    for raw_path in args.file:
        path = Path(raw_path).expanduser().resolve()
        try:
            scan_type, rows, errors = _load_and_validate(path)
        except (FileNotFoundError, ValueError) as exc:
            print(f"[FAIL] {path.name}: {exc}", file=sys.stderr)
            all_ok = False
            continue

        if errors:
            print(f"[FAIL] {path.name}: {len(errors)} validation error(s).", file=sys.stderr)
            for line in errors[:10]:
                print(f"  {line}", file=sys.stderr)
            all_ok = False
            continue

        print(_severity_table(rows, path.name, scan_type))
        print()

    return 0 if all_ok else 1


def cmd_merge(args: argparse.Namespace) -> int:
    """Validate all three supplementary files and emit combined JSON to stdout."""
    specs = [
        ("container", args.container),
        ("iac", args.iac),
        ("oss", args.oss),
    ]
    combined: list[dict[str, Any]] = []
    all_ok = True

    for expected_type, raw_path in specs:
        if not raw_path:
            continue
        path = Path(raw_path).expanduser().resolve()
        try:
            scan_type, rows, errors = _load_and_validate(path)
        except (FileNotFoundError, ValueError) as exc:
            print(f"[FAIL] {path.name}: {exc}", file=sys.stderr)
            all_ok = False
            continue

        if errors:
            print(f"[FAIL] {path.name}: {len(errors)} validation error(s).", file=sys.stderr)
            for line in errors[:10]:
                print(f"  {line}", file=sys.stderr)
            all_ok = False
            continue

        for row in rows:
            combined.append({"_source": expected_type, "_file": str(path), **row})

    if not all_ok:
        return 1

    json.dump(combined, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="isg-scan-reader",
        description=(
            "Validate and summarise ISG supplementary scan CSVs "
            "(container images, IaC, OSS packages) using Pydantic schema enforcement."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # validate subcommand
    p_val = sub.add_parser("validate", help="Validate one or more CSV files.")
    p_val.add_argument(
        "--file",
        action="append",
        required=True,
        metavar="PATH",
        help="Path to a CSV file. Repeat to validate multiple files.",
    )

    # summary subcommand
    p_sum = sub.add_parser("summary", help="Validate and print severity breakdown table.")
    p_sum.add_argument(
        "--file",
        action="append",
        required=True,
        metavar="PATH",
        help="Path to a CSV file. Repeat for multiple files.",
    )

    # merge subcommand
    p_merge = sub.add_parser(
        "merge",
        help="Validate all three supplementary files and emit combined JSON.",
    )
    p_merge.add_argument("--container", metavar="PATH", help="container_images CSV path.")
    p_merge.add_argument("--iac", metavar="PATH", help="iac CSV path.")
    p_merge.add_argument("--oss", metavar="PATH", help="oss_packages CSV path.")

    args = parser.parse_args()

    dispatch = {"validate": cmd_validate, "summary": cmd_summary, "merge": cmd_merge}
    sys.exit(dispatch[args.command](args))


if __name__ == "__main__":
    main()
