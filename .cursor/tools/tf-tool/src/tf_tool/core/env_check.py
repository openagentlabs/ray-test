"""Runtime Python and dependency validation for tf-tool."""

from __future__ import annotations

import importlib
import importlib.metadata
import sys
import tomllib
from pathlib import Path
from typing import Final

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version
from pydantic import BaseModel, ConfigDict, Field
from returns.result import Failure, Success

from tf_tool.build.gate import find_project_root
from tf_tool.core.errors import AppError, ErrorCodes
from tf_tool.core.types import TfResult

_SKIP_ENV: Final[str] = "TF_TOOL_SKIP_ENV_CHECK"

# PyPI distribution name → importable module used for a secondary import probe.
_IMPORT_MODULES: Final[dict[str, str]] = {
    "httpx": "httpx",
    "pydantic": "pydantic",
    "returns": "returns",
    "rich": "rich",
    "typer": "typer",
}

# Fallback when neither pyproject nor wheel metadata is readable.
_FALLBACK_PYTHON: Final[str] = ">=3.12"
_FALLBACK_REQUIREMENTS: Final[tuple[str, ...]] = (
    "httpx>=0.28",
    "pydantic>=2.10",
    "returns>=0.23",
    "rich>=13.7",
    "typer>=0.15",
)


class PythonCheckResult(BaseModel):
    """Python interpreter vs declared requires-python."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    required: str
    current: str
    ok: bool


class DependencyCheckResult(BaseModel):
    """Single runtime dependency check."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    required: str
    installed: str | None = None
    import_ok: bool = False
    ok: bool
    detail: str | None = None


class EnvCheckReport(BaseModel):
    """Full environment validation report."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    python: PythonCheckResult
    dependencies: list[DependencyCheckResult] = Field(default_factory=list)
    source: str = Field(..., min_length=1)
    ok: bool

    def failure_messages(self) -> list[str]:
        lines: list[str] = []
        if not self.python.ok:
            lines.append(
                f"Python {self.python.current} does not satisfy requires-python "
                f"({self.python.required}).",
            )
        for dep in self.dependencies:
            if dep.ok:
                continue
            if dep.installed is None:
                lines.append(f"Missing dependency {dep.name} ({dep.required}).")
            else:
                lines.append(
                    f"Dependency {dep.name}: installed {dep.installed} "
                    f"does not satisfy {dep.required}.",
                )
            if dep.detail:
                lines.append(f"  {dep.detail}")
        return lines


def _current_python_version() -> str:
    return ".".join(str(part) for part in sys.version_info[:3])


def _python_ok(required_spec: str) -> bool:
    spec = SpecifierSet(required_spec)
    return spec.contains(_current_python_version(), prereleases=True)


def _read_pyproject_requirements(manifest: Path) -> tuple[str, list[Requirement]] | None:
    try:
        data = tomllib.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    project = data.get("project")
    if not isinstance(project, dict):
        return None
    python_req = project.get("requires-python")
    if not isinstance(python_req, str) or not python_req.strip():
        python_req = _FALLBACK_PYTHON
    raw_deps = project.get("dependencies")
    if not isinstance(raw_deps, list):
        return None
    requirements: list[Requirement] = []
    for item in raw_deps:
        if isinstance(item, str) and item.strip():
            requirements.append(Requirement(item.strip()))
    if not requirements:
        return None
    return python_req.strip(), requirements


def _read_wheel_requirements() -> tuple[str, list[Requirement]] | None:
    try:
        dist = importlib.metadata.metadata("tf-tool")
    except importlib.metadata.PackageNotFoundError:
        return None
    python_req = dist.get("Requires-Python") or _FALLBACK_PYTHON
    requirements: list[Requirement] = []
    for item in dist.get_all("Requires-Dist") or ():
        if not isinstance(item, str) or not item.strip():
            continue
        base = item.split(";", 1)[0].strip()
        if base:
            requirements.append(Requirement(base))
    if not requirements:
        return None
    return python_req.strip(), requirements


def _load_requirements() -> tuple[str, list[Requirement], str]:
    root = find_project_root()
    if root is not None:
        from_pyproject = _read_pyproject_requirements(root / "pyproject.toml")
        if from_pyproject is not None:
            python_req, reqs = from_pyproject
            return python_req, reqs, f"pyproject.toml ({root})"

    from_wheel = _read_wheel_requirements()
    if from_wheel is not None:
        python_req, reqs = from_wheel
        return python_req, reqs, "installed package metadata (tf-tool)"

    return (
        _FALLBACK_PYTHON,
        [Requirement(item) for item in _FALLBACK_REQUIREMENTS],
        "embedded fallback requirements",
    )


def _installed_version(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def _import_probe(distribution: str) -> tuple[bool, str | None]:
    module_name = _IMPORT_MODULES.get(distribution, distribution.replace("-", "_"))
    try:
        importlib.import_module(module_name)
    except ImportError as exc:
        return False, f"import {module_name} failed: {exc}"
    return True, None


def _dependency_satisfied(requirement: Requirement, installed: str) -> bool:
    try:
        version = Version(installed)
    except ValueError:
        return False
    if not requirement.specifier:
        return True
    return requirement.specifier.contains(version, prereleases=True)


def _check_dependency(requirement: Requirement) -> DependencyCheckResult:
    required = str(requirement)
    name = requirement.name
    installed = _installed_version(name)
    import_ok, import_detail = _import_probe(name)

    if installed is None:
        return DependencyCheckResult(
            name=name,
            required=required,
            installed=None,
            import_ok=import_ok,
            ok=False,
            detail=import_detail or "distribution not found in active environment",
        )

    version_ok = _dependency_satisfied(requirement, installed)
    ok = version_ok and import_ok
    detail: str | None = None
    if not version_ok:
        detail = f"installed {installed} outside required specifier"
    elif not import_ok:
        detail = import_detail

    return DependencyCheckResult(
        name=name,
        required=required,
        installed=installed,
        import_ok=import_ok,
        ok=ok,
        detail=detail,
    )


def run_env_check() -> TfResult[EnvCheckReport]:
    """Validate active Python and runtime dependencies against declared requirements."""
    import os

    if os.environ.get(_SKIP_ENV) == "1":
        report = EnvCheckReport(
            python=PythonCheckResult(
                required="(skipped)",
                current=_current_python_version(),
                ok=True,
            ),
            dependencies=[],
            source="TF_TOOL_SKIP_ENV_CHECK=1",
            ok=True,
        )
        return Success(report)

    python_required, requirements, source = _load_requirements()
    python_result = PythonCheckResult(
        required=python_required,
        current=_current_python_version(),
        ok=_python_ok(python_required),
    )
    dependency_results = [_check_dependency(req) for req in requirements]
    ok = python_result.ok and all(dep.ok for dep in dependency_results)
    report = EnvCheckReport(
        python=python_result,
        dependencies=dependency_results,
        source=source,
        ok=ok,
    )
    if ok:
        return Success(report)
    detail = "\n".join(report.failure_messages())
    return Failure(
        AppError(
            code=ErrorCodes.ENVIRONMENT,
            message="Runtime environment check failed.",
            detail=detail,
        ),
    )


def report_to_json(report: EnvCheckReport) -> str:
    """Serialize an environment report for CLI output."""
    return report.model_dump_json(indent=2)
