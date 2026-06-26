"""
DocuMind 2.0 — FastAPI Application Entry Point
Production-grade RAG platform with multi-tenant isolation.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import settings
from app.database import create_all_tables


# ── Lifespan ───────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup
    logger.info("🚀 DocuMind 2.0 starting up...")

    # Create upload directory
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    logger.info(f"Upload directory: {settings.UPLOAD_DIR}")

    # Initialize database tables
    await create_all_tables()
    logger.info("Database tables initialized")

    # Configure LangSmith tracing
    if settings.LANGCHAIN_TRACING_V2 and settings.LANGCHAIN_API_KEY:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
        os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
        logger.info(f"LangSmith tracing enabled for project: {settings.LANGCHAIN_PROJECT}")

    logger.info("✅ DocuMind 2.0 ready to serve requests")
    yield

    # Shutdown
    logger.info("🔄 DocuMind 2.0 shutting down...")


# ── App Instance ───────────────────────────────────────────────
app = FastAPI(
    title="DocuMind 2.0",
    description="Production-grade multi-user agentic RAG platform",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS Middleware ────────────────────────────────────────────
# On HF Spaces, frontend and backend share the same origin via nginx
_origins = ["*"] if settings.DEPLOY_MODE == "hf_spaces" else [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:7860",
    "http://127.0.0.1:7860",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Register Routers ──────────────────────────────────────────
from app.auth.router import router as auth_router  # noqa: E402
from app.documents.router import router as documents_router  # noqa: E402
from app.rag.router import router as rag_router  # noqa: E402
from app.evaluation.router import router as eval_router  # noqa: E402

app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(documents_router, prefix="/documents", tags=["Documents"])
app.include_router(rag_router, prefix="/chat", tags=["Chat & RAG"])
app.include_router(eval_router, prefix="/eval", tags=["Evaluation"])


# ── Health Check ───────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint for Docker and load balancers."""
    return {
        "status": "healthy",
        "service": "DocuMind 2.0",
        "version": "2.0.0",
    }


@app.get("/", tags=["System"])
async def root():
    """Root endpoint with API information."""
    return {
        "service": "DocuMind 2.0 API",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health",
    }
