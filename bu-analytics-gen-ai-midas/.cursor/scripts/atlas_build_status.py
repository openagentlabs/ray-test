#!/usr/bin/env python3
"""Append the current Jenkins build to an Atlas build-status feed.

Run from a Jenkins stage at the end of a deploy. The output JSON is the
contract Atlas reads (see atlas/agent/REMOTE_INTEGRATIONS.md).

Example:

  python3 .cursor/scripts/atlas_build_status.py \\
      --job "${JOB_NAME}" \\
      --build "${BUILD_NUMBER}" \\
      --result "${currentBuild.result ?: 'SUCCESS'}" \\
      --branch "${GIT_BRANCH}" \\
      --commit "${GIT_COMMIT}" \\
      --url "${BUILD_URL}" \\
      --out build-status.json \\
      --history-keep 20

The script keeps Atlas-side decoupling: it only writes a JSON file. How
the file is published (S3, Pages, archived artifact) is an environment
choice.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

JENKINS_TO_ATLAS_RESULT: dict[str, str] = {
    "SUCCESS": "success",
    "FAILURE": "failure",
    "UNSTABLE": "unstable",
    "ABORTED": "aborted",
    "NOT_BUILT": "unknown",
    "IN_PROGRESS": "in_progress",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--job", required=True, help="Jenkins JOB_NAME")
    p.add_argument("--build", required=True, help="Jenkins BUILD_NUMBER")
    p.add_argument("--result", required=True, help="Jenkins build result (SUCCESS|FAILURE|...)")
    p.add_argument("--branch", default="", help="Source branch (e.g. GIT_BRANCH)")
    p.add_argument("--commit", default="", help="Source commit SHA (e.g. GIT_COMMIT)")
    p.add_argument("--url", default="", help="Build web URL (e.g. BUILD_URL)")
    p.add_argument("--duration-ms", type=int, default=0, help="Build duration in milliseconds")
    p.add_argument("--source", default="", help="Optional 'source' field for the feed (free-form id)")
    p.add_argument("--out", required=True, type=Path, help="Path to build-status.json (read+write)")
    p.add_argument("--history-keep", type=int, default=20, help="Number of most recent builds to keep")
    return p.parse_args()


def normalize_result(raw: str) -> str:
    key = (raw or "").strip().upper()
    return JENKINS_TO_ATLAS_RESULT.get(key, "unknown")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_existing(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    builds = data.get("builds")
    if not isinstance(builds, list):
        return []
    return [b for b in builds if isinstance(b, dict)]


def main() -> int:
    args = parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    entry: dict[str, Any] = {
        "id": str(args.build),
        "name": f"{args.job} #{args.build}",
        "result": normalize_result(args.result),
        "finishedAt": now_iso(),
    }
    if args.branch:
        entry["branch"] = args.branch
    if args.commit:
        entry["commitSha"] = args.commit
    if args.url:
        entry["url"] = args.url
    if args.duration_ms > 0:
        entry["durationMs"] = args.duration_ms

    existing = load_existing(args.out)
    existing = [b for b in existing if b.get("id") != entry["id"]]
    builds = [entry, *existing][: max(1, args.history_keep)]

    feed: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": now_iso(),
        "builds": builds,
    }
    source = args.source or os.environ.get("ATLAS_FEED_SOURCE", "")
    if source:
        feed["source"] = source

    args.out.write_text(json.dumps(feed, indent=2) + "\n", encoding="utf-8")
    print(f"[atlas_build_status] wrote {len(builds)} build(s) to {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
