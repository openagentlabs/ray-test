#!/usr/bin/env python3
"""Fetch a Secrets Manager secret via boto3. Full usage: run with --help."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys


def _strip_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    return s


def _parse_export_line(line: str) -> tuple[str, str] | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if line.lower().startswith("export "):
        line = line[7:].strip()
    elif line.lower().startswith("set "):
        line = line[4:].strip()
    if "=" not in line:
        return None
    key, _, rest = line.partition("=")
    key = key.strip()
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
        return None
    val = _strip_quotes(rest.strip())
    return (key, val)


def _parse_aws_export_block(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        p = _parse_export_line(line)
        if p:
            out[p[0]] = p[1]
    return out


_APPLY_KEYS_FROM_PASTE = frozenset(
    {
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
        "SECRET_ID",
        "MIDAS_ENVIRONMENT",
        "ENVIRONMENT",
    }
)


def _has_explicit_access_keys() -> bool:
    a = (os.environ.get("AWS_ACCESS_KEY_ID") or "").strip()
    s = (os.environ.get("AWS_SECRET_ACCESS_KEY") or "").strip()
    return bool(a and s)


def _has_alternate_credential_chain() -> bool:
    if (os.environ.get("AWS_PROFILE") or "").strip():
        return True
    if (os.environ.get("AWS_CONTAINER_CREDENTIALS_RELATIVE_URI") or "").strip():
        return True
    if (os.environ.get("AWS_CONTAINER_CREDENTIALS_FULL_URI") or "").strip():
        return True
    if (os.environ.get("AWS_WEB_IDENTITY_TOKEN_FILE") or "").strip():
        return True
    return False


def _read_paste_block() -> str:
    if not sys.stdin.isatty():
        return sys.stdin.read()
    print(
        "Paste the export block from AWS (e.g. export AWS_ACCESS_KEY_ID=...).\n"
        "End with an empty line:",
        file=sys.stderr,
    )
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "":
            break
        lines.append(line)
    return "\n".join(lines)


def _maybe_prompt_aws_export_block() -> None:
    if _has_explicit_access_keys() or _has_alternate_credential_chain():
        return
    raw = _read_paste_block().strip()
    if not raw:
        return
    parsed = _parse_aws_export_block(raw)
    for k, v in parsed.items():
        if k in _APPLY_KEYS_FROM_PASTE and not (os.environ.get(k) or "").strip():
            os.environ[k] = v


_HELP_DESCRIPTION = """\
Fetch a Secrets Manager secret using boto3.

Default secret name is midas-test-secret-001 (Terraform:
deploy/ecs-app/modules/secretsmanager-test-secret). Override with SECRET_ID or
--secret-id for other secrets (e.g. midas-rds-creds01 or app config
midas-<environment>-<region>/app).

Requires: pip install boto3
"""

_HELP_EPILOG = """\
Environment variables (defaults for flags):
  SECRET_ID              Secret name or ARN (same as --secret-id).
  AWS_REGION, AWS_DEFAULT_REGION   Region (default: us-east-1).
  AWS_CA_BUNDLE          Optional path to CA bundle (use with --verify-ssl).

Credentials (in order):
  1. If AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are set (or another chain below),
     those are used and nothing is prompted.
  2. Otherwise you are prompted to paste the export block from the AWS console
     (IAM access keys or temporary credentials), for example:

       export AWS_ACCESS_KEY_ID="..."
       export AWS_SECRET_ACCESS_KEY="..."
       export AWS_SESSION_TOKEN="..."   # if present

     The same paste may include AWS_REGION or SECRET_ID; values are applied only for
     keys that are not already set in the environment.
  3. No paste is requested if AWS_PROFILE is set, or ECS/EC2 role env vars are
     present (AWS_CONTAINER_CREDENTIALS_*, AWS_WEB_IDENTITY_TOKEN_FILE).

Non-interactive paste: pipe the export block on stdin (stdin is not a TTY).

TLS:
  By default server certificates are NOT validated (typical behind corporate SSL
  inspection). Use --verify-ssl to enforce verification.

Examples:
  ./deploy/scripts/test/midas-secretsmanager-get-secret.py
  ./deploy/scripts/test/midas-secretsmanager-get-secret.py -v
  SECRET_ID=midas-uat-us-east-1/app ./deploy/scripts/test/midas-secretsmanager-get-secret.py
  ./deploy/scripts/test/midas-secretsmanager-get-secret.py --json-key someKey
"""


def main() -> int:
    if "-h" not in sys.argv and "--help" not in sys.argv:
        _maybe_prompt_aws_export_block()

    p = argparse.ArgumentParser(
        description=_HELP_DESCRIPTION,
        epilog=_HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--secret-id",
        default=os.environ.get("SECRET_ID", "midas-test-secret-001"),
        help="Secret name or ARN (default: SECRET_ID env or midas-test-secret-001).",
    )
    p.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1")),
        help="AWS region (default: AWS_REGION / AWS_DEFAULT_REGION or us-east-1).",
    )
    p.add_argument(
        "--json-key",
        metavar="KEY",
        help="If SecretString is JSON, print only this top-level string value.",
    )
    p.add_argument(
        "--verify-ssl",
        action="store_true",
        help="Verify TLS server certificates (default: off).",
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print secret id and region to stderr before printing the value on stdout.",
    )
    args = p.parse_args()

    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError
    except ImportError:
        print("Install boto3: pip install boto3", file=sys.stderr)
        return 1

    verify_ssl = args.verify_ssl
    if not verify_ssl:
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    client = boto3.client(
        "secretsmanager",
        region_name=args.region,
        verify=verify_ssl,
    )
    try:
        resp = client.get_secret_value(SecretId=args.secret_id)
    except (ClientError, BotoCoreError) as e:
        print(str(e), file=sys.stderr)
        return 1

    if "SecretString" in resp and resp["SecretString"] is not None:
        raw = resp["SecretString"]
    elif "SecretBinary" in resp and resp["SecretBinary"] is not None:
        print("Secret is binary; decode SecretBinary in your own code.", file=sys.stderr)
        return 2
    else:
        print("No SecretString or SecretBinary in response.", file=sys.stderr)
        return 2

    if args.verbose:
        print(f"secret_id={args.secret_id} region={args.region}", file=sys.stderr)

    if args.json_key:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"SecretString is not valid JSON: {e}", file=sys.stderr)
            return 1
        if args.json_key not in data:
            print(f"JSON key not found: {args.json_key!r}", file=sys.stderr)
            return 1
        print(data[args.json_key])
    else:
        print(raw)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
