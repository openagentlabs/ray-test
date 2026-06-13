"""Module entrypoint for ``python -m deploy_to_aws``."""

from deploy_to_aws.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
