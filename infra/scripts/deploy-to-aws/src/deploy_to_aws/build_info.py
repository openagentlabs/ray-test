"""Public access to injected ``BuildInfo`` with dev fallback."""

from __future__ import annotations

try:
    from deploy_to_aws._injected import BuildInfo
except ImportError:
    from deploy_to_aws.build.fallback_build_info import BuildInfo

__all__ = ("BuildInfo",)
