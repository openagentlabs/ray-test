# Work order - Private AWS service connectivity (EKS + data services)

**To:** Core infrastructure / network / cloud platform  
**Region:** `us-east-1` only  
**Account / VPC:** Workload account **`811391286931`**, VPC **`vpc-0c4d673f3e95a93eb`** (MIDAS DEV; adjust if targeting another env).  
**Evidence:** `docs/eks-private-endpoint-check-results.md` (probe from EC2 `i-047d7dcb9806a494c`, 2026-04-05).

---

## Objective

Enable **private-only** access from workload subnets to the AWS APIs and data paths required for **EKS (EC2 + Fargate)**, **RDS PostgreSQL**, **ElastiCache Redis**, **Secrets Manager**, **S3**, and supporting services-without relying on undocumented public egress-while fixing **known TLS/DNS failures** observed in testing.

---

## P0 - Blockers (fix first)

| # | Issue | Ask |
|---|--------|-----|
| 1 | **`eks.us-east-1.api.aws`** and **`eks-auth.us-east-1.api.aws`**: HTTPS **TLS reset** (curl 35) from probe | Confirm **interface VPC endpoints** for **EKS** and **EKS Auth** (or approved path) with **Private DNS**; ensure **no firewall/NACL/proxy** sends **RST** on 443 to these hosts; validate **security groups** on endpoint ENIs allow **443** from **EKS node / Fargate / control-plane** CIDRs. |
| 2 | **`dkr.ecr.us-east-1.amazonaws.com`**: **Certificate SAN mismatch** (curl 60) | Verify traffic hits the **correct ECR DKR** PrivateLink endpoint; rule out **SSL inspection** or **wrong VIP**; align presented cert with hostname. |
| 3 | **`s3-control.us-east-1.amazonaws.com`**: **No DNS answer** | Create **`com.amazonaws.us-east-1.s3control`** **interface** VPC endpoint with **Private DNS** (or fix **Route 53 Resolver** / corporate DNS so the name resolves in-VPC). |

---

## P1 - VPC endpoints and DNS (full private posture)

Deploy **interface** endpoints (subnet groups spanning **≥2 AZs**, **Private DNS = on** where supported) for at least:

`eks`, `eks-auth`, `sts`, `ec2`, `ecr.api`, `ecr.dkr`, `elasticloadbalancing`, `autoscaling`, `kms`, `logs`, `monitoring`, `ssm`, `ssmmessages`, `ec2messages`, `secretsmanager`, `acm`, `rds`, `rds-data` (if Data API used), `elasticache`, `s3control`.

**Gateway endpoint:** `com.amazonaws.us-east-1.s3` - attach to **route tables** for all subnets that need S3 (EKS, nodes, Fargate).

**Endpoint security groups:** Allow **inbound TCP 443** from **workload / EKS / RDS / ElastiCache** subnet CIDRs as appropriate; **no** `0.0.0.0/0`.

---

## P2 - Routing and hybrid DNS

- **TGW / corporate egress:** Confirm routes allow reachability to **endpoint subnets** (not only public internet paths).  
- **Route 53 Resolver:** Rules must not strip or block **`*.api.aws`** / regional AWS names required by EKS.  
- **Split horizon:** If internal DNS overrides AWS public names, ensure they point to **VPC endpoint** addresses, not blackholes.

---

## P3 - Account governance (non-network)

- **SCPs:** Confirm no deny on required APIs (`eks`, `ec2:CreateVpcEndpoint`, `rds`, `elasticache`, `secretsmanager`, `kms`, `ecr`, `s3`, `s3control`, etc.).  
- **IAM:** Service-linked role creation allowed for ELB, ASG, EKS, RDS, ElastiCache as needed.  
- **Quotas:** VPC endpoints per VPC, EKS clusters, etc.-raise if near limits.

*(Application teams still own **EKS cluster roles**, **RDS subnet groups**, **KMS key policies**, **Secrets**, **S3 bucket policies**-see parent doc.)*

---

## Acceptance criteria

1. From a test instance in **workload private subnets** (same path as EKS nodes): **`nslookup`** + **`curl https://<host>/`** succeed for **`eks.us-east-1.api.aws`** and **`eks-auth.us-east-1.api.aws`** (TLS completes; HTTP 4xx acceptable).  
2. **`dkr.ecr.us-east-1.amazonaws.com`**: **curl** completes **without** cert hostname errors (or document corporate CA trust if inspection is mandatory).  
3. **`s3-control.us-east-1.amazonaws.com`** **resolves** and **HTTPS** responds.  
4. **S3 gateway** present and **route tables** associated for subnets that need S3.  
5. **Documentation:** Hand off **endpoint IDs**, **subnet IDs**, **SG rules**, and **DNS** (Private DNS on/off per endpoint) for operations.

---

## References

- Internal: `docs/eks-private-endpoint-check-results.md`  
- AWS: [EKS private clusters](https://docs.aws.amazon.com/eks/latest/userguide/private-clusters.html), [VPC interface endpoints](https://docs.aws.amazon.com/vpc/latest/privatelink/aws-services-in-aws-us-east-1.html)

---

## Request metadata (fill in)

| Field | Value |
|-------|--------|
| Requestor | |
| Target completion | |
| Change window / CAB ticket | |
| Network account contact (if shared VPC) | |
