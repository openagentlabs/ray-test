#!/usr/bin/env python3
"""Thin entry shim — prefer ``uv run deploy-to-aws`` or the console script."""

from deploy_to_aws.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
