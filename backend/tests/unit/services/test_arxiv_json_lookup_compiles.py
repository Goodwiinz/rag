"""Regression tests: arXiv-id JSON lookups must build against the real model.

Production bug (2026-07-16, post-#1181 review): three call sites filtered on
``Document.document_metadata["arxiv_id"].astext``. ``document_metadata`` is the
*generic* ``sqlalchemy.JSON`` type, whose comparator has no ``astext`` (that is
the postgres-dialect ``JSONB`` type) — every statement raised AttributeError at
build time. The tracker counted it as a per-change "error", /force-sync 500'd,
and the agent's arXiv-id document resolution silently fell through.

These tests compile the statements against the postgres dialect — no database
required — so a comparator regression fails unit CI instead of exploding (or
being swallowed) at runtime.
"""

import uuid

import pytest
from sqlalchemy.dialects import postgresql

from src.services.arxiv.arxiv_change_tracker import ArXivChangeTracker


@pytest.mark.unit
def test_paper_lookup_stmt_compiles_on_postgres_dialect():
    """The tracker's tenant-scoped arXiv-id lookup must build + compile."""
    stmt = ArXivChangeTracker._paper_lookup_stmt("1706.03762", str(uuid.uuid4()))

    compiled = str(stmt.compile(dialect=postgresql.dialect()))

    # ->> extraction of the arxiv_id key must survive into the SQL.
    assert "->>" in compiled
    assert "organization_id" in compiled


@pytest.mark.unit
def test_document_metadata_arxiv_id_as_string_filter_compiles():
    """The raw comparator pattern used by extraction + agent lookups compiles."""
    from sqlalchemy import select

    from src.models.document import Document

    stmt = select(Document.id).where(
        Document.document_metadata["arxiv_id"].as_string() == "1706.03762"
    )

    compiled = str(stmt.compile(dialect=postgresql.dialect()))

    assert "->>" in compiled
