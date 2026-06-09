"""
DocuMind 2.0 — Retrieval Tests
Tests for hybrid retrieval, RRF, and CrossEncoder reranking.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.rag.retriever import HybridRetriever, RetrievedChunk


@pytest.fixture
def retriever():
    return HybridRetriever()


@pytest.fixture
def sample_chunks():
    """Sample retrieved chunks for testing."""
    return [
        RetrievedChunk(
            id="chunk-1",
            text="Python is a high-level programming language known for its simplicity.",
            score=0.9,
            metadata={"page_number": 1, "source_file": "intro.pdf"},
        ),
        RetrievedChunk(
            id="chunk-2",
            text="Machine learning uses algorithms to find patterns in data.",
            score=0.85,
            metadata={"page_number": 5, "source_file": "ml.pdf"},
        ),
        RetrievedChunk(
            id="chunk-3",
            text="FastAPI is a modern web framework for building APIs with Python.",
            score=0.8,
            metadata={"page_number": 2, "source_file": "web.pdf"},
        ),
        RetrievedChunk(
            id="chunk-4",
            text="The weather today is sunny with a high of 75 degrees.",
            score=0.3,
            metadata={"page_number": 1, "source_file": "weather.pdf"},
        ),
    ]


def test_reciprocal_rank_fusion(retriever, sample_chunks):
    """RRF should merge multiple ranked lists with correct scoring."""
    list_a = sample_chunks[:2]  # chunk-1, chunk-2
    list_b = [sample_chunks[1], sample_chunks[2]]  # chunk-2, chunk-3

    fused = retriever._reciprocal_rank_fusion([list_a, list_b], k=60)

    assert len(fused) == 3, "Should have 3 unique chunks"
    # chunk-2 appears in both lists, should rank highest
    assert fused[0]["chunk"].id == "chunk-2", \
        "Chunk appearing in both lists should rank highest"


def test_rrf_with_empty_lists(retriever):
    """RRF should handle empty lists gracefully."""
    fused = retriever._reciprocal_rank_fusion([[], []], k=60)
    assert fused == []


def test_bm25_search_keyword_matching(retriever):
    """BM25 should score exact keyword matches highly."""
    chunks_data = [
        {"id": "1", "text": "Python programming language features", "metadata": {}},
        {"id": "2", "text": "Java enterprise development", "metadata": {}},
        {"id": "3", "text": "Python web development with Flask", "metadata": {}},
    ]

    results = retriever._bm25_search("Python programming", chunks_data, top_k=3)

    assert len(results) > 0
    # Python-related chunks should score higher
    python_ids = {r.id for r in results if "Python" in r.text}
    assert "1" in python_ids or "3" in python_ids, \
        "BM25 should match Python-containing chunks"


def test_retrieved_chunk_to_dict(sample_chunks):
    """RetrievedChunk.to_dict should return all required fields."""
    chunk = sample_chunks[0]
    d = chunk.to_dict()

    assert "id" in d
    assert "text" in d
    assert "score" in d
    assert "page_number" in d
    assert "source_file" in d


def test_mmr_rerank_diversity(retriever):
    """MMR should select diverse chunks, not just most similar."""
    # Create chunks with varying content
    chunks = [
        RetrievedChunk(id="1", text="Python is great for data science", score=0.9),
        RetrievedChunk(id="2", text="Python is great for machine learning", score=0.88),
        RetrievedChunk(id="3", text="JavaScript is used for web development", score=0.7),
        RetrievedChunk(id="4", text="Python is great for automation", score=0.85),
    ]

    # With high lambda (relevance-focused), Python chunks should dominate
    query_embedding = retriever.embedding_model.encode(
        "Python data science", normalize_embeddings=True
    ).tolist()

    selected = retriever._mmr_rerank(
        query_embedding, chunks, lambda_param=0.5, top_n=3
    )

    assert len(selected) == 3
    # With balanced lambda, JS chunk should appear for diversity
    selected_ids = {c.id for c in selected}
    assert "3" in selected_ids, "MMR should include diverse JS chunk"
