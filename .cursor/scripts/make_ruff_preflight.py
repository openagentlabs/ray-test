#!/usr/bin/env python3
"""Run ``ruff check`` on each Python microservice; write per-service logs under a session folder."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from make_log_session import RUFF_SERVICE_DIRS, MakeLogSession


@dataclass
class RuffServiceResult:
    service_id: str
    server_dir: Path
    json_path: Path
    text_path: Path
    exit_code: int
    issues: list[dict[str, Any]] = field(default_factory=list)
    error_message: str = ""


def _ruff_cmd(server_dir: Path) -> list[str]:
    venv_ruff = server_dir / ".venv/bin/ruff"
    if venv_ruff.is_file():
        return [str(venv_ruff), "check", "."]
    return ["ruff", "check", "."]


def run_ruff_preflight(session: MakeLogSession) -> list[RuffServiceResult]:
    results: list[RuffServiceResult] = []
    for service_id, server_dir in RUFF_SERVICE_DIRS:
        json_path = session.artifact_path(service_id, "json")
        text_path = session.artifact_path(service_id, "txt")
        result = RuffServiceResult(
            service_id=service_id,
            server_dir=server_dir,
            json_path=json_path,
            text_path=text_path,
            exit_code=0,
        )

        if not server_dir.is_dir():
            result.error_message = f"missing directory: {server_dir}"
            result.exit_code = 127
            text_path.write_text(result.error_message + "\n", encoding="utf-8")
            json_path.write_text("[]\n", encoding="utf-8")
            results.append(result)
            continue

        cmd_json = _ruff_cmd(server_dir) + ["--output-format=json"]
        proc_json = subprocess.run(
            cmd_json,
            cwd=server_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        result.exit_code = proc_json.returncode

        raw_json = proc_json.stdout.strip() or "[]"
        try:
            parsed = json.loads(raw_json)
            if isinstance(parsed, list):
                result.issues = parsed
            else:
                result.error_message = "unexpected ruff JSON shape"
        except json.JSONDecodeError:
            result.error_message = proc_json.stderr.strip() or "ruff JSON parse failed"
            parsed = []

        json_path.write_text(json.dumps(parsed, indent=2) + "\n", encoding="utf-8")

        cmd_text = _ruff_cmd(server_dir) + ["--output-format=full"]
        proc_text = subprocess.run(
            cmd_text,
            cwd=server_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        text_body = proc_text.stdout
        if proc_text.stderr.strip():
            text_body = (text_body + "\n" if text_body else "") + proc_text.stderr
        if result.error_message and result.error_message not in text_body:
            text_body = (text_body + "\n" if text_body else "") + result.error_message
        if not text_body.strip():
            text_body = "All checks passed!\n"
        text_path.write_text(text_body, encoding="utf-8")
        results.append(result)

    meta = {
        "stamp": session.stamp,
        "directory": str(session.directory),
        "services": [
            {
                "service_id": r.service_id,
                "issue_count": len(r.issues),
                "exit_code": r.exit_code,
                "json": str(r.json_path.name),
                "text": str(r.text_path.name),
            }
            for r in results
        ],
    }
    (session.directory / f"session_{session.stamp}.json").write_text(
        json.dumps(meta, indent=2) + "\n",
        encoding="utf-8",
    )
    return results


def main() -> int:
    session = MakeLogSession.create()
    results = run_ruff_preflight(session)
    total = sum(len(r.issues) for r in results)
    print(f"ruff preflight session: {session.directory}")
    for r in results:
        status = "ok" if not r.issues and r.exit_code == 0 else f"{len(r.issues)} issue(s)"
        print(f"  {r.service_id}: {status}")
    print(f"total issues: {total}")
    print(str(session.directory))
    return 0 if total == 0 else 0  # preflight is informational; do not block start


if __name__ == "__main__":
    raise SystemExit(main())
