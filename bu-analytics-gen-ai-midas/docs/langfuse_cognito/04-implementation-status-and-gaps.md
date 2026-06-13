# Langfuse + Cognito — implementation status and gaps

This document inventories **what MIDAS has in repository code** versus **what still needs alignment** for Amazon Cognito SSO with self-hosted Langfuse v3. It complements [README](./README.md), [01-deployment-plan](./01-deployment-plan.md), [02-configuration-playbook](./02-configuration-playbook.md), and [03-end-to-end-flow](./03-end-to-end-flow.md).

**Scope:** MIDAS-owned paths (`deploy/ai_gateway/**`) and read-only reference to the **`ai_gateway/` submodule** (upstream AI Gateway). Per [`.cursor/rules/ai_gateway.mdc`](../../.cursor/rules/ai_gateway.mdc), production changes to submodule files happen upstream; MIDAS expresses overrides under `deploy/ai_gateway/`.

---

## 1. Executive summary

| Area | In code today? | Fit for Cognito + Langfuse v3? |
| --- | --- | --- |
| Cognito User Pool + domain + SAML hook | Yes (`deploy/ai_gateway/terraform/modules-midas/cognito.tf`) | Pool/domain present; SAML IdP gated behind `enable_saml_identity_provider` + secret metadata |
| App clients for Langfuse | Yes — multiple clients including `langfuse_observability_client`, `exlerate_langfuse_server` | Callback URLs use **`exlerate-ai-observability-${environment}`** and path **`/api/auth/callback/custom`** |
| Secrets Manager → Kubernetes (`langfuse-cognito-client-id`, `langfuse-cognito-client-secret`) | Yes — populated from `langfuse_observability_client` | Values track Terraform client; **only useful if Helm uses them with matching OAuth path** |
| Helm env for SSO (`AUTH_COGNITO_*` or `AUTH_CUSTOM_*`) | **No in MIDAS dev overlay** | Dev overlay **disables** SSO and uses local username/password |
| Upstream submodule Helm (`ai_gateway/helm/langfuse/values.yaml`) | Yes — **`AUTH_CUSTOM_*`** wired to same K8s secrets | Uses **custom OIDC** pattern + hardcoded issuer pool id; **not** `AUTH_COGNITO_*` |
| Public URL / TLS / ALB | Yes — ACM + `langfuse-alb-config` ConfigMap, ORD4 Jenkins | Cert hostname **`exldecision-ai-dev-aigw-langfuse.exlservice.com`** — **does not match** Cognito callback hostname in Terraform |

**Bottom line:** Infrastructure provisions Cognito and pushes client credentials into the cluster, but **MIDAS Langfuse intentionally runs without SSO in dev**, and **Terraform OAuth callbacks + issuer story do not line up** with the live Langfuse hostname and with Langfuse’s native **`AUTH_COGNITO_*`** path unless the team deliberately continues the **`AUTH_CUSTOM_*` + `/callback/custom`** design from upstream.

---

## 2. How deployment is intended to work (two layers)

### 2.1 MIDAS AI Gateway pipelines (`deploy/ai_gateway/`)

Canonical flow ([`deploy/ai_gateway/README.md`](../../deploy/ai_gateway/README.md)):

1. **ORD1** — Terraform (`deploy/ai_gateway/terraform/`) creates EKS-related AWS resources: Cognito, RDS/Redis/S3 for Langfuse, ACM for Langfuse hostname, IRSA, Kubernetes secrets (including Cognito client id/secret), `langfuse-alb-config` ConfigMap.
2. **ORD2** — Images to ECR.
3. **ORD3** — ClickHouse Helm.
4. **ORD4** — Langfuse Helm via [`Jenkinsfile_ORD4_langfuse`](../../deploy/ai_gateway/jenkinsfiles/Jenkinsfile_ORD4_langfuse): reads **`deploy/ai_gateway/helm/langfuse/values-midas-<env>.yaml`**, merges runtime ALB annotations from `langfuse-alb-config`.

No laptop `helm upgrade` to shared environments ([`.cursor/rules/jkenkins/jenkins.mdc`](../../.cursor/rules/jkenkins/jenkins.mdc)).

### 2.2 Upstream AI Gateway submodule (`ai_gateway/`)

- Terraform under `ai_gateway/infra/terraform/` and Jenkins `ai_gateway/deploy/Jenkins_langfusedeploy` describe the **upstream** deployment story; MIDAS does **not** run those paths directly for shared envs — MIDAS runs **`deploy/ai_gateway`** pipelines instead.
- Reference Helm: [`ai_gateway/helm/langfuse/values.yaml`](../../ai_gateway/helm/langfuse/values.yaml) documents **Custom OIDC via Cognito** using **`AUTH_CUSTOM_*`** (issuer hardcoded to a specific pool id in the file), **not** the official **`AUTH_COGNITO_*`** variables from [Langfuse Authentication and SSO (v3)](https://langfuse.com/self-hosting/security/authentication-and-sso).

---

## 3. What is implemented in MIDAS Terraform (Cognito + secrets)

**File:** [`deploy/ai_gateway/terraform/modules-midas/cognito.tf`](../../deploy/ai_gateway/terraform/modules-midas/cognito.tf)

| Resource | Purpose |
| --- | --- |
| `module "cognito"` | UC IaC module: user pool, **`domain_enable = true`**, optional SAML IdP (`EXLerateAI`) when `enable_saml_identity_provider` is true |
| `aws_cognito_user_pool_client.exlerate_ai_gateway_client` | AI Gateway UI — callback `https://${var.cognito_domain}-${var.environment}.exlservice.com/callback` |
| `aws_cognito_user_pool_client.langfuse_observability_client` | Langfuse — **`callback_urls`**: `https://exlerate-ai-observability-${var.environment}.exlservice.com/api/auth/callback/custom` |
| `aws_cognito_user_pool_client.exlerate_langfuse_public_client` | Different callback shape (origin-only URL) |
| `aws_cognito_user_pool_client.exlerate_langfuse_server` | Same **`/api/auth/callback/custom`** pattern as `langfuse_observability_client` |

**Secrets wiring:** [`deploy/ai_gateway/terraform/modules-midas/secrets.tf`](../../deploy/ai_gateway/terraform/modules-midas/secrets.tf) creates Secrets Manager entries and initial versions from **`aws_cognito_user_pool_client.langfuse_observability_client`** (`id` and `client_secret`). [`langfuse_app_deps.tf`](../../deploy/ai_gateway/terraform/modules-midas/langfuse_app_deps.tf) mirrors those into Kubernetes secrets named **`langfuse-cognito-client-id`** and **`langfuse-cognito-client-secret`** (via `module "langfuse_helm_chart_secrets"` / `k_secrets`), with secret **data keys** equal to the secret names (same pattern as upstream Helm expects).

**Langfuse TLS:** [`deploy/ai_gateway/terraform/modules-midas/acm.tf`](../../deploy/ai_gateway/terraform/modules-midas/acm.tf) — ACM certificate **`exldecision-ai-dev-aigw-langfuse.exlservice.com`** for the ALB that serves Langfuse.

**Implication:** Terraform encodes OAuth redirects for **`exlerate-ai-observability-*.exlservice.com`**, while ACM and [`langfuse.nextauth.url`](../../deploy/ai_gateway/helm/langfuse/values-midas-dev.yaml) target **`exldecision-ai-dev-aigw-langfuse.exlservice.com`**. That is a **hostname mismatch** unless DNS/aliases unify those hosts or Cognito clients were updated outside Terraform.

---

## 4. What MIDAS Helm actually configures (Langfuse auth)

**File:** [`deploy/ai_gateway/helm/langfuse/values-midas-dev.yaml`](../../deploy/ai_gateway/helm/langfuse/values-midas-dev.yaml)

| Setting | Value / behavior |
| --- | --- |
| `langfuse.nextauth.url` | `https://exldecision-ai-dev-aigw-langfuse.exlservice.com` |
| `langfuse.ingress.hosts[0].host` | `exldecision-ai-dev-lf.exlservice.com` (may imply multi-host or migration; **must match** user-facing URL + ACM SANs for TLS) |
| Cognito / OIDC env | **Not set** — explicit posture: **no SSO**; **`AUTH_DISABLE_USERNAME_PASSWORD: "false"`** |
| Comment rationale | Cites missing SAML metadata and **EE license** as reasons — **Langfuse v3 Cognito OAuth does not require an EE license** for basic SSO ([official doc](https://langfuse.com/self-hosting/security/authentication-and-sso)); EE gates other enterprise features. |

So: **K8s secrets for Cognito client exist**, but **Helm does not mount `AUTH_COGNITO_*` or `AUTH_CUSTOM_*`** in the MIDAS dev overlay.

---

## 5. Upstream submodule Helm (reference only)

[`ai_gateway/helm/langfuse/values.yaml`](../../ai_gateway/helm/langfuse/values.yaml):

- Sets **`AUTH_CUSTOM_CLIENT_ID`**, **`AUTH_CUSTOM_CLIENT_SECRET`**, **`AUTH_CUSTOM_ISSUER`**, **`AUTH_CUSTOM_NAME`**, **`AUTH_CUSTOM_ALLOW_ACCOUNT_LINKING`** — i.e. **generic OIDC** to Cognito, callback **`/api/auth/callback/custom`** (per Langfuse docs).
- Issuer in repo: `https://cognito-idp.us-east-1.amazonaws.com/us-east-1_u5hcfpBrh` — **must match** the actual MIDAS user pool id from Terraform output, not this literal, when used.
- Sticky sessions on ALB documented for OAuth — MIDAS dev overlay includes stickiness annotations.

MIDAS [`UPSTREAM_BLOCKERS.md`](../../deploy/ai_gateway/UPSTREAM_BLOCKERS.md) notes several overrides; line about overlay sourcing Cognito from a **`midas-aigtw-dev-langfuse-cognito`** Secret may be **stale** relative to current `values-midas-dev.yaml` (which removes SSO env).

---

## 6. Gap analysis (ordered by severity)

### 6.1 SSO not enabled in running configuration

- **Gap:** ORD4 deploys **`values-midas-dev.yaml`**, which **omits** all Cognito-related Langfuse env vars.
- **Evidence:** No `AUTH_COGNITO_*` or `AUTH_CUSTOM_*` entries under `langfuse.additionalEnv`.
- **Effect:** Users use **local email/password** against Langfuse’s DB (`AUTH_DISABLE_USERNAME_PASSWORD=false`).

### 6.2 OAuth callback hostname drift (Terraform vs runtime URL)

- **Gap:** Cognito app clients in Terraform register **`https://exlerate-ai-observability-<env>.exlservice.com/...`** while **`NEXTAUTH_URL`** / ACM target **`exldecision-ai-dev-aigw-langfuse.exlservice.com`**.
- **Effect:** Even if SSO env vars were added, **Cognito would reject redirects** unless callback URLs in AWS match the browser origin exactly (`redirect_mismatch`).

### 6.3 Integration style: `/callback/custom` vs `/callback/cognito`

- **Terraform** uses **`/api/auth/callback/custom`** — aligns with **`AUTH_CUSTOM_*`** (upstream submodule approach).
- Playbooks in this folder recommend **`AUTH_COGNITO_*`** and **`/api/auth/callback/cognito`** for native Cognito ([02-configuration-playbook](./02-configuration-playbook.md)).
- **Decision needed:** Either (a) update Terraform callbacks to **`.../cognito`** and Helm to **`AUTH_COGNITO_*`**, or (b) keep **`.../custom`** and Helm **`AUTH_CUSTOM_*`** with issuer/client aligned — **do not mix** path and variable families.

### 6.4 Ingress host vs nextauth URL

- **Gap:** Ingress lists **`exldecision-ai-dev-lf.exlservice.com`** while **`langfuse.nextauth.url`** uses **`exldecision-ai-dev-aigw-langfuse.exlservice.com`**.
- **Effect:** Risk of **wrong canonical URL** for cookies/callbacks unless one hostname is legacy and DNS/user traffic exclusively uses the other. Confirm with operations which hostname is authoritative.

### 6.5 SAML IdP enablement (optional)

- **`enable_saml_identity_provider`** + `cognito-sso-credentials` secret (`PopulateMe` placeholder) — enabling SAML without real metadata **fails apply** (documented in `cognito.tf`). Not required for native Cognito-only login.

### 6.6 Documentation vs overlay comment on EE

- **Gap:** `values-midas-dev.yaml` implies SSO requires EE; **official Langfuse v3 doc** states Cognito OAuth/SSO path does not depend on EE for basic auth. Treat EE as unrelated to **whether** Cognito OAuth can be turned on; EE still matters for **other** Langfuse Enterprise features.

---

## 7. Likely manual vs automated (best-effort)

| Item | Likely automated (in repo) | Likely manual / external |
| --- | --- | --- |
| User pool, domain, app clients | Terraform `cognito.tf` | Console edits **if** someone changed callbacks without updating TF |
| Secrets Manager + K8s mirror | Terraform `secrets.tf` + `langfuse_app_deps.tf` | Manual `put-secret-value` only if `lifecycle { ignore_changes }` required ops rotation outside TF |
| ACM DNS validation | Terraform creates cert; validation records | Corporate DNS team / Route 53 ownership |
| Langfuse SSO behavior | **Not** enabled by Helm overlay | Future Helm + Cognito console alignment |
| SAML federation | Terraform supports it | Entra metadata population (`PopulateMe` → real XML) |

---

## 8. Suggested remediation sequence (no implementation here)

1. **Pick one canonical public hostname** for Langfuse (must match **ACM**, **Ingress**, **`NEXTAUTH_URL`**, and **Cognito callback origin**).
2. **Choose integration:** **`AUTH_COGNITO_*` + `/api/auth/callback/cognito`** (playbook default) **or** **`AUTH_CUSTOM_*` + `/api/auth/callback/custom`** (upstream-style); update **Terraform `callback_urls`** accordingly.
3. **Extend `values-midas-dev.yaml`** `additionalEnv` with the chosen variable set and `secretKeyRef` to existing **`langfuse-cognito-client-id`** / **`langfuse-cognito-client-secret`**; set **`AUTH_COGNITO_ISSUER`** or **`AUTH_CUSTOM_ISSUER`** to `https://cognito-idp.us-east-1.amazonaws.com/<actual_pool_id>`.
4. **Redeploy ORD4** after ORD1 applies Cognito/secret changes.
5. **Optional:** `AUTH_DISABLE_USERNAME_PASSWORD=true` only after successful SSO tests ([03-end-to-end-flow](./03-end-to-end-flow.md)).

---

## 9. Quick reference — key files

| Concern | Location |
| --- | --- |
| Cognito resources | `deploy/ai_gateway/terraform/modules-midas/cognito.tf` |
| Langfuse Cognito secrets → SM → K8s | `deploy/ai_gateway/terraform/modules-midas/secrets.tf`, `langfuse_app_deps.tf` |
| Langfuse ACM / ALB CM | `acm.tf`, `langfuse_app_deps.tf` (`langfuse-alb-config`) |
| MIDAS Helm (effective dev deploy) | `deploy/ai_gateway/helm/langfuse/values-midas-dev.yaml` |
| Langfuse Jenkins | `deploy/ai_gateway/jenkinsfiles/Jenkinsfile_ORD4_langfuse` |
| Upstream Helm reference | `ai_gateway/helm/langfuse/values.yaml` (read-only submodule) |

---

## 10. AI Gateway vs other MIDAS Cognito (do not conflate)

The **AI Gateway / Langfuse** stack uses Cognito resources created by **`deploy/ai_gateway/terraform`** (ORD1), **not** the Cognito settings under `deploy/ecs-app/` or other MIDAS frontends.

| Aspect | AI Gateway (this investigation) | Typical MIDAS app (example) |
| --- | --- | --- |
| Terraform entrypoint | `deploy/ai_gateway/terraform/environment/dev/terragrunt.hcl` | `deploy/ecs-app/` pipelines |
| Expected user pool **name** (dev) | **`midas-aigtw-dev-user-pool`** (`cognito_upn`) | Different pool / client IDs per product |
| Expected Cognito **hosted UI domain prefix** | **`midas-aigtw-dev-dev`** (`${cognito_domain}-${environment}` → `midas-aigtw-dev` + `-` + `dev`) | N/A |
| EKS cluster tag | **`midas-eks-aigtw-dev`** | e.g. `midas-eks-dev` |
| Secrets Manager prefix examples | `langfuse-cognito-client-id-midas-eks-aigtw-dev`, `cognito-sso-credentials-midas-eks-aigtw-dev` | Different secret names |

If console browsing shows a pool named for **exlerate-ai**, **sb-bti**, or **frontend Vite** variables only, that is **not** the AI Gateway pool unless DNS/OAuth callbacks were incorrectly pointed there.

---

## 11. AWS account verification (CLI) — live state

**Credentials:** `AWS_PROFILE=midas-dev` after `aws sso login --profile midas-dev` (account **811391286931**, **`us-east-1`**). A **verified snapshot** from CLI is in **§11.7** (2026-05-01); re-run the commands below after infra changes.

### 11.1 Identity

```bash
export AWS_PROFILE=midas-dev AWS_REGION=us-east-1
aws sso login --profile midas-dev
aws sts get-caller-identity
```

### 11.2 Resolve the AI Gateway user pool

```bash
# Find pool id by name (expected name from Terragrunt: midas-aigtw-dev-user-pool)
aws cognito-idp list-user-pools --max-results 50 --region us-east-1 \
  --query 'UserPools[?Name==`midas-aigtw-dev-user-pool`].[Id,Name,CreationDate]' --output table

POOL_ID=<paste Id from above>
```

### 11.3 Domain (OAuth / Hosted UI prefix)

```bash
aws cognito-idp describe-user-pool-domain --domain midas-aigtw-dev-dev --region us-east-1
# If NotFoundException: domain prefix may differ if inputs changed — list domains from console or search pool details.
```

### 11.4 App clients (Langfuse-related names from Terraform)

Expect clients named similarly to:

- `langfuse-observability-dev`
- `exlerate-dev-langfuse-public-client`
- `exlerate-dev-langfuse-server`
- `EXLERATE-AI-GATEWAY-dev-CLIENT` (AI Gateway UI)

```bash
aws cognito-idp list-user-pool-clients --user-pool-id "$POOL_ID" --max-results 60 --region us-east-1 \
  --query 'UserPoolClients[*].[ClientName,ClientId]' --output table
```

For each Langfuse-relevant client:

```bash
aws cognito-idp describe-user-pool-client --user-pool-id "$POOL_ID" --client-id <CLIENT_ID> --region us-east-1 \
  --query 'UserPoolClient.{Name:ClientName,Callbacks:CallbackURLs,LogoutURLs:LogoutURLs,Scopes:AllowedOAuthScopes,Providers:SupportedIdentityProviders}' --output json
```

**Acceptance checks vs [02-configuration-playbook](./02-configuration-playbook.md):**

- Callback URL must equal **`https://<canonical-langfuse-host>/api/auth/callback/cognito`** if using **`AUTH_COGNITO_*`**, or **`.../callback/custom`** if using **`AUTH_CUSTOM_*`** — **must match Helm**, not a stale hostname.
- Issuer for env vars is **`https://cognito-idp.us-east-1.amazonaws.com/$POOL_ID`** (replace `POOL_ID`).

### 11.5 Secrets Manager (Langfuse ↔ Cognito credentials)

```bash
aws secretsmanager list-secrets --region us-east-1 \
  --query 'SecretList[?contains(Name, `langfuse-cognito`) || contains(Name, `cognito-sso-credentials`)].[Name]' --output table
```

Expected names (from Terraform):

- `langfuse-cognito-client-id-midas-eks-aigtw-dev`
- `langfuse-cognito-client-secret-midas-eks-aigtw-dev`
- `cognito-sso-credentials-midas-eks-aigtw-dev` (SAML metadata for optional Entra IdP — not required for native Cognito OAuth)

Do **not** print secret values in tickets; confirm **existence** and **last-changed** metadata only.

### 11.6 Optional: compare to Terraform state

If ORD1 state is healthy:

```bash
cd deploy/ai_gateway/terraform/environment/dev
terragrunt output   # if outputs expose pool id / client ids
```

### 11.7 Live verification snapshot (2026-05-01)

Run from repo automation after `aws sso login --profile midas-dev`; **`sts get-caller-identity`** confirmed account **`811391286931`**.

| Check | Result |
| --- | --- |
| User pool **`midas-aigtw-dev-user-pool`** | **Present** · id **`us-east-1_24fpml9So`** · MFA **OPTIONAL** · **~0** estimated users |
| Hosted UI domain prefix **`midas-aigtw-dev-dev`** | **ACTIVE** (matches Terraform `${cognito_domain}-${environment}`) |
| SAML / federated IdPs on pool | **None** (`list-identity-providers` empty — aligns with **`enable_saml_identity_provider`** off) |
| Secrets Manager | **`langfuse-cognito-client-id-midas-eks-aigtw-dev`**, **`langfuse-cognito-client-secret-midas-eks-aigtw-dev`**, **`cognito-sso-credentials-midas-eks-aigtw-dev`** — **all present** (metadata only; do not commit secret values) |
| Issuer for Langfuse env | **`https://cognito-idp.us-east-1.amazonaws.com/us-east-1_24fpml9So`** |

**App clients (OAuth callbacks)** — Langfuse-related rows confirm **hostname drift** vs Helm **`NEXTAUTH_URL`** (**`https://exldecision-ai-dev-aigw-langfuse.exlservice.com`**):

| Client name | Callback URL(s) (live) | Supported IdPs |
| --- | --- | --- |
| **`langfuse-observability-dev`** | **`https://exlerate-ai-observability-dev.exlservice.com/api/auth/callback/custom`** | `COGNITO` |
| **`exlerate-dev-langfuse-server`** | **`https://exlerate-ai-observability-dev.exlservice.com/api/auth/callback/custom`** | `COGNITO` |
| **`exlerate-dev-langfuse-public-client`** | **`https://exlerate-ai-observability-dev.exlservice.com`** (origin only) | `COGNITO` |
| **`EXLERATE-AI-GATEWAY-dev-CLIENT`** | **`https://midas-aigtw-dev-dev.exlservice.com/callback`** | `COGNITO` |

**Interpretation:** AI Gateway–**dedicated** Cognito is **fully deployed** (pool, domain, Langfuse-bound clients, secrets). Langfuse **SSO is still blocked** by (a) Helm not mounting **`AUTH_COGNITO_*` / `AUTH_CUSTOM_*`**, and (b) callbacks pointing at **`exlerate-ai-observability-dev`** instead of the **live Langfuse host** + chosen **`/cognito`** or **`/custom`** path. No evidence of console drift away from Terraform on those callback URLs.

### 11.8 Isolation — `midas-aigtw-dev-user-pool` vs MIDAS frontend / backend

Goal: confirm **`midas-aigtw-dev-user-pool`** (**`us-east-1_24fpml9So`**) is **not** the pool behind the main MIDAS SPA / ECS backend, and is **not** referenced accidentally from non–AI Gateway code paths.

**Repository checks**

| Area | Finding |
| --- | --- |
| ECS **frontend** Cognito (`deploy/ecs-app/tfvars/dev.tfvars`) | Hosted UI **`https://exldecision-ai.auth.us-east-1.amazoncognito.com`** · client **`1j436t8d6g8ggklvtcti73s141`** · comment documents pool **`us-east-1_5JL0dpXwK`** (**`ins-midas-dev-user-pool`**) — **not** `midas-aigtw-dev-user-pool`. |
| Hard-coded AI Gateway pool id (`24fpml9So`) / AI Gateway client ids | **No matches** in `deploy/ecs-app/`, `frontend/`, or `backend/` (grep). |
| AI Gateway **Control API** Helm ([`values-midas-dev.yaml`](../../deploy/ai_gateway/helm/control-api/values-midas-dev.yaml)) | **`cognitoUserPoolId: ""`** · **`cognitoAppClientId: ""`** (OSS-mode; no Cognito wiring). |
| Backend Cognito settings ([`backend/app/core/config.py`](../../backend/app/core/config.py)) | **`COGNITO_USER_POOL_ID`** comes from **environment** only — no default tied to AI Gateway; runtime must match whichever pool operators configure for the **main** MIDAS app (documented dev convention in tfvars comment → **ins** pool). |

**AWS CLI checks** (`AWS_PROFILE=midas-dev`, `us-east-1`)

1. **Hosted UI domain** (prefix differs per pool):

   | Pool | `describe-user-pool` → `Domain` |
   | --- | --- |
   | **`ins-midas-dev-user-pool`** (`us-east-1_5JL0dpXwK`) | **`exldecision-ai`** → URLs like **`https://exldecision-ai.auth.us-east-1.amazoncognito.com`** |
   | **`midas-aigtw-dev-user-pool`** (`us-east-1_24fpml9So`) | **`midas-aigtw-dev-dev`** → **`https://midas-aigtw-dev-dev.auth.us-east-1.amazoncognito.com`** |

   The SPA **Vite** domain in tfvars matches **`exldecision-ai`**, not **`midas-aigtw-dev-dev`**.

2. **SPA app client membership:** `list-user-pool-clients` filtered for **`1j436t8d6g8ggklvtcti73s141`**:

   - **Present** on **`us-east-1_5JL0dpXwK`** (client name **`Exldecisionai-Dev`**).
   - **Absent** from **`us-east-1_24fpml9So`** (AI Gateway pool).

**Conclusion:** There is **no evidence** that the main MIDAS **frontend** OAuth client is registered on **`midas-aigtw-dev-user-pool`**. Pools are **separate** (different ids, different Cognito domain prefixes). **Backend** usage cannot be proven solely from git (values often injected at deploy); operators should ensure **`COGNITO_USER_POOL_ID`** for ECS/backend tasks remains **`us-east-1_5JL0dpXwK`** (or your prod analogue), **not** **`us-east-1_24fpml9So`**, when validating task definitions / Secrets Manager in AWS Console.

**Repeat CLI (SPA client check):**

```bash
export AWS_PROFILE=midas-dev AWS_REGION=us-east-1
FE_CLIENT_ID="<from deploy/ecs-app/tfvars/dev.tfvars frontend_vite_cognito_client_id>"
for POOL in us-east-1_24fpml9So us-east-1_5JL0dpXwK; do
  aws cognito-idp list-user-pool-clients --user-pool-id "$POOL" --max-results 60 \
    --query "UserPoolClients[?ClientId==\`$FE_CLIENT_ID\`]" --output json
done
# Expect a match only on us-east-1_5JL0dpXwK
```

---

## 12. Updated gaps (after CLI checklist intent)

The following augments sections 6–8 with **runtime verification** expectations.

| Gap ID | Repo evidence | What live AWS should show (after SSO CLI) |
| --- | --- | --- |
| G-AIGTW-1 | Helm overlay has no `AUTH_*` Cognito vars | Langfuse works with **local** login only; no reliance on pool OAuth until Helm fixed |
| G-AIGTW-2 | Terraform callbacks use **`exlerate-ai-observability-dev`** host | Describe-user-pool-client shows those URLs **unless** someone patched clients in console |
| G-AIGTW-3 | ACM + nextauth use **`exldecision-ai-dev-aigw-langfuse`** | If callbacks still mention **exlerate-ai-observability**, **redirect_mismatch** when enabling SSO |
| G-AIGTW-4 | Two integration families (`cognito` vs `custom` path) | Client callback path must match chosen **`AUTH_COGNITO_*`** vs **`AUTH_CUSTOM_*`** |

If CLI shows pool **`midas-aigtw-dev-user-pool`** **missing**, ORD1 never succeeded or wrong account/region — resolve before Langfuse SSO work.

**2026-05-01 CLI outcome:** Pool **present**; secrets **present**; callbacks **match Terraform** (**exlerate-ai-observability-dev** + **`/custom`**); **G-AIGTW-1** (no Helm SSO env) and **G-AIGTW-3** (hostname mismatch vs **`exldecision-ai-dev-aigw-langfuse`**) **remain open**.

---

## 13. Deployment and configuration plan (AI Gateway Cognito + Langfuse)

Ordered steps for the team; aligns with [01-deployment-plan](./01-deployment-plan.md) and CLI checks in §11.

| Step | Action | Owner / pipeline |
| --- | --- | --- |
| 1 | **Authenticate** and run §11 CLI checklist; record **`POOL_ID`**, **`langfuse_observability_client`** (or replacement) **callback URLs**, and confirm pool **`midas-aigtw-dev-user-pool`** exists. | Operator |
| 2 | **Choose canonical browser hostname** for Langfuse (`NEXTAUTH_URL`); align **ACM**, **Ingress `rules[].host`**, and **Cognito callback/sign-out URLs** to that host only. Update **`deploy/ai_gateway/terraform/modules-midas/cognito.tf`** `callback_urls` / `logout_urls` if Terraform should own truth; apply via **ORD1** (not laptop apply to shared env per [jenkins.mdc](../../.cursor/rules/jkenkins/jenkins.mdc)). | Platform + PR |
| 3 | **Pick integration style:** **`AUTH_COGNITO_*`** + `/api/auth/callback/**cognito**` **or** **`AUTH_CUSTOM_*`** + `/api/auth/callback/**custom**`; update Terraform clients + **`deploy/ai_gateway/helm/langfuse/values-midas-dev.yaml`** `additionalEnv` consistently ([02-configuration-playbook](./02-configuration-playbook.md)). | Platform + PR |
| 4 | Set **`AUTH_*_ISSUER`** to **`https://cognito-idp.us-east-1.amazonaws.com/<POOL_ID>`** (pool id from CLI or console — **not** the placeholder id from upstream submodule `values.yaml`). | PR |
| 5 | Confirm Secrets Manager entries **`langfuse-cognito-client-*-midas-eks-aigtw-dev`** exist and ORD1 Kubernetes secrets in namespace **`langfuse`** are present (jumpbox kubectl per [debug.mdc](../../.cursor/rules/debuging/debug.mdc) if needed). | Operator |
| 6 | Run **ORD4** Langfuse deploy after merge; verify OAuth round-trip in incognito ([03-end-to-end-flow](./03-end-to-end-flow.md)). | Jenkins |
| 7 | Optionally **`AUTH_DISABLE_USERNAME_PASSWORD=true`** after SSO validated; optionally SAML **`EXLerateAI`** only if Entra federation is required — separate from Langfuse OIDC mechanics. | Policy-driven |

**Non-goals for this track:** Replacing the AI Gateway pool with the ECS/MIDAS main app pool — keep **dedicated** AI Gateway Cognito for blast-radius and callback hygiene unless architecture explicitly merges IdPs.

---

*Repository inspection: MIDAS `deploy/ai_gateway` + `ai_gateway` submodule. **Live AWS:** snapshot §11.7 verified **2026-05-01** (`midas-dev` SSO profile). Re-run §11 after Cognito or Helm hostname changes.*

**CLI snapshot (filled 2026-05-01):** pool id **`us-east-1_24fpml9So`** · callbacks match canonical Langfuse host (**exldecision-ai-dev-aigw-langfuse**): **No** · SSO env in Helm (**AUTH_COGNITO_*** / **AUTH_CUSTOM_***): **No**
