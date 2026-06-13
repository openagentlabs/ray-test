import io
import json
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import faiss
import numpy as np
import pandas as pd
from fastapi import UploadFile

from app.core.config import settings
from app.core.logging_config import get_logger
from app.services.llm_service import llm_service

logger = get_logger(__name__)


SUPPORTED_EXTENSIONS = {".txt", ".csv", ".xlsx", ".pdf", ".docx"}
SCOPES = {"objectives", "data_treatment", "data_insights", "feature_engineering", "global"}


@dataclass
class UserKnowledgeIndex:
    scope: str
    index: Optional[faiss.Index] = None
    documents: List[str] = field(default_factory=list)
    metadata: List[Dict[str, str]] = field(default_factory=list)
    use_exl_expertise: bool = True


class UserKnowledgeService:
    def __init__(self):
        self._stores: Dict[str, Dict[str, UserKnowledgeIndex]] = {}
        self._preferences: Dict[str, Dict[str, bool]] = {}
        self._base_dir = Path(settings.VECTOR_STORE_PATH) / "user"
        self._base_dir.mkdir(parents=True, exist_ok=True)
        # Must persist across workers/containers; in-memory only breaks Docker multi-worker flow.
        self._persist = True

    def ingest_files(
        self,
        dataset_id: str,
        scope: str,
        use_across_midas: bool,
        use_exl_expertise: bool,
        files: List[UploadFile],
    ) -> Dict[str, int]:
        if scope not in SCOPES:
            raise ValueError(f"Unsupported scope: {scope}")
        target_scope = "global" if use_across_midas else scope

        texts, metadata = self._extract_texts(files)
        chunks, chunk_meta = self._chunk_texts(texts, metadata)

        store = self._load_or_init_store(dataset_id, target_scope)
        store.use_exl_expertise = use_exl_expertise
        self._set_preference(dataset_id, target_scope, use_exl_expertise)
        store.documents.extend(chunks)
        store.metadata.extend(chunk_meta)

        self._rebuild_index(store)
        if self._persist:
            self._persist_store(dataset_id, store)

        return {
            "indexed_chunks": len(chunks),
            "total_chunks": len(store.documents),
        }

    def set_preferences(
        self,
        dataset_id: str,
        scope: str,
        use_across_midas: bool,
        use_exl_expertise: bool,
    ) -> None:
        if scope not in SCOPES:
            raise ValueError(f"Unsupported scope: {scope}")
        target_scope = "global" if use_across_midas else scope
        self._set_preference(dataset_id, target_scope, use_exl_expertise)
        store = self._load_or_init_store(dataset_id, target_scope)
        store.use_exl_expertise = use_exl_expertise
        if self._persist:
            self._persist_store(dataset_id, store)

    def get_context(
        self,
        user_query: str,
        dataset_id: str,
        scope: str,
        top_k: int = 4,
    ) -> Dict[str, object]:
        if scope not in SCOPES:
            return {"context": "", "use_exl_expertise": True, "chunks_returned": 0, "source_files": []}

        use_exl = self._resolve_use_exl_expertise(dataset_id, scope)
        scopes_to_use = self._resolve_scopes(dataset_id, scope)
        if not scopes_to_use:
            return {"context": "", "use_exl_expertise": use_exl, "chunks_returned": 0, "source_files": []}

        if use_exl is False:
            all_docs: List[str] = []
            all_meta: List[Dict[str, str]] = []
            for scope_name in scopes_to_use:
                store = self._load_or_init_store(dataset_id, scope_name)
                all_docs.extend(store.documents)
                all_meta.extend(store.metadata)
            if all_docs and len(all_docs) <= 20:
                # Extract unique filenames from metadata
                source_files = list(set(meta.get("filename", "") for meta in all_meta if meta.get("filename")))
                result = {
                    "context": "\n\n".join(all_docs),
                    "use_exl_expertise": use_exl,
                    "chunks_returned": len(all_docs),
                    "source_files": source_files,
                }
                logger.info(
                    "User knowledge full-pass for dataset=%s scope=%s chunks=%d use_exl=%s files=%s",
                    dataset_id,
                    scope,
                    result["chunks_returned"],
                    result["use_exl_expertise"],
                    source_files,
                )
                return result

        query_embedding = self._get_query_embedding(user_query)
        if query_embedding is None:
            return {
                "context": "",
                "use_exl_expertise": use_exl,
                "chunks_returned": 0,
                "source_files": [],
            }

        context_parts: List[str] = []
        used_meta: List[Dict[str, str]] = []
        if use_exl is False:
            top_k = max(top_k, 10)
        for scope_name in scopes_to_use:
            store = self._load_or_init_store(dataset_id, scope_name)
            if store.index is None or not store.documents:
                continue
            scores, indices = store.index.search(query_embedding, top_k)
            for idx in indices[0]:
                if 0 <= idx < len(store.documents):
                    context_parts.append(store.documents[idx])
                    if idx < len(store.metadata):
                        used_meta.append(store.metadata[idx])
            if use_exl is False and store.documents:
                first_chunk = store.documents[0]
                if first_chunk not in context_parts:
                    context_parts.append(first_chunk)
                    if len(store.metadata) > 0:
                        used_meta.append(store.metadata[0])

        # Extract unique filenames from metadata
        source_files = list(set(meta.get("filename", "") for meta in used_meta if meta.get("filename")))

        result = {
            "context": "\n\n".join(context_parts),
            "use_exl_expertise": use_exl,
            "chunks_returned": len(context_parts),
            "source_files": source_files,
        }
        if result["chunks_returned"]:
            logger.info(
                "User knowledge hit for dataset=%s scope=%s chunks=%d use_exl=%s files=%s",
                dataset_id,
                scope,
                result["chunks_returned"],
                result["use_exl_expertise"],
                source_files,
            )
        return result

    def clear_dataset(self, dataset_id: str) -> None:
        self._stores.pop(dataset_id, None)
        self._preferences.pop(dataset_id, None)
        dataset_dir = self._base_dir / dataset_id
        if dataset_dir.exists():
            for path in dataset_dir.rglob("*"):
                try:
                    path.unlink()
                except Exception:
                    continue
            for path in sorted(dataset_dir.glob("*"), reverse=True):
                try:
                    path.rmdir()
                except Exception:
                    continue
            try:
                dataset_dir.rmdir()
            except Exception:
                pass

    def _resolve_scopes(self, dataset_id: str, scope: str) -> List[str]:
        scopes = []
        dataset_dir = self._base_dir / dataset_id
        global_dir = dataset_dir / "global"
        if global_dir.exists() or self._store_exists(dataset_id, "global"):
            scopes.append("global")
        scope_dir = dataset_dir / scope
        if scope_dir.exists() or self._store_exists(dataset_id, scope):
            scopes.append(scope)
        return scopes

    def _resolve_use_exl_expertise(self, dataset_id: str, scope: str) -> bool:
        prefs = self._preferences.get(dataset_id, {})
        if scope in prefs:
            return prefs[scope]
        if "global" in prefs:
            return prefs["global"]

        # Cross-worker fallback: read persisted metadata when in-memory prefs are absent.
        scoped_disk_pref = self._read_persisted_use_exl(dataset_id, scope)
        if scoped_disk_pref is not None:
            return scoped_disk_pref
        global_disk_pref = self._read_persisted_use_exl(dataset_id, "global")
        if global_disk_pref is not None:
            return global_disk_pref

        dataset_store = self._stores.get(dataset_id, {})
        scoped_store = dataset_store.get(scope)
        if scoped_store is not None:
            return scoped_store.use_exl_expertise
        global_store = dataset_store.get("global")
        if global_store is not None:
            return global_store.use_exl_expertise
        return True

    def _set_preference(self, dataset_id: str, scope: str, use_exl_expertise: bool) -> None:
        dataset_prefs = self._preferences.setdefault(dataset_id, {})
        dataset_prefs[scope] = use_exl_expertise

    def _read_persisted_use_exl(self, dataset_id: str, scope: str) -> Optional[bool]:
        meta_path = self._scope_dir(dataset_id, scope) / "meta.json"
        if not meta_path.exists():
            return None
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            return bool(meta.get("use_exl_expertise", True))
        except Exception:
            return None

    def _store_exists(self, dataset_id: str, scope: str) -> bool:
        return dataset_id in self._stores and scope in self._stores[dataset_id]

    def _load_or_init_store(self, dataset_id: str, scope: str) -> UserKnowledgeIndex:
        dataset_store = self._stores.setdefault(dataset_id, {})
        if scope in dataset_store:
            return dataset_store[scope]

        store = UserKnowledgeIndex(scope=scope)
        if self._persist:
            self._load_store(dataset_id, store)
        dataset_store[scope] = store
        return store

    def _load_store(self, dataset_id: str, store: UserKnowledgeIndex) -> None:
        scope_dir = self._scope_dir(dataset_id, store.scope)
        index_path = scope_dir / "faiss_index"
        docs_path = scope_dir / "documents.pkl"
        meta_path = scope_dir / "meta.json"

        if index_path.exists() and docs_path.exists():
            try:
                store.index = faiss.read_index(str(index_path))
                with open(docs_path, "rb") as f:
                    store.documents = pickle.load(f)
            except Exception as exc:
                logger.warning(f"Failed to load user knowledge index: {exc}")

        if meta_path.exists():
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    store.use_exl_expertise = bool(meta.get("use_exl_expertise", True))
                    store.metadata = meta.get("metadata", [])
            except Exception:
                pass

    def _persist_store(self, dataset_id: str, store: UserKnowledgeIndex) -> None:
        scope_dir = self._scope_dir(dataset_id, store.scope)
        scope_dir.mkdir(parents=True, exist_ok=True)
        index_path = scope_dir / "faiss_index"
        docs_path = scope_dir / "documents.pkl"
        meta_path = scope_dir / "meta.json"

        if store.index is not None:
            faiss.write_index(store.index, str(index_path))
        with open(docs_path, "wb") as f:
            pickle.dump(store.documents, f)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "use_exl_expertise": store.use_exl_expertise,
                    "metadata": store.metadata,
                },
                f,
                indent=2,
            )

    def _scope_dir(self, dataset_id: str, scope: str) -> Path:
        return self._base_dir / dataset_id / scope

    def _rebuild_index(self, store: UserKnowledgeIndex) -> None:
        if not store.documents:
            store.index = None
            return
        embeddings = self._get_embeddings(store.documents)
        if embeddings.size == 0:
            store.index = None
            return
        dim = embeddings.shape[1] if embeddings.ndim > 1 else 1
        store.index = faiss.IndexFlatIP(dim)
        store.index.add(embeddings)

    def _get_embeddings(self, texts: List[str]) -> np.ndarray:
        if not llm_service.embedding_ready:
            raise RuntimeError("Embedding provider is not configured.")
        vectors = llm_service.get_embeddings(texts)
        return np.array(vectors, dtype=np.float32)

    def _get_query_embedding(self, query: str) -> Optional[np.ndarray]:
        if not llm_service.embedding_ready:
            return None
        try:
            vectors = llm_service.get_embeddings([query])
            return np.array(vectors, dtype=np.float32)
        except Exception as exc:
            logger.warning(f"User knowledge embedding failed: {exc}")
            return None

    def _extract_texts(self, files: List[UploadFile]) -> Tuple[List[str], List[Dict[str, str]]]:
        texts: List[str] = []
        metadata: List[Dict[str, str]] = []

        for upload in files:
            suffix = Path(upload.filename or "").suffix.lower()
            if suffix not in SUPPORTED_EXTENSIONS:
                logger.warning(f"Skipping unsupported file: {upload.filename}")
                continue

            content = upload.file.read()
            extracted = self._parse_file_bytes(content, suffix)
            if extracted:
                texts.append(extracted)
                metadata.append({"filename": upload.filename or "unknown", "type": suffix})

        return texts, metadata

    def _parse_file_bytes(self, content: bytes, suffix: str) -> str:
        try:
            if suffix == ".txt":
                return content.decode("utf-8", errors="ignore")
            if suffix == ".csv":
                df = pd.read_csv(io.BytesIO(content))
                return df.to_csv(index=False)
            if suffix == ".xlsx":
                xls = pd.ExcelFile(io.BytesIO(content))
                sheets = []
                for sheet_name in xls.sheet_names:
                    df = xls.parse(sheet_name)
                    sheets.append(f"[Sheet: {sheet_name}]\n{df.to_csv(index=False)}")
                return "\n\n".join(sheets)
            if suffix == ".pdf":
                from PyPDF2 import PdfReader
                reader = PdfReader(io.BytesIO(content))
                pages = [page.extract_text() or "" for page in reader.pages]
                return "\n\n".join(pages)
            if suffix == ".docx":
                from docx import Document
                doc = Document(io.BytesIO(content))
                paragraphs = [p.text for p in doc.paragraphs if p.text]
                return "\n".join(paragraphs)
        except Exception as exc:
            logger.warning(f"Failed to parse {suffix} content: {exc}")
        return ""

    def _chunk_texts(
        self,
        texts: List[str],
        metadata: List[Dict[str, str]],
        chunk_size: int = 900,
        overlap: int = 180,
    ) -> Tuple[List[str], List[Dict[str, str]]]:
        chunks: List[str] = []
        chunk_meta: List[Dict[str, str]] = []

        for text, meta in zip(texts, metadata):
            cleaned = (text or "").strip()
            if not cleaned:
                continue
            start = 0
            while start < len(cleaned):
                end = min(start + chunk_size, len(cleaned))
                chunk = cleaned[start:end]
                prefix = f"[{meta.get('filename', 'unknown')}] "
                chunks.append(prefix + chunk)
                chunk_meta.append(meta)
                if end == len(cleaned):
                    break
                start = end - overlap
        return chunks, chunk_meta


user_knowledge_service = UserKnowledgeService()
