"""trigger_extraction must scope client document_ids to the matrix's project.

POST /matrices/{matrix_id}/extract validated matrix-project ownership but then
fetched each client-supplied document_id with `select(Document).where(id==...)`
— no org/project filter. A caller (owning matrix M in their own project) could
pass another tenant's document UUIDs and have that document's content_text read
into extraction cells (cross-tenant document-content leak). The fetch now joins
collection_documents on collection_id == matrix.project_id, dropping any id not
in the (owned) project. This test pins the scoping on the built query.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

pytestmark = pytest.mark.unit

from src.api.research.extraction_matrix import _scoped_document_query


def _sql(q):
    return str(q.compile(compile_kwargs={"literal_binds": False})).lower()


def test_query_joins_project_collection():
    sql = _sql(_scoped_document_query(uuid4(), uuid4()))
    assert "join collection_documents" in sql
    assert "collection_id" in sql
    assert "documents.id" in sql  # still keyed by the requested doc id


def test_query_never_bare_id_select():
    # regression: old code was select(Document).where(Document.id == doc_id)
    # with NO collection join.
    sql = _sql(_scoped_document_query(uuid4(), uuid4()))
    assert "collection_documents" in sql
