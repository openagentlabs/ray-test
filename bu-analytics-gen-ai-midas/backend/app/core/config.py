import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Optional

from dotenv import load_dotenv
from pathlib import Path
import litellm

# Always drop unsupported LLM params instead of sending them to provider
litellm.drop_params = True

# Disable TLS certificate verification when a self-signed / internal CA reverse
# proxy is in use.  Set LITELLM_SSL_VERIFY=false in .env to enable this.
# Default is True (verify); only disable in controlled environments.
if os.getenv("LITELLM_SSL_VERIFY", "true").strip().lower() in {"0", "false", "no", "off"}:
    litellm.ssl_verify = False

# Trust HTTPS_PROXY / HTTP_PROXY / NO_PROXY environment variables for both the
# httpx and aiohttp transport paths used by litellm.  Required when the pod runs
# inside a network-restricted VPC that needs a corporate proxy to reach external
# endpoints (e.g. Azure OpenAI).  Set LITELLM_TRUST_ENV=false to opt out.
if os.getenv("LITELLM_TRUST_ENV", "true").strip().lower() not in {"0", "false", "no", "off"}:
    litellm.aiohttp_trust_env = True

DEFAULT_CHAT_MODEL = "gpt-5.4-nano"
DEFAULT_KG_MODEL = "gpt-4.1-mini"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"


def _find_dotenv() -> Optional[Path]:
    """Search for a .env file starting from cwd and walking up to this package root."""
    base_search_paths = [Path.cwd()]
    base_search_paths.extend(Path(__file__).resolve().parents)
    seen = set()
    for candidate in base_search_paths:
        if candidate in seen:
            continue
        seen.add(candidate)
        env_file = candidate / ".env"
        if env_file.is_file():
            return env_file
    return None


# Try to load .env file, but handle errors gracefully
try:
    env_file = _find_dotenv()
    if env_file:
        load_dotenv(env_file)
    else:
        print("Warning: .env file not found. Using default configuration.")
        print("Create a .env file with your Azure OpenAI credentials to enable full functionality.")
except Exception as e:
    print(f"Warning: Error loading .env file: {e}")
    print("Using default configuration. Create a .env file with your provider credentials.")


# ---------------------------------------------------------------------------
# AI Gateway toggle
#
# When ``LLM_USE_GATEWAY`` is truthy (and the URL + virtual key are present),
# every LiteLLM call is routed through the Exlerate AI Gateway using a single
# OpenAI-compatible endpoint. The per-call model id is resolved from
# ``llm_model_mapping.json`` via the ``gateway_model_id`` field. When false,
# the existing direct-provider path (Azure / Bedrock / etc.) is used unchanged.
# ---------------------------------------------------------------------------
_LLM_USE_GATEWAY_RAW = os.getenv("LLM_USE_GATEWAY")
LLM_USE_GATEWAY: bool = (
    str(_LLM_USE_GATEWAY_RAW).strip().lower() in {"1", "true", "yes", "on"}
    if _LLM_USE_GATEWAY_RAW is not None and str(_LLM_USE_GATEWAY_RAW).strip()
    else False
)


def _env_clean(key: str) -> Optional[str]:
    raw = os.getenv(key)
    if raw is None:
        return None
    cleaned = raw.strip()
    if len(cleaned) >= 2 and cleaned[0] in {"'", '"'} and cleaned[-1] == cleaned[0]:
        cleaned = cleaned[1:-1]
    return cleaned or None


LLM_GATEWAY_URL: Optional[str] = _env_clean("LLM_GATEWAY_URL")
LLM_GATEWAY_VIRTUAL_KEY: Optional[str] = _env_clean("LLM_GATEWAY_VIRTUAL_KEY")


def gateway_enabled() -> bool:
    """Return True only when the gateway flag is on and credentials are present."""
    return bool(LLM_USE_GATEWAY and LLM_GATEWAY_URL and LLM_GATEWAY_VIRTUAL_KEY)


def _clean_env_value(value: str) -> str:
    cleaned = value.strip()
    if len(cleaned) >= 2 and cleaned[0] in {"'", '"'} and cleaned[-1] == cleaned[0]:
        cleaned = cleaned[1:-1]
    return cleaned


def _optional_env_str(key: str) -> Optional[str]:
    """Read optional string from environment (via ``.env``); empty or whitespace → ``None``."""
    raw = os.getenv(key)
    if raw is None:
        return None
    cleaned = _clean_env_value(raw)
    return cleaned if cleaned else None


def _env_bool(key: str, *, default: bool) -> bool:
    """Read boolean from environment; empty → ``default``. Accepts true/false, 1/0, yes/no, on/off."""
    raw = os.getenv(key)
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _collect_env_vars(prefixes: Iterable[str]) -> Dict[str, str]:
    vars_map: Dict[str, str] = {}
    seen_keys: set[str] = set()
    for prefix in prefixes:
        normalized_prefix = prefix.strip().upper()
        if not normalized_prefix:
            continue
        marker = normalized_prefix + "_"
        allow_nested = "_" in normalized_prefix

        for key, value in os.environ.items():
            key_upper = key.upper()
            if key_upper in seen_keys:
                continue
            if not key_upper.startswith(marker):
                continue

            suffix = key_upper[len(marker):]
            if not allow_nested and "_" in suffix:
                # treat nested names (e.g., LLM_EMBEDDING_MODEL) as belonging to
                # more specific prefixes rather than the general prefix
                continue

            cleaned_value = _clean_env_value(value)
            if not cleaned_value:
                continue

            vars_map[suffix] = cleaned_value
            seen_keys.add(key_upper)
    return vars_map


def _parse_env_value(value: str) -> Any:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def _normalize_bedrock_model(provider: str, model: Optional[str]) -> Optional[str]:
    if not model:
        return model
    if provider.lower() != "bedrock":
        return model
    cleaned = model.strip()
    if not cleaned:
        return cleaned
    if cleaned.startswith("bedrock/"):
        return cleaned
    if cleaned.startswith("converse/"):
        return f"bedrock/{cleaned}"
    return f"bedrock/{cleaned}"


def env_override_present(usage_type: str) -> bool:
    usage_key = usage_type.strip().lower()
    if usage_key in {"chat", "llm_chat"}:
        prefix = "LLM_CHAT"
    elif usage_key in {"knowledge_graph", "kg", "llm_kg"}:
        prefix = "LLM_KG"
    elif usage_key in {"embedding", "llm_embedding"}:
        prefix = "LLM_EMBEDDING"
    else:
        return False

    override_keys = [
        f"{prefix}_MODEL",
        f"{prefix}_PROVIDER",
        f"{prefix}_API_BASE",
        f"{prefix}_API_VERSION",
        f"{prefix}_CUSTOM_PROVIDER",
    ]
    return any(os.getenv(key) for key in override_keys)


@dataclass
class LitellmUsageConfig:
    name: str
    provider: str
    model: str
    custom_provider: Optional[str]
    api_base: Optional[str]
    api_key: Optional[str]
    api_version: Optional[str]
    defaults: Dict[str, Any]

    @classmethod
    def from_mapping(
        cls,
        name: str,
        usage_type: str,
        model_id: str,
        mapping: Dict[str, Any],
        model_normalizer: Optional[Callable[[str, Optional[str]], Optional[str]]] = None,
    ) -> "LitellmUsageConfig":
        provider = (mapping.get("provider") or "openai").strip()
        model = mapping.get("model") or model_id
        api_base = mapping.get("api_base")
        api_version = mapping.get("api_version")

        defaults = {}
        for key, value in mapping.items():
            if key in {"provider", "model", "api_base", "api_version", "gateway_model_id"}:
                continue
            defaults[key] = _parse_env_value(str(value)) if value is not None else value

        api_key = None
        usage_key = usage_type.strip().lower()
        if provider in {"azure", "azure_ai", "azure/gpt5_series"}:
            if usage_key == "chat":
                api_key = os.getenv("LLM_CHAT_API_KEY")
            elif usage_key == "knowledge_graph":
                api_key = os.getenv("LLM_KG_API_KEY")
            elif usage_key == "embedding":
                api_key = os.getenv("LLM_EMBEDDING_API_KEY")

        normalized_model = model
        if model_normalizer:
            normalized_model = model_normalizer(provider, model)

        effective_provider = provider.lower()
        custom_provider = effective_provider

        if effective_provider == "bedrock":
            api_base = None
            api_key = None
            api_version = None

        cfg = cls(
            name=name,
            provider=effective_provider,
            model=normalized_model,
            custom_provider=custom_provider,
            api_base=api_base,
            api_key=api_key,
            api_version=api_version,
            defaults=defaults,
        )

        gateway_model_id = mapping.get("gateway_model_id")
        if gateway_enabled() and gateway_model_id:
            cfg.apply_gateway(LLM_GATEWAY_URL, LLM_GATEWAY_VIRTUAL_KEY, str(gateway_model_id))

        return cfg

    @classmethod
    def from_env(
        cls,
        name: str,
        prefixes: Iterable[str],
        default_provider: str,
        default_model: str,
        fallback_map: Optional[Dict[str, Optional[str]]] = None,
        model_normalizer: Optional[Callable[[str, Optional[str]], Optional[str]]] = None,
    ) -> "LitellmUsageConfig":
        env_vars = _collect_env_vars(prefixes)
        provider = env_vars.pop("PROVIDER", None) or default_provider or "openai"
        provider = provider.lower()

        model = env_vars.pop("MODEL", None)
        if not model and fallback_map:
            model = fallback_map.get("model")
        if not model:
            model = default_model

        custom_provider = env_vars.pop("CUSTOM_PROVIDER", None)
        custom_provider = custom_provider or provider
        api_base = env_vars.pop("API_BASE", None)
        api_key = env_vars.pop("API_KEY", None)
        api_version = env_vars.pop("API_VERSION", None)
        gateway_model_id_env = env_vars.pop("GATEWAY_MODEL_ID", None)

        if fallback_map:
            api_base = api_base or fallback_map.get("api_base")
            api_key = api_key or fallback_map.get("api_key")
            api_version = api_version or fallback_map.get("api_version")
            if not model and fallback_map.get("model"):
                model = fallback_map.get("model")  # type: ignore

        cleaned_defaults = {
            key.lower(): _parse_env_value(value)
            for key, value in env_vars.items()
            if value is not None
        }

        normalized_model = model
        if model_normalizer:
            normalized_model = model_normalizer(provider, model)

        effective_provider = provider
        if provider == "azure":
            lower_model = (normalized_model or "").lower()
            if lower_model.startswith("bedrock/"):
                effective_provider = "bedrock"
                custom_provider = "bedrock"

        if effective_provider == "bedrock":
            api_base = None
            api_key = None
            api_version = None

        cfg = cls(
            name=name,
            provider=effective_provider,
            model=normalized_model,
            custom_provider=custom_provider.lower() if custom_provider else None,
            api_base=api_base,
            api_key=api_key,
            api_version=api_version,
            defaults=cleaned_defaults,
        )

        if gateway_enabled() and gateway_model_id_env:
            cfg.apply_gateway(LLM_GATEWAY_URL, LLM_GATEWAY_VIRTUAL_KEY, str(gateway_model_id_env))

        return cfg

    def apply_gateway(
        self,
        gateway_url: str,
        virtual_key: str,
        gateway_model_id: str,
    ) -> "LitellmUsageConfig":
        """Rewrite this config to point at the Exlerate AI Gateway.

        All traffic goes through a single OpenAI-compatible endpoint; provider
        specifics (Azure api_base/version, Bedrock creds) become irrelevant.
        """
        self.provider = "openai"
        self.custom_provider = "openai"
        self.model = f"openai/{gateway_model_id}"
        self.api_base = f"{gateway_url.rstrip('/')}/v1"
        self.api_key = virtual_key
        self.api_version = None
        return self

    def build_request_kwargs(self) -> Dict[str, Any]:
        base = {
            "model": self.model,
            "custom_llm_provider": self.custom_provider,
            "api_base": self.api_base,
            "api_key": self.api_key,
            "api_version": self.api_version,
        }
        cleaned_base = {k: v for k, v in base.items() if v}

        extra_defaults = {
            k: v
            for k, v in self.defaults.items()
            if k not in {"model", "custom_llm_provider", "api_base", "api_key", "api_version"}
        }
        cleaned_base.update(extra_defaults)

        if self.provider == "bedrock" and not gateway_enabled():
            if os.getenv("AWS_ACCESS_KEY_ID"):
                cleaned_base["aws_access_key_id"] = os.environ["AWS_ACCESS_KEY_ID"]
            if os.getenv("AWS_SECRET_ACCESS_KEY"):
                cleaned_base["aws_secret_access_key"] = os.environ["AWS_SECRET_ACCESS_KEY"]
            if os.getenv("AWS_SESSION_TOKEN"):
                cleaned_base["aws_session_token"] = os.environ["AWS_SESSION_TOKEN"]
            if os.getenv("AWS_REGION_NAME"):
                cleaned_base["aws_region_name"] = os.environ["AWS_REGION_NAME"]

        return cleaned_base

    def is_ready(self) -> bool:
        return bool(self.model)


@dataclass
class AwsCredentials:
    access_key: Optional[str]
    secret_key: Optional[str]
    session_token: Optional[str]
    region: Optional[str]

    @classmethod
    def load(
        cls,
        prefix: str,
        fallback: Optional[Dict[str, Optional[str]]] = None,
    ) -> "AwsCredentials":
        def _env(key: str, fallback_key: str) -> Optional[str]:
            val = os.getenv(f"{prefix}_{key}", None)
            if val:
                return _clean_env_value(val)
            if fallback and fallback_key in fallback:
                return fallback[fallback_key]
            return None

        return cls(
            access_key=_env("ACCESS_KEY_ID", "access_key"),
            secret_key=_env("SECRET_ACCESS_KEY", "secret_key"),
            session_token=_env("SESSION_TOKEN", "session_token"),
            region=_env("REGION", "region"),
        )

    def apply_to_env(self) -> None:
        if self.access_key:
            os.environ["AWS_ACCESS_KEY_ID"] = self.access_key
        if self.secret_key:
            os.environ["AWS_SECRET_ACCESS_KEY"] = self.secret_key
        if self.session_token:
            os.environ["AWS_SESSION_TOKEN"] = self.session_token
        if self.region:
            os.environ["AWS_REGION"] = self.region
            os.environ["AWS_REGION_NAME"] = self.region

    def as_litellm_kwargs(self) -> Dict[str, Optional[str]]:
        """Return credentials as explicit LiteLLM/boto3 kwargs so they are
        passed directly to the request rather than relying on env vars."""
        kwargs: Dict[str, Optional[str]] = {}
        if self.access_key:
            kwargs["aws_access_key_id"] = self.access_key
        if self.secret_key:
            kwargs["aws_secret_access_key"] = self.secret_key
        if self.session_token:
            kwargs["aws_session_token"] = self.session_token
        if self.region:
            kwargs["aws_region_name"] = self.region
        return kwargs

class Settings:
    # API Configuration
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "MIDAS API"

    # AI Gateway (Exlerate) — expose module-level values on the settings object.
    LLM_USE_GATEWAY: bool = LLM_USE_GATEWAY
    LLM_GATEWAY_URL: Optional[str] = LLM_GATEWAY_URL
    LLM_GATEWAY_VIRTUAL_KEY: Optional[str] = LLM_GATEWAY_VIRTUAL_KEY

    BEDROCK_CHAT_MODEL: Optional[str] = os.getenv("BEDROCK_AWS_MODEL")
    BEDROCK_KG_MODEL: Optional[str] = os.getenv("BEDROCK_AWS_KG_MODEL", BEDROCK_CHAT_MODEL)
    BEDROCK_EMBEDDING_MODEL: Optional[str] = os.getenv("BEDROCK_AWS_EMBEDDING_MODEL")

    # Litellm configuration for chat, embeddings, and knowledge graph
    CHAT_LLM_CONFIG: LitellmUsageConfig = LitellmUsageConfig.from_env(
        name="chat",
        prefixes=["LLM_CHAT", "LLM"],
        default_provider=os.getenv("LLM_PROVIDER", "azure"),
        default_model=os.getenv("LLM_MODEL", os.getenv("MODEL", DEFAULT_CHAT_MODEL)),
        fallback_map={
            "api_base": os.getenv("ENDPOINT"),
            "api_key": os.getenv("API_KEY"),
            "api_version": os.getenv("AZURE_API_VERSION", "2025-01-01-preview"),
            "model": BEDROCK_CHAT_MODEL or os.getenv("MODEL"),
        },
        model_normalizer=_normalize_bedrock_model,
    )

    EMBEDDING_LLM_CONFIG: LitellmUsageConfig = LitellmUsageConfig.from_env(
        name="embedding",
        prefixes=["LLM_EMBEDDING", "EMBEDDING"],
        default_provider=os.getenv("EMBEDDING_PROVIDER", "azure"),
        default_model=os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
        fallback_map={
            "api_base": os.getenv("EMBEDDING_ENDPOINT"),
            "api_key": os.getenv("API_KEY_EMBEDDING", os.getenv("API_KEY")),
            "api_version": os.getenv("EMBEDDING_API_VERSION", os.getenv("AZURE_API_VERSION")),
            "model": BEDROCK_EMBEDDING_MODEL or os.getenv("EMBEDDING_MODEL"),
        },
        model_normalizer=_normalize_bedrock_model,
    )

    KG_LLM_CONFIG: LitellmUsageConfig = LitellmUsageConfig.from_env(
        name="knowledge_graph",
        prefixes=["LLM_KG", "KG"],
        default_provider=os.getenv("KG_PROVIDER", "azure"),
        default_model=os.getenv("KG_MODEL", os.getenv("LLM_KG_MODEL", os.getenv("MODEL", DEFAULT_KG_MODEL))),
        fallback_map={
            "api_base": os.getenv("AZURE_KG_ENDPOINT", os.getenv("ENDPOINT")),
            "api_key": os.getenv("API_KEY_EMBEDDING", os.getenv("API_KEY")),
            "api_version": os.getenv("AZURE_KG_API_VERSION", "2024-12-01-preview"),
            "model": BEDROCK_KG_MODEL or os.getenv("KG_MODEL"),
        },
        model_normalizer=_normalize_bedrock_model,
    )

    BEDROCK_AWS_CREDENTIALS: AwsCredentials = AwsCredentials.load(
        prefix="BEDROCK_AWS",
        fallback={
            "access_key": os.getenv("AWS_ACCESS_KEY_ID"),
            "secret_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
            "session_token": os.getenv("AWS_SESSION_TOKEN"),
            "region": os.getenv("AWS_REGION"),
        },
    )

    # GraphRAG Service Configuration
    GRAPHRAG_SERVICE_URL: str = os.getenv("GRAPHRAG_SERVICE_URL", "http://localhost:8001")
    GRAPHRAG_SERVICE_PORT: int = int(os.getenv("GRAPHRAG_SERVICE_PORT", "8001"))

    # Pod-manager service integration (router.svc client_py)
    POD_MANAGER_ENABLED: bool = _env_bool("POD_MANAGER_ENABLED", default=False)
    POD_MANAGER_HOST: str = os.getenv("POD_MANAGER_HOST", "localhost")
    POD_MANAGER_PORT: int = int(os.getenv("POD_MANAGER_PORT", "8804"))
    POD_MANAGER_TIMEOUT_SECONDS: float = float(os.getenv("POD_MANAGER_TIMEOUT_SECONDS", "2.0"))
    POD_MANAGER_ENSURE_RETRIES: int = int(os.getenv("POD_MANAGER_ENSURE_RETRIES", "1"))
    
    # File Storage
    UPLOAD_DIR: str = "uploads"
    # Default 10 GiB; override via MAX_FILE_SIZE env (bytes). Sized for stress
    # tests with synthetic large datasets (e.g. tt3_2gb.csv ~ 2.44 GB). Common
    # values: 1 GB=1073741824, 2 GB=2147483648, 3 GB=3221225472, 5 GB=5368709120,
    # 10 GB=10737418240. Tighten in production via MAX_FILE_SIZE in .env.
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", str(10 * 1024 * 1024 * 1024)))

    # Parquet storage - same dir as uploads by default; override via PARQUET_DIR on Azure
    PARQUET_DIR: str = os.getenv("PARQUET_DIR", "uploads")

    # Vector Store
    VECTOR_STORE_PATH: str = "vector_store"
    VECTOR_DIMENSION: int = 1536  # OpenAI ada-002 embedding dimension

    # --- Session store (Redis / ElastiCache / memory): set in ``backend/.env`` ---
    # Resolution order: Secrets Manager (SESSION_ELASTICACHE_SECRET_ARN or SESSION_REDIS_SECRET_ID)
    # → SESSION_REDIS_URL → REDIS_URL; if none resolve, in-memory sessions are used.
    SESSION_TIMEOUT: int = int(os.getenv("SESSION_TIMEOUT", "3600"))  # 60 min default
    SESSION_ELASTICACHE_SECRET_ARN: Optional[str] = _optional_env_str("SESSION_ELASTICACHE_SECRET_ARN")
    SESSION_REDIS_SECRET_ID: Optional[str] = _optional_env_str("SESSION_REDIS_SECRET_ID")
    SESSION_REDIS_URL: Optional[str] = _optional_env_str("SESSION_REDIS_URL")
    SESSION_AWS_REGION: Optional[str] = _optional_env_str("SESSION_AWS_REGION")
    # boto3 Secrets Manager TLS verify; set false only for broken CA bundles (e.g. some Windows dev setups). Prefer fixing CA/certs in production.
    AWS_SECRETS_MANAGER_VERIFY_SSL: bool = _env_bool("AWS_SECRETS_MANAGER_VERIFY_SSL", default=True)
    # Named credential profile for boto3 (``~/.aws/config`` / SSO). Same as CLI ``--profile``; use with ``aws sso login --profile NAME``.
    AWS_PROFILE: Optional[str] = _optional_env_str("AWS_PROFILE")

    # AWS region (``.env``); used as fallback for session Secrets Manager if SESSION_AWS_REGION is unset
    AWS_REGION: Optional[str] = _optional_env_str("AWS_REGION")
    AWS_DEFAULT_REGION: Optional[str] = _optional_env_str("AWS_DEFAULT_REGION")

    # --- Application secrets (AWS Secrets Manager): RDS Postgres, S3, ElastiCache, Bedrock ---
    # Set ``AWS_*_SECRET_ID`` to the secret ARN or name; optional ``AWS_*_SECRET_JSON`` overrides with inline JSON (local dev).
    # ElastiCache: set ``AWS_ELASTICACHE_SECRET_ID`` to the Secrets Manager secret (session store uses ``SESSION_*`` separately).
    AWS_SECRETS_MANAGER_REGION: Optional[str] = _optional_env_str("AWS_SECRETS_MANAGER_REGION")
    AWS_RDS_POSTGRES_SECRET_ID: Optional[str] = _optional_env_str("AWS_RDS_POSTGRES_SECRET_ID")
    AWS_S3_SECRET_ID: Optional[str] = _optional_env_str("AWS_S3_SECRET_ID")
    AWS_ELASTICACHE_SECRET_ID: Optional[str] = _optional_env_str("AWS_ELASTICACHE_SECRET_ID")
    AWS_BEDROCK_SECRET_ID: Optional[str] = _optional_env_str("AWS_BEDROCK_SECRET_ID")
    AWS_RDS_POSTGRES_SECRET_JSON: Optional[str] = _optional_env_str("AWS_RDS_POSTGRES_SECRET_JSON")
    # When RDS-managed SM JSON omits dbname: merge this before parse. Prefer Helm (config), not SM. Match Terraform rds_postgres_db_name (default midas_dev).
    AWS_RDS_POSTGRES_DB_NAME: Optional[str] = _optional_env_str("AWS_RDS_POSTGRES_DB_NAME")
    # When RDS-managed SM JSON omits host/port (common after rotation): supply from config.
    # Set via the SM app secret (seeded by Terraform secretsmanager-app-secret-version.tf).
    AWS_RDS_POSTGRES_HOST: Optional[str] = _optional_env_str("AWS_RDS_POSTGRES_HOST")
    AWS_RDS_POSTGRES_PORT: Optional[str] = _optional_env_str("AWS_RDS_POSTGRES_PORT")
    # e.g. require - appended as sslmode query on sqlalchemy_url / DATABASE_URL when exporting from bundle.
    AWS_RDS_POSTGRES_SSLMODE: Optional[str] = _optional_env_str("AWS_RDS_POSTGRES_SSLMODE")
    AWS_S3_SECRET_JSON: Optional[str] = _optional_env_str("AWS_S3_SECRET_JSON")
    AWS_ELASTICACHE_SECRET_JSON: Optional[str] = _optional_env_str("AWS_ELASTICACHE_SECRET_JSON")
    AWS_BEDROCK_SECRET_JSON: Optional[str] = _optional_env_str("AWS_BEDROCK_SECRET_JSON")
    # Object key prefix for dataset uploads when using S3 (``ApplicationSecretsBundle.s3``).
    S3_UPLOAD_KEY_PREFIX: str = os.getenv("S3_UPLOAD_KEY_PREFIX", "uploads")
    # Direct S3 config when AWS_S3_SECRET_ID is not set. Relies on the default
    # boto3 credentials chain (IRSA / EC2 instance profile on EKS). When
    # S3_BUCKET_NAME is blank, the app falls back to local ``UPLOAD_DIR``.
    S3_BUCKET_NAME: Optional[str] = _optional_env_str("S3_BUCKET_NAME")
    S3_REGION: Optional[str] = _optional_env_str("S3_REGION")

    # Database Configuration
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/message_states.db")
    DATABASE_CLEANUP_DAYS: int = int(os.getenv("DATABASE_CLEANUP_DAYS", "30"))

    # Redis (``.env``) - shared fallback for session store and rate limiting
    REDIS_URL: Optional[str] = _optional_env_str("REDIS_URL")
    RATE_LIMIT_REDIS_URL: Optional[str] = _optional_env_str("RATE_LIMIT_REDIS_URL")
    CHROMA_URL: Optional[str] = os.getenv("CHROMA_URL", None)

    # Parallelism tuning
    INSIGHTS_MAX_WORKERS: int = int(os.getenv("INSIGHTS_MAX_WORKERS", "4"))
    TRAINING_MAX_WORKERS: int = int(os.getenv("TRAINING_MAX_WORKERS", "-1"))  # -1 = all cores
    EXECUTOR_MAX_WORKERS: int = int(os.getenv("EXECUTOR_MAX_WORKERS", "0"))   # 0 = auto
    
    MODEL_TRAINING_DUMP_ENABLED: bool = _env_bool("MODEL_TRAINING_DUMP_ENABLED", default=False)
    MODEL_TRAINING_DUMP_DIR: str = os.getenv("MODEL_TRAINING_DUMP_DIR", "models/training_dumps")

    # Data Quality / Treatment Agent Configuration
    DQ_OUTLIER_IQR_MULTIPLIER: float = float(os.getenv("DQ_OUTLIER_IQR_MULTIPLIER", "1.5"))
    DQ_OUTLIER_ZSCORE_THRESHOLD: float = float(os.getenv("DQ_OUTLIER_ZSCORE_THRESHOLD", "3.0"))
    DQ_OUTLIER_PERCENTILE_LOWER: int = int(os.getenv("DQ_OUTLIER_PERCENTILE_LOWER", "1"))
    DQ_OUTLIER_PERCENTILE_UPPER: int = int(os.getenv("DQ_OUTLIER_PERCENTILE_UPPER", "99"))
    DQ_MISSING_HIGH_THRESHOLD: float = float(os.getenv("DQ_MISSING_HIGH_THRESHOLD", "80.0"))
    DQ_MISSING_MODERATE_THRESHOLD: float = float(os.getenv("DQ_MISSING_MODERATE_THRESHOLD", "10.0"))
    DQ_DETECTION_SIGNIFICANCE_THRESHOLD: float = float(os.getenv("DQ_DETECTION_SIGNIFICANCE_THRESHOLD", "1.0"))
    DQ_DEFAULT_OUTLIER_METHOD: str = os.getenv("DQ_DEFAULT_OUTLIER_METHOD", "iqr")
    DQ_ENABLE_DETAILED_LOGGING: bool = os.getenv("DQ_ENABLE_DETAILED_LOGGING", "false").lower() == "true"

    # --- Deployment env + session-store hardening ---
    # APP_ENV drives prod-only safety guards (e.g. forbid in-memory session fallback).
    # Accepts "development" (default), "staging", "production".
    APP_ENV: str = (_optional_env_str("APP_ENV") or "development").lower()
    # When True, session factory refuses to fall back to in-memory store. Auto-enabled when APP_ENV=production.
    SESSION_REQUIRE_REDIS: bool = _env_bool("SESSION_REQUIRE_REDIS", default=False)

    # --- AWS Cognito Hosted UI + Entra ID federation (see cognito-entra-auth-integration-v2.1) ---
    # All values are read from environment/.env. In production, prefer Secrets Manager for CLIENT_SECRET + COOKIE_SECRET.
    COGNITO_DOMAIN: Optional[str] = _optional_env_str("COGNITO_DOMAIN")  # e.g. https://midas.auth.us-east-1.amazoncognito.com (no trailing slash)
    COGNITO_REGION: Optional[str] = _optional_env_str("COGNITO_REGION")
    COGNITO_USER_POOL_ID: Optional[str] = _optional_env_str("COGNITO_USER_POOL_ID")
    COGNITO_CLIENT_ID: Optional[str] = _optional_env_str("COGNITO_CLIENT_ID")
    # Optional: only for *confidential* app clients. Omit entirely for public SPA clients
    # (Cognito "Single-page application" type) — those authenticate with PKCE only.
    COGNITO_CLIENT_SECRET: Optional[str] = _optional_env_str("COGNITO_CLIENT_SECRET")
    # Comma-separated allowlist of redirect URIs (must exactly match the Cognito app client config).
    COGNITO_REDIRECT_URIS: Optional[str] = _optional_env_str("COGNITO_REDIRECT_URIS")
    COGNITO_LOGOUT_REDIRECT_URI: Optional[str] = _optional_env_str("COGNITO_LOGOUT_REDIRECT_URI")
    COGNITO_SCOPES: str = os.getenv("COGNITO_SCOPES", "openid email profile")
    # Optional: force a specific IdP (e.g. the Entra ID IdP name in Cognito) to skip the provider chooser.
    COGNITO_IDP_NAME: Optional[str] = _optional_env_str("COGNITO_IDP_NAME")
    # Cookie flags - set secure=false only on http:// local dev.
    COGNITO_COOKIE_SECURE: bool = _env_bool("COGNITO_COOKIE_SECURE", default=True)
    # HS256 secret for the short-lived cg_login binding cookie (state+nonce+verifier_hash).
    # Dev fallback: random per-process (sessions invalidated on restart). Prod must set explicitly (from SM).
    COGNITO_LOGIN_COOKIE_SECRET: Optional[str] = _optional_env_str("COGNITO_LOGIN_COOKIE_SECRET")
    COGNITO_LOGIN_COOKIE_TTL: int = int(os.getenv("COGNITO_LOGIN_COOKIE_TTL", "600"))  # 10 min
    # Cognito refresh-token cookie TTL (days). Must be <= Cognito app client refresh token validity.
    # The deployed client (us-east-1_5JL0dpXwK / Exldecisionai-Dev) has RefreshTokenValidity=5 days.
    # A cookie that outlives the token causes silent /refresh failures after day 5.
    COGNITO_REFRESH_COOKIE_TTL_DAYS: int = int(os.getenv("COGNITO_REFRESH_COOKIE_TTL_DAYS", "5"))

    # CORS origins (credentials require explicit origins, not "*"). Comma-separated.
    CORS_ALLOW_ORIGINS: Optional[str] = _optional_env_str("CORS_ALLOW_ORIGINS")

    # Feature flag: keep legacy username/password /api/v1/auth/{login,register} enabled.
    # Default False - Cognito is the only login path in production.
    ENABLE_LEGACY_PASSWORD_LOGIN: bool = _env_bool("ENABLE_LEGACY_PASSWORD_LOGIN", default=False)

    # Logging Configuration (see app/core/logging_config.py — env is read there at bootstrap too)
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/midas.log")
    ENABLE_CONSOLE_LOGGING: bool = os.getenv("ENABLE_CONSOLE_LOGGING", "true").lower() == "true"
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "text").strip().lower()
    LOG_CLIENT_IP: bool = _env_bool("LOG_CLIENT_IP", default=False)
    LOG_SENSITIVE_DEBUG: bool = _env_bool("LOG_SENSITIVE_DEBUG", default=False)
    LOG_PROMPT_HASH: bool = _env_bool("LOG_PROMPT_HASH", default=False)
    # Threshold (ms) above which the HTTP request middleware emits a dedicated
    # ``event=slow_request`` WARN log alongside the regular ``http_request``
    # INFO line. The architecture rule "anything > 1s should be a background
    # job" is the policy default; bump in dev / lower for stricter SLOs.
    # See docs/observability-runbook-slow-endpoints.md for the CloudWatch
    # Insights queries that consume these events.
    SLOW_REQUEST_THRESHOLD_MS: int = int(os.getenv("SLOW_REQUEST_THRESHOLD_MS", "1000"))
    # JSON / CloudWatch: service identity and optional stack traces (see logging_config.JsonFormatter)
    LOG_SERVICE_NAME: str = os.getenv("LOG_SERVICE_NAME", os.getenv("APP_NAME", "midas"))
    LOG_ENVIRONMENT: str = os.getenv(
        "LOG_ENVIRONMENT",
        os.getenv("ENVIRONMENT", os.getenv("ENV", "development")),
    )
    LOG_JSON_STACK_TRACE: bool = _env_bool("LOG_JSON_STACK_TRACE", default=False)

    # Observability env vars (OTEL_*, LOG_CLOUDWATCH_LOG_GROUP) are intentionally
    # NOT fields on Settings. telemetry.py and logging_config.py read them directly
    # from os.environ so they work from any injection source (Helm env:, .env, K8s
    # secret, etc.) without coupling the OTel library lifecycle to the Settings
    # dataclass. See docs/observability-configuration.md for the full reference.

    def __init__(self):
        # Create necessary directories
        Path(self.UPLOAD_DIR).mkdir(exist_ok=True)
        Path(self.VECTOR_STORE_PATH).mkdir(exist_ok=True)
        Path("logs").mkdir(exist_ok=True)
        
        # Create data directory for database
        Path(self.DATABASE_PATH).parent.mkdir(exist_ok=True)

    def apply_provider_environment(self, provider: str) -> None:
        # In gateway mode the AI Gateway proxies to Bedrock/Azure/etc. using its
        # own credentials, so we must not leak local AWS env vars onto the
        # process — doing so can confuse boto3-based libraries downstream.
        if gateway_enabled():
            return
        if provider == "bedrock":
            self.BEDROCK_AWS_CREDENTIALS.apply_to_env()

settings = Settings()
