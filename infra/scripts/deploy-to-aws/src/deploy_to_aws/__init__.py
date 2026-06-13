"""deploy-to-aws — modern AWS deployment CLI for ARB infrastructure."""

from deploy_to_aws.build_info import BuildInfo

__all__ = ("BuildInfo", "__version__")

__version__ = BuildInfo.version
