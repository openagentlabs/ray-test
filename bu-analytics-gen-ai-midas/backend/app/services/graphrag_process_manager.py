import os
import subprocess
from pathlib import Path
from threading import Lock
from typing import IO, List, Optional
from urllib.parse import urlparse

from app.core.logging_config import get_logger

logger = get_logger(__name__)


class GraphRAGProcessManager:
    """Keep the GraphRAG microservice running as a dedicated subprocess."""

    _PYTHON_CANDIDATES: List[str] = [
        r"C:\Users\saiyam268728\OneDrive - EXLService.com (I) Pvt. Ltd\Documents\MIDAS-Saiyam\KnowledgeRepo_To_KG\venv\Scripts\python.exe",
        r"C:\Python312\python.exe",
        r"C:\Users\{username}\AppData\Local\Programs\Python\Python312\python.exe",
        "python3.12",
        "python3.12.10",
    ]

    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._lock = Lock()
        self._port = int(os.getenv("GRAPHRAG_SERVICE_PORT", "8001"))
        self._service_url = os.getenv("GRAPHRAG_SERVICE_URL", "http://localhost:8001")
        self._autostart = self._resolve_autostart()
        self._work_dir = Path(__file__).resolve().parents[2]  # midas/backend
        self._start_script = self._work_dir / "graphrag_service" / "start_service.py"
        self._python_path = self._find_python_312()
        self._log_handle: Optional[IO[str]] = None

    def _resolve_autostart(self) -> bool:
        explicit = os.getenv("GRAPHRAG_AUTOSTART")
        if explicit is not None:
            return explicit.strip().lower() in {"1", "true", "yes", "on"}

        try:
            parsed = urlparse(self._service_url)
            host = (parsed.hostname or "").lower()
            return host in {"localhost", "127.0.0.1", "0.0.0.0"}
        except Exception:
            return True

    def _find_python_312(self) -> Optional[str]:
        env_path = os.getenv("GRAPHRAG_PYTHON_PATH")
        if env_path:
            if self._check_python_version(env_path):
                return env_path

        username = os.getenv("USERNAME", "")
        candidates = [path.format(username=username) for path in self._PYTHON_CANDIDATES]
        for candidate in candidates:
            if self._check_python_version(candidate):
                return candidate

        logger.warning("Python 3.12 interpreter not found; GraphRAG service cannot start.")
        return None

    def _check_python_version(self, path: str) -> bool:
        try:
            result = subprocess.run(
                [path, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            version_output = f"{result.stdout} {result.stderr}"
            return "3.12" in version_output
        except Exception:
            return False

    def _build_command(self) -> Optional[List[str]]:
        if not self._python_path or not self._start_script.exists():
            return None

        return [self._python_path, str(self._start_script)]

    def ensure_running(self) -> None:
        with self._lock:
            if not self._autostart:
                logger.debug(
                    "Skipping local GraphRAG autostart because GRAPHRAG_SERVICE_URL=%s and GRAPHRAG_AUTOSTART is disabled/implicit false.",
                    self._service_url,
                )
                return

            if self._process and self._process.poll() is None:
                logger.debug("GraphRAG service already running")
                return

            cmd = self._build_command()
            if not cmd:
                logger.error("Cannot start GraphRAG service because python 3.12 or start_service.py is missing.")
                return

            env = os.environ.copy()
            log_dir = self._work_dir / "logs"
            log_dir.mkdir(exist_ok=True)
            log_file = log_dir / "graphrag_service.log"

            if self._log_handle:
                try:
                    self._log_handle.close()
                except Exception:
                    pass

            logger.info(f"Starting GraphRAG service subprocess on port {self._port}")
            try:
                self._log_handle = open(log_file, "a", encoding="utf-8")
                self._process = subprocess.Popen(
                    cmd,
                    cwd=str(self._work_dir),
                    env=env,
                    stdout=self._log_handle,
                    stderr=subprocess.STDOUT,
                )
            except Exception as exc:
                logger.error(f"Failed to start GraphRAG subprocess: {exc}")
                self._process = None

    def shutdown(self) -> None:
        with self._lock:
            if not self._process:
                return

            logger.info("Stopping GraphRAG subprocess")
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("GraphRAG subprocess did not exit in time, killing it")
                self._process.kill()
            finally:
                self._process = None
                if self._log_handle:
                    try:
                        self._log_handle.close()
                    except Exception:
                        pass
                    finally:
                        self._log_handle = None


graphrag_process_manager = GraphRAGProcessManager()
