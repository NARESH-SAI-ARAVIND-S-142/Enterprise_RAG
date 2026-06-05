"""
DocuMind 2.0 — Document Service
Business logic for document CRUD operations.
"""

import os
import uuid
from pathlib import Path

from fastapi import UploadFile
from loguru import logger
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.documents.models import Document


ALLOWED_FILE_TYPES = {"pdf", "docx", "doc", "txt"}
MAX_SIZE_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


async def validate_upload(file: UploadFile) -> tuple[str, str]:
    """Validate file type and size. Returns (file_type, error_message)."""
    if not file.filename:
        raise ValueError("No filename provided")

    _, ext = os.path.splitext(file.filename)
    file_type = ext.lower().lstrip(".")

    if file_type not in ALLOWED_FILE_TYPES:
        raise ValueError(f"Unsupported file type: {file_type}. Allowed: {ALLOWED_FILE_TYPES}")

    return file_type


async def save_uploaded_file(file: UploadFile, user_id: str) -> tuple[str, int]:
    """Save uploaded file to disk. Returns (file_path, file_size)."""
    user_dir = os.path.join(settings.UPLOAD_DIR, user_id)
    os.makedirs(user_dir, exist_ok=True)

    unique_name = f"{uuid.uuid4()}_{file.filename}"
    file_path = os.path.join(user_dir, unique_name)

    content = await file.read()
    file_size = len(content)

    if file_size > MAX_SIZE_BYTES:
        raise ValueError(f"File too large: {file_size} bytes (max {MAX_SIZE_BYTES})")

    with open(file_path, "wb") as f:
        f.write(content)

    logger.info(f"Saved file: {file_path} ({file_size} bytes)")
    return file_path, file_size


async def create_document_record(
    db: AsyncSession, user_id: str, filename: str, file_type: str,
    file_path: str, file_size: int,
) -> Document:
    """Create a Document record in the database."""
    doc = Document(
        user_id=user_id, filename=filename, file_type=file_type,
        file_path=file_path, file_size_bytes=file_size, status="queued", progress=0,
    )
    db.add(doc)
    await db.flush()
    return doc


async def get_user_documents(
    db: AsyncSession, user_id: str, status: str | None = None,
    page: int = 1, per_page: int = 20,
) -> tuple[list[Document], int]:
    """Get paginated list of user's documents."""
    query = select(Document).where(Document.user_id == user_id)
    count_query = select(func.count()).select_from(Document).where(Document.user_id == user_id)

    if status:
        query = query.where(Document.status == status)
        count_query = count_query.where(Document.status == status)

    query = query.order_by(Document.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    documents = result.scalars().all()

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    return list(documents), total


async def get_document_by_id(db: AsyncSession, document_id: str, user_id: str) -> Document | None:
    """Get a specific document, ensuring it belongs to the user."""
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def delete_document(db: AsyncSession, document: Document) -> None:
    """Delete document record and file from disk."""
    if os.path.exists(document.file_path):
        os.remove(document.file_path)
        logger.info(f"Deleted file: {document.file_path}")
    await db.delete(document)
