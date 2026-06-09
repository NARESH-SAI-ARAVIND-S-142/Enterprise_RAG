"""
DocuMind 2.0 — RAG Pipeline Tests
Tests for the agentic graph, faithfulness, and query rewriting.
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.rag.nodes import decide_if_faithful, decide_if_sufficient
from app.rag.retriever import RetrievedChunk


def test_decide_if_sufficient_with_enough_chunks():
    """Should return 'sufficient' when context_sufficient is True."""
    state = {"context_sufficient": True, "iteration_count": 1}
    assert decide_if_sufficient(state) == "sufficient"


def test_decide_if_sufficient_insufficient():
    """Should return 'insufficient' for first retry."""
    state = {"context_sufficient": False, "iteration_count": 1}
    assert decide_if_sufficient(state) == "insufficient"


def test_decide_if_sufficient_gives_up():
    """Should return 'give_up' after 2 iterations."""
    state = {"context_sufficient": False, "iteration_count": 2}
    assert decide_if_sufficient(state) == "give_up"


def test_decide_if_faithful_above_threshold():
    """Faithful answer should pass when score >= 0.8."""
    state = {"faithfulness_score": 0.9}
    assert decide_if_faithful(state) == "faithful"


def test_decide_if_faithful_below_threshold():
    """Hallucinating answer should be flagged when score < 0.8."""
    state = {"faithfulness_score": 0.5}
    assert decide_if_faithful(state) == "hallucinating"


def test_decide_if_faithful_exact_threshold():
    """Score exactly at threshold should pass."""
    state = {"faithfulness_score": 0.8}
    assert decide_if_faithful(state) == "faithful"


@pytest.mark.asyncio
async def test_citation_formatting_node():
    """Citation formatting should produce valid citation dicts."""
    from app.rag.nodes import citation_formatting_node

    state = {
        "answer_draft": "The system uses Python for backend.",
        "retrieved_chunks": [
            RetrievedChunk(
                id="chunk-1",
                text="Python is used for the backend implementation.",
                score=0.95,
                metadata={
                    "page_number": 3,
                    "source_file": "architecture.pdf",
                    "document_id": "doc-1",
                },
            ),
        ],
        "faithfulness_score": 0.9,
        "rewritten_queries": ["What language is used?"],
        "iteration_count": 1,
    }

    result = await citation_formatting_node(state)

    assert "final_answer" in result
    assert len(result["citations"]) == 1
    assert result["citations"][0]["source_file"] == "architecture.pdf"
    assert result["confidence_score"] > 0
    assert "retrieval_metadata" in result


@pytest.mark.asyncio
async def test_relevance_grading_marks_insufficient():
    """Grading with no chunks should mark context as insufficient."""
    from app.rag.nodes import relevance_grading_node

    state = {
        "query": "What is Python?",
        "retrieved_chunks": [],
        "iteration_count": 0,
    }

    with patch("app.rag.nodes._llm_invoke_json", new_callable=AsyncMock):
        result = await relevance_grading_node(state)

    assert result["context_sufficient"] is False
    assert result["iteration_count"] == 1
