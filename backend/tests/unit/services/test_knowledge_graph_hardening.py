"""
Tests for Knowledge Graph service hardening:
  - Tenant isolation (source_document_ids filtering)
  - Integration contracts (search, adapters)
  - Serialization (metadata/evidence roundtrip)
  - Entity identity (name validation)
"""

import json
import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_neo4j_entity(
    entity_id: str = None,
    name: str = "Test Entity",
    entity_type: str = "PERSON",
    source_document_id: str = None,
    metadata: str = "{}",
):
    """Create a mock Neo4j node record for an entity."""
    return {
        "id": entity_id or str(uuid.uuid4()),
        "name": name,
        "type": entity_type,
        "confidence_score": 0.9,
        "extraction_method": "llm_extraction",
        "position": None,
        "context": "test context",
        "metadata": metadata,
        "source_document_id": source_document_id,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }


# ---------------------------------------------------------------------------
# Phase 1: Tenant Isolation
# ---------------------------------------------------------------------------

class TestTenantIsolation:
    """Verify source_document_ids filtering in service methods."""

    @patch("src.services.knowledge_graph.knowledge_graph_service.KnowledgeGraphService.get_session")
    def test_get_entity_scoped_returns_none_for_wrong_org(self, mock_session):
        """get_entity with source_document_ids should return None when entity
        belongs to a different org's document."""
        from src.services.knowledge_graph.knowledge_graph_service import (
            KnowledgeGraphService,
        )

        # Entity belongs to doc-A, but caller passes doc-B scope
        mock_result = MagicMock()
        mock_result.single.return_value = None
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.run.return_value = mock_result
        mock_session.return_value = mock_ctx

        svc = KnowledgeGraphService()
        result = svc.get_entity("entity-1", source_document_ids=["doc-B"])
        assert result is None

        # Verify the Cypher includes source_document_ids filtering
        call_args = mock_ctx.run.call_args
        query = call_args[0][0]
        assert "source_document_id IN $source_document_ids" in query
        assert call_args[0][1]["source_document_ids"] == ["doc-B"]

    @patch("src.services.knowledge_graph.knowledge_graph_service.KnowledgeGraphService.get_session")
    def test_search_entities_scoped(self, mock_session):
        """search_entities with source_document_ids should include the filter."""
        from src.services.knowledge_graph.knowledge_graph_service import (
            KnowledgeGraphService,
        )

        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.run.return_value = mock_result
        mock_session.return_value = mock_ctx

        svc = KnowledgeGraphService()
        svc.search_entities("test", source_document_ids=["doc-X"])

        call_args = mock_ctx.run.call_args
        query = call_args[0][0]
        assert "source_document_id IN $source_document_ids" in query

    @patch("src.services.knowledge_graph.knowledge_graph_service.KnowledgeGraphService.get_session")
    def test_delete_entity_scoped(self, mock_session):
        """delete_entity with source_document_ids should scope the MATCH."""
        from src.services.knowledge_graph.knowledge_graph_service import (
            KnowledgeGraphService,
        )

        mock_result = MagicMock()
        mock_result.single.return_value = {"deleted_count": 0}
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.run.return_value = mock_result
        mock_session.return_value = mock_ctx

        svc = KnowledgeGraphService()
        result = svc.delete_entity("entity-1", source_document_ids=["doc-B"])
        assert result is False

        call_args = mock_ctx.run.call_args
        query = call_args[0][0]
        assert "source_document_id IN $source_document_ids" in query

    @patch("src.services.knowledge_graph.knowledge_graph_service.KnowledgeGraphService.get_session")
    def test_get_all_entities_no_null_escape(self, mock_session):
        """get_all_entities should NOT include IS NULL escape hatch."""
        from src.services.knowledge_graph.knowledge_graph_service import (
            KnowledgeGraphService,
        )

        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.run.return_value = mock_result
        mock_session.return_value = mock_ctx

        svc = KnowledgeGraphService()
        svc.get_all_entities(limit=10, offset=0, source_document_ids=["doc-A"])

        call_args = mock_ctx.run.call_args
        query = call_args[0][0]
        assert "IS NULL" not in query


# ---------------------------------------------------------------------------
# Phase 2: Integration Contracts
# ---------------------------------------------------------------------------

class TestIntegrationContracts:
    """Verify adapter methods match caller expectations."""

    def test_search_method_exists(self):
        """KnowledgeGraphService should have a search() method."""
        from src.services.knowledge_graph.knowledge_graph_service import (
            KnowledgeGraphService,
        )
        assert hasattr(KnowledgeGraphService, "search")

    def test_create_entity_node_adapter_exists(self):
        """KnowledgeGraphService should have create_entity_node()."""
        from src.services.knowledge_graph.knowledge_graph_service import (
            KnowledgeGraphService,
        )
        assert hasattr(KnowledgeGraphService, "create_entity_node")

    def test_find_entity_node_adapter_exists(self):
        """KnowledgeGraphService should have find_entity_node()."""
        from src.services.knowledge_graph.knowledge_graph_service import (
            KnowledgeGraphService,
        )
        assert hasattr(KnowledgeGraphService, "find_entity_node")

    def test_query_graph_adapter_exists(self):
        """KnowledgeGraphService should have query_graph()."""
        from src.services.knowledge_graph.knowledge_graph_service import (
            KnowledgeGraphService,
        )
        assert hasattr(KnowledgeGraphService, "query_graph")

    @patch("src.services.knowledge_graph.knowledge_graph_service.KnowledgeGraphService.search_entities")
    def test_search_returns_search_response(self, mock_search_entities):
        """search() should return a SearchResponse with .results attribute."""
        from src.services.knowledge_graph.knowledge_graph_service import (
            KnowledgeGraphService,
        )

        mock_search_entities.return_value = []

        svc = KnowledgeGraphService()
        result = svc.search(
            search_request=MagicMock(query="test", limit=10, offset=0),
            user_id="user-1",
            organization_id="org-1",
        )

        assert hasattr(result, "results")
        assert hasattr(result, "search_time_ms")
        assert hasattr(result, "total_results")
        assert isinstance(result.results, list)

    @patch("src.services.knowledge_graph.knowledge_graph_service.KnowledgeGraphService.search_entities")
    def test_query_graph_returns_list_of_dicts(self, mock_search_entities):
        """query_graph() should return a list of dicts."""
        from src.services.knowledge_graph.knowledge_graph_service import (
            KnowledgeGraphService,
        )

        mock_search_entities.return_value = []
        svc = KnowledgeGraphService()
        result = svc.query_graph("some query")
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Phase 3: Serialization
# ---------------------------------------------------------------------------

class TestSerialization:
    """Verify JSON serialization roundtrips correctly."""

    def test_parse_metadata_from_json_string(self):
        """_parse_metadata should parse json.dumps() output."""
        from src.services.knowledge_graph.knowledge_graph_service import (
            _parse_metadata,
        )
        data = {"key": "value", "nested": {"a": 1}}
        result = _parse_metadata(json.dumps(data))
        assert result == data

    def test_parse_metadata_from_python_repr(self):
        """_parse_metadata should handle legacy str() format."""
        from src.services.knowledge_graph.knowledge_graph_service import (
            _parse_metadata,
        )
        result = _parse_metadata("{'key': 'value'}")
        assert result == {"key": "value"}

    def test_parse_metadata_from_dict(self):
        """_parse_metadata should pass through native dicts."""
        from src.services.knowledge_graph.knowledge_graph_service import (
            _parse_metadata,
        )
        data = {"key": "value"}
        assert _parse_metadata(data) == data

    def test_parse_metadata_empty(self):
        """_parse_metadata should handle empty/null values."""
        from src.services.knowledge_graph.knowledge_graph_service import (
            _parse_metadata,
        )
        assert _parse_metadata(None) == {}
        assert _parse_metadata("") == {}
        assert _parse_metadata("{}") == {}

    def test_parse_evidence_from_json_string(self):
        """_parse_evidence should parse json.dumps() output."""
        from src.services.knowledge_graph.knowledge_graph_service import (
            _parse_evidence,
        )
        data = ["evidence1", "evidence2"]
        result = _parse_evidence(json.dumps(data))
        assert result == data

    def test_parse_evidence_from_list(self):
        """_parse_evidence should pass through native lists."""
        from src.services.knowledge_graph.knowledge_graph_service import (
            _parse_evidence,
        )
        data = ["a", "b"]
        assert _parse_evidence(data) == data

    def test_parse_evidence_empty(self):
        """_parse_evidence should handle empty/null values."""
        from src.services.knowledge_graph.knowledge_graph_service import (
            _parse_evidence,
        )
        assert _parse_evidence(None) == []
        assert _parse_evidence("") == []
        assert _parse_evidence("[]") == []


# ---------------------------------------------------------------------------
# Phase 4: Entity Identity
# ---------------------------------------------------------------------------

class TestEntityIdentity:
    """Verify name validation in entity creation."""

    def test_create_entity_rejects_blank_name(self):
        """create_entity should raise ValueError for blank names."""
        from src.models.graph import CreateEntityRequest, EntityType, ExtractionMethod
        from src.services.knowledge_graph.knowledge_graph_service import (
            KnowledgeGraphService,
        )

        svc = KnowledgeGraphService()
        request = CreateEntityRequest(
            name="",
            entity_type=EntityType.PERSON,
        )
        with pytest.raises(ValueError, match="blank"):
            svc.create_entity(request)

    def test_create_entity_rejects_whitespace_name(self):
        """create_entity should raise ValueError for whitespace-only names."""
        from src.models.graph import CreateEntityRequest, EntityType, ExtractionMethod
        from src.services.knowledge_graph.knowledge_graph_service import (
            KnowledgeGraphService,
        )

        svc = KnowledgeGraphService()
        request = CreateEntityRequest(
            name="   ",
            entity_type=EntityType.PERSON,
        )
        with pytest.raises(ValueError, match="blank"):
            svc.create_entity(request)

    @patch("src.services.knowledge_graph.knowledge_graph_service.KnowledgeGraphService.get_session")
    def test_create_entity_strips_whitespace(self, mock_session):
        """create_entity should strip leading/trailing whitespace from names."""
        from src.models.graph import CreateEntityRequest, EntityType
        from src.services.knowledge_graph.knowledge_graph_service import (
            KnowledgeGraphService,
        )

        mock_node = MagicMock()
        mock_node.__getitem__ = MagicMock(return_value={})
        mock_result = MagicMock()
        mock_result.single.return_value = mock_node
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.run.return_value = mock_result
        mock_session.return_value = mock_ctx

        svc = KnowledgeGraphService()
        request = CreateEntityRequest(
            name="  John Doe  ",
            entity_type=EntityType.PERSON,
        )
        result = svc.create_entity(request)

        # Verify the name passed to Neo4j was stripped
        call_args = mock_ctx.run.call_args
        params = call_args[0][1]
        assert params["name"] == "John Doe"
