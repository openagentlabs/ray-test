#!/usr/bin/env python3
"""Post-Terraform: build, ECR push, Helm rollout, LoadBalancer validation for an APP_ENV."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
for p in (REPO_ROOT / "make", Path(__file__).resolve().parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from build_config import PROFILES_BY_NAME  # noqa: E402
import deploy_lib  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("env", choices=["dev", "test", "prod"])
    parser.add_argument("--image-tag", default="")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--helm-stable-timeout", type=int, default=900)
    parser.add_argument("--alb-timeout", type=int, default=600)
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()

    profile = PROFILES_BY_NAME[args.env]
    image_tag = args.image_tag or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    tf_outputs = deploy_lib.run_json(["terraform", "output", "-json"], cwd=deploy_lib.TF_DIR)
    ecr_urls = tf_outputs.get("containers_ecr_repository_urls", {}).get("value") or {}
    if not ecr_urls:
        print("No ECR URLs — run terraform apply first.", file=sys.stderr)
        return 1

    phases: list[tuple[str, object]] = []
    if not args.skip_build:
        phases.append(("build", lambda: deploy_lib.phase_build_images(no_cache=args.no_cache)))
    phases.extend(
        [
            ("ecr_push", lambda: deploy_lib.phase_ecr_push(ecr_urls, image_tag)),
            (
                "helm_rollout",
                lambda: deploy_lib.phase_helm_rollout(
                    tf_outputs,
                    stable_timeout_s=args.helm_stable_timeout,
                    workload_keys=sorted(ecr_urls.keys()),
                ),
            ),
            ("aws_validate", lambda: deploy_lib.phase_aws_validate(tf_outputs, alb_timeout_s=args.alb_timeout)),
        ],
    )
    _, code = deploy_lib.run_phases([(n, fn) for n, fn in phases])  # type: ignore[arg-type]
    return code


if __name__ == "__main__":
    raise SystemExit(main())
