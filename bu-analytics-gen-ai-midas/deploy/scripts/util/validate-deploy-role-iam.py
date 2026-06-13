#!/usr/bin/env python3
"""
Validate midas-deployer-role IAM policy layout: repo files vs Terraform expectations,
and optionally live AWS attachments (us-east-1).

Repo checks (no AWS credentials):
  - Exactly 10 files: midas-deployer-policy-001 .. 010 under deploy/deploy_role/iam-policy/
  - Valid JSON, each compact document <= 6144 chars
  - Unique Sid across all statements

AWS checks (optional, needs valid credentials + iam:ListAttachedRolePolicies):
  python3 validate-deploy-role-iam.py --aws --role-name midas-deployer-role --account-id 811391286931

Exit 0 if all checks pass; non-zero otherwise.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

MAX_POLICY_CHARS = 6144
EXPECTED_COUNT = 10
POLICY_GLOB = "midas-deployer-policy-*"


def repo_root() -> Path:
    p = Path(__file__).resolve()
    # deploy/scripts/util/ -> repo root
    return p.parents[3]


def policy_dir() -> Path:
    return repo_root() / "deploy" / "deploy_role" / "iam-policy"


def validate_repo() -> list[str]:
    errors: list[str] = []
    base = policy_dir()
    if not base.is_dir():
        return [f"Missing directory: {base}"]

    files = sorted(base.glob(POLICY_GLOB))
    if len(files) != EXPECTED_COUNT:
        errors.append(
            f"Expected {EXPECTED_COUNT} files matching {POLICY_GLOB}, found {len(files)}: "
            + ", ".join(f.name for f in files)
        )

    expected_names = {f"midas-deployer-policy-{i:03d}" for i in range(1, EXPECTED_COUNT + 1)}
    actual_names = {f.stem for f in files}
    missing = expected_names - actual_names
    extra = actual_names - expected_names
    if missing:
        errors.append(f"Missing policy files: {sorted(missing)}")
    if extra:
        errors.append(f"Unexpected policy files (wrong name pattern?): {sorted(extra)}")

    all_sids: list[str] = []
    for f in files:
        try:
            doc = json.loads(f.read_text())
        except json.JSONDecodeError as e:
            errors.append(f"{f.name}: invalid JSON: {e}")
            continue
        if doc.get("Version") != "2012-10-17":
            errors.append(f"{f.name}: Version should be 2012-10-17")
        stmts = doc.get("Statement")
        if not isinstance(stmts, list) or not stmts:
            errors.append(f"{f.name}: Statement must be a non-empty list")
            continue
        compact = json.dumps(doc, separators=(",", ":"))
        if len(compact) > MAX_POLICY_CHARS:
            errors.append(
                f"{f.name}: compact JSON length {len(compact)} exceeds AWS limit {MAX_POLICY_CHARS}"
            )
        seen_local: set[str] = set()
        for st in stmts:
            sid = st.get("Sid", "")
            if sid in seen_local:
                errors.append(f"{f.name}: duplicate Sid inside file: {sid!r}")
            seen_local.add(sid)
            if sid:
                all_sids.append(sid)

    dup_global = {s for s in all_sids if all_sids.count(s) > 1}
    if dup_global:
        errors.append(f"Duplicate Sid across repo (should be unique): {sorted(dup_global)}")

    return errors


def expected_managed_policy_names(role_name: str) -> list[str]:
    return [f"{role_name}-midas-deployer-policy-{i:03d}" for i in range(1, EXPECTED_COUNT + 1)]


def validate_aws(role_name: str, region: str, expect_account: str | None) -> list[str]:
    errors: list[str] = []
    try:
        out = subprocess.run(
            [
                "aws",
                "iam",
                "list-attached-role-policies",
                "--role-name",
                role_name,
                "--region",
                region,
                "--output",
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError:
        return ["aws CLI not found; install AWS CLI v2 or skip --aws"]

    if out.returncode != 0:
        return [f"AWS API error: {out.stderr.strip() or out.stdout.strip()}"]

    data = json.loads(out.stdout)
    attached = {p["PolicyName"]: p["PolicyArn"] for p in data.get("AttachedPolicies", [])}
    expected = set(expected_managed_policy_names(role_name))
    missing = sorted(expected - attached.keys())
    unexpected = sorted(attached.keys() - expected)

    if missing:
        errors.append(
            "Attached policies missing (expected Terraform-managed names): " + ", ".join(missing)
        )
    if unexpected:
        errors.append(
            "Unexpected policies on role (old bundles or drift?): " + ", ".join(unexpected)
        )
    if len(attached) != EXPECTED_COUNT and not missing and not unexpected:
        errors.append(f"Expected exactly {EXPECTED_COUNT} matching attachments, got {len(attached)}")

    if expect_account:
        for name, arn in attached.items():
            m = re.match(r"arn:aws:iam::(\d+):policy/", arn)
            if m and m.group(1) != expect_account:
                errors.append(
                    f"Policy {name} ARN account {m.group(1)} != expected {expect_account}"
                )

    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--aws",
        action="store_true",
        help="Also check live IAM attachments via AWS CLI",
    )
    ap.add_argument(
        "--role-name",
        default="midas-deployer-role",
        help="IAM role name (must match Jenkins -var role_name)",
    )
    ap.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region for IAM API",
    )
    ap.add_argument(
        "--account-id",
        default="",
        help="If set, verify policy ARNs use this account id",
    )
    args = ap.parse_args()
    expect_account = args.account_id.strip() or None

    print("=== Repo: deploy/deploy_role/iam-policy (Terraform fileset source) ===")
    errs = validate_repo()
    if errs:
        for e in errs:
            print(f"FAIL: {e}")
        return 1
    print(f"OK: {EXPECTED_COUNT} policy files, all JSON valid, <= {MAX_POLICY_CHARS} chars, Sids unique.")

    print("\n=== Terraform expectation ===")
    print(f"Resource aws_iam_role.deployer_role name = var.role_name (Jenkins: {args.role_name!r})")
    print("Resource aws_iam_role_policy_attachment.deployer_policies: one attachment per file above")
    for n in expected_managed_policy_names(args.role_name):
        print(f"  - Managed policy name: {n}")

    if args.aws:
        print(f"\n=== AWS: list-attached-role-policies --role-name {args.role_name} ===")
        aws_errs = validate_aws(args.role_name, args.region, expect_account)
        if aws_errs:
            for e in aws_errs:
                print(f"FAIL: {e}")
            return 1
        print(f"OK: role has the expected {EXPECTED_COUNT} midas-deployer-policy-* attachments.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
