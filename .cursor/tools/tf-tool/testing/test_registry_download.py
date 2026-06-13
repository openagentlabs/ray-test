"""Unit tests for registry module download."""

from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

import httpx
from returns.result import Success

from tf_tool.actions.registry_search.client import RegistryClient
from tf_tool.actions.registry_search.download import download_registry_module
from tf_tool.actions.registry_search.models import RegistryModuleSummary

_MODULE = RegistryModuleSummary(
    id="terraform-aws-modules/vpc/aws/6.6.1",
    namespace="terraform-aws-modules",
    name="vpc",
    version="6.6.1",
    provider="aws",
    description="VPC module",
    source="https://github.com/terraform-aws-modules/terraform-aws-vpc",
    published_at=datetime(2026, 4, 2, 20, 22, 11, tzinfo=UTC),
    downloads=1,
)


def _zip_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("terraform-aws-vpc-abc/main.tf", 'resource "null_resource" "x" {}')
        archive.writestr("terraform-aws-vpc-abc/README.md", "test")
    return buffer.getvalue()


def _mock_response(
    *,
    status_code: int,
    headers: dict[str, str] | None = None,
    content: bytes = b"",
) -> Mock:
    response = Mock(spec=httpx.Response)
    response.status_code = status_code
    response.headers = headers or {}
    response.text = ""
    response.content = content
    return response


def test_download_registry_module_from_github_archive(tmp_path: Path) -> None:
    http_client = Mock(spec=httpx.Client)
    http_client.get.side_effect = [
        _mock_response(
            status_code=204,
            headers={
                "x-terraform-get": (
                    "git::https://github.com/terraform-aws-modules/terraform-aws-vpc?ref=abc123"
                ),
            },
        ),
        _mock_response(status_code=200, content=_zip_bytes()),
    ]

    client = RegistryClient(client=http_client)
    result = download_registry_module(_MODULE, destination_dir=tmp_path, client=client)

    assert isinstance(result, Success)
    destination = Path(result.unwrap())
    assert destination.is_dir()
    assert (destination / "main.tf").is_file()
    assert http_client.get.call_args_list[1].args[0].endswith("/archive/abc123.zip")
