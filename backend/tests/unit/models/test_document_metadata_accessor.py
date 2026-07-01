"""Regression: the file-metadata endpoint must read the JSON column, not the
reserved SQLAlchemy `MetaData` registry.

`GET /api/v1/files/{id}/metadata` returned `document.metadata`, which on a
declarative model resolves to SQLAlchemy's class-level `MetaData` object (the
whole schema graph), not the document's JSON metadata. FastAPI's jsonable_encoder
cannot serialize that, so the endpoint 500'd on every call. The JSON lives in the
`document_metadata` column, exposed via `get_metadata()`.
"""

from __future__ import annotations

import pytest
from sqlalchemy import MetaData

from src.models.document import Document

pytestmark = pytest.mark.unit


def test_get_metadata_returns_json_column():
    doc = Document()
    doc.document_metadata = {"author": "x", "pages": 3}
    assert doc.get_metadata() == {"author": "x", "pages": 3}


def test_get_metadata_defaults_to_empty_dict_when_null():
    doc = Document()
    doc.document_metadata = None
    assert doc.get_metadata() == {}


def test_reserved_metadata_attribute_is_not_document_json():
    # `Document.metadata` is SQLAlchemy's reserved declarative registry, NOT the
    # document's JSON metadata — the trap that made the endpoint 500. This guards
    # against anyone re-wiring the endpoint back to `document.metadata`.
    assert isinstance(Document.metadata, MetaData)
