#!/usr/bin/env python3
"""
Scan MIDAS FastAPI router modules and emit a JSON + Markdown inventory of HTTP routes.

This avoids importing the full backend (heavy deps) and works when the deployed host
serves the SPA at /openapi.json so OpenAPI cannot be fetched over HTTP.

Usage (from repo root):
  python3 testing/scripts/generate_route_inventory.py
  python3 testing/scripts/generate_route_inventory.py --json testing/generated/route_inventory.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_API = _REPO_ROOT / "backend" / "app" / "api"
_MAIN_PY = _REPO_ROOT / "backend" / "main.py"

# (api module stem, symbol used in @decorators in that file) -> URL prefix
_MODULE_ROUTER_PREFIXES: dict[tuple[str, str], str] = {}


def _parse_main_imports_and_prefixes() -> None:
    """Link include_router(...) prefixes to (module_stem, router_var_in_file)."""
    text = _MAIN_PY.read_text(encoding="utf-8")
    sym_to_module: dict[str, tuple[str, str]] = {}
    for line in text.splitlines():
        line = line.strip()
        m = re.match(
            r"from app\.api\.(\w+) import (.+)$",
            line,
        )
        if not m:
            continue
        mod, rhs = m.group(1), m.group(2)
        parts = [p.strip() for p in rhs.split(",")]
        for part in parts:
            if " as " in part:
                left, right = [x.strip() for x in part.split(" as ", 1)]
                sym_to_module[right] = (mod, left)
            else:
                sym_to_module[part] = (mod, part)

    for m in re.finditer(
        r"app\.include_router\s*\(\s*(\w+)\s*,\s*prefix\s*=\s*[\"']([^\"']+)[\"']",
        text,
    ):
        sym, prefix = m.group(1), m.group(2)
        if sym not in sym_to_module:
            continue
        mod, router_in_file = sym_to_module[sym]
        _MODULE_ROUTER_PREFIXES[(mod, router_in_file)] = prefix


_ROUTE_RE = re.compile(
    r"^@(?P<router>\w+)\.(?P<method>get|post|put|patch|delete)\s*\(\s*"
    r"(?:\n|\s)*"
    r"(?:[\"'](?P<path1>[^\"']+)[\"']|f[\"'](?P<path2>[^\"']+)[\"'])",
    re.MULTILINE,
)


def _iter_router_files() -> Iterable[Path]:
    if not _BACKEND_API.is_dir():
        raise SystemExit(f"Missing API directory: {_BACKEND_API}")
    for p in sorted(_BACKEND_API.glob("*.py")):
        if p.name.startswith("_"):
            continue
        yield p


def _module_stem(path: Path) -> str:
    return path.stem


def _router_vars_declared_in_file(path: Path) -> list[str]:
    body = path.read_text(encoding="utf-8")
    return re.findall(r"^(\w+)\s*=\s*APIRouter\s*\(", body, re.MULTILINE)


@dataclass(frozen=True)
class RouteRecord:
    method: str
    path: str
    router_var: str
    router_prefix: str
    source_file: str
    full_path: str


def _normalize_full(router_prefix: str, path: str) -> str:
    rp = router_prefix.rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return rp + path


def scan_routes() -> list[RouteRecord]:
    _parse_main_imports_and_prefixes()
    records: list[RouteRecord] = []
    for py in _iter_router_files():
        mod = _module_stem(py)
        declared = _router_vars_declared_in_file(py)
        if not declared:
            continue
        body = py.read_text(encoding="utf-8")
        for router_var in declared:
            prefix = _MODULE_ROUTER_PREFIXES.get((mod, router_var))
            if prefix is None:
                continue
            for m in _ROUTE_RE.finditer(body):
                rv = m.group("router")
                if rv != router_var:
                    continue
                method = m.group("method").upper()
                sub = m.group("path1") or m.group("path2") or ""
                full = _normalize_full(prefix, sub)
                records.append(
                    RouteRecord(
                        method=method,
                        path=sub,
                        router_var=router_var,
                        router_prefix=prefix,
                        source_file=str(py.relative_to(_REPO_ROOT)),
                        full_path=full,
                    )
                )
    records.sort(key=lambda r: (r.full_path, r.method))
    return records


def _markdown_table(records: list[RouteRecord]) -> str:
    lines = [
        "# MIDAS backend route inventory (generated)",
        "",
        "| Method | Full path | Source |",
        "|--------|-----------|--------|",
    ]
    for r in records:
        lines.append(f"| {r.method} | `{r.full_path}` | `{r.source_file}` |")
    return "\n".join(lines) + "\n"


def _build_openapi_stub(records: list[RouteRecord], methods: frozenset[str] | None = None) -> dict:
    """Minimal OAS3 document so Schemathesis can drive smoke calls (stubs only; not from running app)."""
    allowed = methods or frozenset({"get", "post", "put", "patch", "delete"})
    paths: dict[str, dict[str, object]] = {}
    for r in records:
        m = r.method.lower()
        if m not in allowed:
            continue
        entry = paths.setdefault(r.full_path, {})
        entry[m] = {
            "responses": {
                "200": {"description": "inventory stub — validate transport only"},
                "401": {"description": "unauthorized"},
                "404": {"description": "not found"},
            }
        }
    return {
        "openapi": "3.0.3",
        "info": {"title": "MIDAS route inventory stub", "version": "1.0.0"},
        "servers": [{"url": "https://placeholder.invalid", "description": "override via case.call(base_url=…)"}],
        "paths": paths,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate static route inventory from backend sources.")
    parser.add_argument(
        "--json",
        type=Path,
        default=_REPO_ROOT / "testing" / "generated" / "route_inventory.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "--md",
        type=Path,
        default=_REPO_ROOT / "testing" / "generated" / "route_inventory.md",
        help="Output Markdown path",
    )
    parser.add_argument(
        "--openapi-stub",
        type=Path,
        default=_REPO_ROOT / "testing" / "generated" / "openapi_from_inventory.json",
        help="Write minimal OpenAPI 3.0 JSON derived from scanned routes (for Schemathesis)",
    )
    parser.add_argument(
        "--openapi-get-only",
        type=Path,
        default=_REPO_ROOT / "testing" / "generated" / "openapi_from_inventory_get_only.json",
        help="GET-only OpenAPI stub for safer Schemathesis runs",
    )
    args = parser.parse_args()
    records = scan_routes()
    payload = {
        "generator": "testing/scripts/generate_route_inventory.py",
        "route_count": len(records),
        "routes": [asdict(r) for r in records],
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    args.md.write_text(_markdown_table(records), encoding="utf-8")
    stub = _build_openapi_stub(records)
    args.openapi_stub.write_text(json.dumps(stub, indent=2), encoding="utf-8")
    stub_get = _build_openapi_stub(
        [r for r in records if r.method == "GET" and "stream" not in r.full_path.lower()],
        methods=frozenset({"get"}),
    )
    args.openapi_get_only.write_text(json.dumps(stub_get, indent=2), encoding="utf-8")
    print(
        f"Wrote {len(records)} routes to {args.json}, {args.md}, {args.openapi_stub}, and {args.openapi_get_only}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
