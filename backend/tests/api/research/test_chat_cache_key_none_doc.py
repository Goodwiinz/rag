"""B6: the RAG cache key must tolerate contexts without a document_id.

``retrieved_contexts`` can contain entries whose ``document_id`` is None
(retrieve_context maps missing ids to None). The cache-key construction
sorted the raw Optional ids, so one id-less context raised TypeError and
turned an already-successful retrieval into a 500.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import BackgroundTasks, HTTPException

from src.api.research import chat as chat_module
from src.api.research.chat import ChatCompletionRequest, ChatMessage, RetrievedContext


def _contexts():
    return [
        RetrievedContext(
            document_id=None,
            title="Mystery doc",
            content="No id on this one.",
            score=0.5,
        ),
        RetrievedContext(
            document_id="doc-b",
            title="Real doc",
            content="Has an arXiv id.",
            score=0.9,
        ),
    ]


@pytest.fixture
def mock_user():
    user = Mock()
    user.id = "user-1"
    user.organization_id = "org-1"
    return user


@pytest.mark.asyncio
async def test_completion_survives_context_without_document_id(mock_user):
    """A None document_id must not 500 after successful retrieval."""
    with (
        patch.object(
            chat_module.azure_openai_service, "is_chat_available", return_value=True
        ),
        patch.object(
            chat_module.azure_openai_service,
            "chat_completion",
            new=AsyncMock(return_value={"content": "answer", "model": "gpt-4o"}),
        ),
        patch.object(
            chat_module,
            "retrieve_context",
            new=AsyncMock(return_value=(_contexts(), "trace-1")),
        ),
        patch.object(
            chat_module.llm_response_cache, "get", new=AsyncMock(return_value=None)
        ) as cache_get,
        patch.object(
            chat_module.llm_response_cache, "set", new=AsyncMock()
        ) as cache_set,
    ):
        request = ChatCompletionRequest(
            messages=[ChatMessage(role="user", content="what is rag?")],
            use_rag=True,
        )
        response = await chat_module.chat_completions(
            request, BackgroundTasks(), current_user=mock_user
        )

    assert response.message.content == "answer"
    assert response.rag_enabled is True

    # Omitting an id-less context from the fingerprint would make distinct
    # context sets collide, so this turn is deliberately not cacheable.
    cache_get.assert_not_awaited()
    cache_set.assert_not_awaited()


@pytest.mark.asyncio
async def test_cache_key_join_matches_expected_order(mock_user):
    """Ids are stringified, de-None'd, sorted, and '|'-joined."""
    contexts = [
        RetrievedContext(document_id="doc-c", title="C", content="c", score=0.3),
        RetrievedContext(document_id="doc-a", title="A", content="a", score=0.8),
    ]
    with (
        patch.object(
            chat_module.azure_openai_service, "is_chat_available", return_value=True
        ),
        patch.object(
            chat_module.azure_openai_service,
            "chat_completion",
            new=AsyncMock(return_value={"content": "ok"}),
        ),
        patch.object(
            chat_module,
            "retrieve_context",
            new=AsyncMock(return_value=(contexts, None)),
        ),
        patch.object(
            chat_module.llm_response_cache, "get", new=AsyncMock(return_value=None)
        ),
        patch.object(
            chat_module.llm_response_cache, "set", new=AsyncMock()
        ) as cache_set,
    ):
        request = ChatCompletionRequest(
            messages=[ChatMessage(role="user", content="q")], use_rag=True
        )
        await chat_module.chat_completions(
            request, BackgroundTasks(), current_user=mock_user
        )

    cache_query = cache_set.await_args.kwargs["query"]
    assert cache_query.endswith("ctx:doc-a|doc-c")


@pytest.mark.asyncio
async def test_orgless_user_cache_scope_falls_back_to_user_id(mock_user):
    """Org-less users must not share the semantic-cache tenant bucket."""
    mock_user.organization_id = None
    with (
        patch.object(
            chat_module.azure_openai_service, "is_chat_available", return_value=True
        ),
        patch.object(
            chat_module.azure_openai_service,
            "chat_completion",
            new=AsyncMock(return_value={"content": "ok"}),
        ),
        patch.object(
            chat_module.llm_response_cache, "get", new=AsyncMock(return_value=None)
        ) as cache_get,
        patch.object(
            chat_module.llm_response_cache, "set", new=AsyncMock()
        ) as cache_set,
    ):
        request = ChatCompletionRequest(
            messages=[ChatMessage(role="user", content="q")], use_rag=False
        )
        await chat_module.chat_completions(
            request, BackgroundTasks(), current_user=mock_user
        )

    assert cache_get.await_args.kwargs["organization_id"] == "user:user-1"
    assert cache_set.await_args.kwargs["organization_id"] == "user:user-1"


# Old behavior (pre-B6), documented rather than unit-tested: the inline
# expression "|".join(sorted([c.document_id for c in contexts])) over raw
# Optional ids raised TypeError as soon as any document_id was None.
