"""Shared Redis URL construction from Secrets Manager JSON (ElastiCache / Redis)."""

from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import quote_plus


def build_redis_url_from_secret_dict(data: Dict[str, Any]) -> Optional[str]:
    """Build redis:// or rediss:// URL from common JSON shapes stored in Secrets Manager."""
    direct = (data.get("redis_url") or data.get("REDIS_URL") or "").strip()
    if direct:
        return direct

    host = (data.get("host") or data.get("hostname") or data.get("endpoint") or "").strip()
    if not host:
        return None

    port = int(data.get("port", 6379))
    password = data.get("password") or data.get("auth_token") or ""
    username = (data.get("username") or "").strip()

    ssl_raw = data.get("ssl", data.get("tls", False))
    if isinstance(ssl_raw, str):
        use_ssl = ssl_raw.lower() in ("1", "true", "yes", "on")
    else:
        use_ssl = bool(ssl_raw)

    scheme = "rediss" if use_ssl else "redis"

    if username or password:
        user_enc = quote_plus(str(username)) if username else ""
        pass_enc = quote_plus(str(password)) if password else ""
        if username:
            auth = f"{user_enc}:{pass_enc}@"
        else:
            auth = f":{pass_enc}@"
    else:
        auth = ""

    return f"{scheme}://{auth}{host}:{port}/0"
