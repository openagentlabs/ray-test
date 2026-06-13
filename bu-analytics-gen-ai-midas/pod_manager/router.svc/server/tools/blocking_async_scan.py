#!/usr/bin/env python3
"""Delegate to repository-wide ``scripts/blocking_async_scan.py`` (this service's ``src``)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "blocking_async_scan.py"
_SRC = Path(__file__).resolve().parents[1] / "src"


def main() -> int:
    proc = subprocess.run(
        [sys.executable, str(_REPO_SCRIPT), str(_SRC)],
        check=False,
    )
    return int(proc.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
