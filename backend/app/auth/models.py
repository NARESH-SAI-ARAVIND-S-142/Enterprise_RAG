"""
DocuMind 2.0 — User Database Model
SQLAlchemy async model for user accounts.
"""

from sqlalchemy import Boolean, Column, String
from sqlalchemy.orm import relationship

from app.database import Base, TimestampMixin, generate_uuid


class User(Base, TimestampMixin):
    """User account model with authentication fields."""

    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    documents = relationship("Document", back_populates="owner", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"
