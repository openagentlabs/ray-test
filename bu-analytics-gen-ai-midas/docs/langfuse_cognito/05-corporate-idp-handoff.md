# Corporate IdP hand-off — AI Gateway Cognito + Langfuse (dev)

All values on this page are **live** (verified 2026-05-01 via `AWS_PROFILE=midas-dev`). Share this document with the corporate DNS and IdP teams.

---

## 1. What MIDAS gives to the corporate IdP team

### 1.1 AWS identity and Cognito details


| Item                                        | Value                                                                                   |
| ------------------------------------------- | --------------------------------------------------------------------------------------- |
| AWS Account ID                              | `**811391286931`**                                                                      |
| Region                                      | `**us-east-1**`                                                                         |
| Cognito User Pool name                      | `**midas-aigtw-dev-user-pool**`                                                         |
| Cognito User Pool ID                        | `**us-east-1_24fpml9So**`                                                               |
| Cognito Hosted UI domain                    | `**midas-aigtw-dev-dev.auth.us-east-1.amazoncognito.com**`                              |
| OIDC Issuer (Langfuse `AUTH_CUSTOM_ISSUER`) | `https://cognito-idp.us-east-1.amazonaws.com/us-east-1_24fpml9So`                       |
| JWKS URL                                    | `https://cognito-idp.us-east-1.amazonaws.com/us-east-1_24fpml9So/.well-known/jwks.json` |


### 1.2 SAML Service Provider (SP) values — for Entra App Registration

The corporate IdP team configures an **Entra Enterprise Application** (SAML) using these values:


| SP field                                     | Value                                                                            |
| -------------------------------------------- | -------------------------------------------------------------------------------- |
| **SAML ACS URL** (Reply URL / Recipient URL) | `https://midas-aigtw-dev-dev.auth.us-east-1.amazoncognito.com/saml2/idpresponse` |
| **SAML Entity ID** (Identifier / Audience)   | `urn:amazon:cognito:sp:us-east-1_24fpml9So`                                      |
| Name ID format                               | `emailAddress`                                                                   |
| Name ID claim                                | `user.mail` (UPN)                                                                |


**Required SAML attribute mappings** (claim → Cognito attribute):


| Entra claim URI                                                        | Cognito attribute  |
| ---------------------------------------------------------------------- | ------------------ |
| `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress`   | `email`            |
| `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/displayname`    | `name`             |
| `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier` | `username`         |
| `http://schemas.microsoft.com/ws/2008/06/identity/claims/groups`       | `custom:groups`    |
| `http://schemas.microsoft.com/identity/claims/objectidentifier`        | `custom:oid`       |
| `http://schemas.microsoft.com/identity/claims/tenantid`                | `custom:tenant_id` |


### 1.3 Networking — what the corporate team needs to provision

**Langfuse UI access (corporate users reaching Langfuse):**


| Item                        | Value                                                                                                                  |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Langfuse hostname           | `exldecision-ai-dev-aigw-langfuse.exlservice.com`                                                                      |
| Langfuse ALB DNS (internal) | `internal-midas-aigtw-langfuse-alb-dev-837475564.us-east-1.elb.amazonaws.com`                                          |
| VPC ID                      | `vpc-0c4d673f3e95a93eb`                                                                                                |
| VPC CIDR                    | `10.72.134.0/23`                                                                                                       |
| Transit Gateway             | `tgw-0ec391fa73943d562` (corporate → MIDAS VPC egress path)                                                            |
| ALB subnets                 | `subnet-04f6c506a5098aa40` (us-east-1c, `10.72.135.64/26`) · `subnet-0bc74e29f773eb7a4` (us-east-1a, `10.72.135.0/26`) |


Corporate network team must **add a route to `10.72.134.0/23` via `tgw-0ec391fa73943d562`** so that users on the corporate network can reach the internal Langfuse ALB.

**Cognito Hosted UI (browser → Entra login page):**
The Cognito Hosted UI at `midas-aigtw-dev-dev.auth.us-east-1.amazoncognito.com` is a **public AWS endpoint** — browser traffic reaches it over the internet. No VPN or VPC route is required for users to complete the Entra login step.

### 1.4 DNS records — required from corporate DNS team

Two records must be created in the `exlservice.com` DNS zone:

**Record 1 — ACM certificate validation (one-time, lets TLS cert issue):**


| Field | Value                                                                                |
| ----- | ------------------------------------------------------------------------------------ |
| Type  | `CNAME`                                                                              |
| Name  | `_9d2e507f52c54d9c1a8bda39735c2ad9.exldecision-ai-dev-aigw-langfuse.exlservice.com.` |
| Value | `_a59c16cf7df95d0c53acba8c27061e92.jkddzztszm.acm-validations.aws.`                  |
| TTL   | 300                                                                                  |


Once created, ACM will validate and issue the certificate (ARN: `arn:aws:acm:us-east-1:811391286931:certificate/5acee63f-b62e-49fc-b309-a5e2d61a18ac`). The Langfuse ALB cannot serve HTTPS until this cert is issued.

**Record 2 — Langfuse UI hostname (points users to the internal ALB):**


| Field | Value                                                                         |
| ----- | ----------------------------------------------------------------------------- |
| Type  | `CNAME` (or `A` via Route 53 alias if DNS is in Route 53)                     |
| Name  | `exldecision-ai-dev-aigw-langfuse.exlservice.com`                             |
| Value | `internal-midas-aigtw-langfuse-alb-dev-837475564.us-east-1.elb.amazonaws.com` |
| TTL   | 60                                                                            |


This record is only resolvable from the corporate network / VPN (the ALB is internal).

---

## 2. What MIDAS needs back from the corporate IdP team


| Item                                                                           | Notes                                                                                                                                                                            |
| ------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Entra federation metadata URL**                                              | Format: `https://login.microsoftonline.com/<TENANT_ID>/federationmetadata/2007-06/federationmetadata.xml`                                                                        |
| **Entra Tenant ID**                                                            | Used to populate `cognito_saml_metadata_url` in `[deploy/ai_gateway/terraform/environment/dev/terragrunt.hcl](../../deploy/ai_gateway/terraform/environment/dev/terragrunt.hcl)` |
| **Confirmation** that `@exlservice.com` is the email domain used for login     | Langfuse identifies users by email — the domain must match what Entra sends in the `emailaddress` claim                                                                          |
| **Confirmation** that the ACM validation DNS CNAME (Record 1) has been created | MIDAS will monitor the cert status in ACM                                                                                                                                        |


---

## 3. MIDAS activation steps (after receiving IdP values)

1. Replace `<TENANT_ID>` in `[deploy/ai_gateway/terraform/environment/dev/terragrunt.hcl](../../deploy/ai_gateway/terraform/environment/dev/terragrunt.hcl)` with the real Entra Tenant ID.
2. Set `enable_saml_identity_provider = true` in the same file.
3. Raise a PR and run **ORD1** (Terraform) — this creates the `EXLerateAI` SAML IdP on the Cognito pool.
4. Run **ORD4** (Langfuse Helm) — no Helm changes needed; `AUTH_CUSTOM_`* is already wired.
5. Test login in incognito — click **"EXLerate SSO"** → Entra → redirect back to Langfuse.
6. Once SSO is validated, optionally set `AUTH_DISABLE_USERNAME_PASSWORD = "true"` to enforce SSO-only.

---

## 4. Integration checklist

### Corporate IdP / DNS team

- Entra App Registration created with ACS URL and Entity ID from §1.2
- SAML attribute mappings configured (§1.2 table)
- ACM validation CNAME created (§1.4 Record 1)
- Langfuse hostname CNAME created (§1.4 Record 2)
- Network route to `10.72.134.0/23` via `tgw-0ec391fa73943d562` added
- Federation metadata URL + Tenant ID provided to MIDAS team

### MIDAS team

- ACM cert status is `ISSUED` (check: `aws acm describe-certificate --certificate-arn arn:aws:acm:us-east-1:811391286931:certificate/5acee63f-b62e-49fc-b309-a5e2d61a18ac --query Certificate.Status`)
- `cognito_saml_metadata_url` updated with real Tenant ID
- `enable_saml_identity_provider = true` set in `terragrunt.hcl`
- ORD1 run — SAML IdP `EXLerateAI` visible on pool `us-east-1_24fpml9So`
- ORD4 run
- Incognito login test successful via Entra

---

*Values sourced from AWS account `811391286931` on 2026-05-01. Re-verify pool ID and ALB DNS name if ORD1 has been re-run since then.*