"""
DocuMind 2.0 — RAG Prompt Templates
All system prompts, grading prompts, and generation prompts.
"""

# ── System Prompt ──────────────────────────────────────────────
RAG_SYSTEM_PROMPT = """You are DocuMind, an expert document analysis assistant. 
You answer questions based ONLY on the provided document context.

Rules:
1. ONLY use information from the provided context to answer
2. If the context doesn't contain enough information, say so clearly
3. Cite your sources using [Source: filename, Page X] format
4. Be precise, thorough, and well-structured in your answers
5. If you find conflicting information, mention both perspectives
6. Never fabricate information not present in the context"""

# ── Generation Prompt ──────────────────────────────────────────
GENERATION_PROMPT = """Based on the following context from the user's documents, answer the question.

Conversation Summary:
{summary}

Recent Messages:
{recent_messages}

Document Context:
{context}

Question: {question}

Provide a comprehensive answer citing sources. If the context is insufficient, clearly state what information is missing."""

# ── Query Decomposition ───────────────────────────────────────
QUERY_DECOMPOSITION_PROMPT = """Given this question: "{query}"
If it contains multiple distinct questions, split into sub-questions.
If it is a single focused question, return it as-is.
Return a JSON array of strings. Example: ["sub-question 1", "sub-question 2"]
Return ONLY the JSON array, no other text."""

# ── HyDE (Hypothetical Document Embeddings) ───────────────────
HYDE_PROMPT = """Write a short paragraph (3-5 sentences) that would be the ideal answer to this question,
as if you were writing it in a technical document. This will be used for retrieval, not shown to the user.
Question: "{query}"
Paragraph:"""

# ── Step-Back Prompting ────────────────────────────────────────
STEPBACK_PROMPT = """What is the broader topic or concept that would need to be understood
to answer this question: "{query}"?
Return a single broader question that captures the underlying concept."""

# ── Relevance Grading ─────────────────────────────────────────
RELEVANCE_GRADING_PROMPT = """You are a relevance grader. Given the question and a document chunk,
determine if the chunk is relevant to answering the question.

Question: {question}
Chunk: {chunk}

Return JSON: {{"relevant": true/false, "reason": "brief explanation"}}
Return ONLY valid JSON."""

# ── Faithfulness Check ─────────────────────────────────────────
FAITHFULNESS_CHECK_PROMPT = """Given the answer and the source context, extract each factual claim 
from the answer and determine if it is supported by the context.

Answer: {answer}
Context: {context}

Return JSON: {{
  "claims": [{{"claim": "...", "supported": true/false}}],
  "faithfulness_score": 0.0-1.0
}}
Return ONLY valid JSON."""

# ── Answer Refinement ──────────────────────────────────────────
REFINEMENT_PROMPT = """The following answer was flagged for potential hallucination.
Please rewrite it using ONLY information from the provided context.
Remove any claims not directly supported by the context.

Original Answer: {answer}
Context: {context}

Rewrite the answer to be fully grounded in the context:"""

# ── History Compression ────────────────────────────────────────
HISTORY_COMPRESSION_PROMPT = """Compress the following conversation history into a concise summary
(max 200 words) that captures the key topics discussed, questions asked,
and important information established. Preserve any specific facts, numbers, or decisions.

Conversation:
{messages}

Summary:"""
