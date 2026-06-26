"""
DocuMind 2.0 — Celery Background Ingestion Tasks
Async document processing pipeline with progress tracking.
Supports both Celery (docker-compose) and synchronous (HF Spaces) modes.
"""

import os
import asyncio
from loguru import logger

from app.config import settings


# ── Celery App (only if Redis is available) ────────────────────
celery_app = None
_celery_available = False

try:
    if settings.DEPLOY_MODE != "hf_spaces":
        from celery import Celery
        celery_app = Celery(
            "documind",
            broker=settings.REDIS_URL,
            backend=settings.REDIS_URL,
        )
        celery_app.conf.update(
            task_serializer="json",
            accept_content=["json"],
            result_serializer="json",
            timezone="UTC",
            enable_utc=True,
            task_track_started=True,
            task_acks_late=True,
            worker_prefetch_multiplier=1,
        )
        _celery_available = True
        logger.info("Celery configured with Redis backend")
except Exception as e:
    logger.info(f"Celery not available, using synchronous ingestion: {e}")


def _update_document_status(document_id: str, status: str, progress: int, error: str | None = None):
    """Update document status in DB (synchronous for Celery workers)."""
    from sqlalchemy import create_engine, update
    from sqlalchemy.orm import Session
    from app.documents.models import Document

    sync_url = settings.DATABASE_URL.replace("+aiosqlite", "")
    engine = create_engine(sync_url)
    with Session(engine) as session:
        stmt = update(Document).where(Document.id == document_id).values(
            status=status, progress=progress, error_message=error,
        )
        session.execute(stmt)
        session.commit()
    engine.dispose()


def _update_document_chunks(document_id: str, chunk_count: int, page_count: int):
    """Update document chunk count and page count."""
    from sqlalchemy import create_engine, update
    from sqlalchemy.orm import Session
    from app.documents.models import Document

    sync_url = settings.DATABASE_URL.replace("+aiosqlite", "")
    engine = create_engine(sync_url)
    with Session(engine) as session:
        stmt = update(Document).where(Document.id == document_id).values(
            chunk_count=chunk_count, page_count=page_count,
        )
        session.execute(stmt)
        session.commit()
    engine.dispose()


def _run_ingestion(document_id: str, user_id: str, file_path: str):
    """
    Core ingestion pipeline (shared between Celery and sync modes).
    Steps: Parse → Chunk → Embed → Index → Ready
    """
    try:
        logger.info(f"Starting ingestion for document {document_id}")

        # Step 1: Parse (10-25%)
        _update_document_status(document_id, "parsing", 10)
        from app.documents.ingestion.parser import parse_document

        _, ext = os.path.splitext(file_path)
        file_type = ext.lower().lstrip(".")

        loop = None
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        parsed = loop.run_until_complete(parse_document(file_path, file_type))
        _update_document_status(document_id, "parsing", 25)
        logger.info(f"Parsed {len(parsed.elements)} elements")

        # Step 2: Chunk (30-45%)
        _update_document_status(document_id, "chunking", 30)
        from app.documents.ingestion.chunker import SmartChunker
        chunker = SmartChunker()
        chunks = chunker.chunk_document(parsed, document_id)
        _update_document_status(document_id, "chunking", 45)
        logger.info(f"Created {len(chunks)} chunks")

        # Step 3: Embed (50-70%)
        _update_document_status(document_id, "embedding", 50)
        from app.documents.ingestion.embedder import embedding_pipeline
        embedded_chunks = embedding_pipeline.embed_chunks(chunks)
        _update_document_status(document_id, "embedding", 70)
        logger.info(f"Embedded {len(embedded_chunks)} chunks")

        # Step 4: Index in Qdrant (80-90%)
        _update_document_status(document_id, "indexing", 80)
        from app.vector_store.qdrant_client import TenantQdrantClient
        qdrant = TenantQdrantClient()
        loop.run_until_complete(qdrant.upsert_chunks(user_id, embedded_chunks))
        _update_document_status(document_id, "indexing", 90)

        # Step 5: Update metadata and mark ready (100%)
        _update_document_chunks(document_id, len(chunks), parsed.page_count)
        _update_document_status(document_id, "ready", 100)
        logger.info(f"Document {document_id} ingestion complete!")

        return {"document_id": document_id, "status": "ready", "chunks": len(chunks)}

    except Exception as exc:
        logger.error(f"Ingestion failed for {document_id}: {exc}")
        _update_document_status(document_id, "failed", 0, error=str(exc))
        raise


# ── Celery Task (only registered if Celery is available) ───────
if _celery_available and celery_app is not None:
    @celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
    def ingest_document_task(self, document_id: str, user_id: str, file_path: str):
        """Full ingestion pipeline as a background Celery task."""
        try:
            return _run_ingestion(document_id, user_id, file_path)
        except Exception as exc:
            raise self.retry(exc=exc)
else:
    # Synchronous fallback for HF Spaces (no Celery)
    class _SyncResult:
        def __init__(self, doc_id):
            self.id = doc_id

    class _SyncTask:
        """Mimics Celery task interface but runs synchronously in a thread."""
        def delay(self, document_id: str, user_id: str, file_path: str):
            import threading
            thread = threading.Thread(
                target=_run_ingestion,
                args=(document_id, user_id, file_path),
                daemon=True,
            )
            thread.start()
            return _SyncResult(document_id)

    ingest_document_task = _SyncTask()
