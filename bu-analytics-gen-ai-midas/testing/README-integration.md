# MIDAS backend integration tests (gold standard)

This folder contains **HTTP integration tests** against a live MIDAS deployment (default: dev), plus a **static route inventory** generator and optional **Schemathesis** contract smoke.

## Prerequisites

- Python **3.11+** (repo standard; a dedicated venv is recommended under `testing/.venv/` — ignored by git).
- Network access to the target host (often corporate VPN).

```bash
cd /path/to/bu-analytics-gen-ai-midas
python3 -m venv testing/.venv
./testing/.venv/bin/pip install -r testing/requirements-integration.txt
./testing/.venv/bin/playwright install chromium
```

## Regenerate route inventory and OpenAPI stubs

From the repo root (no backend import required):

```bash
python3 testing/scripts/generate_route_inventory.py
```

Writes:

- `testing/generated/route_inventory.json` — machine-readable list of routes.
- `testing/generated/route_inventory.md` — human table.
- `testing/generated/openapi_from_inventory.json` — full stub for exploration.
- `testing/generated/openapi_from_inventory_get_only.json` — GET-only stub (no streaming paths).

## Authentication

### Option A — Bearer token (fastest)

Use the same internal JWT the SPA stores in `localStorage` (`auth_token`) after SSO:

```bash
export MIDAS_ACCESS_TOKEN="…"
```

Optional: `MIDAS_SESSION_ID` (maps to `X-Session-Id`), `MIDAS_COOKIE_HEADER` (raw `Cookie` header for Cognito refresh paths).

### Option B — Playwright SSO once per pytest session

Set:

```bash
export MIDAS_SSO_EMAIL="you@example.com"
export MIDAS_SSO_PASSWORD="…"
# Optional; defaults to MIDAS_BASE_URL
export MIDAS_SPA_ORIGIN="https://exldecision-ai-dev.exlservice.com"
export PLAYWRIGHT_HEADLESS=1
```

The harness opens the SPA, clicks **Sign In**, completes the Microsoft / Entra + Cognito flow, then reads `auth_token` and `midas_session_id` from `localStorage` (same keys as [`frontend/src/services/authService.ts`](../frontend/src/services/authService.ts)).

## Base URL

```bash
export MIDAS_BASE_URL="https://exldecision-ai-dev.exlservice.com"
```

**Note:** On the current dev host, OpenAPI is not served at `/openapi.json` (the SPA is mounted there). Inventory is therefore generated from **backend source** via `generate_route_inventory.py`, not by fetching OpenAPI over HTTP.

If your ingress uses a path prefix (for example `/backend`), set `MIDAS_BASE_URL` to the **API origin only** (scheme + host) and keep API paths as `/api/v1/...` exactly as in the inventory.

## Run tests

Always set `rootdir` to `testing/` so pytest does not collect unrelated repo tests:

```bash
cd /path/to/bu-analytics-gen-ai-midas
./testing/.venv/bin/pytest testing/integration -c testing/pytest.ini --rootdir=testing -v
```

### Markers

- `@pytest.mark.slow` — heavier suites (inventory GET sweep, Schemathesis when expanded).
- `@pytest.mark.schemathesis` — contract tests (Hypothesis + Schemathesis).

### Schemathesis scope

[`test_schemathesis_contract.py`](integration/test_schemathesis_contract.py) currently filters to **GET** `/api/v1/keepalive` and `/api/v1/llm-config` for a fast, stable smoke. Widen the `.include(path_regex=…)` chain in that file when you want broader contract coverage.

## Layout

| Path | Role |
|------|------|
| [`testing/api_client/`](../api_client/) | Pydantic config, credentials, auth protocol, `MidasHttpClient`. |
| [`testing/conftest.py`](../conftest.py) | Session fixtures: base URL, credentials, HTTP client, raw OpenAPI schema. |
| [`testing/integration/sso_playwright.py`](integration/sso_playwright.py) | Playwright Cognito + Entra automation. |
| [`testing/scripts/generate_route_inventory.py`](../scripts/generate_route_inventory.py) | Static route + OpenAPI stub generator. |

## Troubleshooting

| Symptom | Mitigation |
|---------|------------|
| Playwright cannot find **Sign In** | SPA markup changed — adjust selector in `sso_playwright.py`. |
| Microsoft MFA required | Use a dedicated test account without MFA, or use **Option A** token injection. |
| `401` on all API calls | Token expired; refresh in browser or supply `MIDAS_COOKIE_HEADER` from DevTools for `/api/v1/auth/cognito/refresh`. |
| SSL errors | `export MIDAS_VERIFY_TLS=0` (local debugging only). |
