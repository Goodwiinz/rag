"""Tests for the model-boundary DO KB chunk sanitizer and deduplicator."""

from __future__ import annotations

from copy import deepcopy

import pytest

from src.services.do_kb.models import Chunk
from src.services.do_kb.postprocess import sanitize_and_deduplicate_chunks


def _chunk(
    text: str,
    *,
    document_id: str = "document-a",
    metadata: dict | None = None,
    score: float = 0.9,
) -> Chunk:
    return Chunk(
        text=text,
        score=score,
        document_id=document_id,
        metadata=metadata or {},
    )


@pytest.mark.unit
class TestSanitizeAndDeduplicateChunks:
    def test_redacts_text_email_and_phone(self) -> None:
        result = sanitize_and_deduplicate_chunks(
            [_chunk("Email synthetic.user@example.test or call 415-555-0123")]
        )

        assert result.chunks[0].text == "Email <email> or call <phone>"
        assert result.redacted_count == 1

    def test_recursively_redacts_nested_metadata_without_document_id_change(
        self,
    ) -> None:
        result = sanitize_and_deduplicate_chunks(
            [
                _chunk(
                    "Clean retrieval text",
                    document_id="original-document-id",
                    metadata={
                        "owner": "synthetic.user@example.test",
                        "nested": [{"phone": "+1 415 555 0123"}],
                    },
                )
            ]
        )

        chunk = result.chunks[0]
        assert chunk.document_id == "original-document-id"
        assert chunk.metadata == {
            "owner": "<email>",
            "nested": [{"phone": "<phone>"}],
        }
        assert result.redacted_count == 1

    def test_exact_duplicates_from_different_documents_collapse(self) -> None:
        result = sanitize_and_deduplicate_chunks(
            [
                _chunk("Shared result", document_id="highest-ranked"),
                _chunk("Shared result", document_id="lower-ranked"),
            ]
        )

        assert [chunk.document_id for chunk in result.chunks] == ["highest-ranked"]
        assert result.duplicate_count == 1

    def test_contact_only_differences_collapse_after_redaction(self) -> None:
        result = sanitize_and_deduplicate_chunks(
            [
                _chunk("Contact synthetic.first@example.test for the report"),
                _chunk("Contact synthetic.second@example.test for the report"),
            ]
        )

        assert [chunk.text for chunk in result.chunks] == [
            "Contact <email> for the report"
        ]
        assert result.duplicate_count == 1
        assert result.redacted_count == 2

    def test_distinct_text_from_one_document_remains_distinct(self) -> None:
        result = sanitize_and_deduplicate_chunks(
            [
                _chunk("First passage", document_id="same-document"),
                _chunk("Second passage", document_id="same-document"),
            ]
        )

        assert [chunk.text for chunk in result.chunks] == [
            "First passage",
            "Second passage",
        ]
        assert result.duplicate_count == 0

    def test_first_duplicate_is_retained_even_when_later_score_is_higher(
        self,
    ) -> None:
        result = sanitize_and_deduplicate_chunks(
            [
                _chunk("Same passage", document_id="first", score=0.1),
                _chunk("Same passage", document_id="second", score=0.99),
            ]
        )

        assert result.chunks[0].document_id == "first"
        assert result.chunks[0].score == 0.1

    def test_whitespace_and_case_variants_collapse(self) -> None:
        result = sanitize_and_deduplicate_chunks(
            [
                _chunk("  Research\n  Result  "),
                _chunk("research result"),
            ]
        )

        assert len(result.chunks) == 1
        assert result.duplicate_count == 1

    def test_empty_after_sanitization_is_dropped(self) -> None:
        result = sanitize_and_deduplicate_chunks([_chunk(" \n\t ")])

        assert result.chunks == []
        assert result.input_count == 1
        assert result.output_count == 0
        assert result.duplicate_count == 0

    def test_input_chunks_and_metadata_are_unchanged(self) -> None:
        original = _chunk(
            "Contact synthetic.user@example.test",
            metadata={"nested": [{"phone": "415-555-0123"}]},
        )
        original_metadata = deepcopy(original.metadata)
        original_text = original.text

        result = sanitize_and_deduplicate_chunks([original])

        assert original.text == original_text
        assert original.metadata == original_metadata
        assert result.chunks[0] is not original
        assert result.chunks[0].metadata is not original.metadata

    def test_counts_are_integers_without_content(self) -> None:
        result = sanitize_and_deduplicate_chunks(
            [
                _chunk("Contact synthetic.user@example.test"),
                _chunk("Contact synthetic.second@example.test"),
                _chunk(" \n "),
            ]
        )

        counts = (
            result.input_count,
            result.output_count,
            result.duplicate_count,
            result.redacted_count,
        )
        assert all(type(count) is int for count in counts)
        assert counts == (3, 1, 1, 2)
