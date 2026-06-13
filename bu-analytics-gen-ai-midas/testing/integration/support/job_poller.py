"""Polls an async job endpoint until a terminal status is reached."""

from __future__ import annotations

import time
from typing import Optional

from pydantic import BaseModel, ConfigDict
from returns.result import Failure, Result, Success

from testing.api_client.client import MidasHttpClient

_TERMINAL_STATUSES: frozenset[str] = frozenset(
    {"completed", "failed", "cancelled", "error"}
)
_DEFAULT_MAX_POLLS: int = 20
_DEFAULT_INTERVAL_S: float = 3.0


class JobPollerOptions(BaseModel):
    """Configuration for a single async job poll run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    job_id: str
    status_path_template: str
    max_polls: Optional[int] = None
    poll_interval_s: Optional[float] = None


class JobPoller:
    """Polls a job status endpoint until it reaches a terminal state."""

    def __init__(self, opts: JobPollerOptions, client: MidasHttpClient) -> None:
        self._opts = opts
        self._client = client

    @staticmethod
    def new(
        opts: JobPollerOptions,
        client: MidasHttpClient,
    ) -> Result["JobPoller", Exception]:
        """Construct a JobPoller, returning Success or Failure."""
        return Success(JobPoller(opts, client))

    @property
    def job_id(self) -> str:
        """The job ID being polled."""
        return self._opts.job_id

    def poll_until_terminal(self) -> Result[str, Exception]:
        """Poll until terminal status or max_polls exceeded; return status string."""
        max_polls = self._opts.max_polls or _DEFAULT_MAX_POLLS
        interval = self._opts.poll_interval_s or _DEFAULT_INTERVAL_S
        path = self._opts.status_path_template.format(job_id=self._opts.job_id)
        for _ in range(max_polls):
            result = self._client.get_raw(path)
            match result:
                case Success(resp):
                    status = _extract_status(resp)
                    if status in _TERMINAL_STATUSES:
                        return Success(status)
                case Failure(exc):
                    return Failure(exc)
            time.sleep(interval)
        return Failure(TimeoutError(f"job {self._opts.job_id} did not finish in {max_polls} polls"))


def _extract_status(resp: object) -> str:
    """Extract status string from job status response."""
    import httpx

    if not isinstance(resp, httpx.Response):
        return "unknown"
    if resp.status_code != 200:
        return "unknown"
    body = resp.json()
    if isinstance(body, dict):
        return str(body.get("status", "unknown"))
    return "unknown"
