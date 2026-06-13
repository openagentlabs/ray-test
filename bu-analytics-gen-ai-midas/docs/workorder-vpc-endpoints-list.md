# Work order - VPC endpoints, URLs, and Private DNS (`us-east-1`)

**Region:** `us-east-1` only.  
**Purpose:** Private connectivity for EKS (EC2 + Fargate), ECR, RDS, ElastiCache, Secrets Manager, S3, and related control-plane APIs.

**Private DNS:** For **interface** endpoints, turn **Private DNS** **on** in the VPC endpoint (unless central DNS mirrors these names). Then the **DNS hostnames** below resolve to the **endpoint ENI** IPs inside the VPC. If you use **custom / on-prem DNS**, create **identical** names **pointing to the same endpoint** (or forward to the VPC resolver).

---

## Interface VPC endpoints (`com.amazonaws.us-east-1.*`)

| Service | VPC endpoint service name | HTTPS URL | DNS hostnames to resolve via this endpoint (Private DNS) |
|---------|---------------------------|-----------|----------------------------------------------------------|
| Amazon EKS (API) | `eks` | `https://eks.us-east-1.amazonaws.com` | `eks.us-east-1.amazonaws.com`, `*.eks.us-east-1.amazonaws.com` |
| EKS control plane (`.api.aws`) | `eks` | `https://eks.us-east-1.api.aws` | `eks.us-east-1.api.aws` (confirm with AWS console for your endpoint version) |
| EKS Auth (Pod Identity) | `eks-auth` | `https://eks-auth.us-east-1.api.aws` | `eks-auth.us-east-1.api.aws` |
| AWS STS | `sts` | `https://sts.us-east-1.amazonaws.com` | `sts.us-east-1.amazonaws.com` |
| Amazon EC2 | `ec2` | `https://ec2.us-east-1.amazonaws.com` | `ec2.us-east-1.amazonaws.com` |
| Amazon ECR (API) | `ecr.api` | `https://api.ecr.us-east-1.amazonaws.com` | `api.ecr.us-east-1.amazonaws.com` |
| Amazon ECR (DKR) | `ecr.dkr` | `https://dkr.ecr.us-east-1.amazonaws.com` | `dkr.ecr.us-east-1.amazonaws.com` |
| Elastic Load Balancing | `elasticloadbalancing` | `https://elasticloadbalancing.us-east-1.amazonaws.com` | `elasticloadbalancing.us-east-1.amazonaws.com` |
| Auto Scaling | `autoscaling` | `https://autoscaling.us-east-1.amazonaws.com` | `autoscaling.us-east-1.amazonaws.com` |
| AWS KMS | `kms` | `https://kms.us-east-1.amazonaws.com` | `kms.us-east-1.amazonaws.com` |
| Amazon CloudWatch Logs | `logs` | `https://logs.us-east-1.amazonaws.com` | `logs.us-east-1.amazonaws.com` |
| Amazon CloudWatch (metrics) | `monitoring` | `https://monitoring.us-east-1.amazonaws.com` | `monitoring.us-east-1.amazonaws.com` |
| AWS Systems Manager | `ssm` | `https://ssm.us-east-1.amazonaws.com` | `ssm.us-east-1.amazonaws.com` |
| SSM Messages | `ssmmessages` | `https://ssmmessages.us-east-1.amazonaws.com` | `ssmmessages.us-east-1.amazonaws.com` |
| EC2 Messages | `ec2messages` | `https://ec2messages.us-east-1.amazonaws.com` | `ec2messages.us-east-1.amazonaws.com` |
| Amazon S3 Control | `s3control` | `https://s3-control.us-east-1.amazonaws.com` | `s3-control.us-east-1.amazonaws.com` |
| AWS Secrets Manager | `secretsmanager` | `https://secretsmanager.us-east-1.amazonaws.com` | `secretsmanager.us-east-1.amazonaws.com` |
| AWS Certificate Manager | `acm` | `https://acm.us-east-1.amazonaws.com` | `acm.us-east-1.amazonaws.com` |
| Amazon RDS | `rds` | `https://rds.us-east-1.amazonaws.com` | `rds.us-east-1.amazonaws.com` |
| RDS Data API | `rds-data` | `https://rds-data.us-east-1.amazonaws.com` | `rds-data.us-east-1.amazonaws.com` |
| Amazon ElastiCache | `elasticache` | `https://elasticache.us-east-1.amazonaws.com` | `elasticache.us-east-1.amazonaws.com` |

**Note:** Exact **Private DNS** names shown in the **VPC console** for each created endpoint override generic lists-use the console as source of truth after creation.

---

## Gateway VPC endpoint (S3 - not Private DNS)

| Service | VPC endpoint service name | HTTPS URLs | DNS / traffic pattern |
|---------|---------------------------|------------|-------------------------|
| Amazon S3 | `s3` | `https://s3.us-east-1.amazonaws.com`, `https://<bucket>.s3.us-east-1.amazonaws.com`, `https://<bucket>.s3.dualstack.us-east-1.amazonaws.com` | **No** interface Private DNS. Traffic to these hostnames is **routed** via the **gateway** endpoint using the **prefix list** in the **route table**. Clients still resolve bucket names in **public DNS**; **routing** sends traffic to S3 through the **VPC endpoint**. |

Attach the gateway endpoint to **route tables** for every subnet that must reach S3 without NAT.

---

## Not covered by this table (VPC-internal only)

These use **per-resource** DNS in your VPC, **not** the regional API endpoints above:

- **RDS PostgreSQL:** `*.rds.amazonaws.com` / `*.cluster-*.rds.amazonaws.com` → DB **ENIs** in **DB subnets**
- **ElastiCache Redis:** `*.cache.amazonaws.com` / `*.serverless.*.cache.amazonaws.com` → cluster **ENIs**

---

## Notes

- **TCP 443** from workload subnets to **interface** endpoint ENIs (security groups).  
- Full context: `docs/eks-private-endpoint-check-results.md`.
