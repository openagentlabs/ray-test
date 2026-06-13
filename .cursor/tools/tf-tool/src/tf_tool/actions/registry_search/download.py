"""Download Terraform Registry modules into the current working directory."""

from __future__ import annotations

import io
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import httpx

from tf_tool.actions.registry_search.client import RegistryClient
from tf_tool.actions.registry_search.constants import DEFAULT_TIMEOUT_SECONDS
from tf_tool.actions.registry_search.models import RegistryModuleSummary
from tf_tool.core.errors import AppError, ErrorCodes
from tf_tool.core.results import Failure, Success
from tf_tool.core.types import TextResult, TfResult

_GIT_GITHUB = re.compile(
    r"^git::https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/?]+)"
    r"(?:\.git)?(?:\?ref=(?P<ref>[^\s&]+))?$",
)


def _module_destination(module: RegistryModuleSummary, *, base_dir: Path) -> Path:
    return base_dir / f"{module.namespace}-{module.name}"


def _github_archive_url(owner: str, repo: str, ref: str) -> str:
    return f"https://github.com/{owner}/{repo}/archive/{ref}.zip"


def _extract_zip_to_directory(content: bytes, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            archive.extractall(tmp)

        children = [path for path in tmp.iterdir() if path.name != "__MACOSX"]
        source_root = children[0] if len(children) == 1 and children[0].is_dir() else tmp

        if destination.exists():
            shutil.rmtree(destination)

        if source_root == tmp:
            shutil.copytree(source_root, destination)
            return

        shutil.copytree(source_root, destination)


def _download_archive(
    url: str,
    *,
    timeout_seconds: float,
    http_client: httpx.Client | None = None,
) -> TfResult[bytes]:
    try:
        if http_client is not None:
            response = http_client.get(url, timeout=timeout_seconds)
        else:
            with httpx.Client(follow_redirects=True, timeout=timeout_seconds) as client:
                response = client.get(url)
    except httpx.TimeoutException as exc:
        return Failure(
            AppError(
                code=ErrorCodes.HTTP,
                message="Module download timed out.",
                detail=str(exc),
            ),
        )
    except httpx.HTTPError as exc:
        return Failure(
            AppError(
                code=ErrorCodes.HTTP,
                message="Module download failed.",
                detail=str(exc),
            ),
        )

    if response.status_code >= 400:
        return Failure(
            AppError(
                code=ErrorCodes.DOWNLOAD,
                message=f"Module download failed (HTTP {response.status_code}).",
                detail=response.text[:500] if response.text else None,
            ),
        )

    return Success(response.content)


def _download_from_terraform_get(
    terraform_get: str,
    *,
    destination: Path,
    timeout_seconds: float,
    http_client: httpx.Client | None = None,
) -> TextResult:
    github_match = _GIT_GITHUB.match(terraform_get)
    if github_match is not None:
        owner = github_match.group("owner")
        repo = github_match.group("repo")
        ref = github_match.group("ref")
        if ref is None:
            return Failure(
                AppError(
                    code=ErrorCodes.DOWNLOAD,
                    message="GitHub module source is missing a ref.",
                    detail=terraform_get,
                ),
            )
        archive_url = _github_archive_url(owner, repo, ref)
        downloaded = _download_archive(
            archive_url,
            timeout_seconds=timeout_seconds,
            http_client=http_client,
        )
        if isinstance(downloaded, Failure):
            return downloaded
        try:
            _extract_zip_to_directory(downloaded.unwrap(), destination)
        except (OSError, zipfile.BadZipFile) as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.DOWNLOAD,
                    message="Failed to extract downloaded module archive.",
                    detail=str(exc),
                ),
            )
        return Success(str(destination.resolve()))

    if terraform_get.startswith(("http://", "https://")):
        downloaded = _download_archive(terraform_get, timeout_seconds=timeout_seconds)
        if isinstance(downloaded, Failure):
            return downloaded
        content = downloaded.unwrap()
        suffix = Path(urlparse(terraform_get).path).suffix.lower()
        if suffix == ".zip":
            try:
                _extract_zip_to_directory(content, destination)
            except (OSError, zipfile.BadZipFile) as exc:
                return Failure(
                    AppError(
                        code=ErrorCodes.DOWNLOAD,
                        message="Failed to extract downloaded module archive.",
                        detail=str(exc),
                    ),
                )
            return Success(str(destination.resolve()))

        destination.mkdir(parents=True, exist_ok=True)
        target_file = destination / Path(urlparse(terraform_get).path).name
        target_file.write_bytes(content)
        return Success(str(target_file.resolve()))

    return Failure(
        AppError(
            code=ErrorCodes.DOWNLOAD,
            message="Unsupported Terraform module source.",
            detail=terraform_get,
        ),
    )


def download_registry_module(
    module: RegistryModuleSummary,
    *,
    destination_dir: Path | None = None,
    client: RegistryClient | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> TextResult:
    """Resolve and download one registry module into the working directory."""
    registry_client = client or RegistryClient(timeout_seconds=timeout_seconds)
    resolved = registry_client.resolve_download(module)
    if isinstance(resolved, Failure):
        return resolved

    base_dir = destination_dir or Path.cwd()
    destination = _module_destination(module, base_dir=base_dir)
    http_client = client._client if client is not None else None
    return _download_from_terraform_get(
        resolved.unwrap(),
        destination=destination,
        timeout_seconds=timeout_seconds,
        http_client=http_client,
    )
