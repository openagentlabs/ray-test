"""Root AWS object managing registered accounts and connections."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from jp_tool.aws.aws_account import AwsAccount
from jp_tool.aws.connection_info import ConnectionInfo
from jp_tool.aws.connection_info_base import ConnectionInfoBase
from jp_tool.core.errors import AppError, ErrorCodes
from jp_tool.core.results import Failure, Success
from jp_tool.core.types import JpResult, UnitResult


class Aws:
    """Object-oriented AWS facade that tracks accounts and connections."""

    def __init__(self) -> None:
        self._accounts: dict[str, AwsAccount] = {}
        self._connections: dict[str, ConnectionInfoBase] = {}

    @property
    def accounts(self) -> Mapping[str, AwsAccount]:
        """Read-only view of registered accounts keyed by account id."""
        return MappingProxyType(self._accounts)

    @property
    def connections(self) -> Mapping[str, ConnectionInfoBase]:
        """Read-only view of registered connections keyed by connection key."""
        return MappingProxyType(self._connections)

    @classmethod
    def new(
        cls,
        *,
        account_id: str | None = None,
        profile: str | None = None,
        region: str | None = None,
    ) -> JpResult[Aws]:
        """Create an AWS object, optionally registering an account and connection."""
        aws = cls()

        if account_id is not None:
            account_result = aws._register_account(account_id)
            if isinstance(account_result, Failure):
                return account_result

        connection_result = aws._maybe_register_connection(profile, region)
        if isinstance(connection_result, Failure):
            return connection_result

        return Success(aws)

    def _maybe_register_connection(
        self,
        profile: str | None,
        region: str | None,
    ) -> UnitResult:
        """Register a connection when profile and region are supplied together."""
        if profile is None and region is None:
            return Success(None)

        if profile is None or region is None:
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="AWS profile and region must both be provided",
                    detail="pass profile and region together or omit both",
                ),
            )

        return self._register_connection(profile, region)

    def _register_account(self, account_id: str) -> UnitResult:
        """Ensure an account id is present in the registry, creating it when needed."""

        def _store(account: AwsAccount) -> UnitResult:
            if account.account_id in self._accounts:
                return Success(None)
            self._accounts[account.account_id] = account
            return Success(None)

        return AwsAccount.new(account_id).bind(_store)

    def _register_connection(self, profile: str, region: str) -> UnitResult:
        """Ensure a connection is present in the registry, creating it when needed."""

        def _store(connection: ConnectionInfo) -> UnitResult:
            if connection.connection_key in self._connections:
                return Success(None)
            self._connections[connection.connection_key] = connection
            return Success(None)

        return ConnectionInfo.new(profile, region).bind(_store)
