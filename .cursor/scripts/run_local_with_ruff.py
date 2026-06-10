#!/usr/bin/env python3
"""Orchestrate make start/stop/restart: optional ruff preflight → stack control → ruff report."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPTS_DIR.parents[1]
_START_LOCAL = _REPO_ROOT / "make/start_local.py"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from make_log_session import MakeLogSession  # noqa: E402
from make_ruff_preflight import run_ruff_preflight  # noqa: E402
from make_ruff_report import build_report  # noqa: E402


def _scripts_python() -> str:
    venv_py = _REPO_ROOT / "make/.venv/bin/python3"
    if venv_py.is_file():
        return str(venv_py)
    return sys.executable


def _run_start_local(command: str, services: list[str]) -> int:
    argv = [_scripts_python(), str(_START_LOCAL), command, *services]
    proc = subprocess.run(argv, check=False)
    return proc.returncode


def run_stack_command(*, command: str, services: list[str]) -> int:
    if command == "restart":
        return _run_start_local("restart", services)

    full_start = command == "start" and not services

    if command == "stop":
        return _run_start_local("stop", services)

    if not full_start:
        return _run_start_local("start", services)

    session = MakeLogSession.create()
    run_ruff_preflight(session)
    start_rc = _run_start_local("start", services)
    build_report(session.directory)
    return start_rc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        nargs="?",
        choices=("start", "stop", "restart"),
        default="start",
        help="start all/partial stack, stop, or restart (stop then start)",
    )
    parser.add_argument(
        "services",
        nargs="*",
        metavar="SERVICE",
        help="optional service id(s), e.g. iam frontend",
    )
    parser.add_argument("--stop", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--skip-start", action="store_true", help="Run ruff + report only.")
    args = parser.parse_args()

    if args.skip_start:
        session = MakeLogSession.create()
        run_ruff_preflight(session)
        build_report(session.directory)
        return 0

    command = "stop" if args.stop else args.command
    return run_stack_command(command=command, services=list(args.services))


if __name__ == "__main__":
    raise SystemExit(main())
