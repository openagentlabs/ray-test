#!/usr/bin/env python3
"""Distributed Ray hello-world — submit via the dashboard Jobs API on the ALB."""

from __future__ import annotations

import os
import socket
import time

import ray


@ray.remote
def work(task_id: int) -> str:
    hostname = socket.gethostname()
    time.sleep(1)
    return f"task={task_id} node={hostname} pid={os.getpid()}"


def main() -> None:
    ray.init()
    print(f"Ray cluster resources: {ray.cluster_resources()}")
    print(f"Connected nodes: {len(ray.nodes())}")

    futures = [work.remote(i) for i in range(8)]
    results = ray.get(futures)

    print("Results from workers:")
    for line in results:
        print(f"  {line}")

    nodes = {line.split("node=")[1].split()[0] for line in results}
    print(f"Distinct worker hostnames: {sorted(nodes)}")


if __name__ == "__main__":
    main()
