"""Draft generation's LLM client must not be OpenAI-key-only.

`_init_openai_client` previously read only `settings.OPENAI_API_KEY`, so on
Azure-only dev environments it always returned `None` and `_build_draft_content`
silently fell back to the template. It now delegates to
`ExtractionMatrixService._get_openai_client` (Azure-first, same selection the
extraction matrix already uses live).
"""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import openai
import pytest

pytestmark = pytest.mark.unit

from src.services.research.draft_generation_service import DraftGenerationService


def test_azure_keys_set_returns_azure_client():
    fake_client = MagicMock(spec=openai.AsyncAzureOpenAI)
    with patch(
        "src.services.research.extraction_matrix_service"
        ".ExtractionMatrixService._get_openai_client",
        return_value=(fake_client, "gpt-4o-deployment"),
    ):
        client, model = DraftGenerationService._init_openai_client()

    assert client is fake_client
    assert model == "gpt-4o-deployment"


def test_openai_key_only_returns_openai_client():
    fake_client = MagicMock(spec=openai.AsyncOpenAI)
    with patch(
        "src.services.research.extraction_matrix_service"
        ".ExtractionMatrixService._get_openai_client",
        return_value=(fake_client, "gpt-4o-mini"),
    ):
        client, model = DraftGenerationService._init_openai_client()

    assert client is fake_client
    assert model == "gpt-4o-mini"


def test_no_keys_returns_none_and_template_fallback():
    with patch(
        "src.services.research.extraction_matrix_service"
        ".ExtractionMatrixService._get_openai_client",
        side_effect=RuntimeError("No OpenAI or Azure OpenAI API key configured."),
    ):
        client, model = DraftGenerationService._init_openai_client()

    assert client is None
    assert model == ""


@pytest.mark.asyncio
async def test_build_draft_content_falls_back_to_template_without_client():
    with patch(
        "src.services.research.extraction_matrix_service"
        ".ExtractionMatrixService._get_openai_client",
        side_effect=RuntimeError("No OpenAI or Azure OpenAI API key configured."),
    ):
        service = DraftGenerationService(db=MagicMock())

    assert service._openai_client is None

    content, used_fallback = await service._build_draft_content(
        documents=[],
        themes=["theme a"],
        style="academic",
        max_sections=5,
        include_abstract=True,
    )

    assert "## Abstract" in content
    assert used_fallback is True  # W-B6: degraded drafts must be marked


@pytest.mark.asyncio
async def test_build_draft_with_llm_passes_configured_model():
    fake_client = MagicMock()
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content="Some draft content."))]
    fake_client.chat.completions.create = AsyncMock(return_value=response)

    with patch(
        "src.services.research.extraction_matrix_service"
        ".ExtractionMatrixService._get_openai_client",
        return_value=(fake_client, "my-deployment"),
    ):
        service = DraftGenerationService(db=MagicMock())

    await service._build_draft_with_llm(
        documents=[],
        themes=["theme a"],
        style="academic",
        max_sections=5,
        include_abstract=True,
    )

    kwargs: Dict[str, Any] = fake_client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "my-deployment"


@pytest.mark.asyncio
async def test_gpt5_model_omits_temperature_gpt4o_keeps_it():
    fake_client = MagicMock()
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content="Some draft content."))]
    fake_client.chat.completions.create = AsyncMock(return_value=response)

    with patch(
        "src.services.research.extraction_matrix_service"
        ".ExtractionMatrixService._get_openai_client",
        return_value=(fake_client, "gpt-5-deployment"),
    ):
        service = DraftGenerationService(db=MagicMock())

    await service._build_draft_with_llm(
        documents=[],
        themes=["theme a"],
        style="academic",
        max_sections=5,
        include_abstract=True,
    )

    kwargs = fake_client.chat.completions.create.call_args.kwargs
    assert "temperature" not in kwargs
    # gpt-5 also rejects max_tokens — must use max_completion_tokens.
    assert "max_tokens" not in kwargs
    assert kwargs["max_completion_tokens"] == 4000

    fake_client.chat.completions.create.reset_mock()
    with patch(
        "src.services.research.extraction_matrix_service"
        ".ExtractionMatrixService._get_openai_client",
        return_value=(fake_client, "gpt-4o"),
    ):
        service = DraftGenerationService(db=MagicMock())

    await service._build_draft_with_llm(
        documents=[],
        themes=["theme a"],
        style="academic",
        max_sections=5,
        include_abstract=True,
    )

    kwargs = fake_client.chat.completions.create.call_args.kwargs
    assert kwargs["temperature"] == 0.7
    assert kwargs["max_tokens"] == 4000
    assert "max_completion_tokens" not in kwargs


@pytest.mark.asyncio
async def test_generate_draft_reuses_active_generation():
    """W-B4: a second generate_draft for the same project must not race the
    in-flight one for the same version number — it returns the active task."""
    from unittest.mock import MagicMock, patch
    from uuid import uuid4

    with patch(
        "src.services.research.extraction_matrix_service"
        ".ExtractionMatrixService._get_openai_client",
        side_effect=RuntimeError("no key"),
    ):
        service = DraftGenerationService(db=MagicMock())

    project_id = uuid4()
    active = {"task_id": "abc123", "status": "generating"}
    with patch.object(
        DraftGenerationService, "get_latest_status", return_value=active
    ) as get_status, patch.object(
        DraftGenerationService, "_fire_and_forget"
    ) as fire:
        result = await service.generate_draft(
            project_id=project_id,
            user_id=uuid4(),
            themes=["t"],
        )

    get_status.assert_called_once_with(project_id, active_only=True)
    fire.assert_not_called()
    assert result["task_id"] == "abc123"
    assert "already in progress" in result["message"]
