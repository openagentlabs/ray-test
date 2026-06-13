# Configuration playbook — Cognito + Langfuse v3

This playbook lists **exact** Langfuse v3 settings for Amazon Cognito per [Langfuse Authentication and SSO (self-hosted), Version v3](https://langfuse.com/self-hosting/security/authentication-and-sso). It also maps **MIDAS** files where values live today.

**Pinned Langfuse version for this repo:** image tag **`3.163`** (see [README](./README.md)).

---

## Part A — Cognito (User Pool + app client)

### A.1 User Pool

| Setting | Required? | Guidance |
| ------- | --------- | -------- |
| Region | **Yes** | `us-east-1` |
| Sign-in aliases / attributes | **Yes** | Ensure **email** is available and verified if you rely on verified-email security controls. |
| MFA | Optional | Organizational policy. |
| Self-registration | Optional | Disable if only admins create users. |
| SAML / OIDC federation **into** Cognito | Optional | Add IdPs on the pool if users should sign in via Entra etc.; Langfuse still uses the **Cognito** OAuth client. |

### A.2 App client (Langfuse-dedicated recommended)

| Setting | Required? | Value |
| ------- | --------- | ----- |
| App type | **Yes** | Traditional web application (server-side secret). |
| Generate client secret | **Yes** | **True** (matches NextAuth Cognito provider with confidential client). |
| OAuth flows | **Yes** | Authorization code grant. |
| OAuth scopes | **Yes** | **`openid`**, **`email`** (add `profile`, `phone` only if you need claims — MIDAS Terraform clients currently include `phone`, `profile`). |
| Callback URL(s) | **Yes** | `https://<YOUR_LANGFUSE_PUBLIC_HOST>/api/auth/callback/cognito` |
| Sign-out URL(s) | Recommended | e.g. `https://<YOUR_LANGFUSE_PUBLIC_HOST>/` |
| Identity providers | **Yes** | At minimum **`COGNITO`**; add federated IdPs if configured on the pool. |

**Critical:** Replace `<YOUR_LANGFUSE_PUBLIC_HOST>` with the **exact** host portion of `NEXTAUTH_URL` (no path). Example pattern from MIDAS dev overlay: host derived from `langfuse.nextauth.url` in `deploy/ai_gateway/helm/langfuse/values-midas-dev.yaml`.

### A.3 Issuer URL (for Langfuse)

**Required** string format ([NextAuth Cognito](https://next-auth.js.org/providers/cognito)):

```text
https://cognito-idp.us-east-1.amazonaws.com/<USER_POOL_ID>
```

Use your real `<USER_POOL_ID>`.

### A.4 Hosted UI domain

| Choice | What you record |
| ------ | ---------------- |
| Prefix domain | Cognito-assigned domain URL (no ACM). |
| Custom domain | Your `https://auth...` domain + ACM in `us-east-1` per AWS docs. |

Langfuse does **not** need you to paste the Hosted UI URL into `AUTH_COGNITO_*`; it needs **issuer**, **client id**, **secret**, and correct **callback** on the client.

---

## Part B — Langfuse (environment variables)

### B.1 Always required (already present in MIDAS Helm/Terraform)

Per [Langfuse configuration](https://langfuse.com/self-hosting/configuration):

| Variable | Purpose |
| -------- | ------- |
| `NEXTAUTH_URL` | Canonical **https** origin users use for Langfuse (no trailing slash). |
| `NEXTAUTH_SECRET` | Session encryption (K8s secret `next-auth` in MIDAS). |
| `SALT` | API key hashing (`salt-key`). |
| `ENCRYPTION_KEY` | App encryption (chart/secret wiring per deployment). |
| Database / ClickHouse / Redis / S3 | v3 requirements unchanged — already in overlay. |

**Helm mapping note:** `langfuse.nextauth.url` in `deploy/ai_gateway/helm/langfuse/values-midas-dev.yaml` drives chart wiring for NextAuth base URL — keep it **identical** to the user-facing URL scheme/host used in Cognito callbacks.

### B.2 Cognito SSO (add when enabling)

| Variable | Required? | Example / source |
| -------- | --------- | ---------------- |
| `AUTH_COGNITO_CLIENT_ID` | **Yes** | Cognito app client id. |
| `AUTH_COGNITO_CLIENT_SECRET` | **Yes** | Cognito app client secret. |
| `AUTH_COGNITO_ISSUER` | **Yes** | `https://cognito-idp.us-east-1.amazonaws.com/<POOL_ID>` |

Source of truth in MIDAS infra (after Terraform alignment): Secrets Manager secrets  
`langfuse-cognito-client-id-<eks_cluster_name>` and `langfuse-cognito-client-secret-<eks_cluster_name>` populated from `aws_cognito_user_pool_client.langfuse_observability_client` — **only valid after** that client’s callback URL matches `/api/auth/callback/cognito` and the correct hostname.

### B.3 Optional Langfuse auth flags

From [Authentication and SSO](https://langfuse.com/self-hosting/security/authentication-and-sso):

| Variable | When to use |
| -------- | ----------- |
| `AUTH_DISABLE_USERNAME_PASSWORD=true` | Force SSO only; **must** have working Cognito (or other SSO) first. |
| `AUTH_COGNITO_ALLOW_ACCOUNT_LINKING=true` | Migrating from local passwords to Cognito with same email — understand security trade-offs (email verification). |
| `AUTH_DISABLE_SIGNUP=true` | Block new self-service accounts (org invites behavior — see Langfuse docs). |
| `AUTH_DOMAINS_WITH_SSO_ENFORCEMENT` | Restrict domains to SSO-only. |
| `AUTH_COGNITO_CLIENT_AUTH_METHOD` | Rarely needed; default `client_secret_basic`. Try `AUTH_COGNITO_CHECKS` / `CLIENT_AUTH_METHOD` only if debugging provider quirks (documented in Langfuse “Additional configuration”). |
| `AUTH_TRUST_HOST` | MIDAS sets `"true"` in `values-midas-dev.yaml` for proxy/internal LB setups — **keep** unless Langfuse docs advise otherwise for your topology. |

### B.4 What **not** to mix without intent

| Approach | Callback path | Variables |
| -------- | ------------- | --------- |
| **Native Cognito** (recommended here) | `/api/auth/callback/cognito` | `AUTH_COGNITO_*` |
| **Generic OIDC** | `/api/auth/callback/custom` | `AUTH_CUSTOM_CLIENT_ID`, `AUTH_CUSTOM_CLIENT_SECRET`, `AUTH_CUSTOM_ISSUER`, `AUTH_CUSTOM_NAME`, … |

MIDAS Terraform today points callbacks at **`/custom`** — pair that only with **`AUTH_CUSTOM_*`**, or change Terraform to **`/cognito`** and use **`AUTH_COGNITO_*`**.

---

## Part C — Helm overlay snippet (conceptual)

Not applied in-repo today; minimal illustration for `deploy/ai_gateway/helm/langfuse/values-midas-dev.yaml` **after** secrets and Cognito client are fixed:

```yaml
langfuse:
  additionalEnv:
    # ... existing entries ...
    - name: AUTH_COGNITO_CLIENT_ID
      valueFrom:
        secretKeyRef: { name: langfuse-cognito-client-id, key: langfuse-cognito-client-id }
    - name: AUTH_COGNITO_CLIENT_SECRET
      valueFrom:
        secretKeyRef: { name: langfuse-cognito-client-secret, key: langfuse-cognito-client-secret }
    - name: AUTH_COGNITO_ISSUER
      value: "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_XXXXXXXXX"
    # Optional:
    # - name: AUTH_DISABLE_USERNAME_PASSWORD
    #   value: "true"
```

**Kubernetes secret key names** must match what ORD1 Terraform actually writes (`langfuse_helm_chart_secrets` uses map keys → secret names; verify keys inside each Secret match `secretKeyRef.key`).

---

## Part D — Checklist (copy/paste)

### Cognito

- [ ] User Pool in `us-east-1`
- [ ] Domain configured (prefix **or** custom with ACM `us-east-1`)
- [ ] App client: **secret enabled**, code grant, scopes include **`openid` + `email`**
- [ ] Callback: `https://<LANGFUSE_HOST>/api/auth/callback/cognito`
- [ ] Issuer recorded: `https://cognito-idp.us-east-1.amazonaws.com/<pool_id>`

### Langfuse

- [ ] `NEXTAUTH_URL` == `https://<LANGFUSE_HOST>` (same host as Cognito callback origin)
- [ ] `AUTH_COGNITO_CLIENT_ID`, `AUTH_COGNITO_CLIENT_SECRET`, `AUTH_COGNITO_ISSUER` set on **web** pods
- [ ] Worker pods unchanged for Cognito (auth is web)
- [ ] Optional: `AUTH_DISABLE_USERNAME_PASSWORD` only after validation

### MIDAS integration hygiene

- [ ] Terraform `callback_urls` for the Langfuse client updated from `/custom` → `/cognito` **if** using `AUTH_COGNITO_*`
- [ ] Hostname in Terraform matches `langfuse.nextauth.url`
- [ ] Jenkins deploy uses image tag **3.163** (or updated tag with docs refreshed)
