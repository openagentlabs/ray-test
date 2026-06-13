"""TrackingTableManager — Flyway-style applied-version tracking on Postgres.

psycopg3 sync implementation. Each tracker gets its own `schema_version_<category>`
table in its configured schema. Idempotent by design: `ensure_tracking_table_exists`
only creates if missing, and `apply_version` is a single transaction that fails
loudly on conflict so the executor can surface a clear error.
"""
from __future__ import annotations

import datetime as _dt
import logging
from typing import Set

import psycopg

from ..db_elements.db_configs import BaseDbConnectionConfig

logger = logging.getLogger(__name__)


def _build_conninfo(cfg: BaseDbConnectionConfig) -> str:
    parts = [
        f"host={cfg.host}",
        f"port={cfg.port}",
        f"dbname={cfg.dbname}",
        f"sslmode={cfg.sslmode}",
    ]
    if cfg.credentials and cfg.credentials.user:
        parts.append(f"user={cfg.credentials.user}")
    if cfg.credentials and cfg.credentials.password:
        parts.append(f"password={cfg.credentials.password}")
    return " ".join(parts)


class TrackingTableManager:
    """Owns the `<schema>.schema_version_<category>` tracking table."""

    def __init__(
        self,
        migrator_db_config: BaseDbConnectionConfig,
        category: str,
        version_table_schema: str = "public",
        init_stmt: str = "",
    ) -> None:
        self._config = migrator_db_config
        self.category = category
        self.schema = version_table_schema
        self.init_stmt = init_stmt

    # ----------------------------------------------------------------- table
    @property
    def qualified_table(self) -> str:
        return f'"{self.schema}"."schema_version_{self.category}"'

    def ensure_tracking_table_exists(self) -> None:
        create_sql = f"""
            CREATE SCHEMA IF NOT EXISTS "{self.schema}";
            CREATE TABLE IF NOT EXISTS {self.qualified_table} (
                version        VARCHAR(64) PRIMARY KEY,
                description    TEXT NOT NULL,
                checksum       CHAR(64) NOT NULL,
                installed_on   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                installed_by   TEXT NOT NULL DEFAULT CURRENT_USER,
                execution_time INTERVAL,
                success        BOOLEAN NOT NULL DEFAULT TRUE
            );
        """
        with psycopg.connect(_build_conninfo(self._config), autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(create_sql)
                if self.init_stmt:
                    logger.info(
                        "Running init_stmt for category '%s'", self.category
                    )
                    cur.execute(self.init_stmt)
        logger.info("Ensured tracking table %s", self.qualified_table)

    # ---------------------------------------------------------------- reads
    def get_applied_versions(self) -> Set[str]:
        query = f"SELECT version FROM {self.qualified_table} WHERE success = TRUE"
        with psycopg.connect(_build_conninfo(self._config)) as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                return {row[0] for row in cur.fetchall()}

    # ---------------------------------------------------------------- apply
    def apply_version(
        self,
        version: str,
        description: str,
        checksum: str,
        sql: str,
    ) -> None:
        """Run `sql` + record the version, all inside one transaction.

        `psycopg.connect(...)` with autocommit=False (the default) will roll
        back the whole operation on any exception, giving us exactly the
        Flyway-style all-or-nothing semantics the framework promises.
        """
        started = _dt.datetime.now(_dt.timezone.utc)

        with psycopg.connect(_build_conninfo(self._config)) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                elapsed = _dt.datetime.now(_dt.timezone.utc) - started
                cur.execute(
                    f"""
                    INSERT INTO {self.qualified_table}
                        (version, description, checksum, execution_time, success)
                    VALUES (%s, %s, %s, %s, TRUE)
                    """,
                    (version, description, checksum, elapsed),
                )
            conn.commit()

        logger.info(
            "Applied version %s (%s) in %s",
            version,
            self.category,
            elapsed,
        )


__all__ = ["TrackingTableManager"]
