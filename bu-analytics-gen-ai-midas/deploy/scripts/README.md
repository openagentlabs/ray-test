# `deploy/scripts`

Operational and CI helpers for the MIDAS **`deploy/`** tree (Jenkins agents, laptops with AWS access, SSM probes). **Not** all are run by **`deploy/Jenkinsfile_Deploy_App`** - see each section.

See also: **[Solution documentation index](../../README.midas.md)** · **[`deploy/README.md`](../README.md)** · **[`.cursor/scripts/README.md`](../../.cursor/scripts/README.md)** (Cursor-local helpers) · **`.cursor/rules/scripts_docs.mdc`**

## Layout

| Folder | Role |
|--------|------|
| **`ci/`** | Intended for **Jenkins `cicd`** agents: Docker build/push, Helm (same paths the Jenkinsfile calls). |
| **`dev/`** | **Development / operations**: env gates, EKS monitoring, SSM endpoint probes, Terraform validate, Secrets Manager recovery. |
| **`test/`** | **Manual connectivity tests** (S3, Secrets Manager, RDS, ElastiCache) - often interactive; use **`--help`** per script. |
| **`util/`** | **Shared utilities**: credentials helper, IAM validators, **security-group traffic-light checks**, **RDS `psql` / Redis `redis-cli` TLS probes** from a laptop or jump host. |

---

## Laptop / workstation: RDS & ElastiCache (us-east-1)

MIDAS **RDS** and **ElastiCache** are **private**; security groups usually allow **EKS** (and sometimes **jump / laptop CIDRs** after your team adds rules). From your **laptop** you can still run meaningful checks in this order:

| Step | What to run | What it proves |
|------|-------------|----------------|
| 1 | **[`aws-credentials-setup.sh`](util/aws-credentials-setup.sh)** then **`export AWS_PROFILE=…`** **`AWS_REGION=us-east-1`** | AWS CLI can call **`sts`** / **`ec2`** for the checks below. |
| 2 | **[`aws-sg-check-laptop-access.sh`](util/aws-sg-check-laptop-access.sh)** (optional **`MIDAS_SG_LAPTOP_CIDRS`**) | **Read-only:** whether **RDS :5432** and **Redis :6379** security groups include ingress from **your** CIDRs (traffic-light table). Does **not** open a DB connection. Details: **[`deploy/README.md` §10](../README.md#section-10-sg-checks)**. |
| 3 | **[`rds-psql-ssl-verify-full.sh`](util/rds-psql-ssl-verify-full.sh)** with **`RDS_NAME`**, **`RDS_IP`**, **`PGPASSWORD`** | End-to-end **PostgreSQL** over **TLS** (`verify-full`). Requires a **network path** to the DB (corporate **VPN**, **SSM jump box**, etc.); otherwise you will see **timeout**. **`--help`** on the script. |
| 4 | **[`elasticache-redis-cli-tls-ping.sh`](util/elasticache-redis-cli-tls-ping.sh)** with **`REDIS_NAME`**, **`REDIS_AUTH`** (or **`REDISCLI_AUTH`**), optional **`REDIS_IP`** | **TLS + AUTH**; default **`PING`** → **`PONG`**. Needs **`redis-cli`** with **`--tls`** (and **`--sni`** if using **`REDIS_IP`**). Same **routing** caveats as RDS. **`--help`** on the script. |
| (alt) | **`test/`** [RDS](test/midas-rds-postgres-connect.py) / [ElastiCache](test/midas-elasticache-redis-test-access.py) Python scripts | **AWS APIs** (and optional live **Redis** ping / **RDS** `SELECT`) with **boto3**; RDS still needs **TCP :5432** from the host running Python. |

### Example hostnames, private IPs, and CIDRs (us-east-1)

**These drift** after failovers, reprovisions, or per-environment differences. **Confirm** in the AWS console or CLI (**`describe-db-instances`**, **`describe-replication-groups`**, **`describe-cache-clusters`**) before treating any value as current.

| What | Value | Where it is used |
|------|--------|------------------|
| **RDS** endpoint (DNS, TLS hostname) | `midas.cuzwqoeau6l8.us-east-1.rds.amazonaws.com` | Default **`RDS_NAME`** in **`rds-psql-ssl-verify-full.sh`** |
| **RDS** primary private IPv4 | `10.72.134.166` | Default **`RDS_IP`** in **`rds-psql-ssl-verify-full.sh`** (example **DEV** writer in **us-east-1c**) |
| **RDS** TCP port | `5432` | **`RDS_PORT`** |
| **Redis** primary endpoint (DNS) | *(no script default - set **`REDIS_NAME`**)* | Shape: **`master.midas-<env>-redis.<16-hex>.use1.cache.amazonaws.com`** from Terraform output **`primary_endpoint_address`** or ElastiCache console |
| **Redis** node private IPv4 | *(optional **`REDIS_IP`** - set if you want TCP to an IP with **`--sni`**)* | ElastiCache → cluster → **Primary endpoint** / node details, or **`aws elasticache describe-cache-clusters`** |
| **Redis** TCP port | `6379` | **`REDIS_PORT`** |
| **Laptop / jump** source CIDRs (SG ingress expectation) | `10.54.74.117/32`, `10.54.67.114/32` | Default **`MIDAS_SG_LAPTOP_CIDRS`** in **`aws-sg-traffic-checks.py`** for **`aws-sg-check-laptop-access.sh`** |
| **Jenkins / Helm** source CIDR (EKS API **:443**) | `10.90.12.0/22` | Default **`MIDAS_JENKINS_HELM_CIDR`** for **`aws-sg-check-jenkins-helm-to-eks.sh`** |
| **CA bundle URL** (HTTPS download for **`psql`** / **`redis-cli --cacert`**) | `https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem` | **`rds-psql-ssl-verify-full.sh`** and **`elasticache-redis-cli-tls-ping.sh`** (override with **`MIDAS_RDS_SSLROOTCERT`** / **`MIDAS_REDIS_CACERT`** or **`REDIS_CA_URL`**) |

**Repository root:** run paths as **`./deploy/scripts/util/…`** (see **`deploy/README.md`** path convention). For deeper context, **`deploy/README.md`** §**2.7**, §**8** (RDS), §**9.4** (Redis), and §**10** (SG checks).

---

## `ci/`

| Script | Purpose |
|--------|--------|
| [`docker-build-matrix.sh`](ci/docker-build-matrix.sh) | Builds every image listed in **`deploy/ecs-app/docker/build-registry/images.yaml`** (`docker build` per row). Uses **`yq`** (downloaded to **`.cache-ci/yq`** if missing). **`IMAGE_TAG`** defaults to `latest`. Run from **repository root**. |
| [`push-images-ecr.sh`](ci/push-images-ecr.sh) | ECR login, then tags and pushes each matrix image to URLs from env vars **`ECR_URL_*`** (from Terraform outputs). Requires **`IMAGE_TAG`**, **`AWS_ACCOUNT_ID`**, **`TENANT_ENV`**. |
| [`helm-deploy-releases.sh`](ci/helm-deploy-releases.sh) | Reads **`deploy/ecs-app/helm/releases.yaml`**, runs **`helm upgrade --install`** per release; needs **`EKS_CLUSTER_NAME`**, **`IMAGE_TAG`**, same **`ECR_URL_*`** as push. Requires network to **private** EKS API if cluster is private. |
| [`eks-rollout-restart.sh`](ci/eks-rollout-restart.sh) | Runs **`kubectl rollout restart`** on MIDAS deployments to force a fresh pod pull (e.g. after pushing a new image under the same tag). Requires **`EKS_CLUSTER_NAME`**. |
| [`populate-secrets.sh`](ci/populate-secrets.sh) | Writes application secrets into AWS Secrets Manager for a given environment. Requires AWS credentials and environment variables for secret values. |
| [`set-graphrag-api-key.sh`](ci/set-graphrag-api-key.sh) | Stores or rotates the GraphRAG API key in Secrets Manager for the target environment. |
| [`fix-sm-app-aws-region-keys.sh`](ci/fix-sm-app-aws-region-keys.sh) | Patches **`aws_region`** / **`AWS_REGION`** keys inside the MIDAS app Secrets Manager secret when the region value is stale (e.g. after a region migration or initial bootstrap). |
| [`terraform-check-ecs-app-aws-sg-descriptions-ascii.py`](ci/terraform-check-ecs-app-aws-sg-descriptions-ascii.py) | Validates that all security group **`description`** fields in **`deploy/ecs-app/`** are pure ASCII (AWS rejects non-ASCII descriptions). Run in the Jenkins pipeline before `terraform plan`. |

**Typical env (after Terraform outputs):** `source deploy/.ci/terraform-env.sh` (Jenkins), then set **`IMAGE_TAG`**.

---

## `dev/`

| Script | Purpose |
|--------|--------|
| [`env-protection.sh`](dev/env-protection.sh) | **UAT/PROD gate:** ensures **`BUILD_USER_ID`** is listed in **`deploy/resources/approvers/<env>.txt`**. No-op for **`dev`**. Invoked from **`Jenkinsfile_Deploy_App`** (run from **`deploy/`** so `resources/` resolves). |
| [`terraform-validate-ecs-app.sh`](dev/terraform-validate-ecs-app.sh) | **`terraform fmt -check`**, **`terraform init -backend=false`**, **`terraform validate`** under **`deploy/ecs-app`**. Needs Terraform and credentials for provider init. |
| [`eks-monitor-provision.sh`](dev/eks-monitor-provision.sh) | **Observe** EKS cluster/node group creation (AWS CLI): polls until ACTIVE, summarizes ASG and control-plane logs. **`CLUSTER_NAME`**, **`NODE_GROUP_NAME`**, **`AWS_REGION`**. |
| [`eks-ssm-endpoint-check.sh`](dev/eks-ssm-endpoint-check.sh) | **11-host** DNS/HTTPS probe script for EKS-related endpoints; payload sent via **SSM** to **`INSTANCE_ID`**. Optional **`TRAFFIC_LIGHT=1`** for report format. |
| [`eks-private-endpoints-probe.sh`](dev/eks-private-endpoints-probe.sh) | **Extended** private-EKS endpoint probe (more hosts than core 11). **`TRAFFIC_LIGHT=1`** supported. |
| [`eks-probe-to-traffic-light.py`](dev/eks-probe-to-traffic-light.py) | Converts raw SSM probe stdout into the traffic-light style report (pairs with **`eks-ssm-endpoint-check`** / **`eks-private-endpoints-probe`**). |
| [`midas-secretsmanager-app-unstick.sh`](dev/midas-secretsmanager-app-unstick.sh) | Restores or deletes/recreates **`midas-*-us-east-1/app`** Secrets Manager secret when stuck in pending deletion. Modes: **`restore`**, **`restore-and-delete`**. Override **`SECRET_ID`**, **`AWS_REGION`** as needed. |
| [`kubectl-validate-via-jumpbox.sh`](dev/kubectl-validate-via-jumpbox.sh) | Sends a **`kubectl get nodes`** + **`kubectl get pods -A`** command to the jumpbox via **SSM `send-command`** and prints the result; validates EKS access from the jumpbox without a local kubeconfig. |
| [`kubectl-logs-via-jumpbox.sh`](dev/kubectl-logs-via-jumpbox.sh) | Streams **`kubectl logs`** for a named pod (or most-recent pod matching a label selector) via SSM **`send-command`** to the jumpbox. |
| [`ssm-apply-api-deployment-from-helm.py`](dev/ssm-apply-api-deployment-from-helm.py) | Applies a Helm-rendered deployment manifest to EKS by sending it through SSM to the jumpbox, useful when the Jenkins agent has no direct path to the private EKS API. |

---

## `test/`

Interactive / CLI tools to validate AWS access from a **laptop or workstation** (credentials prompts or env). Use **`python3 <script> --help`** for options. For **shell-only** TLS checks to **RDS** / **Redis** ( **`psql`** / **`redis-cli`** ) and **SG traffic-light** steps from the same machine, see **[Laptop / workstation: RDS & ElastiCache](#laptop--workstation-rds--elasticache-us-east-1)** above.

| Script | Purpose |
|--------|--------|
| [`midas-s3-test-bucket-access.py`](test/midas-s3-test-bucket-access.py) | Traffic-light style checks against MIDAS test bucket naming (`midas-<env>-<region>-test-*`). |
| [`midas-secretsmanager-get-secret.py`](test/midas-secretsmanager-get-secret.py) | Fetch / validate Secrets Manager secrets for MIDAS patterns. |
| [`midas-rds-postgres-connect.py`](test/midas-rds-postgres-connect.py) | From your laptop: uses **AWS APIs** + **Secrets Manager** to find the MIDAS RDS instance and master secret, then runs a **`SELECT`** when **TCP :5432** is reachable (often **VPN**, **SSM jump box**, or pod - not a bare corporate laptop without a path). |
| [`midas-elasticache-redis-test-access.py`](test/midas-elasticache-redis-test-access.py) | From your laptop: **DescribeReplicationGroups** for **`midas-<environment>-redis`**; optional **`--redis-ping`** (TLS) when **`ELASTICACHE_REDIS_AUTH_SECRET_ARN`** and network to **:6379** allow. |

---

## `util/`

| Script | Purpose |
|--------|--------|
| [`aws-credentials-setup.sh`](util/aws-credentials-setup.sh) | Writes or updates **`~/.aws/credentials`** for a named profile; supports **`--block`** to paste **`export AWS_...`** lines from stdin. |
| [`validate-aws-cli-identity.py`](util/validate-aws-cli-identity.py) | Verifies **`aws`** is on **`PATH`** and **`sts get-caller-identity`** succeeds (exit codes 0/1/2). |
| [`validate-deploy-role-iam.py`](util/validate-deploy-role-iam.py) | Validates **`deploy/deploy_role/iam-policy/midas-deployer-policy-*`** files (count, JSON, size, unique **`Sid`**); optional **`--aws`** to compare live IAM attachments on **`midas-deployer-role`**. |
| [`aws-sg-check-laptop-access.sh`](util/aws-sg-check-laptop-access.sh) | **Read-only:** traffic-light markdown for **RDS + Redis** security groups vs **`MIDAS_SG_LAPTOP_CIDRS`** (default jump IPs). Uses **`aws`** / **`aws-sg-traffic-checks.py laptop`**. |
| [`aws-sg-check-jenkins-helm-to-eks.sh`](util/aws-sg-check-jenkins-helm-to-eks.sh) | **Read-only:** traffic-light markdown for **EKS cluster SG** - **TCP 443** from **`MIDAS_JENKINS_HELM_CIDR`** (default **`10.90.12.0/22`**). Uses **`aws-sg-traffic-checks.py jenkins-eks`**. |
| [`aws-sg-traffic-checks.py`](util/aws-sg-traffic-checks.py) | Python driver for the two checks above (`laptop` \| `jenkins-eks`); no **boto3**. |
| [`rds-psql-ssl-verify-full.sh`](util/rds-psql-ssl-verify-full.sh) | Downloads the RDS global CA PEM, then runs **`psql`** with **`sslmode=verify-full`** using **`host`=`RDS_NAME`** and **`hostaddr`=`RDS_IP`** (works on older libpq; no **`sslhost`**). **Built-in DEV examples:** **`RDS_NAME=midas.cuzwqoeau6l8.us-east-1.rds.amazonaws.com`**, **`RDS_IP=10.72.134.166`**, port **5432** - see **[example IPs table](#example-hostnames-private-ips-and-cidrs-us-east-1)**. Needs **`curl`**, **`psql`**, **`PGPASSWORD`** (or **`.pgpass`**), and network to the DB. |
| [`elasticache-redis-cli-tls-ping.sh`](util/elasticache-redis-cli-tls-ping.sh) | **`redis-cli --tls`** against ElastiCache Redis (**`REDIS_NAME`** required; optional **`REDIS_IP`** + **`--sni`**, **`REDIS_AUTH`** / **`REDISCLI_AUTH`**). Default port **6379**. No baked-in hostname/IP - use console / Terraform; see **[example IPs table](#example-hostnames-private-ips-and-cidrs-us-east-1)** for ports and CA URL. Default command **`PING`**. Needs **TLS-enabled** **`redis-cli`** (6.2+ for **`--sni`** when using **`REDIS_IP`**). |
| [`sm.py`](util/sm.py) | Secrets Manager helper: fetches, lists, or updates MIDAS secrets by name pattern; wraps **`boto3 secretsmanager`** for interactive use and script chaining. |
| [`aws-ssm-kubectl-proxy.py`](util/aws-ssm-kubectl-proxy.py) | Opens an SSM port-forwarding session to the jumpbox and proxies **`kubectl`** API traffic over it; sets **`KUBECONFIG`** and **`HTTPS_PROXY`** for the current shell session. |
| [`aws-ssm-port-forward-all.py`](util/aws-ssm-port-forward-all.py) | Starts SSM port-forward tunnels for all MIDAS private endpoints (EKS API, RDS, Redis) in a single command; useful for local development without VPN. |
| [`eks-tunnel.sh`](util/eks-tunnel.sh) | Opens an SSM port-forward session to the jumpbox and configures `KUBECONFIG` so local `kubectl` commands reach the private EKS API. Requires `AWS_PROFILE` set and SSM agent on the jumpbox. |

---

## Running from repo root

Examples:

```bash
chmod +x deploy/scripts/ci/docker-build-matrix.sh
IMAGE_TAG=latest ./deploy/scripts/ci/docker-build-matrix.sh

cd deploy && ./scripts/dev/env-protection.sh deploy

python3 deploy/scripts/util/validate-deploy-role-iam.py
python3 deploy/scripts/util/validate-deploy-role-iam.py --aws --role-name midas-deployer-role --account-id YOUR_ACCOUNT_ID
```

Region defaults for MIDAS are **`us-east-1`** unless a script says otherwise.
