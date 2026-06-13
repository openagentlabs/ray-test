#!/usr/bin/env python3
"""Parse raw SSM probe stdout (eks-ssm-endpoint-check / eks-private-endpoints-probe) into kt_check_endpoint_for_eks_node_attach report format."""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timezone

RFC1918 = (
    re.compile(r"^10\."),
    re.compile(r"^172\.(1[6-9]|2[0-9]|3[0-1])\."),
    re.compile(r"^192\.168\."),
)


def is_private_ip(ip: str) -> bool:
    return any(p.match(ip) for p in RFC1918)


def classify_dns(body: str) -> tuple[str, str]:
    if re.search(r"Can't find|NXDOMAIN|Could not resolve|no answer", body, re.I):
        return "🔴", "no usable DNS answer"
    lines = body.splitlines()
    ipv4s: list[str] = []
    for ln in lines:
        m = re.match(r"^\s*Address:\s+([0-9.]+)\s*$", ln)
        if m:
            ip = m.group(1)
            if ip != "127.0.0.53":
                ipv4s.append(ip)
    if not ipv4s:
        return "🟡", "no IPv4 in snippet (IPv6-only or empty)"
    priv = [x for x in ipv4s if is_private_ip(x)]
    if len(priv) == len(ipv4s):
        return "🟢", f"private ({priv[0].rsplit('.', 1)[0]}.*)"
    if priv:
        return "🟡", "mixed public/private answers"
    return "🟡", "public AWS IPs"


def classify_https(body: str) -> tuple[str, str]:
    curl_m = re.search(r"curl: \((\d+)\)", body)
    curl_code = int(curl_m.group(1)) if curl_m else None
    hc_m = re.search(r"http_code=(\d+)", body)
    http_code = int(hc_m.group(1)) if hc_m else 0

    if curl_code == 60:
        return "🟡", "cert SAN mismatch (curl 60)"
    if curl_code is not None and curl_code != 60:
        return "🔴", f"curl {curl_code}"
    if 200 <= http_code < 600:
        return "🟢", f"HTTP {http_code}"
    return "🔴", "no successful TLS/HTTP response"


def verdict(entries: list[tuple[str, str, str, str]]) -> str:
    reds = [h for h, d, s, _ in entries if "🔴" in d or "🔴" in s]
    ambers = [h for h, d, s, _ in entries if "🟡" in d or "🟡" in s]
    if reds:
        return f"🔴 Blocked - {', '.join(reds)}"
    if ambers:
        return f"🟡 Gaps - {', '.join(ambers)}"
    return "🟢 Ready"


def main() -> None:
    raw = sys.stdin.read()
    parts = re.split(r"^=== (.+?) ===\s*$", raw, flags=re.MULTILINE)
    if len(parts) < 3:
        print("No === host === blocks found in stdin.", file=sys.stderr)
        sys.exit(1)

    entries: list[tuple[str, str, str, str]] = []
    # parts[0] = header noise; then (host, body) pairs
    for i in range(1, len(parts), 2):
        host = parts[i].strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        dns, dns_note = classify_dns(body)
        https, https_note = classify_https(body)
        note_bits = []
        if dns != "🟢":
            note_bits.append(dns_note)
        if https != "🟢":
            note_bits.append(https_note)
        note = " - ".join(note_bits) if note_bits else ""
        entries.append((host, dns, https, note))

    region = os.environ.get("PROBE_REGION", "us-east-1")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    probe = os.environ.get("PROBE_INSTANCE_ID", "i-xxxx")
    cmd_id = os.environ.get("SSM_COMMAND_ID", "").strip()
    cmd = f" - CommandId [{cmd_id}]" if cmd_id else ""

    print(f"EKS ENDPOINT CHECK (NO CLUSTER) - {today} - {region} - probe [{probe}]{cmd}")
    print()
    print("ENDPOINTS")
    for host, dns, https, note in entries:
        extra = f" - {note}" if note else ""
        print(f"  {host} - DNS {dns} - HTTPS {https}{extra}")

    print()
    print("VERDICT")
    print(f"  {verdict(entries)}")


if __name__ == "__main__":
    main()
