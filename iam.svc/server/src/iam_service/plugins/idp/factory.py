"""Build identity provider driver from application config."""

from __future__ import annotations

from iam_service.core.app_config import IdpConfig
from iam_service.core.errors import AppError, ErrorCodes
from iam_service.core.results import Failure, Result, Success
from iam_service.plugins.idp.hardcoded_driver import HardcodedIdpDriver
from iam_service.plugins.idp.interface import IdentityProviderDriver


def build_idp_driver(config: IdpConfig) -> Result[IdentityProviderDriver, AppError]:
    """Instantiate the configured IdP driver."""
    driver_name = config.driver.strip().lower()
    if driver_name == "hardcoded":
        users = {user.email.lower(): user.password for user in config.hardcoded.users}
        return Success(
            HardcodedIdpDriver(
                provider_id=config.hardcoded.provider_id,
                display_name=config.hardcoded.display_name,
                users=users,
            ),
        )
    return Failure(
        AppError(
            code=ErrorCodes.VALIDATION,
            message="Unknown IdP driver.",
            detail=f"driver={driver_name!r}",
        ),
    )
