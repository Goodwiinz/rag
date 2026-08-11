"""Regression: compare_documents must not fabricate success on LLM failure.

Previously, when the comparison LLM call raised, the tool returned a
success-shaped result containing "Comparison could not be generated. Documents
were retrieved successfully." — so the agent presented a non-comparison as a
real one. It must now return an {"error": ...} result instead.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.agent.tools_impl import _tool_compare_documents


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
            "src.services.agent.tools_impl._resolve_document_id",
            new=AsyncMock(side_effect=lambda raw, *a, **k: docs.get(raw)),
        ),
        patch(
            "src.services.agent.tools_impl._get_tool_llm",
            return_value=failing_llm,
        ),
    ):
        result = await _tool_compare_documents(
            {"document_ids": ["docA", "docB"], "type": "general"}, db, user
        )

    assert "error" in result
    assert "comparison" not in result
    assert "retrieved successfully" not in str(result).lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_comparison_prompt_constrains_the_model_to_the_supplied_text():
    """The system message must carry the grounding contract.

    agent-writing-flow-v1 failed its semantic gate on 5/5 trials because the
    comparison model answered from subject-matter knowledge (GNN
    oversmoothing, long-range interaction limits, benchmark discussion) that
    neither compared document stated. The constraint lives in the system
    message, so that is what this pins.
    """
    user = MagicMock()
    user.organization_id = "org-1"
    db = MagicMock()

    docs = {"docA": _doc("idA", "A"), "docB": _doc("idB", "B")}
    llm = MagicMock()
    response = MagicMock()
    response.content = "a grounded comparison"
    llm.ainvoke = AsyncMock(return_value=response)

    with (
        patch("src.services.documents.file_service.FileService"),
        patch(
            "src.services.agent.tools_impl._resolve_document_id",
            new=AsyncMock(side_effect=lambda raw, *a, **k: docs.get(raw)),
        ),
        patch("src.services.agent.tools_impl._get_tool_llm", return_value=llm),
    ):
        result = await _tool_compare_documents(
            {"document_ids": ["docA", "docB"], "type": "general"}, db, user
        )

    assert result["comparison"] == "a grounded comparison"

    system_message = llm.ainvoke.await_args.args[0][0].content
    assert "Ground every statement in the supplied document text" in system_message
    assert "do not draw on outside knowledge" in system_message
    assert "treat a missing detail as unknown" in system_message


@pytest.mark.unit
@pytest.mark.asyncio
async def test_missing_document_error_does_not_echo_requested_identifier():
    user = MagicMock()
    user.organization_id = "org-1"
    db = AsyncMock()
    result_proxy = MagicMock()
    result_proxy.scalars.return_value.all.return_value = []
    db.execute.return_value = result_proxy
    victim_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

    result = await _tool_compare_documents(
        {"document_ids": [victim_id, "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"]},
        db,
        user,
    )

    assert result == {"error": "Document not found or access denied"}
    assert victim_id not in str(result)
