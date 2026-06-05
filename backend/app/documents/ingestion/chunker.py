"""
DocuMind 2.0 — Smart Document Chunker
Multi-strategy chunking that preserves document structure.
"""

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from loguru import logger
from app.documents.ingestion.parser import ParsedDocument


@dataclass
class Chunk:
    """A single text chunk ready for embedding."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def chunk_type(self) -> str:
        return self.metadata.get("chunk_type", "unknown")

    @property
    def page_number(self) -> int | None:
        return self.metadata.get("page_number")


class SmartChunker:
    """
    Multi-strategy document chunker:
    - Tables → atomic (never split)
    - Code blocks → atomic (never split)
    - Long narrative (>500 chars) → SemanticChunker
    - Short text → keep as-is
    - Fallback → RecursiveCharacterTextSplitter (1000/200)
    """

    def __init__(self):
        self._semantic_splitter = None
        self._fallback_splitter = None

    def _get_semantic_splitter(self):
        if self._semantic_splitter is None:
            try:
                from langchain_experimental.text_splitter import SemanticChunker
                from langchain_huggingface import HuggingFaceEmbeddings
                embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
                self._semantic_splitter = SemanticChunker(
                    embeddings=embeddings,
                    breakpoint_threshold_type="percentile",
                    breakpoint_threshold_amount=95,
                )
            except ImportError:
                logger.warning("SemanticChunker not available")
        return self._semantic_splitter

    def _get_fallback_splitter(self):
        if self._fallback_splitter is None:
            from langchain.text_splitter import RecursiveCharacterTextSplitter
            self._fallback_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000, chunk_overlap=200,
                separators=["\n\n", "\n", ". ", " ", ""],
            )
        return self._fallback_splitter

    def chunk_document(self, parsed_doc: ParsedDocument, document_id: str) -> list[Chunk]:
        chunks: list[Chunk] = []
        chunk_index = 0

        for element in parsed_doc.elements:
            if not element.text or not element.text.strip():
                continue

            base_meta = {**element.metadata, "document_id": document_id}

            if element.is_table:
                chunks.append(Chunk(text=element.text, metadata={**base_meta, "chunk_type": "table", "chunk_index": chunk_index}))
                chunk_index += 1
            elif self._is_code_block(element.text):
                chunks.append(Chunk(text=element.text, metadata={**base_meta, "chunk_type": "code", "chunk_index": chunk_index}))
                chunk_index += 1
            elif len(element.text) > 500:
                sub_chunks = self._semantic_split(element.text)
                for i, sub_text in enumerate(sub_chunks):
                    chunks.append(Chunk(text=sub_text, metadata={**base_meta, "chunk_type": "semantic", "chunk_index": chunk_index, "sub_chunk_index": i}))
                    chunk_index += 1
            else:
                chunks.append(Chunk(text=element.text, metadata={**base_meta, "chunk_type": "small", "chunk_index": chunk_index}))
                chunk_index += 1

        logger.info(f"Chunked document into {len(chunks)} chunks")
        return chunks

    def _semantic_split(self, text: str) -> list[str]:
        semantic = self._get_semantic_splitter()
        if semantic:
            try:
                return semantic.split_text(text)
            except Exception as e:
                logger.warning(f"Semantic splitting failed: {e}")
        return self._get_fallback_splitter().split_text(text)

    @staticmethod
    def _is_code_block(text: str) -> bool:
        code_patterns = [
            r"^\s*(def |class |import |from |async def )",
            r"^\s*(function |const |let |var |export )",
            r"^\s*(public |private |static |void )",
        ]
        lines = text.strip().split("\n")
        if len(lines) < 2:
            return False
        code_lines = sum(1 for line in lines if any(re.search(p, line) for p in code_patterns))
        return code_lines / len(lines) > 0.4
