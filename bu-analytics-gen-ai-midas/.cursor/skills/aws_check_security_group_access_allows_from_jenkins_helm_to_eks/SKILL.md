---
name: kt-aws-check-security-group-access-allows-from-jenkins-helm-to-eks
description: >-
  Read-only AWS CLI check: traffic-light table for EKS cluster security group
  allowing TCP 443 from the Jenkins/Helm agent CIDR.
---

# kt_aws_check_security_group_access_allows_from_jenkins_helm_to_eks

## When to use

The user mentions **`kt_aws_check_security_group_access_allows_from_jenkins_helm_to_eks`**, **Jenkins** / **Helm** reachability to the **private EKS API**, or wants to confirm **TCP 443** from the corporate **Jenkins CIDR** on the **EKS-created cluster security group**.

## Credentials

Same as other MIDAS AWS CLI helpers:

1. **`deploy/scripts/util/aws-credentials-setup.sh`** → **`~/.aws/credentials`**
2. **`export AWS_PROFILE=…`** and **`export AWS_REGION=us-east-1`** (MIDAS default)

Optional:

```bash
export MIDAS_EKS_CLUSTER_NAME=midas-eks-dev
export MIDAS_JENKINS_HELM_CIDR=10.90.12.0/22
```

## What to run

From the **repository root**:

```bash
./deploy/scripts/util/aws-sg-check-jenkins-helm-to-eks.sh
```

Or:

```bash
python3 deploy/scripts/util/aws_sg_traffic_checks.py jenkins-eks --help
python3 deploy/scripts/util/aws_sg_traffic_checks.py jenkins-eks --cluster midas-eks-dev --jenkins-cidr 10.90.12.0/22
```

## Output

- **Markdown table:** single check row - **EKS cluster security group** (`describe-cluster` → **`clusterSecurityGroupId`**) must allow **TCP 443** from the Jenkins CIDR (rule source CIDR must **fully contain** the required network, same logic as the laptop checker).
- **Lights:** 🟢 = rule found; 🔴 = missing or wrong.
- **Exit code:** `0` = 🟢; `1` = 🔴 or missing cluster SG; `2` = AWS CLI / **`aws`** error.

## Agent workflow

1. Ensure credentials work (**`aws sts get-caller-identity`**).
2. Run **`./deploy/scripts/util/aws-sg-check-jenkins-helm-to-eks.sh`** from repo root.
3. Return the markdown table and overall verdict.

## Reference

- Script: **`deploy/scripts/util/aws-sg-check-jenkins-helm-to-eks.sh`**
- Implementation: **`deploy/scripts/util/aws_sg_traffic_checks.py`** (`jenkins-eks` subcommand)
- Credential helper: **`deploy/scripts/util/aws-credentials-setup.sh`**
