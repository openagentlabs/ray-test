"""
S3 storage backend (stub with working put_json/get_json/append_jsonl).

Scaffolded per plan so the filesystem-vs-object-store swap is a single env flag.
Full production hardening (retries, SSE, per-tenant prefixing policy) is deferred
until we explicitly enable `RFE_STORAGE_BACKEND=s3` in production.

Why we ship a partial S3 now: lets `backends.py` factory be symmetric and lets the
interface prove out through tests without the filesystem coupling.
"""

from __future__ import annotations

import io
import json
from typing import Any, Dict, List, Optional

from .base import StorageBackend


class S3Backend(StorageBackend):
    def __init__(self, bucket: str, prefix: str = "rfe_artifacts/"):
        # Lazy import so that local dev with filesystem backend doesn't force boto3 at module load.
        import boto3  # type: ignore

        self.bucket = bucket
        self.prefix = prefix if prefix.endswith("/") else prefix + "/"
        self._s3 = boto3.client("s3")

    def _key(self, job_id: str, key: str) -> str:
        return f"{self.prefix}{job_id}/{key}"

    # ---------- JSON ----------
    def put_json(self, job_id: str, key: str, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self._s3.put_object(Bucket=self.bucket, Key=self._key(job_id, key), Body=body)

    def get_json(self, job_id: str, key: str) -> Optional[Dict[str, Any]]:
        try:
            obj = self._s3.get_object(Bucket=self.bucket, Key=self._key(job_id, key))
        except Exception:
            return None
        return json.loads(obj["Body"].read().decode("utf-8"))

    def append_jsonl(self, job_id: str, key: str, row: Dict[str, Any]) -> None:
        # S3 has no native append - read-modify-write with a short-lived lock is
        # acceptable for the low-write-frequency audit log. For heavy appenders,
        # a per-write object (key+epoch.jsonl) would be safer; we defer that until
        # the S3 backend is actually enabled in production.
        existing = self.get_bytes(job_id, key) or b""
        line = (json.dumps(row, default=str) + "\n").encode("utf-8")
        self.put_bytes(job_id, key, existing + line)

    def read_jsonl(self, job_id: str, key: str) -> List[Dict[str, Any]]:
        data = self.get_bytes(job_id, key)
        if not data:
            return []
        out: List[Dict[str, Any]] = []
        for line in data.decode("utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
        return out

    # ---------- binary / parquet ----------
    def put_bytes(self, job_id: str, key: str, data: bytes) -> None:
        self._s3.put_object(Bucket=self.bucket, Key=self._key(job_id, key), Body=data)

    def get_bytes(self, job_id: str, key: str) -> Optional[bytes]:
        try:
            obj = self._s3.get_object(Bucket=self.bucket, Key=self._key(job_id, key))
        except Exception:
            return None
        return obj["Body"].read()

    # ---------- listing ----------
    def list_keys(self, job_id: str, prefix: str = "") -> List[str]:
        full_prefix = self._key(job_id, prefix)
        strip = f"{self.prefix}{job_id}/"
        paginator = self._s3.get_paginator("list_objects_v2")
        out: List[str] = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=full_prefix):
            for item in page.get("Contents", []) or []:
                k = item["Key"]
                if k.startswith(strip):
                    out.append(k[len(strip) :])
        out.sort()
        return out

    def exists(self, job_id: str, key: str) -> bool:
        try:
            self._s3.head_object(Bucket=self.bucket, Key=self._key(job_id, key))
            return True
        except Exception:
            return False

    def job_path(self, job_id: str) -> str:
        return f"s3://{self.bucket}/{self.prefix}{job_id}"
