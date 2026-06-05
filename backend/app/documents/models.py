"""
DocuMind 2.0 — Document & Chunk Database Models
SQLAlchemy models for document metadata and chunk storage.
"""

from sqlalchemy import Column, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base, TimestampMixin, generate_uuid


class Document(Base, TimestampMixin):
    """Document metadata model — tracks uploaded files and their ingestion status."""

    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=False)  # pdf, docx, txt
    file_path = Column(String(1000), nullable=False)
    file_size_bytes = Column(Integer, nullable=True)
    page_count = Column(Integer, nullable=True)

    # Ingestion status
    status = Column(
        String(50), nullable=False, default="queued"
    )  # queued, parsing, chunking, embedding, indexing, ready, failed
    progress = Column(Integer, nullable=False, default=0)  # 0-100
    error_message = Column(Text, nullable=True)
    celery_task_id = Column(String(255), nullable=True)

    # Chunk statistics
    chunk_count = Column(Integer, nullable=True, default=0)

    # Relationships
    owner = relationship("User", back_populates="documents")
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, filename={self.filename}, status={self.status})>"


class Chunk(Base, TimestampMixin):
    """Document chunk model — individual text chunks stored in vector DB."""

    __tablename__ = "chunks"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(
        String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text = Column(Text, nullable=False)
    chunk_type = Column(String(50), nullable=False)  # table, code, semantic, small
    chunk_index = Column(Integer, nullable=False)  # Order within document
    page_number = Column(Integer, nullable=True)
    element_id = Column(String(255), nullable=True)  # unstructured.io element ID
    table_html = Column(Text, nullable=True)  # HTML representation for tables
    sub_chunk_index = Column(Integer, nullable=True)  # Sub-index for semantic splits

    # Relationships
    document = relationship("Document", back_populates="chunks")

    def __repr__(self) -> str:
        return f"<Chunk(id={self.id}, type={self.chunk_type}, doc={self.document_id})>"


class ChatSession(Base, TimestampMixin):
    """Chat session model — groups messages by conversation."""

    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(500), nullable=True, default="New Chat")
    document_ids = Column(Text, nullable=True)  # JSON list of document IDs in scope

    # Relationships
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ChatSession(id={self.id}, title={self.title})>"


class ChatMessage(Base, TimestampMixin):
    """Individual chat message within a session."""

    __tablename__ = "chat_messages"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(
        String, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    citations = Column(Text, nullable=True)  # JSON list of citation objects
    confidence_score = Column(Float, nullable=True)
    faithfulness_score = Column(Float, nullable=True)
    model_used = Column(String(100), nullable=True)
    feedback = Column(String(10), nullable=True)  # thumbs_up, thumbs_down

    # Relationships
    session = relationship("ChatSession", back_populates="messages")

    def __repr__(self) -> str:
        return f"<ChatMessage(id={self.id}, role={self.role})>"


class TestQuestion(Base, TimestampMixin):
    """RAGAS synthetic test questions for evaluation."""

    __tablename__ = "test_questions"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(
        String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question = Column(Text, nullable=False)
    ground_truth = Column(Text, nullable=False)
    question_type = Column(String(50), nullable=False)  # simple, reasoning, multi_context
    contexts = Column(Text, nullable=True)  # JSON list of context chunks

    def __repr__(self) -> str:
        return f"<TestQuestion(id={self.id}, type={self.question_type})>"


class EvaluationResult(Base, TimestampMixin):
    """RAGAS evaluation run results."""

    __tablename__ = "evaluation_results"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    document_ids = Column(Text, nullable=False)  # JSON list
    faithfulness = Column(Float, nullable=True)
    answer_relevancy = Column(Float, nullable=True)
    context_precision = Column(Float, nullable=True)
    context_recall = Column(Float, nullable=True)
    answer_correctness = Column(Float, nullable=True)
    per_question_results = Column(Text, nullable=True)  # JSON
    status = Column(String(50), nullable=False, default="running")  # running, completed, failed
    error_message = Column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<EvaluationResult(id={self.id}, status={self.status})>"
