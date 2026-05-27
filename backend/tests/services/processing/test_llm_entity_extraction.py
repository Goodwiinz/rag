"""Tests for LLM entity extraction service."""

import pytest

from src.services.processing.llm_entity_extraction import chunk_text


class TestChunkText:
    def test_small_doc_single_chunk(self):
        """Document under token limit returns single chunk."""
        text = "This is a short document about transformers."
        chunks = chunk_text(text, max_tokens=4000, overlap_tokens=200)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_splits_on_paragraph_boundaries(self):
        """Chunks split at double-newline paragraph breaks."""
        para1 = "First paragraph. " * 200  # ~400 tokens
        para2 = "Second paragraph. " * 200
        para3 = "Third paragraph. " * 200
        text = f"{para1}\n\n{para2}\n\n{para3}"
        chunks = chunk_text(text, max_tokens=500, overlap_tokens=50)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert not chunk.startswith(" ")

    def test_overlap_between_chunks(self):
        """Adjacent chunks share overlapping text."""
        # Use many small paragraphs so overlap can carry whole paragraphs
        paragraphs = [f"Paragraph {i} content. " * 20 for i in range(20)]
        text = "\n\n".join(paragraphs)
        chunks = chunk_text(text, max_tokens=300, overlap_tokens=100)
        assert len(chunks) >= 3
        for i in range(len(chunks) - 1):
            tail = chunks[i][-50:]
            assert tail in chunks[i + 1] or chunks[i + 1][:100] in chunks[i]

    def test_empty_text_returns_empty(self):
        chunks = chunk_text("", max_tokens=4000, overlap_tokens=200)
        assert chunks == []

    def test_whitespace_only_returns_empty(self):
        chunks = chunk_text("   \n\n  ", max_tokens=4000, overlap_tokens=200)
        assert chunks == []
