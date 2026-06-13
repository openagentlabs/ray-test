"""Seed a fixed set of application users into BOTH Postgres and SQLite.

Run from the ``backend/`` directory:

    python3 scripts/seed_users.py

Behaviour:

* Upserts the users below into Postgres (if available via DATABASE_URL / AWS
  Secrets Manager bundle).
* Upserts the same users into the local SQLite file (``settings.DATABASE_PATH``)
  regardless, so the fallback DB is in sync.
* Safe to run repeatedly: existing usernames are updated in-place with the
  configured password / full_name / email, keeping the ``id`` and
  ``created_at`` stable so their data (projects, chats, tokens) stays intact.

Passwords are hashed with the same bcrypt context used by the running
application (``passlib.CryptContext(schemes=['bcrypt'])``), so the resulting
hash is always compatible with ``/api/v1/auth/login``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


# Ensure we can import ``app.*`` when invoked as ``python scripts/seed_users.py``.
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))


USERS = [
    {
        "username": "MIDAS_internal",
        "full_name": "MIDAS Internal",
        "email": "MIDAS_internal@example.com",
        "password": "EXL@123456",
    },
    {
        "username": "Saiyam Arora",
        "full_name": "Saiyam Arora",
        "email": "saiyam.arora@example.com",
        "password": "SaiyamEXL@2026",
    },
    {
        "username": "MIDAS_Test01",
        "full_name": "MIDAS Test 01",
        "email": "MIDAS_Test01@example.com",
        "password": "Midas@123456",
    },
    {
        "username": "RPM_user01",
        "full_name": "RPM User 01",
        "email": "RPM_user01@example.com",
        "password": "Midas@123456",
    },
]


def _seed(label: str) -> None:
    """Re-import the app with a forced backend and upsert all users."""
    # Drop cached modules so ``app.models._db_backend`` re-runs its probe
    # against whatever env vars we just set.
    for mod in list(sys.modules):
        if mod == "app" or mod.startswith("app."):
            del sys.modules[mod]

    from app.models._db_backend import BACKEND  # noqa: E402
    from app.models.user_database import UserDB, pwd_context  # noqa: E402

    print(f"\n=== [{label}] backend resolved to: {BACKEND} ===")
    if label.lower() == "postgres" and BACKEND != "postgres":
        print("  Postgres not reachable; skipping (SQLite pass will still run).")
        return
    if label.lower() == "sqlite" and BACKEND != "sqlite":
        print("  Expected SQLite for this pass but got postgres - aborting pass.")
        return

    udb = UserDB()

    for u in USERS:
        hashed = pwd_context.hash(u["password"])
        with udb._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM users WHERE username = ?",
                (u["username"],),
            )
            existing = cursor.fetchone()
            if existing:
                user_id = existing[0]
                cursor.execute(
                    """
                    UPDATE users
                    SET full_name = ?, email = ?, hashed_password = ?, is_active = ?
                    WHERE id = ?
                    """,
                    (u["full_name"], u["email"], hashed, True, user_id),
                )
                action = f"updated (id={user_id})"
            else:
                cursor.execute(
                    """
                    INSERT INTO users (username, full_name, email, hashed_password, is_active)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (u["username"], u["full_name"], u["email"], hashed, True),
                )
                user_id = cursor.lastrowid
                action = f"inserted (id={user_id})"
            conn.commit()

        # Verify we can authenticate with the provided password right away.
        verified = udb.authenticate_user(u["username"], u["password"]) is not None
        print(f"  [{'OK' if verified else 'FAIL'}] {u['username']:<20} {action}"
              f"  auth={'yes' if verified else 'NO'}")


def main() -> int:
    # Pass 1: Postgres (whatever DATABASE_URL / Secrets Manager resolves to).
    os.environ.pop("MIDAS_FORCE_SQLITE", None)
    _seed("Postgres")

    # Pass 2: force SQLite so the fallback DB is seeded too.
    os.environ["DATABASE_URL"] = ""  # empty => _db_backend skips PG probe
    os.environ["MIDAS_FORCE_SQLITE"] = "1"  # informational only
    _seed("SQLite")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
