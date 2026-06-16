"""CLI tests for doctor / env-check."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_TOOL_ROOT = Path(__file__).resolve().parents[1]


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["JP_TOOL_SKIP_BUILD_GATE"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "jp_tool", *args],
        cwd=_TOOL_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_doctor_exits_zero_with_json_report() -> None:
    completed = _run(["doctor"])
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["python"]["ok"] is True
    assert len(payload["dependencies"]) >= 4


def test_env_check_alias_matches_doctor() -> None:
    doctor = _run(["doctor"])
    alias = _run(["env-check"])
    assert doctor.returncode == alias.returncode == 0
    assert json.loads(doctor.stdout)["ok"] == json.loads(alias.stdout)["ok"]
