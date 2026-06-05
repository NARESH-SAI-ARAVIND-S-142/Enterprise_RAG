"""
DocuMind 2.0 — Embedding Pipeline
Batch embedding with sentence-transformers + BM25 sparse vectors.
"""

import numpy as np
from collections import Counter

from loguru import logger
from sentence_transformers import SentenceTransformer

from app.config import settings
from app.documents.ingestion.chunker import Chunk


class EmbeddingPipeline:
    """Generates dense embeddings and BM25 sparse vectors for chunks."""

    def __init__(self):
        self._model = None

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL_NAME}")
            self._model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
        return self._model

    def embed_chunks(self, chunks: list[Chunk], batch_size: int = 64) -> list[dict]:
        """
        Generate dense embeddings + BM25 sparse vectors for all chunks.
        Returns list of dicts ready for Qdrant upsert.
        """
        texts = [chunk.text for chunk in chunks]

        # Dense embeddings (batched)
        logger.info(f"Embedding {len(texts)} chunks (batch_size={batch_size})")
        embeddings = self.model.encode(
            texts, batch_size=batch_size, show_progress_bar=False, normalize_embeddings=True,
        )

        # BM25 sparse vectors
        sparse_vectors = self._compute_bm25_sparse(texts)

        results = []
        for i, chunk in enumerate(chunks):
            results.append({
                "id": chunk.id,
                "dense_vector": embeddings[i].tolist(),
                "sparse_indices": sparse_vectors[i]["indices"],
                "sparse_values": sparse_vectors[i]["values"],
                "text": chunk.text,
                "metadata": chunk.metadata,
            })

        logger.info(f"Embedded {len(results)} chunks successfully")
        return results

    def _compute_bm25_sparse(self, texts: list[str]) -> list[dict]:
        """Compute simple TF-based sparse vectors for BM25-like retrieval."""
        # Build vocabulary from all texts
        vocab = {}
        for text in texts:
            tokens = self._tokenize(text)
            for token in set(tokens):
                if token not in vocab:
                    vocab[token] = len(vocab)

        # Compute sparse vectors
        sparse_vectors = []
        for text in texts:
            tokens = self._tokenize(text)
            token_counts = Counter(tokens)
            indices = []
            values = []
            for token, count in token_counts.items():
                if token in vocab:
                    indices.append(vocab[token])
                    # TF score: log(1 + count)
                    values.append(float(np.log1p(count)))
            sparse_vectors.append({"indices": indices, "values": values})

        return sparse_vectors

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Simple whitespace + lowercase tokenization."""
        import re
        return [t.lower() for t in re.findall(r'\b\w+\b', text) if len(t) > 1]


# Singleton
embedding_pipeline = EmbeddingPipeline()
