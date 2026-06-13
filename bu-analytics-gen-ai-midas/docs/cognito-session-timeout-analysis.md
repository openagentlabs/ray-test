# Cognito Session Timeout — Root Cause Analysis

**Date:** 2026-05-12  
**Scope:** Frontend (React), Backend (FastAPI), AWS Cognito, ALB — MIDAS dev environment  
**User Pool:** `us-east-1_5JL0dpXwK`  
**App Client:** `Exldecisionai-Dev` (`1j436t8d6g8ggklvtcti73s141`)

---

## ID Reference

| ID | Category | Short Title |
|----|----------|-------------|
| ISU0001 | 🔴 Bug | Frontend session timer fires logout, not refresh |
| ISU0002 | 🔴 Bug | No proactive token refresh — reactive 401-only |
| ISU0003 | 🔴 Bug | Redis sid TTL is fixed window, not sliding |
| ISU0004 | 🟡 Warning | `SESSION_TIMEOUT` hardcoded fallback mismatch |
| ISU0005 | 🟡 Warning | `SESSION_TIMEOUT` not set explicitly in Helm |
| OBS0001 | 🟢 OK | Cognito refresh token 5-day validity — correctly configured |
| OBS0002 | 🟢 OK | Cognito access / id token validity — 60 min |
| OBS0003 | 🟢 OK | Refresh cookie path and TTL — correctly scoped |
| OBS0004 | 🟢 OK | Post-refresh timer reset — works correctly |
| OBS0005 | 🟢 OK | ALB idle timeout — 3600s, not the culprit |
| OBS0006 | 🟢 OK | Gunicorn worker timeout — 3600s, not the culprit |
| OBS0007 | 🟢 OK | ALB sticky-session duration — 86400s, not the culprit |
| FIX0001 | 🔴 Must fix | Replace logout timer with proactive refresh timer |
| FIX0002 | 🔴 Must fix | Add sliding TTL extension to Redis sid |
| FIX0003 | 🟡 Should fix | Reconcile `SESSION_TIMEOUT` fallback defaults |
| FIX0004 | 🟡 Should fix | Set `SESSION_TIMEOUT` explicitly in Helm values |
| FIX0005 | 🟢 No action | Cognito client, refresh cookie, ALB — no change needed |

---

## Traffic Light Summary

| ID | Area | Status | Finding |
|----|------|--------|---------|
| OBS0001 | Cognito refresh token (5 days) | 🟢 OK | Cookie TTL and Cognito client validity both set to 5 days — they match |
| OBS0002 | Cognito access / id token validity | 🟢 OK | 60 minutes on both — correct and consistent with internal JWT |
| OBS0005 | ALB idle timeout | 🟢 OK | 3600s (60 min) — not the 20-min culprit |
| OBS0006 | Gunicorn worker timeout | 🟢 OK | 3600s — not the culprit |
| OBS0007 | ALB sticky-session duration | 🟢 OK | 86400s (24h) — not the culprit |
| OBS0003 | Refresh cookie path restriction | 🟡 Warning | Cookie scoped to `/api/v1/auth/cognito` — correct for the refresh call, but browser will not send it on any other path |
| ISU0004 | `SESSION_TIMEOUT` default mismatch | 🟡 Warning | `config.py` default = 3600s; `session_factory.py` fallback = 5400s — inconsistency |
| ISU0005 | `SESSION_TIMEOUT` not set in Helm | 🟡 Warning | Env var not explicitly injected — relies on code defaults |
| ISU0001 | Frontend session timer behaviour | 🔴 Bug | Timer fires **logout**, not **refresh**, when it expires |
| ISU0002 | Proactive token refresh | 🔴 Missing | No scheduled refresh before JWT expiry — system is reactive (401-only) |
| ISU0003 | Redis sid TTL sliding window | 🔴 Missing | Sid TTL not extended on each API call — expires at fixed 3600s from last refresh |

---

## 1. Architecture — How the Parts Fit Together

```
Browser (React)
  │
  ├─ authSessionExpiry.ts   ← client-side countdown timer  [ISU0001, ISU0002]
  ├─ apiInterceptor.ts      ← catches 401 → calls cognitoAuthService.refresh()
  ├─ cognitoAuthService.ts  ← POST /api/v1/auth/cognito/refresh (sends midas_cg_rt cookie)
  │
  ▼
AWS ALB  (idle_timeout = 3600s)  [OBS0005]
  │
  ▼
EKS Pod — FastAPI (GUNICORN_TIMEOUT = 3600s)  [OBS0006]
  ├─ SessionValidationMiddleware  ← validates Bearer JWT + Redis sid  [ISU0003]
  ├─ SessionManager               ← SESSION_TIMEOUT = 3600s  [ISU0004]
  ├─ cognito_routes.py /refresh   ← reads midas_cg_rt HttpOnly cookie  [OBS0003]
  │    └─ calls Cognito /oauth2/token → new internal JWT + new Redis sid
  └─ auth_service.py              ← ACCESS_TOKEN_EXPIRE_MINUTES = 60
  │
  ▼
AWS Cognito (us-east-1_5JL0dpXwK)
  AccessTokenValidity  : 60 min   [OBS0002]
  IdTokenValidity      : 60 min   [OBS0002]
  RefreshTokenValidity : 5 days   [OBS0001]
  │
  ▼
Redis (ElastiCache) — server-side session store (sid key, TTL = SESSION_TIMEOUT)  [ISU0003]
```

---

## 2. All Timeout / TTL Values — Live vs Code

| ID | Layer | Parameter | Value | Unit | Source |
|----|-------|-----------|-------|------|--------|
| OBS0002 | Cognito app client | `AccessTokenValidity` | 60 | minutes | AWS CLI (live) |
| OBS0002 | Cognito app client | `IdTokenValidity` | 60 | minutes | AWS CLI (live) |
| OBS0001 | Cognito app client | `RefreshTokenValidity` | 5 | days | AWS CLI (live) |
| OBS0002 | Backend internal JWT | `ACCESS_TOKEN_EXPIRE_MINUTES` | 60 | minutes | `backend/app/services/auth_service.py:27` |
| ISU0003 | Backend server session (Redis sid) | `SESSION_TIMEOUT` | 3600 | seconds | `backend/app/core/config.py:537` |
| ISU0004 | Session factory fallback | `ttl` fallback default | 5400 | seconds | `backend/app/core/session/session_factory.py:61` |
| OBS0001 | Refresh cookie browser max-age | `COGNITO_REFRESH_COOKIE_TTL_DAYS` | 5 | days | `backend/app/core/config.py:638` |
| OBS0003 | Refresh cookie path scope | `_COOKIE_PATH` | `/api/v1/auth/cognito` | path | `backend/app/api/cognito_routes.py:60` |
| OBS0005 | ALB idle timeout | `idle_timeout.timeout_seconds` | 3600 | seconds | AWS CLI (live) |
| OBS0005 | ALB client keep-alive | `client_keep_alive.seconds` | 3600 | seconds | AWS CLI (live) |
| OBS0006 | Gunicorn worker timeout | `GUNICORN_TIMEOUT` | 3600 | seconds | `deploy/ecs-app/helm/midas-api-backend-svc/templates/deployment.yaml` |
| OBS0007 | ALB sticky-session duration | `stickySession.durationSeconds` | 86400 | seconds | `deploy/ecs-app/helm/midas-api-backend-svc/values.yaml:53` |
| ISU0001 | Frontend client session timer default | `DEFAULT_TTL_SECONDS` | 3600 | seconds | `frontend/src/services/authSessionExpiry.ts:12` |
| ISU0001 | Frontend timer TTL source | `session_ttl_seconds` from API response | 3600 | seconds | `frontend/src/services/authService.ts:96–100` |

---

## 3. Issues — Root Cause Findings

| ID | Root Cause | Severity | Files Affected | Detail |
|----|-----------|----------|----------------|--------|
| ISU0001 | **Frontend session timer fires logout, not refresh, on expiry** | 🔴 Critical | `frontend/src/services/authSessionExpiry.ts:79–82` | `scheduleClientSessionTimer()` calls `dispatchSessionExpiredOnce()` on timeout — this shows the session-expired modal and logs the user out. It does **not** attempt `cognitoAuthService.refresh()` first. The refresh token is still valid (5 days) but is never used when the timer fires. |
| ISU0002 | **No proactive token refresh — system is purely reactive (401-triggered only)** | 🔴 Critical | `frontend/src/services/cognitoAuthService.ts:186`, `frontend/src/services/httpUnauthorized.ts:76` | Refresh only occurs when an API call returns 401. If the user is idle, on a long-running operation, or on a page that makes no API calls, the JWT expires silently. The next API call gets a 401 and refresh is attempted — but if the timer fires first (ISU0001), the user is logged out before the 401 refresh can succeed. |
| ISU0003 | **Redis server session sid TTL is fixed window, not sliding** | 🔴 Critical | `backend/app/core/session/session_manager.py:30–33`, `backend/app/middleware/session_validation.py` | `create_session()` sets a fixed TTL of `SESSION_TIMEOUT` seconds (3600s). The middleware validates the sid but does not extend its TTL. After exactly 3600s from the last `/exchange` or `/refresh`, the sid expires in Redis. The next API call fails sid validation and returns 401 even if the JWT is still valid — which can coincide exactly with the timer in ISU0001. |
| ISU0004 | **`SESSION_TIMEOUT` fallback in `session_factory.py` (5400s) does not match `config.py` default (3600s)** | 🟡 Warning | `backend/app/core/session/session_factory.py:61`, `backend/app/core/config.py:537` | `build_session_manager()` uses `getattr(settings, "SESSION_TIMEOUT", 5400)` as its fallback, but `Settings.SESSION_TIMEOUT` already defaults to 3600. If `SESSION_TIMEOUT` env var is not set, `settings.SESSION_TIMEOUT = 3600` (from `config.py`) and the factory reads it correctly — but the two different hardcoded fallbacks (3600 vs 5400) are confusing and could diverge if `config.py` is changed. |
| ISU0005 | **`SESSION_TIMEOUT` env var not explicitly set in Helm deployment values** | 🟡 Warning | `deploy/ecs-app/helm/midas-api-backend-svc/values.yaml`, `deploy/ecs-app/helm/midas-api-backend-svc/values-midas-dev.yaml` | The pod relies on the code default (3600s from `config.py`). If an operator changes the code default without a matching Helm change, the runtime behaviour silently shifts. Explicitly setting `SESSION_TIMEOUT` in Helm makes the intent unambiguous and operational. |

---

## 4. Observations — What Is Working Correctly

| ID | Observation | Status | Files / Evidence | Detail |
|----|------------|--------|-----------------|--------|
| OBS0001 | **Cognito refresh token (5-day) validity is configured correctly end-to-end** | 🟢 OK | `backend/app/core/config.py:638`, `backend/app/api/cognito_routes.py:120`, AWS CLI (live) | `COGNITO_REFRESH_COOKIE_TTL_DAYS=5` → 432000s cookie max-age. Cognito `RefreshTokenValidity=5 days`. These match. The `midas_cg_rt` cookie is correctly HttpOnly and survives browser restarts. The 5-day refresh would work if ISU0001 and ISU0002 were fixed. |
| OBS0002 | **Cognito access and id token validity (60 min) matches internal JWT expiry** | 🟢 OK | `backend/app/services/auth_service.py:27`, AWS CLI (live) | `ACCESS_TOKEN_EXPIRE_MINUTES = 60` matches Cognito `AccessTokenValidity = 60 min` and `IdTokenValidity = 60 min`. Consistent. |
| OBS0003 | **Refresh cookie path scope is correctly set to the refresh endpoint only** | 🟢 OK | `backend/app/api/cognito_routes.py:60` | `_COOKIE_PATH = "/api/v1/auth/cognito"` — the browser sends `midas_cg_rt` only when calling the refresh endpoint, which is correct. `cognitoAuthService.refresh()` calls `/api/v1/auth/cognito/refresh` with `credentials: 'include'`, so the cookie is sent. |
| OBS0004 | **After a successful `/refresh` call, the frontend timer is correctly rescheduled** | 🟢 OK | `backend/app/api/cognito_routes.py:452`, `frontend/src/services/authService.ts:86–103` | `/refresh` returns `session_created_at: int(time.time())`. `setSessionFromApiResponse()` calls `persistSessionMetaFromApi(created, ttl, ...)` → `scheduleClientSessionTimer()`. If refresh occurs before the timer fires, the countdown resets correctly. This is the desired behaviour — it just needs ISU0001/ISU0002 fixed so refresh is triggered proactively. |
| OBS0005 | **ALB idle timeout (3600s) is not the cause of the 20-minute timeout** | 🟢 OK | AWS CLI (live) | `idle_timeout.timeout_seconds = 3600`. This would only cause a 504 on long-lived HTTP connections idle for >60 min — not a silent auth expiry at 20 min. |
| OBS0006 | **Gunicorn worker timeout (3600s) is not the cause of the 20-minute timeout** | 🟢 OK | `deploy/ecs-app/helm/midas-api-backend-svc/templates/deployment.yaml` | `GUNICORN_TIMEOUT = 3600`. This controls per-worker request timeout, not session lifetime. |
| OBS0007 | **ALB sticky-session duration (86400s) is not the cause of the 20-minute timeout** | 🟢 OK | `deploy/ecs-app/helm/midas-api-backend-svc/values.yaml:53` | `stickySession.durationSeconds: 86400`. The ALB stickiness cookie (`AWSALB`) survives for 24 hours — well beyond any observed timeout window. |

---

## 5. The Exact Timeout Sequence

| Time | Event | Related ID | Result |
|------|-------|-----------|--------|
| T+00:00 | User logs in. Internal JWT minted (exp = T+60min). Redis sid created (TTL = 3600s). Frontend timer set to fire at T+60min. | OBS0004 | Authenticated |
| T+00–20 | User is active. API calls succeed. JWT valid, sid valid. | — | OK |
| T+20:xx | User starts a long operation (upload, training, analysis). No API calls made during the operation. | ISU0002 | JWT still valid — no refresh triggered |
| T+60:00 | Frontend timer fires → `dispatchSessionExpiredOnce()` → session-expired modal. **No refresh attempted.** Redis sid also expires at this exact moment. | ISU0001, ISU0003 | User sees "session expired" — logged out |
| T+60:00 | **Had** an API call fired at T+59:59, the interceptor would have attempted `cognitoAuthService.refresh()` → new JWT + new Redis sid → timer reset → user continues. **This path only works if an API call fires before the timer.** | ISU0002 | Would have worked — race condition |

> **The 20-minute figure** most likely arises from an earlier `SESSION_TIMEOUT` env var set to `1200` (20 minutes) in a prior deployment (see ISU0005 — no explicit Helm override), or a mismatch where the Redis sid was expiring earlier than the JWT. The failure pattern is the same regardless of the exact value: the timer fires logout before the refresh path is exercised.

---

## 6. Why the 5-Day Refresh Token Is Not Working As Expected

| ID | User Expectation | Actual Behaviour | Gap |
|----|-----------------|-----------------|-----|
| ISU0001 | User stays logged in; token silently refreshed | Refresh token valid 5 days ✅. Cookie survives 5 days ✅. **But** timer fires `logout` (not `refresh`) at 60 minutes | Timer fires wrong action |
| ISU0002 | Silent token refresh when JWT expires | Refresh only triggers on a **401 from an API call**. During idle periods or long operations with no API calls, no refresh is attempted | No proactive refresh |
| OBS0004 | After refresh, session continues seamlessly | If refresh succeeds, new JWT + new Redis sid are issued and the frontend timer resets ✅. **This part works** — but only if the 401 path is hit before the timer fires | Timer race condition |
| ISU0003 | Backend session stays alive during long operations | Redis sid TTL is fixed at `SESSION_TIMEOUT` seconds from the last `/exchange` or `/refresh`. Not extended on each API call. | No sliding sid window |
| OBS0001 | 5-day session with automatic renewal | The Cognito refresh token ✅, the cookie ✅, and the backend `/refresh` endpoint ✅ all support this. **Only ISU0001 and ISU0002 block it.** | Frontend timer + no proactive refresh |

---

## 7. Proposed Fixes

| ID | Fix | Related Issue | File | Change Required | Priority |
|----|-----|--------------|------|----------------|----------|
| FIX0001 | **Replace logout timer with proactive refresh timer** — schedule refresh at T-5min (55 min); only fire logout if refresh fails | ISU0001, ISU0002 | `frontend/src/services/authSessionExpiry.ts` | Change `scheduleClientSessionTimer()` to call `cognitoAuthService.refresh()` at T-5min; call `dispatchSessionExpiredOnce()` only if refresh returns `false` | 🔴 Must fix |
| FIX0002 | **Add sliding TTL extension to Redis sid on each authenticated request** | ISU0003 | `backend/app/core/session/session_backends.py`, `backend/app/middleware/session_validation.py` | Add `extend(session_id, ttl)` method to `ISessionStore` and `RedisSessionStore`; call it in `SessionValidationMiddleware.dispatch()` after successful `authenticate_access_token` | 🔴 Must fix |
| FIX0003 | **Reconcile `SESSION_TIMEOUT` fallback between `config.py` (3600) and `session_factory.py` (5400)** | ISU0004 | `backend/app/core/session/session_factory.py:61` | Change `getattr(settings, "SESSION_TIMEOUT", 5400)` to `getattr(settings, "SESSION_TIMEOUT", 3600)` | 🟡 Should fix |
| FIX0004 | **Set `SESSION_TIMEOUT` explicitly in Helm values** | ISU0005 | `deploy/ecs-app/helm/midas-api-backend-svc/values.yaml` or `values-midas-dev.yaml` | Add `SESSION_TIMEOUT: "3600"` to the pod env section (or `7200` if longer sessions are desired) | 🟡 Should fix |
| FIX0005 | **No change required to Cognito client, refresh cookie, or ALB** | OBS0001, OBS0005 | — | Cognito refresh token (5 days), cookie TTL (5 days), ALB idle timeout (3600s) are all correctly configured | 🟢 No action |

---

## 8. Key File Reference

| ID | File | Role in Auth Flow |
|----|------|------------------|
| ISU0001, ISU0002 | `frontend/src/services/authSessionExpiry.ts` | Client-side session countdown timer — fires logout on expiry (the primary bug) |
| ISU0002 | `frontend/src/services/cognitoAuthService.ts` | PKCE login, `/refresh`, `/logout` calls to backend |
| OBS0004 | `frontend/src/services/authService.ts` | Bearer token storage, `initializeAuth`, `refreshAccessToken`, timer reset on refresh |
| ISU0002 | `frontend/src/services/apiInterceptor.ts` | Catches 401s from API calls, triggers refresh once (reactive only) |
| ISU0002 | `frontend/src/services/httpUnauthorized.ts` | 401 handling: refresh → retry → session-expired modal |
| OBS0003 | `frontend/src/services/authHeaders.ts` | Builds `Authorization: Bearer` + `X-Session-Id` headers |
| OBS0001, OBS0003 | `backend/app/api/cognito_routes.py` | `/exchange`, `/refresh`, `/logout` endpoints; sets `midas_cg_rt` cookie |
| OBS0002 | `backend/app/services/auth_service.py` | JWT mint/verify, `ACCESS_TOKEN_EXPIRE_MINUTES = 60` |
| OBS0001 | `backend/app/services/cognito/settings.py` | Cognito config: domain, client id, cookie TTLs |
| ISU0003, ISU0004 | `backend/app/core/config.py` | `SESSION_TIMEOUT = 3600`, `COGNITO_REFRESH_COOKIE_TTL_DAYS = 5` |
| ISU0003 | `backend/app/core/session/session_manager.py` | `create_session()` — sets fixed TTL; `authenticate_access_token()` — validates sid |
| ISU0004 | `backend/app/core/session/session_factory.py` | Builds `SessionManager` with mismatched fallback TTL (5400 vs 3600) |
| ISU0003 | `backend/app/middleware/session_validation.py` | Validates Bearer + sid on every request; does not extend sid TTL |
| ISU0005 | `deploy/ecs-app/helm/midas-api-backend-svc/values.yaml` | `GUNICORN_TIMEOUT=3600`, `stickySession.durationSeconds=86400`; missing `SESSION_TIMEOUT` |
| OBS0006 | `deploy/ecs-app/helm/midas-api-backend-svc/templates/deployment.yaml` | Injects `GUNICORN_TIMEOUT=3600` env var into pod |

---

*Generated by MIDAS Cursor Agent — analysis based on live AWS CLI output and codebase review, 2026-05-12.*
