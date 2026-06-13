"""FastAPI dependency helpers for pod-manager service."""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Depends, Request

from app.services.pod_manager_service import PodManagerService


def get_pod_manager_service(request: Request) -> Optional[PodManagerService]:
    """Return ``app.state.pod_manager_service`` when available."""
    service = getattr(request.app.state, "pod_manager_service", None)
    if service is None:
        return None
    return service


PodManagerServiceDep = Annotated[Optional[PodManagerService], Depends(get_pod_manager_service)]
