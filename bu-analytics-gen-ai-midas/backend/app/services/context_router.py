from typing import Dict, List, Optional
import re

from app.services.vector_store import vector_store
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class ContextRouter:
    def __init__(
        self,
        high_threshold: float = 0.78,
        low_threshold: float = 0.45,
        coverage_threshold: float = 0.2,
        top_k: int = 5
    ):
        self.high_threshold = high_threshold
        self.low_threshold = low_threshold
        self.coverage_threshold = coverage_threshold
        self.top_k = top_k

    def evaluate(self, query: str, dataset_summary: str = "") -> Dict[str, Optional[float]]:
        """Run FAISS search and decide how confident we are in the vector context."""
        search_query = query
        if dataset_summary:
            truncated = self._truncate_summary(dataset_summary)
            search_query = f"{query}\n\nDataset Summary:\n{truncated}"
        try:
            results = vector_store.search(search_query, k=self.top_k)
        except Exception as exc:
            logger.warning(f"Vector store evaluation failed: {exc}")
            return {"status": "low", "top_score": 0, "avg_score": 0, "coverage": 0, "vector_context": ""}

        scores = [item["score"] for item in results if isinstance(item.get("score"), (int, float))]
        if not scores:
            return {"status": "low", "top_score": 0, "avg_score": 0, "coverage": 0, "vector_context": ""}

        top_score = max(scores)
        avg_score = sum(scores) / len(scores)
        coverage = self._token_coverage(query, [item["document"] for item in results])
        vector_context = "\n\n".join(item["document"] for item in results if item.get("document"))

        status = self._determine_status(top_score, avg_score, coverage)

        logger.debug(
            "Context router evaluation metrics: status=%s top_score=%.3f avg_score=%.3f coverage=%.2f",
            status,
            top_score,
            avg_score,
            coverage,
        )

        return {
            "status": status,
            "top_score": top_score,
            "avg_score": avg_score,
            "coverage": coverage,
            "vector_context": vector_context,
        }

    def _determine_status(self, top_score: float, avg_score: float, coverage: float) -> str:
        if top_score >= 0.70:
            return "vector_only"

        if top_score >= 0.5 and coverage >= 0.4:
            return "vector_only"

        if top_score <= self.low_threshold:
            return "low"

        return "ambiguous"

    def _token_coverage(self, query: str, documents: List[str]) -> float:
        if not documents:
            return 0.0
        query_tokens = set(self._normalize_tokens(query))
        if not query_tokens:
            return 0.0
        matched = 0
        for doc in documents:
            doc_tokens = set(self._normalize_tokens(doc))
            if not doc_tokens:
                continue
            overlap = len(query_tokens & doc_tokens) / len(query_tokens)
            matched += min(overlap, 1.0)
        return matched / len(documents)

    def _normalize_tokens(self, text: str) -> List[str]:
        if not text:
            return []
        normalized = text.lower()
        normalized = normalized.replace("•", " ").replace("-", " ").replace(",", " ")
        tokens = re.findall(r"[a-z0-9]+", normalized)
        stopwords = {
            "the", "a", "an", "and", "or", "but", "if", "then", "else", "of", "to", "in", "on",
            "for", "with", "by", "as", "at", "from", "this", "that", "these", "those", "is",
            "are", "was", "were", "be", "been", "being", "it", "its", "into", "about", "over",
            "under", "than"
        }
        return [token for token in tokens if token and token not in stopwords]

    def _truncate_summary(self, dataset_summary: str, limit: int = 2000) -> str:
        if not dataset_summary:
            return ""
        return dataset_summary.strip()[:limit]


context_router = ContextRouter()
