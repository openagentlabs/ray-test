#!/usr/bin/env python3
"""Legacy entry point — delegates to make/build.py (APP_ENV=dev, APP_TARGET=aws).

Prefer:
  make build-dev
  python3 make/build.py dev --yes
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BUILD_PY = REPO_ROOT / "make" / "build.py"


def main() -> int:
    argv = [sys.executable, str(BUILD_PY), "dev"]
    if "--yes" not in sys.argv[1:]:
        argv.append("--yes")
    argv.extend(sys.argv[1:])
    proc = subprocess.run(argv, cwd=REPO_ROOT)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
