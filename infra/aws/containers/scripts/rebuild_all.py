#!/usr/bin/env python3
"""Build (and optionally run) all ARB container images from the repository root.

Prefer ``make build-dockers`` (compile + docker). This script remains for compose --up/--down.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parents[4]
_SCRIPTS = _REPO_ROOT / "make"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from build_config import DOCKER_SPECS_BY_ID, REPO_ROOT  # noqa: E402

COMPOSE_FILE = REPO_ROOT / "infra/local-docker-compose/docker-compose.yml"


def _run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=REPO_ROOT, check=check, text=True)


def build_service(name: str, *, no_cache: bool) -> None:
    spec = DOCKER_SPECS_BY_ID[name]
    rel_df = spec.dockerfile.relative_to(REPO_ROOT)
    cmd = [
        "docker",
        "build",
        "-f",
        str(rel_df),
        "-t",
        spec.image,
    ]
    if no_cache:
        cmd.append("--no-cache")
    cmd.append(".")
    _run(cmd)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--service",
        action="append",
        choices=sorted(DOCKER_SPECS_BY_ID),
        help="Build only these services (default: all).",
    )
    parser.add_argument("--no-cache", action="store_true", help="Pass --no-cache to docker build.")
    parser.add_argument(
        "--up",
        action="store_true",
        help="After building, run docker compose up -d (uses compose file under infra/containers/).",
    )
    parser.add_argument(
        "--down",
        action="store_true",
        help="Stop and remove the compose stack (docker compose down).",
    )
    parser.add_argument(
        "--pull",
        action="store_true",
        help="With --up, pass --pull always to compose (refresh base images).",
    )
    args = parser.parse_args()

    if args.down:
        _run(["docker", "compose", "-f", str(COMPOSE_FILE), "down"])
        return 0

    targets = args.service or list(DOCKER_SPECS_BY_ID)
    for name in targets:
        build_service(name, no_cache=args.no_cache)

    if args.up:
        up_cmd = ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d"]
        if args.pull:
            up_cmd.append("--pull")
            up_cmd.append("always")
        _run(up_cmd)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"Command failed with exit code {exc.returncode}", file=sys.stderr)
        raise SystemExit(exc.returncode) from exc
