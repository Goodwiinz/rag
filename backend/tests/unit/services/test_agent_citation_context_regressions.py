from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from src.services.agent.agent_execution_service import _coerce_citation_document_id
from src.services.agent._nodes_rag import _shape_do_kb_context
from src.services.do_kb.models import Chunk
from src.services.do_kb.postprocess import sanitize_and_deduplicate_chunks


def test_unresolved_do_kb_context_does_not_emit_storage_key_as_document_id() -> None:
    chunk = SimpleNamespace(
        document_id="org/uploads/not-a-document-uuid.pdf",
        metadata={"title": "Unresolved DO KB chunk"},
        text="retrieved content",
        score=0.91,
    )

    shaped = _shape_do_kb_context(chunk, title_by_key={})

    assert shaped["document_id"] is None
    assert shaped["title"] == "Unresolved DO KB chunk"
    assert shaped["content"] == "retrieved content"
    assert shaped["score"] == 0.91


def test_citation_document_id_coercion_ignores_non_uuid_values() -> None:
    assert _coerce_citation_document_id("org/uploads/not-a-document-uuid.pdf") is None


def test_citation_document_id_coercion_preserves_valid_uuid_values() -> None:
    document_id = uuid4()

    assert _coerce_citation_document_id(str(document_id)) == document_id
    assert _coerce_citation_document_id(document_id) == document_id


def test_shaped_do_kb_context_contains_sanitized_content_and_score_provenance() -> None:
    processed = sanitize_and_deduplicate_chunks(
        [
            Chunk(
                text="Contact synthetic.user@example.test",
                score=0.85,
                document_id="storage-key",
                metadata={"title": "Result", "score_source": "rank_proxy"},
            )
        ]
    )

    shaped = _shape_do_kb_context(processed.chunks[0], title_by_key={})

    assert shaped["content"] == "Contact <email>"
    assert shaped["score"] == 0.85
    assert shaped["score_source"] == "rank_proxy"
