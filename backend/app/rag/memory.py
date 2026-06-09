"""
DocuMind 2.0 — Conversation Memory with Compression
Token-budget-aware memory that compresses older exchanges.
"""

import json

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.documents.models import ChatMessage, ChatSession


class ConversationMemory:
    """
    Token-budget-aware conversation memory.
    - Keeps last 4 exchanges verbatim (recency window)
    - Compresses older exchanges into a running summary
    - Total token budget: 2000 tokens for history
    - Uses tiktoken to count tokens accurately
    """

    def __init__(self, max_tokens: int = 2000):
        self.max_tokens = max_tokens
        self._encoder = None

    @property
    def encoder(self):
        if self._encoder is None:
            import tiktoken
            self._encoder = tiktoken.get_encoding("cl100k_base")
        return self._encoder

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken."""
        return len(self.encoder.encode(text))

    async def get_context_for_query(
        self,
        session_id: str,
        new_query: str,
        db: AsyncSession,
    ) -> tuple[str, list[dict]]:
        """
        Returns (summary_context, recent_messages) to inject into RAG prompt.
        Automatically compresses history when token limit is approached.
        """
        messages = await self._get_session_messages(session_id, db)

        if not messages:
            return "", []

        # Always keep last 4 exchanges (8 messages: user+assistant pairs)
        recent = messages[-8:] if len(messages) > 8 else messages
        older = messages[:-8] if len(messages) > 8 else []

        # Format recent messages
        recent_formatted = [
            {"role": m["role"], "content": m["content"]}
            for m in recent
        ]

        # Compress older messages into a summary
        summary = ""
        if older:
            summary = await self._compress_history(older)

        # Check token budget
        total_text = summary + json.dumps(recent_formatted)
        total_tokens = self._count_tokens(total_text)

        if total_tokens > self.max_tokens:
            # Further compress — keep only last 2 exchanges
            recent = messages[-4:] if len(messages) > 4 else messages
            recent_formatted = [
                {"role": m["role"], "content": m["content"]}
                for m in recent
            ]
            older_for_compression = messages[:-4] if len(messages) > 4 else []
            if older_for_compression:
                summary = await self._compress_history(older_for_compression)
            else:
                summary = ""

        return summary, recent_formatted

    async def _compress_history(self, messages: list[dict]) -> str:
        """Compress older messages into a concise summary using LLM."""
        from app.rag.prompts import HISTORY_COMPRESSION_PROMPT

        formatted = "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in messages
        )

        try:
            from app.rag.nodes import get_llm
            llm = get_llm()
            result = await llm.ainvoke(
                HISTORY_COMPRESSION_PROMPT.format(messages=formatted)
            )
            summary = result.content if hasattr(result, "content") else str(result)
            logger.debug(f"Compressed {len(messages)} messages into summary ({len(summary)} chars)")
            return summary
        except Exception as e:
            logger.warning(f"History compression failed, using truncation: {e}")
            # Fallback: just concatenate and truncate
            return formatted[:500]

    async def _get_session_messages(
        self, session_id: str, db: AsyncSession
    ) -> list[dict]:
        """Fetch all messages for a session from the database."""
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
        )
        messages = result.scalars().all()
        return [
            {
                "role": msg.role,
                "content": msg.content,
                "created_at": str(msg.created_at),
            }
            for msg in messages
        ]


# Singleton
conversation_memory = ConversationMemory()
