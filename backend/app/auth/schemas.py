"""
DocuMind 2.0 — Auth Pydantic Schemas
Request/response schemas for authentication endpoints.
"""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# ── Request Schemas ────────────────────────────────────────────
class UserCreate(BaseModel):
    """Schema for user registration."""
    email: EmailStr
    password: str = Field(min_length=8, max_length=128, description="Password (8-128 chars)")
    full_name: str | None = Field(default=None, max_length=255)


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str


class TokenRefresh(BaseModel):
    """Schema for token refresh."""
    refresh_token: str


# ── Response Schemas ───────────────────────────────────────────
class UserResponse(BaseModel):
    """Schema for user data in responses."""
    id: str
    email: str
    full_name: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """Schema for token pair response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
    detail: str | None = None
