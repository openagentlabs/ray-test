# kt_check_endpoint_for_eks_node_attach - EKS endpoint & DNS validation (SSM probe)

This document describes the **Cursor skill** used to validate **AWS regional endpoints** from a **VPC-attached EC2 instance** before or alongside **EKS** (EC2 nodes or Fargate) in a **private** network design. It is a human-readable summary; the canonical skill text lives in the repo under **`.cursor/skills/`**.

---

## What it is for

- **Prove** that **DNS** and **HTTPS** to required **regional service hostnames** work from the **same network path** as future nodes (typically an EC2 “probe” in private subnets).
- **Does not require an EKS cluster** - no `aws eks describe-cluster` and no per-cluster Kubernetes API URL unless you explicitly add that later.
- **Default region:** **`us-east-1`** (aligns with MIDAS deploy conventions in this repo).

---

## Where the skill lives

| Item | Path |
|------|------|
| Skill definition | [`.cursor/skills/kt_check_endpoint_for_eks_node_attach/SKILL.md`](../.cursor/skills/kt_check_endpoint_for_eks_node_attach/SKILL.md) |
| Aliases | `kt_check_endpoint_for_eks_node_attach`, `kt-check-endpoint-for-eks-node-attach` |

Invoke the skill in Cursor when you want this workflow; the agent follows the skill’s rules (confirm probe instance, read-only checks, report format).

---

## Probe scripts (this repo)

| Script | Purpose |
|--------|---------|
| [`deploy/scripts/eks-ssm-endpoint-check.sh`](../deploy/scripts/eks-ssm-endpoint-check.sh) | **Core 11** regional hosts (`eks`, `eks` `.api.aws`, `eks-auth`, `sts`, `ec2`, ECR API/DKR, `s3`, ELB, `logs`, `ssm`). |
| [`deploy/scripts/eks-private-endpoints-probe.sh`](../deploy/scripts/eks-private-endpoints-probe.sh) | **Core 11 first**, then extended services (ASG, KMS, monitoring, SSM messages, `s3-control`, Secrets Manager, ACM, RDS, ElastiCache, etc.). |
| [`deploy/scripts/eks_probe_to_traffic_light.py`](../deploy/scripts/eks_probe_to_traffic_light.py) | Parses raw `nslookup`/`curl` output into the **traffic-light report** format. |

**Run from a machine with AWS CLI credentials** that can call **`ssm:SendCommand`** on the probe instance. **Session Manager plugin** is optional if you use **SendCommand** (`AWS-RunShellScript`).

**Traffic-light report (skill format):**

```bash
TRAFFIC_LIGHT=1 REGION=us-east-1 INSTANCE_ID=i-xxxxxxxxxxxxxxxxx \
  ./deploy/scripts/eks-ssm-endpoint-check.sh
```

Requires **Python 3** on the workstation for `TRAFFIC_LIGHT=1`.

---

## Default probe instance

The skill suggests confirming **`i-047d7dcb9806a494c`** as the SSM probe **only**-always **confirm with the user** before running SSM against any instance.

---

## Traffic-light meaning (summary)

| | DNS | HTTPS |
|---|-----|--------|
| **Green** | Answers point to **private (RFC1918)** addresses when the goal is **VPC interface endpoints** / PrivateLink. | **TLS completes**; HTTP **403/404/3xx/400** from AWS still counts as OK for connectivity. |
| **Amber** | **Public** (or mixed) answers when you expected **private** only; or **S3** public DNS with **gateway** routing (often acceptable). | **Certificate** issues (e.g. `curl 60`), or TLS inspection edge cases. |
| **Red** | **NXDOMAIN**, **no answer**, or unusable resolution. | **Timeout**, **reset**, **no TLS** (`http_code=000` with failure). |

Full rules and the **exact report template** are in the skill file.

---

## Related documentation in `docs/`

| Doc | Topic |
|-----|--------|
| [`eks-private-endpoint-check-results.md`](eks-private-endpoint-check-results.md) | Example probe results, remediation tables, **account-level** requirements beyond VPC endpoints. |
| [`workorder-vpc-endpoints-list.md`](workorder-vpc-endpoints-list.md) | VPC endpoint service names, URLs, and **Private DNS** hostnames for infra handoff. |
| [`core-infrastructure-workorder-private-aws-services.md`](core-infrastructure-workorder-private-aws-services.md) | Work order for core networking / platform teams. |

---

## AWS references

- [Amazon EKS private clusters](https://docs.aws.amazon.com/eks/latest/userguide/private-clusters.html)  
- [Access Amazon EKS using AWS PrivateLink](https://docs.aws.amazon.com/eks/latest/userguide/vpc-interface-endpoints.html)

---

## Security

- Do **not** commit **AWS access keys** or **session tokens** into the repo or docs.  
- Probes are **read-only** (DNS + HTTPS checks only); they do not change VPC endpoints or IAM unless you explicitly run something else.
