"""The request-level RAG toggle must survive into LangGraph retrieval."""

from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import HumanMessage

from src.services.agent._nodes_rag import rag_node


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rag_node_skips_retrieval_when_request_disables_rag():
    search_fn = AsyncMock(
        side_effect=AssertionError("use_rag=False must suppress retrieval")
    )
    project_id = "5ed25258-5ad2-4b06-9678-4a4abe5ecac1"
    state = {
        "messages": [
            HumanMessage(
                content="Find the most relevant evidence in this active project"
            )
        ],
        "page_context": {"type": "project", "project_id": project_id},
        "current_project_id": project_id,
        "use_rag": False,
    }

    result = await rag_node(
        state,
        config={
            "configurable": {
                "user_id": "user-1",
                "organization_id": "org-1",
                "search_fn": search_fn,
            }
        },
    )

    search_fn.assert_not_awaited()
    assert result == {
        "retrieved_contexts": [],
        "current_project_id": project_id,
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rag_node_retrieves_when_request_enables_rag():
    contexts = [
        {
            "document_id": "doc-1",
            "title": "Document 1",
            "content": "evidence",
            "score": 0.0,
        }
    ]
    search_fn = AsyncMock(return_value=contexts)
    state = {
        "messages": [
            HumanMessage(
                content="Find the most relevant evidence in this active project"
            )
        ],
        "page_context": {"type": "project"},
        "current_project_id": None,
        "use_rag": True,
    }

    result = await rag_node(
        state,
        config={
            "configurable": {
                "user_id": "user-1",
                "organization_id": "org-1",
                "search_fn": search_fn,
            }
        },
    )

    search_fn.assert_awaited_once()
    assert result["retrieved_contexts"] == contexts
