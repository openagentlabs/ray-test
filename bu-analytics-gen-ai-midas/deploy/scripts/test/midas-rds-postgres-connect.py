#!/usr/bin/env python3
"""Connect to MIDAS PostgreSQL via RDS master secret. Full usage: run with --help."""
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


# Env keys accepted from a pasted AWS / helper block (applied only if missing or empty in os.environ).
_APPLY_KEYS_FROM_PASTE = frozenset(
    {
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
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


# Shown by: python midas-rds-postgres-connect.py --help
_HELP_DESCRIPTION = """\
Connect to MIDAS PostgreSQL RDS using the master password secret in Secrets Manager.

The script does not take a secret id: it finds the MIDAS RDS instance created by
deploy/ecs-app/modules/rds (identifier prefix midas-<environment>-<region>-pg-, see
main.tf), reads MasterUserSecret.SecretArn from the RDS API, then fetches the
secret (same source as Terraform output rds_postgres_master_user_secret_arn).

Your host must reach the RDS endpoint on port 5432 (VPN, SSM tunnel, or same VPC)
and call RDS + Secrets Manager in the target region.

Requires: pip install "psycopg[binary]" boto3
"""

_HELP_EPILOG = """\
Environment variables (defaults for flags):
  MIDAS_ENVIRONMENT, ENVIRONMENT   Tenant label for DB identifier prefix (default: dev).
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

     The same paste may include AWS_REGION or MIDAS_ENVIRONMENT; values are applied only
     for keys that are not already set in the environment.
  3. No paste is requested if AWS_PROFILE is set, or ECS/EC2 role env vars are
     present (AWS_CONTAINER_CREDENTIALS_*, AWS_WEB_IDENTITY_TOKEN_FILE).

Non-interactive paste: pipe the export block on stdin (stdin is not a TTY).

TLS:
  By default TLS server certificates are NOT validated for boto3 (Secrets Manager and RDS
  API clients), typical behind corporate SSL inspection. Use --verify-ssl to enforce
  verification. PostgreSQL still uses libpq sslmode from --sslmode (default: require).

Examples:
  ./deploy/scripts/test/midas-rds-postgres-connect.py -v
  ./deploy/scripts/test/midas-rds-postgres-connect.py --environment dev --region us-east-1 -v
"""


def load_secret(
    secret_id: str,
    region: str,
    *,
    verify_tls: bool,
) -> dict:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    client = boto3.client("secretsmanager", region_name=region, verify=verify_tls)
    try:
        resp = client.get_secret_value(SecretId=secret_id)
    except (ClientError, BotoCoreError) as e:
        raise RuntimeError(str(e)) from e
    return json.loads(resp["SecretString"])


def _rds_instance_identifier_prefix(environment: str, aws_region: str) -> str:
    """Match deploy/ecs-app/modules/rds/main.tf: identifier_prefix = \"${local.name_prefix}-pg-\"."""
    return f"midas-{environment}-{aws_region}-pg-"


def resolve_midas_rds_master_secret_arn(
    environment: str,
    region: str,
    *,
    verify_tls: bool,
) -> tuple[str, str, bool]:
    """Find Secrets Manager ARN for the RDS master user (manage_master_user_password) for the MIDAS module instance.

    Returns (secret_arn, db_instance_identifier, ambiguous_multiple_matches).
    """
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    prefix = _rds_instance_identifier_prefix(environment, region)
    rds = boto3.client("rds", region_name=region, verify=verify_tls)
    matches: list[tuple[str, str]] = []
    try:
        paginator = rds.get_paginator("describe_db_instances")
        for page in paginator.paginate():
            for inst in page.get("DBInstances", []):
                iid = inst.get("DBInstanceIdentifier") or ""
                if not iid.startswith(prefix):
                    continue
                mus = inst.get("MasterUserSecret") or {}
                arn = mus.get("SecretArn")
                if arn:
                    matches.append((iid, arn))
    except (ClientError, BotoCoreError) as e:
        raise RuntimeError(str(e)) from e

    if not matches:
        raise RuntimeError(
            f"No RDS instance found with DBInstanceIdentifier starting with {prefix!r} "
            f"(expected deploy/ecs-app/modules/rds). Ensure rds_postgres_enabled is true and the "
            f"instance exists in region {region!r}."
        )
    matches.sort(key=lambda x: x[0])
    ambiguous = len(matches) > 1
    return matches[0][1], matches[0][0], ambiguous


def _rds_endpoint_from_instance_id(
    db_instance_identifier: str,
    region: str,
    *,
    verify_tls: bool,
) -> tuple[str, int, str | None]:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    rds = boto3.client("rds", region_name=region, verify=verify_tls)
    try:
        resp = rds.describe_db_instances(DBInstanceIdentifier=db_instance_identifier)
    except (ClientError, BotoCoreError) as e:
        raise RuntimeError(str(e)) from e
    inst = resp["DBInstances"][0]
    ep = inst["Endpoint"]
    return ep["Address"], int(ep["Port"]), inst.get("DBName")


def _rds_endpoint_from_master_secret_arn(
    master_secret_arn: str,
    region: str,
    *,
    verify_tls: bool,
) -> tuple[str, int, str | None]:
    """Resolve host/port/dbname when the secret JSON omits them (match RDS instance by MasterUserSecret)."""
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    rds = boto3.client("rds", region_name=region, verify=verify_tls)
    try:
        paginator = rds.get_paginator("describe_db_instances")
        for page in paginator.paginate():
            for inst in page.get("DBInstances", []):
                mus = inst.get("MasterUserSecret") or {}
                if mus.get("SecretArn") == master_secret_arn:
                    ep = inst["Endpoint"]
                    return ep["Address"], int(ep["Port"]), inst.get("DBName")
    except (ClientError, BotoCoreError) as e:
        raise RuntimeError(str(e)) from e
    raise RuntimeError(
        "Could not find an RDS DB instance whose MasterUserSecret.SecretArn matches this secret. "
        "Check IAM rds:DescribeDBInstances and that the secret is the instance master secret."
    )


def normalize_rds_secret(
    secret: dict,
    *,
    secret_arn: str,
    region: str,
    verify_tls: bool,
) -> dict:
    """Merge alternate JSON keys and fill host/port/dbname from RDS API when missing."""

    def _missing_endpoint(od: dict) -> bool:
        h = od.get("host") or od.get("hostname") or od.get("endpoint")
        p = od.get("port")
        dbn = od.get("dbname") or od.get("database") or od.get("db_name")
        return not h or p is None or not dbn

    out = dict(secret)
    if not _missing_endpoint(out):
        return out

    ident = out.get("dbInstanceIdentifier") or out.get("db_instance_identifier")
    if ident:
        h, p, db = _rds_endpoint_from_instance_id(ident, region, verify_tls=verify_tls)
        if not (out.get("host") or out.get("hostname") or out.get("endpoint")):
            out["host"] = h
        if out.get("port") is None:
            out["port"] = p
        if not (out.get("dbname") or out.get("database") or out.get("db_name")):
            out["dbname"] = db

    if not _missing_endpoint(out):
        return out

    h, p, db = _rds_endpoint_from_master_secret_arn(secret_arn, region, verify_tls=verify_tls)
    if not (out.get("host") or out.get("hostname") or out.get("endpoint")):
        out["host"] = h
    if out.get("port") is None:
        out["port"] = p
    if not (out.get("dbname") or out.get("database") or out.get("db_name")):
        out["dbname"] = db

    return out


def connect_kwargs_from_rds_secret(secret: dict, *, sslmode: str) -> dict:
    """Keyword args for psycopg.connect; RDS-managed secrets include host, port, dbname, username, password."""
    try:
        host = secret.get("host") or secret.get("hostname") or secret.get("endpoint")
        port = secret.get("port")
        dbname = secret.get("dbname") or secret.get("database") or secret.get("db_name")
        user = secret["username"]
        password = secret["password"]
    except KeyError as e:
        raise KeyError(f"Missing key in RDS secret JSON: {e}") from e
    if not host:
        raise KeyError("host (or hostname/endpoint) is missing after RDS resolution")
    if port is None:
        port = 5432
    if not dbname:
        raise KeyError("dbname (or database) is missing after RDS resolution")

    return {
        "host": host,
        "port": int(port) if not isinstance(port, int) else port,
        "dbname": dbname,
        "user": user,
        "password": password,
        "sslmode": sslmode,
    }


def main() -> int:
    if "-h" not in sys.argv and "--help" not in sys.argv:
        _maybe_prompt_aws_export_block()

    p = argparse.ArgumentParser(
        description=_HELP_DESCRIPTION,
        epilog=_HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--environment",
        default=os.environ.get("MIDAS_ENVIRONMENT", os.environ.get("ENVIRONMENT", "dev")),
        help="Tenant environment for RDS identifier prefix midas-<env>-<region>-pg-* (default: MIDAS_ENVIRONMENT or dev).",
    )
    p.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1")),
        help="AWS region (default: AWS_REGION or us-east-1).",
    )
    p.add_argument(
        "--sql",
        default="SELECT current_database() AS db, current_user AS user, version() AS version;",
        help="SQL to run after connecting (default: show db, user, version).",
    )
    p.add_argument(
        "--sslmode",
        default="require",
        help="libpq sslmode for PostgreSQL (default: require). Use verify-full for stricter TLS.",
    )
    p.add_argument(
        "--verify-ssl",
        action="store_true",
        help="Verify TLS for boto3 Secrets Manager and RDS API clients (default: off).",
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print connection hints to stderr (never prints the password).",
    )
    args = p.parse_args()

    verify_sm = args.verify_ssl
    if not verify_sm:
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    try:
        import psycopg
    except ImportError:
        print('Install: pip install "psycopg[binary]" boto3', file=sys.stderr)
        return 1

    try:
        secret_arn, db_instance_id, ambiguous = resolve_midas_rds_master_secret_arn(
            args.environment,
            args.region,
            verify_tls=verify_sm,
        )
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1

    if ambiguous:
        print(
            f"Warning: multiple RDS instances match prefix { _rds_instance_identifier_prefix(args.environment, args.region)!r}; "
            f"using {db_instance_id!r}.",
            file=sys.stderr,
        )

    try:
        raw_secret = load_secret(secret_arn, args.region, verify_tls=verify_sm)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1

    try:
        secret = normalize_rds_secret(
            raw_secret,
            secret_arn=secret_arn,
            region=args.region,
            verify_tls=verify_sm,
        )
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1

    if args.verbose:
        host = secret.get("host") or secret.get("hostname") or secret.get("endpoint") or "?"
        port = secret.get("port", "?")
        dbn = secret.get("dbname") or secret.get("database") or "?"
        user = secret.get("username", "?")
        print(
            f"db_instance_id={db_instance_id!r} master_secret_arn={secret_arn!r} region={args.region} "
            f"host={host!r} port={port!r} dbname={dbn!r} user={user!r} sslmode={args.sslmode}",
            file=sys.stderr,
        )

    try:
        kwargs = connect_kwargs_from_rds_secret(secret, sslmode=args.sslmode)
    except KeyError as e:
        print(str(e), file=sys.stderr)
        return 1

    try:
        conn = psycopg.connect(**kwargs)
    except Exception as e:
        print(f"FAILED: Could not connect to RDS PostgreSQL: {e}", file=sys.stderr)
        return 1

    print(
        f"OK: Connected to RDS PostgreSQL at {kwargs['host']}:{kwargs['port']} "
        f"database {kwargs['dbname']!r}.",
        file=sys.stderr,
    )

    rows: list | None = None
    colnames: list[str] | None = None
    try:
        with conn.cursor() as cur:
            cur.execute(args.sql)
            if cur.description:
                rows = cur.fetchall()
                colnames = [d.name for d in cur.description]
            else:
                conn.commit()
                if args.verbose:
                    print(f"statement complete (rowcount={cur.rowcount})", file=sys.stderr)
                return 0
    except Exception as e:
        print(f"FAILED: RDS PostgreSQL query failed (after connect): {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    assert rows is not None and colnames is not None
    print("\t".join(colnames))
    for row in rows:
        print("\t".join(str(x) for x in row))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
