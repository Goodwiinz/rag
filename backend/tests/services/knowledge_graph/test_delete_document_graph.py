"""Cypher-level tests for KnowledgeGraphService.delete_document_graph (audit D2).

The new method DETACH-DELETEs a document's entity subgraph, anchored on the
`source_document_id` property (globally unique to one doc in one org) and — when
an org is supplied — narrowed by the `organization_id` property (property-based
graph tenancy). It must AND the two, never OR them: OR'ing would widen the delete
to the whole org's graph.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

GET_SESSION = (
    "src.services.knowledge_graph.knowledge_graph_service."
    "KnowledgeGraphService.get_session"
)


def _session_returning(deleted_count):
    """A patched `get_session()` context manager whose `run()` reports a count."""
    result = MagicMock()
    result.single.return_value = {"deleted_count": deleted_count}
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=ctx)
    ctx.__exit__ = MagicMock(return_value=False)
    ctx.run.return_value = result
    return ctx


@pytest.mark.unit
@patch(GET_SESSION)
def test_delete_document_graph_scoped_by_doc_and_org(mock_session):
    from src.services.knowledge_graph.knowledge_graph_service import (
        KnowledgeGraphService,
    )

    ctx = _session_returning(3)
    mock_session.return_value = ctx

    doc_id = str(uuid.uuid4())
    org_id = str(uuid.uuid4())
    deleted = KnowledgeGraphService().delete_document_graph(doc_id, org_id)

    assert deleted == 3
    query, params = ctx.run.call_args[0][0], ctx.run.call_args[0][1]
    # Anchored on source_document_id, DETACH DELETE, org predicate present.
    assert "source_document_id: $source_document_id" in query
    assert "DETACH DELETE e" in query
    assert "e.organization_id = $organization_id" in query
    # Legacy pre-backfill nodes (org NULL) for this doc are still reaped.
    assert "e.organization_id IS NULL" in query
    assert params["source_document_id"] == doc_id
    assert params["organization_id"] == org_id


@pytest.mark.unit
@patch(GET_SESSION)
def test_delete_document_graph_stringifies_ids(mock_session):
    """Non-string ids (e.g. UUID objects) are coerced to match stored string
    properties."""
    from src.services.knowledge_graph.knowledge_graph_service import (
        KnowledgeGraphService,
    )

    ctx = _session_returning(1)
    mock_session.return_value = ctx

    doc_id = uuid.uuid4()
    org_id = uuid.uuid4()
    KnowledgeGraphService().delete_document_graph(doc_id, org_id)

    params = ctx.run.call_args[0][1]
    assert params["source_document_id"] == str(doc_id)
    assert params["organization_id"] == str(org_id)


@pytest.mark.unit
@patch(GET_SESSION)
def test_delete_document_graph_omits_org_predicate_when_org_none(mock_session):
    from src.services.knowledge_graph.knowledge_graph_service import (
        KnowledgeGraphService,
    )

    ctx = _session_returning(0)
    mock_session.return_value = ctx

    doc_id = str(uuid.uuid4())
    deleted = KnowledgeGraphService().delete_document_graph(doc_id, None)

    assert deleted == 0
    query, params = ctx.run.call_args[0][0], ctx.run.call_args[0][1]
    assert "organization_id" not in query  # no org predicate emitted
    assert "organization_id" not in params  # and no org param bound
    assert params["source_document_id"] == doc_id


@pytest.mark.unit
@patch(GET_SESSION)
def test_delete_document_graph_does_not_widen_to_whole_org(mock_session):
    """Regression: the delete must AND doc-anchor with org, never OR them (an OR
    would DETACH DELETE the entire org's graph). The doc anchor stays a MATCH
    pattern property; org lives only in the WHERE."""
    from src.services.knowledge_graph.knowledge_graph_service import (
        KnowledgeGraphService,
    )

    ctx = _session_returning(1)
    mock_session.return_value = ctx
    KnowledgeGraphService().delete_document_graph("doc-1", "org-1")

    query = ctx.run.call_args[0][0]
    assert "MATCH (e:Entity {source_document_id: $source_document_id})" in query
    # Must NOT reuse the read-scope helper's OR'd source_document_id IN-list.
    assert "IN $source_document_ids" not in query


@pytest.mark.unit
@patch(GET_SESSION)
def test_delete_document_graph_zero_when_no_record(mock_session):
    """A missing aggregation row is treated as zero deletions, not a crash."""
    from src.services.knowledge_graph.knowledge_graph_service import (
        KnowledgeGraphService,
    )

    result = MagicMock()
    result.single.return_value = None
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=ctx)
    ctx.__exit__ = MagicMock(return_value=False)
    ctx.run.return_value = result
    mock_session.return_value = ctx

    assert KnowledgeGraphService().delete_document_graph("doc-1", "org-1") == 0
