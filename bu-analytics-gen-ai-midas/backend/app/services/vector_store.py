import json
import faiss
import numpy as np
from typing import List, Dict, Any, Optional
import re
from pathlib import Path
from app.core.config import settings
from app.core.logging_config import get_logger
import pickle
from app.services.llm_service import llm_service

class VectorStore:
    def __init__(self):
        self.logger = get_logger(__name__)

        if not llm_service.is_embedding_ready():
            self.logger.warning("Embedding LLM not configured; vector store will not generate embeddings.")
        else:
            self.logger.info("VectorStore configured to use litellm embeddings")

        self.index = None
        self.documents = []
        self.index_path = Path(settings.VECTOR_STORE_PATH) / "faiss_index"
        self.documents_path = Path(settings.VECTOR_STORE_PATH) / "documents.pkl"
        self._stopwords = {
            "the", "a", "an", "and", "or", "but", "if", "then", "else", "of", "to", "in", "on",
            "for", "with", "by", "as", "at", "from", "this", "that", "these", "those", "is",
            "are", "was", "were", "be", "been", "being", "it", "its", "into", "about", "over",
            "under", "than"
        }

    def _rebuild_index_from_documents(self) -> bool:
        """Rebuild FAISS index using stored documents and current embedding provider."""
        if not self.documents:
            self.logger.warning("No documents available to rebuild vector store")
            return False

        self.logger.info("Rebuilding FAISS index with current embedding provider")
        embeddings = self._get_embeddings(self.documents)
        if embeddings.size == 0:
            self.logger.error("Rebuilt embeddings array is empty")
            return False

        embedding_dim = embeddings.shape[1] if embeddings.ndim > 1 else 1
        self.logger.info(f"Recreating FAISS index with dimension {embedding_dim}")
        self.index = faiss.IndexFlatIP(embedding_dim)
        self.index.add(embeddings)
        self.save_index()
        return True
        
    def _get_embeddings(self, texts: List[str]) -> np.ndarray:
        """Get embeddings for provided texts"""
        if not llm_service.is_embedding_ready():
            self.logger.error("Embedding LLM configuration missing")
            raise RuntimeError("Embedding provider missing; configure EMBEDDING_MODEL and credentials.")

        self.logger.debug(f"Getting embeddings for {len(texts)} texts")
        embedding_vectors = llm_service.get_embeddings(texts)
        self.logger.info(f"Successfully generated {len(embedding_vectors)} embeddings")
        return np.array(embedding_vectors, dtype=np.float32)
    
    def _get_current_embedding_dim(self) -> Optional[int]:
        """Probe the current embedding model dimension using a short test string.
        Returns None if the embedding model is not ready or the call fails."""
        if not llm_service.is_embedding_ready():
            return None
        try:
            probe = self._get_embeddings(["dimension probe"])
            if probe.ndim > 1 and probe.shape[0] > 0:
                return int(probe.shape[1])
        except Exception as e:
            self.logger.warning("Could not probe embedding dimension: %s", repr(e))
        return None

    def create_index_from_knowledge_base(self, knowledge_base_path: str):
        """Create FAISS index from knowledge base JSON.

        If an existing FAISS index is found on disk it is loaded first.  The
        dimension of the loaded index is then compared against the dimension
        reported by the currently-configured embedding model (via LiteLLM).
        When a mismatch is detected - which happens when the embedding model
        has been swapped to one that produces vectors of a different size -
        the index is automatically rebuilt from the stored documents so that
        FAISS and the active model stay in sync.  This keeps the vector store
        compatible with GraphRAG and any other consumer that relies on
        consistent embedding dimensions.
        """
        self.logger.info(f"Creating index from knowledge base: {knowledge_base_path}")
        
        # Check if index already exists on disk
        if self.index_path.exists() and self.documents_path.exists():
            self.logger.info("Vector store already exists, loading existing index...")
            self.load_index()

            # After loading, verify the stored index dimension matches the
            # current embedding model.  If the model was changed (e.g. via
            # LiteLLM model selection) the dimensions may differ and we must
            # rebuild to avoid silent mis-matches during search.
            if self.index is not None:
                current_dim = self._get_current_embedding_dim()
                if current_dim is not None and current_dim != self.index.d:
                    self.logger.warning(
                        "Embedding model dimension changed: stored index has dim=%d "
                        "but current model produces dim=%d. Rebuilding FAISS index.",
                        self.index.d, current_dim,
                    )
                    if not self._rebuild_index_from_documents():
                        self.logger.error(
                            "Failed to rebuild index after dimension change. "
                            "Vector search may return incorrect results."
                        )
                else:
                    self.logger.info(
                        "Existing FAISS index dimension (%d) matches current embedding model. "
                        "No rebuild needed.", self.index.d
                    )
            return
        
        self.logger.info("Creating new vector store from knowledge base...")
        try:
            with open(knowledge_base_path, 'r') as f:
                kb_data = json.load(f)
            self.logger.info(f"Loaded knowledge base with {len(kb_data)} items")
        except Exception as e:
            self.logger.error(f"Failed to load knowledge base from {knowledge_base_path}: {str(e)}")
            raise
        
        # Extract text chunks from knowledge base
        documents = []
        for item in kb_data:
            if not isinstance(item, dict):
                if item is not None:
                    documents.append(str(item).strip())
                continue

            # Generic/title-content knowledge format
            title = item.get("title", "")
            content = item.get("content", "")
            category = item.get("category", "")
            generic_parts = []
            if title:
                generic_parts.append(f"Title: {title}")
            if category:
                generic_parts.append(f"Category: {category}")
            if content:
                generic_parts.append(f"Content: {content}")
            if generic_parts:
                documents.append("\n".join(generic_parts).strip())

            if "features" in item:
                for feature in item["features"]:
                    if isinstance(feature, str):
                        feature_text = f"Feature: {feature}"
                        if content:
                            feature_text += f"\nContext: {content}"
                        documents.append(feature_text.strip())
                        continue

                    if not isinstance(feature, dict):
                        documents.append(str(feature).strip())
                        continue

                    # Create text representation of each feature
                    feature_text = f"Feature: {feature.get('name', '')}\n"
                    feature_text += f"Description: {feature.get('description', '')}\n"
                    
                    if "missing_value_imputation" in feature:
                        missing_info = feature["missing_value_imputation"]
                        feature_text += f"Missing Value Rule: {missing_info.get('rule', '')}\n"
                        if "actions" in missing_info:
                            feature_text += f"Missing Value Actions: {'; '.join(missing_info['actions'])}\n"
                    
                    if "outlier_detection_treatment" in feature:
                        outlier_info = feature["outlier_detection_treatment"]
                        if "detection" in outlier_info:
                            feature_text += f"Outlier Detection: {'; '.join(outlier_info['detection'])}\n"
                        if "treatment" in outlier_info:
                            feature_text += f"Outlier Treatment: {'; '.join(outlier_info['treatment'])}\n"
                    
                    documents.append(feature_text.strip())
            
            # Also include meta_data if present
            if "meta_data" in item:
                meta = item["meta_data"]
                meta_text = f"Project: {meta.get('project_name', '')}\n"
                meta_text += f"Description: {meta.get('description', '')}\n"
                meta_text += f"Model Type: {meta.get('model_type', '')}\n"
                meta_text += f"Objective: {meta.get('objective', '')}\n"
                meta_text += f"Business Context: {meta.get('business_context', '')}\n"
                documents.append(meta_text.strip())
        
        self.documents = [doc for doc in documents if doc]
        self.logger.info(f"Extracted {len(self.documents)} text chunks from knowledge base")
        
        # Get embeddings
        self.logger.info("Generating embeddings for documents...")
        embeddings = self._get_embeddings(documents)
        if embeddings.size == 0:
            raise RuntimeError("Embeddings array is empty")

        embedding_dim = embeddings.shape[1] if embeddings.ndim > 1 else 1

        # Create FAISS index
        self.logger.info(f"Creating FAISS index with dimension {embedding_dim}")
        self.index = faiss.IndexFlatIP(embedding_dim)
        self.index.add(embeddings)
        
        # Save index and documents
        self.save_index()
        self.logger.info(f"Vector store created successfully with {len(documents)} documents")
    
    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Search for similar documents"""
        self.logger.debug(f"Searching for query: '{query[:50]}...' with k={k}")
        
        if self.index is None:
            self.logger.debug("Index not loaded, attempting to load...")
            self.load_index()
        
        if self.index is None:
            self.logger.warning("Index could not be loaded, returning empty results")
            return []
        
        try:
            # Get query embedding
            query_embedding = self._get_embeddings([query])

            # Check for dimension mismatch
            if query_embedding.shape[1] != self.index.d:
                self.logger.warning("Embedding dimension mismatch: index=%s query=%s; rebuilding index", self.index.d, query_embedding.shape[1])
                if self._rebuild_index_from_documents():
                    query_embedding = self._get_embeddings([query])
                else:
                    raise AssertionError("Failed to rebuild index with new embedding dimension")

            # Search more candidates, then rerank with hybrid score
            k_search = max(k * 4, 10)
            scores, indices = self.index.search(query_embedding, k_search)

            candidates = []
            raw_scores = []
            for score, idx in zip(scores[0], indices[0]):
                if idx < len(self.documents):
                    raw_score = float(score)
                    raw_scores.append(raw_score)
                    candidates.append({
                        "document": self.documents[idx],
                        "score": raw_score,
                        "index": int(idx),
                    })

            if not candidates:
                self.logger.debug("Search completed, found 0 results")
                return []

            min_score = min(raw_scores)
            max_score = max(raw_scores)
            score_range = max_score - min_score

            query_tokens = self._tokenize(query)
            for candidate in candidates:
                doc_tokens = self._tokenize(candidate["document"])
                keyword_overlap = self._keyword_overlap(query_tokens, doc_tokens)
                if score_range > 0:
                    vector_score_norm = (candidate["score"] - min_score) / score_range
                else:
                    vector_score_norm = 1.0
                hybrid_score = (0.7 * vector_score_norm) + (0.3 * keyword_overlap)
                candidate["keyword_overlap"] = keyword_overlap
                candidate["hybrid_score"] = hybrid_score

            candidates.sort(key=lambda item: item["hybrid_score"], reverse=True)
            results = []
            for i, candidate in enumerate(candidates[:k]):
                results.append({
                    "document": candidate["document"],
                    "score": candidate["score"],
                    "rank": i + 1,
                    "keyword_overlap": candidate["keyword_overlap"],
                    "hybrid_score": candidate["hybrid_score"],
                })

            self.logger.debug(f"Search completed, found {len(results)} results")
            return results
            
        except Exception as e:
            self.logger.error("Search failed: %s", repr(e), exc_info=True)
            return []
    
    def save_index(self):
        """Save FAISS index and documents"""
        try:
            if self.index is not None:
                faiss.write_index(self.index, str(self.index_path))
                self.logger.debug(f"Saved FAISS index to {self.index_path}")
            
            with open(self.documents_path, 'wb') as f:
                pickle.dump(self.documents, f)
            self.logger.debug(f"Saved documents to {self.documents_path}")
            
            self.logger.info("Vector store saved successfully")
        except Exception as e:
            self.logger.error(f"Failed to save vector store: {str(e)}")
            raise
    
    def load_index(self):
        """Load FAISS index and documents"""
        try:
            if self.index_path.exists() and self.documents_path.exists():
                self.logger.debug("Loading existing vector store...")
                self.index = faiss.read_index(str(self.index_path))
                with open(self.documents_path, 'rb') as f:
                    self.documents = pickle.load(f)
                self.logger.info(f"Vector store loaded successfully with {len(self.documents)} documents")
            else:
                self.logger.warning("Vector store files not found")
        except Exception as e:
            self.logger.error(f"Failed to load vector store: {str(e)}")
            raise
    
    def get_relevant_context(self, query: str, max_chunks: int = 3) -> str:
        """Get relevant context from knowledge base for a query"""
        self.logger.debug(f"Getting relevant context for query: '{query[:50]}...'")
        
        # Check if vector store is initialized
        if self.index is None:
            self.logger.warning("Vector store not initialized, returning empty context")
            return ""
        
        results = self.search(query, k=max_chunks)
        if not results:
            self.logger.debug("No relevant context found")
            return ""
        
        context_parts = []
        for result in results:
            context_parts.append(result["document"])
        
        context = "\n\n".join(context_parts)
        self.logger.debug(f"Retrieved context with {len(context_parts)} chunks")
        return context
    
    def is_initialized(self) -> bool:
        """Check if vector store is properly initialized"""
        return self.index is not None and len(self.documents) > 0

    def check_and_rebuild_if_needed(self) -> bool:
        """Check whether the current embedding model dimension matches the stored
        FAISS index and rebuild if not.

        This should be called whenever the active embedding model may have
        changed at runtime (e.g. after the LiteLLM model-selection middleware
        updates the session selection, or after GraphRAG re-initialises with a
        different provider).

        Returns True if the index is valid (either already correct or
        successfully rebuilt), False if a rebuild was attempted but failed.
        """
        if self.index is None:
            self.logger.debug("check_and_rebuild_if_needed: index not loaded, nothing to check.")
            return False

        current_dim = self._get_current_embedding_dim()
        if current_dim is None:
            self.logger.debug("check_and_rebuild_if_needed: embedding model not ready, skipping check.")
            return True  # can't verify, assume ok

        if current_dim == self.index.d:
            self.logger.debug(
                "check_and_rebuild_if_needed: dimension %d matches, no rebuild needed.", current_dim
            )
            return True

        self.logger.warning(
            "check_and_rebuild_if_needed: dimension mismatch (index=%d, model=%d). "
            "Triggering FAISS rebuild.", self.index.d, current_dim
        )
        success = self._rebuild_index_from_documents()
        if success:
            self.logger.info(
                "check_and_rebuild_if_needed: FAISS index rebuilt successfully with dim=%d.", current_dim
            )
        else:
            self.logger.error("check_and_rebuild_if_needed: FAISS rebuild failed.")
        return success

    def _tokenize(self, text: str) -> List[str]:
        tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
        return [token for token in tokens if token and token not in self._stopwords]

    def _keyword_overlap(self, query_tokens: List[str], doc_tokens: List[str]) -> float:
        if not query_tokens or not doc_tokens:
            return 0.0
        overlap = len(set(query_tokens) & set(doc_tokens))
        return overlap / max(len(set(query_tokens)), 1)

# Global vector store instance
vector_store = VectorStore()
