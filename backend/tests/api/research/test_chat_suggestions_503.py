"""B9: the suggestions endpoint must not swallow infrastructure failures.

The bare ``except Exception`` returned ``{suggestions: []}`` for every
failure, making an LLM outage indistinguishable from "no suggestions".
Genuine parse failures (LLM replied unparseably) still degrade to empty;
infrastructure failures now surface as HTTP 503.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException

from src.api.research import chat as chat_module
from src.api.research.chat import ChatMessage, SuggestionsRequest


def _request() -> SuggestionsRequest:
    return SuggestionsRequest(
        messages=[ChatMessage(role="user", content="What is RAG?")],
        count=3,
    )


@pytest.fixture
def mock_user() -> Mock:
    return Mock(id="user-1", organization_id="org-1")


@pytest.mark.asyncio
async def test_infrastructure_failure_raises_503(mock_user: Mock) -> None:
    """An unexpected LLM/service exception surfaces as 503, not empty 200."""
    with (
        patch.object(
            chat_module.azure_openai_service, "is_chat_available", return_value=True
        ),
        patch.object(
            chat_module.azure_openai_service,
            "chat_completion",
            new=AsyncMock(side_effect=RuntimeError("connection reset")),
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await chat_module.generate_suggestions(_request(), current_user=mock_user)

    assert exc_info.value.status_code == 503
    assert "unavailable" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_unparseable_llm_output_still_returns_empty(mock_user: Mock) -> None:
    """Genuine 'no suggestions' (unparseable reply) degrades to empty 200."""
    with (
        patch.object(
            chat_module.azure_openai_service, "is_chat_available", return_value=True
        ),
        patch.object(
            chat_module.azure_openai_service,
            "chat_completion",
            new=AsyncMock(return_value={"content": "not json at all"}),
        ),
    ):
        response = await chat_module.generate_suggestions(
            _request(), current_user=mock_user
        )

    assert response.suggestions == []


@pytest.mark.asyncio
async def test_happy_path_returns_parsed_suggestions(mock_user: Mock) -> None:
    """Existing behavior preserved: valid JSON array is parsed and trimmed."""
    with (
        patch.object(
            chat_module.azure_openai_service, "is_chat_available", return_value=True
        ),
        patch.object(
            chat_module.azure_openai_service,
            "chat_completion",
            new=AsyncMock(
                return_value={
                    "content": '["How does hybrid search work?", "Show citations?"]'
                }
            ),
        ),
    ):
        response = await chat_module.generate_suggestions(
            _request(), current_user=mock_user
        )

    assert response.suggestions == [
        "How does hybrid search work?",
        "Show citations?",
    ]


@pytest.mark.asyncio
async def test_service_unavailable_still_returns_empty(mock_user: Mock) -> None:
    """Explicit availability gate keeps its pre-existing empty-response contract."""
    with patch.object(
        chat_module.azure_openai_service, "is_chat_available", return_value=False
    ):
        response = await chat_module.generate_suggestions(
            _request(), current_user=mock_user
        )

    assert response.suggestions == []
