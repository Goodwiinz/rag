"""run_background_extraction must scope document fetches to the matrix's project.

The background extraction worker fetched each document with
`select(Document).where(Document.id == doc_id)` — no project/org scope. Callers
currently pass project-scoped ids, but scoping the fetch itself (join
collection_documents on the matrix's project_id) is defense-in-depth: a
document id outside the matrix's project can never be read into a cell. This
pins the scoping on the extracted helper's compiled query.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

pytestmark = pytest.mark.unit

from src.services.research.extraction_matrix_service import _scoped_document_query


def _sql(q):
    return str(q.compile(compile_kwargs={"literal_binds": False})).lower()


def test_query_joins_project_collection():
    sql = _sql(_scoped_document_query(uuid4(), uuid4()))
    assert "join collection_documents" in sql
    assert "collection_id" in sql
    assert "documents.id" in sql


def test_query_not_bare_id_select():
    sql = _sql(_scoped_document_query(uuid4(), uuid4()))
    assert "collection_documents" in sql
