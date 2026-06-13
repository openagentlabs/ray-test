#!/usr/bin/env python3
"""Verify AWS CLI is installed and credentials work via `aws sts get-caller-identity`.

Callers (e.g. kt_aws_validate_conectivity_from_laptop_to_aws_service) assume
``AWS_ACCESS_KEY_ID``, ``AWS_SECRET_ACCESS_KEY``, and ``AWS_SESSION_TOKEN`` are
already set when using temporary credentials. This script does not read or
validate those variables; the AWS CLI uses the normal credential provider chain.

Exits:
  0 - CLI present and STS call succeeded
  1 - CLI present but STS failed (invalid/expired creds, network, IAM, etc.)
  2 - AWS CLI not found on PATH

This script invokes the AWS CLI as a subprocess (does not use boto3).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys


def _print_install_help() -> None:
    sys.stderr.write(
        "\nAWS CLI is not installed or not on your PATH.\n\n"
        "Install options:\n"
        "  • macOS (official bundles): https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html\n"
        "  • macOS (Homebrew): brew install awscli\n"
        "  • Linux: use your package manager or the official installer from the same AWS docs page.\n"
        "  • Windows: MSI installer from the AWS CLI user guide.\n\n"
        "After install, open a new terminal and run: aws --version\n"
    )


def main() -> int:
    aws_exe = shutil.which("aws")
    if not aws_exe:
        print("AWS_CLI_ON_PATH=false", flush=True)
        print("STS_OK=false", flush=True)
        _print_install_help()
        return 2

    print(f"AWS_CLI_ON_PATH=true", flush=True)
    ver = subprocess.run(
        [aws_exe, "--version"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    version_line = (ver.stdout or ver.stderr or "").strip().splitlines()
    version_summary = version_line[0] if version_line else "(no output)"
    print(f"AWS_CLI_VERSION={version_summary!r}", flush=True)

    sts = subprocess.run(
        [aws_exe, "sts", "get-caller-identity", "--output", "json"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if sts.returncode != 0:
        print("STS_OK=false", flush=True)
        err = (sts.stderr or sts.stdout or "").strip()
        if err:
            sys.stderr.write(err + "\n")
        return 1

    try:
        data = json.loads(sts.stdout or "{}")
    except json.JSONDecodeError:
        print("STS_OK=false", flush=True)
        sys.stderr.write("STS returned non-JSON output.\n")
        return 1

    print("STS_OK=true", flush=True)
    for key in ("UserId", "Account", "Arn"):
        if key in data:
            print(f"STS_{key.upper()}={data[key]!r}", flush=True)
    print("STS_JSON=" + json.dumps(data, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
