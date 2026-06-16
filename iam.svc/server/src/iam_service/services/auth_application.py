"""Auth orchestration: IdP login, token issuance, refresh, and permission resolution."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta

from iam_service.auth.permissions_codec import (
    PermissionGrantSet,
    ServicePermissionGrant,
)
from iam_service.auth.token_models import AuthTokenClaims, IssuedAuthToken, JwksDocument
from iam_service.auth.token_service import REFRESH_TOKEN_TTL_SECONDS, AuthTokenService
from iam_service.core.errors import AppError, ErrorCodes
from iam_service.core.results import Failure, Result, Success
from iam_service.database.models.records import (
    AuthSessionRecord,
    UserRecord,
)
from iam_service.database.repositories.auth_permission_repository import (
    ServiceFunctionRegistryRepository,
    UserPermissionRepository,
)
from iam_service.database.repositories.auth_session_repository import AuthSessionRepository
from iam_service.database.repositories.user_repository import UserRepository
from iam_service.grpc_transport.proto_time import utc_now_iso_z
from iam_service.plugins.idp.interface import IdentityProviderDriver
from iam_service.plugins.idp.types import IdpAuthResult, IdpCredentialRequest


class AuthApplication:
    """Central auth service coordinating IdP, permissions, and signed tokens."""

    __slots__ = (
        "_idp",
        "_token_service",
        "_users",
        "_user_permissions",
        "_service_registry",
        "_auth_sessions",
    )

    def __init__(
        self,
        *,
        idp: IdentityProviderDriver,
        token_service: AuthTokenService,
        users: UserRepository,
        user_permissions: UserPermissionRepository,
        service_registry: ServiceFunctionRegistryRepository,
        auth_sessions: AuthSessionRepository,
    ) -> None:
        self._idp = idp
        self._token_service = token_service
        self._users = users
        self._user_permissions = user_permissions
        self._service_registry = service_registry
        self._auth_sessions = auth_sessions

    async def get_jwks(self) -> Result[JwksDocument, AppError]:
        return await self._token_service.build_jwks()

    async def validate_access_token(self, token: str) -> Result[AuthTokenClaims, AppError]:
        return await self._token_service.validate_token(token, allow_refresh=False)

    async def login_with_password(
        self,
        *,
        email: str,
        password: str,
    ) -> Result[IssuedAuthToken, AppError]:
        idp_result = await self._idp.authenticate_credentials(
            IdpCredentialRequest(username=email, password=password),
        )
        if isinstance(idp_result, Failure):
            return idp_result
        identity = idp_result.unwrap()
        user = await self._resolve_or_create_user(identity)
        if isinstance(user, Failure):
            return user
        grants = await self._build_grants_for_user(user.unwrap().id)
        if isinstance(grants, Failure):
            return grants
        session_id = str(uuid.uuid4())
        issued = await self._token_service.issue_tokens(
            user_id=user.unwrap().id,
            grants=grants.unwrap(),
            session_id=session_id,
        )
        if isinstance(issued, Failure):
            return issued
        tokens = issued.unwrap()
        persisted = await self._persist_session(
            session_id=session_id,
            user_id=user.unwrap().id,
            identity=identity,
            refresh_token=tokens.refresh_token,
        )
        if isinstance(persisted, Failure):
            return persisted
        return Success(tokens)

    async def refresh_tokens(self, refresh_token: str) -> Result[IssuedAuthToken, AppError]:
        claims_result = await self._token_service.validate_token(
            refresh_token,
            allow_refresh=True,
        )
        if isinstance(claims_result, Failure):
            return claims_result
        claims = claims_result.unwrap()
        session = await self._auth_sessions.get_by_id(claims.jti)
        if isinstance(session, Failure):
            return session
        if session.unwrap() is None:
            return Failure(
                AppError(
                    code=ErrorCodes.UNAUTHENTICATED,
                    message="Auth session is revoked or missing.",
                    detail=None,
                ),
            )
        expected_hash = _hash_token(refresh_token)
        stored = session.unwrap()
        if stored is None:
            return Failure(
                AppError(
                    code=ErrorCodes.UNAUTHENTICATED,
                    message="Auth session is revoked or missing.",
                    detail=None,
                ),
            )
        if stored.refresh_token_hash and not _secure_compare(
            stored.refresh_token_hash,
            expected_hash,
        ):
            return Failure(
                AppError(
                    code=ErrorCodes.UNAUTHENTICATED,
                    message="Refresh token does not match stored session.",
                    detail=None,
                ),
            )
        grants = await self._build_grants_for_user(claims.sub)
        if isinstance(grants, Failure):
            return grants
        issued = await self._token_service.issue_tokens(
            user_id=claims.sub,
            grants=grants.unwrap(),
            session_id=claims.jti,
        )
        if isinstance(issued, Failure):
            return issued
        tokens = issued.unwrap()
        now_iso = utc_now_iso_z()
        updated = stored.model_copy(
            update={
                "refresh_token_hash": _hash_token(tokens.refresh_token),
                "updated_at": now_iso,
                "expires_at": (
                    datetime.now(tz=UTC) + timedelta(seconds=REFRESH_TOKEN_TTL_SECONDS)
                ).strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )
        saved = await self._auth_sessions.put(updated)
        if isinstance(saved, Failure):
            return saved
        return Success(tokens)

    async def logout(
        self,
        *,
        access_token: str | None,
        refresh_token: str | None,
    ) -> Result[None, AppError]:
        session_id: str | None = None
        if refresh_token:
            claims = await self._token_service.validate_token(refresh_token, allow_refresh=True)
            if isinstance(claims, Success):
                session_id = claims.unwrap().jti
        elif access_token:
            claims = await self._token_service.validate_token(access_token, allow_refresh=False)
            if isinstance(claims, Success):
                session_id = claims.unwrap().jti
        if session_id is None:
            return Success(None)
        return await self._auth_sessions.revoke(session_id, now_iso=utc_now_iso_z())

    async def _resolve_or_create_user(
        self,
        identity: IdpAuthResult,
    ) -> Result[UserRecord, AppError]:
        # Lookup by email via account scan is expensive; for bootstrap use deterministic id.
        user_id = str(uuid.uuid5(uuid.NAMESPACE_URL, identity.email.lower()))
        now = utc_now_iso_z()
        record = UserRecord(
            id=user_id,
            created_at=now,
            updated_at=now,
            enabled=True,
            first_name=identity.given_name,
            last_name=identity.family_name,
            account_id="default",
        )
        saved = await self._users.put(record)
        if isinstance(saved, Failure):
            return saved
        return Success(record)

    async def _build_grants_for_user(
        self,
        user_id: str,
    ) -> Result[PermissionGrantSet, AppError]:
        rows = await self._user_permissions.list_for_user(user_id)
        if isinstance(rows, Failure):
            return rows
        grants: list[ServicePermissionGrant] = []
        for row in rows.unwrap():
            try:
                function_ids = tuple(json.loads(row.functions_json))
            except json.JSONDecodeError:
                return Failure(
                    AppError(
                        code=ErrorCodes.INTERNAL,
                        message="Invalid user permission functions JSON.",
                        detail=f"user_id={user_id} service_id={row.service_id}",
                    ),
                )
            if not function_ids:
                continue
            grants.append(
                ServicePermissionGrant(
                    service_id=row.service_id,
                    function_ids=tuple(str(fn) for fn in function_ids),
                ),
            )
        if not grants:
            grants.append(
                ServicePermissionGrant(
                    service_id="iam-svc",
                    function_ids=("read-pro",),
                ),
            )
        return Success(PermissionGrantSet(grants=tuple(grants)))

    async def _persist_session(
        self,
        *,
        session_id: str,
        user_id: str,
        identity: IdpAuthResult,
        refresh_token: str,
    ) -> Result[None, AppError]:
        now = utc_now_iso_z()
        expires = (
            datetime.now(tz=UTC) + timedelta(seconds=REFRESH_TOKEN_TTL_SECONDS)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        record = AuthSessionRecord(
            id=session_id,
            user_id=user_id,
            idp_provider_id=identity.idp_provider_id,
            idp_subject=identity.idp_subject,
            refresh_token_hash=_hash_token(refresh_token),
            created_at=now,
            updated_at=now,
            expires_at=expires,
        )
        return await self._auth_sessions.put(record)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _secure_compare(left: str, right: str) -> bool:
    import secrets

    return secrets.compare_digest(left, right)
