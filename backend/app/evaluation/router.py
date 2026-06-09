"""
DocuMind 2.0 — Evaluation Router
Endpoints for triggering and viewing RAGAS evaluations.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.auth.models import User
from app.auth.utils import get_current_user
from app.database import get_db
from app.documents.models import EvaluationResult
from app.evaluation.ragas_eval import rag_evaluator

router = APIRouter()


@router.post("/run")
async def run_evaluation(
    document_ids: list[str] = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a RAGAS evaluation run for specified documents."""
    # Create evaluation record
    eval_result = EvaluationResult(
        user_id=current_user.id,
        document_ids=json.dumps(document_ids),
        status="running",
    )
    db.add(eval_result)
    await db.flush()

    logger.info(f"Starting evaluation {eval_result.id} for docs: {document_ids}")

    try:
        scores = await rag_evaluator.run_evaluation(
            user_id=current_user.id,
            document_ids=document_ids,
            eval_result_id=eval_result.id,
            db=db,
        )
        return {
            "eval_id": eval_result.id,
            "status": "completed",
            "scores": scores,
        }
    except Exception as e:
        eval_result.status = "failed"
        eval_result.error_message = str(e)
        await db.flush()
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {e}")


@router.get("/results/{eval_id}")
async def get_eval_results(
    eval_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get results of a specific evaluation run."""
    result = await db.execute(
        select(EvaluationResult).where(
            EvaluationResult.id == eval_id,
            EvaluationResult.user_id == current_user.id,
        )
    )
    eval_record = result.scalar_one_or_none()
    if not eval_record:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    return {
        "id": eval_record.id,
        "status": eval_record.status,
        "scores": {
            "faithfulness": eval_record.faithfulness,
            "answer_relevancy": eval_record.answer_relevancy,
            "context_precision": eval_record.context_precision,
            "context_recall": eval_record.context_recall,
            "answer_correctness": eval_record.answer_correctness,
        },
        "per_question_results": json.loads(eval_record.per_question_results)
        if eval_record.per_question_results else [],
        "created_at": str(eval_record.created_at),
        "error": eval_record.error_message,
    }


@router.get("/history")
async def get_eval_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all past evaluation results with trend data."""
    result = await db.execute(
        select(EvaluationResult)
        .where(EvaluationResult.user_id == current_user.id)
        .order_by(EvaluationResult.created_at.desc())
    )
    records = result.scalars().all()

    return [
        {
            "id": r.id,
            "status": r.status,
            "faithfulness": r.faithfulness,
            "answer_relevancy": r.answer_relevancy,
            "context_precision": r.context_precision,
            "context_recall": r.context_recall,
            "answer_correctness": r.answer_correctness,
            "document_ids": json.loads(r.document_ids) if r.document_ids else [],
            "created_at": str(r.created_at),
        }
        for r in records
    ]
