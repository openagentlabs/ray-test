"""``returns`` re-exports and deploy-to-aws ``Result`` type aliases."""

from __future__ import annotations

from returns.result import Failure, Result, Success

from deploy_to_aws.core.types import DeployResult, TextResult, UnitResult

__all__ = (
    "DeployResult",
    "Failure",
    "Result",
    "Success",
    "TextResult",
    "UnitResult",
)
