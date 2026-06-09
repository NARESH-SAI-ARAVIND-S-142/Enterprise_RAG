"""
DocuMind 2.0 — Ingestion Tests
Tests for document parsing, chunking, and embedding.
"""

import pytest

from app.documents.ingestion.chunker import Chunk, SmartChunker
from app.documents.ingestion.parser import ParsedDocument, ParsedElement


@pytest.fixture
def chunker():
    return SmartChunker()


@pytest.fixture
def sample_parsed_doc():
    """A parsed document with mixed element types."""
    doc = ParsedDocument(file_path="/test/doc.pdf", page_count=3)

    # Table element
    doc.elements.append(ParsedElement(
        element_type="Table",
        text="Name | Age | City\nAlice | 30 | NYC\nBob | 25 | LA",
        metadata={"page_number": 1, "is_table": True, "source_file": "doc.pdf"},
        is_table=True,
    ))

    # Long narrative text (>500 chars)
    long_text = "This is a detailed explanation of the system architecture. " * 20
    doc.elements.append(ParsedElement(
        element_type="NarrativeText",
        text=long_text,
        metadata={"page_number": 1, "is_table": False, "source_file": "doc.pdf"},
    ))

    # Short text
    doc.elements.append(ParsedElement(
        element_type="NarrativeText",
        text="Quick summary of the findings.",
        metadata={"page_number": 2, "is_table": False, "source_file": "doc.pdf"},
    ))

    # Code block
    code = """def calculate_metrics(data):
    results = {}
    for key, values in data.items():
        results[key] = sum(values) / len(values)
    return results

class MetricsEngine:
    def __init__(self):
        self.cache = {}
    def process(self, data):
        return calculate_metrics(data)"""
    doc.elements.append(ParsedElement(
        element_type="NarrativeText",
        text=code,
        metadata={"page_number": 3, "is_table": False, "source_file": "doc.pdf"},
    ))

    return doc


def test_tables_not_split_across_chunks(chunker, sample_parsed_doc):
    """Tables in PDFs must be kept as single atomic chunks."""
    chunks = chunker.chunk_document(sample_parsed_doc, "doc-123")

    table_chunks = [c for c in chunks if c.chunk_type == "table"]
    assert len(table_chunks) >= 1, "At least one table chunk should exist"

    for tc in table_chunks:
        assert "Name" in tc.text and "Alice" in tc.text, \
            "Table chunk must contain the complete table content"


def test_code_blocks_kept_atomic(chunker, sample_parsed_doc):
    """Code blocks should be kept as single chunks, never split."""
    chunks = chunker.chunk_document(sample_parsed_doc, "doc-123")

    code_chunks = [c for c in chunks if c.chunk_type == "code"]
    assert len(code_chunks) >= 1, "Code block should be detected"

    for cc in code_chunks:
        assert "def calculate_metrics" in cc.text, \
            "Code chunk must contain complete function"


def test_semantic_chunks_better_than_fixed(chunker, sample_parsed_doc):
    """Semantic chunker chunks should not end mid-sentence."""
    chunks = chunker.chunk_document(sample_parsed_doc, "doc-123")

    semantic_chunks = [c for c in chunks if c.chunk_type == "semantic"]
    for sc in semantic_chunks:
        # Check that chunks don't end abruptly mid-word
        text = sc.text.strip()
        if len(text) > 50:
            # Should end with punctuation or complete word
            assert not text[-1].isalpha() or text.endswith((".", "!", "?", ":", ";", ")", "]")), \
                f"Chunk appears to end mid-sentence: ...{text[-30:]}"


def test_all_chunks_have_metadata(chunker, sample_parsed_doc):
    """Every chunk must have required metadata fields."""
    chunks = chunker.chunk_document(sample_parsed_doc, "doc-123")

    for chunk in chunks:
        assert chunk.metadata.get("document_id") == "doc-123"
        assert "chunk_type" in chunk.metadata
        assert "chunk_index" in chunk.metadata
        assert chunk.text.strip(), "Chunk text must not be empty"


def test_short_text_kept_as_is(chunker, sample_parsed_doc):
    """Short text (<500 chars) should remain as a single 'small' chunk."""
    chunks = chunker.chunk_document(sample_parsed_doc, "doc-123")

    small_chunks = [c for c in chunks if c.chunk_type == "small"]
    assert len(small_chunks) >= 1
    # The "Quick summary" text should be a small chunk
    assert any("Quick summary" in c.text for c in small_chunks)


def test_chunk_indices_are_sequential(chunker, sample_parsed_doc):
    """Chunk indices should be sequential starting from 0."""
    chunks = chunker.chunk_document(sample_parsed_doc, "doc-123")

    indices = [c.metadata["chunk_index"] for c in chunks]
    assert indices == list(range(len(chunks))), \
        f"Chunk indices should be sequential: {indices}"
