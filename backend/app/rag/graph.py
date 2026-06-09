"""
DocuMind 2.0 — LangGraph Agentic RAG Graph
Self-correcting 7-node workflow with faithfulness checking.
"""

from typing import Any

from langgraph.graph import END, StateGraph
from loguru import logger

from app.rag.nodes import (
    citation_formatting_node,
    decide_if_faithful,
    decide_if_sufficient,
    faithfulness_check_node,
    generation_node,
    query_rewriting_node,
    refinement_node,
    relevance_grading_node,
    retrieval_node,
)


# ── RAG State Definition ──────────────────────────────────────
class RAGState(dict):
    """
    State dictionary for the RAG graph.
    
    Keys:
    - query: str — original user query
    - user_id: str — authenticated user ID
    - document_ids: list[str] — document scope
    - chat_history: tuple[str, list[dict]] — (summary, recent messages)
    - model: str | None — LLM model override
    - provider: str | None — LLM provider override
    - rewritten_queries: list[str] — expanded queries
    - retrieved_chunks: list[RetrievedChunk] — retrieval results
    - context_sufficient: bool — enough relevant chunks?
    - answer_draft: str — generated answer
    - faithfulness_score: float — grounding score
    - iteration_count: int — retrieval retry counter
    - final_answer: str — final output
    - citations: list[dict] — source citations
    - confidence_score: float — overall confidence
    - retrieval_metadata: dict — stats
    """
    pass


def build_rag_graph() -> StateGraph:
    """
    Build the complete agentic RAG graph.

    Flow:
    rewrite_query → retrieve → grade_relevance
        ├─ sufficient → generate → check_faithfulness
        │                              ├─ faithful → format_citations → END
        │                              └─ hallucinating → refine_answer → format_citations → END
        ├─ insufficient → retrieve (retry with broader query)
        └─ give_up → END (after 2 retries)
    """
    workflow = StateGraph(dict)

    # Add nodes
    workflow.add_node("rewrite_query", query_rewriting_node)
    workflow.add_node("retrieve", retrieval_node)
    workflow.add_node("grade_relevance", relevance_grading_node)
    workflow.add_node("generate", generation_node)
    workflow.add_node("check_faithfulness", faithfulness_check_node)
    workflow.add_node("refine_answer", refinement_node)
    workflow.add_node("format_citations", citation_formatting_node)

    # Define the flow
    workflow.set_entry_point("rewrite_query")
    workflow.add_edge("rewrite_query", "retrieve")
    workflow.add_edge("retrieve", "grade_relevance")

    # Conditional: if context is insufficient, try broader retrieval once
    workflow.add_conditional_edges(
        "grade_relevance",
        decide_if_sufficient,
        {
            "sufficient": "generate",
            "insufficient": "retrieve",  # One retry with broader query
            "give_up": "generate",       # Generate "not found" answer
        },
    )

    workflow.add_edge("generate", "check_faithfulness")

    # Conditional: if answer is hallucinating, refine it
    workflow.add_conditional_edges(
        "check_faithfulness",
        decide_if_faithful,
        {
            "faithful": "format_citations",
            "hallucinating": "refine_answer",
        },
    )

    workflow.add_edge("refine_answer", "format_citations")
    workflow.add_edge("format_citations", END)

    compiled = workflow.compile()
    logger.info("RAG graph compiled successfully")
    return compiled


# ── Singleton compiled graph ───────────────────────────────────
_rag_graph = None


def get_rag_graph():
    """Get or create the compiled RAG graph (singleton)."""
    global _rag_graph
    if _rag_graph is None:
        _rag_graph = build_rag_graph()
    return _rag_graph


async def run_rag_pipeline(
    query: str,
    user_id: str,
    document_ids: list[str] | None = None,
    chat_history: tuple[str, list[dict]] | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> dict:
    """
    Run the full agentic RAG pipeline.
    Returns the final state with answer, citations, and metadata.
    """
    graph = get_rag_graph()

    initial_state = {
        "query": query,
        "user_id": user_id,
        "document_ids": document_ids or [],
        "chat_history": chat_history or ("", []),
        "model": model,
        "provider": provider,
        "rewritten_queries": [],
        "retrieved_chunks": [],
        "context_sufficient": False,
        "answer_draft": "",
        "faithfulness_score": 0.0,
        "iteration_count": 0,
        "final_answer": "",
        "citations": [],
        "confidence_score": 0.0,
        "retrieval_metadata": {},
    }

    logger.info(f"Running RAG pipeline for query: '{query[:80]}...'")

    final_state = await graph.ainvoke(initial_state)

    logger.info(
        f"RAG pipeline complete: confidence={final_state.get('confidence_score', 0):.2f}, "
        f"citations={len(final_state.get('citations', []))}"
    )

    return final_state
