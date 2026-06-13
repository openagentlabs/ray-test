#!/usr/bin/env python3
"""MIDAS S3 test bucket access checker. Full usage: run with --help."""
from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass, field


def _prefix_for(env: str, region: str) -> str:
    return f"midas-{env}-{region}-test-"


@dataclass
class StepResult:
    name: str
    light: str  # 🟢 🟡 🔴
    detail: str
    ok: bool


@dataclass
class RunState:
    steps: list[StepResult] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str, warn: bool = False) -> None:
        if ok:
            light = "🟢"
        elif warn:
            light = "🟡"
        else:
            light = "🔴"
        self.steps.append(StepResult(name=name, light=light, detail=detail, ok=ok))

    def verdict(self) -> tuple[str, bool]:
        if any(s.light == "🔴" for s in self.steps):
            failed = [s.name for s in self.steps if s.light == "🔴"]
            return f"🔴 Blocked - {', '.join(failed)}", False
        if any(s.light == "🟡" for s in self.steps):
            gaps = [s.name for s in self.steps if s.light == "🟡"]
            return f"🟡 Gaps - {', '.join(gaps)}", True
        return "🟢 Ready", True


def _print_step(msg: str) -> None:
    print(f"  → {msg}", flush=True)


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


# Env keys we accept from a pasted AWS / helper block (applied only if missing in os.environ).
_APPLY_KEYS_FROM_PASTE = frozenset(
    {
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
        "S3_BUCKET",
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
    """If terminal already has access keys (or alternate chain), do nothing; else parse paste into env."""
    if _has_explicit_access_keys() or _has_alternate_credential_chain():
        return
    raw = _read_paste_block().strip()
    if not raw:
        return
    parsed = _parse_aws_export_block(raw)
    for k, v in parsed.items():
        if k in _APPLY_KEYS_FROM_PASTE and not (os.environ.get(k) or "").strip():
            os.environ[k] = v


# Shown by: python midas-s3-test-bucket-access.py --help
_HELP_DESCRIPTION = """\
Verify access to the MIDAS Terraform S3 test bucket (deploy/ecs-app/modules/s3) via boto3.

The module creates a bucket with prefix midas-<environment>-<region>-test- (AWS assigns
the suffix). Pass the full bucket name from Terraform output test_bucket_id, or use
--environment to discover the bucket by listing names with that prefix.

Requires: pip install boto3
"""

_HELP_EPILOG = """\
Environment variables (defaults for flags):
  S3_BUCKET              Exact bucket name (same as --bucket).
  MIDAS_ENVIRONMENT, ENVIRONMENT   Tenant env for discovery (default: dev).
  AWS_REGION, AWS_DEFAULT_REGION   Region (default: us-east-1).
  TRAFFIC_LIGHT=1        Print skill-style traffic-light summary to stdout.
  AWS_CA_BUNDLE          Optional path to CA bundle (use with --verify-ssl).

Credentials (in order):
  1. If AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are set (or another chain below),
     those are used and nothing is prompted.
  2. Otherwise you are prompted to paste the export block from the AWS console
     (IAM access keys or temporary credentials), for example:

       export AWS_ACCESS_KEY_ID="..."
       export AWS_SECRET_ACCESS_KEY="..."
       export AWS_SESSION_TOKEN="..."   # if present

     The same paste may include AWS_REGION, S3_BUCKET, or MIDAS_ENVIRONMENT; values
     are applied only for keys that are not already set in the environment.
  3. No paste is requested if AWS_PROFILE is set, or ECS/EC2 role env vars are
     present (AWS_CONTAINER_CREDENTIALS_*, AWS_WEB_IDENTITY_TOKEN_FILE).

Non-interactive paste: pipe the export block on stdin (stdin is not a TTY).

TLS:
  By default server certificates are NOT validated (typical behind corporate SSL
  inspection). Use --verify-ssl to enforce verification.

Examples:
  TRAFFIC_LIGHT=1 ./deploy/scripts/test/midas-s3-test-bucket-access.py --environment dev
  ./deploy/scripts/test/midas-s3-test-bucket-access.py --bucket my-midas-dev-us-east-1-test-abc
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
        "--bucket",
        default=os.environ.get("S3_BUCKET", "").strip() or None,
        help="Exact bucket name (from terraform output test_bucket_id). Overrides discovery.",
    )
    p.add_argument(
        "--environment",
        default=os.environ.get("MIDAS_ENVIRONMENT", os.environ.get("ENVIRONMENT", "dev")),
        help="Tenant environment for prefix midas-<env>-<region>-test-* (default: MIDAS_ENVIRONMENT or dev).",
    )
    p.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1")),
        help="AWS region (default: AWS_REGION / us-east-1).",
    )
    p.add_argument(
        "--verify-ssl",
        action="store_true",
        help="Verify TLS server certificates (default: off).",
    )
    p.add_argument(
        "-q",
        "--quiet-steps",
        action="store_true",
        help="Suppress per-step lines (traffic-light block still prints if TRAFFIC_LIGHT=1).",
    )
    args = p.parse_args()

    traffic_light = os.environ.get("TRAFFIC_LIGHT", "").strip() == "1"

    def log(msg: str) -> None:
        if not args.quiet_steps:
            _print_step(msg)

    state = RunState()

    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
    except ImportError:
        print("Install boto3: pip install boto3", file=sys.stderr)
        return 1

    verify_ssl = args.verify_ssl
    if not verify_ssl:
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # Step: credentials present (informational)
    has_explicit = bool(os.environ.get("AWS_ACCESS_KEY_ID"))
    log(
        "Credentials: using default chain"
        + (" (AWS_ACCESS_KEY_ID is set)" if has_explicit else " (e.g. profile or instance role)")
    )
    state.add(
        "credential_chain",
        True,
        "explicit AWS_ACCESS_KEY_ID" if has_explicit else "default chain (profile/role/env)",
    )

    def s3_client():
        return boto3.client("s3", region_name=args.region, verify=verify_ssl)

    bucket: str | None = args.bucket

    # Resolve bucket name
    if bucket:
        log(f"Using bucket from argument/env: {bucket}")
        state.add("resolve_bucket", True, f"explicit {bucket}")
    else:
        prefix = _prefix_for(args.environment, args.region)
        log(f"Discovering bucket with prefix: {prefix!r}")
        try:
            c = s3_client()
            names = [b["Name"] for b in c.list_buckets().get("Buckets", []) if b["Name"].startswith(prefix)]
        except (ClientError, BotoCoreError, NoCredentialsError) as e:
            log(f"ERROR: {e}")
            state.add("resolve_bucket", False, str(e))
            bucket = None
        else:
            if not names:
                msg = f"no bucket found with prefix {prefix!r}"
                log(f"ERROR: {msg}")
                state.add("resolve_bucket", False, msg)
                bucket = None
            elif len(names) > 1:
                picked = sorted(names)[0]
                log(f"Multiple matches {names!r}; using first sorted: {picked}")
                bucket = picked
                state.add("resolve_bucket", True, f"ambiguous {len(names)} buckets; picked {picked}", warn=True)
            else:
                bucket = names[0]
                log(f"Found bucket: {bucket}")
                state.add("resolve_bucket", True, bucket)

    if not bucket:
        if traffic_light:
            _emit_traffic_light(args, state)
        else:
            v, _ = state.verdict()
            print(f"\nVERDICT: {v}")
        return 1

    # HeadBucket
    log("Calling HeadBucket (s3:HeadBucket / HEAD)...")
    try:
        s3_client().head_bucket(Bucket=bucket)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        status = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        msg = f"{code} HTTP {status} {e}"
        log(f"ERROR: {msg}")
        state.add("head_bucket", False, msg)
    except (BotoCoreError, NoCredentialsError) as e:
        log(f"ERROR: {e}")
        state.add("head_bucket", False, str(e))
    else:
        log("HeadBucket succeeded (bucket exists and principal may access it).")
        state.add("head_bucket", True, "OK")

    # ListObjectsV2 (read path; minimal)
    log("Calling ListObjectsV2 (max 1 key)...")
    try:
        r = s3_client().list_objects_v2(Bucket=bucket, MaxKeys=1)
        n = r.get("KeyCount", 0)
        log(f"ListObjectsV2 OK (KeyCount in page: {n}).")
        state.add("list_objects", True, f"KeyCount={n}")
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        status = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        msg = f"{code} HTTP {status} {e}"
        log(f"ERROR: {msg}")
        state.add("list_objects", False, msg)
    except (BotoCoreError, NoCredentialsError) as e:
        log(f"ERROR: {e}")
        state.add("list_objects", False, str(e))

    ok_final = all(s.ok for s in state.steps if s.name in ("head_bucket", "list_objects", "resolve_bucket"))
    if traffic_light:
        _emit_traffic_light(args, state, bucket)
    elif not args.quiet_steps:
        v, _ = state.verdict()
        print()
        print(f"VERDICT: {v}")

    return 0 if ok_final else 1


def _emit_traffic_light(args: argparse.Namespace, state: RunState, bucket: str | None = None) -> None:
    from datetime import datetime, timezone

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    b = bucket or "(unresolved)"
    print()
    print(f"S3 MODULE BUCKET ACCESS - {today} - {args.region} - bucket [{b}]")
    print()
    print("STEPS")
    for s in state.steps:
        extra = f" - {s.detail}" if s.detail else ""
        print(f"  {s.name} - {s.light}{extra}")
    print()
    print("VERDICT")
    v, _ = state.verdict()
    print(f"  {v}")


if __name__ == "__main__":
    raise SystemExit(main())
