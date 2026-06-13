"""
Utility to embed plain TXT knowledge files directly into the FAISS store.

Running this script bypasses the GraphRAG exporter: it reads every `.txt` under
`knowledge_repo_kg/input/`, submits the content to Azure OpenAI embeddings, and
dumps the resulting vectors/documents into the same paths that `VectorStore`
uses (`backend/vector_store/{faiss_index,documents.pkl}`).

Usage: `python backend/scripts/load_txt_into_vector_store.py`
"""
from __future__ import annotations

import sys
import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# Ensure we can import from `app`
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))
load_dotenv(ROOT / ".env")

from app.core.logging_config import get_logger
from app.core.config import settings
from app.services.vector_store import VectorStore
from app.services.llm_service import llm_service

logger = get_logger(__name__)


def load_txt_documents(input_dir: Path) -> List[str]:
    if not input_dir.exists():
        raise FileNotFoundError(f"{input_dir} does not exist")

    texts: List[str] = []
    for txt_path in sorted(input_dir.rglob("*.txt")):
        try:
            text = txt_path.read_text(encoding="utf-8", errors="ignore").strip()
        except Exception as exc:
            logger.warning(f"Skipping {txt_path.name}: {exc}")
            continue

        if text:
            texts.append(text)
            logger.info(f"Queued {txt_path.name} ({len(text)} chars)")

    return texts


def rebuild_vector_store_from_texts(texts: List[str]) -> None:
    if not texts:
        logger.info("No text documents found; ensure files are placed in knowledge_repo_kg/input/")
        return

    settings.VECTOR_STORE_PATH = str(ROOT / "vector_store")
    vs = VectorStore()
    if not llm_service.embedding_ready:
        raise RuntimeError("Embedding provider is not configured. Update EMBEDDING_MODEL and credentials.")

    logger.info("Generating embeddings for %d text files", len(texts))
    embeddings = vs._get_embeddings(texts)

    logger.info("Creating FAISS index (dimension=%d)", settings.VECTOR_DIMENSION)
    import faiss  # noqa: WPS433

    vs.index = faiss.IndexFlatIP(settings.VECTOR_DIMENSION)
    vs.index.add(embeddings)
    vs.documents = texts
    vs.save_index()

    logger.info("FAISS vector store rebuilt from %d txt files", len(texts))


def main():
    input_dir = ROOT / "knowledge_repo_kg" / "input"
    texts = load_txt_documents(input_dir)
    rebuild_vector_store_from_texts(texts)


if __name__ == "__main__":
    main()
