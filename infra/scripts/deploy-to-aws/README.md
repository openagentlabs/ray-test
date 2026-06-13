# deploy-to-aws

Modern **uv** CLI for deploying ARB workloads to AWS: Terraform apply, Docker build, ECR push, Helm rollout, and frontend validation.

---

## 1. Purpose

End-to-end and post-Terraform AWS deployment for the ARB monorepo. Replaces the legacy `make/build.py` entry point with typed configuration, `returns` `Result` boundaries, and an action-based CLI (same pattern as `tf-tool`).

---

## 2. Prerequisites

| Requirement | Notes |
|-------------|--------|
| Python 3.12+ | Managed by uv |
| uv | `uv sync --dev` in this directory |
| AWS CLI profile `kt-acc` | See `.cursor/rules/constants.mdc` |
| Terraform, Docker, kubectl, helm | Checked in preflight phase |

---

## 3. Quick start

From this directory:

```bash
uv sync --dev
uv run deploy-to-aws-build          # compile with uv; inject build id/date
source output/env.sh                # optional: add launchers to PATH
uv run deploy-to-aws deploy --yes   # full AWS pipeline
uv run deploy-to-aws-clean          # remove output/ and generated artifacts
```

Install launchers to `~/.local/bin`:

```bash
uv run deploy-to-aws-build
uv run deploy-to-aws-install
deploy-to-aws deploy --yes
```

Show injected application metadata:

```bash
uv run deploy-to-aws --version
```

---

## 4. Application identity (`pyproject.toml`)

Edit the **`[project]`** table in **`pyproject.toml`** (single source of truth):

```toml
[project]
name = "deploy-to-aws"
version = "0.1.0"
description = "Modern AWS deployment CLI for ARB infrastructure (Terraform, ECR, Helm)."
requires-python = ">=3.12"
```

On every **build** or **run**, metadata is injected into `src/deploy_to_aws/_injected.py` as static **`BuildInfo`**, then ruff auto-fix/format and validation run:

1. `uv run ruff check --fix .`
2. `uv run ruff format .`
3. `uv run ruff check .`
4. `uv run ruff format --check .`

Injected fields from `[project]`: `name`, `version`, `description`, `requires_python`, plus `build_id` and `build_date`. Ruff output is written under `logging/` (see §5).

Skip ruff gate (debug only): `DEPLOY_TO_AWS_SKIP_BUILD_GATE=1`.

```python
from deploy_to_aws.build_info import BuildInfo

print(BuildInfo.version)
print(BuildInfo.app())
```

**Env overrides (UPPERCASE, win over pyproject):** `DEPLOY_TO_AWS_PROJECT_NAME`, `_VERSION`, `_DESCRIPTION`, `_REQUIRES_PYTHON`.

---

## 5. Logging

**All file logs for this application live only under `logging/`.** Nothing writes log files to `output/`, `dist/`, `build/`, or the repo root.

### Layout

```
logging/
  .gitkeep              # keeps logging/ in git; build output is gitignored
  builds/
    <build_id>/         # UUID injected into BuildInfo.build_id
      ruff.log          # ruff gate (build/run/prepare)
      format.log        # deploy-to-aws-format command
      build.log         # uv build/venv/install failures during compile
```

The `<build_id>` folder name always matches the UUID written into `BuildInfo.build_id` for that run.

### When logs are created

| Trigger | Log file | Created by |
|---------|----------|------------|
| `deploy-to-aws-build`, `deploy-to-aws-run`, or CLI entry (ruff gate) | `logging/builds/<build_id>/ruff.log` | `build/gate.py` via `build/logging_paths.py` |
| `deploy-to-aws-format` | `logging/builds/<build_id>/format.log` | `build/format_code.py` |
| `uv build`, `uv venv`, or `uv pip install` failure during compile | `logging/builds/<build_id>/build.log` | `build/package.py` |

Directories are created automatically (`logging/builds/<build_id>/`); you do not create them manually.

### Gitignore

`logging/builds/` is gitignored (see `.gitignore`). Only the empty `logging/` scaffold is tracked.

---

## 6. Build commands (tf-tool parity)

| Command | What it does |
|---------|----------------|
| `uv sync --dev` | Install dependencies into `.venv` |
| `uv run deploy-to-aws-build` | Inject `[project]` metadata, **ruff gate**, `uv build` → `output/` |
| `uv run deploy-to-aws-format` | Run `ruff check --fix .` then `ruff format .`; log to `logging/` (no wheel build) |
| `uv run deploy-to-aws-run -- …` | Inject metadata, then `uv run deploy-to-aws …` |
| `uv run deploy-to-aws-install` | Symlink `output/bin/*` to `~/.local/bin` |
| `uv run deploy-to-aws-clean` | Remove `output/`, `_injected.py`, caches |
| `uv run deploy-to-aws --version` | Print `BuildInfo.app()` |

| Variable | Purpose |
|----------|---------|
| `DEPLOY_TO_AWS_SKIP_BUILD_GATE` | Skip ruff validation (debug only) |

`output/` layout after build:

```
output/
  bin/          # bash launchers
  venv/         # isolated runtime with wheel installed
  dist/         # wheel + sdist from uv build
  app/          # extracted wheel contents
  env.sh        # export PATH helper
```

---

## 7. Runtime configuration (`app_config.toml`)

PascalCase section keys and property names (KeithTobin / PascalCase style):

```toml
[App]
Env = "dev"

[Aws]
Profile = "kt-acc"
Region = "us-east-1"
AccountId = "017868795096"
```

### Environment overrides (win over TOML)

**Precedence:** defaults → `app_config.toml` → **environment variables**.

Env names are **UPPERCASE** with app prefix `DEPLOY_TO_AWS_`:

| TOML | Environment variable (UPPERCASE) |
|------|----------------------------------|
| `[App] Env` | `DEPLOY_TO_AWS_APP_ENV` |
| `[Aws] Profile` | `DEPLOY_TO_AWS_AWS_PROFILE` |
| `[Deploy] AutoApprove` | `DEPLOY_TO_AWS_DEPLOY_AUTO_APPROVE` |

Example:

```bash
export DEPLOY_TO_AWS_APP_ENV=test
export DEPLOY_TO_AWS_AWS_PROFILE=kt-acc
uv run deploy-to-aws deploy --yes
```

Access in code via the `AppConfig` facade:

```python
config.app.Env
config.aws.Profile
config.deploy.AutoApprove
config.terraform_dir
```

---

## 8. Layout

| Path | Role |
|------|------|
| `pyproject.toml` | Application identity (`[project]`) and ruff/mypy config |
| `app_config.toml` | Runtime deploy configuration (TOML) |
| `logging/` | **Only** location for build/format log files (see §5) |
| `deploy-to-aws.py` | Thin entry shim |
| `src/deploy_to_aws/core/` | Errors, config, subprocess helpers, `Option` / `DeployResult` types |
| `src/deploy_to_aws/deploy/` | Phase functions (`DeployResult`) and pipeline orchestration |
| `src/deploy_to_aws/actions/` | Typer-bound actions registered via `ActionManager` |
| `testing/` | pytest suite |

---

## 9. Deploy commands

| Command | Description |
|---------|-------------|
| `deploy` | Full pipeline: configure → preflight → terraform → build → ECR → Helm → validate |
| `post-deploy` | Skip Terraform; run build/ECR/Helm/validate after prior apply |

Common flags: `--yes`, `--skip-build`, `--skip-preflight`, `--image-tag`, `--no-cache`.

---

## 10. Development

```bash
uv sync --dev
uv run pytest
uv run deploy-to-aws-format
uv run ruff check .
uv run ruff format --check .
```

---

## 12. Related docs

| Topic | Path |
|-------|------|
| Container / EKS deploy overview | `infra/aws/containers/README.md` |
| Terraform root | `infra/aws/aws_tf/` |
| Project constants | `.cursor/rules/constants.mdc` |
| Redeploy after destroy | `infra/aws/aws_tf/REDEPLOY.md` |
