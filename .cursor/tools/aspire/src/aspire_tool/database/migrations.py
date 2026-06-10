"""SQLite migrations for `registered_services` (keep aligned with `aspire.svc/lib/database/`)."""

from __future__ import annotations

import sqlite3

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


def ensure_registered_services_columns_sync(conn: sqlite3.Connection) -> None:
    cur = conn.execute("PRAGMA table_info(registered_services)")
    names = {row[1] for row in cur.fetchall()}
    if "auto_start_with_home" not in names:
        conn.execute(
            "ALTER TABLE registered_services ADD COLUMN auto_start_with_home INTEGER NOT NULL DEFAULT 0",
        )


async def ensure_registered_services_columns_async(conn: AsyncConnection) -> None:
    result = await conn.execute(text("PRAGMA table_info(registered_services)"))
    rows = result.fetchall()
    names = {row[1] for row in rows}
    if "auto_start_with_home" not in names:
        await conn.execute(
            text(
                "ALTER TABLE registered_services ADD COLUMN auto_start_with_home INTEGER NOT NULL DEFAULT 0",
            ),
        )
