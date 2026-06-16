#!/usr/bin/env python3
"""Start MIDAS locally: Docker Postgres/Redis, FastAPI backend, Vite frontend."""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
STATE_DIR = ROOT / "runb-local" / "state"
LOG_DIR = ROOT / "runb-local" / "logs"
PID_FILE = STATE_DIR / "pids.json"

POSTGRES_USER = "midas_pg"
POSTGRES_DB = "midas_dev"
POSTGRES_HOST = "localhost"
POSTGRES_PORT = 5433
DEFAULT_POSTGRES_PASSWORD = "midas_local"

BACKEND_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:5173"
HEALTH_PATH = "/health"


def log(msg: str) -> None:
    print(msg, flush=True)


def fail(msg: str) -> None:
    log(f"ERROR: {msg}")
    sys.exit(1)


def run_cmd(
    cmd: List[str],
    *,
    cwd: Optional[Path] = None,
    env: Optional[Dict[str, str]] = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
    log(f"  $ {' '.join(cmd)}")
    return subprocess.run(
        cmd,
        cwd=str(cwd or ROOT),
        env=env,
        check=check,
        text=True,
        capture_output=True,
    )


def ensure_dirs() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def read_root_env() -> Dict[str, str]:
    env_path = ROOT / ".env"
    values: Dict[str, str] = {}
    if not env_path.is_file():
        return values
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        values[key.strip()] = val.strip()
    return values


def ensure_root_env() -> str:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        env_path.write_text(
            f"POSTGRES_PASSWORD={DEFAULT_POSTGRES_PASSWORD}\n",
            encoding="utf-8",
        )
        log(f"Created {env_path} with default POSTGRES_PASSWORD.")
    values = read_root_env()
    password = values.get("POSTGRES_PASSWORD", DEFAULT_POSTGRES_PASSWORD)
    if not password:
        fail("POSTGRES_PASSWORD is empty in .env")
    return password


def ensure_psql_client() -> None:
    if shutil.which("psql"):
        log("psql client: OK")
        return
    log("psql not found — installing postgresql-client (requires apt)...")
    if not shutil.which("apt-get"):
        fail("psql missing and apt-get not available; install postgresql-client manually.")
    run_cmd(["sudo", "apt-get", "update", "-qq"])
    run_cmd(["sudo", "apt-get", "install", "-y", "postgresql-client"])
    if not shutil.which("psql"):
        fail("postgresql-client install did not provide psql.")


def docker_compose_base() -> List[str]:
    if shutil.which("docker"):
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
    fail("docker compose / docker-compose not found.")


def start_infra(password: str) -> None:
    compose = docker_compose_base()
    env = os.environ.copy()
    env["POSTGRES_PASSWORD"] = password
    log("Starting Postgres and Redis containers...")
    proc = subprocess.run(
        compose + ["up", "-d", "postgres", "redis"],
        cwd=str(ROOT),
        env=env,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        log(proc.stdout)
        log(proc.stderr)
        fail("docker compose up postgres redis failed.")


def wait_for_postgres_container(timeout_sec: int = 90) -> None:
    compose = docker_compose_base()
    log("Waiting for Postgres container health...")
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        proc = subprocess.run(
            compose + ["ps", "--format", "json", "postgres"],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
        )
        if "healthy" in proc.stdout.lower():
            log("Postgres container: healthy")
            return
        time.sleep(2)
    fail("Postgres container did not become healthy within timeout.")


def postgres_dsn(password: str) -> str:
    return (
        f"postgresql://{POSTGRES_USER}:{password}@"
        f"{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )


def test_postgres(password: str) -> None:
    dsn = postgres_dsn(password)
    log("Testing Postgres with psql...")
    proc = subprocess.run(
        [
            "psql",
            dsn,
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            "SELECT 1 AS midas_local_ok;",
        ],
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        log(proc.stdout)
        log(proc.stderr)
        fail("Postgres connection test failed.")
    log("Postgres connection test: OK")


def find_backend_python() -> str:
    """Prefer Python 3.12+ for backend (matches Docker / GraphRAG tooling)."""
    candidates = [
        os.environ.get("MIDAS_PYTHON", "").strip(),
        shutil.which("python3.12") or "",
        shutil.which("python3.13") or "",
        sys.executable,
        shutil.which("python3") or "",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            proc = subprocess.run(
                [candidate, "-c", "import sys; assert sys.version_info >= (3, 12)"],
                capture_output=True,
                text=True,
            )
            if proc.returncode == 0:
                log(f"Backend Python: {candidate}")
                return candidate
        except OSError:
            continue
    fail("Python 3.12+ required for backend venv (install python3.12).")


def ensure_backend_venv() -> Path:
    venv_dir = BACKEND_DIR / "venv"
    py = venv_dir / "bin" / "python"
    if py.is_file():
        try:
            subprocess.run([str(py), "-c", "import sys; assert sys.version_info >= (3, 12)"], check=True)
        except (subprocess.CalledProcessError, OSError):
            log("Removing incompatible backend venv...")
            shutil.rmtree(venv_dir, ignore_errors=True)
            py = venv_dir / "bin" / "python"
    if not py.is_file():
        base_python = find_backend_python()
        log("Creating backend virtualenv...")
        run_cmd([base_python, "-m", "venv", str(venv_dir)])
    req = BACKEND_DIR / "requirements.txt"
    marker = venv_dir / ".midas_deps_installed"
    if not marker.is_file():
        log("Installing backend dependencies (first run may take several minutes)...")
        run_cmd([str(py), "-m", "pip", "install", "--upgrade", "pip"])
        run_cmd([str(py), "-m", "pip", "install", "-r", str(req)])
        marker.touch()
    return py


def ensure_frontend_deps() -> None:
    if (FRONTEND_DIR / "node_modules").is_dir():
        log("frontend node_modules: OK")
        return
    log("Installing frontend npm dependencies...")
    npm = shutil.which("npm") or fail("npm not found")
    proc = subprocess.run(
        [npm, "install"],
        cwd=str(FRONTEND_DIR),
        text=True,
    )
    if proc.returncode != 0:
        fail("npm install failed in frontend/")


def ensure_app_env_files() -> None:
    backend_env = BACKEND_DIR / ".env"
    frontend_env = FRONTEND_DIR / ".env"
    if not backend_env.is_file():
        fail(f"Missing {backend_env} — copy from runb-local guide or rerun setup.")
    if not frontend_env.is_file():
        fail(f"Missing {frontend_env} — copy from runb-local guide or rerun setup.")
    log(f"backend/.env: OK ({backend_env})")
    log(f"frontend/.env: OK ({frontend_env})")


def http_ok(url: str, timeout: float = 3.0) -> Tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read(500).decode("utf-8", errors="replace")
            return resp.status == 200, body
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:
        return False, str(exc)


def wait_for_url(name: str, url: str, timeout_sec: int = 120) -> None:
    log(f"Waiting for {name} at {url}...")
    deadline = time.time() + timeout_sec
    last_err = ""
    while time.time() < deadline:
        ok, detail = http_ok(url)
        if ok:
            log(f"{name}: OK")
            return
        last_err = detail
        time.sleep(2)
    fail(f"{name} did not respond at {url} (last error: {last_err})")


def write_pids(pids: Dict[str, int]) -> None:
    PID_FILE.write_text(json.dumps(pids, indent=2) + "\n", encoding="utf-8")


def kill_pid(pid: int, name: str) -> None:
    """Stop a process (and its session group when possible)."""
    if pid <= 0:
        return
    try:
        try:
            pgid = os.getpgid(pid)
            os.killpg(pgid, signal.SIGTERM)
            log(f"Sent SIGTERM to {name} process group (pid {pid}, pgid {pgid})")
        except OSError:
            os.kill(pid, signal.SIGTERM)
            log(f"Sent SIGTERM to {name} (pid {pid})")
        for _ in range(15):
            try:
                os.kill(pid, 0)
                time.sleep(0.5)
            except OSError:
                log(f"{name} stopped")
                return
        try:
            pgid = os.getpgid(pid)
            os.killpg(pgid, signal.SIGKILL)
        except OSError:
            os.kill(pid, signal.SIGKILL)
        log(f"Sent SIGKILL to {name} (pid {pid})")
    except ProcessLookupError:
        log(f"{name} (pid {pid}) already stopped")
    except PermissionError:
        log(f"WARNING: no permission to stop {name} pid {pid}")


def pids_listening_on_port(port: int) -> Set[int]:
    """Return PIDs listening on a TCP port (Linux: ss, fallback fuser)."""
    found: Set[int] = set()
    if shutil.which("ss"):
        proc = subprocess.run(
            ["ss", "-tlnp", f"sport = :{port}"],
            capture_output=True,
            text=True,
        )
        for match in re.finditer(r"pid=(\d+)", proc.stdout):
            found.add(int(match.group(1)))
    if not found and shutil.which("fuser"):
        proc = subprocess.run(
            ["fuser", "-n", "tcp", str(port)],
            capture_output=True,
            text=True,
        )
        line = (proc.stdout or proc.stderr).strip()
        if ":" in line:
            for token in line.split(":", 1)[1].split():
                if token.isdigit():
                    found.add(int(token))
    return found


def port_in_use(port: int) -> bool:
    return bool(pids_listening_on_port(port))


def wait_for_port_free(port: int, timeout_sec: float = 10.0) -> None:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if not port_in_use(port):
            return
        time.sleep(0.5)
    pids = sorted(pids_listening_on_port(port))
    fail(f"Port {port} still in use (pids: {pids or 'unknown'})")


def stop_existing_services() -> None:
    """Stop prior backend/frontend from PID file and anything on dev ports."""
    log("Stopping any existing backend/frontend processes...")
    if PID_FILE.is_file():
        try:
            data = json.loads(PID_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
        for name in ("frontend", "backend"):
            pid = int(data.get(name, 0) or 0)
            if pid:
                kill_pid(pid, name)
        PID_FILE.unlink(missing_ok=True)

    for port, label in ((8000, "backend"), (5173, "frontend")):
        for pid in sorted(pids_listening_on_port(port)):
            kill_pid(pid, f"{label} (port {port})")

    for port in (8000, 5173):
        wait_for_port_free(port)
    log("Ports 8000 and 5173 are free")


def start_backend(python: Path) -> int:
    log_file = LOG_DIR / "backend.log"
    log(f"Starting backend (logs: {log_file})...")
    with open(log_file, "a", encoding="utf-8") as fh:
        proc = subprocess.Popen(
            [
                str(python),
                "-m",
                "uvicorn",
                "main:app",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
                "--reload",
            ],
            cwd=str(BACKEND_DIR),
            stdout=fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    return proc.pid


def start_frontend() -> int:
    log_file = LOG_DIR / "frontend.log"
    npm = shutil.which("npm")
    if not npm:
        fail("npm not found")
    log(f"Starting frontend (logs: {log_file})...")
    with open(log_file, "a", encoding="utf-8") as fh:
        proc = subprocess.Popen(
            [npm, "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"],
            cwd=str(FRONTEND_DIR),
            stdout=fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    return proc.pid


def validate_stack() -> None:
    backend_health = f"{BACKEND_URL}{HEALTH_PATH}"
    ok, body = http_ok(backend_health)
    if not ok:
        fail(f"Backend health check failed: {body}")
    log(f"Backend health: {body[:200]}")

    ok, _ = http_ok(FRONTEND_URL)
    if not ok:
        # Vite may return 200 or 304; also try index path
        ok, detail = http_ok(f"{FRONTEND_URL}/")
        if not ok:
            fail(f"Frontend check failed: {detail}")
    log("Frontend dev server: OK")


def main() -> None:
    log("=== MIDAS local run ===")
    ensure_dirs()
    if not shutil.which("docker"):
        fail("docker not found")

    password = ensure_root_env()
    ensure_app_env_files()
    ensure_psql_client()
    start_infra(password)
    wait_for_postgres_container()
    test_postgres(password)

    python = ensure_backend_venv()
    ensure_frontend_deps()
    stop_existing_services()

    pids: Dict[str, int] = {}
    pids["backend"] = start_backend(python)
    time.sleep(2)
    pids["frontend"] = start_frontend()
    write_pids(pids)

    wait_for_url("backend", f"{BACKEND_URL}{HEALTH_PATH}", timeout_sec=180)
    wait_for_url("frontend", FRONTEND_URL, timeout_sec=120)
    validate_stack()

    log("")
    log("=== All services running ===")
    log(f"  Frontend:  {FRONTEND_URL}")
    log(f"  Backend:   {BACKEND_URL}")
    log(f"  API docs:  {BACKEND_URL}/docs")
    log(f"  Postgres:  {POSTGRES_HOST}:{POSTGRES_PORT} (user={POSTGRES_USER}, db={POSTGRES_DB})")
    log(f"  PIDs:      {PID_FILE}")
    log(f"  Logs:      {LOG_DIR}")
    log("Stop with: python3 stop.py")


if __name__ == "__main__":
    main()
