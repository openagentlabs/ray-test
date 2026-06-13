"""Service config and runtime environment RPC handlers."""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime

from pod_manager.v1 import pool_pb2

from solutions_service.core.app_config import AppConfig
from solutions_service.core.errors import AppError, ErrorCodes
from solutions_service.core.results import Failure, Result, Success
from solutions_service.database.models.service_config_records import ServiceConfigRecord
from solutions_service.database.repositories.service_config_repository import ServiceConfigRepository
_SECRET_PATTERN = re.compile(r"(key|secret|password|token|credential)", re.IGNORECASE)
_REDACTED = "***REDACTED***"


class ConfigRpcHandler:
    """Operator config CRUD and runtime env introspection."""

    __slots__ = ("_app_config", "_repo")

    def __init__(
        self,
        *,
        app_config: AppConfig,
        service_config_repository: ServiceConfigRepository,
    ) -> None:
        self._app_config = app_config
        self._repo = service_config_repository

    async def get_runtime_environment(
        self,
    ) -> Result[pool_pb2.GetRuntimeEnvironmentResponse, AppError]:
        entries = [
            pool_pb2.ConfigEntry(key=key, value=_redact_if_secret(key, value))
            for key, value in sorted(os.environ.items())
            if key.startswith("POD_MANAGER_") or key.startswith("SOLUTIONS_") or key.startswith("AWS_")
        ]
        return Success(pool_pb2.GetRuntimeEnvironmentResponse(entries=entries))

    async def list_service_config(
        self,
    ) -> Result[pool_pb2.ListServiceConfigResponse, AppError]:
        listed = await self._repo.scan_all()
        if isinstance(listed, Failure):
            return listed
        entries = [_to_proto_entry(r) for r in listed.unwrap()]
        return Success(pool_pb2.ListServiceConfigResponse(entries=entries))

    async def get_service_config(
        self,
        *,
        config_key: str,
    ) -> Result[pool_pb2.ServiceConfigEntry, AppError]:
        key = config_key.strip()
        if not key:
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="config_key is required.",
                    detail=None,
                ),
            )
        got = await self._repo.get(config_key=key)
        if isinstance(got, Failure):
            return got
        rec = got.unwrap()
        if rec is None:
            return Failure(
                AppError(
                    code=ErrorCodes.NOT_FOUND,
                    message=f"Config key not found: {key}",
                    detail=None,
                ),
            )
        return Success(_to_proto_entry(rec))

    async def put_service_config(
        self,
        *,
        config_key: str,
        value: str,
        description: str,
    ) -> Result[pool_pb2.ServiceConfigEntry, AppError]:
        key = config_key.strip()
        if not key:
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="config_key is required.",
                    detail=None,
                ),
            )
        now = datetime.now(tz=UTC).isoformat()
        record = ServiceConfigRecord(
            config_key=key,
            value=value,
            updated_at=now,
            description=description,
        )
        put = await self._repo.put(record)
        if isinstance(put, Failure):
            return put
        return Success(_to_proto_entry(record))

    async def delete_service_config(
        self,
        *,
        config_key: str,
    ) -> Result[pool_pb2.DeleteServiceConfigResponse, AppError]:
        key = config_key.strip()
        if not key:
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="config_key is required.",
                    detail=None,
                ),
            )
        deleted = await self._repo.delete(config_key=key)
        if isinstance(deleted, Failure):
            return deleted
        return Success(pool_pb2.DeleteServiceConfigResponse())


def _to_proto_entry(rec: ServiceConfigRecord) -> pool_pb2.ServiceConfigEntry:
    return pool_pb2.ServiceConfigEntry(
        config_key=rec.config_key,
        value=rec.value,
        updated_at=rec.updated_at,
        description=rec.description,
    )


def _redact_if_secret(key: str, value: str) -> str:
    if _SECRET_PATTERN.search(key):
        return _REDACTED
    return value
