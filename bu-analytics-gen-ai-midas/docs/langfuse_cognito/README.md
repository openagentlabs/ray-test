# Langfuse + Amazon Cognito (MIDAS alignment)

This folder documents how to integrate **self-hosted Langfuse v3** with **Amazon Cognito** using Langfuse’s **first-party Cognito OAuth provider** (Auth.js / NextAuth “Cognito” provider), and how that relates to the **MIDAS AI Gateway** Terraform and Helm under `deploy/ai_gateway/`.

## Sources (reviewed)

| Source | Role |
| ------ | ---- |
| [Langfuse — Authentication and SSO (self-hosted)](https://langfuse.com/self-hosting/security/authentication-and-sso) | Official env vars, callback path, optional flags (**labeled Version: v3**). |
| [Langfuse — Environment variables](https://langfuse.com/self-hosting/configuration) | `NEXTAUTH_URL`, core secrets, v3 stack requirements. |
| [Langfuse — Deployment Guide (v2)](https://langfuse.com/self-hosting/v2/deployment-guide) | Historical reference only; MIDAS runs **v3**, not v2. |
| [NextAuth.js — Cognito provider](https://next-auth.js.org/providers/cognito) | Issuer URL shape and OAuth behavior. |
| [AWS — Add custom domain to Cognito](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-add-custom-domain.html) | When you choose a **custom** Hosted UI domain (optional); ACM **us-east-1** for Cognito custom domains. |
| [DEV — Cognito + self-hosted Langfuse (CDK)](https://dev.to/aws-builders/adding-cognito-authentication-to-self-hosted-langfuse-with-aws-cdk-4gfe) | Community pattern; HTTPS and callback URL reminders (cross-check with official Langfuse docs). |

## Version pinning (must match this repo)

These instructions apply to **Langfuse v3** as deployed by MIDAS, not Langfuse v2.

| Artifact | Location in repo | Pinned value (as of doc authoring) |
| -------- | ---------------- | ----------------------------------- |
| Langfuse **web/worker image tag** | `deploy/ai_gateway/jenkinsfiles/Jenkinsfile_ORD4_langfuse` (`IMAGE_TAG` default) and `deploy/ai_gateway/helm/langfuse/values-midas-dev.yaml` (`langfuse.web.image.tag`, `langfuse.worker.image.tag`) | **`3.163`** |
| Helm chart | `https://langfuse.github.io/langfuse-k8s` (`CHART_REPO` in `Jenkinsfile_ORD4_langfuse`) | Floating chart version from repo; app behavior tied to **image `3.163`** |

**Doc maintenance rule:** When MIDAS bumps the Langfuse image tag, re-open [Langfuse v3 Authentication and SSO](https://langfuse.com/self-hosting/security/authentication-and-sso) for any breaking auth changes. Do not assume v2 guides apply.

## Repository findings (Cognito ↔ Langfuse)

1. **Official Langfuse Cognito integration** uses:
   - `AUTH_COGNITO_CLIENT_ID`, `AUTH_COGNITO_CLIENT_SECRET`, `AUTH_COGNITO_ISSUER`
   - Redirect/callback: **`/api/auth/callback/cognito`**  
   See [Authentication and SSO](https://langfuse.com/self-hosting/security/authentication-and-sso).

2. **MIDAS Helm overlay** (`deploy/ai_gateway/helm/langfuse/values-midas-dev.yaml`) currently **does not** set any `AUTH_COGNITO_*` variables and keeps local email/password enabled (`AUTH_DISABLE_USERNAME_PASSWORD=false`). Comments in that file mention restoring **`AUTH_CUSTOM_*`** blocks; that is a **different** integration path (`/api/auth/callback/custom`). For native Cognito, use **`AUTH_COGNITO_*`**, not `AUTH_CUSTOM_*`, unless you intentionally configure a generic OIDC provider.

3. **MIDAS Terraform** (`deploy/ai_gateway/terraform/modules-midas/cognito.tf`) defines `aws_cognito_user_pool_client.langfuse_observability_client` with callback  
   `https://exlerate-ai-observability-${environment}.exlservice.com/api/auth/callback/custom`.  
   That path matches **`AUTH_CUSTOM_*`**, **not** the official **`cognito`** callback. It also uses a **different hostname** than the dev Helm overlay’s `langfuse.nextauth.url` (`https://exldecision-ai-dev-aigw-langfuse.exlservice.com`). **Enabling SSO requires aligning** Cognito app client callback/sign-out URLs with the **actual** public Langfuse URL and the **`cognito`** callback path if using `AUTH_COGNITO_*`.

4. **Enterprise Edition:** Langfuse **SSO via OAuth/OIDC (including Cognito) does not depend on an EE license** per the official v3 Authentication and SSO page. EE gates separate features (RBAC, SCIM, etc.). Do not treat EE as a blocker for Cognito OAuth.

## MIDAS architecture notes

- **Private VPC:** Langfuse is exposed via an **internal** ALB (`alb.ingress.kubernetes.io/scheme: internal` in the Helm overlay). Users reach it from corporate networks/VPN, not from the public Internet.
- **Cognito:** The Hosted UI and Cognito OAuth/OIDC endpoints are **AWS public endpoints**. Browsers and Langfuse pods still call `https://cognito-idp.us-east-1.amazonaws.com/...` (and related URLs). That is normal and **not** the same as exposing Langfuse itself publicly.
- **HTTPS:** Callback URLs for production Cognito app clients must use **https** (community guide also notes this). Internal ALB termination with a corporate TLS cert satisfies this **provided** the hostname in `NEXTAUTH_URL` matches what users use.

## Deliverables in this folder

| File | Contents |
| ---- | -------- |
| [01-deployment-plan.md](./01-deployment-plan.md) | Ordered AWS-focused deployment steps (Cognito-first footprint). |
| [02-configuration-playbook.md](./02-configuration-playbook.md) | Cognito + Langfuse settings, env vars, URLs, secrets. |
| [03-end-to-end-flow.md](./03-end-to-end-flow.md) | Narrative + verification from zero to signed-in user. |
| [04-implementation-status-and-gaps.md](./04-implementation-status-and-gaps.md) | Code vs manual: Terraform/Helm/Jenkins inventory, Cognito↔Langfuse gaps, AWS CLI verification checklist, deployment plan. |
| [05-corporate-idp-handoff.md](./05-corporate-idp-handoff.md) | Corporate IdP hand-off card: live AWS values, SAML SP config, DNS records, networking, and activation checklist. |
| [06-s3-litellm-tracing-troubleshooting.md](./06-s3-litellm-tracing-troubleshooting.md) | **Tracing troubleshooting runbook:** the three bugs that blocked Langfuse ingestion (wrong S3 bucket names, wrong IAM policy resources, unpopulated Secrets Manager keys), root causes, fixes, diagnostic commands, and deployment order. |
