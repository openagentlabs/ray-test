"""HTTP client for the public Terraform Registry API."""

from __future__ import annotations

import json
from typing import Any

import httpx
from pydantic import ValidationError

from tf_tool.actions.registry_search.constants import DEFAULT_TIMEOUT_SECONDS, REGISTRY_API_BASE
from tf_tool.actions.registry_search.models import (
    RegistryErrorResponse,
    RegistryModuleSummary,
    RegistrySearchResponse,
)
from tf_tool.actions.registry_search.validation import ListRequest, SearchRequest
from tf_tool.core.errors import AppError, ErrorCodes
from tf_tool.core.results import Failure, Success
from tf_tool.core.types import TfResult


def _parse_registry_errors(payload: dict[str, Any]) -> str:
    try:
        parsed = RegistryErrorResponse.model_validate(payload)
    except ValidationError:
        return json.dumps(payload)
    return "; ".join(parsed.errors)


class RegistryClient:
    """Search and list modules on ``registry.terraform.io``."""

    def __init__(
        self,
        *,
        base_url: str = REGISTRY_API_BASE,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._client = client

    def _get(
        self,
        *,
        path: str,
        params: dict[str, str | int | bool],
        failure_message: str,
    ) -> TfResult[RegistrySearchResponse]:
        url = f"{self._base_url}{path}"
        try:
            if self._client is not None:
                response = self._client.get(url, params=params, timeout=self._timeout_seconds)
            else:
                with httpx.Client() as http_client:
                    response = http_client.get(url, params=params, timeout=self._timeout_seconds)
        except httpx.TimeoutException as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.HTTP,
                    message="Registry request timed out.",
                    detail=str(exc),
                ),
            )
        except httpx.HTTPError as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.HTTP,
                    message="Registry request failed.",
                    detail=str(exc),
                ),
            )

        if response.status_code >= 400:
            detail: str | None
            try:
                payload = response.json()
                if isinstance(payload, dict):
                    detail = _parse_registry_errors(payload)
                else:
                    detail = response.text
            except json.JSONDecodeError:
                detail = response.text
            return Failure(
                AppError(
                    code=ErrorCodes.REGISTRY,
                    message=f"{failure_message} (HTTP {response.status_code}).",
                    detail=detail,
                ),
            )

        try:
            payload = response.json()
            if not isinstance(payload, dict):
                msg = "Registry response was not a JSON object."
                raise TypeError(msg)
            return Success(RegistrySearchResponse.model_validate(payload))
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.REGISTRY,
                    message="Registry response failed schema validation.",
                    detail=str(exc),
                ),
            )

    def search(self, request: SearchRequest) -> TfResult[RegistrySearchResponse]:
        """Execute a keyword module search (``GET .../search``)."""
        params: dict[str, str | int | bool] = {
            "q": request.query,
            "limit": request.limit,
            "offset": request.offset,
        }
        if request.provider is not None:
            params["provider"] = request.provider
        if request.namespace is not None:
            params["namespace"] = request.namespace
        if request.verified is not None:
            params["verified"] = request.verified

        return self._get(
            path="/search",
            params=params,
            failure_message="Registry search failed",
        )

    def list_modules(self, request: ListRequest) -> TfResult[RegistrySearchResponse]:
        """List modules without a keyword (``GET ...`` or ``GET .../:namespace``)."""
        params: dict[str, str | int | bool] = {
            "limit": request.limit,
            "offset": request.offset,
        }
        if request.provider is not None:
            params["provider"] = request.provider
        if request.verified is not None:
            params["verified"] = request.verified

        path = f"/{request.namespace}" if request.namespace is not None else ""
        return self._get(
            path=path,
            params=params,
            failure_message="Registry list failed",
        )

    def resolve_download(self, module: RegistryModuleSummary) -> TfResult[str]:
        """Resolve the ``X-Terraform-Get`` source for a module version."""
        url = (
            f"{self._base_url}/{module.namespace}/{module.name}/"
            f"{module.provider}/{module.version}/download"
        )
        try:
            if self._client is not None:
                response = self._client.get(url, timeout=self._timeout_seconds)
            else:
                with httpx.Client() as http_client:
                    response = http_client.get(url, timeout=self._timeout_seconds)
        except httpx.TimeoutException as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.HTTP,
                    message="Registry download lookup timed out.",
                    detail=str(exc),
                ),
            )
        except httpx.HTTPError as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.HTTP,
                    message="Registry download lookup failed.",
                    detail=str(exc),
                ),
            )

        if response.status_code >= 400:
            detail: str | None
            try:
                payload = response.json()
                if isinstance(payload, dict):
                    detail = _parse_registry_errors(payload)
                else:
                    detail = response.text
            except json.JSONDecodeError:
                detail = response.text
            return Failure(
                AppError(
                    code=ErrorCodes.REGISTRY,
                    message=f"Registry download lookup failed (HTTP {response.status_code}).",
                    detail=detail,
                ),
            )

        terraform_get = response.headers.get("x-terraform-get")
        if terraform_get is None:
            return Failure(
                AppError(
                    code=ErrorCodes.REGISTRY,
                    message="Registry download response did not include X-Terraform-Get.",
                    detail=None,
                ),
            )
        return Success(terraform_get)


# Backward-compatible alias used by existing imports and tests.
RegistrySearchClient = RegistryClient
