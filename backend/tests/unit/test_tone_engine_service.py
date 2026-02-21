# tests/unit/test_tone_engine_service.py
"""Tests for the Scholarly Tone Engine service."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.services.research.tone_engine_service import ToneEngineService


@pytest.mark.asyncio
async def test_rewrite_preserves_citations():
    service = ToneEngineService()

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="The findings [1] suggest improvements [3]."))]

    with patch("openai.AsyncOpenAI") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await service.rewrite(
            text="Results [1] show that this works [3].",
            tone="academic",
        )

    assert "[1]" in result["rewritten"]
    assert "[3]" in result["rewritten"]
    assert result["tone_applied"] == "academic"
    assert "[1]" in result["citations_preserved"]
    assert "[3]" in result["citations_preserved"]


def test_extract_citations():
    service = ToneEngineService()
    citations = service._extract_citations("This [1] is a test [2] with [15] citations.")
    assert citations == ["[1]", "[2]", "[15]"]


def test_extract_citations_empty():
    service = ToneEngineService()
    citations = service._extract_citations("No citations here.")
    assert citations == []
