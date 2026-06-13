"""Shared Postgres-first / SQLite-fallback plumbing for the model DB files.

Exposes two key helpers:

* ``connect(path)`` - returns either a real :mod:`sqlite3` connection to
  ``path`` or a :class:`_PgConnection` adapter that speaks the
  ``sqlite3``-style API (``cursor()``, ``commit()``, ``rowcount``,
  ``lastrowid``, row factory) but routes through :mod:`psycopg2`.
* ``BACKEND`` - ``"postgres"`` or ``"sqlite"``, decided once at import time via
  a short connectivity probe.

The adapter translates SQL for Postgres on the fly:

* ``?`` placeholders → ``%s``
* ``AUTOINCREMENT`` → removed; ``INTEGER PRIMARY KEY`` → ``BIGSERIAL PRIMARY KEY``
* ``INSERT OR REPLACE INTO ...`` → ``INSERT ... ON CONFLICT DO NOTHING`` warning
  (callers that rely on REPLACE semantics should use ``ON CONFLICT DO UPDATE``
  directly - only :mod:`app.models.database` uses ``INSERT OR REPLACE`` and it
  has its own Postgres implementation).
* ``PRAGMA table_info(T)`` → ``information_schema`` query returning rows
  shaped like SQLite's PRAGMA output.
* ``datetime('now', '-N days')`` → ``NOW() - INTERVAL '<N> days'``
* ``ALTER TABLE ... RENAME COLUMN ...`` - works unchanged on Postgres >= 9.2.

Mapped errors:

* Postgres ``UndefinedColumn`` / ``UndefinedTable`` are re-raised as
  :class:`sqlite3.OperationalError` so existing ``try / except OperationalError``
  migration blocks behave the same.

``commit()`` outside a transaction is a no-op on Postgres. Connections are
opened with ``autocommit=False`` and committed explicitly, matching SQLite
semantics used throughout the codebase.
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, List, Optional, Union

logger = logging.getLogger(__name__)


def coerce_datetime(value: Any) -> Optional[datetime]:
    """Normalize a timestamp value read from either Postgres or SQLite.

    Postgres (psycopg2) returns a native :class:`datetime` for ``TIMESTAMP``
    columns, while SQLite returns an ISO-8601 string. Callers building a
    pydantic model from a ``cursor.fetchone()`` row should funnel every
    ``created_at`` / ``updated_at`` / ``expires_at`` through this helper so
    the same code path works regardless of backend.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value)
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        try:
            return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")


# ---------------------------------------------------------------------------
# Health check & backend selection (runs once at import time)
# ---------------------------------------------------------------------------
def _resolve_database_url() -> Optional[str]:
    """Return a Postgres URL if configured, else ``None``.

    Checks ``DATABASE_URL`` env var first (populated by ``main.py`` startup or
    docker-compose); if absent, builds one from the AWS Secrets Manager RDS
    bundle so this module works even when imported before the FastAPI startup
    event has run.
    """
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if url and url.startswith(("postgres://", "postgresql://", "postgresql+")):
        if url.startswith("postgresql+psycopg2://"):
            url = url.replace("postgresql+psycopg2://", "postgresql://", 1)
        return url
    try:
        from app.core.config import settings
        from app.core.secrets.loader import load_application_secrets_bundle

        bundle = load_application_secrets_bundle(settings)
        if bundle.rds_postgres is not None:
            sslm = (settings.AWS_RDS_POSTGRES_SSLMODE or "").strip() or None
            url = bundle.rds_postgres.sqlalchemy_url(sslmode=sslm)
            if url and url.startswith("postgresql+psycopg2://"):
                url = url.replace("postgresql+psycopg2://", "postgresql://", 1)
            return url
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Could not resolve RDS bundle for Postgres URL: %s", exc)
    return None


def _probe_postgres(database_url: str) -> bool:
    try:
        import psycopg2  # type: ignore

        with psycopg2.connect(database_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return True
    except Exception as exc:
        logger.warning("Postgres health check failed: %s", exc)
        return False


_DATABASE_URL: Optional[str] = _resolve_database_url()
BACKEND: str = "postgres" if (_DATABASE_URL and _probe_postgres(_DATABASE_URL)) else "sqlite"

if BACKEND == "postgres":
    logger.info("Model DBs using backend=postgres")
else:
    if _DATABASE_URL:
        logger.warning("Postgres not usable; model DBs falling back to SQLite")
    else:
        logger.info("No DATABASE_URL configured; model DBs using SQLite")


# ---------------------------------------------------------------------------
# SQL translation (SQLite -> Postgres)
# ---------------------------------------------------------------------------
_CREATE_TABLE_AUTOINC_RE = re.compile(
    r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT", re.IGNORECASE,
)
_AUTOINC_ONLY_RE = re.compile(r"\s+AUTOINCREMENT", re.IGNORECASE)
_PRAGMA_TABLE_INFO_RE = re.compile(
    r"^\s*PRAGMA\s+table_info\s*\(\s*([\w\"']+)\s*\)\s*$", re.IGNORECASE,
)
_DATETIME_NOW_DAYS_RE = re.compile(
    r"datetime\(\s*'now'\s*,\s*'\-\s*(\d+)\s*days'\s*\)", re.IGNORECASE,
)
_BEGIN_IMMEDIATE_RE = re.compile(r"^\s*BEGIN\s+IMMEDIATE\s*$", re.IGNORECASE)

# INSERT OR REPLACE INTO <table> (<cols>) VALUES (<vals>)
# Captures: table, column list, values list. Used to rewrite into
# Postgres's ``INSERT ... ON CONFLICT (<pk>) DO UPDATE SET ...``.
_INSERT_OR_REPLACE_RE = re.compile(
    r"INSERT\s+OR\s+REPLACE\s+INTO\s+(\w+)\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)",
    re.IGNORECASE | re.DOTALL,
)

# Detect a plain INSERT to extract target table (to auto-append RETURNING <pk>)
_PLAIN_INSERT_RE = re.compile(
    r"^\s*INSERT\s+INTO\s+(\w+)\b", re.IGNORECASE,
)

# Table -> conflict column (primary-key column) used when translating
# ``INSERT OR REPLACE``. If a table is not in this map we fall back to
# ``ON CONFLICT DO NOTHING`` with a warning, since we cannot infer the PK.
_PK_COLUMN_BY_TABLE: dict = {
    "message_states": "dataset_id",
    "evaluation_models": "id",
    "projects": "id",
    "users": "id",
}

# Tables whose primary key is a server-generated integer (BIGSERIAL). For
# plain ``INSERT INTO <table> ...`` statements the adapter will automatically
# append ``RETURNING <pk>`` so that ``cursor.lastrowid`` works on Postgres.
_SERIAL_PK_TABLES = {"users", "refresh_tokens"}


def _translate_insert_or_replace(sql: str) -> str:
    """Rewrite SQLite ``INSERT OR REPLACE`` to Postgres ``ON CONFLICT DO UPDATE``."""

    def _repl(m: "re.Match") -> str:
        table = m.group(1).strip()
        cols_raw = m.group(2)
        vals_raw = m.group(3)
        cols = [c.strip() for c in cols_raw.split(",")]
        pk = _PK_COLUMN_BY_TABLE.get(table)
        if pk is None:
            logger.warning(
                "INSERT OR REPLACE on unknown table %s: using ON CONFLICT DO NOTHING", table
            )
            return f"INSERT INTO {table} ({cols_raw}) VALUES ({vals_raw}) ON CONFLICT DO NOTHING"
        update_cols = [c for c in cols if c != pk]
        set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
        if not set_clause:
            return f"INSERT INTO {table} ({cols_raw}) VALUES ({vals_raw}) ON CONFLICT ({pk}) DO NOTHING"
        return (
            f"INSERT INTO {table} ({cols_raw}) VALUES ({vals_raw}) "
            f"ON CONFLICT ({pk}) DO UPDATE SET {set_clause}"
        )

    return _INSERT_OR_REPLACE_RE.sub(_repl, sql)


def _translate_sql_for_postgres(sql: str) -> str:
    """Translate SQLite SQL to Postgres-compatible SQL.

    Only the transformations actually used in the four model DB files are
    handled; this is not a general purpose SQLite dialect converter.
    """
    out = sql

    # INSERT OR REPLACE INTO T (...) VALUES (...) -> INSERT ... ON CONFLICT (pk) DO UPDATE SET ...
    out = _translate_insert_or_replace(out)

    # INTEGER PRIMARY KEY AUTOINCREMENT -> BIGSERIAL PRIMARY KEY
    out = _CREATE_TABLE_AUTOINC_RE.sub("BIGSERIAL PRIMARY KEY", out)
    # Any remaining AUTOINCREMENT keyword (e.g. from migration CREATE TABLEs)
    out = _AUTOINC_ONLY_RE.sub("", out)

    # datetime('now', '-N days') -> NOW() - INTERVAL 'N days'
    out = _DATETIME_NOW_DAYS_RE.sub(lambda m: f"NOW() - INTERVAL '{m.group(1)} days'", out)

    # BEGIN IMMEDIATE -> BEGIN (Postgres has no IMMEDIATE lock variant)
    if _BEGIN_IMMEDIATE_RE.match(out):
        out = "BEGIN"

    # SQLite ``BOOLEAN DEFAULT FALSE/TRUE`` already valid in Postgres.
    # ``TIMESTAMP DEFAULT CURRENT_TIMESTAMP`` already valid.
    # ``TEXT DEFAULT CURRENT_TIMESTAMP`` -> keep as-is (Postgres accepts this too).

    # Replace ? placeholders with %s, but skip anything inside string literals.
    out = _replace_qmark_placeholders(out)
    return out


def _replace_qmark_placeholders(sql: str) -> str:
    """Replace ``?`` with ``%s``, respecting single-quoted string literals."""
    result = []
    in_str = False
    i = 0
    while i < len(sql):
        ch = sql[i]
        if ch == "'":
            # Handle escaped '' inside string
            result.append(ch)
            in_str = not in_str
            i += 1
            continue
        if ch == "?" and not in_str:
            result.append("%s")
            i += 1
            continue
        # Escape literal % to %% for psycopg2's format parser
        if ch == "%" and not in_str:
            result.append("%%")
            i += 1
            continue
        result.append(ch)
        i += 1
    return "".join(result)


# ---------------------------------------------------------------------------
# sqlite3-compatible row type for Postgres results
# ---------------------------------------------------------------------------
class _PgRow:
    """Dict+index hybrid row object, imitating :class:`sqlite3.Row`."""

    __slots__ = ("_cols", "_values", "_map")

    def __init__(self, cols: List[str], values: tuple):
        self._cols = cols
        self._values = values
        self._map = {c: v for c, v in zip(cols, values)}

    def __getitem__(self, key: Union[str, int]):
        if isinstance(key, int):
            return self._values[key]
        return self._map[key]

    def __contains__(self, key: str) -> bool:
        return key in self._map

    def keys(self):
        return list(self._cols)

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def get(self, key: str, default=None):
        return self._map.get(key, default)


# ---------------------------------------------------------------------------
# PRAGMA table_info emulation (Postgres information_schema)
# ---------------------------------------------------------------------------
_PRAGMA_TABLE_INFO_COLUMNS = ("cid", "name", "type", "notnull", "dflt_value", "pk")


def _fetch_pragma_table_info(conn, table_name: str) -> List[tuple]:
    """Return rows in the shape that ``PRAGMA table_info(T)`` would produce
    on SQLite: ``(cid, name, type, notnull, dflt_value, pk)``.
    """
    clean_name = table_name.strip().strip('"').strip("'")
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                (a.attnum - 1)::int AS cid,
                a.attname AS name,
                pg_catalog.format_type(a.atttypid, a.atttypmod) AS type,
                a.attnotnull::int AS notnull,
                pg_get_expr(ad.adbin, ad.adrelid) AS dflt_value,
                COALESCE(
                  (SELECT 1 FROM pg_index i
                   WHERE i.indrelid = a.attrelid
                   AND i.indisprimary
                   AND a.attnum = ANY(i.indkey)),
                  0
                )::int AS pk
            FROM pg_attribute a
            LEFT JOIN pg_attrdef ad
              ON ad.adrelid = a.attrelid AND ad.adnum = a.attnum
            WHERE a.attrelid = %s::regclass
              AND a.attnum > 0
              AND NOT a.attisdropped
            ORDER BY a.attnum
            """,
            (clean_name,),
        )
        return list(cur.fetchall())


# ---------------------------------------------------------------------------
# Adapter: Postgres cursor that speaks sqlite3.Cursor semantics
# ---------------------------------------------------------------------------
class _PgCursor:
    def __init__(self, pg_cursor, parent_conn: "_PgConnection"):
        self._cur = pg_cursor
        self._parent = parent_conn
        self._pragma_rows: Optional[List[tuple]] = None
        self._last_description: Optional[tuple] = None
        self._lastrowid: Optional[int] = None
        # When we auto-append RETURNING we must consume the single returned
        # row before the caller calls fetchone() themselves (they are not
        # expecting to see that row; they only want ``cursor.lastrowid``).
        self._suppress_next_fetch: bool = False

    @property
    def rowcount(self) -> int:
        return self._cur.rowcount

    @property
    def lastrowid(self) -> Optional[int]:
        return self._lastrowid

    @property
    def description(self):
        return self._cur.description

    def execute(self, sql: str, params: Optional[Iterable[Any]] = None):
        import psycopg2

        # Intercept PRAGMA table_info(T)
        m = _PRAGMA_TABLE_INFO_RE.match(sql)
        if m:
            self._pragma_rows = _fetch_pragma_table_info(
                self._parent._conn, m.group(1)
            )
            self._last_description = tuple(
                (name, None, None, None, None, None, None)
                for name in _PRAGMA_TABLE_INFO_COLUMNS
            )
            return self

        translated = _translate_sql_for_postgres(sql)

        # Auto-append RETURNING <pk> for plain INSERTs on serial-PK tables so
        # that ``cursor.lastrowid`` keeps working transparently.
        appended_returning = False
        ins_m = _PLAIN_INSERT_RE.match(translated)
        if ins_m:
            table = ins_m.group(1).lower()
            if (
                table in _SERIAL_PK_TABLES
                and "RETURNING" not in translated.upper()
                and "ON CONFLICT" not in translated.upper()
            ):
                pk = _PK_COLUMN_BY_TABLE.get(table, "id")
                translated = f"{translated.rstrip().rstrip(';')} RETURNING {pk}"
                appended_returning = True

        # SQLite treats individual statement errors as recoverable - the next
        # statement on the same connection just executes. Postgres aborts the
        # entire transaction on any error, so every idempotent migration probe
        # pattern (``try: ALTER ADD COLUMN; except OperationalError: pass``)
        # poisons the outer transaction and makes every subsequent call fail
        # with InFailedSqlTransaction. We wrap every execute in a per-statement
        # SAVEPOINT using a side cursor (so the main cursor's result set isn't
        # clobbered on success) and roll back the savepoint on the specific
        # migration-probe errors callers are catching.
        pg_conn = self._parent._conn
        savepoint = f"_sp_{id(self)}_{id(sql) & 0xffffffff:x}"
        sp_active = False
        try:
            with pg_conn.cursor() as sp_cur:
                sp_cur.execute(f"SAVEPOINT {savepoint}")
            sp_active = True
        except Exception:
            sp_active = False

        def _rollback_sp() -> None:
            if not sp_active:
                return
            try:
                with pg_conn.cursor() as sp_cur:
                    sp_cur.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                    sp_cur.execute(f"RELEASE SAVEPOINT {savepoint}")
            except Exception:
                pass

        def _release_sp() -> None:
            if not sp_active:
                return
            try:
                with pg_conn.cursor() as sp_cur:
                    sp_cur.execute(f"RELEASE SAVEPOINT {savepoint}")
            except Exception:
                pass

        try:
            if params is None:
                self._cur.execute(translated)
            else:
                self._cur.execute(translated, tuple(params))
        except (
            psycopg2.errors.UndefinedColumn,
            psycopg2.errors.UndefinedTable,
            psycopg2.errors.DuplicateColumn,
            psycopg2.errors.DuplicateTable,
            psycopg2.errors.DuplicateObject,
        ) as exc:
            _rollback_sp()
            raise sqlite3.OperationalError(str(exc)) from exc
        except Exception:
            _rollback_sp()
            raise
        else:
            _release_sp()

        if appended_returning:
            try:
                returned = self._cur.fetchone()
                if returned is not None:
                    self._lastrowid = int(returned[0])
            except Exception:
                self._lastrowid = None

        self._pragma_rows = None
        self._last_description = self._cur.description
        return self

    def executemany(self, sql: str, seq):
        translated = _translate_sql_for_postgres(sql)
        self._cur.executemany(translated, [tuple(p) for p in seq])
        self._pragma_rows = None
        return self

    def _wrap_rows(self, rows: List[tuple]):
        if self._pragma_rows is not None:
            return [tuple(r) for r in rows]
        factory = self._parent.row_factory
        if factory is sqlite3.Row:
            cols = [c[0] for c in (self._last_description or [])]
            return [_PgRow(cols, tuple(r)) for r in rows]
        return [tuple(r) for r in rows]

    def fetchone(self):
        if self._pragma_rows is not None:
            rows = self._pragma_rows
            self._pragma_rows = []  # consume
            return rows[0] if rows else None
        row = self._cur.fetchone()
        if row is None:
            return None
        return self._wrap_rows([row])[0]

    def fetchall(self):
        if self._pragma_rows is not None:
            rows = self._pragma_rows
            self._pragma_rows = []
            return [tuple(r) for r in rows]
        rows = self._cur.fetchall()
        return self._wrap_rows(rows)

    def close(self):
        self._cur.close()

    def __iter__(self):
        if self._pragma_rows is not None:
            return iter(self._wrap_rows(self._pragma_rows))
        return iter(self._wrap_rows(self._cur.fetchall()))


# ---------------------------------------------------------------------------
# Adapter: Postgres connection that speaks sqlite3.Connection semantics
# ---------------------------------------------------------------------------
class _PgConnection:
    def __init__(self, database_url: str):
        import psycopg2  # type: ignore

        self._conn = psycopg2.connect(database_url, connect_timeout=5)
        self._conn.autocommit = False
        self.row_factory = None  # set by caller; supports sqlite3.Row or None

    # ---- sqlite3.Connection API surface ----
    def cursor(self) -> _PgCursor:
        return _PgCursor(self._conn.cursor(), self)

    def execute(self, sql: str, params: Optional[Iterable[Any]] = None) -> _PgCursor:
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass

    # ---- context manager ----
    # In SQLite, ``with conn:`` commits/rolls back but does NOT close. The
    # pattern everywhere in this codebase is ``with sqlite3.connect(path) as
    # conn:`` which does close in CPython's sqlite3 because the connection is
    # a fresh instance going out of scope. We mirror the close-on-exit
    # behaviour to keep connection counts bounded and match that usage.
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                try:
                    self._conn.commit()
                except Exception:
                    pass
            else:
                try:
                    self._conn.rollback()
                except Exception:
                    pass
        finally:
            self.close()
        return False


# ---------------------------------------------------------------------------
# Public connect() factory
# ---------------------------------------------------------------------------
def connect(sqlite_path: Union[str, Path], timeout: Optional[float] = None) -> Any:
    """Return a DB connection: Postgres adapter when ``BACKEND == "postgres"``,
    else a real :func:`sqlite3.connect` to ``sqlite_path``.

    ``timeout`` is forwarded to SQLite only.
    """
    if BACKEND == "postgres" and _DATABASE_URL:
        try:
            return _PgConnection(_DATABASE_URL)
        except Exception as exc:
            logger.error("Postgres connect failed mid-session; falling back to SQLite: %s", exc)
            # Do NOT switch BACKEND; this is a transient failure. Callers that
            # have already created tables in Postgres will get SQLite misses,
            # but the app stays up. One-off fallback per call is acceptable.
    if timeout is not None:
        return sqlite3.connect(str(sqlite_path), timeout=timeout)
    return sqlite3.connect(str(sqlite_path))


__all__ = ["BACKEND", "connect"]
