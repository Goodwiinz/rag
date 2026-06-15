"""Audit D2/D3: graph analytics must scope on organization_id (matching the write
path + #50 read-flip) and refuse to run unscoped (no cross-org leakage)."""

import pytest


@pytest.mark.unit
class TestValidateOrganizationId:
    def _fn(self):
        from src.services.knowledge_graph.graph_algorithms import (
            _validate_organization_id,
        )

        return _validate_organization_id

    def test_valid_uuid_returns(self):
        org = "123e4567-e89b-12d3-a456-426614174000"
        assert self._fn()(org) == org

    @pytest.mark.parametrize("bad", [None, "", "not-a-uuid", "12345"])
    def test_missing_or_invalid_raises(self, bad):
        with pytest.raises(ValueError):
            self._fn()(bad)


class _FakeResult:
    def __init__(self, records):
        self._records = records

    def __aiter__(self):
        async def _gen():
            for r in self._records:
                yield r

        return _gen()


class _FakeSession:
    def __init__(self):
        self.last_query = None
        self.last_params = None
        self.run_called = False

    async def run(self, query, params=None):
        self.run_called = True
        self.last_query = query
        self.last_params = params or {}
        return _FakeResult([])


@pytest.mark.unit
class TestDegreeCentralityScoping:
    def _algo(self):
        from src.services.knowledge_graph.graph_algorithms import GraphAlgorithms

        return GraphAlgorithms()

    @pytest.mark.asyncio
    async def test_scopes_query_by_organization_id(self):
        org = "123e4567-e89b-12d3-a456-426614174000"
        session = _FakeSession()
        await self._algo().compute_degree_centrality(session, organization_id=org)
        assert "e.organization_id = $organization_id" in session.last_query
        assert session.last_params["organization_id"] == org

    @pytest.mark.asyncio
    async def test_unscoped_returns_empty_and_never_queries(self):
        """No organization_id → validator raises → empty result, no Cypher run
        (so analytics can never run over the whole cross-org graph)."""
        session = _FakeSession()
        result = await self._algo().compute_degree_centrality(
            session, organization_id=None
        )
        assert result["results"] == []
        assert session.run_called is False
