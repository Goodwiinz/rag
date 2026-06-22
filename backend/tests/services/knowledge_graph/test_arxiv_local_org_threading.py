"""Phase 1b-2: arxiv_local sync KG update threads org across the executor.

extract_features_from_local_pdfs schedules _post_process_extraction as a
background task (no current_user), which runs the KG update in a thread executor.
The org is resolved at the handler and threaded through so entities created off
the request thread are still tenant-scoped.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
def test_sync_kg_update_threads_org_to_entities() -> None:
    from src.api.arxiv import arxiv_local

    captured = []

    def _capture(req: Any) -> Any:
        captured.append(req)
        return MagicMock(id="e")

    mock_kg = MagicMock()
    mock_kg.create_entity.side_effect = _capture

    with patch(
        "src.services.knowledge_graph.knowledge_graph_service.KnowledgeGraphService",
        return_value=mock_kg,
    ):
        arxiv_local._update_knowledge_graph_with_local_extractions_sync(
            {
                "paper_id": "2605.1",
                "filename": "f.pdf",
                "features": {
                    "metadata": {"title": "EHR-RAGp"},
                    "topics": ["retrieval"],
                    "keyphrases": [],
                    "summary": "",
                },
            },
            organization_id="org-X",
        )

    assert captured, "expected entities to be created"
    # Both the paper entity and the topic entity carry the threaded org.
    assert all(r.organization_id == "org-X" for r in captured)
