"""Load per-service `.env.local` for secrets scaffolding (build-time only).

Committed static Kubernetes env lives in `infra/envs/<APP_ENV>/k8s.tfvars`.
Deploy does not rewrite Terraform var files at runtime.
"""

from __future__ import annotations

import re
import secrets
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_K8S_NAMESPACE = "ray-test"
AWS_ENV_FILE = REPO_ROOT / "infra/envs/dev/.env.aws"

WORKLOAD_ENV_SOURCES: dict[str, list[Path]] = {
    "frontend": [
        AWS_ENV_FILE,
        REPO_ROOT / "frontend/.env.local",
        REPO_ROOT / "infra/local-docker-compose/.env.local",
    ],
    "iam_svc": [AWS_ENV_FILE, REPO_ROOT / "iam.svc/server/.env.local"],
    "general_ai_agent": [AWS_ENV_FILE, REPO_ROOT / "general.ai.agent.svc/server/.env.local"],
    "solutions_svc": [AWS_ENV_FILE, REPO_ROOT / "solutions.svc/server/.env.local"],
    "notification_svc": [AWS_ENV_FILE, REPO_ROOT / "notification.svc/server/.env.local"],
    "storage_svc": [AWS_ENV_FILE, REPO_ROOT / "storage.svc/server/.env.local"],
    "collaboration_svc": [
        AWS_ENV_FILE,
        REPO_ROOT / "collaboration.svc/server/.env.local",
    ],
    "document_storage_svc": [
        AWS_ENV_FILE,
        REPO_ROOT / "document-storage.svc/server/.env.local",
    ],
    "arch_diagram_agent_svc": [
        AWS_ENV_FILE,
        REPO_ROOT / "arch.diagram.agent.svc/server/.env.local",
    ],
}

# Keys owned by committed k8s.tfvars — never duplicated into secrets.auto.tfvars.
_STATIC_K8S_KEYS = frozenset(
    {
        "APP_ENV",
        "APP_TARGET",
        "PORT",
        "HOSTNAME",
        "AUTH_TRUST_HOST",
        "FRONTEND_K8S_NAMESPACE",
        "IAM_SERVICE_HOST",
        "IAM_SERVICE_PORT",
        "SOLUTIONS_SERVICE_HOST",
        "SOLUTIONS_SERVICE_PORT",
        "STORAGE_SERVICE_GRPC_HOST",
        "STORAGE_SERVICE_GRPC_PORT",
        "GENERAL_AI_AGENT_GRPC_HOST",
        "GENERAL_AI_AGENT_GRPC_PORT",
        "NOTIFICATION_SERVICE_GRPC_HOST",
        "NOTIFICATION_SERVICE_GRPC_PORT",
        "COLLABORATION_SERVICE_HOST",
        "COLLABORATION_SERVICE_PORT",
        "DOCUMENT_STORAGE_SERVICE_HOST",
        "DOCUMENT_STORAGE_SERVICE_PORT",
        "ARCH_DIAGRAM_AGENT_SERVICE_GRPC_HOST",
        "ARCH_DIAGRAM_AGENT_SERVICE_GRPC_PORT",
        "DOCUMENT_STORAGE_REGISTRY_DYNAMO_TABLE_NAME",
        "DOCUMENT_STORAGE_GROUPS_DYNAMO_TABLE_NAME",
        "DOCUMENT_STORAGE_S3_BUCKET",
        "DOCUMENT_STORAGE_OPENSEARCH_ENDPOINT",
        "ARCH_DIAGRAM_AGENT_CONVERSION_JOBS_DYNAMO_TABLE_NAME",
        "ARCH_DIAGRAM_AGENT_DOCUMENT_STORAGE_ENABLED",
        "ARCH_DIAGRAM_AGENT_DOCUMENT_STORAGE_GRPC_HOST",
        "ARCH_DIAGRAM_AGENT_DOCUMENT_STORAGE_GRPC_PORT",
        "ARCH_DIAGRAM_AGENT_STORAGE_ENABLED",
        "ARCH_DIAGRAM_AGENT_STORAGE_GRPC_HOST",
        "ARCH_DIAGRAM_AGENT_STORAGE_GRPC_PORT",
        "STORAGE_DATABASE_PATH",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_PROFILE",
        "AWS_DEFAULT_PROFILE",
    }
)


def parse_dotenv(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        if key:
            out[key] = value
    return out


def merge_env_files(paths: list[Path]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in paths:
        merged.update(parse_dotenv(path))
    return merged


def filter_secret_env(env: dict[str, str]) -> dict[str, str]:
    """Drop empty values and static keys already in k8s.tfvars."""
    return {
        k: v
        for k, v in env.items()
        if v and k not in _STATIC_K8S_KEYS and not k.startswith("FRONTEND_RUNTIME")
    }


_IAM_BOOTSTRAP_KEYS = (
    "IAM_BOOTSTRAP_FIRST_NAME",
    "IAM_BOOTSTRAP_LAST_NAME",
    "IAM_BOOTSTRAP_EMAIL",
    "IAM_BOOTSTRAP_PASSWORD",
)
_RESET_IAM_KEYS = (
    "RESET_IAM_FIRST_NAME",
    "RESET_IAM_LAST_NAME",
    "RESET_IAM_USERNAME",
    "RESET_IAM_PASSWORD",
)


def _is_valid_bootstrap_email(email: str) -> bool:
    """Reject placeholder access keys and other non-email bootstrap values."""
    normalized = email.strip()
    if not normalized or "@" not in normalized:
        return False
    local, _, domain = normalized.rpartition("@")
    if not local or not domain or "." not in domain:
        return False
    if normalized.startswith("AKIA") or normalized.startswith("ASIA"):
        return False
    return True


def build_secret_workload_environments(
    *,
    region: str = "us-east-1",
) -> dict[str, dict[str, str]]:
    """Secrets + bootstrap keys from `.env.local` for `containers_workload_secret_environment`."""
    result: dict[str, dict[str, str]] = {}
    for workload_key, paths in WORKLOAD_ENV_SOURCES.items():
        raw = merge_env_files(paths)
        env = filter_secret_env(raw)
        if workload_key not in ("iam_svc", "frontend"):
            for key in _IAM_BOOTSTRAP_KEYS:
                env.pop(key, None)
        env.setdefault("AWS_DEFAULT_REGION", region)
        result[workload_key] = env

    # iam.svc/server/.env.local is the single source of truth for bootstrap identity.
    iam = result.get("iam_svc", {})
    frontend = result.setdefault("frontend", {})
    for key in _IAM_BOOTSTRAP_KEYS:
        if iam.get(key):
            frontend[key] = iam[key]

    # Local-only reset credentials must not ship in deploy secrets.
    for workload_env in result.values():
        for key in _RESET_IAM_KEYS:
            workload_env.pop(key, None)
    return result


def ensure_auth_secret(env: dict[str, dict[str, str]]) -> bool:
    frontend = env.setdefault("frontend", {})
    if frontend.get("AUTH_SECRET", "").strip():
        return False
    secret = secrets.token_hex(32)
    compose_env = REPO_ROOT / "infra/local-docker-compose/.env.local"
    line = f"AUTH_SECRET={secret}\n"
    if compose_env.is_file():
        text = compose_env.read_text(encoding="utf-8")
        if "AUTH_SECRET=" in text:
            text = re.sub(
                r"^AUTH_SECRET=.*$",
                line.strip(),
                text,
                flags=re.MULTILINE,
            )
            compose_env.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
        else:
            compose_env.write_text(text.rstrip() + "\n" + line, encoding="utf-8")
    else:
        compose_env.write_text(
            "# Auto-generated — do not commit\n" + line,
            encoding="utf-8",
        )
    frontend["AUTH_SECRET"] = secret
    return True


def validate_secret_workloads(
    env: dict[str, dict[str, str]],
    *,
    app_env: str,
    app_target: str,
) -> list[str]:
    errors: list[str] = []
    frontend = env.get("frontend", {})
    if not frontend.get("AUTH_SECRET", "").strip():
        errors.append(
            "frontend: AUTH_SECRET missing — set in frontend/.env.local or "
            "infra/local-docker-compose/.env.local",
        )
    iam = env.get("iam_svc", {})
    for key in _IAM_BOOTSTRAP_KEYS:
        if not iam.get(key, "").strip():
            errors.append(f"iam_svc: {key} missing in iam.svc/server/.env.local")
            break
    else:
        email = iam.get("IAM_BOOTSTRAP_EMAIL", "").strip()
        if not _is_valid_bootstrap_email(email):
            errors.append(
                "iam_svc: IAM_BOOTSTRAP_EMAIL must be a real email address "
                "(set in iam.svc/server/.env.local; do not use AWS access-key placeholders)",
            )
    fe = env.get("frontend", {})
    for key in _IAM_BOOTSTRAP_KEYS:
        if not fe.get(key, "").strip():
            errors.append(
                f"frontend: {key} missing after iam bootstrap sync — "
                "check iam.svc/server/.env.local",
            )
            break
    if app_target == "aws":
        aws = merge_env_files([AWS_ENV_FILE])
        for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"):
            if not aws.get(key, "").strip():
                errors.append(
                    f"canonical AWS env: {key} missing in "
                    f"{AWS_ENV_FILE.relative_to(REPO_ROOT)} — "
                    "run: python3 make/set-local-aws-credentials.py",
                )
                break
    del app_env  # reserved for future env-specific secret rules
    return errors


def load_secret_workloads(*, region: str = "us-east-1") -> tuple[dict[str, dict[str, str]], bool]:
    env = build_secret_workload_environments(region=region)
    created = ensure_auth_secret(env)
    return env, created
