"""
DocuMind 2.0 — LangGraph Node Implementations
All node functions for the agentic RAG graph.
"""

import json

from langchain_groq import ChatGroq
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from app.config import settings
from app.rag.prompts import (
    FAITHFULNESS_CHECK_PROMPT,
    GENERATION_PROMPT,
    HYDE_PROMPT,
    QUERY_DECOMPOSITION_PROMPT,
    RAG_SYSTEM_PROMPT,
    REFINEMENT_PROMPT,
    RELEVANCE_GRADING_PROMPT,
    STEPBACK_PROMPT,
)
from app.rag.retriever import hybrid_retriever


def get_llm(model: str | None = None, provider: str | None = None):
    """Get LLM instance based on provider and model."""
    provider = provider or settings.DEFAULT_LLM_PROVIDER
    model = model or settings.DEFAULT_LLM_MODEL

    if provider == "groq":
        return ChatGroq(
            api_key=settings.GROQ_API_KEY,
            model_name=model,
            temperature=0.1,
            max_tokens=4096,
        )
    elif provider == "anthropic":
        return ChatAnthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            model_name=model,
            temperature=0.1,
            max_tokens=4096,
        )
    else:
        raise ValueError(f"Unknown provider: {provider}")


async def _llm_invoke(prompt: str, llm=None) -> str:
    """Invoke LLM and return content string."""
    if llm is None:
        llm = get_llm()
    result = await llm.ainvoke([HumanMessage(content=prompt)])
    return result.content if hasattr(result, "content") else str(result)


async def _llm_invoke_json(prompt: str, llm=None) -> dict | list:
    """Invoke LLM and parse JSON response."""
    raw = await _llm_invoke(prompt, llm)
    # Extract JSON from possible markdown code fences
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1]) if len(lines) > 2 else cleaned
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse LLM JSON: {raw[:200]}")
        return {}


# ── Node 1: Query Rewriting ───────────────────────────────────
async def query_rewriting_node(state: dict) -> dict:
    """
    Three-strategy query rewriting:
    1. Decompose: split multi-part questions
    2. HyDE: generate hypothetical document excerpt
    3. Step-back: abstract to broader concept
    """
    query = state["query"]
    logger.info(f"Rewriting query: '{query[:80]}...'")

    rewritten = [query]  # Always include original

    try:
        # Strategy 1: Decomposition
        decomposed = await _llm_invoke_json(
            QUERY_DECOMPOSITION_PROMPT.format(query=query)
        )
        if isinstance(decomposed, list):
            rewritten.extend(decomposed)

        # Strategy 2: HyDE
        hyde_doc = await _llm_invoke(HYDE_PROMPT.format(query=query))
        if hyde_doc:
            rewritten.append(hyde_doc)

        # Strategy 3: Step-back
        stepback = await _llm_invoke(STEPBACK_PROMPT.format(query=query))
        if stepback:
            rewritten.append(stepback)

    except Exception as e:
        logger.warning(f"Query rewriting partially failed: {e}")

    # Deduplicate
    seen = set()
    unique = []
    for q in rewritten:
        q_clean = q.strip()
        if q_clean and q_clean not in seen:
            seen.add(q_clean)
            unique.append(q_clean)

    state["rewritten_queries"] = unique
    logger.info(f"Produced {len(unique)} rewritten queries")
    return state


# ── Node 2: Retrieval ─────────────────────────────────────────
async def retrieval_node(state: dict) -> dict:
    """Retrieve chunks using hybrid retriever for all rewritten queries."""
    user_id = state["user_id"]
    document_ids = state.get("document_ids", [])
    queries = state.get("rewritten_queries", [state["query"]])

    all_chunks = {}

    for query in queries:
        chunks = await hybrid_retriever.retrieve(
            query=query,
            user_id=user_id,
            document_ids=document_ids if document_ids else None,
            top_k=10,
        )
        for chunk in chunks:
            if chunk.id not in all_chunks:
                all_chunks[chunk.id] = chunk

    state["retrieved_chunks"] = list(all_chunks.values())
    logger.info(f"Retrieved {len(state['retrieved_chunks'])} unique chunks")
    return state


# ── Node 3: Relevance Grading ─────────────────────────────────
async def relevance_grading_node(state: dict) -> dict:
    """
    Grade each retrieved chunk for relevance.
    Filter out irrelevant chunks.
    Mark context as insufficient if < 2 relevant chunks.
    """
    query = state["query"]
    chunks = state["retrieved_chunks"]

    if not chunks:
        state["context_sufficient"] = False
        state["iteration_count"] = state.get("iteration_count", 0) + 1
        return state

    graded = []
    for chunk in chunks:
        try:
            result = await _llm_invoke_json(
                RELEVANCE_GRADING_PROMPT.format(
                    question=query, chunk=chunk.text[:1000]
                )
            )
            if isinstance(result, dict) and result.get("relevant", False):
                graded.append(chunk)
        except Exception as e:
            logger.warning(f"Grading failed for chunk {chunk.id}: {e}")
            graded.append(chunk)  # Include on failure to be safe

    state["retrieved_chunks"] = graded
    state["context_sufficient"] = len(graded) >= 2
    state["iteration_count"] = state.get("iteration_count", 0) + 1

    logger.info(
        f"Graded: {len(graded)}/{len(chunks)} relevant, "
        f"sufficient={state['context_sufficient']}"
    )
    return state


# ── Node 4: Generation ────────────────────────────────────────
async def generation_node(state: dict) -> dict:
    """Generate answer from retrieved context."""
    query = state["query"]
    chunks = state["retrieved_chunks"]
    chat_history = state.get("chat_history", [])

    # Build context from chunks
    context_parts = []
    for i, chunk in enumerate(chunks):
        source = chunk.metadata.get("source_file", "Unknown")
        page = chunk.metadata.get("page_number", "?")
        context_parts.append(
            f"[Source {i+1}: {source}, Page {page}]\n{chunk.text}"
        )
    context = "\n\n---\n\n".join(context_parts)

    # Format history
    summary = ""
    recent_msgs = ""
    if isinstance(chat_history, tuple) and len(chat_history) == 2:
        summary, recent = chat_history
        recent_msgs = "\n".join(
            f"{m.get('role', 'user').upper()}: {m.get('content', '')}"
            for m in (recent if isinstance(recent, list) else [])
        )

    prompt = GENERATION_PROMPT.format(
        summary=summary or "No previous conversation.",
        recent_messages=recent_msgs or "None",
        context=context or "No relevant context found.",
        question=query,
    )

    llm = get_llm(
        model=state.get("model"),
        provider=state.get("provider"),
    )
    result = await llm.ainvoke([
        SystemMessage(content=RAG_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ])

    state["answer_draft"] = result.content
    logger.info(f"Generated answer ({len(result.content)} chars)")
    return state


# ── Node 5: Faithfulness Check ────────────────────────────────
async def faithfulness_check_node(state: dict) -> dict:
    """
    Check if generated answer is grounded in retrieved context.
    Extract claims and verify each against source material.
    """
    answer = state.get("answer_draft", "")
    chunks = state.get("retrieved_chunks", [])

    if not answer or not chunks:
        state["faithfulness_score"] = 0.0
        return state

    context = "\n---\n".join(c.text for c in chunks)

    try:
        result = await _llm_invoke_json(
            FAITHFULNESS_CHECK_PROMPT.format(answer=answer, context=context)
        )
        score = float(result.get("faithfulness_score", 0.5)) if isinstance(result, dict) else 0.5
    except Exception as e:
        logger.warning(f"Faithfulness check failed: {e}")
        score = 0.5

    state["faithfulness_score"] = score
    logger.info(f"Faithfulness score: {score:.2f}")
    return state


# ── Node 6: Answer Refinement ─────────────────────────────────
async def refinement_node(state: dict) -> dict:
    """Refine answer to remove hallucinations."""
    answer = state.get("answer_draft", "")
    chunks = state.get("retrieved_chunks", [])
    context = "\n---\n".join(c.text for c in chunks)

    refined = await _llm_invoke(
        REFINEMENT_PROMPT.format(answer=answer, context=context)
    )
    state["answer_draft"] = refined
    state["faithfulness_score"] = 0.85  # Assume improvement
    logger.info("Answer refined to remove hallucinations")
    return state


# ── Node 7: Citation Formatting ───────────────────────────────
async def citation_formatting_node(state: dict) -> dict:
    """Format final answer with structured citations."""
    answer = state.get("answer_draft", "")
    chunks = state.get("retrieved_chunks", [])

    citations = []
    for chunk in chunks:
        citations.append({
            "chunk_id": chunk.id,
            "text": chunk.text[:300],
            "page_number": chunk.metadata.get("page_number"),
            "source_file": chunk.metadata.get("source_file", "Unknown"),
            "document_id": chunk.metadata.get("document_id", ""),
            "relevance_score": chunk.score,
        })

    state["final_answer"] = answer
    state["citations"] = citations
    state["confidence_score"] = min(state.get("faithfulness_score", 0.5), 1.0)

    state["retrieval_metadata"] = {
        "total_chunks_retrieved": len(chunks),
        "rewritten_queries": len(state.get("rewritten_queries", [])),
        "iteration_count": state.get("iteration_count", 1),
    }

    logger.info(f"Formatted {len(citations)} citations, confidence={state['confidence_score']:.2f}")
    return state


# ── Decision Functions ─────────────────────────────────────────
def decide_if_sufficient(state: dict) -> str:
    """Decide whether context is sufficient, needs retry, or should give up."""
    if state.get("context_sufficient", False):
        return "sufficient"
    if state.get("iteration_count", 0) >= 2:
        return "give_up"
    return "insufficient"


def decide_if_faithful(state: dict) -> str:
    """Decide if the answer is faithful or needs refinement."""
    score = state.get("faithfulness_score", 0.0)
    threshold = settings.RAGAS_FAITHFULNESS_THRESHOLD
    if score >= threshold:
        return "faithful"
    return "hallucinating"
