"""Phase 1b: ingest paths thread organization_id onto entity writes.

Covers the arxiv KG integration entity path (the one with a clean, unit-testable
signature). The other ingest sites (processing_tasks, multimodal, enhanced_doc,
arxiv_local) build CreateEntityRequest with organization_id=document/user org;
they are exercised by integration smoke + reviewed by diff.
"""

from typing import Any, Dict
from unittest.mock import MagicMock

import pytest


@pytest.mark.unit
@pytest.mark.asyncio
async def test_add_entity_to_kg_threads_org() -> None:
    from src.services.arxiv.arxiv_kg_integration import (
        ArXivKnowledgeGraphIntegration,
    )

    svc = ArXivKnowledgeGraphIntegration()
    captured: Dict[str, Any] = {}

    kg = MagicMock()
    kg.create_entity.side_effect = lambda req: captured.update(request=req)
    svc.kg_service = kg

    await svc._add_entity_to_kg(
        entity={
            "text": "Insulin",
            "type": "concept",
            "confidence": 0.9,
            "source": "abstract",
        },
        paper={"id": "2605.1", "title": "T", "primary_category": "cs.AI"},
        organization_id="org-X",
    )

    assert captured["request"].organization_id == "org-X"
