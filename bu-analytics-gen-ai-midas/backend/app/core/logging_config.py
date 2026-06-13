"""
Application logging for local dev (colored text) and production (JSON on stdout for CloudWatch).

Environment (read directly here to avoid import cycles with Settings):
  LOG_LEVEL              DEBUG|INFO|WARNING|ERROR (default INFO)
  LOG_FILE               Path to file, or empty to disable file logging (default logs/midas.log)
  ENABLE_CONSOLE_LOGGING true|false (default true)
  LOG_FORMAT             text|json — json emits one JSON object per line (default text)
  LOG_CLIENT_IP          true|false — include client_ip_hash in http_request logs (default false)
  LOG_SERVICE_NAME       Logical service name in JSON logs (default midas, or APP_NAME)
  LOG_ENVIRONMENT        deployment/stage, e.g. production (default ENVIRONMENT / ENV / development)
  LOG_JSON_STACK_TRACE   true|false — include stackTrace in error object for exceptions (default false)

Structured JSON fields (when LOG_FORMAT=json):
  - Always: timestamp, level, service, environment, logger, message, caller (file/line/function)
  - Correlation: request_id, dataset_id, user_id, tenant_id, trace_id, span_id (from contextvars when set)
  - App events: pass logger.info("name", extra={...}) — extra keys merge into the JSON object
  - Common extras: event (e.g. http_request, llm_call, dependency_call), log_category, outcome, etc.

Request correlation: set_request_id / set_user_context / set_trace_context from HTTP middleware
(contextvars) so child loggers include correlation on each record.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import traceback
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
import time
from functools import wraps


def _load_dotenv_before_logging() -> None:
    """So LOG_FORMAT / LOG_LEVEL from backend/.env apply when setup_logging() runs at import."""
    try:
        from dotenv import load_dotenv

        for candidate in (
            Path.cwd(),
            Path(__file__).resolve().parent.parent.parent,
        ):
            env_path = candidate / ".env"
            if env_path.is_file():
                load_dotenv(env_path)
                return
    except Exception:
        pass


_load_dotenv_before_logging()

# --- Request correlation (async-safe) ---
_request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_dataset_id_ctx: ContextVar[Optional[str]] = ContextVar("dataset_id", default=None)
_user_id_ctx: ContextVar[Optional[int]] = ContextVar("user_id", default=None)
_tenant_id_ctx: ContextVar[Optional[str]] = ContextVar("tenant_id", default=None)
_trace_id_ctx: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)
_span_id_ctx: ContextVar[Optional[str]] = ContextVar("span_id", default=None)


def set_request_id(value: Optional[str]) -> None:
    _request_id_ctx.set(value)


def get_request_id() -> Optional[str]:
    return _request_id_ctx.get()


def set_dataset_id(value: Optional[str]) -> None:
    _dataset_id_ctx.set(value)


def get_dataset_id() -> Optional[str]:
    return _dataset_id_ctx.get()


def set_user_context(user_id: Optional[int] = None, tenant_id: Optional[str] = None) -> None:
    """Attach authenticated user (numeric id) and optional tenant for all logs in this request."""
    if user_id is not None:
        _user_id_ctx.set(user_id)
    if tenant_id is not None:
        _tenant_id_ctx.set(tenant_id)


def set_tenant_id(value: Optional[str]) -> None:
    """Opaque tenant / org id from header (non-PII); does not clear user_id."""
    _tenant_id_ctx.set(value)


def set_trace_context(trace_id: Optional[str] = None, span_id: Optional[str] = None) -> None:
    """Distributed tracing ids (e.g. W3C traceparent or upstream headers)."""
    _trace_id_ctx.set(trace_id)
    _span_id_ctx.set(span_id)


def clear_request_context() -> None:
    _request_id_ctx.set(None)
    _dataset_id_ctx.set(None)
    _user_id_ctx.set(None)
    _tenant_id_ctx.set(None)
    _trace_id_ctx.set(None)
    _span_id_ctx.set(None)


def parse_w3c_traceparent(header: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """
    Parse W3C traceparent: version-trace_id-parent_id-flags.
    Returns (trace_id, parent_span_id) for logging correlation.
    """
    if not header or not isinstance(header, str):
        return None, None
    parts = header.strip().split("-")
    if len(parts) < 4:
        return None, None
    if parts[0] not in ("00", "01"):
        return None, None
    trace_id, parent_id = parts[1], parts[2]
    if len(trace_id) == 32 and len(parent_id) == 16:
        return trace_id, parent_id
    return None, None


class RequestContextFilter(logging.Filter):
    """Injects correlation fields from contextvars into each LogRecord."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        record.dataset_id = get_dataset_id()
        record.user_id = _user_id_ctx.get()
        record.tenant_id = _tenant_id_ctx.get()
        record.trace_id = _trace_id_ctx.get()
        record.span_id = _span_id_ctx.get()
        return True


# LogRecord keys that must not be copied as custom fields into JSON output
_JSON_RESERVED_KEYS = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "message",
        "asctime",
        "taskName",  # asyncio / Python 3.12+
    }
)


def _json_safe_value(value: Any) -> Any:
    """Ensure value can be serialized; fall back to string for odd types."""
    try:
        json.dumps(value, default=str)
        return value
    except (TypeError, ValueError):
        return str(value)


class JsonFormatter(logging.Formatter):
    """
    One JSON object per line (CloudWatch Logs friendly).

    Merges ``extra=`` from ``logger.info(..., extra={...})`` into the object.
    Known structured events (set ``event`` in extra): ``http_request``, ``llm_call``,
    ``agent_prompt_init``, ``plan_context_for_code_gen``, etc.
    """

    def format(self, record: logging.LogRecord) -> str:
        service = os.getenv("LOG_SERVICE_NAME", os.getenv("APP_NAME", "midas"))
        environment = os.getenv(
            "LOG_ENVIRONMENT",
            os.getenv("ENVIRONMENT", os.getenv("ENV", "development")),
        )
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat().replace("+00:00", "Z")

        extras: Dict[str, Any] = {}
        _ctx_keys = ("request_id", "dataset_id", "user_id", "tenant_id", "trace_id", "span_id")
        for key, value in record.__dict__.items():
            if key in _JSON_RESERVED_KEYS or key.startswith("_"):
                continue
            if key in _ctx_keys:
                continue
            extras[key] = _json_safe_value(value)

        rid = getattr(record, "request_id", None)
        did = getattr(record, "dataset_id", None)
        uid = getattr(record, "user_id", None)
        tid = getattr(record, "tenant_id", None)
        trid = getattr(record, "trace_id", None)
        spid = getattr(record, "span_id", None)

        # Prefer explicit event name first (Insights: fields.event = "llm_call" | "http_request")
        event_val = extras.pop("event", None)

        payload: Dict[str, Any] = {
            "timestamp": ts,
            "level": record.levelname,
            "service": service,
            "environment": environment,
        }
        log_group = os.getenv("LOG_CLOUDWATCH_LOG_GROUP")
        if log_group:
            payload["@logGroupName"] = log_group
        if event_val is not None:
            payload["event"] = event_val
        payload["logger"] = record.name
        payload["message"] = record.getMessage()
        # "caller" avoids clashing with domain extras named "source"
        payload["caller"] = {
            "file": getattr(record, "filename", None),
            "line": record.lineno,
            "function": record.funcName,
        }
        if rid:
            payload["request_id"] = rid
        if did:
            payload["dataset_id"] = did
        if uid is not None:
            payload["user_id"] = uid
        if tid:
            payload["tenant_id"] = tid
        if trid:
            payload["trace_id"] = trid
        if spid:
            payload["span_id"] = spid

        # Remaining structured fields (LLM metrics, HTTP fields, hashes, etc.) — stable sort for diff-friendly logs
        for key in sorted(extras.keys()):
            if key in payload:
                continue
            payload[key] = extras[key]

        if record.exc_info:
            err: Dict[str, Any] = {}
            typ, val, _tb = record.exc_info
            if typ is not None:
                err["type"] = getattr(typ, "__name__", str(typ))
            if val is not None:
                err["message"] = str(val)
            if os.getenv("LOG_JSON_STACK_TRACE", "").lower() in ("1", "true", "yes"):
                st = "".join(traceback.format_exception(*record.exc_info))
                if len(st) > 16000:
                    st = st[:16000] + "...[truncated]"
                err["stackTrace"] = st
            payload["error"] = err

        return json.dumps(payload, default=str, ensure_ascii=False, separators=(",", ":"))


class CustomFormatter(logging.Formatter):
    """Colored console output for local development."""

    grey = "\x1b[38;21m"
    blue = "\x1b[34;21m"
    yellow = "\x1b[33;21m"
    red = "\x1b[31;21m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    FORMATS = {
        logging.DEBUG: grey + format_str + reset,
        logging.INFO: blue + format_str + reset,
        logging.WARNING: yellow + format_str + reset,
        logging.ERROR: red + format_str + reset,
        logging.CRITICAL: bold_red + format_str + reset,
    }

    def format(self, record: logging.LogRecord) -> str:
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)


class SafeStreamHandler(logging.StreamHandler):
    """StreamHandler that handles Unicode encoding errors gracefully."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            super().emit(record)
        except UnicodeEncodeError:
            try:
                msg = self.format(record)
                msg = msg.encode("ascii", "replace").decode("ascii")
                stream = self.stream
                stream.write(msg + self.terminator)
                self.flush()
            except Exception:
                self.handleError(record)


def _read_log_file_path() -> Optional[str]:
    raw = os.getenv("LOG_FILE")
    if raw is None:
        return "logs/midas.log"
    stripped = raw.strip()
    return stripped if stripped else None


def setup_logging(
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_console: Optional[bool] = None,
    log_format: Optional[str] = None,
) -> logging.Logger:
    """
    Configure the root application logger ``midas``.

    When arguments are None, values are taken from environment variables.
    """
    level_str = (log_level or os.getenv("LOG_LEVEL", "INFO")).upper()
    numeric_level = getattr(logging, level_str, logging.INFO)

    if log_file is None:
        log_file = _read_log_file_path()

    if enable_console is None:
        enable_console = os.getenv("ENABLE_CONSOLE_LOGGING", "true").lower() == "true"

    if log_format is None:
        log_format = os.getenv("LOG_FORMAT", "text").strip().lower()
    use_json = log_format == "json"

    logger = logging.getLogger("midas")
    logger.setLevel(numeric_level)
    logger.handlers.clear()

    ctx_filter = RequestContextFilter()

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(numeric_level)
        file_handler.addFilter(ctx_filter)
        if use_json:
            file_handler.setFormatter(JsonFormatter())
        else:
            file_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
        logger.addHandler(file_handler)

    if enable_console:
        console_handler = SafeStreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        console_handler.addFilter(ctx_filter)
        if use_json:
            console_handler.setFormatter(JsonFormatter())
        else:
            console_handler.setFormatter(CustomFormatter())
        logger.addHandler(console_handler)

    logger.propagate = False
    return logger


def reconfigure_logging() -> logging.Logger:
    """Reload logging from environment (e.g. after tests or dynamic config)."""
    return setup_logging()


def get_logger(name: str) -> logging.Logger:
    """Return a module logger under the ``midas`` hierarchy."""
    return logging.getLogger(f"midas.{name}")


def hash_for_log(value: str) -> str:
    """SHA-256 hex digest for optional correlation (never log raw content)."""
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def log_dependency_event(
    logger: logging.Logger,
    *,
    dependency: str,
    operation: str,
    duration_ms: float,
    success: bool,
    error_type: Optional[str] = None,
) -> None:
    """
    Structured log for outbound dependency calls (postgres, redis, s3, bedrock, http, ...).
    Use from repositories/clients after timing the call.
    """
    extra: Dict[str, Any] = {
        "event": "dependency_call",
        "log_category": "integration",
        "dependency": dependency,
        "dependency_operation": operation,
        "duration_ms": round(duration_ms, 3),
        "outcome": "success" if success else "failure",
        "success": success,
    }
    if error_type:
        extra["error_type"] = error_type
    logger.info("dependency_call", extra=extra)
class DataQualityLogger:
    """
    Specialized logger for Data Quality / Treatment Agent operations.
    Provides structured logging with timing, metrics, and correlation support.
    """

    def __init__(self, logger_name: str = "data_quality"):
        self._logger = get_logger(logger_name)
        self._operation_timers: Dict[str, float] = {}

    def _create_extra(self, **kwargs) -> Dict[str, Any]:
        """Create extra data dict for structured logging."""
        extra_data = {k: v for k, v in kwargs.items() if v is not None}
        return {"extra_data": extra_data} if extra_data else {}

    def start_operation(self, operation_id: str, operation_name: str, **context) -> None:
        """Log the start of an operation and begin timing."""
        self._operation_timers[operation_id] = time.time()
        self._logger.info(
            f"Starting operation: {operation_name}",
            extra=self._create_extra(
                operation_id=operation_id,
                operation=operation_name,
                event="operation_start",
                **context
            )
        )

    def end_operation(self, operation_id: str, operation_name: str, success: bool = True, **context) -> float:
        """Log the end of an operation with duration."""
        start_time = self._operation_timers.pop(operation_id, None)
        duration_ms = (time.time() - start_time) * 1000 if start_time else 0

        log_method = self._logger.info if success else self._logger.error
        status = "completed" if success else "failed"

        log_method(
            f"Operation {status}: {operation_name} ({duration_ms:.2f}ms)",
            extra=self._create_extra(
                operation_id=operation_id,
                operation=operation_name,
                event="operation_end",
                status=status,
                duration_ms=round(duration_ms, 2),
                **context
            )
        )
        return duration_ms

    def log_detection(
        self, 
        treatment_type: str, 
        column: str, 
        detected: bool, 
        count: int = 0, 
        percentage: float = 0.0,
        **extra
    ) -> None:
        """Log a detection result with metrics."""
        self._logger.info(
            f"Detection [{treatment_type}] {column}: detected={detected}, count={count}, pct={percentage:.2f}%",
            extra=self._create_extra(
                event="detection",
                treatment_type=treatment_type,
                column=column,
                detected=detected,
                issue_count=count,
                issue_percentage=percentage,
                **extra
            )
        )

    def log_treatment_plan(
        self, 
        treatment_type: str, 
        column: str, 
        method: str, 
        reason: str = None,
        **extra
    ) -> None:
        """Log a treatment plan decision."""
        self._logger.info(
            f"Treatment plan [{treatment_type}] {column}: method={method}",
            extra=self._create_extra(
                event="treatment_plan",
                treatment_type=treatment_type,
                column=column,
                method=method,
                reason=reason,
                **extra
            )
        )

    def log_treatment_applied(
        self, 
        treatment_type: str, 
        column: str, 
        method: str, 
        rows_affected: int = 0,
        duration_ms: float = 0,
        **extra
    ) -> None:
        """Log a treatment application."""
        self._logger.info(
            f"Treatment applied [{treatment_type}] {column}: method={method}, rows_affected={rows_affected}",
            extra=self._create_extra(
                event="treatment_applied",
                treatment_type=treatment_type,
                column=column,
                method=method,
                rows_affected=rows_affected,
                duration_ms=round(duration_ms, 2),
                **extra
            )
        )

    def log_error(
        self, 
        operation: str, 
        error: Exception, 
        context: Dict[str, Any] = None,
        **extra
    ) -> None:
        """Log an error with full context."""
        error_context = context or {}
        self._logger.error(
            f"Error in {operation}: {type(error).__name__}: {str(error)}",
            exc_info=True,
            extra=self._create_extra(
                event="error",
                operation=operation,
                error_type=type(error).__name__,
                error_message=str(error),
                **error_context,
                **extra
            )
        )

    def log_metrics(self, operation: str, metrics: Dict[str, Any], **extra) -> None:
        """Log metrics/statistics."""
        self._logger.info(
            f"Metrics [{operation}]: {json.dumps(metrics)}",
            extra=self._create_extra(
                event="metrics",
                operation=operation,
                metrics=metrics,
                **extra
            )
        )

    def debug(self, message: str, **context) -> None:
        """Debug level log with context."""
        self._logger.debug(message, extra=self._create_extra(**context))

    def info(self, message: str, **context) -> None:
        """Info level log with context."""
        self._logger.info(message, extra=self._create_extra(**context))

    def warning(self, message: str, **context) -> None:
        """Warning level log with context."""
        self._logger.warning(message, extra=self._create_extra(**context))

    def error(self, message: str, exc_info: bool = False, **context) -> None:
        """Error level log with context."""
        self._logger.error(message, exc_info=exc_info, extra=self._create_extra(**context))


def log_execution_time(operation_name: str = None):
    """
    Decorator to log function execution time.
    
    Usage:
        @log_execution_time("outlier_detection")
        def detect_outliers(df):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            op_name = operation_name or func.__name__
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                logger.debug(
                    f"{op_name} completed in {duration_ms:.2f}ms",
                    extra={"extra_data": {"operation": op_name, "duration_ms": round(duration_ms, 2)}}
                )
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.error(
                    f"{op_name} failed after {duration_ms:.2f}ms: {e}",
                    exc_info=True,
                    extra={"extra_data": {"operation": op_name, "duration_ms": round(duration_ms, 2)}}
                )
                raise
        return wrapper
    return decorator


# Singleton instance for Data Quality logging
dq_logger = DataQualityLogger()

# Initialize from environment at import time
default_logger = setup_logging()
