"""ext_authz Check logic: resolve ``sub`` → upstream host for Envoy DFP (DS-1–DS-5)."""

from __future__ import annotations

import logging

from google.protobuf.json_format import ParseDict

from envoy.service.auth.v3 import external_auth_pb2
from solutions_service.auth.email_format import is_valid_email
from solutions_service.auth.jwt_validator import JwtValidator
from solutions_service.auth.session_cookie import extract_email_from_cookie_header
from solutions_service.core.app_config import AppConfig
from solutions_service.core.errors import AppError, ErrorCodes
from solutions_service.core.results import Failure, Result, Success
from solutions_service.database.models.pool_kind import BACKEND_POOL
from solutions_service.drivers.store.protocol import AssignmentStoreDriver
from solutions_service.ext_authz.assignment_cache import AssignmentRouteCache
from solutions_service.observability.metrics import log_authz_cache, observe_ext_authz_check

logger = logging.getLogger(__name__)

ROUTE_UPSTREAM_HEADER = "x-route-upstream"
USER_SUB_HEADER = "x-user-sub"


class ExtAuthzCheckHandler:
    """Stateless Check handler; reads assignments from store driver + optional cache."""

    __slots__ = (
        "_app_config",
        "_store",
        "_route_cache",
        "_jwt",
    )

    def __init__(
        self,
        *,
        app_config: AppConfig,
        assignment_store: AssignmentStoreDriver,
        route_cache: AssignmentRouteCache | None = None,
        jwt_validator: JwtValidator | None = None,
    ) -> None:
        self._app_config = app_config
        self._store = assignment_store
        self._route_cache = route_cache
        self._jwt = jwt_validator

    async def check(
        self,
        request: external_auth_pb2.CheckRequest,
    ) -> external_auth_pb2.CheckResponse:
        with observe_ext_authz_check():
            return await self._check_inner(request)

    async def _check_inner(
        self,
        request: external_auth_pb2.CheckRequest,
    ) -> external_auth_pb2.CheckResponse:
        sub_result = await self._extract_sub(request)
        if isinstance(sub_result, Failure):
            return _deny(403, sub_result.failure().message)
        sub = sub_result.unwrap()
        if not sub:
            return _deny(401, "Missing identity.")

        if self._route_cache is not None:
            cached = self._route_cache.get(sub=sub)
            if cached is not None:
                logger.debug("ext_authz_cache_hit sub=%s", sub)
                log_authz_cache(hits=self._route_cache.hits, misses=self._route_cache.misses)
                return _allow(cached.pod_dns, sub=sub)
            log_authz_cache(hits=self._route_cache.hits, misses=self._route_cache.misses)

        assignment_result = await self._store.get_assignment_by_sub(sub=sub)
        if isinstance(assignment_result, Failure):
            logger.warning(
                "ext_authz assignment lookup failed: %s",
                assignment_result.failure().message,
            )
            return _deny(503, "Assignment lookup failed.")
        assignment = assignment_result.unwrap()
        if assignment is None:
            login_upstream = self._app_config.login_pod_pool.routing_upstream
            logger.info("ext_authz_allow_login_pool sub=%s upstream=%s", sub, login_upstream)
            return _allow(login_upstream, sub=sub)

        pod_result = await self._store.get_pod_by_id(
            pool=BACKEND_POOL,
            pod_id=assignment.pod_id,
        )
        if isinstance(pod_result, Failure):
            return _deny(503, "Pod lookup failed.")
        pod = pod_result.unwrap()
        upstream = assignment.pod_dns
        if pod is not None and pod.pod_dns:
            upstream = pod.pod_dns
        elif pod is None:
            logger.warning(
                "ext_authz_allow_missing_pod_row sub=%s pod_id=%s",
                sub,
                assignment.pod_id,
            )

        if self._route_cache is not None:
            self._route_cache.set(
                sub=sub,
                pod_dns=upstream,
                epoch=assignment.assignment_epoch,
            )

        logger.info("ext_authz_allow sub=%s upstream=%s", sub, upstream)
        return _allow(upstream, sub=sub)

    async def _extract_sub(
        self,
        request: external_auth_pb2.CheckRequest,
    ) -> Result[str, AppError]:
        headers = _request_headers(request)
        dev_header = ""
        if self._app_config.auth.dev_mode:
            dev_header = self._app_config.auth.dev_sub_header.strip().lower()
        if dev_header:
            value = headers.get(dev_header)
            if value:
                candidate = value.strip()
                if is_valid_email(candidate):
                    return Success(candidate)
                return Failure(
                    AppError(
                        code=ErrorCodes.VALIDATION,
                        message="dev sub header must be a valid email.",
                        detail=None,
                    ),
                )

        cookie_header = headers.get("cookie", "")
        if cookie_header:
            email = extract_email_from_cookie_header(
                cookie_header,
                cookie_name=self._app_config.auth.session_cookie_name,
            )
            if email:
                return Success(email)

        auth = headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
            if self._jwt is not None:
                return await self._jwt.validate_and_extract_sub(token)
            if token.startswith("sub:"):
                candidate = token[4:].strip()
                if is_valid_email(candidate):
                    return Success(candidate)
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="JWT validation not configured.",
                    detail=None,
                ),
            )
        return Success("")


def _request_headers(request: external_auth_pb2.CheckRequest) -> dict[str, str]:
    """Normalize Envoy ``AttributeContext.HttpRequest`` headers to a lowercase map."""
    headers: dict[str, str] = {}
    http_ctx = request.attributes.request.http

    def _add(key: str, value: str) -> None:
        lk = key.lower()
        if lk in headers:
            headers[lk] = f"{headers[lk]},{value}"
        else:
            headers[lk] = value

    for key, value in http_ctx.headers.items():
        _add(key, value)

    for header_value in http_ctx.header_map.headers:
        _add(header_value.key, header_value.value)

    return headers


def _allow(upstream_host: str, *, sub: str) -> external_auth_pb2.CheckResponse:
    headers = [
        {
            "header": {
                "key": ROUTE_UPSTREAM_HEADER,
                "value": upstream_host,
            },
        },
        {
            "header": {
                "key": USER_SUB_HEADER,
                "value": sub,
            },
        },
    ]
    return ParseDict(
        {
            "status": {"code": 0},
            "ok_response": {"headers": headers},
        },
        external_auth_pb2.CheckResponse(),
    )


def _deny(http_code: int, message: str) -> external_auth_pb2.CheckResponse:
    _ = http_code
    logger.info("ext_authz_deny message=%s", message)
    return ParseDict(
        {
            "status": {"code": 16, "message": message},
            "denied_response": {"status": {"code": "Forbidden"}},
        },
        external_auth_pb2.CheckResponse(),
    )
