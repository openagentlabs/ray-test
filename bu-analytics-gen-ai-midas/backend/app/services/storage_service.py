"""
Storage Service - Unified dataset resolution with pluggable backends.

Resolution order (first hit wins):
  1. InMemoryBackend  - DataFrameStateManager (always present)
  2. ParquetBackend   - Parquet file on disk / Azure blob path
  3. CSVBackend       - Original uploaded CSV (last resort)
  4. RedisBackend     - Activated when REDIS_URL env var is set (stub)
  5. ChromaBackend    - Activated when CHROMA_URL env var is set (stub)

All scattered pd.read_csv fallbacks across the codebase should call
`storage_service.load_dataframe(dataset_id)` instead.

Azure safety:
  - No local paths are hardcoded. PARQUET_DIR is env-configurable.
  - When running on Azure without a local filesystem, InMemoryBackend
    is the primary store; Parquet/CSV paths gracefully return None.

Future provisioning:
  - Set REDIS_URL or CHROMA_URL in Azure App Settings to activate those backends.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, List
import pandas as pd

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class DatasetNotFoundError(Exception):
    """Raised when a dataset cannot be resolved from any backend."""


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class StorageBackend(ABC):
    """Abstract interface for a dataset storage backend."""

    @abstractmethod
    async def load(self, dataset_id: str) -> Optional[pd.DataFrame]:
        """Return the DataFrame for dataset_id, or None if not available."""

    @abstractmethod
    async def save(self, dataset_id: str, df: pd.DataFrame) -> None:
        """Persist df under dataset_id."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable backend name for logging."""


# ---------------------------------------------------------------------------
# InMemoryBackend - wraps DataFrameStateManager
# ---------------------------------------------------------------------------

class InMemoryBackend(StorageBackend):
    """Primary backend: uses the in-process DataFrameStateManager."""

    @property
    def name(self) -> str:
        return "in-memory"

    async def load(self, dataset_id: str) -> Optional[pd.DataFrame]:
        # Import here to avoid circular imports at module load time
        from app.services.dataframe_state_manager import dataframe_state_manager
        df = dataframe_state_manager.get_dataframe_readonly(dataset_id)
        if df is not None:
            logger.debug(f"[InMemoryBackend] Hit for {dataset_id}, shape={df.shape}")
        return df

    async def save(self, dataset_id: str, df: pd.DataFrame) -> None:
        from app.services.dataframe_state_manager import dataframe_state_manager
        dataframe_state_manager.update_dataframe(dataset_id, df)


# ---------------------------------------------------------------------------
# ParquetBackend - fast columnar reads, preferred over CSV
# ---------------------------------------------------------------------------

class ParquetBackend(StorageBackend):
    """Reads/writes Parquet files. 3-5x faster than CSV for large datasets."""

    def __init__(self, parquet_dir: Optional[str] = None):
        self._dir = Path(parquet_dir or getattr(settings, "PARQUET_DIR", settings.UPLOAD_DIR))

    @property
    def name(self) -> str:
        return "parquet"

    def _parquet_path(self, dataset_id: str) -> Optional[Path]:
        """Find the Parquet file for dataset_id by scanning the directory."""
        if not self._dir.exists():
            return None
        # Naming convention: {dataset_id}_{original_name}.parquet
        matches = list(self._dir.glob(f"{dataset_id}_*.parquet"))
        if matches:
            return matches[0]
        # Fallback: exact match
        exact = self._dir / f"{dataset_id}.parquet"
        return exact if exact.exists() else None

    async def load(self, dataset_id: str) -> Optional[pd.DataFrame]:
        loop = asyncio.get_event_loop()
        path = self._parquet_path(dataset_id)
        if path is None:
            return None
        try:
            df = await loop.run_in_executor(
                None, lambda: pd.read_parquet(path, engine="pyarrow")
            )
            logger.info(f"[ParquetBackend] Loaded {dataset_id} from {path}, shape={df.shape}")
            return df
        except Exception as exc:
            logger.warning(f"[ParquetBackend] Failed to load {dataset_id}: {exc}")
            return None

    async def save(self, dataset_id: str, df: pd.DataFrame) -> None:
        loop = asyncio.get_event_loop()
        self._dir.mkdir(parents=True, exist_ok=True)
        # Preserve original filename suffix if already known
        path = self._dir / f"{dataset_id}.parquet"
        try:
            await loop.run_in_executor(
                None, lambda: df.to_parquet(path, engine="pyarrow", index=False)
            )
            logger.info(f"[ParquetBackend] Saved {dataset_id} to {path}")
        except Exception as exc:
            logger.warning(f"[ParquetBackend] Failed to save {dataset_id}: {exc}")

    def get_parquet_path_for_csv(self, csv_path: str) -> str:
        """Return the Parquet path that corresponds to a given CSV path."""
        p = Path(csv_path)
        return str(p.with_suffix(".parquet"))


# ---------------------------------------------------------------------------
# CSVBackend - last-resort fallback using DatasetManager
# ---------------------------------------------------------------------------

class CSVBackend(StorageBackend):
    """Loads from the original uploaded CSV via DatasetManager."""

    @property
    def name(self) -> str:
        return "csv"

    async def load(self, dataset_id: str) -> Optional[pd.DataFrame]:
        loop = asyncio.get_event_loop()
        try:
            from app.services.dataset_service import dataset_manager
            df = await loop.run_in_executor(
                None, dataset_manager.load_dataset, dataset_id
            )
            if df is not None:
                logger.info(f"[CSVBackend] Loaded {dataset_id} from CSV, shape={df.shape}")
            return df
        except Exception as exc:
            logger.warning(f"[CSVBackend] Failed to load {dataset_id}: {exc}")
            return None

    async def save(self, dataset_id: str, df: pd.DataFrame) -> None:
        # CSV backend is read-only (uploads are managed by DatasetManager)
        logger.debug(f"[CSVBackend] save() is a no-op for {dataset_id}")


# ---------------------------------------------------------------------------
# RedisBackend - stub, activated by REDIS_URL env var
# ---------------------------------------------------------------------------

class RedisBackend(StorageBackend):
    """
    Stub Redis backend. Activate by setting REDIS_URL in environment.
    Implement load/save using redis-py or aioredis when provisioned on Azure.
    """

    @property
    def name(self) -> str:
        return "redis"

    async def load(self, dataset_id: str) -> Optional[pd.DataFrame]:
        # TODO: implement with aioredis + pickle/parquet serialization
        logger.debug(f"[RedisBackend] stub load for {dataset_id} - not yet implemented")
        return None

    async def save(self, dataset_id: str, df: pd.DataFrame) -> None:
        # TODO: implement with aioredis + pickle/parquet serialization
        logger.debug(f"[RedisBackend] stub save for {dataset_id} - not yet implemented")


# ---------------------------------------------------------------------------
# ChromaBackend - stub, activated by CHROMA_URL env var
# ---------------------------------------------------------------------------

class ChromaBackend(StorageBackend):
    """
    Stub Chroma backend for vector/metadata storage.
    Activate by setting CHROMA_URL in environment.
    Note: Chroma is not a tabular store; this stub is for future metadata/embedding use.
    """

    @property
    def name(self) -> str:
        return "chroma"

    async def load(self, dataset_id: str) -> Optional[pd.DataFrame]:
        logger.debug(f"[ChromaBackend] stub load for {dataset_id} - not yet implemented")
        return None

    async def save(self, dataset_id: str, df: pd.DataFrame) -> None:
        logger.debug(f"[ChromaBackend] stub save for {dataset_id} - not yet implemented")


# ---------------------------------------------------------------------------
# StorageService - orchestrates resolution chain
# ---------------------------------------------------------------------------

class StorageService:
    """
    Resolves datasets through a prioritised chain of backends.

    Resolution order:
      1. InMemoryBackend
      2. RedisBackend (if REDIS_URL set)
      3. ParquetBackend
      4. CSVBackend
      5. ChromaBackend (if CHROMA_URL set, metadata only)

    After a miss on InMemory, the resolved DataFrame is written back to
    InMemoryBackend so subsequent calls are fast.
    """

    def __init__(self):
        self._backends: List[StorageBackend] = self._build_chain()

    def _build_chain(self) -> List[StorageBackend]:
        chain: List[StorageBackend] = [InMemoryBackend()]

        redis_url = getattr(settings, "REDIS_URL", None)
        if redis_url:
            chain.append(RedisBackend())
            logger.info("StorageService: RedisBackend enabled")

        chain.append(ParquetBackend())
        chain.append(CSVBackend())

        chroma_url = getattr(settings, "CHROMA_URL", None)
        if chroma_url:
            chain.append(ChromaBackend())
            logger.info("StorageService: ChromaBackend enabled")

        logger.info(f"StorageService chain: {[b.name for b in chain]}")
        return chain

    async def load_dataframe(self, dataset_id: str) -> pd.DataFrame:
        """
        Load a DataFrame for dataset_id using the resolution chain.
        Raises DatasetNotFoundError if no backend can supply the data.
        """
        for backend in self._backends:
            df = await backend.load(dataset_id)
            if df is not None:
                # Write-back to in-memory if we had to go past it
                if not isinstance(backend, InMemoryBackend):
                    try:
                        await self._backends[0].save(dataset_id, df)
                        logger.info(
                            f"StorageService: wrote {dataset_id} back to in-memory "
                            f"after loading from [{backend.name}]"
                        )
                    except Exception as wb_exc:
                        logger.warning(f"StorageService: write-back failed: {wb_exc}")
                return df

        raise DatasetNotFoundError(
            f"Dataset '{dataset_id}' not found in any storage backend. "
            "Ensure the dataset was uploaded and is still in session memory or on disk."
        )

    async def load_dataframe_or_none(self, dataset_id: str) -> Optional[pd.DataFrame]:
        """Like load_dataframe but returns None instead of raising."""
        try:
            return await self.load_dataframe(dataset_id)
        except DatasetNotFoundError:
            return None

    async def save_dataframe(self, dataset_id: str, df: pd.DataFrame) -> None:
        """Persist to all writable backends (in-memory + Parquet)."""
        for backend in self._backends:
            try:
                await backend.save(dataset_id, df)
            except Exception as exc:
                logger.warning(f"StorageService: save to [{backend.name}] failed: {exc}")

    @property
    def parquet_backend(self) -> ParquetBackend:
        """Direct access to the Parquet backend for upload-time writes."""
        for b in self._backends:
            if isinstance(b, ParquetBackend):
                return b
        raise RuntimeError("ParquetBackend not in chain")


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

storage_service = StorageService()
