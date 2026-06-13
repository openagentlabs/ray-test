# Authentication, Authorization & Session Management

> **Quick summary:** MIDAS authenticates users via **AWS Cognito Hosted UI** federated with
> **Microsoft Entra ID**. The browser never sees Cognito tokens — everything passes through
> a secure backend exchange that produces a short-lived internal JWT. Sessions are tracked
> server-side in Redis (or in-memory for dev). The legacy username/password endpoints
> (`/api/v1/auth/{login,register}`) are disabled by default.
>
> For a deep-dive with code snippets, sequence diagrams, and troubleshooting,
> see **[`docs/MIDAS-Auth-Detailed-Workbook.md`](../docs/MIDAS-Auth-Detailed-Workbook.md)**.

---

## 1. How login works — the big picture

When a user clicks "Sign in", the following chain of redirects and API calls happens
automatically. The entire flow takes about 2–3 seconds.

```
┌──────────┐     ┌─────────────────┐     ┌───────────┐     ┌──────────┐     ┌──────────────┐
│  React   │────▶│ Cognito Hosted  │────▶│ Microsoft │────▶│ Cognito  │────▶│ FastAPI      │
│  SPA     │     │ UI (/authorize) │     │ Entra ID  │     │ /token   │     │ /exchange    │
└──────────┘     └─────────────────┘     └───────────┘     └──────────┘     └──────────────┘
     │                                                                            │
     │◀───── internal Bearer JWT + midas_cg_rt HttpOnly cookie ──────────────────┘
```

**In plain English:**

1. The React app generates a one-time PKCE secret and asks the backend for a Cognito login URL.
2. The backend creates an anti-CSRF `state` and OIDC `nonce`, binds them into a signed cookie (`cg_login`), and returns the URL.
3. The browser redirects to Cognito → Entra ID → user authenticates → Cognito redirects back with an authorization `code`.
4. The frontend sends the `code` + its PKCE secret to the backend's `/exchange` endpoint.
5. The backend exchanges the code with Cognito, validates both JWTs (id + access token), creates a local user record, starts a server session, and returns an internal Bearer JWT.
6. The frontend stores the JWT and user profile; every subsequent API call uses this JWT.

### Step-by-step detail

| # | Where | What happens |
|---|-------|-------------|
| 1 | **Frontend** | `cognitoAuthService.beginLogin()` — generates PKCE `code_verifier` (64 random bytes) + `code_challenge` (SHA-256, base64url). Stores `code_verifier` in `sessionStorage`. |
| 2 | **Frontend → Backend** | `GET /api/v1/auth/cognito/login-url?vhash=<sha256hex(verifier)>` — backend mints `state` + `nonce`, signs them with the verifier hash into the `cg_login` HttpOnly cookie (10 min TTL). Returns the Cognito authorize URL. |
| 3 | **Frontend** | Appends `code_challenge` to the URL and redirects the browser to Cognito Hosted UI. Stores `state` and `nonce` in `sessionStorage`. |
| 4 | **Cognito ↔ Entra** | Cognito auto-redirects to Entra ID (if `COGNITO_IDP_NAME` is set). User authenticates via SSO. Cognito receives the assertion. |
| 5 | **Cognito → Browser** | Cognito redirects to `/auth/callback?code=...&state=...`. |
| 6 | **Frontend** | `AuthCallback.tsx` calls `completeLogin()` — verifies `state`, POSTs `{ code, state, code_verifier, redirect_uri }` to the backend. |
| 7 | **Backend** | `/exchange` — validates cookie binding (state + verifier hash), exchanges code with Cognito, validates both JWTs via JWKS, provisions local user, creates server session, mints internal JWT, sets `midas_cg_rt` cookie, clears `cg_login` cookie. Returns JWT + user profile. |
| 8 | **Frontend** | Stores JWT in `localStorage` (`auth_token`), user profile in `localStorage` (`user_data`), starts session timer, updates `UserContext`, clears PKCE scratch, navigates to `/`. |

### Why is this secure?

Every login attempt is protected by **five independent security mechanisms** working together:

- **PKCE S256** — prevents authorization code interception; the `code_verifier` never leaves the browser until the final `/exchange` POST (over HTTPS).
- **`state` parameter** — anti-CSRF; generated server-side, bound in the `cg_login` cookie, and verified at exchange time.
- **OIDC `nonce`** — replay protection; bound in the `cg_login` cookie, verified inside the `id_token`.
- **`at_hash` verification** — the `id_token`'s `at_hash` claim is verified against the `access_token` hash at decode time (via `python-jose`).
- **JWKS RS256 validation** — both Cognito tokens are verified against the user pool's public keys with a 1-hour TTL cache, auto-refresh on key rotation, and 30-second clock skew leeway.

---

## 2. Tokens — what exists and where it lives

MIDAS uses **six distinct tokens** across the auth lifecycle. Understanding where each one is stored is critical for security audits and debugging.

### 2.1 Cognito-issued tokens (external — never in JS-accessible storage)

These tokens are issued by Cognito's `/oauth2/token` endpoint and are **never stored in `localStorage` or exposed to JavaScript**.

| Token | Where it's stored | Lifetime | What it does |
|-------|-------------------|----------|-------------|
| **`id_token`** | Backend memory only — validated and discarded during `/exchange` and `/refresh` | ~1 hour (Cognito default) | Contains user identity claims: `sub`, `email`, `name`, `nonce`, `at_hash`. Used to identify and provision the local user. |
| **`access_token`** | Backend memory only — validated and discarded | ~1 hour | Validated for `token_use=access` and `client_id`. Used for `at_hash` cross-verification of the `id_token`. |
| **`refresh_token`** | `midas_cg_rt` **HttpOnly cookie** (path `/api/v1/auth/cognito`, SameSite=Lax) | Up to 30 days (configurable) | Sent automatically by the browser on `/refresh` calls. Backend uses it to request new Cognito tokens silently. **Never readable by JavaScript.** |

### 2.2 MIDAS internal tokens (app-issued)

These are short-lived JWTs that the MIDAS backend creates and the frontend uses for API authorization.

| Token | Algorithm | Where it's stored | Lifetime | JWT claims | What it does |
|-------|-----------|-------------------|----------|------------|-------------|
| **Internal access JWT** | HS256 | Frontend `localStorage` → key `auth_token` | 45 min | `sub` (username, e.g. `cg:<cognito-sub>`), `sid` (session UUID), `exp` | Sent as `Authorization: Bearer <token>` on every API request. Verified by `SessionManager`. |
| **Internal refresh JWT** | HS256 | SQLite `refresh_tokens` table (stored as SHA-256 hash) | 3 days | `sub`, `type=refresh`, `exp` | *Legacy path only* — the Cognito flow uses the `midas_cg_rt` cookie instead. |

### 2.3 Login binding token (ephemeral)

| Token | Where it's stored | Lifetime | What it contains |
|-------|-------------------|----------|-----------------|
| **`cg_login` JWS** | **HttpOnly cookie** (path `/api/v1/auth/cognito`, SameSite=Lax) | 10 min | `state`, `nonce`, `vhash` (SHA-256 of PKCE verifier), `exp`. HS256-signed with `COGNITO_LOGIN_COOKIE_SECRET`. |

This short-lived cookie exists only during the login redirect and is cleared after `/exchange` succeeds.

---

## 3. Session management

After login, every API request is authorized through a **server-side session** that binds the internal JWT's `sid` claim to a stored session record. This means even if a JWT is stolen, revoking the session on the server immediately invalidates it.

### 3.1 How sessions are stored

| Environment | Implementation | Where data lives | Key format |
|------------|----------------|-----------------|------------|
| **Production** | `RedisSessionStore` | Redis — `SET midas:sess:<sid> <username> EX <ttl>` | `midas:sess:{uuid4}` |
| **Development** | `InMemorySessionStore` | Python dict with async lock (process-local, lost on restart) | Same key format |

The backend picks the right store automatically via a **resolution chain** in `session_factory.py`:
1. `SESSION_ELASTICACHE_SECRET_ARN` → resolve from AWS Secrets Manager
2. `SESSION_REDIS_URL` → explicit Redis URL
3. `REDIS_URL` → shared Redis URL
4. **Fallback**: In-memory (dev only); **fail fast** in production

**Session TTL**: Default 5,400 seconds (90 minutes), minimum 600 seconds. Configured via `SESSION_TIMEOUT`.

### 3.2 Session lifecycle

| Event | What happens |
|-------|-------------|
| **Login** (`/exchange`) | `SessionManager.create_session(username)` generates a UUID `sid`, saves it to the store with TTL. The `sid` is embedded in the internal JWT. |
| **Every API request** | `SessionManager.authenticate_access_token(token)` decodes the JWT, checks that the user exists and is active, then verifies the `sid` is still valid in the session store. Tokens without `sid` still work for backward compatibility. |
| **Silent refresh** (`/refresh`) | Creates a **brand-new** `sid` every time — this is a session fixation defense. The old session expires naturally via TTL. |
| **Logout** (`/logout`) | `SessionManager.invalidate_access_token(token)` extracts the `sid` from the JWT and deletes it from the store immediately. |
| **Timeout** | Server-side: Redis TTL expires the key. Client-side: a JavaScript timer fires `midas:session-expired` → modal → redirect to login. |

### 3.3 What the frontend stores

**`localStorage`** (persists across tabs and page reloads):

| Key | Value | Written by |
|-----|-------|------------|
| `auth_token` | The internal Bearer JWT string | `authService.setSessionFromApiResponse()` |
| `user_data` | JSON object: `{id, username, full_name, email, is_active, created_at, updated_at}` | Same |
| `userData` | JSON object: `{name, role, avatar, email, id, username}` (frontend display format) | `UserContext.login()` |
| `midas_session_created_at` | Unix epoch (seconds) when session was created | `authSessionExpiry.persistSessionMetaFromApi()` |
| `midas_session_ttl_seconds` | Server session TTL in seconds | Same |
| `midas_session_id` | Server session UUID | Same |

**`sessionStorage`** (cleared after login completes or tab closes):

| Key | Value | Lifetime |
|-----|-------|----------|
| `cg_verifier` | PKCE `code_verifier` | Login start → `/exchange` callback |
| `cg_state` | OAuth `state` parameter | Login start → `/exchange` callback |
| `cg_nonce` | OIDC `nonce` | Login start → `/exchange` callback |

---

## 4. User storage & JIT provisioning

MIDAS does not require pre-registering users. When someone logs in via Cognito for the first time, a local user record is **automatically created** (Just-in-Time provisioning).

### 4.1 The `users` table (SQLite)

| Column | Type | Description |
|--------|------|-------------|
| `id` | `INTEGER PRIMARY KEY AUTOINCREMENT` | Internal numeric user ID, used as FK in other tables |
| `username` | `TEXT UNIQUE NOT NULL` | For Cognito users: `cg:<cognito-sub>` (truncated to 50 chars) |
| `full_name` | `TEXT NOT NULL` | Resolved from `id_token` claims: `name` → `cognito:username` → email → sub |
| `email` | `TEXT` | From `id_token` `email` claim (nullable — some IdPs may not provide it) |
| `hashed_password` | `TEXT NOT NULL` | Cognito users get a random bcrypt hash — they can never log in via username/password |
| `is_active` | `BOOLEAN DEFAULT TRUE` | Set to FALSE to block a user without deleting their record |
| `created_at` | `TIMESTAMP` | Auto-set on INSERT |
| `updated_at` | `TIMESTAMP` | Auto-set on INSERT and UPDATE |

**Indexes:** `idx_username` on `username`, `idx_email` on `email`.

### 4.2 The `refresh_tokens` table (SQLite)

This table stores **hashed** copies of internal refresh tokens (legacy path). In the Cognito flow, refresh is handled via the `midas_cg_rt` cookie, but this table is still used for token revocation on logout.

| Column | Type | Description |
|--------|------|-------------|
| `id` | `INTEGER PRIMARY KEY AUTOINCREMENT` | Row ID |
| `user_id` | `INTEGER NOT NULL` | References `users.id` |
| `token_hash` | `TEXT NOT NULL` | SHA-256 hex digest of the raw refresh JWT |
| `created_at` | `TIMESTAMP` | When the token was created |
| `expires_at` | `TIMESTAMP NOT NULL` | Absolute expiry; checked at verification time |
| `revoked` | `BOOLEAN DEFAULT FALSE` | Set to TRUE on logout or token rotation |

**Indexes:** `idx_refresh_token_hash` on `token_hash`, `idx_refresh_user_id` on `user_id`.

### 4.3 How JIT provisioning works

Every time `/exchange` or `/refresh` succeeds, the backend runs this logic (in `user_provisioning.py`):

1. **Derive a local username** from the Cognito `sub` claim: `cg:<sub>` (truncated to 50 chars).
2. **Look up** the user by username. If found, **update** `email` and `full_name` from the latest IdP claims (so name changes in Entra are reflected automatically).
3. If not found, **create** a new user with `UserCreate(username, full_name, email, password=<random>)`.
4. **Race-condition safe**: if two concurrent requests try to create the same user, the loser catches the integrity error and re-fetches the row the winner created.

The **`full_name` fallback chain**: `id_token.name` → `id_token.cognito:username` → `email` → `sub`.

---

## 5. Silent refresh — how sessions stay alive

When the internal access JWT expires (after 45 minutes), the frontend transparently refreshes it using the `midas_cg_rt` HttpOnly cookie — no user interaction needed.

```
Frontend detects 401 on any API call
  └─▶ authService.refreshAccessToken()
        └─▶ cognitoAuthService.refresh()
              └─▶ POST /api/v1/auth/cognito/refresh  (credentials: include → browser sends midas_cg_rt)
                    ├── Backend sends Cognito refresh_token to /oauth2/token (grant_type=refresh_token)
                    ├── Validates new id_token + access_token via JWKS
                    ├── Re-syncs local user from latest IdP claims (name/email may have changed)
                    ├── Creates new server session with fresh sid (rotation defense)
                    ├── Mints new internal Bearer JWT
                    ├── Optionally rotates the midas_cg_rt cookie (if Cognito returned a new refresh token)
                    └── Returns { access_token, expires_in, session_id, session_created_at, session_ttl_seconds }
```

**What happens when refresh fails?** The frontend's `httpUnauthorized.ts` handles it:
- Attempts **one** silent refresh
- Retries the original failed request
- If still 401 → dispatches `midas:session-expired` → shows a modal → user clicks OK → full logout + redirect to login

---

## 6. Logout — how everything gets cleaned up

Logout is a **multi-step cascade** that revokes tokens at every layer and ends the SSO session.

```
User clicks "Sign out" → UserContext.logout()
  └─▶ cognitoAuthService.logout()
        │
        ├─ POST /api/v1/auth/cognito/logout  (Authorization: Bearer <token>)
        │     ├── Step 1: Revoke Cognito refresh token via /oauth2/revoke (best-effort)
        │     ├── Step 2: Delete Redis session (invalidate the sid)
        │     ├── Step 3: Revoke all app refresh_tokens for this user in SQLite
        │     ├── Step 4: Clear midas_cg_rt and cg_login cookies
        │     └── Step 5: Return { cognito_logout_url, cognito_revoked, app_refresh_tokens_revoked }
        │
        ├─ authService.logout()  (local browser cleanup)
        │     ├── Clear localStorage: auth_token, user_data, chatSessions, datasets, connections
        │     ├── Clear session timer + meta (midas_session_*)
        │     ├── Clear sessionStorage entirely
        │     └── Dispatch 'midas:auth-changed' event → UserContext sets user to null
        │
        └─ window.location.assign(cognito_logout_url)
              └─ Cognito /logout?client_id=...&logout_uri=...
                    └─ Ends the Cognito Hosted UI session + federated Entra SSO session
                          └─ Redirects browser to COGNITO_LOGOUT_REDIRECT_URI (e.g. http://localhost:5173/)
```

> **`/logout-everywhere`** is currently an alias for `/logout` (refresh tokens are already revoked user-wide). It exists as a future extension point for per-device revocation.

---

## 7. Authorization

Authorization is currently **simple and authentication-based**:

- **All authenticated users** have equal access to all API endpoints.
- The frontend's `ProtectedRoute` component gates pages behind authentication — unauthenticated visitors are redirected to the login page.
- The `role` displayed in the UI header (e.g. "Data Analyst") is a **static default** set at login time — it is not sourced from Cognito groups or claims.
- **Future direction**: Cognito User Pool groups can be mapped to app roles via the `cognito:groups` claim, enabling fine-grained RBAC without code changes.

---

## 8. API endpoints & cookies

### Cognito auth endpoints (mounted at `/api/v1/auth/cognito`)

| Method | Path | Auth required? | Cookies involved | Purpose |
|--------|------|----------------|-----------------|---------|
| `GET` | `/login-url?vhash=<hex>` | No | **Sets** `cg_login` | Returns the Cognito authorize URL; generates `state` + `nonce` |
| `POST` | `/exchange` | No (cookie-bound) | **Reads** `cg_login`, **sets** `midas_cg_rt`, **clears** `cg_login` | Exchanges auth code for tokens; returns internal JWT + user profile |
| `POST` | `/refresh` | No (cookie-bound) | **Reads** `midas_cg_rt`, optionally **rotates** it | Silent token refresh; returns new internal JWT |
| `POST` | `/logout` | `Bearer <token>` | **Clears** `midas_cg_rt` + `cg_login` | Full logout; returns `cognito_logout_url` for browser redirect |
| `POST` | `/logout-everywhere` | `Bearer <token>` | Same as `/logout` | Alias for `/logout` (future: per-device revocation) |

### Cookie reference

| Cookie | HttpOnly | Secure | SameSite | Path | Max-Age | What's inside |
|--------|----------|--------|----------|------|---------|--------------|
| `cg_login` | Yes | Configurable | Lax | `/api/v1/auth/cognito` | 600s (10 min) | HS256-signed JWS: `{state, nonce, vhash, exp}` |
| `midas_cg_rt` | Yes | Configurable | Lax | `/api/v1/auth/cognito` | 30 days (configurable) | Raw Cognito refresh token |

Both cookies are **HttpOnly** (no JavaScript access) and **path-scoped** to `/api/v1/auth/cognito` so they are only sent on auth-related requests.

---

## 9. JWKS & token validation

All Cognito-issued JWTs are validated in `app/services/cognito/jwks.py` using `python-jose`:

- **JWKS caching**: Process-local async cache with 1-hour TTL and `asyncio.Lock` to prevent thundering-herd refreshes.
- **Key rotation**: If a token has an unknown `kid`, the cache is force-refreshed once before rejecting — so key rotation in Cognito doesn't require a backend restart.
- **Signature**: RS256 only (algorithm is enforced; tokens with other algorithms are rejected).
- **Standard claims**: `iss` (must match Cognito issuer URL), `exp` (with 30-second leeway).
- **`id_token` specifics**: `aud` must equal `client_id`; `nonce` must match cookie binding; `at_hash` is verified against the `access_token` (prevents token substitution).
- **`access_token` specifics**: `client_id` claim must match the app client (Cognito access tokens use `client_id` instead of the standard `aud` claim).

---

## 10. Environment variables

### Backend (`.env`)

```env
# ─── Core ────────────────────────────────────────────────────────────────
APP_ENV=development                 # "production" enforces SESSION_REQUIRE_REDIS + cookie-secret
SESSION_REQUIRE_REDIS=false         # true in prod: refuse in-memory session fallback
SESSION_TIMEOUT=3600                # server session TTL in seconds (default 60 min, min 600s).
                                    # Must be >= Cognito AccessTokenValidity (60 min default).
                                    # The server session must never expire before the JWT.

# ─── Internal JWT signing ────────────────────────────────────────────────
# Production: REQUIRED. Use Secrets Manager or Helm secret injection.
# Dev: leave unset → random per-process key generated (all JWTs invalidated on restart).
#JWT_SECRET_KEY=<32+ random bytes; generate: python3 -c "import secrets; print(secrets.token_urlsafe(48))">

# ─── Cognito (Entra ID federation is configured inside the Cognito user pool) ──
COGNITO_DOMAIN=https://<pool>.auth.<region>.amazoncognito.com
COGNITO_REGION=us-east-1
COGNITO_USER_POOL_ID=us-east-1_XXXXXXXXX
COGNITO_CLIENT_ID=<app-client-id>
# COGNITO_CLIENT_SECRET is OPTIONAL:
#   Confidential client ("Traditional web app"): set to the Cognito value.
#   Public SPA client ("Single-page application"): leave unset — PKCE is sufficient.
# COGNITO_CLIENT_SECRET=<secret>
COGNITO_REDIRECT_URIS=http://localhost:5173/auth/callback,https://app.example.com/auth/callback
COGNITO_LOGOUT_REDIRECT_URI=http://localhost:5173/
COGNITO_SCOPES=openid email profile
COGNITO_IDP_NAME=MicrosoftEntraID   # optional: skip the Cognito provider chooser
COGNITO_COOKIE_SECURE=false         # true in production (requires HTTPS); drives SameSite below
COGNITO_LOGIN_COOKIE_SECRET=<32+ byte HS256 key>   # required in prod; auto-generated in dev
COGNITO_LOGIN_COOKIE_TTL=600        # cg_login cookie TTL (seconds)
COGNITO_REFRESH_COOKIE_TTL_DAYS=5   # must be ≤ Cognito app client refresh token validity (client set to 5 days)

# ─── Redis for sessions (STRONGLY RECOMMENDED for local dev) ────────────
# Without Redis, sessions are in-memory and are wiped on every uvicorn reload
# (e.g. the file watcher can trigger when .prometheus_multiproc/*.db files are
# written). Each reload invalidates all active JWTs → immediate 401 for logged-in
# users → looks like "session expires after N minutes" (however long until reload).
# Resolution chain: SESSION_ELASTICACHE_SECRET_ARN → SESSION_REDIS_URL → REDIS_URL
SESSION_REDIS_URL=redis://localhost:6379/0      # brew install redis && brew services start redis
# SESSION_ELASTICACHE_SECRET_ARN=arn:aws:secretsmanager:...

# ─── CORS (credentials-mode cookies require explicit origins) ────────────
CORS_ALLOW_ORIGINS=http://localhost:5173,https://app.example.com

# ─── Legacy password login ──────────────────────────────────────────────
ENABLE_LEGACY_PASSWORD_LOGIN=false  # keep false; Cognito is the supported path
```

### Cookie SameSite policy matrix

The refresh cookie (`midas_cg_rt`) SameSite attribute is set automatically based on `COGNITO_COOKIE_SECURE`:

| `COGNITO_COOKIE_SECURE` | `SameSite` | Use case |
|---|---|---|
| `false` | `Lax` | Local dev — `localhost:5173` ↔ `localhost:8000` are same-site; browsers send cookie on same-site POST |
| `true` | `None; Secure` | Deployed — frontend `https://app.example.com` ↔ API `https://api.example.com` are cross-site; `SameSite=None; Secure` is required for `fetch(..., credentials:'include')` |

**Never** set `COGNITO_COOKIE_SECURE=true` without HTTPS — browsers reject `SameSite=None` without `Secure`.

### Frontend (`.env`)

```env
VITE_BASE_URL=http://localhost:8000              # Backend API base URL
VITE_COGNITO_DOMAIN=https://<pool>.auth.<region>.amazoncognito.com
VITE_COGNITO_CLIENT_ID=<app-client-id>
VITE_COGNITO_REDIRECT_URI=http://localhost:5173/auth/callback
VITE_COGNITO_LOGOUT_REDIRECT_URI=http://localhost:5173/
```

> **Security note:** All `VITE_*` variables are bundled into the JavaScript output.
> **Never** put `COGNITO_CLIENT_SECRET` in the frontend `.env`.

---

## 11. Redis session store — dev vs production

### Development (no Redis)

Leave `SESSION_REDIS_URL`, `REDIS_URL`, and `SESSION_ELASTICACHE_SECRET_ARN` **unset**.
Sessions live in process memory (`InMemorySessionStore`) and are lost on restart — this is fine for local `uvicorn --reload`.

### Development (with Redis)

```bash
docker compose -f docker-compose.dev.yml up redis
# then set:
SESSION_REDIS_URL=redis://localhost:6379/0
```

### Production

```env
APP_ENV=production
SESSION_REQUIRE_REDIS=true
SESSION_REDIS_URL=rediss://...   # or SESSION_ELASTICACHE_SECRET_ARN=arn:aws:...
```

If Redis is unreachable at startup, the process **fails fast** — k8s / ECS immediately surfaces the issue instead of silently losing sessions across pods.

---

## 12. Cognito app-client checklist

When setting up or verifying the Cognito app client, ensure:

- [ ] **Callback URL(s)** match `COGNITO_REDIRECT_URIS` exactly (case-sensitive, trailing-slash-sensitive)
- [ ] **Sign-out URL(s)** include `COGNITO_LOGOUT_REDIRECT_URI`
- [ ] **Authorization Code Grant** is enabled
- [ ] **OAuth scopes**: `openid`, `email`, `profile`
- [ ] **Token revocation is enabled** (required for `/logout` to actually revoke refresh tokens)
- [ ] **Entra IdP attribute mapping** includes at minimum `email` and `name`

---

## 13. Source file reference

### Backend

| File | What it does |
|------|-------------|
| `app/api/cognito_routes.py` | All 5 Cognito endpoints: `/login-url`, `/exchange`, `/refresh`, `/logout`, `/logout-everywhere` |
| `app/services/cognito/settings.py` | `CognitoSettings` dataclass — derives URLs, validates config, `lru_cache` singleton |
| `app/services/cognito/login_state.py` | `cg_login` JWS cookie: issue + verify (state, nonce, vhash binding) |
| `app/services/cognito/jwks.py` | Async JWKS cache, RS256 signature validation, `at_hash` verification |
| `app/services/cognito/oauth_client.py` | HTTP calls to Cognito `/oauth2/token` and `/oauth2/revoke` |
| `app/services/cognito/user_provisioning.py` | JIT provisioning: create/update local user from Cognito claims |
| `app/services/auth_service.py` | Internal JWT creation (HS256) + verification, password hashing |
| `app/core/session/contracts.py` | Interfaces: `ISessionStore`, `ISessionAuthenticator` |
| `app/core/session/session_backends.py` | `InMemorySessionStore`, `RedisSessionStore` |
| `app/core/session/session_manager.py` | `SessionManager` — create, validate, invalidate sessions |
| `app/core/session/session_factory.py` | `build_session_store()` with Redis URL chain + fallback |
| `app/core/session/redis_url_resolution.py` | Redis URL chain: Secrets Manager → explicit URL → shared URL |
| `app/models/user_database.py` | SQLite `users` + `refresh_tokens` CRUD |
| `app/models/schemas.py` | Pydantic models: `UserCreate`, `UserInDB`, `User`, `TokenData` |

### Frontend

| File | What it does |
|------|-------------|
| `src/services/cognitoAuthService.ts` | PKCE generation, `beginLogin`, `completeLogin`, `refresh`, `logout` |
| `src/services/authService.ts` | Bearer token storage (`localStorage`), session initialization, local logout |
| `src/services/authSessionExpiry.ts` | Client-side session TTL timer, `midas:session-expired` event |
| `src/services/httpUnauthorized.ts` | 401 interception: one-shot refresh, session-expired modal |
| `src/contexts/UserContext.tsx` | React context for current user state, login/logout methods |
| `src/pages/AuthCallback.tsx` | Handles `/auth/callback` redirect from Cognito |

---

## 14. Testing

Run all Cognito-related tests from the `backend/` directory:

```powershell
python -m unittest discover -s tests -p "test_cognito_*.py" -v
```

| Test file | What it covers |
|-----------|---------------|
| `test_cognito_login_state.py` | `cg_login` JWS roundtrip, state/verifier mismatch, tampered tokens, wrong signing secret |
| `test_cognito_settings.py` | Settings resolution, URL composition, missing-field errors, production guardrails, public SPA client |
| `test_cognito_user_provisioning.py` | Username derivation (`cg:` prefix, 50-char truncation), `full_name` fallback chain, JIT create/update, race condition |
| `test_cognito_oauth_client.py` | Confidential vs public app-client auth mode (`BasicAuth` vs `None`) |
