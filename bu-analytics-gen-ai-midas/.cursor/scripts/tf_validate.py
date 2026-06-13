#!/usr/bin/env python3
"""
tf_validate.py — Run Checkov against MIDAS Terraform under `deploy/`.

Purpose:
    Execution helper for the `tf_validate` Cursor skill. Verifies the Checkov
    CLI is installed (and offers to install it via Homebrew when run
    interactively or with `--install`), scans a Terraform tree (default
    `deploy/`), and emits either a human-readable table or structured JSON
    the skill can format into a markdown report.

Prerequisites:
    - Python 3.9+
    - Checkov CLI (`brew install checkov` or `pip install checkov`)

Exit codes:
    0  No failed checks.
    1  Failed checks (violations) found.
    2  Operational error running Checkov or parsing its output.
    3  Checkov is not installed and was not (re)installed.

Quick start:
    python3 .cursor/scripts/tf_validate.py
    python3 .cursor/scripts/tf_validate.py --json
    python3 .cursor/scripts/tf_validate.py --path deploy/ecs-app --json
    python3 .cursor/scripts/tf_validate.py --install --json
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

AI_HELP_SCHEMA: dict[str, Any] = {
    "script": ".cursor/scripts/tf_validate.py",
    "purpose": (
        "Run Checkov on MIDAS Terraform under deploy/ and return a structured "
        "error report. Designed to be invoked by the `tf_validate` Cursor skill."
    ),
    "flags": {
        "--path PATH": "Path to scan (default: <repo>/deploy).",
        "--framework FRAMEWORK": "Checkov framework (default: terraform).",
        "--json": "Emit normalized JSON (for agents) instead of a human table.",
        "--install": (
            "If Checkov is missing, attempt `brew install checkov` before "
            "scanning. Non-interactive."
        ),
        "--skip-check ID": "Pass-through Checkov --skip-check (repeatable).",
        "--help": "Show human CLI help.",
        "--help-ai": "Print this JSON schema and exit (no tool calls).",
    },
    "exit_codes": {
        "0": "No failed checks.",
        "1": "Failed checks found.",
        "2": "Operational error.",
        "3": "Checkov not installed (and --install not used / failed).",
    },
    "examples": [
        "python3 .cursor/scripts/tf_validate.py",
        "python3 .cursor/scripts/tf_validate.py --json",
        "python3 .cursor/scripts/tf_validate.py --path deploy/ecs-app --json",
        "python3 .cursor/scripts/tf_validate.py --install --json",
    ],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _repo_root() -> Path:
    """Git top-level if available, else the current working directory."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if out:
            return Path(out)
    except Exception:
        pass
    return Path.cwd()


def _checkov_on_path() -> str | None:
    return shutil.which("checkov")


def _install_checkov_via_brew() -> bool:
    brew = shutil.which("brew")
    if not brew:
        print(
            "[ERROR] Homebrew (`brew`) is not on PATH. Install Checkov "
            "manually (e.g. `pip install checkov`) and retry.",
            file=sys.stderr,
        )
        return False
    print("[INFO] Installing Checkov: brew install checkov", file=sys.stderr)
    rc = subprocess.call([brew, "install", "checkov"])
    return rc == 0 and _checkov_on_path() is not None


def _emit_missing(as_json: bool, message: str, attempted_install: bool) -> None:
    payload = {
        "error": message,
        "tool": "checkov",
        "install_command": "brew install checkov",
        "pip_fallback": "python3 -m pip install checkov",
        "attempted_install": attempted_install,
    }
    if as_json:
        json.dump(payload, sys.stdout)
        print()
    else:
        print(f"[ERROR] {message}", file=sys.stderr)
        print(f"        Install: {payload['install_command']}", file=sys.stderr)
        print(f"        or:      {payload['pip_fallback']}", file=sys.stderr)


def _ensure_checkov(install: bool, as_json: bool) -> str | None:
    """Return the checkov binary path, or None if it cannot be resolved."""
    path = _checkov_on_path()
    if path:
        return path

    if install:
        if _install_checkov_via_brew():
            return _checkov_on_path()
        _emit_missing(
            as_json,
            "Checkov installation via Homebrew failed.",
            attempted_install=True,
        )
        return None

    if sys.stdin.isatty() and sys.stdout.isatty():
        print("[WARN] Checkov is not installed.", file=sys.stderr)
        print("       Install command: brew install checkov", file=sys.stderr)
        try:
            answer = input(
                "Install Checkov now via `brew install checkov`? [y/N] "
            ).strip().lower()
        except EOFError:
            answer = ""
        if answer in ("y", "yes"):
            if _install_checkov_via_brew():
                return _checkov_on_path()
            _emit_missing(
                as_json,
                "Checkov installation via Homebrew failed.",
                attempted_install=True,
            )
            return None

    _emit_missing(
        as_json,
        "Checkov is not installed.",
        attempted_install=False,
    )
    return None


def _run_checkov(
    checkov_bin: str,
    path: Path,
    framework: str,
    skip_checks: list[str],
) -> subprocess.CompletedProcess[str]:
    cmd = [
        checkov_bin,
        "-d", str(path),
        "--framework", framework,
        "-o", "json",
        "--quiet",
        "--soft-fail",
    ]
    for sc in skip_checks:
        cmd += ["--skip-check", sc]
    return subprocess.run(cmd, capture_output=True, text=True)


def _parse_checkov_json(stdout: str) -> dict[str, list]:
    """
    Normalize Checkov's JSON output (list-of-frameworks OR single-object)
    into a flat aggregate.
    """
    agg: dict[str, list] = {
        "passed": [],
        "failed": [],
        "skipped": [],
        "parsing_errors": [],
    }
    text = (stdout or "").strip()
    if not text:
        return agg

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Could not parse Checkov JSON output: {e}") from e

    frameworks = data if isinstance(data, list) else [data]
    for fw in frameworks:
        if not isinstance(fw, dict):
            continue
        results = fw.get("results") or {}
        agg["passed"].extend(results.get("passed_checks", []) or [])
        agg["failed"].extend(results.get("failed_checks", []) or [])
        agg["skipped"].extend(results.get("skipped_checks", []) or [])
        # parsing_errors can live on the framework object directly
        agg["parsing_errors"].extend(results.get("parsing_errors", []) or [])
        agg["parsing_errors"].extend(fw.get("parsing_errors", []) or [])
    return agg


def _format_human_table(agg: dict[str, list], scan_path: Path) -> str:
    failed = agg["failed"]
    passed = agg["passed"]
    skipped = agg["skipped"]
    parsing_errors = agg["parsing_errors"]

    lines: list[str] = []
    lines.append("=" * 96)
    lines.append(f"Checkov report  |  path: {scan_path}  |  framework: terraform")
    lines.append("-" * 96)
    lines.append(
        f"Summary: passed={len(passed)}  failed={len(failed)}  "
        f"skipped={len(skipped)}  parsing_errors={len(parsing_errors)}"
    )
    lines.append("=" * 96)

    if parsing_errors:
        lines.append("")
        lines.append("Parsing errors:")
        for p in parsing_errors:
            lines.append(f"  - {p}")

    if not failed:
        if not parsing_errors:
            lines.append("No violations found.")
        return "\n".join(lines)

    lines.append("")
    lines.append(f"{'ID':<14} {'Severity':<10} {'Resource':<55} File:Line")
    lines.append("-" * 96)
    for chk in failed:
        cid = str(chk.get("check_id") or "")
        sev = str((chk.get("severity") or "").upper() or "N/A")
        res = str(chk.get("resource") or "")[:55]
        fp = chk.get("file_path") or ""
        rng = chk.get("file_line_range") or []
        loc = f"{fp}:{rng[0]}" if fp and rng else fp
        lines.append(f"{cid:<14} {sev:<10} {res:<55} {loc}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Run Checkov on MIDAS Terraform under deploy/.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    ap.add_argument("--help-ai", action="store_true",
                    help="Print machine-readable JSON schema and exit.")
    ap.add_argument("--path", default=None,
                    help="Path to scan (default: <repo>/deploy).")
    ap.add_argument("--framework", default="terraform",
                    help="Checkov --framework (default: terraform).")
    ap.add_argument("--json", dest="as_json", action="store_true",
                    help="Emit normalized JSON instead of a human table.")
    ap.add_argument("--install", action="store_true",
                    help="If Checkov is missing, install it via Homebrew.")
    ap.add_argument("--skip-check", action="append", default=[],
                    metavar="ID",
                    help="Pass-through Checkov --skip-check (repeatable).")
    args = ap.parse_args()

    if args.help_ai:
        print(json.dumps(AI_HELP_SCHEMA, indent=2))
        return 0

    scan_path = (
        Path(args.path).resolve()
        if args.path
        else (_repo_root() / "deploy").resolve()
    )

    if not scan_path.exists():
        err = {"error": f"Scan path does not exist: {scan_path}"}
        if args.as_json:
            json.dump(err, sys.stdout); print()
        else:
            print(f"[ERROR] {err['error']}", file=sys.stderr)
        return 2

    checkov_bin = _ensure_checkov(install=args.install, as_json=args.as_json)
    if not checkov_bin:
        return 3

    try:
        result = _run_checkov(
            checkov_bin=checkov_bin,
            path=scan_path,
            framework=args.framework,
            skip_checks=args.skip_check,
        )
    except OSError as e:
        err = {"error": f"Failed to execute Checkov: {e}"}
        if args.as_json:
            json.dump(err, sys.stdout); print()
        else:
            print(f"[ERROR] {err['error']}", file=sys.stderr)
        return 2

    # With --soft-fail Checkov exits 0 on findings; any non-zero is an
    # operational error we should surface to the skill.
    if result.returncode != 0:
        err = {
            "error": "Checkov exited with a non-zero status.",
            "returncode": result.returncode,
            "stderr_tail": (result.stderr or "").strip().splitlines()[-20:],
        }
        if args.as_json:
            json.dump(err, sys.stdout); print()
        else:
            print(f"[ERROR] {err['error']} (exit {result.returncode})",
                  file=sys.stderr)
            if result.stderr:
                sys.stderr.write(result.stderr)
        return 2

    try:
        agg = _parse_checkov_json(result.stdout)
    except RuntimeError as e:
        err = {
            "error": str(e),
            "stdout_tail": (result.stdout or "").strip().splitlines()[-20:],
        }
        if args.as_json:
            json.dump(err, sys.stdout); print()
        else:
            print(f"[ERROR] {err['error']}", file=sys.stderr)
        return 2

    has_failures = bool(agg["failed"]) or bool(agg["parsing_errors"])

    if args.as_json:
        payload = {
            "path": str(scan_path),
            "framework": args.framework,
            "summary": {
                "passed": len(agg["passed"]),
                "failed": len(agg["failed"]),
                "skipped": len(agg["skipped"]),
                "parsing_errors": len(agg["parsing_errors"]),
            },
            "failed_checks": [
                {
                    "check_id": c.get("check_id"),
                    "check_name": c.get("check_name"),
                    "severity": (c.get("severity") or "").upper() or None,
                    "resource": c.get("resource"),
                    "file_path": c.get("file_path"),
                    "file_line_range": c.get("file_line_range"),
                    "guideline": c.get("guideline"),
                }
                for c in agg["failed"]
            ],
            "parsing_errors": agg["parsing_errors"],
        }
        json.dump(payload, sys.stdout, indent=2)
        print()
    else:
        print(_format_human_table(agg, scan_path))

    return 1 if has_failures else 0


if __name__ == "__main__":
    sys.exit(main())
