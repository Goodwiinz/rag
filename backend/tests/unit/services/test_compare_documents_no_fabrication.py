"""Regression: compare_documents must not fabricate success on LLM failure.

Previously, when the comparison LLM call raised, the tool returned a
success-shaped result containing "Comparison could not be generated. Documents
were retrieved successfully." — so the agent presented a non-comparison as a
real one. It must now return an {"error": ...} result instead.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.agent.tools_impl import _tool_compare_documents


def _doc(doc_id: str, title: str):
    d = MagicMock()
    d.id = doc_id
    d.title = title
    d.content_text = "some document body text"
    return d


@pytest.mark.unit
@pytest.mark.asyncio
async def test_llm_failure_returns_error_not_fabricated_success():
    user = MagicMock()
    user.organization_id = "org-1"
    db = MagicMock()

    docs = {"docA": _doc("idA", "A"), "docB": _doc("idB", "B")}
    failing_llm = MagicMock()
    failing_llm.ainvoke = AsyncMock(side_effect=Exception("model down"))

    with (
        patch("src.services.documents.file_service.FileService"),
        patch(
            "src.api.agent.tools_impl._resolve_document_id",
            new=AsyncMock(side_effect=lambda raw, *a, **k: docs.get(raw)),
        ),
        patch(
            "src.api.agent.tools_impl._get_tool_llm",
            return_value=failing_llm,
        ),
    ):
        result = await _tool_compare_documents(
            {"document_ids": ["docA", "docB"], "type": "general"}, db, user
        )

    assert "error" in result
    assert "comparison" not in result
    assert "retrieved successfully" not in str(result).lower()
