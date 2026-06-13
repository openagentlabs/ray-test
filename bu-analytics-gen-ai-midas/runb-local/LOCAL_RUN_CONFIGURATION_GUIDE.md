# Local Run Configuration Guide

This document compares the **current Dev31 config** with the **local-ready baseline** (from `Dev004/bu-analytics-gen-ai-midas`) and lists what must be changed so frontend and backend run locally.

## Goal

Run:
- frontend on `http://localhost:5173`
- backend on `http://localhost:8000`
- browser auth/cookies/CORS working in local mode

## Files Reviewed

- `frontend/.env.example`
- `frontend/vite.config.ts`
- `backend/main.py`
- `backend/app/core/config.py`
- `backend/.env.backup`
- `backend/README-Auth.md`
- `backend/docs/API_REFERENCE.md`

## Key Findings From Current Dev31

- Frontend local defaults are already correct in `frontend/.env.example`:
  - `VITE_BASE_URL=http://localhost:8000`
  - local callback/logout URLs point to `localhost:5173`
- Vite dev proxy already targets local backend by default:
  - `VITE_DEV_PROXY_TARGET` fallback is `http://localhost:8000`
- Backend code supports local mode, but current `backend/.env.backup` has deployed values that break local login flow:
  - `APP_ENV=production`
  - `SESSION_REQUIRE_REDIS=true`
  - `SESSION_REDIS_URL` points to remote ElastiCache
  - `COGNITO_REDIRECT_URIS` points to deployed URL
  - `CORS_ALLOW_ORIGINS` points to deployed URL

## Required Changes To Run Locally

### File: `frontend/.env`

Use/copy from `frontend/.env.example` and confirm these:

- `VITE_BASE_URL=http://localhost:8000`
- `VITE_COGNITO_REDIRECT_URI=http://localhost:5173/auth/callback`
- `VITE_COGNITO_LOGOUT_REDIRECT_URI=http://localhost:5173/`
- `VITE_COGNITO_DOMAIN` and `VITE_COGNITO_CLIENT_ID` must match backend Cognito config
- `VITE_COGNITO_SCOPES=openid email profile`

Optional for bypass mode:
- `VITE_DEV_BYPASS_AUTH=true` (only if backend also enables dev bypass)

### File: `backend/.env`

Create/update `backend/.env` with local-safe values:

- `APP_ENV=development`
- `SESSION_REQUIRE_REDIS=false` (or true only if local Redis configured)
- `COGNITO_REDIRECT_URIS=http://localhost:5173/auth/callback`
- `COGNITO_LOGOUT_REDIRECT_URI=http://localhost:5173/`
- `COGNITO_COOKIE_SECURE=false` (required for HTTP local)
- `CORS_ALLOW_ORIGINS=http://localhost:5173`

Session store options:
- No Redis local:
  - leave `SESSION_REDIS_URL` and `REDIS_URL` empty
- With local Redis:
  - `SESSION_REDIS_URL=redis://localhost:6379/0`
  - optionally `REDIS_URL=redis://localhost:6379/0`

### File: `frontend/vite.config.ts`

No code change required for local:
- fallback proxy target already `http://localhost:8000`

### File: `backend/main.py`

No code change required for local:
- CORS behavior already supports explicit allowlist via `CORS_ALLOW_ORIGINS`

## Parameter List Grouped By File

### `frontend/.env`

- `VITE_BASE_URL`
- `VITE_COGNITO_DOMAIN`
- `VITE_COGNITO_CLIENT_ID`
- `VITE_COGNITO_REDIRECT_URI`
- `VITE_COGNITO_LOGOUT_REDIRECT_URI`
- `VITE_COGNITO_SCOPES`
- `VITE_DEV_BYPASS_AUTH` (optional)

### `backend/.env`

- `APP_ENV`
- `SESSION_REQUIRE_REDIS`
- `SESSION_REDIS_URL`
- `REDIS_URL`
- `COGNITO_DOMAIN`
- `COGNITO_REGION`
- `COGNITO_USER_POOL_ID`
- `COGNITO_CLIENT_ID`
- `COGNITO_CLIENT_SECRET` (optional)
- `COGNITO_REDIRECT_URIS`
- `COGNITO_LOGOUT_REDIRECT_URI`
- `COGNITO_SCOPES`
- `COGNITO_IDP_NAME` (optional)
- `COGNITO_COOKIE_SECURE`
- `COGNITO_LOGIN_COOKIE_SECRET` (optional in local)
- `COGNITO_LOGIN_COOKIE_TTL`
- `COGNITO_REFRESH_COOKIE_TTL_DAYS`
- `CORS_ALLOW_ORIGINS`

## Interactive Script

Use:

```bash
python3 runb-local/generate_local_config.py
```

What it does:
- **Step 1**: interactive value collection
- reads current values from:
  - `frontend/.env.example`
  - `backend/.env.backup`
  - optional existing `frontend/.env`, `backend/.env`
- asks user value for each local-run parameter (grouped by target file)
- behavior per prompt:
  - **Enter** = use local default
  - `=` = keep current value (if present)
  - any other text = use custom value
- writes generated files to:
  - `runb-local/output/frontend.env`
  - `runb-local/output/backend.env`
  - `runb-local/output/config-review.md`
- **Step 2**: built-in local-readiness validation
  - validates generated output files against local-required rules
  - validates current `frontend/.env` and `backend/.env` (if present)
  - prints PASS/FAIL checklist and overall status

Then copy reviewed values into real app files:

```bash
cp runb-local/output/frontend.env frontend/.env
cp runb-local/output/backend.env backend/.env
```

