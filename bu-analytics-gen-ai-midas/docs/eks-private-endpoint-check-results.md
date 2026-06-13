# Private EKS connectivity check (EC2 nodes + Fargate)

**Region:** `us-east-1`  
**EC2 test instance:** `i-047d7dcb9806a494c` (SSM online; same VPC path as future EKS nodes / workloads).  
**Probe:** SSM `AWS-RunShellScript` - `nslookup` (DNS) and `curl` to `https://<host>/` (HTTPS/TLS + HTTP response).  
**Last validated:** 2026-04-05 - `CommandId=f4169519-d00b-4e3f-9a58-6197f1320dae` (script: `deploy/scripts/eks-private-endpoints-probe.sh`).  
**Assumption:** Cluster and data plane are **fully private**; DNS should prefer **VPC interface endpoints** (private IPs in the workload VPC) where those endpoints exist.

**Reference:** [Amazon EKS private clusters](https://docs.aws.amazon.com/eks/latest/userguide/private-clusters.html) - required **interface** endpoints (and **S3** gateway) for nodes and Fargate in a private-only design.

**Handoff to networking:** [Core infrastructure work order - private AWS services](core-infrastructure-workorder-private-aws-services.md) (endpoints, P0 issues, acceptance criteria).

---

## Endpoints required for both EC2-managed nodes and Fargate

These AWS APIs are required (directly or via agents/addons) for a **private** EKS cluster running **both** EC2 capacity and **Fargate** profiles. Map each to **interface** VPC endpoints (and **S3** as a **gateway** endpoint) in the workload VPC, with **Private DNS** enabled where supported.

| AWS service (VPC endpoint name) | Regional hostname probed | EC2 nodes | Fargate |
|--------------------------------|--------------------------|-----------|---------|
| Amazon EKS | `eks.us-east-1.amazonaws.com` | Yes | Yes |
| EKS (`.api.aws` control plane API) | `eks.us-east-1.api.aws` | Yes* | Yes* |
| EKS Auth (Pod Identity / auth API) | `eks-auth.us-east-1.api.aws` | Yes* | Yes* |
| STS | `sts.us-east-1.amazonaws.com` | Yes | Yes |
| EC2 | `ec2.us-east-1.amazonaws.com` | Yes | Yes |
| ECR API | `api.ecr.us-east-1.amazonaws.com` | Yes | Yes |
| ECR DKR | `dkr.ecr.us-east-1.amazonaws.com` | Yes | Yes |
| Elastic Load Balancing | `elasticloadbalancing.us-east-1.amazonaws.com` | Yes | Yes |
| Auto Scaling | `autoscaling.us-east-1.amazonaws.com` | Yes† | No† |
| KMS | `kms.us-east-1.amazonaws.com` | Yes‡ | Yes‡ |
| CloudWatch Logs | `logs.us-east-1.amazonaws.com` | Yes | Yes |
| CloudWatch (metrics) | `monitoring.us-east-1.amazonaws.com` | Yes† | Yes† |
| Systems Manager | `ssm.us-east-1.amazonaws.com` | Yes§ | No§ |
| SSM Messages | `ssmmessages.us-east-1.amazonaws.com` | Yes§ | No§ |
| EC2 Messages | `ec2messages.us-east-1.amazonaws.com` | Yes§ | No§ |
| Amazon S3 | `s3.us-east-1.amazonaws.com` | Yes | Yes |
| Secrets Manager | `secretsmanager.us-east-1.amazonaws.com` | Optional | Optional |
| ACM | `acm.us-east-1.amazonaws.com` | Optional | Optional |

\* Required when using **EKS Pod Identity** / **EKS Auth API** flows; strongly recommended for current EKS feature sets.  
† Common for **Cluster Autoscaler**, **metrics-server**, **CloudWatch** observability.  
‡ Required when **secrets encryption** or workloads use **KMS**.  
§ Needed for **SSM-managed** EC2 nodes (Session Manager, patching). Not used by Fargate itself.

---

## Account-level requirements (beyond VPC endpoints)

VPC interface and gateway endpoints are **necessary but not sufficient**. The table below lists **additional** account, IAM, and platform capabilities typically required to **use** these AWS services in production. Align with your **organization’s security, networking, and landing-zone** standards.

| Area | What you need |
|------|----------------|
| **Organization / SCPs** | No **Service Control Policy** (or similar guardrail) that **denies** the APIs above (e.g. `eks:*`, `ec2:CreateVpcEndpoint`, `rds:*`, `elasticache:*`, `secretsmanager:*`, `kms:*`, `ecr:*`, `elasticloadbalancing:*`, `autoscaling:*`, `logs:*`, `monitoring:*`, `ssm:*`, `s3:*`, `sts:GetCallerIdentity`, `s3control:*`). Confirm **opt-in regions** if your org restricts regions-**`us-east-1`** must be allowed. |
| **IAM (workload & automation)** | **EKS:** cluster IAM role, **OIDC provider** for IRSA (if used), node/Fargate execution roles, Pod Identity / IRSA policies. **ECR:** pull/push policies for nodes and CI. **RDS / ElastiCache:** least-privilege for provisioning and runtime (e.g. Secrets Manager read, RDS `rds-db:connect` if IAM DB auth). **KMS:** key policies allowing EKS, RDS, Secrets Manager, S3 as applicable. **SSM:** instance profile for managed nodes. |
| **Service-linked roles (SLRs)** | AWS creates SLRs when you first use a service (e.g. **ELB**, **Auto Scaling**, **EKS**, **RDS**, **ElastiCache**). Ensure IAM **trust** and **org policies** allow **`iam:CreateServiceLinkedRole`** (or pre-create SLRs) for those services. |
| **Service quotas** | **EKS** clusters/Fargate, **EC2** vCPU, **EIP** (if any), **VPC endpoints** per VPC, **RDS** instances, **ElastiCache** nodes-request increases before scale. |
| **KMS** | **CMKs** or AWS managed keys for: **EKS** secrets encryption, **RDS** / **ElastiCache** at rest (if enabled), **Secrets Manager**, **S3** buckets, **EBS** (nodes). Key policies must allow the consuming principals. |
| **VPC networking (data plane)** | **Subnets** for EKS (nodes/Fargate ENIs), **RDS subnet groups**, **ElastiCache subnet groups**-typically **private**, multi-AZ. **Security groups**: node ↔ cluster API (443), node ↔ ECR, app ↔ RDS/ElastiCache ports, endpoints SG allowing **443** from workload CIDRs. **NACLs** and **TGW** routes must allow traffic to **VPC endpoint** subnets and (if used) **egress** paths. |
| **Route 53 / DNS** | **Private hosted zones** (optional), **Route 53 Resolver** rules for hybrid DNS, **conditional forwarders**-must not block **`*.api.aws`** or regional service names used by EKS. **Private DNS** on interface endpoints must be **enabled** where required. |
| **ECR** | **Repositories** created; **lifecycle policies**; **image scanning** if required. Nodes need **pull** access via instance/task role-**VPC endpoint alone does not grant IAM permission**. |
| **RDS (PostgreSQL)** | **DB subnet group**, **parameter/option groups**, **security groups**, optional **IAM DB authentication**, **Performance Insights** role if used. **Public accessibility = false** for private DBs. |
| **ElastiCache (Redis)** | **Subnet group**, **security groups**, **parameter group**; **TLS** / **AUTH** if required. **Serverless vs node-based**-different quotas. |
| **S3** | **Buckets** and **policies**; **gateway endpoint** route tables; **block public access** defaults. **S3 Control** APIs need **IAM** + working **DNS** to `s3-control` endpoint. |
| **CloudWatch** | **Log groups** (retention), **metric alarms**-IAM to `logs:*` / `cloudwatch:*` as needed. |
| **Systems Manager** | **SSM Agent** on EC2 nodes, **instance profile**, **Session Manager** preferences (KMS log encryption optional). |
| **ACM** | **Certificate** in **same region** as ALB/NLB (or use appropriate pattern); **DNS validation** may need **Route 53** or manual records. |
| **EKS-specific** | **Cluster** and **Fargate profiles** in **supported subnets**; **add-ons** (VPC CNI, CoreDNS, kube-proxy, EBS CSI, etc.) pull from **ECR**-depends on **ECR + DKR** path. **Pod Identity** / **EKS Auth** require working **`eks-auth` / `eks.*.api.aws`** path. |
| **Cross-account / shared VPC** | If **VPC** is **owned by a network account**, confirm **resource shares**, **RAM**, **endpoint policy** permissions, and **who** may create endpoints in that VPC. |

**Summary:** Endpoints fix **north-south API reachability**; you still need **IAM**, **KMS**, **security groups**, **subnet groups**, **quotas**, **SCP allow-lists**, and **service configuration** for each product (EKS, RDS, ElastiCache, S3, etc.).

---

## Traffic-light legend

| Signal | DNS | HTTPS |
|--------|-----|--------|
| **Green** | Name resolves to **RFC1918** addresses in the VPC range (e.g. `10.72.x.x`) consistent with **interface endpoints** + **Private DNS**. | TLS completes within timeout; HTTP status is irrelevant if AWS responds (403/404/301/302/400/307 treated as OK). |
| **Amber** | Name resolves, but answers are **public** AWS addresses (or mixed) when **private endpoint DNS** was the target architecture. | TLS completes but **certificate warnings** (e.g. hostname mismatch) or other partial failure. |
| **Red** | **NXDOMAIN**, timeout, or no usable answer. | **Connection reset**, timeout, or **no TLS** (`http_code=000` / curl errors 35, 60, etc.). |

---

## Summary of findings (this run)

- **DNS:** **Private** `10.72.x.x` answers for **EC2, ECR API, ECR DKR, Secrets Manager, RDS API** (`rds.us-east-1.amazonaws.com`). **Public** answers for most other regional names (**amber** vs strict private-only DNS). **`s3-control.us-east-1.amazonaws.com`** returned **no DNS answer** from the instance resolver (**red**)-expect **`s3control`** interface endpoint + **Private DNS** or resolver policy.
- **HTTPS:** **Red** on **`eks.us-east-1.api.aws`** and **`eks-auth.us-east-1.api.aws`** (TLS **connection reset**). **Amber** on **`dkr.ecr.us-east-1.amazonaws.com`** (**certificate SAN mismatch**). **Red** on **`s3-control.us-east-1.amazonaws.com`** (no resolve → no HTTPS). **RDS API** and **RDS Data API** / **ElastiCache API** returned usable TLS where DNS worked (**🟢** HTTPS for `rds`, **🟢** for `rds-data` and `elasticache` with HTTP 404).
- **Verdict:** Same **EKS `.api.aws` / EKS Auth** and **ECR DKR** gaps as prior runs; add **S3 Control** to the fix list until **`s3-control.us-east-1.amazonaws.com`** resolves and TLS succeeds. Align **RDS Data** / **ElastiCache** with **interface endpoints + Private DNS** if those APIs must not use public resolution.

---

## Per-endpoint results and remediation

| Endpoint | DNS | HTTPS | Configuration / connectivity fix | DNS fix (private design) |
|----------|-----|-------|----------------------------------|---------------------------|
| `eks.us-east-1.amazonaws.com` | 🟡 | 🟢 | None if public endpoint access is intended; otherwise ensure **com.amazonaws.us-east-1.eks** interface endpoint + policies. | Enable **Private DNS** on EKS endpoint; confirm Route 53 resolver / hybrid DNS. |
| `eks.us-east-1.api.aws` | 🟡 | 🔴 | **Critical:** TLS reset-check **security groups**, **NACLs**, **firewall**, **proxy**, and **interface endpoint** for EKS; no middlebox RST on 443. | Steer name to **VPC endpoint** DNS; fix split-horizon so clients do not hit blocked paths. |
| `eks-auth.us-east-1.api.aws` | 🟡 | 🔴 | **Critical:** Same as above for **EKS Auth** / Pod Identity path. | Same as `eks` / `eks-auth` endpoint **Private DNS**. |
| `sts.us-east-1.amazonaws.com` | 🟡 | 🟢 | Add **STS** interface endpoint if traffic must stay private. | **Private DNS** for `sts`. |
| `ec2.us-east-1.amazonaws.com` | 🟢 | 🟢 | None observed. | None observed. |
| `api.ecr.us-east-1.amazonaws.com` | 🟢 | 🟢 | None observed. | None observed. |
| `dkr.ecr.us-east-1.amazonaws.com` | 🟢 | 🟡 | **ECR DKR** TLS name mismatch: validate endpoint presents cert for `dkr.ecr...`; rule out **SSL inspection** or wrong VIP. | If using custom DNS, ensure it targets the **ECR DKR** endpoint ENIs. |
| `elasticloadbalancing.us-east-1.amazonaws.com` | 🟡 | 🟢 | Add **ELB** interface endpoint for private-only egress. | **Private DNS** for ELB endpoint. |
| `autoscaling.us-east-1.amazonaws.com` | 🟡 | 🟢 | Add **Auto Scaling** interface endpoint if CA / ASG API must be private. | **Private DNS**. |
| `kms.us-east-1.amazonaws.com` | 🟡 | 🟢 | Add **KMS** interface endpoint if KMS used from private subnets only. | **Private DNS**. |
| `logs.us-east-1.amazonaws.com` | 🟡 | 🟢 | Add **Logs** interface endpoint for private logging path. | **Private DNS**. |
| `monitoring.us-east-1.amazonaws.com` | 🟡 | 🟢 | Add **monitoring** interface endpoint for private metrics path. | **Private DNS**. |
| `ssm.us-east-1.amazonaws.com` | 🟡 | 🟢 | Required only for **SSM on EC2 nodes**; add endpoint if nodes use SSM. | **Private DNS**. |
| `ssmmessages.us-east-1.amazonaws.com` | 🟡 | 🟢 | Pair with SSM for Session Manager. | **Private DNS**. |
| `ec2messages.us-east-1.amazonaws.com` | 🟡 | 🟢 | Pair with SSM agent. | **Private DNS**. |
| `s3.us-east-1.amazonaws.com` | 🟡 | 🟢 | Ensure **S3 gateway endpoint** (and routes) for private clusters; `nslookup` may still show public-validate **routing**, not DNS alone. | **Gateway endpoint** + route tables; **interface** not required for classic S3 gateway pattern. |
| `s3-control.us-east-1.amazonaws.com` | 🔴 | 🔴 | **`s3control`** interface endpoint missing or **Private DNS** off; resolver returned **no answer** on test instance. | Enable **Private DNS** on `com.amazonaws.us-east-1.s3control` or fix **Route 53 Resolver** / corporate forwarding. |
| `secretsmanager.us-east-1.amazonaws.com` | 🟢 | 🟢 | None observed. | None observed. |
| `acm.us-east-1.amazonaws.com` | 🟡 | 🟢 | Add **ACM** interface endpoint if certs/API must be private-only. | **Private DNS**. |
| `rds.us-east-1.amazonaws.com` | 🟢 | 🟢 | None observed. | None observed. |
| `rds-data.us-east-1.amazonaws.com` | 🟡 | 🟢 | Add **rds-data** interface endpoint if **Data API** must stay private-only. | **Private DNS** for `rds-data`. |
| `elasticache.us-east-1.amazonaws.com` | 🟡 | 🟢 | Add **elasticache** interface endpoint if control-plane API must stay private-only. | **Private DNS** for ElastiCache API. |

---

## Additional services: required endpoints and DNS (`us-east-1`)

The sections below group **VPC endpoint identifiers** (for Terraform / console), **regional API hostnames** (SDK/CLI/control plane), and **application/data-plane DNS** patterns. All assume workloads run in **private subnets** with **interface** endpoints (or **gateway** for S3) and **Private DNS** where applicable.

### Amazon RDS (PostgreSQL)

| Role | VPC endpoint service name | DNS / hostname | Notes |
|------|---------------------------|----------------|--------|
| **RDS API** (create/modify/describe DBs) | `com.amazonaws.us-east-1.rds` | `rds.us-east-1.amazonaws.com` | **Interface** endpoint; enable **Private DNS** so the regional name resolves to VPC addresses. |
| **RDS Data API** (optional; Aurora Serverless v2 / certain setups) | `com.amazonaws.us-east-1.rds-data` | `rds-data.us-east-1.amazonaws.com` | Only if you use **Data API** instead of direct SQL over 5432. |
| **PostgreSQL data plane** | *(none-traffic stays in VPC)* | `*.XXXXXXXXXXXX.us-east-1.rds.amazonaws.com` (instance) or `*.cluster-XXXXXXXXXXXX.us-east-1.rds.amazonaws.com` / `*.cluster-ro-...` (Aurora) | Resolved inside the VPC to **private IPs** of the DB subnet group; **not** the same as the RDS API endpoint. Requires **security groups** (ECS/EKS → RDS), **subnet routing**, and **no** internet requirement for the DB if truly private. |
| **Performance Insights / Enhanced Monitoring** | Uses **CloudWatch** / **monitoring** APIs | `monitoring.us-east-1.amazonaws.com` (see probe table) | Align with interface endpoint for **monitoring** if API calls must be private. |

**Probe cross-reference (EC2 test instance):** `rds.us-east-1.amazonaws.com` - DNS 🟢 / HTTPS 🟢 (HTTP 302). `rds-data.us-east-1.amazonaws.com` - DNS 🟡 / HTTPS 🟢 (HTTP 404).

**DNS summary:** Use **Private DNS** on **`rds` interface endpoint** for `rds.us-east-1.amazonaws.com`. DB **connection strings** use the **per-instance or per-cluster hostname** from RDS console (always **private** for private subnets).

---

### AWS Secrets Manager

| Role | VPC endpoint service name | DNS / hostname | Notes |
|------|---------------------------|----------------|--------|
| **Secrets Manager API** | `com.amazonaws.us-east-1.secretsmanager` | `secretsmanager.us-east-1.amazonaws.com` | **Interface** endpoint + **Private DNS** for SDK/CLI from private subnets. |

**Probe cross-reference:** `secretsmanager.us-east-1.amazonaws.com` - DNS 🟢 / HTTPS 🟢 in this run.

**DNS summary:** Single regional hostname; **Private DNS** on the endpoint makes `secretsmanager.us-east-1.amazonaws.com` resolve to **VPC** addresses.

---

### Amazon ElastiCache (Redis)

| Role | VPC endpoint service name | DNS / hostname | Notes |
|------|---------------------------|----------------|--------|
| **ElastiCache API** (create clusters, modify) | `com.amazonaws.us-east-1.elasticache` | `elasticache.us-east-1.amazonaws.com` | **Interface** endpoint for API calls from private subnets. |
| **Redis data plane** | *(none-traffic stays in VPC)* | `*.XXXXX.ng.0001.use1.cache.amazonaws.com` (node), `*.XXXXX.serverless.use1.cache.amazonaws.com` (Serverless), replication group CNAMEs | Endpoints resolve to **ENIs in your VPC**; **not** HTTPS to `elasticache.amazonaws.com`. Requires **security groups** and **subnet** placement. |

**Probe cross-reference (EC2 test instance):** `elasticache.us-east-1.amazonaws.com` - DNS 🟡 / HTTPS 🟢 (HTTP 404).

**DNS summary:** **API:** enable **Private DNS** for `elasticache.us-east-1.amazonaws.com` via the **elasticache** interface endpoint. **Redis clients** use the **cluster/configuration endpoint** hostnames from the ElastiCache console (VPC-internal).

---

### Amazon S3

| Role | VPC endpoint service name | DNS / hostname | Notes |
|------|---------------------------|----------------|--------|
| **S3 API** (private-only; no NAT) | `com.amazonaws.us-east-1.s3` (**Gateway** endpoint) | `s3.us-east-1.amazonaws.com`, `bucket-name.s3.us-east-1.amazonaws.com`, `bucket-name.s3.amazonaws.com` (legacy) | **Gateway** endpoint attached to **route tables** for subnets that need S3; **no** Private DNS in the same way as interface endpoints-routing is via **prefix list** / gateway. Optional **interface** endpoint exists for S3 if your design uses it. |
| **S3 Control** (optional; bucket policies / multi-region) | `com.amazonaws.us-east-1.s3control` | `s3-control.us-east-1.amazonaws.com` | Add if workloads call **S3 Control** API from private subnets only. |

**Probe cross-reference:** `s3.us-east-1.amazonaws.com` - DNS 🟡 / HTTPS 🟢 in this run (public answers from `nslookup` are expected unless you rely on gateway routing only).

**S3 Control probe:** `s3-control.us-east-1.amazonaws.com` - DNS 🔴 / HTTPS 🔴 (`nslookup` **no answer**; `curl` could not resolve). Deploy **`com.amazonaws.us-east-1.s3control`** with **Private DNS**, or confirm **Route 53 Resolver** / corporate DNS policy allows this name.

**DNS summary:** Prefer **gateway endpoint** + **correct route table associations**; validate **bucket** hostnames resolve and traffic uses the **VPC endpoint path** per your network design.

---

### Amazon EC2

| Role | VPC endpoint service name | DNS / hostname | Notes |
|------|---------------------------|----------------|--------|
| **EC2 API** | `com.amazonaws.us-east-1.ec2` | `ec2.us-east-1.amazonaws.com` | **Interface** endpoint + **Private DNS** for Describe*, RunInstances, etc., from private subnets. |

**Probe cross-reference:** `ec2.us-east-1.amazonaws.com` - DNS 🟢 / HTTPS 🟢 in this run.

**DNS summary:** **Private DNS** on the **ec2** interface endpoint should steer `ec2.us-east-1.amazonaws.com` to **VPC** addresses. **User instances** do not use this hostname for east-west traffic; it is for **AWS API** access.

---

## Raw probe output (verbatim)

<details>
<summary>Click to expand</summary>

```
Status=Success
CommandId=f4169519-d00b-4e3f-9a58-6197f1320dae

=== eks.us-east-1.amazonaws.com ===
Server:		127.0.0.53
Address:	127.0.0.53#53

Non-authoritative answer:
Name:	eks.us-east-1.amazonaws.com
Address: 52.204.111.168
Name:	eks.us-east-1.amazonaws.com
Address: 18.215.111.185
Name:	eks.us-east-1.amazonaws.com
Address: 52.71.221.249

http_code=403 connect=0.003515s

=== eks.us-east-1.api.aws ===
Server:		127.0.0.53
Address:	127.0.0.53#53

Non-authoritative answer:
Name:	eks.us-east-1.api.aws
Address: 3.209.201.58
Name:	eks.us-east-1.api.aws
Address: 44.219.119.252
Name:	eks.us-east-1.api.aws
Address: 44.221.0.115
Name:	eks.us-east-1.api.aws
Address: 2600:1f18:2b4e:b803:d16e:35f7:9fc3:189a
Name:	eks.us-east-1.api.aws
Address: 2600:1f18:2b4e:b801:f1b4:2be7:ee46:33ca
Name:	eks.us-east-1.api.aws
Address: 2600:1f18:2b4e:b802:e1e2:a9ff:a8ff:a4d1

curl: (35) OpenSSL SSL_connect: Connection reset by peer in connection to eks.us-east-1.api.aws:443 
http_code=000 connect=0.003932s

=== eks-auth.us-east-1.api.aws ===
Server:		127.0.0.53
Address:	127.0.0.53#53

Non-authoritative answer:
Name:	eks-auth.us-east-1.api.aws
Address: 54.82.222.117
Name:	eks-auth.us-east-1.api.aws
Address: 2600:1f18:3375:bf00:1505:e9a9:babd:3341

curl: (35) OpenSSL SSL_connect: Connection reset by peer in connection to eks-auth.us-east-1.api.aws:443 
http_code=000 connect=0.004282s

=== sts.us-east-1.amazonaws.com ===
Server:		127.0.0.53
Address:	127.0.0.53#53

Non-authoritative answer:
Name:	sts.us-east-1.amazonaws.com
Address: 13.217.78.146

http_code=302 connect=0.005417s

=== ec2.us-east-1.amazonaws.com ===
Server:		127.0.0.53
Address:	127.0.0.53#53

Non-authoritative answer:
Name:	ec2.us-east-1.amazonaws.com
Address: 10.72.135.81
Name:	ec2.us-east-1.amazonaws.com
Address: 10.72.135.172

http_code=301 connect=0.004069s

=== api.ecr.us-east-1.amazonaws.com ===
Server:		127.0.0.53
Address:	127.0.0.53#53

Non-authoritative answer:
Name:	api.ecr.us-east-1.amazonaws.com
Address: 10.72.135.75
Name:	api.ecr.us-east-1.amazonaws.com
Address: 10.72.135.169

http_code=404 connect=0.004001s

=== dkr.ecr.us-east-1.amazonaws.com ===
Server:		127.0.0.53
Address:	127.0.0.53#53

Non-authoritative answer:
Name:	dkr.ecr.us-east-1.amazonaws.com
Address: 10.72.134.251
Name:	dkr.ecr.us-east-1.amazonaws.com
Address: 10.72.135.174

curl: (60) SSL: no alternative certificate subject name matches target host name 'dkr.ecr.us-east-1.amazonaws.com'
More details here: https://curl.se/docs/sslcerts.html

curl failed to verify the legitimacy of the server and therefore could not
establish a secure connection to it. To learn more about this situation and
how to fix it, please visit the web page mentioned above.
http_code=000 connect=0.004130s

=== elasticloadbalancing.us-east-1.amazonaws.com ===
Server:		127.0.0.53
Address:	127.0.0.53#53

Non-authoritative answer:
Name:	elasticloadbalancing.us-east-1.amazonaws.com
Address: 54.239.29.176

http_code=400 connect=0.003858s

=== autoscaling.us-east-1.amazonaws.com ===
Server:		127.0.0.53
Address:	127.0.0.53#53

Non-authoritative answer:
Name:	autoscaling.us-east-1.amazonaws.com
Address: 44.216.184.178

http_code=302 connect=0.005267s

=== kms.us-east-1.amazonaws.com ===
Server:		127.0.0.53
Address:	127.0.0.53#53

Non-authoritative answer:
Name:	kms.us-east-1.amazonaws.com
Address: 44.216.189.96

http_code=404 connect=0.006175s

=== logs.us-east-1.amazonaws.com ===
Server:		127.0.0.53
Address:	127.0.0.53#53

Non-authoritative answer:
Name:	logs.us-east-1.amazonaws.com
Address: 3.236.94.200
Name:	logs.us-east-1.amazonaws.com
Address: 3.236.94.201
Name:	logs.us-east-1.amazonaws.com
Address: 3.236.94.228
Name:	logs.us-east-1.amazonaws.com
Address: 3.236.94.251
Name:	logs.us-east-1.amazonaws.com
Address: 44.202.79.158
Name:	logs.us-east-1.amazonaws.com
Address: 44.202.79.185
Name:	logs.us-east-1.amazonaws.com
Address: 3.236.94.151
Name:	logs.us-east-1.amazonaws.com
Address: 3.236.94.164

http_code=404 connect=0.004782s

=== monitoring.us-east-1.amazonaws.com ===
Server:		127.0.0.53
Address:	127.0.0.53#53

Non-authoritative answer:
Name:	monitoring.us-east-1.amazonaws.com
Address: 44.213.98.34
Name:	monitoring.us-east-1.amazonaws.com
Address: 44.213.98.38
Name:	monitoring.us-east-1.amazonaws.com
Address: 44.213.98.50
Name:	monitoring.us-east-1.amazonaws.com
Address: 44.213.98.79
Name:	monitoring.us-east-1.amazonaws.com
Address: 44.213.98.104
Name:	monitoring.us-east-1.amazonaws.com
Address: 44.213.98.194
Name:	monitoring.us-east-1.amazonaws.com
Address: 44.213.98.225
Name:	monitoring.us-east-1.amazonaws.com
Address: 44.213.98.253

http_code=404 connect=0.005380s

=== ssm.us-east-1.amazonaws.com ===
Server:		127.0.0.53
Address:	127.0.0.53#53

Non-authoritative answer:
Name:	ssm.us-east-1.amazonaws.com
Address: 100.55.128.217

http_code=400 connect=0.005299s

=== ssmmessages.us-east-1.amazonaws.com ===
Server:		127.0.0.53
Address:	127.0.0.53#53

Non-authoritative answer:
Name:	ssmmessages.us-east-1.amazonaws.com
Address: 98.87.173.241

http_code=400 connect=0.005632s

=== ec2messages.us-east-1.amazonaws.com ===
Server:		127.0.0.53
Address:	127.0.0.53#53

Non-authoritative answer:
Name:	ec2messages.us-east-1.amazonaws.com
Address: 98.90.63.41

http_code=404 connect=0.004609s

=== s3.us-east-1.amazonaws.com ===
Server:		127.0.0.53
Address:	127.0.0.53#53

Non-authoritative answer:
Name:	s3.us-east-1.amazonaws.com
Address: 52.217.201.96
Name:	s3.us-east-1.amazonaws.com
Address: 52.217.201.112
Name:	s3.us-east-1.amazonaws.com
Address: 16.15.207.71
Name:	s3.us-east-1.amazonaws.com
Address: 16.182.64.88
Name:	s3.us-east-1.amazonaws.com
Address: 52.216.38.184
Name:	s3.us-east-1.amazonaws.com
Address: 52.216.54.112
Name:	s3.us-east-1.amazonaws.com
Address: 52.216.62.112
Name:	s3.us-east-1.amazonaws.com
Address: 52.217.120.72

http_code=307 connect=0.001824s

=== s3-control.us-east-1.amazonaws.com ===
Server:		127.0.0.53
Address:	127.0.0.53#53

Non-authoritative answer:
*** Can't find s3-control.us-east-1.amazonaws.com: No answer

curl: (6) Could not resolve host: s3-control.us-east-1.amazonaws.com
http_code=000 connect=0.000000s

=== secretsmanager.us-east-1.amazonaws.com ===
Server:		127.0.0.53
Address:	127.0.0.53#53

Non-authoritative answer:
Name:	secretsmanager.us-east-1.amazonaws.com
Address: 10.72.135.186
Name:	secretsmanager.us-east-1.amazonaws.com
Address: 10.72.135.201

http_code=404 connect=0.004928s

=== acm.us-east-1.amazonaws.com ===
Server:		127.0.0.53
Address:	127.0.0.53#53

Non-authoritative answer:
Name:	acm.us-east-1.amazonaws.com
Address: 44.216.188.149

http_code=404 connect=0.005105s

=== rds.us-east-1.amazonaws.com ===
Server:		127.0.0.53
Address:	127.0.0.53#53

Non-authoritative answer:
Name:	rds.us-east-1.amazonaws.com
Address: 10.72.134.29
Name:	rds.us-east-1.amazonaws.com
Address: 10.72.135.190

http_code=302 connect=0.004437s

=== rds-data.us-east-1.amazonaws.com ===
Server:		127.0.0.53
Address:	127.0.0.53#53

Non-authoritative answer:
Name:	rds-data.us-east-1.amazonaws.com
Address: 34.200.123.248
Name:	rds-data.us-east-1.amazonaws.com
Address: 44.219.242.28
Name:	rds-data.us-east-1.amazonaws.com
Address: 44.221.253.237
Name:	rds-data.us-east-1.amazonaws.com
Address: 18.209.140.120
Name:	rds-data.us-east-1.amazonaws.com
Address: 18.235.102.174

http_code=404 connect=0.005101s

=== elasticache.us-east-1.amazonaws.com ===
Server:		127.0.0.53
Address:	127.0.0.53#53

Non-authoritative answer:
Name:	elasticache.us-east-1.amazonaws.com
Address: 13.217.78.139

http_code=404 connect=0.005833s

```

</details>

---

*This document was generated from automated probes; rotate any credentials used for AWS CLI and do not commit secrets to the repository.*
