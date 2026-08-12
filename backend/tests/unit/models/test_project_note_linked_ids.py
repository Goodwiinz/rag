"""ProjectNote.linked_document_ids must stay JSON-serializable (str, not UUID)."""

import json
from uuid import uuid4

from src.models.project_note import ProjectNote


def test_linked_document_ids_coerced_to_str_on_assignment() -> None:
    doc_id = uuid4()
    note = ProjectNote(title="t", content="c", linked_document_ids=[doc_id])

    assert note.linked_document_ids == [str(doc_id)]
    json.dumps(note.linked_document_ids)  # JSONB write path


def test_linked_document_ids_none_becomes_empty_list() -> None:
    note = ProjectNote(title="t", content="c")
    # The update route assigns whatever the request schema yielded, including None;
    # mypy sees the declarative Column descriptor rather than the validated value.
    note.linked_document_ids = None  # type: ignore[assignment]

    assert note.linked_document_ids == []
