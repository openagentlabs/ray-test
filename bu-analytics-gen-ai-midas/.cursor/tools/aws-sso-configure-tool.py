#!/usr/bin/env python3
"""
aws-sso-configure-tool.py  –  Write an AWS SSO profile to ~/.aws/config and
optionally trigger `aws sso login` for it.

All inputs are validated via a Pydantic v2 model (SSOProfileConfig) before
any file is written.  MIDAS-dev defaults are baked in; every field is
overridable via a CLI flag.

Defaults:
  --sso-start-url   https://exlcloudprod.awsapps.com/start/#/?tab=accounts
  --sso-region      us-east-1
  --account-id      811391286931
  --role-name       uc-dev2.0-app.architects-ps
  --profile         midas-dev
  --region          us-east-1
  --output          json

Usage (from repo root):
  python3 .cursor/tools/aws-sso-configure-tool.py
  python3 .cursor/tools/aws-sso-configure-tool.py --profile midas-uat --account-id 123456789012
  python3 .cursor/tools/aws-sso-configure-tool.py --login
  python3 .cursor/tools/aws-sso-configure-tool.py --dry-run
  python3 .cursor/tools/aws-sso-configure-tool.py --help

Prerequisites:
  - Python 3.11+
  - pydantic>=2  (pip install pydantic)
  - AWS CLI v2   (brew install awscli)
  - Network access to the SSO start URL
"""

from __future__ import annotations

import argparse
import configparser
import subprocess
import sys
from enum import StrEnum
from pathlib import Path
from typing import Annotated

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator, model_validator


# ──────────────────────────────────────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────────────────────────────────────

class OutputFormat(StrEnum):
    json  = "json"
    text  = "text"
    table = "table"


# ──────────────────────────────────────────────────────────────────────────────
# Pydantic model — single source of truth for all inputs + defaults
# ──────────────────────────────────────────────────────────────────────────────

class SSOProfileConfig(BaseModel):
    """Validated configuration for one AWS SSO profile entry in ~/.aws/config."""

    sso_start_url: Annotated[
        AnyHttpUrl,
        Field(
            default="https://exlcloudprod.awsapps.com/start/#/?tab=accounts",
            description="AWS IAM Identity Center start URL.",
        ),
    ] = "https://exlcloudprod.awsapps.com/start/#/?tab=accounts"  # type: ignore[assignment]

    sso_region: Annotated[
        str,
        Field(
            default="us-east-1",
            description="AWS region hosting the SSO / IdP endpoint.",
            min_length=1,
        ),
    ] = "us-east-1"

    account_id: Annotated[
        str,
        Field(
            default="811391286931",
            description="12-digit AWS account ID.",
            pattern=r"^\d{12}$",
        ),
    ] = "811391286931"

    role_name: Annotated[
        str,
        Field(
            default="uc-dev2.0-app.architects-ps",
            description="SSO permission-set / role name.",
            min_length=1,
        ),
    ] = "uc-dev2.0-app.architects-ps"

    profile: Annotated[
        str,
        Field(
            default="midas-dev",
            description="AWS CLI profile name to create or update in ~/.aws/config.",
            min_length=1,
        ),
    ] = "midas-dev"

    region: Annotated[
        str,
        Field(
            default="us-east-1",
            description="Default AWS region written to the profile.",
            min_length=1,
        ),
    ] = "us-east-1"

    output: Annotated[
        OutputFormat,
        Field(
            default=OutputFormat.json,
            description="Default CLI output format.",
        ),
    ] = OutputFormat.json

    login: Annotated[
        bool,
        Field(
            default=False,
            description="Run `aws sso login` after writing the profile.",
        ),
    ] = False

    dry_run: Annotated[
        bool,
        Field(
            default=False,
            description="Print what would be written without touching ~/.aws/config.",
        ),
    ] = False

    @field_validator("account_id")
    @classmethod
    def _strip_account_id(cls, v: str) -> str:
        return v.strip()

    @field_validator("sso_region", "region")
    @classmethod
    def _validate_region_format(cls, v: str) -> str:
        v = v.strip()
        parts = v.split("-")
        if len(parts) < 3:  # noqa: PLR2004
            raise ValueError(
                f"'{v}' does not look like a valid AWS region (expected e.g. us-east-1)."
            )
        return v

    @model_validator(mode="after")
    def _login_requires_no_dry_run(self) -> SSOProfileConfig:
        if self.login and self.dry_run:
            raise ValueError("--login and --dry-run are mutually exclusive.")
        return self

    def to_ini_section(self) -> dict[str, str]:
        """Return the key/value pairs written to [profile <name>] in ~/.aws/config."""
        return {
            "sso_start_url":  str(self.sso_start_url),
            "sso_region":     self.sso_region,
            "sso_account_id": self.account_id,
            "sso_role_name":  self.role_name,
            "region":         self.region,
            "output":         str(self.output),
        }


# ──────────────────────────────────────────────────────────────────────────────
# CLI parsing
# ──────────────────────────────────────────────────────────────────────────────

def parse_args() -> SSOProfileConfig:
    """Parse CLI flags and return a validated SSOProfileConfig."""
    defaults = SSOProfileConfig()

    p = argparse.ArgumentParser(
        description="Write an AWS SSO profile to ~/.aws/config for MIDAS.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--sso-start-url",
        default=str(defaults.sso_start_url),
        help=f"SSO start URL (default: {defaults.sso_start_url})",
    )
    p.add_argument(
        "--sso-region",
        default=defaults.sso_region,
        help=f"SSO/IdP region (default: {defaults.sso_region})",
    )
    p.add_argument(
        "--account-id",
        default=defaults.account_id,
        help=f"AWS account ID — must be exactly 12 digits (default: {defaults.account_id})",
    )
    p.add_argument(
        "--role-name",
        default=defaults.role_name,
        help=f"SSO permission-set / role name (default: {defaults.role_name})",
    )
    p.add_argument(
        "--profile",
        default=defaults.profile,
        help=f"AWS CLI profile name to create/update (default: {defaults.profile})",
    )
    p.add_argument(
        "--region",
        default=defaults.region,
        help=f"Default AWS region for API calls (default: {defaults.region})",
    )
    p.add_argument(
        "--output",
        default=str(defaults.output),
        choices=[f.value for f in OutputFormat],
        help=f"Default output format (default: {defaults.output})",
    )
    p.add_argument(
        "--login",
        action="store_true",
        help="Run `aws sso login --profile <profile>` after writing config.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be written without modifying ~/.aws/config.",
    )

    raw = p.parse_args()

    try:
        return SSOProfileConfig(
            sso_start_url=raw.sso_start_url,
            sso_region=raw.sso_region,
            account_id=raw.account_id,
            role_name=raw.role_name,
            profile=raw.profile,
            region=raw.region,
            output=raw.output,
            login=raw.login,
            dry_run=raw.dry_run,
        )
    except Exception as exc:
        p.error(f"Invalid input: {exc}")


# ──────────────────────────────────────────────────────────────────────────────
# AWS CLI check
# ──────────────────────────────────────────────────────────────────────────────

def ensure_aws_cli() -> None:
    """Abort with a helpful message if AWS CLI v2 is not installed."""
    try:
        result = subprocess.run(
            ["aws", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        version_line = result.stdout.strip() or result.stderr.strip()
        if "aws-cli/2" not in version_line:
            print(
                f"WARNING: AWS CLI may not be v2 ({version_line}).\n"
                "SSO requires AWS CLI v2.  Install: brew install awscli",
                file=sys.stderr,
            )
    except FileNotFoundError:
        print(
            "ERROR: AWS CLI not found on PATH.\n"
            "Install it with: brew install awscli",
            file=sys.stderr,
        )
        sys.exit(1)


# ──────────────────────────────────────────────────────────────────────────────
# Profile write
# ──────────────────────────────────────────────────────────────────────────────

def write_profile(
    config_path: Path,
    profile: str,
    section: dict[str, str],
    *,
    dry_run: bool,
) -> None:
    """Upsert the [profile <name>] section in ~/.aws/config."""
    cfg = configparser.RawConfigParser()
    if config_path.exists():
        cfg.read(config_path)

    section_name = f"profile {profile}"
    if not cfg.has_section(section_name):
        cfg.add_section(section_name)
    for key, value in section.items():
        cfg.set(section_name, key, value)

    if dry_run:
        print(f"[DRY RUN] Would write to {config_path}:\n")
        print(f"[{section_name}]")
        for key, value in section.items():
            print(f"  {key} = {value}")
        print()
        return

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w") as fh:
        cfg.write(fh)
    config_path.chmod(0o600)


# ──────────────────────────────────────────────────────────────────────────────
# SSO login
# ──────────────────────────────────────────────────────────────────────────────

def run_sso_login(profile: str) -> None:
    """Invoke `aws sso login`; opens a browser for OIDC authentication."""
    print(f"\nRunning: aws sso login --profile {profile}")
    print("A browser window will open for you to authenticate.\n")
    subprocess.run(["aws", "sso", "login", "--profile", profile], check=False)


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    cfg = parse_args()
    ensure_aws_cli()

    config_path = Path.home() / ".aws" / "config"
    section = cfg.to_ini_section()

    print("──────────────────────────────────────────────")
    print("  MIDAS AWS SSO profile configurator")
    print("──────────────────────────────────────────────")
    print(f"  Profile     : {cfg.profile}")
    print(f"  SSO URL     : {cfg.sso_start_url}")
    print(f"  SSO region  : {cfg.sso_region}")
    print(f"  Account ID  : {cfg.account_id}")
    print(f"  Role name   : {cfg.role_name}")
    print(f"  AWS region  : {cfg.region}")
    print(f"  Output fmt  : {cfg.output}")
    print(f"  Config file : {config_path}")
    if cfg.dry_run:
        print("  Mode        : DRY RUN — no files will be written")
    print("──────────────────────────────────────────────\n")

    write_profile(config_path, cfg.profile, section, dry_run=cfg.dry_run)

    if not cfg.dry_run:
        print(f"Done. Profile '{cfg.profile}' written to {config_path}.")
        print()
        print("Next steps:")
        print(f"  1. Log in:   aws sso login --profile {cfg.profile}")
        print(f"  2. Verify:   aws sts get-caller-identity --profile {cfg.profile}")
        print(f"  3. Activate: export AWS_PROFILE={cfg.profile}")
        print()
        print("  Or re-run with --login to do step 1 automatically.")

    if cfg.login:
        run_sso_login(cfg.profile)


if __name__ == "__main__":
    main()
