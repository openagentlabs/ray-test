"""REST API backend pool node for routing-tier E2E tests."""

from __future__ import annotations

import json
import os
from typing import Any

from aiohttp import web

NODE_NAME = os.environ.get("BACKEND_POOL_NODE_NAME", "unknown")
API_PREFIX = "/api/v1"


def _json_response(data: dict[str, Any], *, status: int = 200) -> web.Response:
    return web.Response(
        text=json.dumps(data),
        status=status,
        content_type="application/json",
    )


def _require_sub(request: web.Request) -> str | web.Response:
    sub = request.headers.get("x-user-sub", "").strip()
    if not sub:
        return _json_response(
            {
                "error": "unauthorized",
                "message": "Missing identity (x-user-sub). Route through Envoy after ext_authz.",
            },
            status=401,
        )
    return sub


async def index(_request: web.Request) -> web.Response:
    body = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Backend pool node {NODE_NAME}</title></head>
<body>
  <h1>backend_pool_node</h1>
  <p><strong>BACKEND_POOL_NODE_NAME</strong>: {NODE_NAME}</p>
  <p>REST API: <code>GET {API_PREFIX}/me</code> (JSON)</p>
</body>
</html>"""
    return web.Response(text=body, content_type="text/html")


async def healthz(_request: web.Request) -> web.Response:
    return web.Response(text="ok\n", content_type="text/plain")


async def api_v1_me(request: web.Request) -> web.Response:
    sub_or_err = _require_sub(request)
    if isinstance(sub_or_err, web.Response):
        return sub_or_err
    return _json_response(
        {
            "service": "backend_pool_node",
            "pod_id": NODE_NAME,
            "backend_pool_node": NODE_NAME,
            "sub": sub_or_err,
            "message": "Exclusive backend lease is active for this identity.",
        },
    )


async def api_v1_ping(request: web.Request) -> web.Response:
    sub_or_err = _require_sub(request)
    if isinstance(sub_or_err, web.Response):
        return sub_or_err
    return _json_response({"ok": True, "pod_id": NODE_NAME, "sub": sub_or_err})


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/healthz", healthz)
    app.router.add_get(f"{API_PREFIX}/me", api_v1_me)
    app.router.add_get(f"{API_PREFIX}/ping", api_v1_ping)
    # Legacy path used by older clients and docs.
    app.router.add_get("/api/me", api_v1_me)
    return app


def main() -> None:
    port = int(os.environ.get("PORT", "8080"))
    web.run_app(create_app(), host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
