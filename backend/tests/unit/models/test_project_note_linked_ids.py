"""ProjectNote.linked_document_ids must stay JSON-serializable (str, not UUID)."""

import json
from uuid import uuid4

from src.models.project_note import ProjectNote


def test_linked_document_ids_coerced_to_str_on_assignment():
    doc_id = uuid4()
    note = ProjectNote(title="t", content="c", linked_document_ids=[doc_id])

    assert note.linked_document_ids == [str(doc_id)]
    json.dumps(note.linked_document_ids)  # JSONB write path


def test_linked_document_ids_none_becomes_empty_list():
    note = ProjectNote(title="t", content="c")
    note.linked_document_ids = None

    assert note.linked_document_ids == []
