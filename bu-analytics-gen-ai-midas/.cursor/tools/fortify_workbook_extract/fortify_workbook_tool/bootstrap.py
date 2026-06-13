"""Resolve third-party dependencies via pip when imports fail (with user feedback)."""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path
from subprocess import CompletedProcess
from typing import TYPE_CHECKING, List, Tuple

if TYPE_CHECKING:
    from fortify_workbook_tool.feedback import ColoredFeedback

# Must succeed for CSV/JSON extraction paths.
_REQUIRED_MODULES = frozenset({"pypdf", "pydantic"})


class DependencyProvisioner:
    """
    Ensures packages from ``requirements-workbook-tools.txt`` are importable.

    **Required** (pypdf, pydantic): installed with pip retries (user site, then break-system-packages).
    **Optional** (PyYAML): best-effort — CSV/JSON work without it; YAML formatter needs it.
    """

    def __init__(self, requirements_path: Path | None = None) -> None:
        base = Path(__file__).resolve().parent.parent
        self._req_file = requirements_path or (base / "requirements-workbook-tools.txt")

    def ensure(self, feedback: "ColoredFeedback") -> None:
        required, optional = self._split_required_optional()
        if not required and not optional:
            feedback.warn(f"No dependency lines found in {self._req_file}")
            return

        n = len(required) + len(optional)
        feedback.step(f"Checking Python dependencies ({n} package(s))…")

        for pip_spec, import_name in required:
            self._ensure_one(pip_spec, import_name, feedback, mandatory=True)

        for pip_spec, import_name in optional:
            self._ensure_one(pip_spec, import_name, feedback, mandatory=False)

        feedback.ok("Dependency check complete.")

    def _ensure_one(
        self,
        pip_spec: str,
        import_name: str,
        feedback: "ColoredFeedback",
        *,
        mandatory: bool,
    ) -> None:
        try:
            importlib.import_module(import_name)
            feedback.dim(f"  {import_name}: OK")
            return
        except ImportError:
            pass

        feedback.warn(f"Missing `{import_name}` — installing `{pip_spec}`…")
        rc = self._pip_install_with_retries(pip_spec, feedback)
        if rc.returncode != 0:
            if mandatory:
                err_tail = (rc.stderr or rc.stdout or "").strip().splitlines()[-3:]
                detail = " ".join(err_tail) if err_tail else "pip failed"
                feedback.error(f"pip could not install required package {pip_spec}: {detail}")
                raise RuntimeError(f"Could not install {pip_spec}") from None
            feedback.warn(
                f"Optional package `{import_name}` not installed — use JSON/CSV, "
                f"or install PyYAML manually for YAML output."
            )
            return

        try:
            importlib.import_module(import_name)
        except ImportError as exc:
            if mandatory:
                feedback.error(f"Still cannot import `{import_name}` after install.")
                raise RuntimeError(f"Import failed for {import_name}") from exc
            feedback.warn(f"Optional `{import_name}` still unavailable after pip.")
            return

        feedback.ok(f"Installed and loaded `{import_name}`.")

    def _pip_install_with_retries(self, pip_spec: str, feedback: "ColoredFeedback") -> CompletedProcess[str]:
        attempts: Tuple[Tuple[str, dict[str, bool]], ...] = (
            ("default", {}),
            ("user site", {"user_site": True}),
            ("PEP 668 bypass", {"break_system": True}),
        )
        last: CompletedProcess[str] | None = None
        for label, kw in attempts:
            last = self._pip_install(pip_spec, **kw)
            if last.returncode == 0:
                return last
            if label != "PEP 668 bypass":
                feedback.dim(f"  pip retry ({label})…")
        assert last is not None
        return last

    def _split_required_optional(self) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
        entries = self._read_requirement_specs()
        req: List[Tuple[str, str]] = []
        opt: List[Tuple[str, str]] = []
        for item in entries:
            _, import_name = item
            if import_name in _REQUIRED_MODULES:
                req.append(item)
            else:
                opt.append(item)
        return req, opt

    def _read_requirement_specs(self) -> List[Tuple[str, str]]:
        if not self._req_file.is_file():
            return []

        result: List[Tuple[str, str]] = []
        for raw in self._req_file.read_text(encoding="utf-8").splitlines():
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            pip_spec = line
            base_pkg = line.split("==")[0].split(">=")[0].split("<")[0].strip()
            import_name = self._import_name_for_distribution(base_pkg)
            result.append((pip_spec, import_name))
        return result

    @staticmethod
    def _import_name_for_distribution(dist_name: str) -> str:
        key = dist_name.strip().lower().replace("_", "-")
        if key in ("pyyaml", "yaml"):
            return "yaml"
        if key == "pypdf":
            return "pypdf"
        if key == "pydantic":
            return "pydantic"
        return dist_name.replace("-", "_")

    @staticmethod
    def _pip_install(
        pip_spec: str,
        *,
        user_site: bool = False,
        break_system: bool = False,
    ) -> CompletedProcess[str]:
        cmd: List[str] = [sys.executable, "-m", "pip", "install", pip_spec]
        if user_site:
            cmd.append("--user")
        if break_system:
            cmd.append("--break-system-packages")
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
        )
