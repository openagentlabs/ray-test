"""
FastAPI routes for AWS Cognito Hosted UI + Entra ID federation.

Flow (see plan cognito-entra-auth-integration-v2.1-6bdea7.md):

1. GET  /login-url   -> server builds authorize URL + sets signed cg_login cookie
2. POST /exchange    -> validates cg_login + PKCE + JWKS; JIT-provisions UserInDB;
                        creates Redis-backed server session; mints internal JWT;
                        sets HttpOnly midas_cg_rt cookie with Cognito refresh token
3. POST /refresh     -> uses midas_cg_rt cookie to mint a new internal JWT
4. POST /logout      -> revokes Cognito refresh token (RFC 7009), invalidates
                        Redis session, revokes app refresh tokens, clears cookies,
                        returns the Cognito /logout URL for the frontend redirect
5. POST /logout-everywhere -> same as /logout plus revoke-all-app-refresh-tokens

Security controls implemented:
- Authorization Code + PKCE (S256) + OIDC nonce
- Server-bound state via JWS-signed cg_login cookie (HttpOnly + path-scoped)
- Redirect-URI allowlist enforced server-side (open-redirect defense)
- RFC 7636 ``code_verifier`` length + charset validation
- Strict Pydantic models (``extra='forbid'``) prevent parameter smuggling
- Generic 401 ``auth_failed`` surface; full context in structured logs
- New Redis ``sid`` minted on every exchange and every refresh (fixation defense)
"""

from __future__ import annotations

import gc
import asyncio
import logging
import json
import os
import re
import shutil
import time
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from app.api.auth_routes import get_current_user_dependency
from app.core.pod_manager.deps import get_pod_manager_service
from app.core.session.contracts import ISessionAuthenticator
from app.services.pod_manager_service import PodManagerServiceError
from app.utils import helpers
from app.models.user_database import user_db
from app.services.auth_service import ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token
from app.services.dataframe_state_manager import dataframe_state_manager
from app.services.cognito import oauth_client
from app.services.cognito.jwks import CognitoTokenInvalid, verify_cognito_jwt
from app.services.cognito.login_state import (
    LOGIN_COOKIE_NAME,
    LoginStateInvalid,
    issue as issue_login_cookie,
    verify as verify_login_cookie,
)
from app.services.cognito.oauth_client import CognitoOAuthError
from app.services.cognito.settings import CognitoConfigError, get_cognito_settings
from app.services.cognito.user_provisioning import get_or_create_from_cognito
from app.services.background_jobs import background_job_manager
from app.services.model_training_rfe import get_job_manager

logger = logging.getLogger(__name__)

cognito_router = APIRouter()

_REFRESH_COOKIE_NAME = "midas_cg_rt"
_COOKIE_PATH = "/api/v1/auth/cognito"
_CODE_VERIFIER_RE = re.compile(r"^[A-Za-z0-9\-._~]{43,128}$")
_DATASET_ID_SAFE_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_BACKEND_ROOT = Path(__file__).resolve().parents[2]

security = HTTPBearer(auto_error=False)


# ---------- Pydantic request/response models --------------------------------


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExchangeRequest(_StrictModel):
    code: str = Field(..., min_length=1, max_length=4096)
    state: str = Field(..., min_length=1, max_length=512)
    code_verifier: str = Field(..., min_length=43, max_length=128)
    redirect_uri: str = Field(..., min_length=1, max_length=2048)


class LogoutRequest(_StrictModel):
    """JSON body from ``cognitoAuthService.logout()``: ``{ "dataset_id": "<id>" | null }``."""

    dataset_id: Optional[str] = Field(default=None, max_length=2048)


class LoginUrlResponse(BaseModel):
    authorize_url: str
    state: str
    nonce: str


# ---------- Helpers ---------------------------------------------------------


def _auth_failed(detail: str = "auth_failed") -> HTTPException:
    """Single choke-point for client-facing auth errors. Never leak internals."""
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


async def _parse_logout_dataset_id(request: Request) -> Optional[str]:
    """Parse optional JSON body from the frontend logout call (``Content-Type: application/json``)."""
    content_type = request.headers.get("content-type", "")
    media_type = content_type.partition(";")[0].strip().lower()
    if media_type != "application/json":
        return None
    try:
        raw = await request.json()
    except Exception:
        logger.warning("cognito.logout: could not parse JSON body")
        return None
    if not isinstance(raw, dict):
        return None
    try:
        return LogoutRequest.model_validate(raw).dataset_id
    except Exception as exc:
        logger.warning("cognito.logout: invalid logout body ignored: %s", exc)
        return None


def _safe_unlink(path: Path) -> bool:
    """Best-effort file delete. Returns True if a file was removed."""
    try:
        if path.is_file():
            path.unlink()
            return True
    except OSError as exc:
        logger.warning("logout cleanup: could not delete %s: %s", path, exc)
    return False


def _safe_unlink_with_retries(path: Path, retries: int = 6, delay_seconds: float = 0.5) -> bool:
    """Best-effort file delete with bounded retries for transient lock contention."""
    if not path.is_file():
        return False
    for attempt in range(retries):
        if _safe_unlink(path):
            return True
        # Windows file locking can keep the lock file busy briefly after cancellation.
        if attempt < retries - 1:
            time.sleep(delay_seconds)
    return False


def _safe_rmtree(path: Path) -> bool:
    """Best-effort directory delete. Returns True when removed."""
    try:
        if path.is_dir():
            shutil.rmtree(path)
            return True
    except OSError as exc:
        logger.warning("logout cleanup: could not delete directory %s: %s", path, exc)
    return False


def _cleanup_logout_artifacts(dataset_id: str) -> Dict[str, Any]:
    """
    Delete only ephemeral, dataset-scoped artifacts on logout.

    We intentionally do NOT delete canonical dataset files, model artifacts, or
    global state. The targets here are safe-to-recreate caches/snapshots.
    """
    result: Dict[str, Any] = {
        "dataset_id": dataset_id,
        "attempted": False,
        "deleted_count": 0,
        "deleted": [],
        "skipped": [],
    }
    if not dataset_id:
        result["skipped"].append("no_dataset_id")
        return result
    if not _DATASET_ID_SAFE_RE.fullmatch(dataset_id):
        result["skipped"].append("unsafe_dataset_id")
        return result

    result["attempted"] = True

    candidates = [
        _BACKEND_ROOT / "background_locks" / f"{dataset_id}.lock",
        _BACKEND_ROOT / "uploads" / dataset_id / "samples",
        _BACKEND_ROOT / "uploads" / dataset_id / "snapshots",
        _BACKEND_ROOT / "uploads" / f"{dataset_id}.target_profile.json",
    ]

    for candidate in candidates:
        if candidate.name.endswith(".lock"):
            deleted = _safe_unlink_with_retries(candidate)
        else:
            deleted = _safe_rmtree(candidate) if candidate.is_dir() else _safe_unlink(candidate)
        if deleted:
            result["deleted_count"] += 1
            result["deleted"].append(str(candidate))

    split_cfg_path = _BACKEND_ROOT / "split_configs_state.json"
    try:
        if split_cfg_path.is_file():
            with split_cfg_path.open("r", encoding="utf-8") as fh:
                raw = json.load(fh) or {}
            if isinstance(raw, dict) and dataset_id in raw:
                raw.pop(dataset_id, None)
                with split_cfg_path.open("w", encoding="utf-8") as fh:
                    json.dump(raw, fh)
                result["deleted_count"] += 1
                result["deleted"].append(str(split_cfg_path) + f"::{dataset_id}")
    except Exception as exc:
        logger.warning("logout cleanup: split config cleanup failed for %s: %s", dataset_id, exc)

    return result


async def _run_logout_cleanup_background(dataset_id: str, username: str) -> None:
    """Run logout artifact cleanup off the request path."""
    try:
        report = await asyncio.to_thread(_cleanup_logout_artifacts, dataset_id)
        lock_path = _BACKEND_ROOT / "background_locks" / f"{dataset_id}.lock"

        # Cancellation and cleanup are both fire-and-forget. If cleanup runs first,
        # the lock can still be held; retry cleanup asynchronously for a short window.
        if lock_path.is_file():
            for attempt in range(1, 13):
                await asyncio.sleep(2.0)
                retry_report = await asyncio.to_thread(_cleanup_logout_artifacts, dataset_id)
                report["deleted_count"] = int(report.get("deleted_count") or 0) + int(
                    retry_report.get("deleted_count") or 0
                )
                report.setdefault("deleted", [])
                report["deleted"].extend(retry_report.get("deleted") or [])
                if not lock_path.is_file():
                    logger.info(
                        "cognito.logout lock cleanup succeeded after retry dataset_id=%r username=%s attempt=%s",
                        dataset_id,
                        username,
                        attempt,
                    )
                    break

            if lock_path.is_file():
                logger.warning(
                    "cognito.logout lock file still present after retries dataset_id=%r username=%s path=%s",
                    dataset_id,
                    username,
                    str(lock_path),
                )

        logger.info(
            "cognito.logout background cleanup complete dataset_id=%r username=%s report=%s",
            dataset_id,
            username,
            report,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "cognito.logout background cleanup failed dataset_id=%r username=%s err=%s",
            dataset_id,
            username,
            exc,
        )


def _cancel_dataset_background_jobs_on_logout(dataset_id: str, username: str) -> Dict[str, List[str]]:
    """Cancel running dataset-scoped training jobs when logout is called."""
    cancelled: Dict[str, List[str]] = {"background_jobs": [], "rfe_jobs": []}
    if not dataset_id:
        return cancelled

    try:

        cancelled["background_jobs"] = background_job_manager.cancel_active_jobs(
            dataset_id=dataset_id,
            job_types={"vif_correlation", "auto_training_analyze", "auto_training_run"},
            reason="Cancelled due to logout",
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "cognito.logout: failed cancelling background jobs dataset_id=%r username=%s err=%s",
            dataset_id,
            username,
            exc,
        )

    try:

        rfe_manager = get_job_manager()
        for row in rfe_manager.list_active_jobs():
            if str(row.get("dataset_id") or "") != dataset_id:
                continue
            job_id = str(row.get("job_id") or "")
            if not job_id:
                continue
            if rfe_manager.cancel(job_id):
                cancelled["rfe_jobs"].append(job_id)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "cognito.logout: failed cancelling RFE jobs dataset_id=%r username=%s err=%s",
            dataset_id,
            username,
            exc,
        )

    return cancelled


async def _run_logout_job_cancellation_background(dataset_id: str, username: str) -> None:
    """Cancel training jobs off the request path during logout."""
    try:
        cancelled = await asyncio.to_thread(
            _cancel_dataset_background_jobs_on_logout,
            dataset_id,
            username,
        )
        logger.info(
            "cognito.logout cancelled running jobs dataset_id=%r username=%s cancelled=%s",
            dataset_id,
            username,
            cancelled,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "cognito.logout background cancellation failed dataset_id=%r username=%s err=%s",
            dataset_id,
            username,
            exc,
        )


def _handle_logout_dataset_cleanup(dataset_id: Optional[str], username: str) -> None:
    """Run logout-time dataframe cleanup and background artifact deletion."""
    # helpers.count_dataframes("before count_dataframes in congnito logout")
    helpers.dataframe_report("before dataframe_report in congnito logout")
    if dataset_id:
        asyncio.create_task(
            _run_logout_cleanup_background(dataset_id=dataset_id, username=username)
        )
        asyncio.create_task(
            _run_logout_job_cancellation_background(dataset_id=dataset_id, username=username)
        )
        dataframe_state_manager.clear_dataset(dataset_id)

    # helpers.count_dataframes("after count_dataframes in congnito logout")
    helpers.dataframe_report("after dataframe_report in congnito logout")
    logger.info("cognito.logout dataset_id=%r username=%s", dataset_id, username)


def _audit(event: str, *, outcome: str, request: Request, **fields: Any) -> None:
    """Emit one structured log line for every login/refresh/logout attempt."""
    client = request.client
    ip = client.host if client else None
    ua = request.headers.get("user-agent")
    req_id = request.headers.get("x-request-id", "")
    logger.info(
        "cognito_audit",
        extra={
            "event": event,
            "outcome": outcome,
            "ip": ip,
            "ua": ua,
            "req_id": req_id,
            **fields,
        },
    )


def _cookie_samesite(cfg) -> str:
    # SameSite=None; Secure is required for cross-origin fetch(..., credentials:'include')
    # on deployed envs (COGNITO_COOKIE_SECURE=true implies HTTPS + likely cross-origin).
    # Local dev (COGNITO_COOKIE_SECURE=false, http://localhost) uses Lax — same-site by
    # registrable domain so the browser sends cookies on same-site POST requests.
    return "none" if cfg.cookie_secure else "lax"


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    cfg = get_cognito_settings()
    response.set_cookie(
        key=_REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=cfg.cookie_secure,
        samesite=_cookie_samesite(cfg),
        path=_COOKIE_PATH,
        max_age=cfg.refresh_cookie_ttl_seconds,
    )


def _clear_refresh_cookie(response: Response) -> None:
    cfg = get_cognito_settings()
    response.delete_cookie(
        key=_REFRESH_COOKIE_NAME,
        path=_COOKIE_PATH,
        httponly=True,
        secure=cfg.cookie_secure,
        samesite=_cookie_samesite(cfg),
    )


def _set_login_cookie(response: Response, token: str) -> None:
    cfg = get_cognito_settings()
    response.set_cookie(
        key=LOGIN_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=cfg.cookie_secure,
        samesite=_cookie_samesite(cfg),
        path=_COOKIE_PATH,
        max_age=cfg.login_cookie_ttl_seconds,
    )


def _clear_login_cookie(response: Response) -> None:
    cfg = get_cognito_settings()
    response.delete_cookie(
        key=LOGIN_COOKIE_NAME,
        path=_COOKIE_PATH,
        httponly=True,
        secure=cfg.cookie_secure,
        samesite=_cookie_samesite(cfg),
    )


# Cognito error codes that indicate the refresh token itself is permanently invalid.
# On these we MUST clear the cookie so the client re-authenticates.
# All other errors (5xx, JWKS, network) are transient — keep the cookie so the next
# request can retry without forcing the user through a full login again.
_DEFINITIVE_COGNITO_ERROR_CODES = frozenset({
    "invalid_grant",
    "invalid_request",
    "unauthorized_client",
})


def _ensure_cognito_configured() -> None:
    try:
        get_cognito_settings()
    except CognitoConfigError as exc:
        logger.error("Cognito routes invoked but integration is not configured: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="cognito_not_configured",
        ) from exc


# ---------- Endpoints -------------------------------------------------------


@cognito_router.get("/login-url", response_model=LoginUrlResponse)
async def login_url(vhash: str, request: Request, response: Response) -> LoginUrlResponse:
    """
    Return the Cognito authorize URL plus the ``state`` + ``nonce`` to be
    echoed by the frontend. Also sets the HttpOnly ``cg_login`` cookie that
    binds these values (plus the verifier hash) to the /exchange step.

    The frontend generates the PKCE verifier locally and passes only its SHA-256
    hex (``vhash``) here; the raw verifier never leaves the browser until /exchange.
    """
    _ensure_cognito_configured()
    cfg = get_cognito_settings()
    if not re.fullmatch(r"[0-9a-fA-F]{64}", vhash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_vhash")

    cookie_token, binding = issue_login_cookie(vhash)
    _set_login_cookie(response, cookie_token)

    # Build authorize URL. PKCE challenge (S256) is appended by the caller
    # because we do not see the verifier itself.
    # The frontend supplies code_challenge explicitly when navigating.
    params = {
        "client_id": cfg.client_id,
        "response_type": "code",
        "scope": cfg.scopes,
        "redirect_uri": cfg.primary_redirect_uri(),
        "state": binding.state,
        "nonce": binding.nonce,
        "code_challenge_method": "S256",
    }
    if cfg.idp_name:
        params["identity_provider"] = cfg.idp_name

    authorize_url = f"{cfg.authorize_url}?{urlencode(params)}"
    _audit("cognito.login_url", outcome="success", request=request, state=binding.state)
    return LoginUrlResponse(authorize_url=authorize_url, state=binding.state, nonce=binding.nonce)


@cognito_router.post("/exchange")
async def exchange(
    payload: ExchangeRequest,
    request: Request,
    response: Response,
) -> Dict[str, Any]:
    """
    Exchange an authorization code + PKCE verifier for tokens and issue the
    internal app session used by every existing protected API.
    """
    _ensure_cognito_configured()
    cfg = get_cognito_settings()

    # --- 1. Local preconditions (cheap, before hitting Cognito) ---
    if not _CODE_VERIFIER_RE.fullmatch(payload.code_verifier):
        _audit("cognito.exchange", outcome="bad_verifier_format", request=request)
        raise _auth_failed()

    if not cfg.redirect_uri_allowed(payload.redirect_uri):
        _audit(
            "cognito.exchange",
            outcome="redirect_uri_rejected",
            request=request,
            redirect_uri=payload.redirect_uri,
        )
        raise _auth_failed()

    cookie_value = request.cookies.get(LOGIN_COOKIE_NAME)
    if not cookie_value:
        _audit("cognito.exchange", outcome="missing_login_cookie", request=request)
        raise _auth_failed()

    try:
        binding = verify_login_cookie(
            cookie_value,
            expected_state=payload.state,
            expected_verifier=payload.code_verifier,
        )
    except LoginStateInvalid as exc:
        _audit("cognito.exchange", outcome="login_cookie_invalid", request=request, reason=str(exc))
        raise _auth_failed() from exc

    # --- 2. Code exchange with Cognito ---
    try:
        tokens = await oauth_client.exchange_code(
            payload.code,
            payload.code_verifier,
            payload.redirect_uri,
        )
    except CognitoOAuthError as exc:
        _audit(
            "cognito.exchange",
            outcome="token_endpoint_error",
            request=request,
            status_code=exc.status_code,
            payload=exc.payload,
        )
        raise _auth_failed() from exc

    id_token = tokens.get("id_token")
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    if not (id_token and access_token and refresh_token):
        _audit("cognito.exchange", outcome="missing_tokens", request=request)
        raise _auth_failed()

    # --- 3. JWT validation (id + access) ---
    try:
        id_claims = await verify_cognito_jwt(id_token, "id", nonce=binding.nonce, access_token=access_token)
        await verify_cognito_jwt(access_token, "access")
    except CognitoTokenInvalid as exc:
        _audit("cognito.exchange", outcome="jwt_invalid", request=request, reason=str(exc))
        raise _auth_failed() from exc

    sub = id_claims.get("sub")
    email = id_claims.get("email")
    name = id_claims.get("name") or id_claims.get("cognito:username") or email
    if not sub:
        _audit("cognito.exchange", outcome="missing_sub", request=request)
        raise _auth_failed()

    # --- 4. JIT-provision local user + create server session + mint internal JWT ---
    user = get_or_create_from_cognito(sub=sub, email=email, full_name=name)
    if not user.is_active:
        _audit("cognito.exchange", outcome="user_inactive", request=request, sub=sub)
        raise _auth_failed()

    sm: ISessionAuthenticator = request.app.state.session_manager
    session_id = await sm.create_session(user.username)
    pod_manager_service = get_pod_manager_service(request)
    if pod_manager_service is not None:
        try:
            await pod_manager_service.acquire_lease(user.username)
        except PodManagerServiceError as exc:
            logger.warning("pod_manager lease acquire failed for '%s': %s", user.username, str(exc))
    internal_access = create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        session_id=session_id,
    )

    # --- 5. Set refresh cookie + clear login cookie ---
    _set_refresh_cookie(response, refresh_token)
    _clear_login_cookie(response)

    _audit(
        "cognito.exchange",
        outcome="success",
        request=request,
        sub=sub,
        username=user.username,
        session_id=session_id,
    )

    return {
        "access_token": internal_access,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "session_id": session_id,
        "session_created_at": int(time.time()),
        "session_ttl_seconds": sm.ttl_seconds,
        "user": {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "email": user.email,
            "is_active": user.is_active,
        },
    }


@cognito_router.post("/refresh")
async def refresh_endpoint(
    request: Request,
    response: Response,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Dict[str, Any]:
    """
    Silent refresh: mint a new internal app JWT using the ``midas_cg_rt`` cookie.

    Rotates the Redis ``sid`` every call (session fixation defense). Invalidates the
    previous ``sid`` (extracted from the inbound Bearer) before creating the new one
    to prevent session-store leaks and stale-sid races. If Cognito returns a new
    refresh token, the cookie is rotated too.

    Cookie clearing policy: only clear ``midas_cg_rt`` on *definitive* Cognito errors
    (``invalid_grant``, ``invalid_request``, ``unauthorized_client``). Transient errors
    (5xx, JWKS hiccup, network failure) 401 the call but keep the cookie so the very
    next request can retry without forcing a full re-login.
    """
    _ensure_cognito_configured()

    refresh_cookie = request.cookies.get(_REFRESH_COOKIE_NAME)
    if not refresh_cookie:
        _audit("cognito.refresh", outcome="missing_cookie", request=request)
        raise _auth_failed()

    try:
        tokens = await oauth_client.refresh(refresh_cookie)
    except CognitoOAuthError as exc:
        error_code = (
            exc.payload.get("error") if isinstance(exc.payload, dict) else None
        )
        is_definitive = error_code in _DEFINITIVE_COGNITO_ERROR_CODES
        _audit(
            "cognito.refresh",
            outcome="token_endpoint_error",
            request=request,
            status_code=exc.status_code,
            error_code=error_code,
            cookie_cleared=is_definitive,
        )
        if is_definitive:
            # Refresh token is permanently invalid; clear so client re-authenticates.
            _clear_refresh_cookie(response)
        # For transient errors keep the cookie — the next API call can retry /refresh.
        raise _auth_failed() from exc

    id_token = tokens.get("id_token")
    access_token = tokens.get("access_token")
    new_refresh = tokens.get("refresh_token")  # may be absent

    if not (id_token and access_token):
        _audit("cognito.refresh", outcome="missing_tokens", request=request)
        # Missing tokens from Cognito is a backend/protocol error, not an
        # invalid-grant; keep the cookie so a retry is possible.
        raise _auth_failed()

    try:
        id_claims = await verify_cognito_jwt(id_token, "id")
        await verify_cognito_jwt(access_token, "access")
    except CognitoTokenInvalid as exc:
        _audit("cognito.refresh", outcome="jwt_invalid", request=request, reason=str(exc))
        # JWT validation failure is a definitive error for this refresh cycle.
        _clear_refresh_cookie(response)
        raise _auth_failed() from exc

    sub = id_claims.get("sub")
    if not sub:
        _audit("cognito.refresh", outcome="missing_sub", request=request)
        raise _auth_failed()

    # Re-sync local mirror (name/email may have changed in IdP since last login).
    user = get_or_create_from_cognito(
        sub=sub,
        email=id_claims.get("email"),
        full_name=id_claims.get("name") or id_claims.get("cognito:username"),
    )
    if not user.is_active:
        _audit("cognito.refresh", outcome="user_inactive", request=request, sub=sub)
        raise _auth_failed()

    sm: ISessionAuthenticator = request.app.state.session_manager

    # Invalidate the previous server-side session before creating the new one.
    # This prevents sid leaks when multiple concurrent refreshes race (the last
    # winner's sid is the only valid one; stale sids are pruned here).
    if credentials and credentials.credentials:
        try:
            await sm.invalidate_access_token(credentials.credentials)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Could not invalidate previous sid during refresh: %s", exc)

    session_id = await sm.create_session(user.username)
    pod_manager_service = get_pod_manager_service(request)
    if pod_manager_service is not None:
        try:
            await pod_manager_service.acquire_lease(user.username)
        except PodManagerServiceError as exc:
            logger.warning("pod_manager lease acquire failed for '%s': %s", user.username, str(exc))
    internal_access = create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        session_id=session_id,
    )

    if new_refresh:
        _set_refresh_cookie(response, new_refresh)

    _audit(
        "cognito.refresh",
        outcome="success",
        request=request,
        sub=sub,
        username=user.username,
        session_id=session_id,
        rotated=bool(new_refresh),
    )

    return {
        "access_token": internal_access,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "session_id": session_id,
        "session_created_at": int(time.time()),
        "session_ttl_seconds": sm.ttl_seconds,
    }


@cognito_router.post("/logout")
async def logout_endpoint(
    request: Request,
    response: Response,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    current_user=Depends(get_current_user_dependency),
) -> Dict[str, Any]:
    """
    Revoke the Cognito refresh token (RFC 7009), invalidate the Redis
    ``sid`` session, revoke the app's legacy refresh tokens, clear cookies,
    and return the Cognito ``/logout`` URL for the frontend to redirect to
    (so the Hosted UI + federated Entra SSO session are also ended).

    The frontend may send ``Content-Type: application/json`` with
    ``{"dataset_id": "<string>" | null}`` (see ``cognitoAuthService.logout``).
    """
    _ensure_cognito_configured()
    cfg = get_cognito_settings()

    dataset_id = await _parse_logout_dataset_id(request)
    # Matches frontend: cognitoAuthService sends JSON.stringify({ dataset_id }).

    print(f"[cognito.logout] dataset_id={dataset_id!r}", flush=True)
    _handle_logout_dataset_cleanup(dataset_id=dataset_id, username=current_user.username)

    # 1. Revoke Cognito refresh token (best-effort, logged on failure).
    refresh_cookie = request.cookies.get(_REFRESH_COOKIE_NAME)
    cognito_revoked = False
    if refresh_cookie:
        cognito_revoked = await oauth_client.revoke(refresh_cookie)

    # 2. Invalidate server session (delete Redis sid).
    sm: ISessionAuthenticator = request.app.state.session_manager
    if credentials and credentials.credentials:
        try:
            await sm.invalidate_access_token(credentials.credentials)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Session invalidation failed during logout: %s", exc)
    pod_manager_service = get_pod_manager_service(request)
    if pod_manager_service is not None:
        try:
            await pod_manager_service.release_lease(current_user.username)
        except PodManagerServiceError as exc:
            logger.warning("pod_manager lease release failed for '%s': %s", current_user.username, str(exc))

    # 3. Revoke the app's own refresh tokens for this user (current-session-scoped default).
    # Note: the local refresh_tokens table does not track session_id; revoking all for this
    # user is the correct conservative default when a Cognito user logs out on one device.
    # A dedicated ``/logout-everywhere`` exists for explicit multi-device revocation.
    revoked_app_tokens = user_db.revoke_all_refresh_tokens_for_user(current_user.id)

    # 4. Clear cookies.
    _clear_refresh_cookie(response)
    _clear_login_cookie(response)

    # 5. Build Cognito /logout URL for the frontend redirect.
    cognito_logout_url = (
        f"{cfg.logout_url}?"
        + urlencode(
            {
                "client_id": cfg.client_id,
                "logout_uri": cfg.logout_redirect_uri,
            }
        )
    )

    _audit(
        "cognito.logout",
        outcome="success",
        request=request,
        username=current_user.username,
        cognito_revoked=cognito_revoked,
        app_refresh_tokens_revoked=revoked_app_tokens,
        dataset_id=dataset_id,
        cleanup_deleted_count=None,
    )
    # Best-effort: encourage reclaim of objects dropped during session/token teardown.
    gc.collect()   
    return {
        "cognito_logout_url": cognito_logout_url,
        "cognito_revoked": cognito_revoked,
        "app_refresh_tokens_revoked": revoked_app_tokens,
        "dataset_id": dataset_id,
    }


@cognito_router.post("/logout-everywhere")
async def logout_everywhere_endpoint(
    request: Request,
    response: Response,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    current_user=Depends(get_current_user_dependency),
) -> Dict[str, Any]:
    """
    Same as ``/logout`` today (since local refresh tokens are already revoked
    user-wide). Exists as an explicit endpoint for future divergence when
    per-session refresh tokens are introduced.
    """
    return await logout_endpoint(
        request=request,
        response=response,
        credentials=credentials,
        current_user=current_user,
    )
