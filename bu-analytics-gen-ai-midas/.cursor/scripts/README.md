# `.cursor/scripts`

Small **operator / agent helpers** for MIDAS Jenkins and EKS validation. They are **not** invoked by **`deploy/Jenkinsfile_Deploy_App`** unless you wire them yourself. For pipeline and repo automation scripts (**`ci/`**, **`dev/`**, **`test/`**, **`util/`**), see **[`deploy/scripts/README.md`](../../deploy/scripts/README.md)**.

See also: **[Solution documentation index](../../README.midas.md)** · **`.cursor/rules/scripts_docs.mdc`**

| File | Purpose |
|------|--------|
| [`pre-deploy-validate-eks.sh`](pre-deploy-validate-eks.sh) | Pre-deploy checks: caller identity, VPC, subnets, AZ spread (see [pre-deploy-eks-validation.md](../validation/pre-deploy-eks-validation.md)). |
| [`post-deploy-validate-eks.sh`](post-deploy-validate-eks.sh) | Post-deploy: EKS cluster/node group status, optional wait for nodes Ready, optional SSM kubelet logs. |
| [`jenkins_tools.py`](../tools/jenkins_tools.py) | Jenkins CLI (api4jenkins): status, logs, stages, approve, trigger, abort, queue, list-jobs, artifacts, nodes, plugins, whoami, server-info, build-history, test-results, enable, disable, set-env. |
| [`requirements-jenkins-cli.txt`](requirements-jenkins-cli.txt) | Python deps for **`jenkins_tools.py`** (`api4jenkins>=2.1.0`). |
| [`jp-commit-push`](jp-commit-push) | Git helper: safe pull → stage → commit → push for the current branch. |

---

## `pre-deploy-validate-eks.sh`

Runs AWS CLI checks before applying EKS-related Terraform: identity, VPC, subnet IDs, and that subnets span at least two AZs. Aligns with **`.cursor/validation/pre-deploy-eks-validation.md`**.

**Prerequisites:** AWS CLI v2, credentials that can describe EC2/VPC in **`us-east-1`**.

**Usage:**

```bash
export AWS_REGION=us-east-1
export EKS_VPC_ID=vpc-xxxxxxxx
export EKS_CLUSTER_SUBNET_IDS="subnet-aaa,subnet-bbb"
chmod +x .cursor/scripts/pre-deploy-validate-eks.sh
./.cursor/scripts/pre-deploy-validate-eks.sh
```

Defaults in the script match MIDAS DEV snapshot IDs if env vars are unset; override for your environment.

---

## `post-deploy-validate-eks.sh`

After deploy, verifies cluster and managed node group in AWS, runs **`kubectl get nodes`** after **`aws eks update-kubeconfig`** (waits up to **`WAIT_MINUTES`** for Ready nodes). Optional **`SSM_INSTANCE_IDS`** for kubelet logs via SSM.

**Prerequisites:** AWS CLI, network path to the **private** EKS API if applicable; **`kubectl`** optional for node checks.

**Usage:**

```bash
export AWS_REGION=us-east-1
export CLUSTER_NAME=midas-eks-dev
export WAIT_MINUTES=25
# optional: export SSM_INSTANCE_IDS="i-abc,i-def"
chmod +x .cursor/scripts/post-deploy-validate-eks.sh
./.cursor/scripts/post-deploy-validate-eks.sh
```

---

## `jenkins_tools.py`

Full-featured Jenkins CLI using **[api4jenkins](https://api4jenkins.readthedocs.io/en/stable/)** — the gold standard Python Jenkins client (sync + async, object-oriented, covers every Jenkins item type).

Targets the MIDAS nested pipeline job **`bu-analytics-gen-ai-midas-deploy-eks`** by default; override with `--job`.

**Prerequisites:** Python 3.9+, `api4jenkins>=2.1.0` (see `requirements-jenkins-cli.txt`).

**Install:**

```bash
python3 -m pip install -r .cursor/scripts/requirements-jenkins-cli.txt
```

**Authentication — environment variables (recommended):**

```bash
export JENKINS_USER="your.name"
export JENKINS_API_TOKEN="your-jenkins-api-token"
# API token: Jenkins UI → User → Configure → API Token → Add new Token
```

**Save credentials permanently (one-time setup):**

```bash
python3 .cursor/tools/jenkins_tools.py set-env \
    --user your.name \
    --api-token your-jenkins-api-token
source ~/.zshrc   # or open a new terminal
```

**All commands:**

| Command | Description |
|---------|-------------|
| `set-env` | Persist `JENKINS_USER` / `JENKINS_API_TOKEN` to your shell RC file |
| `whoami` | Print authenticated Jenkins user |
| `server-info` | Jenkins version, executor count, mode |
| `list-jobs` | List jobs/folders at a path (`--path`, `--depth`) |
| `status` | Build status (`--build N`) |
| `build-history` | Recent builds with result and timestamp (`--count N`) |
| `logs` | Console log (`--tail N`, `--follow`) |
| `stages` | Pipeline stage tree + pending input hints |
| `parameters` | Job parameter definitions |
| `trigger` | Trigger new build (`--param KEY=VALUE`, `--wait`, `--timeout`) |
| `abort` | Stop the running build |
| `approve` | Submit (or `--abort-input`) a pending pipeline input step |
| `queue` | List Jenkins build queue |
| `artifacts` | List and optionally download artifacts (`--download-dir`) |
| `enable` | Enable the job |
| `disable` | Disable the job |
| `nodes` | Jenkins agents with online/offline status |
| `plugins` | Installed plugins (`--updates-only`) |
| `test-results` | Test report summary for a build |

**Global flags:** `--user`, `--api-token`, `--url`, `--job`, `--build N`, `--json` (machine-readable output), `--help`, `--help-ai` (JSON schema for AI agents).

**Quick examples:**

```bash
python3 .cursor/tools/jenkins_tools.py status
python3 .cursor/tools/jenkins_tools.py logs --tail 200
python3 .cursor/tools/jenkins_tools.py logs --follow
python3 .cursor/tools/jenkins_tools.py stages
python3 .cursor/tools/jenkins_tools.py approve
python3 .cursor/tools/jenkins_tools.py trigger --param ENVIRONMENT=dev --wait
python3 .cursor/tools/jenkins_tools.py build-history --count 10
python3 .cursor/tools/jenkins_tools.py queue --json
python3 .cursor/tools/jenkins_tools.py --help-ai   # AI agent JSON schema
```

**Passing credentials as flags** (if env vars are not set):

```bash
python3 .cursor/tools/jenkins_tools.py \
    --user your.name \
    --api-token your-jenkins-api-token \
    status
```

---

## `requirements-jenkins-cli.txt`

Pins **`api4jenkins>=2.1.0`** for **`jenkins_tools.py`**. Install with `pip install -r requirements-jenkins-cli.txt` (ideally in a venv).

---

## `jp-commit-push`

“Gold standard” helper to **pull first**, then **stage**, **commit**, and **push** your current branch using safe defaults:

- Stops on any `git pull` error or merge conflict (prints a small conflict table).
- Never force-pushes, never amends, never bypasses hooks.

**Usage:**

```bash
chmod +x .cursor/scripts/jp-commit-push

# stage everything
./.cursor/scripts/jp-commit-push --all

# stage only specific paths
./.cursor/scripts/jp-commit-push --paths docs/ deploy/ --subject "docs: update runbook"
```
