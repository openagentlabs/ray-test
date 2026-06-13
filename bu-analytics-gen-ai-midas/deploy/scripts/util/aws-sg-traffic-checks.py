#!/usr/bin/env python3
"""Read-only AWS CLI checks: security-group ingress vs expected sources (traffic-light tables).

Uses the AWS CLI subprocess (no boto3). Honors the normal credential chain
(~/.aws/credentials, AWS_PROFILE, env vars) - same as after
``deploy/scripts/util/aws-credentials-setup.sh``.

Subcommands:
  laptop      - RDS PostgreSQL + ElastiCache Redis: required source CIDRs allowed?
  jenkins-eks - EKS cluster security group: TCP 443 from Jenkins/Helm CIDR?
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Iterable


def _aws_json(region: str, argv: list[str], *, profile: str | None) -> dict[str, Any]:
    aws = shutil.which("aws")
    if not aws:
        raise RuntimeError("AWS CLI not found on PATH")
    cmd = [aws, "--region", region, "--output", "json", *argv]
    env = os.environ.copy()
    if profile:
        env["AWS_PROFILE"] = profile
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)
    if p.returncode != 0:
        err = (p.stderr or p.stdout or "").strip()
        raise RuntimeError(err or f"aws exited {p.returncode}")
    return json.loads(p.stdout or "{}")


def _parse_networks(cidrs: str) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    out: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for part in cidrs.replace(" ", "").split(","):
        if not part:
            continue
        try:
            out.append(ipaddress.ip_network(part, strict=False))
        except ValueError as e:
            raise SystemExit(f"Invalid CIDR in list: {part!r} ({e})") from e
    if not out:
        raise SystemExit("No CIDRs provided (comma-separated list required)")
    return out


def _rule_covers_port(rule: dict[str, Any], proto: str, port: int) -> bool:
    ip_proto = rule.get("IpProtocol")
    if ip_proto == "-1":
        return True
    if ip_proto != proto:
        return False
    fp = rule.get("FromPort")
    tp = rule.get("ToPort")
    if fp is None or tp is None:
        return False
    return int(fp) <= port <= int(tp)


def _required_subnet_of_rule(
    required: ipaddress.IPv4Network | ipaddress.IPv6Network, rule_cidr: str
) -> bool:
    try:
        rule_net = ipaddress.ip_network(rule_cidr, strict=False)
    except ValueError:
        return False
    if required.version != rule_net.version:
        return False
    # Every address in `required` must lie inside `rule_net` (single-rule check).
    return required.subnet_of(rule_net)


def _ingress_union_allows_cidr(
    ingress: list[dict[str, Any]],
    required: ipaddress.IPv4Network | ipaddress.IPv6Network,
    proto: str,
    port: int,
) -> tuple[bool, str]:
    """True if some rule allows `proto`/`port` from a source CIDR that fully contains `required`."""
    hits: list[str] = []
    for rule in ingress:
        if not _rule_covers_port(rule, proto, port):
            continue
        for pair in rule.get("UserIdGroupPairs") or []:
            gid = pair.get("GroupId")
            if gid:
                hits.append(f"SG-ref:{gid}")
        for r in rule.get("IpRanges") or []:
            cidr = r.get("CidrIp")
            if not cidr:
                continue
            if _required_subnet_of_rule(required, cidr):
                desc = (r.get("Description") or "").strip()
                hits.append(f"{cidr}" + (f" ({desc})" if desc else ""))
    if not hits:
        return False, "no CIDR+port match (SG-only refs do not satisfy laptop CIDR checks)"
    return True, "; ".join(hits[:4]) + (" …" if len(hits) > 4 else "")


def _load_sgs(region: str, sg_ids: Iterable[str], *, profile: str | None) -> dict[str, dict[str, Any]]:
    ids = sorted({x for x in sg_ids if x})
    if not ids:
        return {}
    # describe-security-groups supports up to 200 ids per call
    out: dict[str, dict[str, Any]] = {}
    batch = 100
    for i in range(0, len(ids), batch):
        chunk = ids[i : i + batch]
        data = _aws_json(
            region,
            ["ec2", "describe-security-groups", "--group-ids", *chunk],
            profile=profile,
        )
        for sg in data.get("SecurityGroups") or []:
            out[sg["GroupId"]] = sg
    return out


def _merge_ingress_for_resource(
    sg_map: dict[str, dict[str, Any]], sg_ids: list[str]
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for gid in sg_ids:
        sg = sg_map.get(gid)
        if not sg:
            continue
        merged.extend(sg.get("IpPermissions") or [])
    return merged


@dataclass
class Row:
    resource: str
    rtype: str
    check: str
    expected: str
    light: str
    notes: str


def cmd_laptop(args: argparse.Namespace) -> int:
    region = args.region or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
    cidrs = args.cidrs or os.environ.get("MIDAS_SG_LAPTOP_CIDRS", "10.54.74.117/32,10.54.67.114/32")
    required_nets = _parse_networks(cidrs)
    profile = args.profile or os.environ.get("AWS_PROFILE")

    rds = _aws_json(region, ["rds", "describe-db-instances"], profile=profile)
    ec = _aws_json(
        region,
        ["elasticache", "describe-cache-clusters", "--show-cache-node-info"],
        profile=profile,
    )

    sg_ids: set[str] = set()
    resources: list[tuple[str, str, list[str], str, int]] = []
    # id, type, sg_ids, protocol, port
    for db in rds.get("DBInstances") or []:
        rid = db.get("DBInstanceIdentifier", "?")
        sgs = [x.get("VpcSecurityGroupId") for x in (db.get("VpcSecurityGroups") or []) if x.get("VpcSecurityGroupId")]
        for s in sgs:
            sg_ids.add(s)
        resources.append((rid, "RDS PostgreSQL", sgs, "tcp", 5432))

    for cl in ec.get("CacheClusters") or []:
        cid = cl.get("CacheClusterId", "?")
        sgs = []
        for x in cl.get("SecurityGroups") or []:
            g = x.get("SecurityGroupId")
            if g:
                sgs.append(g)
                sg_ids.add(g)
        if sgs:
            resources.append((cid, "ElastiCache Redis", sgs, "tcp", 6379))

    if not resources:
        print("| Resource | Type | Check | Expected | Light | Notes |")
        print("|----------|------|-------|----------|-------|-------|")
        print("| (none) | - | - | - | 🟡 | No RDS instances or ElastiCache clusters found in this region |")
        return 0

    sg_map = _load_sgs(region, sg_ids, profile=profile)
    rows: list[Row] = []

    for rid, rtype, sgs, proto, port in resources:
        merged = _merge_ingress_for_resource(sg_map, sgs)
        sg_label = ", ".join(sgs) if sgs else "(none)"
        for req in required_nets:
            ok, detail = _ingress_union_allows_cidr(merged, req, proto, port)
            # Yellow if only SG-ref paths matched union? _ingress_union_allows_cidr returns ok True only for CIDR matches
            if ok:
                light = "🟢"
                note = detail[:500]
            else:
                # If SG refs exist but no CIDR, call out yellow-ish message in notes but light red for laptop path
                light = "🔴"
                note = detail
            rows.append(
                Row(
                    resource=rid,
                    rtype=rtype,
                    check=f"Inbound {proto.upper()} {port} (or all) from CIDR ⊇ {req}",
                    expected=str(req),
                    light=light,
                    notes=note[:500],
                )
            )

    print("## Laptop / jump-host security group check (read-only)")
    print()
    print(f"- **Region:** `{region}`")
    print(f"- **Sources tested:** `{cidrs}`")
    print(
        "- **Rule logic:** At least one ingress **CIDR** on the resource’s security groups must **fully contain** "
        "each required source network, and allow **TCP 5432** (RDS) or **TCP 6379** (Redis), or **all traffic** (`-1`). "
        "**Security-group references alone** do not count toward laptop CIDR rows."
    )
    print()
    print("| Resource | Type | Check | Expected source | Light | Notes |")
    print("|----------|------|-------|-----------------|-------|-------|")
    for r in rows:
        print(
            f"| {r.resource} | {r.rtype} | {r.check} | {r.expected} | {r.light} | {r.notes} |".replace("\n", " ")
        )

    bad = sum(1 for r in rows if r.light == "🔴")
    print()
    if bad:
        print(f"**Overall:** 🔴 **Blocked** - {bad} row(s) failed (see 🔴).")
        return 1
    print("**Overall:** 🟢 **OK** - all required CIDRs are allowed for each listed resource (CIDR + port).")
    return 0


def cmd_jenkins_eks(args: argparse.Namespace) -> int:
    region = args.region or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
    cluster = args.cluster or os.environ.get("MIDAS_EKS_CLUSTER_NAME", "midas-eks-dev")
    jenkins_cidr = args.jenkins_cidr or os.environ.get("MIDAS_JENKINS_HELM_CIDR", "10.90.12.0/22")
    profile = args.profile or os.environ.get("AWS_PROFILE")

    try:
        req = ipaddress.ip_network(jenkins_cidr, strict=False)
    except ValueError as e:
        raise SystemExit(f"Invalid Jenkins CIDR: {jenkins_cidr!r} ({e})") from e

    eks = _aws_json(region, ["eks", "describe-cluster", "--name", cluster], profile=profile)
    cfg = (eks.get("cluster") or {}).get("resourcesVpcConfig") or {}
    csg = cfg.get("clusterSecurityGroupId")
    if not csg:
        print("| Check | Expected | Light | Notes |")
        print("|-------|----------|-------|-------|")
        print(f"| EKS API 443 ← Jenkins | `{jenkins_cidr}` → `{cluster}` | 🔴 | No clusterSecurityGroupId on cluster |")
        return 1

    sg_map = _load_sgs(region, [csg], profile=profile)
    sg = sg_map.get(csg) or {}
    merged = sg.get("IpPermissions") or []
    ok, detail = _ingress_union_allows_cidr(merged, req, "tcp", 443)

    print("## Jenkins / Helm → EKS API security group check (read-only)")
    print()
    print(f"- **Region:** `{region}`")
    print(f"- **Cluster:** `{cluster}`")
    print(f"- **Cluster security group:** `{csg}` (`{sg.get('GroupName', '')}`)")
    print(f"- **Required:** TCP **443** from **`{jenkins_cidr}`** (CIDR must **contain** the Jenkins agent network if you pass a wider required net).")
    print()
    print("| Check | Expected | Light | Notes |")
    print("|-------|----------|-------|-------|")
    light = "🟢" if ok else "🔴"
    print(f"| EKS private API (ENI SG) inbound 443 | `{jenkins_cidr}` | {light} | {detail} |")
    print()
    if ok:
        print("**Overall:** 🟢 **OK** - Jenkins/Helm CIDR is permitted on TCP 443 for the EKS cluster security group.")
        return 0
    print("**Overall:** 🔴 **Blocked** - add or fix an ingress rule on the cluster security group.")
    return 1


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("laptop", help="RDS + Redis SG ingress vs laptop CIDRs")
    pl.add_argument("--region", help="AWS region (default: AWS_REGION / AWS_DEFAULT_REGION / us-east-1)")
    pl.add_argument("--profile", help="AWS CLI profile (default: AWS_PROFILE env)")
    pl.add_argument(
        "--cidrs",
        help="Comma-separated required source CIDRs (default: env MIDAS_SG_LAPTOP_CIDRS or MIDAS defaults)",
    )
    pl.set_defaults(func=cmd_laptop)

    pj = sub.add_parser("jenkins-eks", help="EKS cluster SG: TCP 443 from Jenkins CIDR")
    pj.add_argument("--region", help="AWS region (default: AWS_REGION / AWS_DEFAULT_REGION / us-east-1)")
    pj.add_argument("--profile", help="AWS CLI profile (default: AWS_PROFILE env)")
    pj.add_argument("--cluster", help="EKS cluster name (default: env MIDAS_EKS_CLUSTER_NAME or midas-eks-dev)")
    pj.add_argument(
        "--jenkins-cidr",
        help="Jenkins agent / Helm runner CIDR (default: env MIDAS_JENKINS_HELM_CIDR or 10.90.12.0/22)",
    )
    pj.set_defaults(func=cmd_jenkins_eks)

    args = p.parse_args()
    try:
        return int(args.func(args))
    except RuntimeError as e:
        sys.stderr.write(f"ERROR: {e}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
