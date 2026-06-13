"""Compose ``ApplicationSecretsBundle`` from ``SECRET_SLOTS`` + ``Settings``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

from app.core.secrets.factory import build_secrets_reader
from app.core.secrets.models import ApplicationSecretsBundle
from app.core.secrets.slot_definitions import SECRET_SLOTS
from app.core.secrets.slot_loading import load_secret_slot

if TYPE_CHECKING:
    from app.core.config import Settings


def load_application_secrets_bundle(settings: "Settings") -> ApplicationSecretsBundle:
    """
    Resolve secrets for each slot: identifiers from ``Settings`` (``.env``) →
    optional inline JSON → else AWS Secrets Manager via ``ISecretsReader``.
    """
    reader = build_secrets_reader(settings)
    resolved: Dict[str, Any] = {}
    for slot in SECRET_SLOTS:
        merge_into_payload: Dict[str, Any] | None = None
        if slot.label == "rds_postgres":
            inline = slot.inline_json_from_settings(settings)
            if not (inline and str(inline).strip()):
                # RDS-managed secrets after rotation may only contain username/password.
                # Supply host, port, and dbname from Settings (sourced from the SM app secret
                # via AWS_RDS_POSTGRES_HOST / AWS_RDS_POSTGRES_PORT / AWS_RDS_POSTGRES_DB_NAME)
                # so the connection can be fully resolved without modifying the managed secret.
                extra: Dict[str, Any] = {}
                dbn = (settings.AWS_RDS_POSTGRES_DB_NAME or "").strip()
                if dbn:
                    extra["dbname"] = dbn
                host = (getattr(settings, "AWS_RDS_POSTGRES_HOST", None) or "").strip()
                if host:
                    extra["host"] = host
                port_raw = (getattr(settings, "AWS_RDS_POSTGRES_PORT", None) or "").strip()
                if port_raw:
                    try:
                        extra["port"] = int(port_raw)
                    except ValueError:
                        pass
                if extra:
                    merge_into_payload = extra
        resolved[slot.bundle_attr] = load_secret_slot(
            label=slot.label,
            env_json=slot.inline_json_from_settings(settings),
            secret_id=slot.secret_id_from_settings(settings),
            reader=reader,
            parser=slot.parse,
            merge_into_payload=merge_into_payload,
        )
    return ApplicationSecretsBundle(**resolved)
