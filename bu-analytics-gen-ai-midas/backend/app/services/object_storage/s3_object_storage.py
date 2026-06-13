"""S3-backed object storage using a bucket + key prefix."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from typing import Any, BinaryIO, Dict, Iterator, List, Optional, Tuple

from botocore.exceptions import ClientError

from app.services.object_storage.contracts import ObjectStorageBackend


# S3 multipart-upload requires every part except the last to be at least 5 MiB.
# We expose the constant so callers (e.g. chunked_upload finalize) can validate
# part sizes before initiating a server-side assembly.
S3_MULTIPART_MIN_PART_BYTES = 5 * 1024 * 1024


class S3ObjectStorage(ObjectStorageBackend):
    def __init__(
        self,
        s3_client: Any,
        bucket: str,
        *,
        key_prefix: str = "uploads",
    ) -> None:
        self._client = s3_client
        self._bucket = bucket.strip()
        p = (key_prefix or "uploads").strip().strip("/")
        self._prefix = f"{p}/" if p else ""

    @property
    def kind(self) -> str:
        return "s3"

    def _full_key(self, key: str) -> str:
        k = key.replace("\\", "/").lstrip("/")
        return f"{self._prefix}{k}" if self._prefix else k

    def _rel_from_full(self, full_key: str) -> str:
        if self._prefix and full_key.startswith(self._prefix):
            return full_key[len(self._prefix) :]
        return full_key

    def put_bytes(self, key: str, data: bytes) -> None:
        fk = self._full_key(key)
        self._client.put_object(Bucket=self._bucket, Key=fk, Body=data)

    def get_bytes(self, key: str) -> bytes:
        fk = self._full_key(key)
        resp = self._client.get_object(Bucket=self._bucket, Key=fk)
        return resp["Body"].read()

    @contextmanager
    def open_binary_stream(self, key: str) -> Iterator[BinaryIO]:
        fk = self._full_key(key)
        resp = self._client.get_object(Bucket=self._bucket, Key=fk)
        body = resp["Body"]
        try:
            yield body
        finally:
            try:
                body.close()
            except Exception:
                pass

    def exists(self, key: str) -> bool:
        fk = self._full_key(key)
        try:
            self._client.head_object(Bucket=self._bucket, Key=fk)
            return True
        except ClientError as exc:
            status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            code = exc.response.get("Error", {}).get("Code", "")
            if status == 404 or code in ("404", "NotFound", "NoSuchKey"):
                return False
            raise

    def head_object(self, key: str) -> Optional[Dict[str, Any]]:
        fk = self._full_key(key)
        try:
            resp = self._client.head_object(Bucket=self._bucket, Key=fk)
        except ClientError as exc:
            status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            code = exc.response.get("Error", {}).get("Code", "")
            if status == 404 or code in ("404", "NotFound", "NoSuchKey"):
                return None
            raise
        last_modified = resp.get("LastModified")
        return {
            "size": int(resp.get("ContentLength") or 0),
            "etag": (resp.get("ETag") or "").strip('"') or None,
            "last_modified": last_modified.isoformat() if last_modified is not None else None,
        }

    def upload_file_path(self, key: str, path: Path) -> None:
        fk = self._full_key(key)
        self._client.upload_file(str(path), self._bucket, fk)

    def delete(self, key: str) -> None:
        fk = self._full_key(key)
        try:
            self._client.delete_object(Bucket=self._bucket, Key=fk)
        except Exception:
            pass

    def list_csv_keys(self) -> List[str]:
        keys: List[str] = []
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=self._prefix):
            for obj in page.get("Contents", []):
                fk = obj["Key"]
                if fk.endswith(".csv"):
                    keys.append(self._rel_from_full(fk))
        return sorted(keys)

    def list_prefix(self, prefix: str) -> List[str]:
        """Return logical keys under ``prefix`` (relative to the upload prefix)."""
        keys: List[str] = []
        fk_prefix = self._full_key(prefix)
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=fk_prefix):
            for obj in page.get("Contents", []):
                fk = obj["Key"]
                keys.append(self._rel_from_full(fk))
        return sorted(keys)

    def assemble_via_multipart_copy(
        self,
        target_key: str,
        sources: List[str],
        *,
        max_concurrency: int = 10,
    ) -> Dict[str, Any]:
        """Server-side concatenation of ``sources`` into ``target_key`` via
        S3 ``CreateMultipartUpload`` + ``UploadPartCopy`` + ``CompleteMultipartUpload``.

        Bytes never transit our network: each ``UploadPartCopy`` runs entirely
        inside S3. This is the only sane way to finalize a multi-GB chunked
        upload that already has all its parts in the same bucket -- the naive
        get-bytes/concat/put-bytes loop has to download then re-upload every
        byte and routinely exceeds ALB / API-gateway idle timeouts on >1 GB
        files.

        Each entry in ``sources`` becomes one multipart part, in order. Per
        S3's contract every part except the last must be at least 5 MiB
        (``S3_MULTIPART_MIN_PART_BYTES``) -- callers must validate before
        invoking. Sources beyond 5 GiB per part require a ranged
        ``UploadPartCopy`` which we don't implement here.

        On any error the in-flight multipart upload is aborted (best effort)
        so we don't leave dangling pre-paid storage in the bucket.

        Returns ``{"key": target_key, "etag": "<assembled etag>"}``.
        """
        if not sources:
            raise ValueError("assemble_via_multipart_copy: sources is empty")

        target_full = self._full_key(target_key)
        mpu = self._client.create_multipart_upload(
            Bucket=self._bucket,
            Key=target_full,
        )
        mp_upload_id = mpu["UploadId"]

        def _copy_one(idx_src: Tuple[int, str]) -> Dict[str, Any]:
            part_number, source_key = idx_src
            source_full = self._full_key(source_key)
            resp = self._client.upload_part_copy(
                Bucket=self._bucket,
                Key=target_full,
                UploadId=mp_upload_id,
                PartNumber=part_number,
                CopySource={"Bucket": self._bucket, "Key": source_full},
            )
            return {
                "PartNumber": part_number,
                "ETag": resp["CopyPartResult"]["ETag"],
            }

        indexed: List[Tuple[int, str]] = list(enumerate(sources, start=1))
        try:
            if max_concurrency <= 1 or len(indexed) <= 1:
                parts_etag: List[Dict[str, Any]] = [_copy_one(ix) for ix in indexed]
            else:
                workers = max(1, min(max_concurrency, len(indexed)))
                with ThreadPoolExecutor(max_workers=workers) as ex:
                    parts_etag = list(ex.map(_copy_one, indexed))

            parts_etag.sort(key=lambda p: int(p["PartNumber"]))
            result = self._client.complete_multipart_upload(
                Bucket=self._bucket,
                Key=target_full,
                UploadId=mp_upload_id,
                MultipartUpload={"Parts": parts_etag},
            )
            return {
                "key": target_key,
                "etag": (result.get("ETag") or "").strip('"'),
            }
        except Exception:
            try:
                self._client.abort_multipart_upload(
                    Bucket=self._bucket,
                    Key=target_full,
                    UploadId=mp_upload_id,
                )
            except Exception:
                pass
            raise

    def delete_keys_batch(self, keys: List[str]) -> int:
        """Delete up to 1000 keys per ``DeleteObjects`` request.

        Returns the count of keys S3 acknowledged as deleted (i.e. did not
        return an Errors entry for). Per-batch errors are best-effort: we do
        not raise on partial failures so cleanup paths can keep going.
        """
        if not keys:
            return 0
        BATCH = 1000
        deleted = 0
        for i in range(0, len(keys), BATCH):
            batch = keys[i : i + BATCH]
            objects = [{"Key": self._full_key(k)} for k in batch]
            try:
                resp = self._client.delete_objects(
                    Bucket=self._bucket,
                    Delete={"Objects": objects, "Quiet": True},
                )
            except Exception:
                continue
            errors = resp.get("Errors") or []
            deleted += len(batch) - len(errors)
        return deleted
