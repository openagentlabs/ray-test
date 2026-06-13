"""Logical pool identifiers for routing-tier node registries."""

from __future__ import annotations

from typing import Final

BACKEND_POOL: Final[str] = "backend_pool"
LOGIN_POD_POOL: Final[str] = "login_pod_pool"

ALL_POOL_KINDS: Final[tuple[str, ...]] = (BACKEND_POOL, LOGIN_POD_POOL)
