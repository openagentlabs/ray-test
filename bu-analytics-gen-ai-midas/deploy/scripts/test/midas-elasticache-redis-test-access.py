#!/usr/bin/env python3
"""MIDAS ElastiCache Redis API (and optional PING) checker. Full usage: run with --help."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field


def _replication_group_id_default(environment: str) -> str:
    """Match deploy/ecs-app/modules/elasticache/main.tf local.replication_group_id."""
    return f"midas-{environment}-redis"


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


_APPLY_KEYS_FROM_PASTE = frozenset(
    {
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
        "ELASTICACHE_REPLICATION_GROUP_ID",
        "ELASTICACHE_AUTH_SECRET_ARN",
        "ELASTICACHE_REDIS_AUTH_SECRET_ARN",
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
Verify access to MIDAS ElastiCache for Redis (deploy/ecs-app/modules/elasticache) via boto3.

Terraform sets replication group id to midas-<environment>-redis. Pass
--replication-group-id or set ELASTICACHE_REPLICATION_GROUP_ID, or rely on
--environment (default id: midas-<environment>-redis).

The script calls elasticache:DescribeReplicationGroups. With --redis-ping it also
tries a Redis PING over TLS using the AUTH token from Secrets Manager (requires
network path to the cluster, e.g. same VPC as the cache).

Requires: pip install boto3
Optional (for --redis-ping): pip install redis
"""

_HELP_EPILOG = """\
Environment variables (defaults for flags):
  ELASTICACHE_REPLICATION_GROUP_ID   Override constructed midas-<env>-redis.
  ELASTICACHE_AUTH_SECRET_ARN,
  ELASTICACHE_REDIS_AUTH_SECRET_ARN   Redis AUTH secret (Terraform: elasticache_redis_auth_secret_arn).
  MIDAS_ENVIRONMENT, ENVIRONMENT   Used to build default replication group id (default env: dev).
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

     The same paste may include AWS_REGION or ELASTICACHE_*; values are applied only
     for keys that are not already set in the environment.
  3. No paste is requested if AWS_PROFILE is set, or ECS/EC2 role env vars are
     present (AWS_CONTAINER_CREDENTIALS_*, AWS_WEB_IDENTITY_TOKEN_FILE).

Non-interactive paste: pipe the export block on stdin (stdin is not a TTY).

TLS:
  By default boto3 and redis-py do not verify server certificates (typical behind
  corporate SSL inspection). Use --verify-ssl to enforce verification.

Examples:
  TRAFFIC_LIGHT=1 ./deploy/scripts/test/midas-elasticache-redis-test-access.py --environment dev
  ./deploy/scripts/test/midas-elasticache-redis-test-access.py --replication-group-id midas-dev-redis
  ./deploy/scripts/test/midas-elasticache-redis-test-access.py --environment dev --redis-ping \\
      --auth-secret-arn "$ELASTICACHE_REDIS_AUTH_SECRET_ARN"
"""


def _primary_endpoint_from_rg(rg: dict) -> tuple[str | None, int]:
    """Best-effort primary address/port from DescribeReplicationGroups payload."""
    port = int(rg.get("ConfigurationEndpoint", {}).get("Port") or rg.get("Port") or 6379)
    for ng in rg.get("NodeGroups") or []:
        pe = ng.get("PrimaryEndpoint") or {}
        addr = pe.get("Address")
        if addr:
            p = pe.get("Port")
            return addr, int(p) if p is not None else port
    return None, port


def _load_secret_string(secret_id: str, region: str, *, verify_ssl: bool) -> str:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    sm = boto3.client("secretsmanager", region_name=region, verify=verify_ssl)
    try:
        resp = sm.get_secret_value(SecretId=secret_id)
    except (ClientError, BotoCoreError) as e:
        raise RuntimeError(str(e)) from e
    s = resp.get("SecretString")
    if s is None:
        raise RuntimeError("Secret has no SecretString (expected plaintext AUTH token).")
    s = s.strip()
    if s.startswith("{"):
        try:
            data = json.loads(s)
            if isinstance(data, dict) and "password" in data:
                return str(data["password"])
        except json.JSONDecodeError:
            pass
    return s


def main() -> int:
    if "-h" not in sys.argv and "--help" not in sys.argv:
        _maybe_prompt_aws_export_block()

    p = argparse.ArgumentParser(
        description=_HELP_DESCRIPTION,
        epilog=_HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--replication-group-id",
        default=os.environ.get("ELASTICACHE_REPLICATION_GROUP_ID", "").strip() or None,
        help="ElastiCache replication group id (default: ELASTICACHE_REPLICATION_GROUP_ID or midas-<env>-redis).",
    )
    p.add_argument(
        "--environment",
        default=os.environ.get("MIDAS_ENVIRONMENT", os.environ.get("ENVIRONMENT", "dev")),
        help="Tenant environment for default id midas-<env>-redis (default: MIDAS_ENVIRONMENT or dev).",
    )
    p.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1")),
        help="AWS region (default: AWS_REGION / us-east-1).",
    )
    p.add_argument(
        "--auth-secret-arn",
        default=(
            os.environ.get("ELASTICACHE_REDIS_AUTH_SECRET_ARN", "").strip()
            or os.environ.get("ELASTICACHE_AUTH_SECRET_ARN", "").strip()
            or None
        ),
        help="Secrets Manager ARN for Redis AUTH token (default: ELASTICACHE_REDIS_AUTH_SECRET_ARN or ELASTICACHE_AUTH_SECRET_ARN).",
    )
    p.add_argument(
        "--redis-ping",
        action="store_true",
        help="After DescribeReplicationGroups, connect with redis-py (TLS) and PING (needs --auth-secret-arn and network reachability).",
    )
    p.add_argument(
        "--verify-ssl",
        action="store_true",
        help="Verify TLS for boto3 and redis-py (default: off).",
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

    rg_id = (args.replication_group_id or "").strip() or _replication_group_id_default(args.environment)
    log(f"Using replication group id: {rg_id!r}")

    def ec_client():
        return boto3.client("elasticache", region_name=args.region, verify=verify_ssl)

    log("Calling DescribeReplicationGroups...")
    rg: dict | None = None
    try:
        resp = ec_client().describe_replication_groups(ReplicationGroupId=rg_id)
        rgs = resp.get("ReplicationGroups") or []
        if not rgs:
            msg = "empty ReplicationGroups in response"
            log(f"ERROR: {msg}")
            state.add("describe_replication_group", False, msg)
        else:
            rg = rgs[0]
            status = rg.get("Status", "?")
            detail = f"Status={status}"
            warn = status != "available"
            log(f"DescribeReplicationGroups OK ({detail}).")
            state.add("describe_replication_group", True, detail, warn=warn)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        msg = f"{code} {e}"
        log(f"ERROR: {msg}")
        state.add("describe_replication_group", False, msg)
    except (BotoCoreError, NoCredentialsError) as e:
        log(f"ERROR: {e}")
        state.add("describe_replication_group", False, str(e))

    primary_host: str | None = None
    primary_port = 6379
    if rg:
        primary_host, primary_port = _primary_endpoint_from_rg(rg)
        if primary_host:
            log(f"Primary endpoint (from API): {primary_host}:{primary_port}")

    redis_ping_ok: bool | None = None
    if args.redis_ping:
        if not args.auth_secret_arn:
            log("ERROR: --redis-ping requires --auth-secret-arn (or ELASTICACHE_*_AUTH_SECRET_ARN).")
            state.add("redis_ping", False, "missing auth secret ARN")
            redis_ping_ok = False
        elif not primary_host:
            log("ERROR: could not read primary endpoint from API response; cannot PING.")
            state.add("redis_ping", False, "no primary endpoint in DescribeReplicationGroups")
            redis_ping_ok = False
        else:
            try:
                password = _load_secret_string(args.auth_secret_arn, args.region, verify_ssl=verify_ssl)
            except RuntimeError as e:
                log(f"ERROR: Secrets Manager: {e}")
                state.add("redis_ping", False, str(e))
                redis_ping_ok = False
            else:
                try:
                    import redis
                except ImportError:
                    log("ERROR: pip install redis")
                    state.add("redis_ping", False, "redis package not installed")
                    redis_ping_ok = False
                else:
                    import ssl as ssl_module

                    cert_reqs = ssl_module.CERT_REQUIRED if verify_ssl else ssl_module.CERT_NONE
                    log(f"Redis PING via TLS to {primary_host!r}:{primary_port}...")
                    try:
                        r = redis.Redis(
                            host=primary_host,
                            port=primary_port,
                            password=password,
                            ssl=True,
                            ssl_cert_reqs=cert_reqs,
                            socket_connect_timeout=10,
                            socket_timeout=10,
                        )
                        r.ping()
                    except Exception as e:
                        log(f"ERROR: {e}")
                        state.add("redis_ping", False, str(e))
                        redis_ping_ok = False
                    else:
                        log("PING OK (TLS).")
                        state.add("redis_ping", True, "PONG")
                        redis_ping_ok = True

    critical = ("describe_replication_group",)
    if args.redis_ping:
        critical = ("describe_replication_group", "redis_ping")

    ok_final = all(s.ok for s in state.steps if s.name in critical)

    if traffic_light:
        _emit_traffic_light(args, state, rg_id, primary_host, primary_port)
    elif not args.quiet_steps:
        v, _ = state.verdict()
        print()
        print(f"VERDICT: {v}")

    return 0 if ok_final else 1


def _emit_traffic_light(
    args: argparse.Namespace,
    state: RunState,
    rg_id: str,
    primary_host: str | None,
    primary_port: int,
) -> None:
    from datetime import datetime, timezone

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ep = f"{primary_host}:{primary_port}" if primary_host else "(unknown)"
    print()
    print(f"ELASTICACHE REDIS - {today} - {args.region} - replication group [{rg_id}] - primary [{ep}]")
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
