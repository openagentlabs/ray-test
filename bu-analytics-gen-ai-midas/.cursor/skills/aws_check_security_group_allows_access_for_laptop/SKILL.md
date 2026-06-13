---
name: kt-aws-check-security-group-allows-access-for-laptop
description: >-
  Read-only AWS CLI check: prints a traffic-light markdown table for whether RDS
  and ElastiCache security groups allow inbound from configured laptop/jump CIDRs.
---

# kt_aws_check_security_group_allows_access_for_laptop

## When to use

The user mentions **`kt_aws_check_security_group_allows_access_for_laptop`**, laptop/jump-host **security group** compliance for **RDS** / **Redis**, or wants a **traffic-light** report without opening the AWS console.

## Credentials (same chain as the rest of MIDAS CLI)

1. From the repository root, use **`deploy/scripts/util/aws-credentials-setup.sh`** to write **`~/.aws/credentials`** (interactive paste or **`--block`** with **`export AWS_…`** lines). Full narrative: **`deploy/README.md`** section **10** (Security group compliance checks).
2. In the same shell (including Cursor’s terminal):

   ```bash
   export AWS_PROFILE=default          # or the profile you configured
   export AWS_REGION=us-east-1         # MIDAS default
   ```

3. Optional: override sources without editing the skill:

   ```bash
   export MIDAS_SG_LAPTOP_CIDRS="10.54.74.117/32,10.54.67.114/32"
   ```

The checker uses **`aws` subprocess calls** only (no boto3). It honors **`AWS_PROFILE`**, **`AWS_REGION`**, and the normal credential provider chain.

## What to run (agent or human)

From the **repository root**:

```bash
./deploy/scripts/util/aws-sg-check-laptop-access.sh
```

Or call the Python entry point directly (same options):

```bash
python3 deploy/scripts/util/aws_sg_traffic_checks.py laptop --help
python3 deploy/scripts/util/aws_sg_traffic_checks.py laptop --region us-east-1 --cidrs "10.54.74.117/32,10.54.67.114/32"
```

## Output (what “good” looks like)

- **Markdown table** to stdout: one row per **(RDS or ElastiCache resource × required CIDR)**.
- **Lights:** 🟢 = a matching **ingress CIDR** on the **union** of that resource’s security groups allows **TCP 5432** (RDS) or **TCP 6379** (Redis), or **all traffic** (`IpProtocol -1`), with the rule’s source CIDR **fully containing** the required network. 🔴 = no such CIDR rule (security-group-only rules do **not** satisfy laptop CIDR checks).
- **Exit code:** `0` if every row is 🟢; `1` if any 🔴; `2` if the AWS CLI is missing or **`aws`** failed (stderr has details).

## Agent workflow

1. Confirm **`aws sts get-caller-identity`** works for the intended account/region (or run after the user refreshes credentials).
2. Run **`./deploy/scripts/util/aws-sg-check-laptop-access.sh`** from repo root.
3. Paste the script’s markdown output into the reply and state the **overall** line (**🟢 OK** vs **🔴 Blocked**).

## Reference

- Script: **`deploy/scripts/util/aws-sg-check-laptop-access.sh`**
- Implementation: **`deploy/scripts/util/aws_sg_traffic_checks.py`** (`laptop` subcommand)
- Credential helper: **`deploy/scripts/util/aws-credentials-setup.sh`**
