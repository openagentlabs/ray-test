"""
Redis-backed JobStateStore for multi-replica deployments.

Design:
- Every job maps to a hash at `rfe:job:{job_id}`.
- `request_cancel` flips `cancel_flag` and bumps `updated_at`; the worker
  reads this field between iterations and exits cooperatively.
- `list_active` uses a secondary set `rfe:active_jobs` that create/update
  maintain so we avoid a `KEYS rfe:job:*` scan on a loaded Redis.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from .base import JobStateRow, JobStateStore


_ACTIVE_SET = "rfe:active_jobs"


def _row_key(job_id: str) -> str:
    return f"rfe:job:{job_id}"


class RedisJobStateStore(JobStateStore):
    def __init__(self, redis_client: Any):
        # Duck-typed so tests can inject a fake. Expected to be `redis.Redis`.
        self._redis = redis_client

    def _hget_row(self, job_id: str) -> Optional[JobStateRow]:
        raw = self._redis.hgetall(_row_key(job_id))
        if not raw:
            return None
        plain: Dict[str, Any] = {}
        for k, v in raw.items():
            k = k.decode() if isinstance(k, bytes) else k
            if isinstance(v, bytes):
                v = v.decode()
            plain[k] = v
        # Coerce types
        for int_field in ("current_iteration", "total_features", "best_iteration"):
            if int_field in plain and plain[int_field] != "":
                try:
                    plain[int_field] = int(plain[int_field])
                except (TypeError, ValueError):
                    plain[int_field] = 0
        for float_field in ("latest_cv_auc", "heartbeat_at", "created_at", "updated_at"):
            if float_field in plain and plain[float_field] not in ("", "None"):
                try:
                    plain[float_field] = float(plain[float_field])
                except (TypeError, ValueError):
                    plain[float_field] = 0.0
            elif plain.get(float_field) == "None":
                plain[float_field] = None if float_field == "latest_cv_auc" else 0.0
        if "cancel_flag" in plain:
            plain["cancel_flag"] = str(plain["cancel_flag"]).lower() in ("1", "true", "yes")
        return JobStateRow(**{k: v for k, v in plain.items() if k in JobStateRow.__dataclass_fields__})

    def _hset_row(self, row: JobStateRow) -> None:
        mapping = {}
        for k, v in asdict(row).items():
            mapping[k] = "" if v is None else (str(v) if not isinstance(v, bool) else ("1" if v else "0"))
        self._redis.hset(_row_key(row.job_id), mapping=mapping)

    def create(self, row: JobStateRow) -> None:
        now = time.time()
        if not row.created_at:
            row.created_at = now
        row.updated_at = now
        self._hset_row(row)
        self._redis.sadd(_ACTIVE_SET, row.job_id)

    def get(self, job_id: str) -> Optional[JobStateRow]:
        return self._hget_row(job_id)

    def update(self, job_id: str, **fields: Any) -> None:
        if not self._redis.exists(_row_key(job_id)):
            return
        now = time.time()
        to_set: Dict[str, str] = {"updated_at": str(now)}
        for k, v in fields.items():
            if k not in JobStateRow.__dataclass_fields__:
                continue
            if isinstance(v, bool):
                to_set[k] = "1" if v else "0"
            elif v is None:
                to_set[k] = ""
            else:
                to_set[k] = str(v)
        self._redis.hset(_row_key(job_id), mapping=to_set)
        status = fields.get("status")
        if status in ("completed", "failed", "cancelled"):
            self._redis.srem(_ACTIVE_SET, job_id)

    def request_cancel(self, job_id: str) -> bool:
        row = self.get(job_id)
        if row is None or row.status in ("completed", "failed", "cancelled"):
            return False
        self.update(job_id, cancel_flag=True)
        return True

    def list_active(self) -> List[JobStateRow]:
        ids = self._redis.smembers(_ACTIVE_SET) or []
        out: List[JobStateRow] = []
        for jid in ids:
            jid_s = jid.decode() if isinstance(jid, bytes) else jid
            r = self._hget_row(jid_s)
            if r is not None:
                out.append(r)
        return out

    def delete(self, job_id: str) -> None:
        self._redis.delete(_row_key(job_id))
        self._redis.srem(_ACTIVE_SET, job_id)
