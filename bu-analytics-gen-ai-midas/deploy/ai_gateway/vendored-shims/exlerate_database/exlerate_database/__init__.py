"""MIDAS shim for exlerate_database.

Implements the Flyway-style versioned-migration runner surface used by the
c1-api source tree. Backed by psycopg (sync, libpq) because the migrations
are idempotent DDL statements that run once at pod startup and must not
hold connections open.

Public surface (matches what `ai_gateway/src/aigtw_c1_api/` imports):

    from exlerate_database import DbVersionExecutor, DbVersionTracker, Version
    from exlerate_database.db_elements.db_configs import (
        BaseDbConnectionConfig, DbCredentials, MigratorDbConnectionConfig,
    )
    from exlerate_database.migrating.tracking_table_manager import TrackingTableManager

See `deploy/ai_gateway/vendored-shims/exlerate_database/pyproject.toml` for the
intent and why this shim exists (zero JFrog at build and runtime — MIDAS arch
rule Q15.2).
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Version:
    """A single versioned migration.

    The upstream corporate package exposes only these two attributes. `version`
    is the zero-padded migration number (e.g. "0001") and `version_file` is an
    absolute path to a `.sql` file whose contents are executed in a single
    transaction.
    """

    version: str
    version_file: str


# ---------------------------------------------------------------------------
# DbVersionTracker
# ---------------------------------------------------------------------------


_VERSION_METHOD_RE = re.compile(r"^v_(\d+)$")


class DbVersionTracker:
    """Abstract base: subclasses define `v_NNNN(self) -> Version` methods.

    Mirrors the corporate package's shape:

    * `category` — logical bucket (e.g. "ddl", "dml"). Flows into the tracking
      table name.
    * `version_table_schema` — Postgres schema the tracking table lives in.
    * `init_stmt` — optional SQL run once before any migration (e.g. to create
      the target schema). Left as an empty string by default.
    * `_get_db_config()` — returns a `BaseDbConnectionConfig`. Subclasses
      override to plug in their own env-var naming scheme.
    * `get_tracking_manager()` — returns a `TrackingTableManager` bound to the
      same DB config as the migrations themselves.
    * `get_execution_order()` — integer ordering across trackers (lower runs
      first).
    * `get_db_tracker_description()` — human-readable label for logs.
    """

    def __init__(
        self,
        category: str,
        version_table_schema: str = "public",
        init_stmt: str = "",
    ) -> None:
        self.category = category
        self.version_table_schema = version_table_schema
        self.init_stmt = init_stmt

    # ------------------------------------------------------------------ config
    def _get_db_config(self) -> "BaseDbConnectionConfig":  # pragma: no cover
        from .db_elements.db_configs import BaseDbConnectionConfig
        return BaseDbConnectionConfig.for_migrator_account()

    def get_tracking_manager(self) -> "TrackingTableManager":
        from .migrating.tracking_table_manager import TrackingTableManager
        config = self._get_db_config()
        return TrackingTableManager(
            migrator_db_config=config,
            category=self.category,
            version_table_schema=self.version_table_schema,
            init_stmt=self.init_stmt,
        )

    # -------------------------------------------------------------- metadata
    def get_execution_order(self) -> int:
        return 100

    def get_db_tracker_description(self) -> str:
        return self.__class__.__name__

    # -------------------------------------------------------------- versions
    def _iter_versions(self) -> Iterable[Version]:
        """Discover every `v_NNNN` method on the subclass, in numeric order."""
        pairs: List[tuple] = []
        for attr in dir(self):
            match = _VERSION_METHOD_RE.match(attr)
            if not match:
                continue
            method = getattr(self, attr)
            if not callable(method):
                continue
            pairs.append((int(match.group(1)), attr, method))
        pairs.sort()
        for _, _, method in pairs:
            version = method()
            if not isinstance(version, Version):
                raise TypeError(
                    f"{self.__class__.__name__}.{method.__name__}() must return "
                    f"a Version, got {type(version).__name__}"
                )
            yield version


# ---------------------------------------------------------------------------
# DbVersionExecutor
# ---------------------------------------------------------------------------


class DbVersionExecutor:
    """Runs every tracker's pending versions in tracker-order."""

    def __init__(self, trackers: Sequence[DbVersionTracker]) -> None:
        self._trackers = sorted(
            list(trackers), key=lambda t: t.get_execution_order()
        )

    def run_all(self) -> None:
        for tracker in self._trackers:
            description = tracker.get_db_tracker_description()
            logger.info("Running migrations for tracker: %s", description)
            self._run_tracker(tracker)
            logger.info("Completed migrations for tracker: %s", description)

    # ------------------------------------------------------------------ impl
    def _run_tracker(self, tracker: DbVersionTracker) -> None:
        manager = tracker.get_tracking_manager()
        manager.ensure_tracking_table_exists()
        already_applied = manager.get_applied_versions()

        for version in tracker._iter_versions():
            if version.version in already_applied:
                logger.info(
                    "Skipping already-applied version %s (%s)",
                    version.version,
                    tracker.category,
                )
                continue

            file_path = Path(version.version_file)
            if not file_path.is_file():
                raise FileNotFoundError(
                    f"Migration file not found: {file_path}"
                )

            sql = file_path.read_text(encoding="utf-8")
            checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()

            logger.info(
                "Applying version %s (%s) — %s",
                version.version,
                tracker.category,
                file_path.name,
            )
            manager.apply_version(
                version=version.version,
                description=file_path.stem,
                checksum=checksum,
                sql=sql,
            )


__all__ = [
    "DbVersionExecutor",
    "DbVersionTracker",
    "Version",
]
