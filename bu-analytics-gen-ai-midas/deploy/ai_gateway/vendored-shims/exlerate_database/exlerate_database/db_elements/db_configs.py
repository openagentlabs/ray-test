"""DB connection configs for the MIDAS `exlerate_database` shim.

Only the three names the c1-api source actually imports are defined:

    from exlerate_database.db_elements.db_configs import (
        BaseDbConnectionConfig, DbCredentials, MigratorDbConnectionConfig,
    )

See `..__init__.py` for the design rationale.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class DbCredentials:
    user: Optional[str]
    password: Optional[str]


@dataclass
class BaseDbConnectionConfig:
    host: Optional[str]
    port: int
    dbname: str
    credentials: DbCredentials
    sslmode: str = "prefer"

    @classmethod
    def for_migrator_account(cls) -> "BaseDbConnectionConfig":
        """Fallback that reads the framework's canonical env vars.

        The c1-api's `C2DdlTracker` overrides `_get_db_config()` with its own
        env-var mapping, so this classmethod is effectively unreachable in
        production — it exists only because the upstream package surfaces it
        and a tracker that forgot to override would otherwise crash at import
        time.
        """
        return cls(
            host=os.getenv("DB_HOST"),
            port=int(os.getenv("DB_PORT", "5432")),
            dbname=os.getenv("DB_NAME", "postgres"),
            sslmode=os.getenv("DB_SSLMODE", "prefer"),
            credentials=DbCredentials(
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
            ),
        )


@dataclass
class MigratorDbConnectionConfig(BaseDbConnectionConfig):
    """Alias type — semantically represents the privileged migrator account."""

    @classmethod
    def for_migrator_account(cls) -> "MigratorDbConnectionConfig":  # type: ignore[override]
        base = BaseDbConnectionConfig.for_migrator_account()
        return cls(
            host=base.host,
            port=base.port,
            dbname=base.dbname,
            sslmode=base.sslmode,
            credentials=base.credentials,
        )


__all__ = [
    "BaseDbConnectionConfig",
    "DbCredentials",
    "MigratorDbConnectionConfig",
]
