"""
DocuMind 2.0 — Hybrid Retriever
Dense + BM25 + RRF + MMR + CrossEncoder reranking pipeline.
"""

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from loguru import logger
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer, CrossEncoder

from app.config import settings
from app.vector_store.qdrant_client import qdrant_client


@dataclass
class RetrievedChunk:
    """A retrieved chunk with relevance metadata."""
    id: str
    text: str
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "text": self.text, "score": self.score,
            "page_number": self.metadata.get("page_number"),
            "source_file": self.metadata.get("source_file", ""),
            "document_id": self.metadata.get("document_id", ""),
            "chunk_type": self.metadata.get("chunk_type", ""),
        }


class HybridRetriever:
    """
    5-stage retrieval pipeline:
    1. Dense search — top-20 cosine similarity via Qdrant
    2. BM25 sparse search — top-20 keyword matching
    3. Reciprocal Rank Fusion — merge ranked lists
    4. MMR reranking — diversity (λ=0.7)
    5. CrossEncoder reranking — ms-marco-MiniLM-L-12-v2
    Returns top-k with scores and metadata.
    """

    def __init__(self):
        self._embedding_model = None
        self._cross_encoder = None

    @property
    def embedding_model(self) -> SentenceTransformer:
        if self._embedding_model is None:
            self._embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
        return self._embedding_model

    @property
    def cross_encoder(self) -> CrossEncoder:
        if self._cross_encoder is None:
            self._cross_encoder = CrossEncoder(settings.CROSS_ENCODER_MODEL)
        return self._cross_encoder

    async def retrieve(
        self, query: str, user_id: str,
        document_ids: list[str] | None = None, top_k: int = 5,
    ) -> list[RetrievedChunk]:
        """Full hybrid retrieval pipeline."""
        logger.info(f"Retrieving for query: '{query[:80]}...' (user={user_id})")

        # 1. Dense retrieval
        query_embedding = self.embedding_model.encode(query, normalize_embeddings=True).tolist()
        dense_results = await qdrant_client.search_dense(
            user_id=user_id, query_vector=query_embedding,
            document_ids=document_ids, limit=20,
        )
        dense_chunks = [
            RetrievedChunk(
                id=str(r.id), text=r.payload.get("text", ""), score=r.score,
                metadata={k: v for k, v in r.payload.items() if k != "text"},
            )
            for r in dense_results
        ]

        # 2. BM25 sparse retrieval
        all_chunks_data = await qdrant_client.get_all_chunks(user_id, document_ids, limit=500)
        bm25_chunks = self._bm25_search(query, all_chunks_data, top_k=20)

        # 3. Reciprocal Rank Fusion
        fused = self._reciprocal_rank_fusion([dense_chunks, bm25_chunks], k=60)

        if not fused:
            logger.warning("No results after fusion")
            return []

        # 4. MMR for diversity
        fused_chunks = [item["chunk"] for item in fused]
        mmr_selected = self._mmr_rerank(query_embedding, fused_chunks, lambda_param=0.7, top_n=10)

        # 5. CrossEncoder reranking
        if mmr_selected:
            pairs = [(query, chunk.text) for chunk in mmr_selected]
            scores = self.cross_encoder.predict(pairs)
            reranked = sorted(zip(mmr_selected, scores), key=lambda x: x[1], reverse=True)
            final = [chunk for chunk, _ in reranked[:top_k]]
            for i, (chunk, score) in enumerate(reranked[:top_k]):
                final[i].score = float(score)
        else:
            final = []

        logger.info(f"Retrieved {len(final)} chunks (dense={len(dense_chunks)}, bm25={len(bm25_chunks)})")
        return final

    def _bm25_search(self, query: str, chunks_data: list[dict], top_k: int = 20) -> list[RetrievedChunk]:
        """BM25 keyword search over chunk texts."""
        if not chunks_data:
            return []

        corpus = [self._tokenize(c["text"]) for c in chunks_data]
        bm25 = BM25Okapi(corpus)
        query_tokens = self._tokenize(query)
        scores = bm25.get_scores(query_tokens)
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                c = chunks_data[idx]
                results.append(RetrievedChunk(
                    id=c["id"], text=c["text"], score=float(scores[idx]),
                    metadata=c.get("metadata", {}),
                ))
        return results

    def _reciprocal_rank_fusion(self, result_lists: list[list[RetrievedChunk]], k: int = 60) -> list[dict]:
        """RRF: score(d) = sum(1 / (k + rank(d)))"""
        scores: dict[str, dict] = {}
        for result_list in result_lists:
            for rank, chunk in enumerate(result_list):
                if chunk.id not in scores:
                    scores[chunk.id] = {"chunk": chunk, "score": 0.0}
                scores[chunk.id]["score"] += 1.0 / (k + rank + 1)
        return sorted(scores.values(), key=lambda x: x["score"], reverse=True)

    def _mmr_rerank(
        self, query_embedding: list[float], chunks: list[RetrievedChunk],
        lambda_param: float = 0.7, top_n: int = 10,
    ) -> list[RetrievedChunk]:
        """Maximal Marginal Relevance for diversity."""
        if not chunks:
            return []

        query_vec = np.array(query_embedding)
        # Encode chunk texts
        chunk_embeddings = self.embedding_model.encode(
            [c.text for c in chunks], normalize_embeddings=True,
        )

        selected_indices: list[int] = []
        remaining = list(range(len(chunks)))

        for _ in range(min(top_n, len(chunks))):
            best_idx, best_score = -1, -float("inf")
            for idx in remaining:
                relevance = float(np.dot(query_vec, chunk_embeddings[idx]))
                diversity = 0.0
                if selected_indices:
                    sims = [float(np.dot(chunk_embeddings[idx], chunk_embeddings[s])) for s in selected_indices]
                    diversity = max(sims)
                mmr_score = lambda_param * relevance - (1 - lambda_param) * diversity
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = idx

            if best_idx >= 0:
                selected_indices.append(best_idx)
                remaining.remove(best_idx)

        return [chunks[i] for i in selected_indices]

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        import re
        return [t.lower() for t in re.findall(r'\b\w+\b', text) if len(t) > 1]


# Singleton
hybrid_retriever = HybridRetriever()
