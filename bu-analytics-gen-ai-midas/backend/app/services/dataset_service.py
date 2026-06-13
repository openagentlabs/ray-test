import io
import json
import os
import re
import shutil
import tempfile
import threading
import time as _time
import uuid
from collections import OrderedDict
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Optional, Tuple

import pandas as pd

from app.core.config import settings
from app.core.executor import executor as _pool_executor
from app.core.logging_config import get_logger
from app.models.schemas import DataStats
from app.services.object_storage.registry import get_object_storage

UPLOAD_STREAM_CHUNK_SIZE = 2 * 1024 * 1024  # 2 MiB


# ---------------------------------------------------------------------------
# Shared in-process DataFrame load cache (P-large-dataset fix).
#
# Read-only stats endpoints (column-info-by-scope, dqs-by-scope,
# overview-bundle) all reload the baseline DataFrame from object storage
# on every call. For multi-GB CSVs, three near-simultaneous requests from
# the UI used to cause three independent CSV parses inside the same
# gunicorn worker process — RAM spike (raw bytes + parsed df held at the
# same time), worker OOM kill, and 504 cascade. A small TTL + LRU cache
# collapses those parallel reads onto a single shared DataFrame parse.
# Callers MUST treat the returned frame as read-only (no in-place
# mutation); the existing endpoints already .copy() before slicing.
# ---------------------------------------------------------------------------
_LOAD_CACHE_TTL_SECONDS = float(os.getenv("MIDAS_DATASET_LOAD_CACHE_TTL", "60"))
_LOAD_CACHE_MAX_ENTRIES = int(os.getenv("MIDAS_DATASET_LOAD_CACHE_MAX", "2"))


class _SharedDataFrameLoadCache:
    """TTL + LRU cache with in-flight coalescing for parsed DataFrames.

    The cache key is the dataset_id. Concurrent calls for the same key
    collapse onto a single loader invocation; later callers block on a
    threading.Event and pick the cached frame up once the leader finishes.
    """

    def __init__(self, max_entries: int, ttl_seconds: float) -> None:
        self._max = max(1, max_entries)
        self._ttl = max(1.0, ttl_seconds)
        self._lock = threading.RLock()
        self._entries: "OrderedDict[str, Tuple[float, pd.DataFrame]]" = OrderedDict()
        self._inflight: Dict[str, threading.Event] = {}

    def _is_fresh(self, ts: float) -> bool:
        return (_time.monotonic() - ts) <= self._ttl

    def get(self, key: str) -> Optional[pd.DataFrame]:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            ts, df = entry
            if not self._is_fresh(ts):
                self._entries.pop(key, None)
                return None
            self._entries.move_to_end(key)
            return df

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._entries.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def get_or_load(
        self, key: str, loader: Callable[[], Optional[pd.DataFrame]]
    ) -> Optional[pd.DataFrame]:
        """Return a cached DataFrame for ``key`` or run ``loader`` to populate it.

        Concurrent calls with the same key wait on the first-in-flight
        loader instead of re-running it. The loader MUST return either a
        DataFrame (cached on success) or None (not cached, callers may
        retry on their next request).
        """
        # Fast path.
        cached = self.get(key)
        if cached is not None:
            return cached

        with self._lock:
            cached = self.get(key)
            if cached is not None:
                return cached
            event = self._inflight.get(key)
            if event is None:
                event = threading.Event()
                self._inflight[key] = event
                is_leader = True
            else:
                is_leader = False

        if not is_leader:
            event.wait(timeout=self._ttl)
            cached = self.get(key)
            if cached is not None:
                return cached
            return loader()

        try:
            df = loader()
        except Exception:
            with self._lock:
                self._inflight.pop(key, None)
            event.set()
            raise

        with self._lock:
            if df is not None:
                self._entries[key] = (_time.monotonic(), df)
                self._entries.move_to_end(key)
                while len(self._entries) > self._max:
                    self._entries.popitem(last=False)
            self._inflight.pop(key, None)
        event.set()
        return df


_dataset_load_cache = _SharedDataFrameLoadCache(
    max_entries=_LOAD_CACHE_MAX_ENTRIES,
    ttl_seconds=_LOAD_CACHE_TTL_SECONDS,
)


class FileTooLargeError(Exception):
    """Raised when a streamed upload exceeds the configured maximum size."""


def _normalize_storage_key(val: str) -> str:
    """Logical object name (basename) for CSV / Parquet / metadata keys."""
    if not val:
        return ""
    return Path(val.replace("\\", "/")).name


def _parquet_key(csv_key: str) -> str:
    return str(Path(csv_key).with_suffix(".parquet"))


def _split_tag_sidecar_key(csv_key: str) -> str:
    """Object-storage key for the lightweight split-tag sidecar parquet.

    A 30M-row ``split_tag`` (categorical: 'train'/'test'/'validation'/...)
    compresses to ~10–50 MB in Parquet, vs. the multi-GB main object. We
    keep it as a *separate* object so ``apply_split_configuration`` does
    not have to rewrite the whole dataset when the user (re)configures
    the split.
    """
    return str(Path(csv_key).with_suffix("")) + ".split_tag.parquet"


def _metadata_object_key(dataset_id: str) -> str:
    return f"{dataset_id}.metadata.json"


def _read_csv_raw_bytes(store, file_path_or_key: str) -> bytes:
    """Read bytes from legacy absolute path or from object storage by key."""
    p = Path(file_path_or_key)
    if p.is_absolute() and p.is_file():
        return p.read_bytes()
    return store.get_bytes(_normalize_storage_key(file_path_or_key))


def _read_parquet_head_streaming(fp, nrows: int) -> Tuple[pd.DataFrame, int, int]:
    """Read up to ``nrows`` from a Parquet file stream without loading the full file."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    pf = pq.ParquetFile(fp)
    total_rows = int(pf.metadata.num_rows)
    ncols = int(pf.schema_arrow.num_fields)
    if total_rows <= 0:
        return pd.DataFrame(), total_rows, ncols
    parts = []
    need = min(nrows, total_rows)
    for i in range(pf.num_row_groups):
        rg = pf.read_row_group(i)
        nr = rg.num_rows
        if nr <= need:
            parts.append(rg)
            need -= nr
            if need == 0:
                break
        else:
            parts.append(rg.slice(0, need))
            break
    if not parts:
        tbl = pf.read_row_group(0).slice(0, min(nrows, total_rows))
    else:
        tbl = pa.concat_tables(parts).slice(0, min(nrows, total_rows))
    return tbl.to_pandas(), total_rows, ncols


def _count_csv_data_rows_streaming(store, csv_key: str) -> int:
    """Data row count (excluding header) via newline scan; bounded memory."""
    buf_size = 8 * 1024 * 1024
    newline_total = 0
    with store.open_binary_stream(csv_key) as fp:
        while True:
            chunk = fp.read(buf_size)
            if not chunk:
                break
            newline_total += chunk.count(b"\n")
    return max(newline_total - 1, 0)


def _read_csv_head_streaming(store, csv_key: str, nrows: int) -> Tuple[pd.DataFrame, int]:
    """First ``nrows`` CSV rows plus total data row count (streaming, two passes for CSV)."""
    encodings = ["utf-8", "latin-1", "cp1252", "iso-8859-1"]
    last_err: Optional[Exception] = None
    for encoding in encodings:
        try:
            with store.open_binary_stream(csv_key) as fp:
                preview = pd.read_csv(fp, encoding=encoding, nrows=nrows, low_memory=False)
            total_data_rows = _count_csv_data_rows_streaming(store, csv_key)
            return preview, total_data_rows
        except UnicodeDecodeError as e:
            last_err = e
            continue
        except Exception as e:
            last_err = e
            continue
    if last_err:
        raise last_err
    return pd.DataFrame(), 0


class DatasetManager:
    """Manages uploaded datasets via pluggable object storage (local dir or S3)."""

    def __init__(self) -> None:
        self.logger = get_logger(__name__)
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.upload_dir.mkdir(exist_ok=True)
        self.datasets: Dict[str, Any] = {}
        st = get_object_storage()
        self.logger.info(
            "DatasetManager initialized: upload_dir=%s object_storage=%s",
            self.upload_dir,
            st.kind,
        )
        self._reload_existing_datasets()
        self._auto_register_existing_datasets()

    def refresh_object_storage_index(self) -> None:
        """Call after FastAPI startup configures S3 so dataset discovery uses the right backend."""
        self.datasets.clear()
        self._reload_existing_datasets()
        self._auto_register_existing_datasets()

    def _reload_existing_datasets(self) -> None:
        try:
            store = get_object_storage()
            keys = store.list_csv_keys()
            self.logger.info("Found %s CSV object(s) in %s storage", len(keys), store.kind)
            for key in keys:
                if "_" not in key:
                    continue
                parts = key.split("_", 1)
                if len(parts) != 2:
                    continue
                dataset_id, original_filename = parts[0], parts[1]
                self.datasets[dataset_id] = {
                    "filename": original_filename,
                    "file_path": key,
                    "storage_key": key,
                    "upload_time": 0.0,
                }
            self.logger.info("Reloaded %s dataset(s) from object storage", len(self.datasets))
        except Exception as e:
            self.logger.warning("Failed to reload existing datasets: %s", e)

    def _metadata_path(self, dataset_id: str) -> Path:
        return self.upload_dir / f"{dataset_id}.metadata.json"

    def _persist_dataset_info(self, dataset_id: str) -> None:
        try:
            if dataset_id not in self.datasets:
                return
            payload = json.dumps(self.datasets[dataset_id], ensure_ascii=False, indent=2).encode("utf-8")
            store = get_object_storage()
            store.put_bytes(_metadata_object_key(dataset_id), payload)
            # Legacy sidecar next to local uploads (optional)
            try:
                mp = self._metadata_path(dataset_id)
                mp.write_text(
                    json.dumps(self.datasets[dataset_id], ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except OSError:
                pass
        except Exception as e:
            self.logger.warning("Failed to persist metadata for %s: %s", dataset_id, e)

    def _load_dataset_info_from_disk(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        store = get_object_storage()
        mk = _metadata_object_key(dataset_id)
        if store.exists(mk):
            try:
                info = json.loads(store.get_bytes(mk).decode("utf-8"))
                if isinstance(info, dict):
                    self.datasets[dataset_id] = info
                    return info
            except Exception as e:
                self.logger.warning("Failed reading metadata object for %s: %s", dataset_id, e)

        metadata_path = self._metadata_path(dataset_id)
        if metadata_path.exists():
            try:
                with open(metadata_path, encoding="utf-8") as f:
                    info = json.load(f)
                if isinstance(info, dict):
                    self.datasets[dataset_id] = info
                    return info
            except Exception as e:
                self.logger.warning("Failed reading legacy metadata file for %s: %s", dataset_id, e)

        candidates = [k for k in store.list_csv_keys() if k.startswith(f"{dataset_id}_")]
        if not candidates:
            return None
        key = candidates[0]
        info = {
            "file_path": key,
            "storage_key": key,
            "filename": key.split("_", 1)[1] if "_" in key else key,
            "target_variable": "",
            "target_variable_type": "",
            "data_dictionary": "",
            "problem_statement": "",
            "unique_id_combinations": [],
            "segmentation_variable": None,
            "sample_identifier_variable": None,
            "uploaded_at": pd.Timestamp.now().isoformat(),
        }
        self.datasets[dataset_id] = info
        self._persist_dataset_info(dataset_id)
        return info

    def _auto_register_existing_datasets(self) -> None:
        if not self.upload_dir.exists():
            return
        csv_files = [f for f in self.upload_dir.iterdir() if f.suffix.lower() == ".csv"]
        self.logger.info("Found %s legacy CSV file(s) on local disk", len(csv_files))
        for file_path in csv_files:
            filename = file_path.name
            if "_" in filename:
                dataset_id = filename.split("_")[0]
                if dataset_id not in self.datasets:
                    self.register_existing_dataset(dataset_id, str(file_path), filename)
                    self.logger.info("Auto-registered dataset: %s", dataset_id)

    def save_uploaded_file(self, file_content: bytes, filename: str) -> Tuple[str, str]:
        """Save uploaded file; returns (dataset_id, storage_key)."""
        self.logger.info("Saving uploaded file: %s (size: %s bytes)", filename, len(file_content))
        dataset_id = str(uuid.uuid4())
        safe_filename = re.sub(r"[^a-zA-Z0-9._-]", "_", filename)
        key = f"{dataset_id}_{safe_filename}"
        try:
            get_object_storage().put_bytes(key, file_content)
            self.logger.info("File saved successfully: key=%s", key)
            return dataset_id, key
        except Exception as e:
            self.logger.error("Failed to save file %s: %s", filename, e)
            raise

    async def save_uploaded_file_streaming(self, upload_file, filename: str, max_size: int) -> Tuple[str, str]:
        """Stream upload; returns (dataset_id, storage_key)."""
        self.logger.info("Streaming upload: %s (max %s bytes)", filename, max_size)
        dataset_id = str(uuid.uuid4())
        safe_filename = re.sub(r"[^a-zA-Z0-9._-]", "_", filename)
        key = f"{dataset_id}_{safe_filename}"
        store = get_object_storage()
        total = 0

        if store.kind == "local":
            path = self.upload_dir / key
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with open(path, "wb") as out:
                    while True:
                        chunk = await upload_file.read(UPLOAD_STREAM_CHUNK_SIZE)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > max_size:
                            raise FileTooLargeError("File size exceeds maximum limit")
                        out.write(chunk)
                self.logger.info("Streamed upload saved locally: %s (%s bytes)", path, total)
                return dataset_id, key
            except FileTooLargeError:
                path.unlink(missing_ok=True)
                raise
            except Exception as e:
                self.logger.error("Failed streaming upload %s: %s", filename, e)
                path.unlink(missing_ok=True)
                raise

        tmp_path: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
                tmp_path = tmp.name
                while True:
                    chunk = await upload_file.read(UPLOAD_STREAM_CHUNK_SIZE)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_size:
                        raise FileTooLargeError("File size exceeds maximum limit")
                    tmp.write(chunk)
            store.upload_file_path(key, Path(tmp_path))
            self.logger.info("Streamed upload saved to S3: key=%s (%s bytes)", key, total)
            return dataset_id, key
        except FileTooLargeError:
            if tmp_path and os.path.isfile(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            raise
        except Exception as e:
            self.logger.error("Failed streaming upload %s: %s", filename, e)
            raise
        finally:
            if tmp_path and os.path.isfile(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    def read_csv_for_upload(self, file_path_or_key: str) -> pd.DataFrame:
        """Load the dataset for the ``/upload`` pipeline.

        Prefers the Parquet sidecar when one exists (written either by the
        chunked-upload finalize background job or by the streaming converter
        at ``/upload`` time). For a 2 GB CSV this trims this stage from
        ~60-120 s + ~6-10 GB peak RAM (full bytes buffer + pandas 3-5x
        amplification) down to ~5-15 s + ~64 MB peak RAM (parquet row-group
        buffer), which keeps the request comfortably inside the ALB's 60 s
        idle timeout.

        On the CSV fallback we stream the object-storage body to a temp file
        in 4 MiB chunks rather than buffering ``store.get_bytes(...)`` in
        process memory, then ``pd.read_csv`` from the path so the parser
        streams from disk too.
        """
        store = get_object_storage()
        csv_key = _normalize_storage_key(file_path_or_key)
        pq_key = _parquet_key(csv_key) if csv_key else ""

        if pq_key and store.exists(pq_key):
            staged_pq_path: Optional[str] = None
            try:
                if store.kind == "local":
                    pq_disk_path = self.upload_dir / pq_key
                    df = pd.read_parquet(str(pq_disk_path), engine="pyarrow")
                else:
                    with store.open_binary_stream(pq_key) as src, tempfile.NamedTemporaryFile(
                        delete=False, suffix=".parquet"
                    ) as tmp:
                        shutil.copyfileobj(src, tmp, length=4 * 1024 * 1024)
                        staged_pq_path = tmp.name
                    df = pd.read_parquet(staged_pq_path, engine="pyarrow")
                self.logger.info(
                    "read_csv_for_upload: parquet sidecar hit, csv_key=%s shape=%s",
                    csv_key,
                    df.shape,
                )
                return df
            except Exception as exc:
                self.logger.warning(
                    "read_csv_for_upload: parquet sidecar load failed for %s, "
                    "falling back to CSV: %s",
                    csv_key,
                    exc,
                )
            finally:
                if staged_pq_path and os.path.isfile(staged_pq_path):
                    try:
                        os.unlink(staged_pq_path)
                    except OSError:
                        pass

        p = Path(file_path_or_key)
        cleanup_csv_path: Optional[str] = None
        if p.is_absolute() and p.is_file():
            csv_local_path = str(p)
        else:
            try:
                with store.open_binary_stream(csv_key) as src, tempfile.NamedTemporaryFile(
                    delete=False, suffix=".csv"
                ) as tmp:
                    shutil.copyfileobj(src, tmp, length=4 * 1024 * 1024)
                    csv_local_path = tmp.name
                    cleanup_csv_path = csv_local_path
            except Exception as exc:
                self.logger.error(
                    "read_csv_for_upload: failed to stage %s to local disk: %s",
                    csv_key,
                    exc,
                )
                raise

        # P3.x: Polars first, pandas fallback. Polars's multithreaded CSV
        # reader is ~3-5x faster than ``pd.read_csv`` on multi-GB files
        # (15-30 s vs 60-120 s for a 2.5 GB CSV) and ``to_pandas()`` is a
        # zero-copy Arrow handoff for primitive columns. On the ``/upload``
        # hot path -- which falls into this branch when the chunked-finalize
        # background parquet conversion hasn't yet completed -- the saved
        # 30-60 s is enough to keep the request inside the ALB idle timeout.
        #
        # Polars is best-effort: any error (encoding, ragged columns, schema
        # surprise) drops back to the legacy pandas multi-encoding loop, so
        # behaviour is never worse than before.
        try:
            import polars as pl  # type: ignore  # noqa: WPS433

            try:
                df_pl = pl.read_csv(
                    csv_local_path,
                    infer_schema_length=10_000,
                    ignore_errors=False,
                    null_values=["", "NA", "N/A", "null", "None"],
                )
                df = df_pl.to_pandas()
                self.logger.info(
                    "read_csv_for_upload: polars csv path, shape=%s",
                    df.shape,
                )
                self.schedule_parquet_alongside_csv(csv_key, df)
                return df
            except Exception as exc:
                self.logger.warning(
                    "read_csv_for_upload: polars csv read failed for %s, "
                    "falling back to pandas: %s",
                    csv_key,
                    exc,
                )
        except ImportError:
            self.logger.debug(
                "read_csv_for_upload: polars not installed; using pandas csv reader"
            )

        encodings = ["utf-8", "latin-1", "cp1252", "iso-8859-1"]
        last_err: Optional[Exception] = None
        try:
            for encoding in encodings:
                try:
                    df = pd.read_csv(csv_local_path, encoding=encoding, low_memory=False)
                    self.logger.info(
                        "read_csv_for_upload: csv path, encoding=%s, shape=%s",
                        encoding,
                        df.shape,
                    )
                    self.schedule_parquet_alongside_csv(csv_key, df)
                    return df
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    last_err = e
                    break
        finally:
            if cleanup_csv_path and os.path.isfile(cleanup_csv_path):
                try:
                    os.unlink(cleanup_csv_path)
                except OSError:
                    pass

        if last_err:
            self.logger.error(
                "read_csv_for_upload failed for %s: %s", file_path_or_key, last_err
            )
            raise last_err
        raise ValueError(f"Could not read CSV: {file_path_or_key}")

    def schedule_parquet_alongside_csv(self, csv_key: str, df: pd.DataFrame) -> None:
        """Write Parquet asynchronously on the shared thread pool (non-blocking for callers)."""
        key = _normalize_storage_key(csv_key)
        _pool_executor.submit(self._run_parquet_write_background, key, df)

    def stream_convert_csv_to_parquet(self, csv_key: str) -> Optional[str]:
        """
        P2.1: Stream a CSV from object storage into a Parquet file *without*
        ever materializing the whole frame in pandas. Uses pyarrow's CSV
        reader in batched mode (~10 MB blocks) and pipes RecordBatches into
        a `pyarrow.parquet.ParquetWriter`. Returns the parquet storage key
        on success, or None if conversion was skipped / failed (the caller
        falls back to the legacy `read_csv_for_upload` path which uses pandas).

        Memory ceiling: ~1 batch (~10 MB decoded) + ParquetWriter row-group
        buffer (~64 MB), regardless of input size. On a 2 GB CSV this avoids
        the ~3-5x peak RAM amplification of `pd.read_csv` and writes the
        Parquet ~3x faster than the legacy "load with pandas, then to_parquet".
        """
        try:
            import pyarrow as pa
            import pyarrow.csv as pacsv
            import pyarrow.parquet as papq
        except ImportError as exc:
            self.logger.warning("pyarrow not available, skipping streaming convert: %s", exc)
            return None

        csv_key = _normalize_storage_key(csv_key)
        pq_key = _parquet_key(csv_key)
        store = get_object_storage()

        if store.exists(pq_key):
            self.logger.debug("Parquet already exists for %s, skipping conversion", csv_key)
            return pq_key

        # Local-disk fast path: pyarrow can read CSV directly off the path.
        # For S3-backed storage we stage to a temp file (S3 streaming through
        # pyarrow needs an fsspec adapter; not worth the dependency for the
        # current single-region deployment).
        if store.kind == "local":
            csv_disk_path = self.upload_dir / csv_key
            if not csv_disk_path.is_file():
                self.logger.warning("stream_convert: CSV not found at %s", csv_disk_path)
                return None
            csv_path_str = str(csv_disk_path)
            cleanup_path: Optional[str] = None
        else:
            try:
                # Stream the CSV body to disk in 4 MiB chunks rather than
                # buffering ``store.get_bytes(csv_key)`` (the entire CSV) in
                # process memory. boto3's StreamingBody is a file-like with
                # ``read(size)`` semantics, so ``shutil.copyfileobj`` keeps
                # peak RAM bounded at ``length`` regardless of file size.
                with store.open_binary_stream(csv_key) as src, tempfile.NamedTemporaryFile(
                    delete=False, suffix=".csv"
                ) as tmp:
                    shutil.copyfileobj(src, tmp, length=4 * 1024 * 1024)
                    csv_path_str = tmp.name
                    cleanup_path = csv_path_str
            except Exception as exc:
                self.logger.warning("stream_convert: failed to stage S3 CSV: %s", exc)
                return None

        parquet_tmp_path: Optional[str] = None
        try:
            read_options = pacsv.ReadOptions(block_size=8 * 1024 * 1024)
            convert_options = pacsv.ConvertOptions(strings_can_be_null=True)
            parse_options = pacsv.ParseOptions()

            with pacsv.open_csv(
                csv_path_str,
                read_options=read_options,
                parse_options=parse_options,
                convert_options=convert_options,
            ) as reader:
                first_batch = reader.read_next_batch()
                schema = first_batch.schema

                with tempfile.NamedTemporaryFile(delete=False, suffix=".parquet") as tmp:
                    parquet_tmp_path = tmp.name

                writer = papq.ParquetWriter(parquet_tmp_path, schema, compression="snappy")
                try:
                    writer.write_table(pa.Table.from_batches([first_batch], schema=schema))
                    while True:
                        try:
                            batch = reader.read_next_batch()
                        except StopIteration:
                            break
                        writer.write_table(pa.Table.from_batches([batch], schema=schema))
                finally:
                    writer.close()

            # Push to object storage. For local backend this is just a copy,
            # for S3 the helper streams the file in one PUT.
            if store.kind == "local":
                target_path = self.upload_dir / pq_key
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(parquet_tmp_path, target_path)
            else:
                store.upload_file_path(pq_key, Path(parquet_tmp_path))

            self.logger.info(
                "stream_convert_csv_to_parquet: csv=%s -> parquet=%s",
                csv_key,
                pq_key,
            )
            return pq_key
        except Exception as exc:
            self.logger.warning("stream_convert_csv_to_parquet failed for %s: %s", csv_key, exc)
            return None
        finally:
            if parquet_tmp_path and os.path.isfile(parquet_tmp_path):
                try:
                    os.unlink(parquet_tmp_path)
                except OSError:
                    pass
            if cleanup_path and os.path.isfile(cleanup_path):
                try:
                    os.unlink(cleanup_path)
                except OSError:
                    pass

    def compute_target_profile(
        self, dataset_id: str, csv_key: str, target_column: str
    ) -> Optional[Dict[str, Any]]:
        """
        P2.1: Compute a `target_profile` sidecar (JSON) for the configured
        target column. This is read by the LLM classifier and the sampler so
        downstream code does NOT need to scan the full file again to detect
        rare classes - the profile is the source of truth.

        The profile contains: dtype, n_unique, n_missing, top-K value counts
        (K=20), and `is_imbalanced` (max class > 95% of rows). For numeric
        targets we compute min/max/mean/quantiles instead.

        Reads ONLY the target column from Parquet (columnar projection), so
        even for a 2 GB / 200-column CSV this is sub-second on commodity SSDs.
        """
        try:
            import pyarrow.parquet as papq
        except ImportError:
            return None

        csv_key = _normalize_storage_key(csv_key)
        pq_key = _parquet_key(csv_key)
        store = get_object_storage()
        if not store.exists(pq_key):
            self.logger.debug("compute_target_profile: parquet missing for %s", csv_key)
            return None
        if not target_column:
            return None

        try:
            if store.kind == "local":
                pq_path = str(self.upload_dir / pq_key)
                table = papq.read_table(pq_path, columns=[target_column])
            else:
                raw = store.get_bytes(pq_key)
                table = papq.read_table(io.BytesIO(raw), columns=[target_column])
        except Exception as exc:
            self.logger.warning(
                "compute_target_profile: failed to read column %s from %s: %s",
                target_column,
                pq_key,
                exc,
            )
            return None

        try:
            series = table.column(target_column).to_pandas()
        except Exception as exc:
            self.logger.warning("compute_target_profile: to_pandas failed: %s", exc)
            return None

        n_total = int(len(series))
        n_missing = int(series.isna().sum())
        n_present = n_total - n_missing
        dtype = str(series.dtype)

        profile: Dict[str, Any] = {
            "version": 1,
            "dataset_id": dataset_id,
            "target_column": target_column,
            "dtype": dtype,
            "n_total": n_total,
            "n_missing": n_missing,
            "n_present": n_present,
        }

        if pd.api.types.is_numeric_dtype(series) and series.nunique(dropna=True) > 50:
            present = series.dropna()
            if len(present):
                profile["mode"] = "numeric"
                profile["min"] = float(present.min())
                profile["max"] = float(present.max())
                profile["mean"] = float(present.mean())
                profile["quantiles"] = {
                    "p25": float(present.quantile(0.25)),
                    "p50": float(present.quantile(0.50)),
                    "p75": float(present.quantile(0.75)),
                    "p95": float(present.quantile(0.95)),
                }
        else:
            profile["mode"] = "categorical"
            counts = series.value_counts(dropna=True).head(20)
            profile["n_unique"] = int(series.nunique(dropna=True))
            profile["top_values"] = [
                {"value": str(idx), "count": int(cnt)} for idx, cnt in counts.items()
            ]
            if n_present > 0 and len(counts) > 0:
                max_count = int(counts.iloc[0])
                profile["max_class_share"] = max_count / float(n_present)
                profile["is_imbalanced"] = profile["max_class_share"] > 0.95
                profile["minority_classes"] = [
                    item["value"]
                    for item in profile["top_values"]
                    if item["count"] / float(n_present) < 0.01
                ]

        # Persist sidecar JSON next to the CSV/Parquet so subsequent endpoints
        # can short-circuit to it without re-scanning the data.
        try:
            sidecar_key = f"{dataset_id}.target_profile.json"
            store.put_bytes(sidecar_key, json.dumps(profile).encode("utf-8"))
            self.logger.info(
                "compute_target_profile: wrote sidecar key=%s mode=%s",
                sidecar_key,
                profile.get("mode"),
            )
        except Exception as exc:
            self.logger.warning("compute_target_profile: sidecar persist failed: %s", exc)
        return profile

    def get_target_profile(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """Read the cached target_profile sidecar JSON, if any."""
        try:
            store = get_object_storage()
            sidecar_key = f"{dataset_id}.target_profile.json"
            if not store.exists(sidecar_key):
                return None
            raw = store.get_bytes(sidecar_key)
            return json.loads(raw.decode("utf-8"))
        except Exception as exc:
            self.logger.warning("get_target_profile failed for %s: %s", dataset_id, exc)
            return None

    def _run_parquet_write_background(self, csv_key: str, df: pd.DataFrame) -> None:
        try:
            self._write_parquet_alongside_csv(csv_key, df)
        except Exception:
            self.logger.exception("Background Parquet write failed for %s", csv_key)

    def _write_parquet_alongside_csv(self, csv_key: str, df: pd.DataFrame) -> None:
        try:
            pq = _parquet_key(csv_key)
            buf = io.BytesIO()
            df.to_parquet(buf, engine="pyarrow", index=False)
            get_object_storage().put_bytes(pq, buf.getvalue())
            self.logger.info("Parquet written: key=%s (%s KB)", pq, len(buf.getvalue()) // 1024)
        except Exception as exc:
            self.logger.warning("Could not write Parquet for %s: %s", csv_key, exc)

    def _csv_storage_key(self, dataset_id: str) -> Optional[str]:
        if dataset_id not in self.datasets:
            if not self._load_dataset_info_from_disk(dataset_id):
                return None
        info = self.datasets.get(dataset_id) or {}
        ref = str(info.get("storage_key") or info.get("file_path") or "")
        if not ref:
            return None
        return _normalize_storage_key(ref)

    def save_dataset(self, dataset_id: str, df: pd.DataFrame) -> bool:
        """Write the dataframe to this dataset's CSV object (and schedule Parquet)."""
        csv_key = self._csv_storage_key(dataset_id)
        if not csv_key:
            self.logger.error("save_dataset: no storage key for dataset_id=%s", dataset_id)
            return False
        try:
            buf = io.BytesIO()
            df.to_csv(buf, index=False, encoding="utf-8")
            get_object_storage().put_bytes(csv_key, buf.getvalue())
            self.schedule_parquet_alongside_csv(csv_key, df)
            # Drop any cached read-only DataFrame for this dataset so the next
            # stats request sees the just-written content rather than a stale
            # parse from the prior version.
            _dataset_load_cache.invalidate(dataset_id)
            self.logger.info("save_dataset: wrote CSV key=%s rows=%s cols=%s", csv_key, len(df), len(df.columns))
            return True
        except Exception as e:
            self.logger.error("save_dataset failed for %s: %s", dataset_id, e)
            return False

    def persist_dataframe_and_scheme_metadata(
        self, dataset_id: str, df: pd.DataFrame, scheme_record: Dict[str, Any]
    ) -> bool:
        """
        Persist the dataframe then append one scheme metadata record and save dataset info once.
        Used by Add to Data so the new column and registry row land together (plan §12.3–12.4).
        """
        if not self.save_dataset(dataset_id, df):
            return False
        return self.append_segmentation_scheme_metadata(dataset_id, scheme_record)

    def save_split_tag_sidecar(self, dataset_id: str, split_tag_series: "pd.Series") -> bool:
        """Persist only the ``split_tag`` column for ``dataset_id`` to object storage.

        Memory-safe at multi-GB scale: writes a single-column Parquet to a
        ``NamedTemporaryFile`` on disk via ``pyarrow.parquet.write_table``
        (no full-buffer ``io.BytesIO``), then streams the file to S3. Peak
        process memory while serialising 30M rows of a 5-char categorical is
        ~5–50 MB, regardless of how large the source dataset is.
        """
        csv_key = self._csv_storage_key(dataset_id)
        if not csv_key:
            self.logger.error("save_split_tag_sidecar: no storage key for %s", dataset_id)
            return False
        sidecar_key = _split_tag_sidecar_key(csv_key)
        store = get_object_storage()
        try:
            import pyarrow as pa
            import pyarrow.parquet as papq
        except ImportError as exc:
            self.logger.warning("pyarrow unavailable, skipping split_tag sidecar write: %s", exc)
            return False
        try:
            # Categorical compresses extremely well in Parquet (dictionary
            # encoding) and avoids 30M Python string objects on read.
            ser = split_tag_series.astype("category")
            table = pa.table({"split_tag": pa.array(ser)})
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".parquet")
            tmp_path = tmp.name
            tmp.close()
            try:
                papq.write_table(table, tmp_path, compression="snappy")
                if store.kind == "local":
                    target_path = self.upload_dir / sidecar_key
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(tmp_path, target_path)
                else:
                    store.upload_file_path(sidecar_key, Path(tmp_path))
                size_bytes = os.path.getsize(tmp_path)
                self.logger.info(
                    "split_tag sidecar written: key=%s rows=%s size=%sKB",
                    sidecar_key, len(ser), size_bytes // 1024,
                )
                return True
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
        except Exception as exc:
            self.logger.warning("save_split_tag_sidecar failed for %s: %s", dataset_id, exc)
            return False

    def load_split_tag_sidecar(self, dataset_id: str) -> Optional["pd.Series"]:
        """Load the ``split_tag`` sidecar (one-column Parquet) if present.

        Memory cost: ~5–50 MB in pandas for 30M rows (categorical). Falls
        back to ``None`` if the sidecar is missing so callers can use the
        in-frame ``split_tag`` column (if any) or the in-RAM split state.
        """
        csv_key = self._csv_storage_key(dataset_id)
        if not csv_key:
            return None
        sidecar_key = _split_tag_sidecar_key(csv_key)
        store = get_object_storage()
        try:
            if not store.exists(sidecar_key):
                return None
            raw = store.get_bytes(sidecar_key)
            df = pd.read_parquet(io.BytesIO(raw), engine="pyarrow")
            if "split_tag" not in df.columns:
                return None
            return df["split_tag"]
        except Exception as exc:
            self.logger.warning("load_split_tag_sidecar failed for %s: %s", dataset_id, exc)
            return None

    def load_dataset_readonly_cached(self, dataset_id: str) -> Optional[pd.DataFrame]:
        """Return a SHARED, read-only DataFrame for ``dataset_id``.

        Wraps :meth:`load_dataset` with a process-local TTL+LRU cache that
        also coalesces concurrent loads. Use this from endpoints that
        only need the original baseline frame for read-only stats
        (column-info-by-scope, dqs-by-scope, overview-bundle).

        WARNING: the returned DataFrame may be referenced by other
        in-flight requests. Callers MUST NOT mutate it. Use ``.copy()``
        before any slice/assign/mutate.
        """
        return _dataset_load_cache.get_or_load(
            dataset_id, lambda: self.load_dataset(dataset_id)
        )

    def invalidate_readonly_cache(self, dataset_id: str) -> None:
        """Drop any cached DataFrame for ``dataset_id`` (call after re-upload)."""
        _dataset_load_cache.invalidate(dataset_id)

    def load_dataset(self, dataset_id: str) -> Optional[pd.DataFrame]:
        self.logger.debug("Loading dataset: %s", dataset_id)
        store = get_object_storage()

        if dataset_id not in self.datasets:
            disk_info = self._load_dataset_info_from_disk(dataset_id)
            if not disk_info:
                self.logger.warning("Dataset not found in memory: %s", dataset_id)
                return None

        dataset_info = self.datasets[dataset_id]
        csv_key = _normalize_storage_key(
            str(dataset_info.get("storage_key") or dataset_info["file_path"])
        )
        pq_k = _parquet_key(csv_key)

        if store.exists(pq_k):
            try:
                raw = store.get_bytes(pq_k)
                df = pd.read_parquet(io.BytesIO(raw), engine="pyarrow")
                self.logger.info(
                    "Dataset loaded from Parquet: %s, shape=%s", dataset_id, df.shape
                )
                return df
            except Exception as exc:
                self.logger.warning(
                    "Parquet load failed for %s, falling back to CSV: %s", dataset_id, exc
                )

        try:
            raw = _read_csv_raw_bytes(store, csv_key)
        except Exception as e:
            self.logger.error("Dataset object not found: %s (%s)", csv_key, e)
            del self.datasets[dataset_id]
            return None

        try:
            encodings = ["utf-8", "latin-1", "cp1252", "iso-8859-1"]
            df = None
            for encoding in encodings:
                try:
                    buf = io.BytesIO(raw)
                    df = pd.read_csv(buf, encoding=encoding)
                    self.logger.info(
                        "Dataset loaded from CSV (%s): %s, shape=%s",
                        encoding,
                        dataset_id,
                        df.shape,
                    )
                    break
                except UnicodeDecodeError:
                    continue
            if df is None:
                self.logger.error("Could not decode dataset %s", dataset_id)
                return None

            df = df.infer_objects()
            for col in df.columns:
                try:
                    df[col] = pd.to_numeric(df[col], errors="ignore")
                except Exception:
                    try:
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                    except Exception as conv_err:
                        self.logger.warning("Could not convert column %s: %s", col, conv_err)

            self.schedule_parquet_alongside_csv(csv_key, df)
            return df
        except Exception as e:
            self.logger.error("Error loading dataset %s: %s", dataset_id, e)
            return None

    def load_dataset_head_for_preview(
        self, dataset_id: str, nrows: int = 10
    ) -> Optional[Tuple[pd.DataFrame, int, int]]:
        """
        Load only the first ``nrows`` for preview APIs (avoids loading multi-GB Parquet/CSV into RAM).
        Returns (preview_df, total_row_count, column_count) or None if the dataset is missing.
        """
        store = get_object_storage()
        if dataset_id not in self.datasets:
            disk_info = self._load_dataset_info_from_disk(dataset_id)
            if not disk_info:
                self.logger.warning("Dataset not found for head preview: %s", dataset_id)
                return None

        dataset_info = self.datasets[dataset_id]
        csv_key = _normalize_storage_key(
            str(dataset_info.get("storage_key") or dataset_info["file_path"])
        )
        pq_k = _parquet_key(csv_key)

        try:
            if store.exists(pq_k):
                with store.open_binary_stream(pq_k) as fp:
                    preview, total_rows, ncols = _read_parquet_head_streaming(fp, nrows)
                self.logger.info(
                    "Preview head from Parquet: %s rows_total=%s preview_shape=%s",
                    dataset_id,
                    total_rows,
                    getattr(preview, "shape", None),
                )
                return preview, int(total_rows), int(ncols)

            if not store.exists(csv_key):
                self.logger.warning("No Parquet or CSV object for head preview: %s", dataset_id)
                return None

            preview_df, total_data_rows = _read_csv_head_streaming(store, csv_key, nrows)
            ncols = int(len(preview_df.columns)) if preview_df is not None else 0
            self.logger.info(
                "Preview head from CSV: %s rows_total~=%s preview_shape=%s",
                dataset_id,
                total_data_rows,
                getattr(preview_df, "shape", None),
            )
            return preview_df, int(total_data_rows), ncols
        except Exception as exc:
            self.logger.error("load_dataset_head_for_preview failed for %s: %s", dataset_id, exc)
            return None

    def validate_dataset(
        self,
        df: pd.DataFrame,
        duplicate_row_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        self.logger.info("Validating dataset with shape: %s", df.shape)
        validation_result: Dict[str, Any] = {"is_valid": True, "errors": [], "warnings": []}
        if df.empty:
            validation_result["is_valid"] = False
            validation_result["errors"].append("The uploaded file is empty.")
            self.logger.warning("Dataset validation failed: Empty file")
        if df.shape[1] < 2:
            validation_result["is_valid"] = False
            validation_result["errors"].append("Dataset must have at least 2 columns.")
            self.logger.warning("Dataset validation failed: Insufficient columns")
        missing_data = df.isnull().sum()
        if missing_data.sum() > 0:
            validation_result["warnings"].append(
                f"Dataset contains {missing_data.sum()} missing values."
            )
            self.logger.info("Dataset has %s missing values", missing_data.sum())
        dup_count = (
            int(duplicate_row_count)
            if duplicate_row_count is not None
            else int(df.duplicated().sum())
        )
        if dup_count > 0:
            validation_result["warnings"].append(
                f"Dataset contains {dup_count} duplicate rows."
            )
            self.logger.info("Dataset has %s duplicate rows", dup_count)
        self.logger.info(
            "Dataset validation completed: Valid=%s, Errors=%s, Warnings=%s",
            validation_result["is_valid"],
            len(validation_result["errors"]),
            len(validation_result["warnings"]),
        )
        return validation_result

    def get_dataset_stats(
        self,
        df: pd.DataFrame,
        target_variable: Optional[str] = None,
        duplicate_rows: Optional[int] = None,
        skip_missing_summary: bool = False,
        skip_duplicate_count: bool = False,
    ) -> DataStats:
        """Compute summary stats over ``df``.

        The expensive operations are gated so callers on the hot ``/upload``
        path can opt out:

        * ``skip_missing_summary``: skip ``df.isnull().sum()`` (O(rows*cols),
          ~5-15 s on a 2 GB / ~5 M-row frame). Returns an empty mapping.
        * ``skip_duplicate_count``: skip ``df.duplicated().sum()`` when the
          caller did not pre-compute one (O(rows), ~30-60 s on 2 GB).

        ``memory_usage`` is always shallow (``deep=False``); ``deep=True``
        walks every Python string in every object column and on a 2 GB
        DataFrame can itself take ~30 s, but the value is only used for
        display and the shallow estimate is good enough for that.
        """
        if skip_missing_summary:
            missing_dict: Dict[str, int] = {}
        else:
            missing_data = df.isnull().sum()
            missing_dict = {
                col: int(count) for col, count in missing_data[missing_data > 0].items()
            }
        column_types = {col: str(dtype) for col, dtype in df.dtypes.items()}
        target_info = None
        if target_variable and target_variable in df.columns:
            target_col = df[target_variable]
            unique_vals = int(target_col.nunique())
            if unique_vals <= 10:
                target_info = {
                    "type": "categorical",
                    "unique_values": unique_vals,
                    "value_counts": target_col.value_counts().head(5).to_dict(),
                }
            else:
                target_info = {
                    "type": "numerical",
                    "min": float(target_col.min()),
                    "max": float(target_col.max()),
                    "mean": float(target_col.mean()),
                    "std": float(target_col.std()),
                }
        if duplicate_rows is not None:
            dup_rows = int(duplicate_rows)
        elif skip_duplicate_count:
            dup_rows = 0
        else:
            dup_rows = int(df.duplicated().sum())
        return DataStats(
            rows=df.shape[0],
            columns=df.shape[1],
            memory_usage_mb=float(df.memory_usage(deep=False).sum() / 1024**2),
            missing_values=missing_dict,
            duplicate_rows=dup_rows,
            column_types=column_types,
            target_variable_info=target_info,
        )

    def store_dataset_info(
        self,
        dataset_id: str,
        file_path: str,
        filename: str,
        target_variable: str,
        target_variable_type: str,
        data_dictionary: str,
        problem_statement: str,
        unique_id_combinations: list = None,
        segmentation_variable: str = None,
        sample_identifier_variable: str = None,
        split_configuration: dict = None,
    ) -> None:
        key = _normalize_storage_key(file_path)
        row = {
            "file_path": key,
            "storage_key": key,
            "filename": filename,
            "target_variable": target_variable,
            "target_variable_type": target_variable_type,
            "data_dictionary": data_dictionary,
            "problem_statement": problem_statement,
            "unique_id_combinations": unique_id_combinations or [],
            "segmentation_variable": segmentation_variable,
            "sample_identifier_variable": sample_identifier_variable,
            "uploaded_at": pd.Timestamp.now().isoformat(),
        }
        if split_configuration is not None:
            row["split_configuration"] = split_configuration
        self.datasets[dataset_id] = row

    @contextmanager
    def materialize_unique_id_validation_path(
        self, dataset_id: str
    ) -> Iterator[Tuple[Optional[str], bool]]:
        """
        Yield ``(path, is_parquet)`` for streaming unique-ID checks.

        Prefers the Parquet sidecar over the raw CSV. For local storage the
        path points directly into ``upload_dir``. For remote storage (S3),
        the file is staged through ``SidecarCache`` so subsequent calls for
        the same ``(key, version)`` pair are instant; the cached entry is
        pinned for the duration of the ``with`` block.

        Yields ``(None, False)`` if the dataset is unknown or its file is
        missing. Callers must use this in a ``with`` statement so the
        sidecar cache can release its refcount.
        """
        info = self.get_dataset_info(dataset_id)
        if not info:
            yield None, False
            return
        csv_key = _normalize_storage_key(
            str(info.get("storage_key") or info.get("file_path") or "")
        )
        if not csv_key:
            yield None, False
            return
        pq_key = _parquet_key(csv_key)
        store = get_object_storage()

        target_key: Optional[str] = None
        is_pq = False
        if store.exists(pq_key):
            target_key = pq_key
            is_pq = True
        elif store.exists(csv_key):
            target_key = csv_key
            is_pq = False
        if target_key is None:
            yield None, False
            return

        if store.kind == "local":
            p = (self.upload_dir / target_key).resolve()
            if p.is_file():
                yield str(p), is_pq
                return
            yield None, False
            return

        # Remote storage: route through the local sidecar cache so the file
        # is downloaded at most once per (key, etag) pair.
        from app.services.sidecar_cache import get_sidecar_cache  # noqa: WPS433

        with get_sidecar_cache().acquire(store, target_key) as cached_path:
            yield str(cached_path), is_pq

    def get_dataset_info(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        if dataset_id in self.datasets:
            return self.datasets.get(dataset_id)
        return self._load_dataset_info_from_disk(dataset_id)

    def delete_dataset(self, dataset_id: str) -> bool:
        if dataset_id not in self.datasets:
            if not self._load_dataset_info_from_disk(dataset_id):
                return False
        dataset_info = self.datasets[dataset_id]
        ref = str(dataset_info.get("storage_key") or dataset_info["file_path"])
        csv_key = _normalize_storage_key(ref)
        store = get_object_storage()

        leg = Path(ref)
        if leg.is_absolute() and leg.is_file():
            try:
                leg.unlink()
            except OSError:
                pass
        pq_k = _parquet_key(csv_key)
        store.delete(csv_key)
        store.delete(pq_k)
        store.delete(_metadata_object_key(dataset_id))
        mp = self._metadata_path(dataset_id)
        if mp.exists():
            try:
                mp.unlink()
            except OSError:
                pass
        del self.datasets[dataset_id]
        return True

    def update_dataset_config(self, dataset_id: str, updated_config: Dict[str, Any]) -> bool:
        if dataset_id not in self.datasets:
            if not self._load_dataset_info_from_disk(dataset_id):
                return False
        current_config = self.datasets[dataset_id]
        current_config.update(updated_config)
        if "file_path" not in current_config:
            current_config["file_path"] = self.datasets[dataset_id]["file_path"]
        if "storage_key" not in current_config and "file_path" in current_config:
            current_config["storage_key"] = _normalize_storage_key(current_config["file_path"])
        if "uploaded_at" not in current_config:
            current_config["uploaded_at"] = self.datasets[dataset_id]["uploaded_at"]
        self.datasets[dataset_id] = current_config
        self._persist_dataset_info(dataset_id)
        return True

    def append_segmentation_scheme_metadata(self, dataset_id: str, scheme_record: Dict[str, Any]) -> bool:
        """
        Append one SegmentationSchemeMetadata dict (JSON-serializable) to dataset info
        and persist. Used by Add to Data for scheme registry / audit trail (plan 12.3).
        """
        if dataset_id not in self.datasets:
            if not self._load_dataset_info_from_disk(dataset_id):
                return False
        row = self.datasets[dataset_id]
        schemes = list(row.get("segmentation_schemes") or [])
        schemes.append(scheme_record)
        row["segmentation_schemes"] = schemes
        self.datasets[dataset_id] = row
        self._persist_dataset_info(dataset_id)
        return True

    def get_segmentation_schemes_metadata(self, dataset_id: str) -> list:
        """Return stored segmentation scheme metadata records (list of dicts)."""
        if dataset_id not in self.datasets:
            if not self._load_dataset_info_from_disk(dataset_id):
                return []
        row = self.datasets.get(dataset_id) or {}
        return list(row.get("segmentation_schemes") or [])

    _SEGMENTATION_AUDIT_LOG_MAX = 2000

    def append_segmentation_audit_event(self, dataset_id: str, event: Dict[str, Any]) -> bool:
        """
        Append one structured segmentation audit row (plan Section 15) to dataset metadata
        and persist. Events are capped to the most recent _SEGMENTATION_AUDIT_LOG_MAX entries.
        """
        if dataset_id not in self.datasets:
            if not self._load_dataset_info_from_disk(dataset_id):
                return False
        row = self.datasets[dataset_id]
        log = list(row.get("segmentation_audit_log") or [])
        log.append(event)
        if len(log) > self._SEGMENTATION_AUDIT_LOG_MAX:
            log = log[-self._SEGMENTATION_AUDIT_LOG_MAX :]
        row["segmentation_audit_log"] = log
        self.datasets[dataset_id] = row
        self._persist_dataset_info(dataset_id)
        return True

    def get_segmentation_audit_log(self, dataset_id: str) -> list:
        """Return persisted segmentation audit events (newest last)."""
        if dataset_id not in self.datasets:
            if not self._load_dataset_info_from_disk(dataset_id):
                return []
        row = self.datasets.get(dataset_id) or {}
        return list(row.get("segmentation_audit_log") or [])

    def register_existing_dataset(
        self, dataset_id: str, file_path: str, filename: str = None
    ) -> bool:
        try:
            store = get_object_storage()
            p = Path(file_path)
            if p.is_file():
                key = p.name
            else:
                key = _normalize_storage_key(file_path)
            if not p.is_file() and not store.exists(key):
                self.logger.error("File not found: %s", file_path)
                return False
            if filename is None:
                filename = key
            self.datasets[dataset_id] = {
                "file_path": key,
                "storage_key": key,
                "filename": filename,
                "target_variable": "target_flag",
                "target_variable_type": "binary",
                "data_dictionary": "",
                "problem_statement": "",
                "uploaded_at": pd.Timestamp.now().isoformat(),
            }
            self._persist_dataset_info(dataset_id)
            self.logger.info("Registered existing dataset: %s -> %s", dataset_id, key)
            return True
        except Exception as e:
            self.logger.error("Failed to register dataset %s: %s", dataset_id, e)
            return False


dataset_manager = DatasetManager()
