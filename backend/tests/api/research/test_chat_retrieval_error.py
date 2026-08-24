"""B10: a failed RAG retrieval must be visible, and its answer uncached.

``retrieve_context`` used to swallow every exception and return ``([], None)``,
so the caller reported ``rag_enabled=True`` with zero contexts and cached the
context-free answer under the RAG-shaped cache key — poisoning later turns.
Failures now raise ``RetrievalError``; the completion endpoint marks
``retrieval_error=True`` on an additive response field and skips the LLM
response cache for that turn.
"""

from contextlib import ExitStack
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import BackgroundTasks

from src.api.research import chat as chat_module
from src.api.research.chat import (
    ChatCompletionRequest,
    ChatMessage,
    RetrievalError,
    RetrievedContext,
    retrieve_context,
)
from src.services.infrastructure.llm_response_cache import (
    LLMCacheConfig,
    LLMResponseCache,
)


@pytest.fixture
def mock_user():
    user = Mock()
    user.id = "user-1"
    user.organization_id = "org-1"
    return user


def _completion_patches(cache_set):
    return (
        patch.object(
            chat_module.azure_openai_service, "is_chat_available", return_value=True
        ),
        patch.object(
            chat_module.azure_openai_service,
            "chat_completion",
            new=AsyncMock(return_value={"content": "degraded answer"}),
        ),
        patch.object(
            chat_module.llm_response_cache, "get", new=AsyncMock(return_value=None)
        ),
        patch.object(chat_module.llm_response_cache, "set", new=cache_set),
    )


@pytest.mark.asyncio
async def test_retrieve_context_raises_dedicated_error_on_search_failure():
    """Hybrid-search infrastructure failures raise RetrievalError, not []."""
    with patch.object(
        chat_module.hybrid_search_service,
        "search_with_diagnostics",
        side_effect=RuntimeError("redis down"),
    ):
        with pytest.raises(RetrievalError):
            await retrieve_context("what is rag?", 5, organization_id="org-1")


@pytest.mark.asyncio
async def test_completion_marks_retrieval_error_and_skips_cache(mock_user):
    """Failure turn: retrieval_error=True, answer still served, never cached."""
    cache_set = AsyncMock()
    patches = _completion_patches(cache_set)
    request = ChatCompletionRequest(
        messages=[ChatMessage(role="user", content="what is rag?")],
        use_rag=True,
    )
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        stack.enter_context(
            patch.object(
                chat_module,
                "retrieve_context",
                new=AsyncMock(side_effect=RetrievalError("hybrid search down")),
            )
        )
        response = await chat_module.chat_completions(
            request, BackgroundTasks(), current_user=mock_user
        )

    # Response contract intact: answer served, RAG intent reflected...
    assert response.message.content == "degraded answer"
    assert response.rag_enabled is True
    assert response.retrieved_contexts == []

    # ...but the degradation is visible and nothing was cached.
    assert response.retrieval_error is True
    cache_set.assert_not_awaited()


@pytest.mark.asyncio
async def test_successful_rag_turn_has_no_retrieval_error_and_caches(mock_user):
    """Success path unchanged: default flag False, response still cached."""
    cache_set = AsyncMock()
    patches = _completion_patches(cache_set)
    contexts = [
        RetrievedContext(
            document_id="doc-1",
            title="Paper",
            content="Relevant passage.",
            score=0.9,
        )
    ]
    request = ChatCompletionRequest(
        messages=[ChatMessage(role="user", content="what is rag?")],
        use_rag=True,
    )
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        stack.enter_context(
            patch.object(
                chat_module,
                "retrieve_context",
                new=AsyncMock(return_value=(contexts, None)),
            )
        )
        response = await chat_module.chat_completions(
            request, BackgroundTasks(), current_user=mock_user
        )

    assert response.retrieval_error is False
    cache_set.assert_awaited_once()


@pytest.mark.asyncio
async def test_non_rag_turn_unaffected_by_flag(mock_user):
    """use_rag=False responses default retrieval_error=False."""
    cache_set = AsyncMock()
    patches = _completion_patches(cache_set)
    request = ChatCompletionRequest(
        messages=[ChatMessage(role="user", content="hello")],
        use_rag=False,
    )
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        response = await chat_module.chat_completions(
            request, BackgroundTasks(), current_user=mock_user
        )

    assert response.rag_enabled is False
    assert response.retrieval_error is False


@pytest.mark.asyncio
async def test_degraded_turn_never_serves_poisoned_legacy_cache_entry(mock_user):
    """A retrieval_error turn must not read the RAG-shaped cache key.

    Entries cached before the write-skip fix exist under the context-free
    key shape (context-free answers stored as if RAG-backed). If the cache
    GET still runs on a degraded turn, one of those legacy poison entries
    gets served as the answer.
    """
    POISON = "POISONED legacy answer"
    cache = LLMResponseCache(LLMCacheConfig(use_redis=False, use_semantic_cache=False))
    # Pre-seed under the exact shape the endpoint computes for this turn:
    # single user message -> query == last_query, no conv/ctx suffix.
    await cache.set(
        query="what is rag?",
        response_content=POISON,
        model="gpt-4o",
        temperature=0.7,
        organization_id="org-1",
    )

    request = ChatCompletionRequest(
        messages=[ChatMessage(role="user", content="what is rag?")],
        use_rag=True,
    )
    with ExitStack() as stack:
        stack.enter_context(
            patch.object(
                chat_module.azure_openai_service,
                "is_chat_available",
                return_value=True,
            )
        )
        stack.enter_context(
            patch.object(
                chat_module.azure_openai_service,
                "chat_completion",
                new=AsyncMock(return_value={"content": "degraded answer"}),
            )
        )
        # Real seeded instance: get/set NOT mocked, so a poisoned entry can
        # actually be served (or not).
        stack.enter_context(patch.object(chat_module, "llm_response_cache", cache))
        stack.enter_context(
            patch.object(
                chat_module,
                "retrieve_context",
                new=AsyncMock(side_effect=RetrievalError("hybrid search down")),
            )
        )
        response = await chat_module.chat_completions(
            request, BackgroundTasks(), current_user=mock_user
        )

    # Degraded turn must regenerate fresh, never serve the poison.
    assert response.retrieval_error is True
    assert response.message.content != POISON
