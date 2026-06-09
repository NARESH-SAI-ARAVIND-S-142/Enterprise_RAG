"""
DocuMind 2.0 — CrossEncoder Reranker
Wrapper around sentence-transformers CrossEncoder for final reranking.
"""

from loguru import logger
from sentence_transformers import CrossEncoder as _CrossEncoder

from app.config import settings


class CrossEncoderReranker:
    """
    CrossEncoder reranker using ms-marco-MiniLM-L-12-v2.
    Provides high-precision relevance scoring for the final reranking pass.
    """

    def __init__(self):
        self._model = None

    @property
    def model(self) -> _CrossEncoder:
        if self._model is None:
            logger.info(f"Loading CrossEncoder: {settings.CROSS_ENCODER_MODEL}")
            self._model = _CrossEncoder(settings.CROSS_ENCODER_MODEL)
        return self._model

    def rerank(
        self,
        query: str,
        texts: list[str],
        top_k: int = 5,
    ) -> list[tuple[int, float]]:
        """
        Rerank texts by relevance to query.
        Returns list of (original_index, score) sorted by score descending.
        """
        if not texts:
            return []

        pairs = [(query, text) for text in texts]
        scores = self.model.predict(pairs)

        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)

        return indexed_scores[:top_k]

    def score_pair(self, query: str, text: str) -> float:
        """Score a single query-text pair."""
        return float(self.model.predict([(query, text)])[0])


# Singleton
cross_encoder_reranker = CrossEncoderReranker()
