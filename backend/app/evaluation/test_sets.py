"""
DocuMind 2.0 — Synthetic Test Set Generation
Generates QA pairs for RAGAS evaluation from uploaded documents.
"""

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.evaluation.ragas_eval import rag_evaluator


async def generate_test_questions_for_document(
    document_id: str,
    chunks: list,
    db: AsyncSession,
    n_questions: int = 10,
) -> list[dict]:
    """
    Generate synthetic test questions from document chunks.
    Called automatically after document ingestion completes.
    """
    logger.info(f"Generating test questions for document {document_id}")
    return await rag_evaluator.generate_test_set(
        document_id=document_id,
        chunks=chunks,
        db=db,
        n_questions=n_questions,
    )
