"""Cross-pod / cross-process per-dataset job locks.

Layered design (top wins; falls back on failure):

1. **Phase 2 — Redis SETNX lock (cross-pod authoritative).**
   ``SET midas:dslock:<dataset_id> <token> NX PX <ttl>`` against the existing
   MIDAS ElastiCache cluster (provisioned by
   ``deploy/ecs-app/elasticache.tf``). Background heartbeat thread extends
   the TTL every ``_REDIS_LOCK_HEARTBEAT_SECONDS`` while the job runs; if a
   pod is OOM-killed the heartbeat dies with it and the TTL elapses, so no
   manual recovery is required. Release uses a compare-and-delete Lua script
   keyed on the fencing token so one job can never accidentally release
   another's lock. See ``docs/adr/0003-midas-redis-cross-pod-job-locks.md``.

2. **Phase 1 — POSIX advisory file lock (pod-local).**
   ``fcntl.flock`` on a per-dataset file under
   ``$MIDAS_DATASET_JOB_LOCK_DIR`` (default ``backend/background_locks``).
   Serialises all gunicorn worker processes on one pod. Used when Redis is
   not reachable (local dev, ElastiCache outage).

3. **Always-on — ``threading.Lock`` per dataset (in-process).**
   Collapses parallel threads inside one Python process to a single waiter;
   wraps either of the above so the in-process semantics are consistent.

The public API ``dataset_job_lock(dataset_id, job_label, ...)`` is
**unchanged**. Existing callers in ``backend/app/api/routes.py`` and the
training runners need no edits.

Why this matters (OOM-cascade context):

When two CPU-heavy jobs run concurrently on the same dataset (e.g.
VIF/correlation finishing while a manual ``train_multiple_models`` starts),
each holds its own multi-GB DataFrame copy plus algorithm state. On 4M-row
workloads pod RSS climbs into the 30-40 GiB range; a brief overlap then
trips the ``memory: 53Gi`` ceiling and the kernel OOM-kills the gunicorn
worker. All in-process job threads die with it and the user sees the
canonical ``Job was interrupted by server restart. Please retry.`` failure.

Phase 1 alone serialises within one pod. Phase 2 extends mutual exclusion
**across pods** so MIDAS can run more than one backend replica without
re-creating the same OOM race at the cluster level.

Usage::

    from app.services.job_locks import dataset_job_lock
    with dataset_job_lock(dataset_id, job_label="train_multiple_models"):
        ...do heavy CPU work here...
"""

from __future__ import annotations

import contextlib
import errno
import os
import secrets
import threading
import time
from pathlib import Path
from typing import Any, Iterator, Optional

from app.core.logging_config import get_logger

logger = get_logger(__name__)

# POSIX-only. The backend image is Debian-slim Linux, so fcntl is always
# available; on non-POSIX dev hosts (Windows) we fall back to a no-op so
# the import does not break local tooling.
try:
    import fcntl  # type: ignore[import-not-found]
    _HAVE_FCNTL = True
except ImportError:
    fcntl = None  # type: ignore[assignment]
    _HAVE_FCNTL = False

_DEFAULT_LOCK_DIR = Path(
    os.environ.get(
        "MIDAS_DATASET_JOB_LOCK_DIR",
        os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "background_locks")
        ),
    )
)

try:
    _DEFAULT_LOCK_DIR.mkdir(parents=True, exist_ok=True)
except OSError as exc:
    # If we can't write the lock directory (read-only FS in some CI
    # runners) fall back to /tmp so the import never blocks startup.
    logger.warning(
        "dataset_job_lock: cannot create %s (%s); falling back to /tmp",
        _DEFAULT_LOCK_DIR,
        exc,
    )
    _DEFAULT_LOCK_DIR = Path("/tmp/midas-dataset-job-locks")
    _DEFAULT_LOCK_DIR.mkdir(parents=True, exist_ok=True)

_THREAD_LOCKS: dict[str, threading.Lock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()

# Phase 2 — Redis lock tuning. Sensible defaults; overridable via env.
# TTL bounds the wall-clock window during which a crashed pod's lock will
# block other pods. Heartbeat extends the TTL while the job is alive.
_REDIS_LOCK_TTL_MS = int(float(os.environ.get("DATASET_LOCK_TTL_MS", str(30 * 60 * 1000))))
_REDIS_LOCK_HEARTBEAT_SECONDS = float(
    os.environ.get("DATASET_LOCK_HEARTBEAT_SECONDS", "30.0")
)
_REDIS_LOCK_KEY_PREFIX = os.environ.get("DATASET_LOCK_KEY_PREFIX", "midas:dslock:")

# Compare-and-delete Lua so we never release someone else's lock after a
# heartbeat miss or clock skew. Keyed on the fencing token issued at
# acquire time.
_REDIS_LOCK_RELEASE_LUA = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then "
    "return redis.call('del', KEYS[1]) "
    "else return 0 end"
)

# Process-wide cached Redis client. ``None`` means "not yet resolved";
# ``False`` means "resolved as unavailable, do not retry this process".
_REDIS_CLIENT_CACHE: Any = None
_REDIS_CLIENT_CACHE_LOCK = threading.Lock()


def _thread_lock_for(dataset_id: str) -> threading.Lock:
    with _THREAD_LOCKS_GUARD:
        lk = _THREAD_LOCKS.get(dataset_id)
        if lk is None:
            lk = threading.Lock()
            _THREAD_LOCKS[dataset_id] = lk
    return lk


def _lock_path(dataset_id: str) -> Path:
    safe = "".join(c for c in (dataset_id or "unknown") if c.isalnum() or c in ("-", "_")) or "unknown"
    return _DEFAULT_LOCK_DIR / f"{safe}.lock"


def _redis_key(dataset_id: str) -> str:
    """Redis key used for the cross-pod lock. Same sanitisation as the file lock path."""
    safe = "".join(c for c in (dataset_id or "unknown") if c.isalnum() or c in ("-", "_")) or "unknown"
    return f"{_REDIS_LOCK_KEY_PREFIX}{safe}"


def _resolve_redis_client() -> Any:
    """Return a connected ``redis.Redis`` client, or ``None`` if unavailable.

    Resolution order mirrors the session store
    (``app.core.session.redis_url_resolution``):

    1. ElastiCache via Secrets Manager (``SESSION_ELASTICACHE_SECRET_ARN``
       / ``SESSION_REDIS_SECRET_ID``).
    2. ``SESSION_REDIS_URL``.
    3. ``REDIS_URL``.

    Cached at module level; on first failure we cache ``False`` so we do
    not pay the resolution cost on every lock acquire. Set the env var
    ``DATASET_LOCK_REDIS_DISABLED=1`` to force the fcntl/thread fallback
    (useful for local dev without ElastiCache).
    """
    global _REDIS_CLIENT_CACHE
    if _REDIS_CLIENT_CACHE is not None:
        return _REDIS_CLIENT_CACHE if _REDIS_CLIENT_CACHE is not False else None

    with _REDIS_CLIENT_CACHE_LOCK:
        if _REDIS_CLIENT_CACHE is not None:
            return _REDIS_CLIENT_CACHE if _REDIS_CLIENT_CACHE is not False else None

        if os.environ.get("DATASET_LOCK_REDIS_DISABLED", "").lower() in {"1", "true", "yes"}:
            logger.info(
                "dataset_job_lock: Redis disabled via DATASET_LOCK_REDIS_DISABLED; "
                "using pod-local fcntl+thread fallback",
                extra={"event": "dataset_job_lock_redis_disabled"},
            )
            _REDIS_CLIENT_CACHE = False
            return None

        try:
            import redis  # type: ignore[import-not-found]
            from app.core.session.redis_url_resolution import (  # type: ignore[import-not-found]
                build_default_redis_url_chain,
            )
        except ImportError as exc:
            logger.warning(
                "dataset_job_lock: redis client or URL resolver unavailable (%s); "
                "falling back to pod-local fcntl+thread lock",
                exc,
                extra={"event": "dataset_job_lock_redis_unavailable"},
            )
            _REDIS_CLIENT_CACHE = False
            return None

        try:
            url = build_default_redis_url_chain().resolve()
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(
                "dataset_job_lock: failed to resolve Redis URL (%s); using fcntl fallback",
                exc,
                extra={"event": "dataset_job_lock_redis_unavailable"},
            )
            _REDIS_CLIENT_CACHE = False
            return None

        if not url:
            logger.info(
                "dataset_job_lock: no Redis URL configured; using pod-local fcntl+thread lock",
                extra={"event": "dataset_job_lock_redis_unavailable"},
            )
            _REDIS_CLIENT_CACHE = False
            return None

        try:
            client = redis.Redis.from_url(
                url,
                socket_connect_timeout=3.0,
                socket_timeout=3.0,
                health_check_interval=30,
            )
            client.ping()
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(
                "dataset_job_lock: Redis ping failed (%s); using fcntl fallback",
                exc,
                extra={"event": "dataset_job_lock_redis_unavailable"},
            )
            _REDIS_CLIENT_CACHE = False
            return None

        logger.info(
            "dataset_job_lock: Redis cross-pod lock backend active",
            extra={"event": "dataset_job_lock_backend_redis"},
        )
        _REDIS_CLIENT_CACHE = client
        return client


class DatasetJobLockTimeout(RuntimeError):
    """Raised when ``dataset_job_lock`` cannot be acquired before timeout."""


@contextlib.contextmanager
def _redis_lock(
    dataset_id: str,
    job_label: str,
    *,
    wait: bool,
    timeout_seconds: Optional[float],
    poll_interval: float,
    log_every: float,
) -> Iterator[bool]:
    """Acquire a cross-pod Redis lock; yield True on success, False if Redis is unavailable.

    On failure to reach Redis the context manager yields False so the
    caller can fall back to the fcntl path. On a real lock-acquire
    timeout it raises ``DatasetJobLockTimeout``.
    """
    client = _resolve_redis_client()
    if client is None:
        yield False
        return

    key = _redis_key(dataset_id)
    token = secrets.token_hex(16)
    waited_for = 0.0
    last_log = -1.0
    deadline = (
        time.monotonic() + timeout_seconds
        if timeout_seconds is not None
        else None
    )

    while True:
        try:
            acquired = bool(
                client.set(key, token, nx=True, px=_REDIS_LOCK_TTL_MS)
            )
        except Exception as exc:  # pylint: disable=broad-except
            # Connection blip: surface a warning, fall back to fcntl.
            logger.warning(
                "dataset_job_lock: Redis SETNX failed (%s); "
                "falling back to fcntl for dataset=%s job=%s",
                exc, dataset_id, job_label,
                extra={
                    "event": "dataset_job_lock_redis_error",
                    "dataset_id": dataset_id,
                    "job_label": job_label,
                },
            )
            yield False
            return

        if acquired:
            if waited_for > 0:
                logger.info(
                    "dataset_job_lock acquired (redis) after %.1fs "
                    "wait: dataset=%s job=%s",
                    waited_for, dataset_id, job_label,
                    extra={
                        "event": "dataset_job_lock_acquired",
                        "backend": "redis",
                        "dataset_id": dataset_id,
                        "job_label": job_label,
                        "wait_seconds": waited_for,
                    },
                )
            else:
                logger.info(
                    "dataset_job_lock acquired (redis): dataset=%s job=%s",
                    dataset_id, job_label,
                    extra={
                        "event": "dataset_job_lock_acquired",
                        "backend": "redis",
                        "dataset_id": dataset_id,
                        "job_label": job_label,
                        "wait_seconds": 0.0,
                    },
                )
            break

        if not wait:
            raise DatasetJobLockTimeout(
                f"Another job is already running for dataset {dataset_id}"
            )
        if deadline is not None and time.monotonic() >= deadline:
            raise DatasetJobLockTimeout(
                f"dataset_job_lock: gave up after {timeout_seconds:.0f}s "
                f"waiting for dataset={dataset_id}"
            )
        if last_log < 0 or (waited_for - last_log) >= log_every:
            logger.info(
                "dataset_job_lock waiting (redis, %.1fs): "
                "dataset=%s job=%s",
                waited_for, dataset_id, job_label,
                extra={
                    "event": "dataset_job_lock_waiting",
                    "backend": "redis",
                    "dataset_id": dataset_id,
                    "job_label": job_label,
                    "wait_seconds": waited_for,
                },
            )
            last_log = waited_for
        time.sleep(poll_interval)
        waited_for += poll_interval

    # Heartbeat: extend TTL every _REDIS_LOCK_HEARTBEAT_SECONDS while the
    # job runs. Daemon thread dies with the pod, so an OOM-killed pod's
    # lock naturally expires after _REDIS_LOCK_TTL_MS.
    stop_heartbeat = threading.Event()

    def _heartbeat() -> None:
        while not stop_heartbeat.wait(_REDIS_LOCK_HEARTBEAT_SECONDS):
            try:
                client.pexpire(key, _REDIS_LOCK_TTL_MS)
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning(
                    "dataset_job_lock heartbeat (redis) failed for "
                    "dataset=%s job=%s: %s",
                    dataset_id, job_label, exc,
                    extra={
                        "event": "dataset_job_lock_heartbeat_failed",
                        "dataset_id": dataset_id,
                        "job_label": job_label,
                    },
                )
                return

    hb_thread = threading.Thread(
        target=_heartbeat,
        name=f"dataset-job-lock-hb-{dataset_id}",
        daemon=True,
    )
    hb_thread.start()

    try:
        yield True
    finally:
        stop_heartbeat.set()
        try:
            client.eval(_REDIS_LOCK_RELEASE_LUA, 1, key, token)
        except Exception as exc:  # pylint: disable=broad-except
            # Best-effort release; if it fails the TTL will reap the lock.
            logger.warning(
                "dataset_job_lock release (redis) failed for "
                "dataset=%s job=%s: %s",
                dataset_id, job_label, exc,
                extra={
                    "event": "dataset_job_lock_release_failed",
                    "dataset_id": dataset_id,
                    "job_label": job_label,
                },
            )
        logger.info(
            "dataset_job_lock released (redis): dataset=%s job=%s",
            dataset_id, job_label,
            extra={
                "event": "dataset_job_lock_released",
                "backend": "redis",
                "dataset_id": dataset_id,
                "job_label": job_label,
            },
        )


@contextlib.contextmanager
def _fcntl_pod_lock(
    dataset_id: str,
    job_label: str,
    *,
    wait: bool,
    timeout_seconds: Optional[float],
    poll_interval: float,
    log_every: float,
) -> Iterator[None]:
    """Pod-local Phase 1 lock: POSIX advisory ``fcntl.flock`` on a per-dataset file.

    Identical semantics to the previous module-level implementation, just
    extracted so the Redis path can fall back to it cleanly.
    """
    lock_file_path = _lock_path(dataset_id)
    fp = open(lock_file_path, "w", encoding="utf-8")
    try:
        if _HAVE_FCNTL:
            waited_for = 0.0
            last_log = -1.0
            while True:
                try:
                    fcntl.flock(  # type: ignore[union-attr]
                        fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB
                    )
                    if waited_for > 0:
                        logger.info(
                            "dataset_job_lock acquired (fcntl) after "
                            "%.1fs wait: dataset=%s job=%s",
                            waited_for, dataset_id, job_label,
                            extra={
                                "event": "dataset_job_lock_acquired",
                                "backend": "fcntl",
                                "dataset_id": dataset_id,
                                "job_label": job_label,
                                "wait_seconds": waited_for,
                            },
                        )
                    else:
                        logger.info(
                            "dataset_job_lock acquired (fcntl): "
                            "dataset=%s job=%s",
                            dataset_id, job_label,
                            extra={
                                "event": "dataset_job_lock_acquired",
                                "backend": "fcntl",
                                "dataset_id": dataset_id,
                                "job_label": job_label,
                                "wait_seconds": 0.0,
                            },
                        )
                    break
                except (BlockingIOError, OSError) as exc:
                    ecode = getattr(exc, "errno", None)
                    if ecode not in (
                        errno.EAGAIN, errno.EACCES, errno.EWOULDBLOCK
                    ):
                        raise
                    if not wait:
                        raise DatasetJobLockTimeout(
                            f"Another job is already running for "
                            f"dataset {dataset_id}"
                        ) from exc
                    if (
                        timeout_seconds is not None
                        and waited_for >= timeout_seconds
                    ):
                        raise DatasetJobLockTimeout(
                            f"dataset_job_lock: gave up after "
                            f"{timeout_seconds:.0f}s waiting for "
                            f"dataset={dataset_id}"
                        ) from exc
                    if last_log < 0 or (waited_for - last_log) >= log_every:
                        logger.info(
                            "dataset_job_lock waiting (fcntl, %.1fs): "
                            "dataset=%s job=%s",
                            waited_for, dataset_id, job_label,
                            extra={
                                "event": "dataset_job_lock_waiting",
                                "backend": "fcntl",
                                "dataset_id": dataset_id,
                                "job_label": job_label,
                                "wait_seconds": waited_for,
                            },
                        )
                        last_log = waited_for
                    time.sleep(poll_interval)
                    waited_for += poll_interval
        else:
            logger.warning(
                "dataset_job_lock: fcntl unavailable on this platform; "
                "lock degrades to in-process only for dataset=%s job=%s",
                dataset_id, job_label,
                extra={
                    "event": "dataset_job_lock_thread_only",
                    "dataset_id": dataset_id,
                    "job_label": job_label,
                },
            )
        yield
    finally:
        if _HAVE_FCNTL:
            try:
                fcntl.flock(  # type: ignore[union-attr]
                    fp.fileno(), fcntl.LOCK_UN
                )
            except OSError:
                pass
        try:
            fp.close()
        except OSError:
            pass
        logger.info(
            "dataset_job_lock released (fcntl): dataset=%s job=%s",
            dataset_id, job_label,
            extra={
                "event": "dataset_job_lock_released",
                "backend": "fcntl",
                "dataset_id": dataset_id,
                "job_label": job_label,
            },
        )


@contextlib.contextmanager
def dataset_job_lock(
    dataset_id: str,
    job_label: str,
    *,
    wait: bool = True,
    timeout_seconds: Optional[float] = None,
    poll_interval: float = 2.0,
    log_every: float = 30.0,
) -> Iterator[None]:
    """Hold an exclusive lock on ``dataset_id`` for the duration of the with block.

    Acquisition order:

    1. ``threading.Lock`` per dataset (always; collapses in-process waiters).
    2. **Redis** ``SETNX`` lock if ElastiCache is reachable (cross-pod
       authoritative).
    3. ``fcntl.flock`` file lock if Redis is unavailable (pod-local).

    Args:
        dataset_id: Dataset identifier the lock is keyed on. Two jobs
            for different datasets do not contend.
        job_label: Human-readable label included in log lines so
            operators can see who is holding the lock.
        wait: If True (default) blocks until the lock is free. If False
            and the lock is held, raises ``DatasetJobLockTimeout``
            immediately.
        timeout_seconds: When ``wait`` is True, give up after this many
            seconds and raise ``DatasetJobLockTimeout``. ``None`` means
            wait forever (the daemon thread is cheap; the gunicorn
            ``--timeout`` ceiling already caps the upper bound).
        poll_interval: Seconds between non-blocking acquire attempts.
        log_every: Seconds between waiter log lines.
    """
    thread_lk = _thread_lock_for(dataset_id)
    if not wait:
        acquired_thread = thread_lk.acquire(blocking=False)
    else:
        acquired_thread = thread_lk.acquire(
            timeout=(timeout_seconds if timeout_seconds is not None else -1)
        )
    if not acquired_thread:
        raise DatasetJobLockTimeout(
            f"dataset_job_lock: timed out waiting for in-process lock on {dataset_id}"
        )
    try:
        # Try Redis first (cross-pod). If Redis is unreachable, _redis_lock
        # yields False and we fall through to fcntl.
        with _redis_lock(
            dataset_id,
            job_label,
            wait=wait,
            timeout_seconds=timeout_seconds,
            poll_interval=poll_interval,
            log_every=log_every,
        ) as got_redis:
            if got_redis:
                yield
                return

        # Redis was unavailable - use pod-local fcntl.
        with _fcntl_pod_lock(
            dataset_id,
            job_label,
            wait=wait,
            timeout_seconds=timeout_seconds,
            poll_interval=poll_interval,
            log_every=log_every,
        ):
            yield
    finally:
        thread_lk.release()
