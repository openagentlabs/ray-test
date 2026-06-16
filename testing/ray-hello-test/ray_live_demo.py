#!/usr/bin/env python3
"""
Live Ray cluster demo — runs on the cluster head pod only (not Ray Client / not local).

Streams task completions as they happen so you can watch workers pick up work
in the dashboard (Actors / Tasks / Cluster) while this script runs.

Run via the wrapper (do not invoke this file directly on your laptop):

  ./ray-hello-test/run_in_cluster.sh --tasks 16 --actors
"""

from __future__ import annotations

import argparse
import os
import random
import socket
import sys
import time
from dataclasses import dataclass

import ray

# Set by run_in_cluster.sh when kubectl exec runs this script inside the head pod.
_IN_CLUSTER_ENV = "RAY_HELLO_TEST_IN_CLUSTER"


@dataclass(frozen=True)
class TaskResult:
    task_id: int
    worker_host: str
    worker_pid: int
    sleep_s: float
    started_at: float
    finished_at: float

    @property
    def duration_s(self) -> float:
        return self.finished_at - self.started_at


@ray.remote
def staggered_work(task_id: int, sleep_s: float) -> TaskResult:
    started = time.time()
    time.sleep(sleep_s)
    return TaskResult(
        task_id=task_id,
        worker_host=socket.gethostname(),
        worker_pid=os.getpid(),
        sleep_s=sleep_s,
        started_at=started,
        finished_at=time.time(),
    )


@ray.remote
class CounterActor:
    def __init__(self, name: str) -> None:
        self.name = name
        self.host = socket.gethostname()
        self.pid = os.getpid()
        self.count = 0

    def increment(self, n: int = 1) -> dict[str, object]:
        self.count += n
        time.sleep(0.15)
        return {
            "actor": self.name,
            "host": self.host,
            "pid": self.pid,
            "count": self.count,
        }


def _assert_running_on_cluster() -> None:
    """Refuse to run as a laptop Ray Client — driver must execute inside the Ray head pod."""
    if os.environ.get(_IN_CLUSTER_ENV) == "1":
        return

    host = socket.gethostname()
    if host.startswith("ray-cluster-"):
        # Invoked manually inside the pod (e.g. kubectl exec) without the wrapper env.
        return

    print(
        "ERROR: This script must run on the Ray cluster, not on your local machine.\n"
        "Use:\n"
        "  ./ray-hello-test/run_in_cluster.sh --tasks 16 --actors\n",
        file=sys.stderr,
    )
    raise SystemExit(1)


def _assert_connected_to_cluster() -> None:
    """Sanity-check we joined the KubeRay cluster (head + workers), not a local single-node Ray."""
    resources = ray.cluster_resources()
    node_keys = [k for k in resources if k.startswith("node:") and k != "node:__internal_head__"]
    if len(node_keys) < 1:
        print(
            "ERROR: ray.init() did not join a multi-node cluster (no worker nodes visible).\n"
            "Run via ./ray-hello-test/run_in_cluster.sh",
            file=sys.stderr,
        )
        raise SystemExit(1)

    driver_host = socket.gethostname()
    if not driver_host.startswith("ray-cluster-"):
        print(
            f"ERROR: Driver hostname {driver_host!r} is not a Ray cluster pod.\n"
            "Run via ./ray-hello-test/run_in_cluster.sh",
            file=sys.stderr,
        )
        raise SystemExit(1)


def _print_cluster_snapshot(label: str) -> None:
    print(f"\n=== {label} ===")
    print(f"  driver pod        : {socket.gethostname()} pid={os.getpid()}")
    resources = ray.cluster_resources()
    print(f"  cluster resources : {resources}")
    nodes = [n for n in ray.nodes() if n.get("Alive")]
    print(f"  alive nodes       : {len(nodes)}")
    for node in nodes:
        addr = node.get("NodeManagerAddress", "?")
        res = node.get("Resources", {})
        cpu = res.get("CPU", 0)
        mem = round(res.get("memory", 0) / (1024**3), 2)
        print(f"    - {addr}  CPU={cpu}  memory={mem} GiB")


def _stream_task_results(
    futures: list[ray.ObjectRef],
    *,
    poll_timeout_s: float,
) -> list[TaskResult]:
    pending = list(futures)
    results: list[TaskResult] = []
    total = len(pending)
    done_count = 0
    t0 = time.time()

    print(f"\nStreaming {total} tasks (ray.wait poll={poll_timeout_s}s)…")
    print("  Open dashboard → Tasks / Cluster to watch workers live.\n")

    while pending:
        ready, pending = ray.wait(pending, num_returns=1, timeout=poll_timeout_s)
        if not ready:
            elapsed = time.time() - t0
            print(f"  … waiting ({done_count}/{total} done, {elapsed:.1f}s elapsed, {len(pending)} in flight)")
            continue

        for ref in ready:
            result = ray.get(ref)
            done_count += 1
            elapsed = time.time() - t0
            bar = "#" * done_count + "-" * (total - done_count)
            print(
                f"  [{bar}] {done_count}/{total} "
                f"task={result.task_id:02d} "
                f"node={result.worker_host} "
                f"pid={result.worker_pid} "
                f"sleep={result.sleep_s:.1f}s "
                f"wall={result.duration_s:.2f}s "
                f"(+{elapsed:.1f}s)"
            )
            results.append(result)

    return results


def _run_task_demo(*, task_count: int, max_stagger: float, poll_timeout_s: float) -> None:
    sleep_times = [random.uniform(0.5, max_stagger) for _ in range(task_count)]
    futures = [staggered_work.remote(i, sleep_s) for i, sleep_s in enumerate(sleep_times)]
    results = _stream_task_results(futures, poll_timeout_s=poll_timeout_s)

    hosts = sorted({r.worker_host for r in results})
    print(f"\nSummary: {len(results)} tasks on {len(hosts)} worker host(s): {', '.join(hosts)}")


def _run_actor_demo(*, actor_count: int, rounds: int) -> None:
    print(f"\nActor demo: {actor_count} actors × {rounds} increments (streaming replies)…")
    actors = [CounterActor.remote(f"counter-{i}") for i in range(actor_count)]
    futures = [actors[i % actor_count].increment.remote(i + 1) for i in range(rounds)]

    pending = list(futures)
    done = 0
    while pending:
        ready, pending = ray.wait(pending, num_returns=1, timeout=0.5)
        for ref in ready:
            payload = ray.get(ref)
            done += 1
            print(
                f"  actor reply {done}/{rounds}: "
                f"{payload['actor']} on {payload['host']} pid={payload['pid']} count={payload['count']}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Live Ray cluster demo (cluster head pod only — use run_in_cluster.sh).",
    )
    parser.add_argument("--tasks", type=int, default=16, help="Number of parallel remote tasks")
    parser.add_argument(
        "--max-stagger",
        type=float,
        default=2.5,
        help="Max random sleep seconds per task (spread finish times)",
    )
    parser.add_argument(
        "--poll",
        type=float,
        default=0.5,
        help="ray.wait timeout seconds between progress prints",
    )
    parser.add_argument(
        "--actors",
        action="store_true",
        help="Also run a short CounterActor streaming demo after tasks",
    )
    parser.add_argument("--actor-count", type=int, default=3)
    parser.add_argument("--actor-rounds", type=int, default=12)
    args = parser.parse_args()

    _assert_running_on_cluster()

    print("Connecting on-cluster (ray.init in head pod) …\n")
    try:
        ray.init(ignore_reinit_error=True, logging_level="warning")
    except ConnectionError as exc:
        print(f"ERROR: ray.init failed: {exc}", file=sys.stderr)
        return 1

    _assert_connected_to_cluster()

    try:
        _print_cluster_snapshot("Cluster at connect")
        _run_task_demo(task_count=args.tasks, max_stagger=args.max_stagger, poll_timeout_s=args.poll)
        if args.actors:
            _run_actor_demo(actor_count=args.actor_count, rounds=args.actor_rounds)
        _print_cluster_snapshot("Cluster at finish")
        print("\nDone. Check the Ray dashboard Tasks/Actors tabs for the run you just drove.")
        return 0
    finally:
        ray.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
