#!/usr/bin/env python3
"""
sm.py — AWS Secrets Manager management utility for MIDAS.

Modes (choose exactly one):
  <secret-name>          Update an existing secret's JSON value (default mode).
  -n <secret-name>       Create a NEW secret and set its JSON value.
  -l [PREFIX]            List all secrets (optionally filtered by name prefix).
  -d <secret-name>       Delete a secret by name (with confirmation prompt).
  -h / --help            Show this help and exit.

Credentials:
  Uses the stored ~/.aws/credentials 'default' profile by default.
  Override with --profile PROFILE or --region REGION.

Usage examples:
  # Update an existing secret (prompts for JSON):
  python3 deploy/scripts/util/sm.py midas-dev-us-east-1/frontend

  # Create a new secret (errors if it already exists):
  python3 deploy/scripts/util/sm.py -n my-new-secret

  # List all secrets:
  python3 deploy/scripts/util/sm.py -l

  # List secrets matching a prefix:
  python3 deploy/scripts/util/sm.py -l midas-dev

  # Delete a secret (prompts for confirmation):
  python3 deploy/scripts/util/sm.py -d midas-dev-us-east-1/frontend
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
import warnings
from typing import Any

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

# ── Colour helpers ────────────────────────────────────────────────────────────
_USE_COLOR = True


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


def bold(t: str) -> str:   return _c("1", t)
def green(t: str) -> str:  return _c("32", t)
def yellow(t: str) -> str: return _c("33", t)
def cyan(t: str) -> str:   return _c("36", t)
def red(t: str) -> str:    return _c("31", t)
def dim(t: str) -> str:    return _c("2", t)


# ── boto3 / session ───────────────────────────────────────────────────────────
def _get_session(profile: str, region: str):
    try:
        import boto3
    except ImportError:
        _die("boto3 is not installed. Install it with: pip install boto3")
    return boto3.Session(profile_name=profile, region_name=region)


def _sm_client(session, region: str):
    return session.client("secretsmanager", region_name=region, verify=False)


def _sts_check(session, region: str) -> str:
    """Verify credentials and return the caller ARN."""
    try:
        sts = session.client("sts", region_name=region, verify=False)
        identity = sts.get_caller_identity()
        return identity.get("Arn", "unknown")
    except Exception as e:
        _die(f"Could not verify AWS credentials: {e}\n"
             "  Ensure your credentials are valid (run aws-credentials-setup.sh if needed).")


# ── Helpers ───────────────────────────────────────────────────────────────────
def _die(msg: str, code: int = 1) -> None:
    print(red(f"ERROR: {msg}"), file=sys.stderr)
    sys.exit(code)


def _confirm(prompt: str) -> bool:
    """Ask user to confirm with y/yes (anything else = no)."""
    try:
        answer = input(f"{yellow(prompt)} [y/N]: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print()
        return False
    return answer in ("y", "yes")


def _read_json_from_user(secret_name: str) -> str:
    """
    Prompt the user to paste a JSON value, then press Enter.
    Accepts single-line or multi-line JSON (keep pasting until a line contains
    only a closing brace/bracket on its own, OR press Enter on a blank line
    after the JSON is complete).
    Returns the raw JSON string after validating it parses correctly.
    """
    print()
    print(bold(f"Paste the JSON value for secret '{secret_name}':"))
    print(dim("  • Single line:  paste the JSON and press Enter."))
    print(dim("  • Multi-line:   paste all lines, then press Enter on a blank line."))
    print(dim("  • To abort:     press Ctrl-C."))
    print()

    lines: list[str] = []
    try:
        while True:
            line = input()
            if not line and lines:
                # Blank line after content = end of input
                break
            lines.append(line)
            # Try to parse after each line — if it succeeds and looks complete, stop
            candidate = "\n".join(lines).strip()
            if candidate:
                try:
                    json.loads(candidate)
                    # Valid JSON — but only stop if the last character closes a structure
                    stripped = candidate.rstrip()
                    if stripped and stripped[-1] in ('}', ']', '"', 'e', 'l'):
                        # 'e' → true/false/null end, 'l' → null end
                        break
                except json.JSONDecodeError:
                    pass
    except (KeyboardInterrupt, EOFError):
        print()
        _die("Aborted by user.")

    raw = "\n".join(lines).strip()
    if not raw:
        _die("No JSON input provided.")

    # Validate
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        _die(f"Invalid JSON: {e}\n  Input received:\n{textwrap.indent(raw, '    ')}")

    if not isinstance(parsed, dict):
        _die(f"JSON must be an object (got {type(parsed).__name__}). "
             "Example: {{\"KEY\": \"value\"}}")

    # Pretty-print for confirmation
    pretty = json.dumps(parsed, indent=2)
    print()
    print(bold("JSON parsed successfully:"))
    for line in pretty.splitlines():
        print(f"  {cyan(line)}")
    print()
    return raw


def _secret_exists(client, name: str) -> dict | None:
    """Return secret metadata dict if it exists, None otherwise."""
    try:
        return client.describe_secret(SecretId=name)
    except client.exceptions.ResourceNotFoundException:
        return None
    except Exception as e:
        _die(f"Unexpected error checking secret '{name}': {e}")


# ── Mode: update existing secret ──────────────────────────────────────────────
def cmd_update(client, secret_name: str) -> int:
    print(bold(f"Mode: UPDATE existing secret '{secret_name}'"))
    print()

    meta = _secret_exists(client, secret_name)
    if meta is None:
        _die(
            f"Secret '{secret_name}' does not exist in Secrets Manager.\n"
            "  To create a new secret use the -n flag:\n"
            f"    python3 sm.py -n {secret_name}"
        )

    print(dim(f"  ARN : {meta.get('ARN', '')}"))
    print()

    raw_json = _read_json_from_user(secret_name)

    if not _confirm(f"Write this JSON to '{secret_name}'?"):
        print(yellow("Aborted — no changes made."))
        return 0

    resp = client.put_secret_value(SecretId=secret_name, SecretString=raw_json)
    print(green(f"✓ Secret '{secret_name}' updated (version: {resp.get('VersionId', '?')})."))
    return 0


# ── Mode: create new secret ───────────────────────────────────────────────────
def cmd_create(client, secret_name: str, region: str, account_id: str) -> int:
    print(bold(f"Mode: CREATE new secret '{secret_name}'"))
    print()

    meta = _secret_exists(client, secret_name)
    if meta is not None:
        _die(
            f"Secret '{secret_name}' already exists in Secrets Manager.\n"
            "  To update its value, run without the -n flag:\n"
            f"    python3 sm.py {secret_name}"
        )

    raw_json = _read_json_from_user(secret_name)

    if not _confirm(f"Create secret '{secret_name}' with this JSON value?"):
        print(yellow("Aborted — no secret created."))
        return 0

    resp = client.create_secret(
        Name=secret_name,
        SecretString=raw_json,
        Tags=[
            {"Key": "ManagedBy",   "Value": "sm.py"},
            {"Key": "AccountId",   "Value": account_id},
        ],
    )
    print(green(f"✓ Secret '{secret_name}' created."))
    print(dim(f"  ARN: {resp.get('ARN', '?')}"))
    return 0


# ── Mode: list secrets ────────────────────────────────────────────────────────
def cmd_list(client, prefix: str, region: str) -> int:
    filter_desc = f" matching '{prefix}*'" if prefix else ""
    print(bold(f"Listing Secrets Manager secrets{filter_desc} in {region}…"))
    print()

    filters = [{"Key": "name", "Values": [prefix]}] if prefix else []
    secrets: list[dict] = []
    try:
        paginator = client.get_paginator("list_secrets")
        for page in paginator.paginate(Filters=filters):
            secrets.extend(page.get("SecretList", []))
    except Exception as e:
        _die(f"Could not list secrets: {e}")

    if not secrets:
        print(yellow(f"No secrets found{filter_desc}."))
        return 0

    for i, meta in enumerate(secrets, 1):
        name = meta.get("Name", "(unknown)")
        arn  = meta.get("ARN", "")
        print(bold(cyan(f"{'─' * 68}")))
        print(bold(f"[{i}] {name}"))
        print(dim(f"    ARN : {arn}"))

        # Fetch and show value
        try:
            resp = client.get_secret_value(SecretId=name)
            raw = resp.get("SecretString")
            if raw is not None:
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict):
                        max_k = max((len(k) for k in parsed), default=0)
                        print(dim(f"    Type: json ({len(parsed)} key(s))"))
                        for k, v in sorted(parsed.items()):
                            display = str(v)
                            if len(display) > 100:
                                display = display[:97] + dim("…")
                            pad = " " * (max_k - len(k))
                            print(f"    {green(k)}{pad}  =  {display}")
                    else:
                        print(dim("    Type: string"))
                        print(f"    {str(raw)[:100]}")
                except json.JSONDecodeError:
                    print(dim("    Type: string"))
                    print(f"    {str(raw)[:100]}")
            else:
                print(dim("    Type: binary"))
        except Exception as e:
            print(yellow(f"    (could not read value: {e})"))
        print()

    print(bold(cyan("─" * 68)))
    print(bold(f"Total: {len(secrets)} secret(s)"))
    return 0


# ── Mode: delete secret ───────────────────────────────────────────────────────
def cmd_delete(client, secret_name: str) -> int:
    print(bold(f"Mode: DELETE secret '{secret_name}'"))
    print()

    meta = _secret_exists(client, secret_name)
    if meta is None:
        _die(
            f"Secret '{secret_name}' was not found in Secrets Manager.\n"
            "  Check the name is correct. Use -l to list available secrets:\n"
            "    python3 sm.py -l"
        )

    arn = meta.get("ARN", "")
    print(dim(f"  ARN : {arn}"))
    print()
    print(yellow("WARNING: This will permanently delete the secret with no recovery window."))
    print(yellow("         Any application reading this secret will break immediately."))
    print()

    if not _confirm(f"Permanently delete '{secret_name}'?"):
        print(yellow("Aborted — secret not deleted."))
        return 0

    # Second confirmation for safety
    try:
        confirm2 = input(
            f"  {yellow('Type the secret name to confirm deletion')}: "
        ).strip()
    except (KeyboardInterrupt, EOFError):
        print()
        print(yellow("Aborted."))
        return 0

    if confirm2 != secret_name:
        _die("Name did not match — aborting deletion.")

    client.delete_secret(SecretId=secret_name, ForceDeleteWithoutRecovery=True)
    print()
    print(green(f"✓ Secret '{secret_name}' permanently deleted."))
    return 0


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> int:
    global _USE_COLOR

    parser = argparse.ArgumentParser(
        prog="sm.py",
        description="AWS Secrets Manager utility — create, update, list, or delete secrets.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Modes (choose exactly one):
              <secret-name>        Update an existing secret's JSON value.
              -n <secret-name>     Create a NEW secret (errors if already exists).
              -l [PREFIX]          List all secrets, optionally filtered by prefix.
              -d <secret-name>     Delete a secret (double confirmation required).

            Examples:
              python3 deploy/scripts/util/sm.py midas-dev-us-east-1/frontend
              python3 deploy/scripts/util/sm.py -n my-new-secret
              python3 deploy/scripts/util/sm.py -l
              python3 deploy/scripts/util/sm.py -l midas-dev
              python3 deploy/scripts/util/sm.py -d midas-dev-us-east-1/old-secret
        """),
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "-n", "--new", metavar="SECRET_NAME",
        help="Create a NEW secret. Errors if the secret already exists.",
    )
    mode.add_argument(
        "-l", "--list", nargs="?", const="", metavar="PREFIX",
        help="List secrets. Optional PREFIX filters by name prefix.",
    )
    mode.add_argument(
        "-d", "--delete", metavar="SECRET_NAME",
        help="Delete a secret (force, no recovery window). Double confirmation required.",
    )
    parser.add_argument(
        "secret_name", nargs="?", metavar="SECRET_NAME",
        help="Secret name to update (default mode — secret must already exist).",
    )
    parser.add_argument("--profile", default="default", metavar="PROFILE",
                        help="AWS credentials profile (default: default).")
    parser.add_argument("--region",  default="us-east-1", metavar="REGION",
                        help="AWS region (default: us-east-1).")
    parser.add_argument("--no-color", action="store_true",
                        help="Disable ANSI colour output.")

    args = parser.parse_args()

    if args.no_color:
        _USE_COLOR = False

    # Must have at least one mode
    if args.new is None and args.list is None and args.delete is None and args.secret_name is None:
        parser.print_help()
        return 1

    # Build session
    session = _get_session(args.profile, args.region)
    arn = _sts_check(session, args.region)
    print(bold("AWS identity:"), green(arn))
    print(dim(f"Account region: {args.region}"))
    print()

    client = _sm_client(session, args.region)

    # Dispatch
    if args.new is not None:
        # Grab account id for tagging
        try:
            acct = session.client("sts", region_name=args.region, verify=False).get_caller_identity()["Account"]
        except Exception:
            acct = "unknown"
        return cmd_create(client, args.new, args.region, acct)

    if args.list is not None:
        return cmd_list(client, args.list, args.region)

    if args.delete is not None:
        return cmd_delete(client, args.delete)

    # Default: update existing
    return cmd_update(client, args.secret_name)


if __name__ == "__main__":
    sys.exit(main())
