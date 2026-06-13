"""Persistence package.

Routing-tier records live in **Postgres** (see ``app_config.toml`` ``[postgres]``).
Repositories receive an ``asyncpg`` pool at the gRPC composition root (``main.py``).
"""
