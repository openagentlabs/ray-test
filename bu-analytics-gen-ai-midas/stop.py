#!/usr/bin/env python3
"""Stop MIDAS local dev processes and optional Docker Postgres/Redis."""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent
STATE_DIR = ROOT / "runb-local" / "state"
PID_FILE = STATE_DIR / "pids.json"


def log(msg: str) -> None:
    print(msg, flush=True)


def docker_compose_base() -> List[str] | None:
    if not shutil.which("docker"):
        return None
    try:
        subprocess.run(
            ["docker", "compose", "version"],
            check=True,
            capture_output=True,
            text=True,
        )
        return ["docker", "compose"]
    except subprocess.CalledProcessError:
        pass
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    return None


def kill_pid(pid: int, name: str) -> None:
    if pid <= 0:
        return
    try:
        os.kill(pid, signal.SIGTERM)
        log(f"Sent SIGTERM to {name} (pid {pid})")
        for _ in range(15):
            try:
                os.kill(pid, 0)
                time.sleep(0.5)
            except OSError:
                log(f"{name} stopped")
                return
        os.kill(pid, signal.SIGKILL)
        log(f"Sent SIGKILL to {name} (pid {pid})")
    except ProcessLookupError:
        log(f"{name} (pid {pid}) already stopped")
    except PermissionError:
        log(f"WARNING: no permission to stop {name} pid {pid}")


def stop_processes() -> None:
    if not PID_FILE.is_file():
        log(f"No PID file at {PID_FILE} — nothing to stop.")
        return
    data = json.loads(PID_FILE.read_text(encoding="utf-8"))
    for name in ("frontend", "backend"):
        pid = int(data.get(name, 0) or 0)
        if pid:
            kill_pid(pid, name)
    PID_FILE.unlink(missing_ok=True)


def stop_containers() -> None:
    compose = docker_compose_base()
    if not compose:
        log("Docker not available — skipping container stop.")
        return
    log("Stopping Postgres and Redis containers...")
    proc = subprocess.run(
        compose + ["stop", "postgres", "redis"],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        log(proc.stderr or proc.stdout)
    else:
        log("Containers stopped.")


def main() -> None:
    log("=== MIDAS local stop ===")
    stop_processes()
    stop_containers()
    log("Done.")


if __name__ == "__main__":
    main()
