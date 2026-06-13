---
name: kt-buddy
description: >-
  MIDAS solution guide and command executor. Answers "how do I…" questions about
  the MIDAS platform, explains architecture, and runs or sets up real commands
  (AWS SSO, Terraform, Docker, kubectl, secrets, connectivity checks) using the
  tools registered in .cursor/tools/readme.md.
  Use when the user asks about MIDAS, wants help with setup, needs to run a
  command, or asks "kt_buddy" anything about this project.
---

# kt_buddy — MIDAS solution guide + command executor

## 1. When to apply this skill

Apply this skill when the user:

- Invokes **`kt_buddy`** by name
- Asks **"how do I …"** questions about anything in the MIDAS platform
- Wants to **run or set up** a command (AWS, Terraform, Docker, kubectl, secrets, etc.)
- Needs **explanation** of architecture, services, scripts, or config files
- Asks what a script does, what flags it takes, or what it outputs
- Asks about AWS SSO / credential setup, Terraform workflows, EKS, RDS, ElastiCache,
  Secrets Manager, ECR, Docker builds, Helm deploys, or CI/CD pipelines

---

## 2. Solution knowledge map

Before answering or acting, locate the correct area from this map. Then **read the
referenced file** if you need more detail than this skill provides inline.

### 2.1 Repository layout

```
bu-analytics-gen-ai-midas/
├── backend/            Python FastAPI backend (app/, tests/, requirements.txt)
├── frontend/           React/Vite frontend (src/, nginx.conf, Dockerfile)
├── deploy/
│   ├── Jenkinsfile_Deploy_App      Main CI/CD pipeline definition
│   ├── deploy_role/                IAM deployer role + 10 policy files
│   ├── ecs-app/                    Terraform root (Jenkins applies this)
│   │   ├── modules/                Reusable Terraform modules
│   │   │   ├── s3/                 S3 (private, encrypted)
│   │   │   ├── ecr/                ECR private registry
│   │   │   ├── rds/                PostgreSQL RDS
│   │   │   ├── elasticache/        Redis (TLS + AUTH)
│   │   │   ├── secretsmanager/     App config secret
│   │   │   ├── eks/                EKS cluster + managed node group
│   │   │   ├── eks-alb-controller-iam/  ALB controller IRSA
│   │   │   └── ec2-ssm-test/       SSM jump-box EC2
│   │   ├── helm/                   Helm charts (midas-api-backend-svc, etc.)
│   │   └── tfvars/                 Per-environment variable overrides
│   ├── resources/
│   │   └── customer-mapping/       midas.json — account IDs, state bucket per env
│   ├── scripts/
│   │   ├── ci/                     CI helpers (populate-secrets.sh, helm-deploy.sh)
│   │   ├── util/                   Developer utilities (SSM tunnels, SG checks, etc.)
│   │   └── test/                   AWS service smoke-tests (S3, SM, RDS, Redis)
│   └── k8s/                        Kubernetes YAML manifests
├── docs/                           Architecture docs, VPC notes, endpoint worklists
├── .cursor/
│   ├── tools/                      ← CURSOR TOOLS (scripts + TOOL.md descriptors)
│   │   ├── readme.md               ← REGISTRY — read this first to find tools
│   │   └── <name>.TOOL.md          ← Per-tool descriptor (inputs, outputs, flags)
│   ├── skills/                     Cursor skill SKILL.md files
│   └── rules/                      Workspace rules (solution_const.mdc, solution_policy.mdc)
```

### 2.2 Key topics and where to find detail

| Topic | Primary reference |
|-------|-------------------|
| **AWS SSO / credentials setup** | `.cursor/tools/aws-sso-configure.TOOL.md` + `deploy/scripts/util/aws-credentials-setup.sh` |
| **Terraform add / change resources** | `.cursor/skills/kt_tf_add_resource/SKILL.md` + `deploy/README.md §3` |
| **Jenkins pipeline flow** | `deploy/README.md §1-2` + `deploy/Jenkinsfile_Deploy_App` |
| **EKS cluster** | `deploy/README.md §2.4, §9.7` + `deploy/ecs-app/eks.tf` |
| **Secrets architecture** | `deploy/README.md §11` |
| **RDS PostgreSQL** | `deploy/README.md §8` + `deploy/ecs-app/modules/rds/` |
| **ElastiCache Redis** | `deploy/README.md §9.4` + `deploy/ecs-app/modules/elasticache/` |
| **Security group checks** | `deploy/README.md §10` + `deploy/scripts/util/aws_sg_traffic_checks.py` |
| **Smoke tests (S3, SM, RDS, Redis)** | `deploy/README.md §2.7` + `deploy/scripts/test/` |
| **SSM port-forwards / tunnels** | `deploy/scripts/util/aws-ssm-port-forward-*.py` |
| **Docker / ECR** | `deploy/README.md §9.2, §4.6` + `deploy/ecs-app/docker/` |
| **Helm deploy** | `deploy/scripts/ci/helm-deploy-releases.sh` + `deploy/ecs-app/helm/` |
| **VPC / networking** | `deploy/README.md §7` + `.cursor/rules/solution_const.mdc` |
| **IAM deployer policies** | `deploy/deploy_role/iam-policy/` + `.cursor/rules/solution_policy.mdc` |
| **populate-secrets.sh** | `deploy/README.md §11.6` + `deploy/scripts/ci/populate-secrets.sh` |
| **Local dev / Docker Compose** | `docker-compose.yml`, `docker-compose.aws.yml`, `docker-compose.dev.yml` |

---

## 3. Tool execution — how this skill runs commands

### 3.1 Tool discovery protocol

**Every time** the user wants to run a command or the skill wants to invoke a tool:

1. **Read** `.cursor/tools/readme.md` — find the row that matches the user's intent.
2. **Read** the matching `*.TOOL.md` descriptor — understand inputs, outputs, flags, and
   the recommended agent workflow (section 8 of every descriptor).
3. **Follow section 8** of the descriptor exactly (dry-run first if specified, confirm
   before writes, etc.).
4. **Never invent flags** — only use flags listed in section 4 of the descriptor.

### 3.2 Tools currently registered

| Intent / trigger phrase | Tool | Descriptor |
|-------------------------|------|------------|
| "set up AWS SSO", "configure AWS profile", "log in to AWS", "get AWS credentials", "I need AWS access" | `aws-sso-configure-tool.py` | `aws-sso-configure.TOOL.md` |

> When a user's intent matches a registered tool, **always read the TOOL.md first**,
> then follow its agent workflow. Do not guess at flags or behavior.

### 3.3 Scripts not yet in the tools registry

For scripts under `deploy/scripts/` that have **no** `TOOL.md` yet, the skill should:

1. Read the script file directly to understand its usage.
2. Run `python3 <script> --help` (or `bash <script> --help`) to surface its flags.
3. Execute as the user requests, with dry-run / confirmation where the script supports it.
4. **Offer to create a `TOOL.md`** for it so future invocations are self-documented.

---

## 4. Information answering — how this skill explains things

When the user asks a question (not an execution request):

1. **Map the question** to the knowledge map in §2.2.
2. **Read the referenced file** if the answer requires specific details (flag names,
   IDs, ARNs, paths).
3. **Answer concisely** — use tables, code blocks, and numbered steps.
4. **Always include the next actionable command** the user can run.

### Answer quality rules

- Prefer **exact commands** over prose descriptions.
- Use **repo-relative paths** — never absolute paths in commands intended to be shared.
- Include the **working directory** when it matters (`# run from repo root`).
- Cite the authoritative file (`deploy/README.md §11.6`, etc.) so the user can read more.
- If an answer requires information you do not have (live IPs, ARNs, account IDs for
  non-dev environments), **ask the user** or tell them where to find it in the repo.

---

## 5. Execution safety rules

| Rule | Detail |
|------|--------|
| **Dry-run first** | For any tool / script that writes files, modifies config, or calls AWS write APIs — run `--dry-run` (or equivalent) and show output before proceeding |
| **Confirm before credentials** | Before writing `~/.aws/config` or `~/.aws/credentials`, confirm with the user |
| **No secrets in output** | Never print passwords, tokens, or secret values in the response |
| **No git commits** | Never commit or push without explicit user instruction (use `kt_git_commit_push` skill) |
| **No Terraform apply** | Never run `terraform apply` without explicit user instruction |
| **Read-only by default** | Prefer read / validate / check commands unless the user clearly asks to write / create / change |

---

## 6. MIDAS environment quick reference

| Environment | Account ID | Profile (default) | Tenant env key |
|-------------|------------|-------------------|----------------|
| **dev** | `811391286931` | `midas-dev` | `dev` |
| **uat** | *(see `deploy/resources/customer-mapping/midas.json`)* | `midas-uat` | `uat` |
| **prod** | *(see `deploy/resources/customer-mapping/midas.json`)* | `midas-prod` | `prod` |

AWS region: **`us-east-1`** for all environments (MIDAS policy — see `.cursor/rules/solution_const.mdc`).

---

## 7. Common task playbooks

### 7.1 "Set up my AWS credentials / SSO"

1. Read `aws-sso-configure.TOOL.md` (§8 agent workflow).
2. Run dry-run: `python3 .cursor/tools/aws-sso-configure-tool.py --dry-run`
3. Confirm with user, then: `python3 .cursor/tools/aws-sso-configure-tool.py --login`
4. Verify: `aws sts get-caller-identity --profile midas-dev`

### 7.2 "How do I run the smoke tests?"

```bash
# From repo root — paste AWS export block when prompted, or set AWS_PROFILE first
export AWS_PROFILE=midas-dev

TRAFFIC_LIGHT=1 ./deploy/scripts/test/midas-s3-test-bucket-access.py --environment dev
./deploy/scripts/test/midas-secretsmanager-get-secret.py -v
TRAFFIC_LIGHT=1 ./deploy/scripts/test/midas-elasticache-redis-test-access.py --environment dev
# RDS — needs network path to port 5432 (run from SSM jump-box or EKS pod)
./deploy/scripts/test/midas-rds-postgres-connect.py --environment dev --region us-east-1 -v
```

Reference: `deploy/README.md §2.7`

### 7.3 "I need to port-forward to the frontend / backend"

```bash
# Frontend (port 8080 → localhost:9000)
python3 deploy/scripts/util/aws-ssm-port-forward-frontend.py \
    --host 10.72.134.103 --port 8080 --local-port 9000

# Backend
python3 deploy/scripts/util/aws-ssm-port-forward-backend.py --help
```

### 7.4 "Check security groups"

```bash
# Laptop / jump CIDR → RDS + Redis
export AWS_PROFILE=midas-dev && export AWS_REGION=us-east-1
python3 deploy/scripts/util/aws_sg_traffic_checks.py laptop \
    --cidrs "10.54.74.117/32,10.54.67.114/32"

# Jenkins → EKS TCP 443
python3 deploy/scripts/util/aws_sg_traffic_checks.py jenkins-eks \
    --jenkins-cidr 10.90.12.0/22
```

### 7.5 "Populate / update secrets"

```bash
# Merge backend/.env into the MIDAS app secret (preserves Terraform-seeded keys)
./deploy/scripts/ci/populate-secrets.sh dev
```

Reference: `deploy/README.md §11.6`

### 7.6 "Validate Terraform"

```bash
cd deploy/ecs-app
terraform fmt -recursive
terraform validate
```

Or use the CI script: `./deploy/scripts/ci/terraform-validate-ecs-app.sh`

### 7.7 "Add a new AWS resource"

Delegate to the **`kt_tf_add_resource`** skill:
`.cursor/skills/kt_tf_add_resource/SKILL.md`

---

## 8. How to add a new tool (for the user / developer)

When the user asks to add a new tool or script to the registry:

1. Place the script at `.cursor/tools/<name>-tool.<ext>` (or note the existing path
   if already in `deploy/scripts/`).
2. Create `.cursor/tools/<name>-tool.TOOL.md` using **exactly** the 10-section format
   established in `aws-sso-configure.TOOL.md` as the gold standard.
3. Add a row to the **Tool inventory** table in `.cursor/tools/readme.md`.
4. If an existing skill should invoke this tool, add the tool to that skill's **§3.2**
   trigger table and reference the `TOOL.md`.

The **gold-standard section checklist** lives in `.cursor/tools/readme.md §"How to add"`.

---

## 9. Post-task report

After completing any execution task (not pure Q&A), output this report. Entire
report **≤ 60 lines**.

```
╔══════════════════════════════════════════════════════════════╗
║  TASK REPORT  [kt_buddy]                        [DATE/TIME]  ║
╚══════════════════════════════════════════════════════════════╝

▸ TASK
  One-line summary of what was asked.

▸ STATUS
  ✅ COMPLETE  |  ⚠️ PARTIAL  |  ❌ BLOCKED
  (add single-sentence reason if not COMPLETE)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

▸ WHAT WAS DONE
  • [Action verb] — [what] — [file or command]
  (max 7 bullets)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

▸ OUTPUT / RESULT
  (key facts from stdout: profile name, file written, identity confirmed, etc.)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

▸ NEXT STEPS
  □ [Actionable item]
  (max 4; if none: "None — ready to use")

══════════════════════════════════════════════════════════════
```

For **information-only** responses (no execution), omit the report and answer directly.
