"""In-process metrics hooks (OP-8) — export via logs until platform wiring."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from collections.abc import Iterator

logger = logging.getLogger(__name__)

_ext_authz_duration_ms: list[float] = []
_reconcile_duration_ms: list[float] = []


@contextmanager
def observe_ext_authz_check() -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        _ext_authz_duration_ms.append(elapsed_ms)
        if len(_ext_authz_duration_ms) > 1000:
            _ext_authz_duration_ms.pop(0)
        logger.debug("metric ext_authz_check_duration_ms=%.2f", elapsed_ms)


@contextmanager
def observe_reconcile_cycle() -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        _reconcile_duration_ms.append(elapsed_ms)
        logger.debug("metric reconcile_duration_ms=%.2f", elapsed_ms)


def log_pool_gauges(*, free_count: int, claimed_count: int) -> None:
    logger.info(
        "metric pool_free_count=%d pool_claimed_count=%d",
        free_count,
        claimed_count,
    )


def log_authz_cache(*, hits: int, misses: int) -> None:
    logger.debug("metric authz_cache_hits=%d authz_cache_misses=%d", hits, misses)
