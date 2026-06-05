"""
DocuMind 2.0 — Document Router
CRUD endpoints for document management + ingestion status.
"""

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.auth.models import User
from app.auth.utils import get_current_user
from app.database import get_db
from app.documents.models import Document
from app.documents.schemas import (
    DocumentListResponse,
    DocumentResponse,
    DocumentStatusResponse,
    DocumentUploadResponse,
)
from app.documents.service import (
    create_document_record,
    delete_document,
    get_document_by_id,
    get_user_documents,
    save_uploaded_file,
    validate_upload,
)
from app.vector_store.qdrant_client import qdrant_client

router = APIRouter()


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a document for ingestion. Returns immediately with job ID."""
    # 1. Validate file
    try:
        file_type = await validate_upload(file)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 2. Save file to disk
    try:
        file_path, file_size = await save_uploaded_file(file, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=413, detail=str(e))

    # 3. Create DB record
    doc = await create_document_record(
        db, current_user.id, file.filename, file_type, file_path, file_size,
    )
    await db.flush()

    # 4. Queue Celery task
    celery_task_id = None
    try:
        from app.documents.ingestion.tasks import ingest_document_task
        result = ingest_document_task.delay(doc.id, current_user.id, file_path)
        celery_task_id = result.id
        doc.celery_task_id = celery_task_id
    except Exception as e:
        logger.warning(f"Celery not available, ingestion queued in DB only: {e}")

    logger.info(f"Document uploaded: {doc.filename} (id={doc.id}, user={current_user.id})")

    return DocumentUploadResponse(
        document_id=doc.id,
        filename=doc.filename,
        status="queued",
        celery_task_id=celery_task_id,
        message="Document queued for ingestion",
    )


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List the current user's documents with pagination."""
    documents, total = await get_user_documents(db, current_user.id, status_filter, page, per_page)
    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(d) for d in documents],
        total=total, page=page, per_page=per_page,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific document's metadata."""
    doc = await get_document_by_id(db, document_id, current_user.id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse.model_validate(doc)


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_ingestion_status(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get ingestion status (frontend polls every 2s)."""
    doc = await get_document_by_id(db, document_id, current_user.id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentStatusResponse(
        document_id=doc.id, status=doc.status, progress=doc.progress,
        error_message=doc.error_message, chunk_count=doc.chunk_count,
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a document and its chunks from DB and Qdrant."""
    doc = await get_document_by_id(db, document_id, current_user.id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete from Qdrant
    try:
        await qdrant_client.delete_document_chunks(current_user.id, document_id)
    except Exception as e:
        logger.warning(f"Failed to delete from Qdrant: {e}")

    # Delete from DB and disk
    await delete_document(db, doc)
    logger.info(f"Deleted document {document_id}")
