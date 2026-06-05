"""
DocuMind 2.0 — Document Pydantic Schemas
Request/response schemas for document endpoints.
"""

from datetime import datetime
from pydantic import BaseModel, Field


# ── Response Schemas ───────────────────────────────────────────
class DocumentResponse(BaseModel):
    """Full document metadata response."""
    id: str
    filename: str
    file_type: str
    file_size_bytes: int | None
    page_count: int | None
    status: str
    progress: int
    error_message: str | None
    chunk_count: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentUploadResponse(BaseModel):
    """Response after uploading a document."""
    document_id: str
    filename: str
    status: str
    celery_task_id: str | None
    message: str


class DocumentStatusResponse(BaseModel):
    """Ingestion status polling response."""
    document_id: str
    status: str
    progress: int
    error_message: str | None
    chunk_count: int | None


class DocumentListResponse(BaseModel):
    """Paginated list of documents."""
    documents: list[DocumentResponse]
    total: int
    page: int
    per_page: int


# ── Chunk Schemas ──────────────────────────────────────────────
class ChunkResponse(BaseModel):
    """Individual chunk metadata."""
    id: str
    text: str
    chunk_type: str
    page_number: int | None
    chunk_index: int
    source_file: str | None = None

    model_config = {"from_attributes": True}


# ── Chat Schemas ───────────────────────────────────────────────
class ChatQueryRequest(BaseModel):
    """Chat query request body."""
    query: str = Field(min_length=1, max_length=5000)
    document_ids: list[str] = Field(default_factory=list)
    model: str = Field(default="llama-3.1-8b-instant")
    provider: str = Field(default="groq")


class CitationSchema(BaseModel):
    """Citation reference in an answer."""
    chunk_id: str
    text: str
    page_number: int | None
    source_file: str
    relevance_score: float


class ChatMessageResponse(BaseModel):
    """Chat message response with citations and confidence."""
    message_id: str
    role: str
    content: str
    citations: list[CitationSchema] = Field(default_factory=list)
    confidence_score: float | None
    faithfulness_score: float | None
    model_used: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatSessionResponse(BaseModel):
    """Chat session with messages."""
    id: str
    title: str | None
    document_ids: list[str] = Field(default_factory=list)
    messages: list[ChatMessageResponse] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatSessionCreateRequest(BaseModel):
    """Create a new chat session."""
    title: str | None = "New Chat"
    document_ids: list[str] = Field(default_factory=list)


class MessageFeedbackRequest(BaseModel):
    """Submit feedback on a message."""
    feedback: str = Field(pattern="^(thumbs_up|thumbs_down)$")
