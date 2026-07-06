from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from src.api.agent.jobs import _coerce_citation_document_id
from src.services.agent._nodes_rag import _shape_do_kb_context


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
