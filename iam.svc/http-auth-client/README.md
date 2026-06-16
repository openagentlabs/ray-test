# IAM HTTP auth client (`@arb/http-auth-client`)

Zod-validated HTTP client for the IAM browser-facing auth API (login, refresh, validate, logout, JWKS).

<div align="left">

<small>

| | |
|:--|:--|
| **Package** | `@arb/http-auth-client` |
| **Server HTTP auth** | `iam.svc/server` port **8873** |
| **Routes** | `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/validate`, `/auth/jwks`, `/.well-known/jwks.json` |

</small>

</div>

---

## 1. Purpose

HTTP client and token manager for JWT-based browser auth against the FastAPI routes in `iam.svc/server/src/iam_service/http_transport/routes.py`. Maps server error JSON to `IamAuthClientError`.

---

## 2. When to use it

| Need | Use |
|------|-----|
| Browser or SPA login / refresh / logout | `IamAuthClient` + optional `AuthTokenManager` |
| Server-side user/RBAC CRUD | `iam.svc/server` gRPC from other `*.svc/` backends — not this package |
| OAuth/SAML redirect (`/auth/authorize`) | Not implemented — server returns `501` until IdP driver supports it |

---

## 3. Layout

| Path | Role |
|------|------|
| `src/index.ts` | `IamAuthClient`, Zod response schemas |
| `src/token-manager.ts` | `AuthTokenManager`, `TokenStorage` |
| `test/unit/` | Token manager behavior |
| `test/integration/` | HTTP client route wiring with mocked `fetch` |

---

## 4. Run / test

```bash
npm install
npm test
```

Example:

```typescript
import { AuthTokenManager, IamAuthClient, InMemoryTokenStorage } from "@arb/http-auth-client";

const client = new IamAuthClient({ baseUrl: "http://127.0.0.1:8873" });
const manager = new AuthTokenManager({ client, storage: new InMemoryTokenStorage() });
await manager.login("user@example.com", "password");
const token = await manager.getValidAccessToken();
```

---

## 12. Related

| Topic | Path |
|-------|------|
| IAM service root | **`../README.md`** |
| Solution ports | **`.cursor/rules/solution/solution.mdc`** |
