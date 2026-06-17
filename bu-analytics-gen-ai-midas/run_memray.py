#!/usr/bin/env python3
"""Start MIDAS locally: Docker Postgres/Redis, memray-instrumented backend, Vite frontend.

IMPORTANT: memray ``--live-remote`` does NOT start uvicorn until a client connects.
Run ``./venv/bin/python -m memray live <port>`` in another terminal right after this script.
Backend usually comes up within ~10s once the client is connected.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict

import run as base

BACKEND_DIR = base.BACKEND_DIR
LOG_DIR = base.LOG_DIR
PID_FILE = base.PID_FILE

MEMRAY_LIVE_PORT = int(os.environ.get("MIDAS_MEMRAY_PORT", "9999"))


def ensure_memray(python: Path) -> None:
    proc = subprocess.run(
        [str(python), "-m", "memray", "--version"],
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        base.log(f"memray: OK ({proc.stdout.strip()})")
        return
    base.log("Installing memray into backend venv...")
    base.run_cmd([str(python), "-m", "pip", "install", "memray"])


def memray_client_cmd() -> str:
    return f"cd {BACKEND_DIR} && ./venv/bin/python -m memray live {MEMRAY_LIVE_PORT}"


def start_backend_memray(python: Path) -> int:
    log_file = LOG_DIR / "backend.log"
    base.log(
        f"Starting memray wrapper on port {MEMRAY_LIVE_PORT} "
        f"(uvicorn starts AFTER memray client connects; logs: {log_file})..."
    )
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    with open(log_file, "a", encoding="utf-8") as fh:
        proc = subprocess.Popen(
            [
                str(python),
                "-u",
                "-m",
                "memray",
                "run",
                "--live-remote",
                "--live-port",
                str(MEMRAY_LIVE_PORT),
                "-m",
                "uvicorn",
                "main:app",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
            ],
            cwd=str(BACKEND_DIR),
            env=env,
            stdout=fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    return proc.pid


def main() -> None:
    base.log("=== MIDAS local run (memray backend) ===")
    base.ensure_dirs()
    if not base.shutil.which("docker"):
        base.fail("docker not found")

    password = base.ensure_root_env()
    base.ensure_app_env_files()
    base.ensure_psql_client()
    base.start_infra(password)
    base.wait_for_postgres_container()
    base.test_postgres(password)

    python = base.ensure_backend_venv()
    ensure_memray(python)
    base.ensure_frontend_deps()
    base.stop_existing_services()

    pids: Dict[str, int] = {}
    pids["backend"] = start_backend_memray(python)
    pids["memray_live_port"] = MEMRAY_LIVE_PORT
    time.sleep(1)
    pids["frontend"] = base.start_frontend()
    base.write_pids(pids)

    # Frontend only — backend stays down until memray live connects.
    base.wait_for_url("frontend", base.FRONTEND_URL, timeout_sec=60)

    base.log("")
    base.log("=== Started (backend waiting for memray client) ===")
    base.log(f"  Frontend:    {base.FRONTEND_URL}")
    base.log(f"  Backend:     {base.BACKEND_URL}  (not up until step 2 below)")
    base.log(f"  Memray port: {MEMRAY_LIVE_PORT}")
    base.log(f"  PIDs:        {PID_FILE}")
    base.log(f"  Logs:        {LOG_DIR}")
    base.log("")
    base.log("STEP 2 — run this in a separate terminal NOW:")
    base.log(f"  {memray_client_cmd()}")
    base.log("")
    base.log("Then check backend: curl http://localhost:8000/health")
    base.log("Stop with: python3 stop.py")


if __name__ == "__main__":
    main()
