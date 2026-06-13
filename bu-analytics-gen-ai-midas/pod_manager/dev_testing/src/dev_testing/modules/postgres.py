"""Postgres table existence and local-seed checks."""

from __future__ import annotations

import asyncpg
from returns.result import Failure, Result, Success

from dev_testing.config import DeployTarget, EndpointProfile
from dev_testing.results_ext import Reporter


async def run(profile: EndpointProfile, report: Reporter) -> Result[None, str]:
    if not profile.database_url:
        report(True, "postgres check skipped (no DATABASE_URL for this target)")
        return Success(None)

    prefix = profile.table_prefix
    schema = profile.schema_name
    tables = [
        f"{prefix}backend_pool",
        f"{prefix}login_pod_pool",
        f"{prefix}user_assignments",
    ]
    try:
        conn = await asyncpg.connect(dsn=profile.database_url)
    except (asyncpg.PostgresError, OSError) as exc:
        report(False, f"connect: {exc}")
        return Failure(str(exc))

    try:
        for table in tables:
            qualified = f"{schema}.{table}"
            exists = await conn.fetchval("SELECT to_regclass($1) IS NOT NULL", qualified)
            if not exists:
                report(False, f"{qualified} missing")
                return Failure(f"{qualified} missing")
            report(True, f"{qualified} exists")

        if profile.deploy_target == DeployTarget.LOCAL:
            rows = await conn.fetch(f"SELECT pod_id FROM {schema}.{prefix}backend_pool")  # noqa: S608
            ids = {row["pod_id"] for row in rows}
            if not {"backend-pool-node-0", "backend-pool-node-1"}.issubset(ids):
                report(False, f"local backend seed missing: {ids}")
                return Failure("backend seed")
            report(True, f"local backend pool seeded {sorted(ids)}")
    finally:
        await conn.close()

    return Success(None)
