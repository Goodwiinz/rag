import pytest
from unittest.mock import AsyncMock
from src.services.knowledge_graph.sync_service import KGSyncService, KGSyncResult


@pytest.mark.asyncio
async def test_sync_returns_result_in_dry_run_mode():
    pg = AsyncMock()
    neo4j = AsyncMock()
    pg.fetch_indexed_document_ids.return_value = set()
    neo4j.fetch_document_node_ids.return_value = set()
    neo4j.fetch_entity_counts.return_value = {}
    pg.fetch_entity_counts.return_value = {}
    neo4j.fetch_nodes_missing_tenant.return_value = []

    svc = KGSyncService(pg=pg, neo4j=neo4j, auto_repair=False)
    result = await svc.run(run_id="test-run")

    assert isinstance(result, KGSyncResult)
    assert result.orphan_count == 0
    assert result.fixed_count == 0
    assert result.status == "success"
