"""FastAPI dependency for the resolved application secrets bundle."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.core.secrets.models import ApplicationSecretsBundle


def get_application_secrets(request: Request) -> ApplicationSecretsBundle:
    """Return ``app.state.secrets_bundle`` (populated at startup)."""
    bundle = getattr(request.app.state, "secrets_bundle", None)
    if bundle is None:
        return ApplicationSecretsBundle()
    return bundle


ApplicationSecrets = Annotated[ApplicationSecretsBundle, Depends(get_application_secrets)]
