"""AWS provider constants for Terraform Registry search."""

from __future__ import annotations

from typing import Final

AWS_PROVIDER: Final[str] = "aws"
AWS_PROVIDER_LABEL: Final[str] = "AWS"

# Common verified/community namespaces for AWS modules (documentation hints).
KNOWN_AWS_NAMESPACES: Final[tuple[str, ...]] = (
    "terraform-aws-modules",
    "aws-ia",
    "cloudposse",
)
