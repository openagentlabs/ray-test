"""Typed HTTP client for MIDAS backend integration tests."""

from __future__ import annotations

import logging
from typing import Optional, Type, TypeVar

import httpx
from pydantic import BaseModel
from returns.result import Failure, Result, Success

from testing.api_client.auth_protocol import AuthHeaderProvider
from testing.api_client.config import MidasClientConfig
from testing.api_client.http_types import MultipartFile

logger = logging.getLogger("midas.integration.client")

TModel = TypeVar("TModel", bound=BaseModel)


class MidasHttpClient:
    """
    Synchronous HTTP client with injected auth headers.

    All fallible methods return ``Result[httpx.Response, Exception]``.
    Use ``request()`` for raw access or the typed helpers for common verbs.
    """

    def __init__(self, config: MidasClientConfig, auth: AuthHeaderProvider) -> None:
        self._config = config
        self._auth = auth
        base = str(config.base_url).rstrip("/")
        self._client = httpx.Client(
            base_url=base,
            timeout=config.timeout_seconds,
            verify=config.verify_tls,
            headers={"Accept": "application/json"},
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()

    def __enter__(self) -> MidasHttpClient:
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object],
    ) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _merge_headers(self, headers: Optional[dict[str, str]]) -> dict[str, str]:
        merged: dict[str, str] = {}
        merged.update(self._auth.request_headers())
        if headers:
            merged.update(headers)
        return merged

    def _effective_timeout(self, timeout: Optional[float]) -> float:
        return timeout if timeout is not None else self._config.timeout_seconds

    # ------------------------------------------------------------------
    # Low-level raw request (returns bare httpx.Response, may raise)
    # ------------------------------------------------------------------

    def request(
        self,
        method: str,
        path: str,
        *,
        headers: Optional[dict[str, str]] = None,
        json_body: Optional[object] = None,
        params: Optional[dict[str, str]] = None,
        content: Optional[bytes] = None,
        timeout: Optional[float] = None,
    ) -> httpx.Response:
        """Perform an HTTP request relative to base_url (may raise on transport error)."""
        hdrs = self._merge_headers(headers)
        t = self._effective_timeout(timeout)
        if json_body is not None:
            return self._client.request(
                method.upper(), path, headers=hdrs, json=json_body, params=params, timeout=t
            )
        if content is not None:
            return self._client.request(
                method.upper(), path, headers=hdrs, content=content, params=params, timeout=t
            )
        return self._client.request(method.upper(), path, headers=hdrs, params=params, timeout=t)

    # ------------------------------------------------------------------
    # Result-returning GET helpers
    # ------------------------------------------------------------------

    def get_raw(
        self,
        path: str,
        *,
        params: Optional[dict[str, str]] = None,
        headers: Optional[dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> Result[httpx.Response, Exception]:
        """GET path; return Success(response) or Failure(exception)."""
        try:
            resp = self.request("GET", path, headers=headers, params=params, timeout=timeout)
            return Success(resp)
        except Exception as exc:  # noqa: BLE001
            return Failure(exc)

    def get_json(
        self,
        path: str,
        *,
        headers: Optional[dict[str, str]] = None,
    ) -> object:
        """GET and parse JSON (kept for backwards compatibility; raises on error)."""
        import json

        r = self.request("GET", path, headers=headers)
        r.raise_for_status()
        return json.loads(r.text)

    def get_model(
        self,
        path: str,
        model: Type[TModel],
        *,
        headers: Optional[dict[str, str]] = None,
    ) -> TModel:
        """GET and validate against a Pydantic model (raises on error)."""
        data = self.get_json(path, headers=headers)
        if not isinstance(data, dict):
            raise TypeError(f"Expected JSON object for {path}, got {type(data).__name__}")
        return model.model_validate(data)

    def health_payload(self) -> dict[str, object]:
        """GET /health and return parsed JSON as a plain dict."""
        data = self.get_json("/health")
        if not isinstance(data, dict):
            raise TypeError("health endpoint must return a JSON object")
        return data

    # ------------------------------------------------------------------
    # Result-returning POST helpers
    # ------------------------------------------------------------------

    def post_json(
        self,
        path: str,
        body: dict[str, object],
        *,
        params: Optional[dict[str, str]] = None,
        headers: Optional[dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> Result[httpx.Response, Exception]:
        """POST JSON body; return Success(response) or Failure(exception)."""
        try:
            resp = self.request(
                "POST", path, headers=headers, json_body=body, params=params, timeout=timeout
            )
            return Success(resp)
        except Exception as exc:  # noqa: BLE001
            return Failure(exc)

    def post_form(
        self,
        path: str,
        data: dict[str, str],
        *,
        params: Optional[dict[str, str]] = None,
        headers: Optional[dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> Result[httpx.Response, Exception]:
        """POST application/x-www-form-urlencoded; return Success(response) or Failure."""
        try:
            hdrs = self._merge_headers(headers)
            t = self._effective_timeout(timeout)
            resp = self._client.post(path, data=data, headers=hdrs, params=params, timeout=t)
            return Success(resp)
        except Exception as exc:  # noqa: BLE001
            return Failure(exc)

    def post_multipart(
        self,
        path: str,
        *,
        fields: Optional[dict[str, str]] = None,
        files: Optional[list[MultipartFile]] = None,
        params: Optional[dict[str, str]] = None,
        headers: Optional[dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> Result[httpx.Response, Exception]:
        """POST multipart/form-data; return Success(response) or Failure."""
        try:
            hdrs = self._merge_headers(headers)
            t = self._effective_timeout(timeout)
            httpx_files = _build_httpx_files(files or [])
            resp = self._client.post(
                path,
                data=fields or {},
                files=httpx_files,
                headers=hdrs,
                params=params,
                timeout=t,
            )
            return Success(resp)
        except Exception as exc:  # noqa: BLE001
            return Failure(exc)

    # ------------------------------------------------------------------
    # Result-returning PATCH helper
    # ------------------------------------------------------------------

    def patch_bytes(
        self,
        path: str,
        content: bytes,
        content_range: str,
        *,
        headers: Optional[dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> Result[httpx.Response, Exception]:
        """PATCH with raw bytes and Content-Range header (chunked upload)."""
        try:
            extra = {"Content-Range": content_range, "Content-Type": "application/octet-stream"}
            if headers:
                extra.update(headers)
            resp = self.request("PATCH", path, headers=extra, content=content, timeout=timeout)
            return Success(resp)
        except Exception as exc:  # noqa: BLE001
            return Failure(exc)

    # ------------------------------------------------------------------
    # Streaming helper
    # ------------------------------------------------------------------

    def stream_lines(
        self,
        path: str,
        *,
        max_lines: Optional[int] = None,
        timeout: Optional[float] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> Result[list[str], Exception]:
        """GET a streaming endpoint and collect up to max_lines lines."""
        limit = max_lines if max_lines is not None else 5
        try:
            hdrs = self._merge_headers(headers)
            t = self._effective_timeout(timeout)
            lines: list[str] = []
            with self._client.stream("GET", path, headers=hdrs, timeout=t) as resp:
                for raw in resp.iter_lines():
                    lines.append(raw)
                    if len(lines) >= limit:
                        break
            return Success(lines)
        except Exception as exc:  # noqa: BLE001
            return Failure(exc)

    # ------------------------------------------------------------------
    # DELETE helper
    # ------------------------------------------------------------------

    def delete(
        self,
        path: str,
        *,
        params: Optional[dict[str, str]] = None,
        headers: Optional[dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> Result[httpx.Response, Exception]:
        """DELETE path; return Success(response) or Failure."""
        try:
            resp = self.request("DELETE", path, headers=headers, params=params, timeout=timeout)
            return Success(resp)
        except Exception as exc:  # noqa: BLE001
            return Failure(exc)

    # ------------------------------------------------------------------
    # PUT helper
    # ------------------------------------------------------------------

    def put_json(
        self,
        path: str,
        body: dict[str, object],
        *,
        params: Optional[dict[str, str]] = None,
        headers: Optional[dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> Result[httpx.Response, Exception]:
        """PUT JSON body; return Success(response) or Failure."""
        try:
            resp = self.request(
                "PUT", path, headers=headers, json_body=body, params=params, timeout=timeout
            )
            return Success(resp)
        except Exception as exc:  # noqa: BLE001
            return Failure(exc)


# ------------------------------------------------------------------
# Private helpers
# ------------------------------------------------------------------


def _build_httpx_files(
    files: list[MultipartFile],
) -> list[tuple[str, tuple[str, bytes, str]]]:
    """Convert MultipartFile list to httpx files= format."""
    return [
        ("file", (f.name, f.content, f.content_type))
        for f in files
    ]
