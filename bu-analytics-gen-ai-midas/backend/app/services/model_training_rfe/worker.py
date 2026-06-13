"""
RFE worker loop - entrypoint for a standalone worker container.

Launch:
    python -m app.services.model_training_rfe.worker

What it does:
    - Reads env (RFE_SCALING_MODE=redis, REDIS_URL=...)
    - BLPOPs `rfe:queue` for a job_id (5s timeout, loops forever)
    - For each job_id, instantiates RfeService(worker_context=True) and runs it.
    - On terminal error, logs and keeps looping (never crashes the pod).

`worker_context=True` flag tells TrainingDataProvider to prefer the shared
`train.parquet` rather than the in-memory DFSM (which is empty in a fresh
worker pod). That's the mechanism that makes multi-worker mode work without
cross-process shared memory.
"""

from __future__ import annotations

import signal
import time

from app.core.logging_config import get_logger

from .backends import get_backends
from .rfe_service import RfeService

_logger = get_logger(__name__)

_SHOULD_STOP = False


def _handle_term(signum, frame):  # noqa: ARG001 - unused args part of signal ABI
    global _SHOULD_STOP
    _logger.info("RFE worker received signal %s - stopping after current job", signum)
    _SHOULD_STOP = True


def run_worker_loop(poll_timeout_sec: float = 5.0) -> None:
    storage, state, bus, queue, mode = get_backends()
    _logger.info("RFE worker starting (mode=%s)", mode)
    while not _SHOULD_STOP:
        try:
            job_id = queue.dequeue(timeout=poll_timeout_sec)
        except Exception as e:
            _logger.warning("Queue dequeue failed, retrying in 5s: %s", e)
            time.sleep(5.0)
            continue
        if not job_id:
            continue
        _logger.info("RFE worker picked up job_id=%s", job_id)
        svc = RfeService(
            storage=storage,
            job_state=state,
            event_bus=bus,
            worker_context=True,
        )
        try:
            svc.run(job_id)
        except Exception as e:
            _logger.exception("Unhandled error running job %s: %s", job_id, e)
    _logger.info("RFE worker shutdown complete")


def main() -> None:
    signal.signal(signal.SIGTERM, _handle_term)
    signal.signal(signal.SIGINT, _handle_term)
    run_worker_loop()


if __name__ == "__main__":
    main()
