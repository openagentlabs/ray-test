# Architecture and call flows

How the routing tier fits together locally: **decision plane** (router.svc) vs **data plane** (Envoy), and the two pool types (**login** vs **backend lease**).

## Design principles (local)

| Principle | Local manifestation |
|-----------|---------------------|
| Routing is security | `sub` from cookie / `x-test-sub` / JWT — never `Host` from client |
| ALB does not pick pods | Envoy + ext_authz + DFP pick upstream inside the cluster |
| Decision ≠ data plane | gRPC assignment and Check on router; HTTP body flows Envoy → pod |
| Fail closed | Authz error or missing lease → deny or login-pod `403` on `/api/*` |

## Pool model

```mermaid
stateDiagram-v2
  [*] --> NoLease: User authenticates
  NoLease --> LoginPool: HTTP via Envoy
  NoLease --> HasLease: AcquireLease (gRPC)
  HasLease --> BackendPod: HTTP via Envoy
  HasLease --> NoLease: ReleaseLease (gRPC)
  LoginPool --> NoLease: Still no backend lease
```

| State | Postgres | Envoy upstream |
|-------|----------|----------------|
| **No backend lease** | No row in `pm_user_assignments` for `sub` | `login-pod:8080` |
| **Leased** | Assignment + claimed backend pod | `backend-pool-node-N:8080` |

Login pool does **not** consume a backend slot. Only `AcquireLease` marks a backend `claimed`.

---

## Flow 1 — HTTP API without backend lease

Typical: user logged in (cookie) but has not called `AcquireLease`.

```mermaid
sequenceDiagram
  autonumber
  participant Browser
  participant Next as Next.js BFF
  participant Envoy
  participant Authz as router ext_authz
  participant DDB as Postgres
  participant Login as login-pod

  Browser->>Next: GET /api/backend/api/v1/me
  Note over Next: Forwards Cookie pod_manager_user
  Next->>Envoy: GET /api/v1/me + Cookie
  Envoy->>Authz: gRPC Check(headers)
  Authz->>DDB: get assignment(sub)
  DDB-->>Authz: none
  Authz-->>Envoy: ALLOW upstream=login-pod:8080, x-user-sub
  Envoy->>Login: GET /api/v1/me
  Login-->>Envoy: 403 no_backend_lease
  Envoy-->>Next: 403
  Next-->>Browser: 403 JSON
```

**Expected body (login-pod):**

```json
{
  "error": "no_backend_lease",
  "message": "Acquire a backend lease before calling the backend API."
}
```

---

## Flow 2 — Acquire backend lease (control plane)

Lease operations **never** go through Envoy in the test client; they use gRPC directly.

```mermaid
sequenceDiagram
  autonumber
  participant UI as Next.js or CLI
  participant API as router gRPC :8804
  participant Handler as PoolRpcHandler
  participant DDB as Postgres

  UI->>API: AcquireLease(sub=email)
  API->>Handler: acquire_lease
  Handler->>DDB: TransactWrite (claim pod + assignment)
  DDB-->>Handler: ok
  Handler-->>API: pod_id, pod_dns, epoch
  API-->>UI: LeaseResult
```

After this, ext_authz finds an assignment and returns the backend pod DNS.

---

## Flow 3 — HTTP API with backend lease

```mermaid
sequenceDiagram
  autonumber
  participant Browser
  participant Next as Next.js BFF
  participant Envoy
  participant Authz as router ext_authz
  participant DDB as Postgres
  participant Backend as backend_pool_node

  Browser->>Next: GET /api/backend/api/v1/me
  Next->>Envoy: GET /api/v1/me + Cookie
  Envoy->>Authz: gRPC Check
  Authz->>DDB: get assignment(sub)
  DDB-->>Authz: pod_id, pod_dns
  Authz-->>Envoy: ALLOW upstream=backend-pool-node-0:8080
  Envoy->>Backend: GET /api/v1/me + x-user-sub
  Backend-->>Envoy: 200 JSON
  Envoy-->>Next: 200
  Next-->>Browser: 200 JSON
```

**Example success JSON:**

```json
{
  "service": "backend_pool_node",
  "pod_id": "backend-pool-node-0",
  "backend_pool_node": "backend-pool-node-0",
  "sub": "alice@example.com",
  "message": "Exclusive backend lease is active for this identity."
}
```

---

## Flow 4 — Login through Envoy (browser)

```mermaid
sequenceDiagram
  autonumber
  participant Browser
  participant Next as Next.js
  participant Envoy
  participant Authz as router ext_authz
  participant Login as login-pod

  Browser->>Next: POST /api/auth/login {user_name, password}
  Note over Next: Server-side; sets cookie on :3000
  Next->>Envoy: POST /login JSON
  Note over Next,Envoy: First login may need identity;<br/>BFF does not send x-test-sub today
  Envoy->>Authz: Check
  Authz-->>Envoy: ALLOW (login upstream) or DENY
  Envoy->>Login: POST /login
  Login-->>Envoy: 200 + Set-Cookie
  Envoy-->>Next: 200
  Next-->>Browser: 200 + pod_manager_user cookie
```

For **CLI/curl** through Envoy, send `x-test-sub: <email>` on `POST /login` in dev mode. Direct login without Envoy: `http://localhost:18082/login`.

---

## Flow 5 — CLI HTTP smoke (`route` / `e2e`)

```mermaid
sequenceDiagram
  participant CLI as pod-manager CLI
  participant API as router :8804
  participant Envoy
  participant Backend as backend_pool_node

  CLI->>API: AcquireLease (gRPC)
  API-->>CLI: pod_id
  loop e2e repeats
    CLI->>Envoy: GET /api/v1/me + x-test-sub
    Envoy->>Backend: proxied request
    Backend-->>CLI: JSON pod_id
  end
  CLI->>API: ReleaseLease (gRPC)
```

CLI bypasses Next.js BFF; uses **dev header** instead of cookie.

---

## Flow 6 — Release lease

```mermaid
sequenceDiagram
  participant UI as Next or CLI
  participant API as router :8804
  participant DDB as Postgres
  participant Envoy
  participant Login as login-pod

  UI->>API: ReleaseLease(sub)
  API->>DDB: transact release + free pod
  UI->>Envoy: GET /api/v1/me (optional)
  Envoy->>Login: routed again
  Login-->>UI: 403 no_backend_lease
```

---

## ext_authz response headers (internal)

Envoy uses metadata from a successful Check:

| Header | Set by | Purpose |
|--------|--------|---------|
| `x-route-upstream` | router.svc | Host for dynamic forward proxy |
| `x-user-sub` | router.svc | Trusted identity for backend pods |

Backend apps must treat `x-user-sub` as authoritative only when the request came through Envoy (production: NetworkPolicy restricts ingress).

---

## Health check path (no authz)

```mermaid
flowchart LR
  curl[curl :8080/healthz] --> EnvoyHealth[Envoy health listener]
  EnvoyHealth --> OK[200 ok]
```

Does not call router.svc or pods — used by compose/Kubernetes probes.

---

## Capacity and “pool full”

```mermaid
flowchart TD
  A[AcquireLease] --> B{Free backend pod?}
  B -->|yes| C[Claim + assign]
  B -->|no| D[gRPC RESOURCE_EXHAUSTED]
  D --> E[Web: redirect /wait]
  D --> F[CLI: error exit]
```

Local seed has **2** backends → at most **2** simultaneous leases.

---

## Related reading

- Component reference: [components.md](components.md)  
- API listing: [apis-and-clients.md](apis-and-clients.md)  
- Web journeys: [web-test-client.md](web-test-client.md)
