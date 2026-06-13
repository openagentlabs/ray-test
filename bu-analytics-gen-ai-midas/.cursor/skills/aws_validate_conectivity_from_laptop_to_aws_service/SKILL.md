---
name: kt-aws-validate-conectivity-from-laptop-to-aws-service
description: >-
  This will validate connectivity from your laptop to the AWS services used in this
  project.
---

# kt_aws_validate_conectivity_from_laptop_to_aws_service - MIDAS AWS access validation (strict workflow)

## When to apply

User invokes **`kt_aws_validate_conectivity_from_laptop_to_aws_service`** (this skill) or needs the laptop-to-AWS connectivity checks below.

Use this skill when validating **temporary (or static) AWS keys** and **MIDAS** reachability to **Elasticache Redis**, **RDS PostgreSQL**, **S3 test bucket**, and **Secrets Manager** from a **local terminal** (repo root: `deploy/scripts/test/…`).

**Region:** MIDAS deploy target is **`us-east-1`** unless the user specifies otherwise; pass `--region us-east-1` where scripts support it and set `AWS_REGION` / `AWS_DEFAULT_REGION` if needed.

## Credentials (assumed, not verified)

The same shell used for the steps below is assumed to already export **`AWS_ACCESS_KEY_ID`**, **`AWS_SECRET_ACCESS_KEY`**, and **`AWS_SESSION_TOKEN`** (for temporary credentials). **Do not** run pre-flight checks, Python one-liners, or gates on whether these variables are set or non-empty. Proceed directly to **W1**.

---

## Mandatory workflow (strict)

**Rules for the agent**

1. Execute **only** in the order **W1 → W2 → W3**. Do **not** merge, skip, or reorder sections.
2. If any **gate** fails, **stop** after documenting the failure; do **not** run later sections until the user fixes the issue and you re-run from the failed section (or from W1 if credentials changed).
3. After **W2**, always produce **W3** in the same response (unless W2 was aborted by a gate).

Copy this checklist and mark each row before moving on:

```text
[ ] W1 - validate-aws-cli-identity.py exit 0
[ ] W2 - All four test scripts executed with results captured
[ ] W3 - Final traffic-light table and overall verdict
```

---

### W1 - AWS CLI installed and credentials valid (STS)

**Goal:** Confirm **AWS CLI** is on `PATH` and **`aws sts get-caller-identity`** succeeds using the current environment (no boto3 required for this step).

**Steps (must all run)**

1. Run from repository root:

   ```bash
   python3 deploy/scripts/util/validate-aws-cli-identity.py
   ```

2. **If exit code is `2`:** AWS CLI is missing. The script prints install hints on stderr; repeat the **macOS / Linux / Windows** guidance from that output (and [AWS CLI install guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)) so the user can install and open a new terminal. **Gate:** Exit W1 only after re-run returns **not** `2`.

3. **If exit code is `1`:** STS failed (expired session, wrong account, network, etc.). Show stderr; suggest refreshing credentials and re-running **W1**. **Gate:** Do not start **W2** until exit code is **0**.

4. **If exit code is `0`:** Record `STS_JSON` / account ARN from stdout for the report. Proceed to **W2**.

---

### W2 - Run MIDAS service test scripts

**Goal:** Run all four scripts and capture **exit code** and **enough output** to judge pass/fail without leaking secrets.

**Preparation**

- Work from **repository root**.
- Set `MIDAS_ENVIRONMENT` or pass `--environment` consistently (e.g. `dev`) across scripts that need it.
- For **traffic-light formatted** stdout, set `TRAFFIC_LIGHT=1` where supported (see below).

**Commands (run all four; order may be sequential)**

1. **ElastiCache Redis**

   ```bash
   TRAFFIC_LIGHT=1 python3 deploy/scripts/test/midas-elasticache-redis-test-access.py --environment "${MIDAS_ENVIRONMENT:-dev}"
   ```

2. **RDS PostgreSQL**

   ```bash
   python3 deploy/scripts/test/midas-rds-postgres-connect.py --environment "${MIDAS_ENVIRONMENT:-dev}"
   ```

   (No `TRAFFIC_LIGHT` flag; infer 🟢 if exit `0` and stderr contains `OK: Connected`, 🔴 if exit non-zero or `FAILED:` in stderr.)

3. **S3 test bucket**

   ```bash
   TRAFFIC_LIGHT=1 python3 deploy/scripts/test/midas-s3-test-bucket-access.py --environment "${MIDAS_ENVIRONMENT:-dev}"
   ```

4. **Secrets Manager**

   ```bash
   python3 deploy/scripts/test/midas-secretsmanager-get-secret.py >/dev/null
   ```

   **Do not** capture or echo stdout (secret value). Use **exit code** and **stderr** only for the report (🟢 exit `0`, 🔴 non-zero with stderr summary).

**Gate:** If a script **cannot** be run (e.g. missing file), stop W2, report 🔴 for that row with reason, still produce **W3** with available results and note what was not run.

---

### W3 - Final traffic-light report

**Goal:** Single markdown report: table rows + short overall verdict.

**Steps (must all run)**

1. Build a **markdown table** with exactly these columns:

   | Column | Content |
   |--------|---------|
   | **Service** | Human-readable name (see row list below) |
   | **Light** | `🟢` or `🟡` or `🔴` |
   | **Feedback** | One or two sentences: exit code, key stderr line, or `VERDICT` line from traffic-light output - **never** paste secret material |

2. **Required rows (in this order):**

   | Service (label) | Source |
   |-----------------|--------|
   | AWS CLI / STS identity | W1 (`validate-aws-cli-identity.py` result) |
   | ElastiCache Redis | W2 script 1 (`VERDICT` under `TRAFFIC_LIGHT=1` or step lines) |
   | RDS PostgreSQL | W2 script 2 |
   | S3 test bucket | W2 script 3 |
   | Secrets Manager | W2 script 4 (stderr + exit only) |

3. **Light mapping (default):**

   - **🟢** - success (exit `0`; for RDS, connected + query path OK; for STS, script exit `0`).
   - **🔴** - failure (non-zero exit, `FAILED`, `Blocked`, or explicit CLI/STS error).
   - **🟡** - partial / warning (e.g. script verdict `Gaps` or step-level 🟡 in traffic-light output).

4. After the table, print an **Overall verdict** line using the same convention as other MIDAS traffic-light summaries, for example:

   - `🟢 Ready` - all rows 🟢  
   - `🟡 Gaps` - any 🟡 and no 🔴  
   - `🔴 Blocked` - any 🔴  

---

## Reference

- Utility script: `deploy/scripts/util/validate-aws-cli-identity.py` (repo root)
- Tests: `deploy/scripts/test/midas-elasticache-redis-test-access.py`, `midas-rds-postgres-connect.py`, `midas-s3-test-bucket-access.py`, `midas-secretsmanager-get-secret.py`
