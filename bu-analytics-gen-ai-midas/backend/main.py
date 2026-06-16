# Configure pandas Copy-on-Write BEFORE importing routes/services so the global
# option is in effect before any DataFrame is created in this (main) process.
# Gated by MIDAS_PANDAS_COW (1=on default, 0=off). .env is already loaded by
# app.core.logging_config at import time, so the env var is available here.
# See app/utils/helpers.configure_pandas_copy_on_write for rationale/impact.
from app.utils.helpers import configure_pandas_copy_on_write as _configure_pandas_cow
_configure_pandas_cow()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import upload_router, chat_router
from app.api.chunked_upload import router as chunked_upload_router
from app.api.sse import router as sse_router
from app.api.auth_routes import auth_router
from app.api.project_routes import project_router
from app.api.documentation_routes import documentation_router
from app.api.rfe_routes import rfe_router
from app.core.logging_config import (
    get_logger,
    set_request_id,
    clear_request_context,
    hash_for_log,
    parse_w3c_traceparent,
    set_trace_context,
    set_tenant_id,
)
from app.services.graphrag_process_manager import graphrag_process_manager
from app.core.executor import executor, shutdown_executor
from app.core.config import settings as app_settings
from app.core.rate_limit_config import load_rate_limit_settings
from app.core.rate_limit_store import build_rate_limit_store
from app.core.session import build_session_manager
from app.core.secrets import load_application_secrets_bundle
from app.services.object_storage import build_upload_object_storage, set_object_storage
from app.services.pod_manager_service import PodManagerService, PodManagerServiceError
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.session_validation import SessionValidationMiddleware
import os
import time
import uuid
import warnings
from typing import Optional

# Suppress scikit-learn deprecation warnings about CatBoost __sklearn_tags__
# These warnings are from scikit-learn checking tags and will be fixed by CatBoost maintainers
warnings.filterwarnings('ignore', category=DeprecationWarning, module='sklearn.utils._tags')

# Initialize logger
logger = get_logger(__name__)

app = FastAPI(
    title="MIDAS API",
    description="Modularized FastAPI backend for MIDAS data analysis system",
    version="1.0.0"
)

app.state.session_manager = build_session_manager()
app.state.pod_manager_service = None

logger.info("Starting MIDAS FastAPI application")


@app.on_event("startup")
async def startup_event():
    from app.services.keith_log_matrics_test import (
        start_backend_heartbeat,
        start_dfsm_state_metrics_heartbeat,
    )
    start_backend_heartbeat(logger)
    start_dfsm_state_metrics_heartbeat(logger)

    app.state.secrets_bundle = load_application_secrets_bundle(app_settings)
    sb = app.state.secrets_bundle
    logger.info(
        "Application secrets bundle: rds_postgres=%s s3=%s elasticache=%s bedrock=%s",
        sb.rds_postgres is not None,
        sb.s3 is not None,
        sb.elasticache is not None,
        sb.bedrock is not None,
    )
    if sb.rds_postgres is not None and not os.environ.get("DATABASE_URL"):
        sslm = (app_settings.AWS_RDS_POSTGRES_SSLMODE or "").strip() or None
        os.environ["DATABASE_URL"] = sb.rds_postgres.sqlalchemy_url(sslmode=sslm)
        logger.info("DATABASE_URL populated from RDS bundle (sslmode=%s)", sslm or "default")
    app.state.object_storage = build_upload_object_storage(app_settings, sb)
    set_object_storage(app.state.object_storage)
    from app.services.dataset_service import dataset_manager as dm

    dm.refresh_object_storage_index()
    logger.info("Object storage backend: %s", app.state.object_storage.kind)
    app.state.executor = executor
    logger.info("Shared ThreadPoolExecutor attached to app.state.executor")
    if app_settings.POD_MANAGER_ENABLED:
        try:
            pod_manager_service = PodManagerService(
                host=app_settings.POD_MANAGER_HOST,
                port=app_settings.POD_MANAGER_PORT,
                timeout_seconds=app_settings.POD_MANAGER_TIMEOUT_SECONDS,
                ensure_retries=app_settings.POD_MANAGER_ENSURE_RETRIES,
            )
            await pod_manager_service.start()
            app.state.pod_manager_service = pod_manager_service
            logger.info(
                "Pod-manager integration enabled",
                extra={
                    "event": "pod_manager_enabled",
                    "host": app_settings.POD_MANAGER_HOST,
                    "port": app_settings.POD_MANAGER_PORT,
                },
            )
        except PodManagerServiceError as exc:
            app.state.pod_manager_service = None
            logger.warning(
                "Pod-manager startup skipped",
                extra={
                    "event": "pod_manager_startup_failed",
                    "error": str(exc),
                },
            )
    # Restore any training jobs that were in-flight before a process restart
    from app.api.routes import _load_jobs_state
    _load_jobs_state()
    # Mark any RFE jobs that were running on a previous process as `interrupted`
    # so the UI can prompt the user to restart. Best-effort - never fail startup.
    try:
        from app.services.model_training_rfe import get_job_manager as _get_rfe_manager
        _get_rfe_manager().hydrate_startup()
    except Exception as _rfe_err:
        logger.warning("RFE job hydration skipped: %s", _rfe_err)
    # Pre-warm heavy scientific libraries used by Step 3 (RFE) in a daemon thread
    # so the first RFE job does not pay the one-time cost of building matplotlib's
    # font cache (20-45s) or loading xgboost / shap. Non-blocking; safe to no-op.
    try:
        from app.services.model_training_rfe.warmup import (
            ensure_mpl_config_dir,
            start_rfe_warmup,
        )
        ensure_mpl_config_dir()
        start_rfe_warmup(background=True)
    except Exception as _warmup_err:
        logger.warning("RFE warmup skipped: %s", _warmup_err)
    graphrag_process_manager.ensure_running()


@app.on_event("shutdown")
async def shutdown_event():
    pod_manager_service: PodManagerService | None = getattr(app.state, "pod_manager_service", None)
    if pod_manager_service is not None:
        await pod_manager_service.close()
    shutdown_executor()
    graphrag_process_manager.shutdown()


# Configure CORS.
# Credentials (HttpOnly cookies for Cognito refresh) require an explicit origin allowlist:
# the spec forbids "*" combined with allow_credentials=True. Set CORS_ALLOW_ORIGINS in .env
# as a comma-separated list. Falls back to "*" WITHOUT credentials in pure-dev mode.
_cors_origins_raw = app_settings.CORS_ALLOW_ORIGINS or ""
_cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Content-Range",
            "X-Session-Id",
            "x-llm-chat-model",
            "x-llm-kg-model",
            "x-llm-embedding-model",
        ],
    )
    logger.info("CORS configured with credentials for origins: %s", _cors_origins)
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.warning(
        "CORS_ALLOW_ORIGINS is not set; using wildcard without credentials. "
        "Cognito cookie-based auth will NOT work cross-origin until this is configured."
    )


def _route_template(request: Request) -> Optional[str]:
    route = request.scope.get("route")
    if route is None:
        return None
    return getattr(route, "path", None)


def _http_outcome(status_code: int) -> str:
    if 200 <= status_code < 300:
        return "success"
    if 300 <= status_code < 400:
        return "redirect"
    if 400 <= status_code < 500:
        return "client_error"
    if 500 <= status_code < 600:
        return "server_error"
    return "unknown"


@app.middleware("http")
async def log_requests(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/v1/rfe/stream/") or path.startswith("/api/v1/auto-training/stream/"):
        return await call_next(request)
    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    path = request.url.path
    route_tpl = _route_template(request)
    status_code = response.status_code
    # Architecture rule: any request that takes > SLOW_REQUEST_THRESHOLD_MS
    # belongs in a background job (see .cursor/rules/architecture.mdc and
    # docs/observability-runbook-slow-endpoints.md). We tag the regular
    # ``http_request`` event with ``is_slow`` so a single CloudWatch Insights
    # filter can return offenders, and we ALSO emit a dedicated WARN-level
    # ``slow_request`` event so the existing CloudWatch alarm pattern
    # (filter on level=WARNING) fires without any extra wiring.
    is_slow = duration_ms > app_settings.SLOW_REQUEST_THRESHOLD_MS
    extra = {
        "event": "http_request",
        "log_category": "http",
        "method": request.method,
        "path": path,
        "route": route_tpl or path,
        "operation": route_tpl or path,
        "status_code": status_code,
        "outcome": _http_outcome(status_code),
        "duration_ms": duration_ms,
        "is_slow": is_slow,
        "slow_threshold_ms": app_settings.SLOW_REQUEST_THRESHOLD_MS,
    }
    if app_settings.LOG_CLIENT_IP and request.client and request.client.host:
        extra["client_ip_hash"] = hash_for_log(request.client.host)
    path_norm = path.rstrip("/") or "/"
    if path_norm in ("/health", "/"):
        logger.debug("http_request", extra=extra)
    else:
        logger.info("http_request", extra=extra)
    if is_slow:
        # Separate event so the alerting rule can scope to slow_request only
        # (CloudWatch Insights stats over `event=slow_request` cheaply
        # produces top-N offenders without scanning every http_request line).
        logger.warning(
            "slow_request",
            extra={
                "event": "slow_request",
                "log_category": "http",
                "method": request.method,
                "route": route_tpl or path,
                "path": path,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "slow_threshold_ms": app_settings.SLOW_REQUEST_THRESHOLD_MS,
                "outcome": _http_outcome(status_code),
            },
        )
    return response


# Note: tag-based routing (see app.core.llm_routing) replaces the previous
# per-request LLM selection headers. No middleware needed here.

# Last @app.middleware runs first on incoming request — set correlation ID before inner middleware.
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/v1/rfe/stream/") or path.startswith("/api/v1/auto-training/stream/"):
        return await call_next(request)
    rid = request.headers.get("x-request-id") or request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = rid
    set_request_id(rid)
    tp = request.headers.get("traceparent") or request.headers.get("Traceparent")
    tr_t, sp_t = parse_w3c_traceparent(tp)
    if tr_t:
        set_trace_context(trace_id=tr_t, span_id=sp_t)
    else:
        tr_x = request.headers.get("x-trace-id") or request.headers.get("X-Trace-Id")
        sp_x = request.headers.get("x-span-id") or request.headers.get("X-Span-Id")
        if tr_x or sp_x:
            set_trace_context(trace_id=tr_x, span_id=sp_x)
    tenant_hdr = request.headers.get("x-tenant-id") or request.headers.get("X-Tenant-ID")
    if tenant_hdr:
        set_tenant_id(tenant_hdr.strip()[:128])
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response
    finally:
        clear_request_context()


# Session validation: after CORS / logging / request correlation; before rate limit (rate limit stays outermost).
app.add_middleware(SessionValidationMiddleware)

# Rate limiting: registered last so it runs first on incoming requests (outermost middleware).
_rate_limit_settings = load_rate_limit_settings()
app.state.rate_limit_store = build_rate_limit_store(_rate_limit_settings.redis_url)
app.add_middleware(
    RateLimitMiddleware,
    settings=_rate_limit_settings,
    store=app.state.rate_limit_store,
)

# Include routers
app.include_router(upload_router, prefix="/api/v1", tags=["upload"])
app.include_router(chunked_upload_router, prefix="/api/v1", tags=["upload-chunked"])
app.include_router(sse_router, prefix="/api/v1", tags=["sse"])
app.include_router(chat_router, prefix="/api/v1", tags=["chat"])
app.include_router(auth_router, prefix="/api/v1/auth", tags=["authentication"])
app.include_router(project_router, prefix="/api/v1", tags=["projects"])
app.include_router(documentation_router, prefix="/api/v1", tags=["documentation"])
app.include_router(rfe_router, prefix="/api/v1", tags=["model-training-rfe"])

logger.info("API routers registered")

@app.get("/")
async def root():
    logger.debug("root_endpoint")
    return {"message": "MIDAS API is running"}

@app.get("/health")
async def health_check():
    from app.services.vector_store import vector_store

    health_status = {
        "status": "healthy",
        "vector_store": {
            "initialized": vector_store.is_initialized(),
            "documents_count": len(vector_store.documents) if vector_store.documents else 0
        }
    }
    logger.debug(
        "health_check",
        extra={
            "event": "health_check",
            "log_category": "ops",
            "outcome": "success",
            "vector_store_initialized": health_status["vector_store"]["initialized"],
            "documents_count": health_status["vector_store"]["documents_count"],
        },
    )
    return health_status
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
