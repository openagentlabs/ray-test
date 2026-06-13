"""
Shared ThreadPoolExecutor singleton.

Use this executor for all run_in_executor calls so the process keeps a
single, bounded thread pool instead of creating ad-hoc pools per request.

Usage in route handlers:
    from app.core.executor import executor
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, sync_fn, *args)

Or via the FastAPI request object (wired in main.py):
    request.app.state.executor
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Default sizing (P1.6):
#   Threads inside a single Python process share memory and are cheap.
#   They serve CPU-bound run_in_executor calls (pandas reads, DQS,
#   column-info, variable review). Sized at 4 * CPU count, capped at 32,
#   because most work is dominated by GIL-released numeric kernels
#   (numpy/pandas/pyarrow) and we want headroom for concurrent users
#   on a single Gunicorn worker without queueing.
_default_workers = min(
    int(os.getenv("EXECUTOR_MAX_WORKERS", "0"))
    or (os.cpu_count() or 4) * 4,
    32,
)

executor = ThreadPoolExecutor(
    max_workers=_default_workers,
    thread_name_prefix="midas-worker",
)

logger.info(
    "Shared ThreadPoolExecutor initialised with max_workers=%s",
    _default_workers,
)


def shutdown_executor() -> None:
    """Gracefully shut down the executor. Called from main.py on app shutdown."""
    logger.info("Shutting down shared ThreadPoolExecutor")
    executor.shutdown(wait=True)
