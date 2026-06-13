# Deployment plan — Cognito for Langfuse (MIDAS-oriented)

Ordered steps to stand up **Amazon Cognito** for **Langfuse v3** with the **smallest AWS footprint**: one **User Pool** and one (or more) **User Pool app clients**. No extra AWS services are **required** unless you choose optional features below.

**Region:** `us-east-1` only (MIDAS solution constraint).

**Official behavior:** Langfuse documents Cognito SSO via `AUTH_COGNITO_*` and callback `/api/auth/callback/cognito` ([Authentication and SSO — v3](https://langfuse.com/self-hosting/security/authentication-and-sso)).

---

## Prerequisites (explicit)

| Prerequisite | Required? | Notes |
| ------------ | --------- | ----- |
| Langfuse **public base URL** users will use (HTTPS) | **Yes** | Must match `NEXTAUTH_URL` (see configuration playbook). For MIDAS dev this is currently `https://exldecision-ai-dev-aigw-langfuse.exlservice.com` in Helm — confirm for your environment. |
| DNS + TLS for that hostname | **Yes** | MIDAS uses internal ALB + ACM (ORD1 publishes cert ARN into `langfuse-alb-config`). |
| Corporate network path to Langfuse | **Yes** | Internal ALB: VPN / private network. |
| Egress from EKS/VPC to Cognito public endpoints | **Yes** | Langfuse server exchanges OAuth codes with Cognito; browsers hit Hosted UI on the public internet. Align with MIDAS egress (Transit Gateway) and firewall allowlists if applicable. |
| Langfuse image consistent with v3 auth docs | **Yes** | MIDAS pins **3.163** (see [README](./README.md)). |

---

## Step 1 — Decide Hosted UI domain strategy

**Required:** Cognito needs a **domain** for OAuth (Hosted UI / authorize URLs).

| Option | Extra AWS services | When to use |
| ------ | ------------------- | ----------- |
| **A. Cognito prefix domain** | None beyond Cognito | Fastest: domain like `your-prefix.auth.us-east-1.amazoncognito.com`. |
| **B. Custom domain** (e.g. `auth.langfuse.example.com`) | **ACM certificate in `us-east-1`**, Route 53 (or DNS delegation), Cognito custom domain (CloudFront distribution behind the scenes per AWS) | Branding / corporate URL standards. |

**Optional footprint:** If you only need Cognito’s OAuth endpoints and can use the prefix domain, **do not** provision ACM/Route 53 for Cognito.

---

## Step 2 — Create or reuse a Cognito User Pool

**Required.**

1. Create a User Pool in **`us-east-1`** (or reuse MIDAS pool created by `deploy/ai_gateway/terraform/modules-midas/cognito.tf` module output `module.cognito.user_pool_id`).
2. Configure sign-in attributes so users have a stable **email** claim Langfuse can use (Langfuse identifies users by email for SSO; see [Authentication and SSO](https://langfuse.com/self-hosting/security/authentication-and-sso) troubleshooting).
3. Set policies as required by security (MFA, password policy, self-sign-up vs admin-only users).

**MIDAS note:** Existing Terraform already provisions a pool named via `cognito_upn` (e.g. `midas-aigtw-dev-user-pool`) and optional SAML IdP — SAML is **not** required for native Cognito OAuth with Langfuse.

---

## Step 3 — Enable Cognito domain

**Required.**

1. For prefix domain: create a **domain** on the pool (Cognito console or API).
2. For custom domain: follow [AWS: Add custom domain to user pool](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-add-custom-domain.html) — ACM must be in **`us-east-1`**. Custom domains require a valid DNS hierarchy (AWS documents parent-domain A record prerequisites).

---

## Step 4 — Create User Pool app client for Langfuse (OAuth code + secret)

**Required** for the Auth.js Cognito provider pattern Langfuse documents.

1. **Allowed OAuth flows:** Authorization code grant (Cognito: “Authorization code grant”).
2. **Generate client secret:** **Yes** (`generate_secret = true` in Terraform aligns with this).
3. **OAuth scopes:** Include at least **`openid`** and **`email`** (Langfuse/Auth.js expectations; pool must expose these scopes).
4. **Callback URL(s):** Exactly:

   `https://<LANGFUSE_HOST>/api/auth/callback/cognito`

   where `<LANGFUSE_HOST>` is the **same origin** users use in the browser for Langfuse (no trailing slash on the origin; path must match Langfuse docs).

5. **Sign-out URLs (optional but recommended):** Set to your Langfuse origin or a corporate logout landing page if you use centralized logout.

6. **Supported identity providers:** For “Cognito user directory only,” **`COGNITO`**. If you federate SAML/OIDC **into the same pool**, you may add those IdPs — Langfuse still talks OAuth to Cognito; Cognito handles federation.

**MIDAS drift to fix before go-live:** Terraform resource `aws_cognito_user_pool_client.langfuse_observability_client` currently registers  
`/api/auth/callback/custom` on hostname `exlerate-ai-observability-${environment}.exlservice.com`.  
That does **not** match Langfuse’s documented **`cognito`** callback or the current dev `NEXTAUTH_URL` host. Update Terraform or create a **new** client dedicated to Langfuse with the correct callback.

---

## Step 5 — Store client ID and secret for Langfuse

**Required.**

- MIDAS already mirrors client id/secret into Secrets Manager and Kubernetes (`langfuse-cognito-client-id`, `langfuse-cognito-client-secret`) via `deploy/ai_gateway/terraform/modules-midas/secrets.tf` and `langfuse_app_deps.tf` **when** the Terraform client matches reality.
- Helm must expose these as **`AUTH_COGNITO_CLIENT_ID`** and **`AUTH_COGNITO_CLIENT_SECRET`** (see playbook). Today’s `values-midas-dev.yaml` does **not** wire them into `additionalEnv`.

---

## Step 6 — Network and TLS validation

**Required.**

1. From a representative client browser on the corporate network, open `NEXTAUTH_URL` and confirm TLS.
2. From a Langfuse pod network path (or jump host), confirm HTTPS egress to `cognito-idp.us-east-1.amazonaws.com` (and Hosted UI hostnames if restricted).

---

## Step 7 — Deploy Langfuse configuration

**Required.**

1. Merge Helm `additionalEnv` (or chart-supported auth fields) for `AUTH_COGNITO_*` and correct `NEXTAUTH_URL` / `langfuse.nextauth.url`.
2. Run the MIDAS Jenkins Langfuse pipeline (`deploy/ai_gateway/jenkinsfiles/Jenkinsfile_ORD4_langfuse`) per [jenkins.mdc](../../.cursor/rules/jkenkins/jenkins.mdc) — no laptop `helm upgrade` to shared envs.

---

## Optional AWS additions (only if needed)

| Capability | Service | Justification |
| ---------- | ------- | ------------- |
| Custom Hosted UI domain | ACM + Route 53 + Cognito custom domain | Branding / URL policy only; **not** required for OAuth. |
| Secrets rotation | Secrets Manager rotation | Operational hardening; Cognito client secret rotation must stay in sync with Langfuse env. |
| WAF / Shield | WAF | Not required for Cognito integration correctness; organizational policy may mandate. |

---

## Contradictions / exceptions vs MIDAS “private-by-default”

- **Not a contradiction:** Langfuse remains on an **internal** load balancer.  
- **Expected public dependency:** User browsers load **Cognito Hosted UI** (public AWS). Langfuse **application** does not need a public ALB for Cognito SSO to function if users have internet access for IdP pages while using VPN for Langfuse, which is a common enterprise split.  
- **If** policy forbids any browser traffic to public endpoints, Cognito Hosted UI would be blocked — that is an organizational constraint outside “Cognito + Langfuse” mechanics; alternatives would be a different SSO architecture (not covered here).
