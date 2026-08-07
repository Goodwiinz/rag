"""The hybrid fallback is the default-config retrieval path (DO_KB_ENABLED
false) and must redact credential-shaped content before contexts reach the
system prompt / SSE frame / citations (audit 2026-08-07, gap 1)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

MARKER = "gho_000000000000000000000000000000000000"


def _fake_result(title: str, full_text: str) -> SimpleNamespace:
    return SimpleNamespace(
        document_id="11111111-1111-1111-1111-111111111111",
        title=title,
        metadata={"full_text": full_text},
        content_preview=None,
        relevance_score=0.9,
    )


async def test_hybrid_fallback_redacts_title_and_content() -> None:
    from src.services.agent._nodes_rag import _legacy_hybrid_search_fallback

    response = SimpleNamespace(
        results=[_fake_result(f"Ops notes {MARKER}", f"token is {MARKER} ok")]
    )
    with patch(
        "src.services.search.hybrid_search_service.hybrid_search_service.search",
        return_value=response,
    ):
        contexts = await _legacy_hybrid_search_fallback(
            query="ops token", user_id="u-1", organization_id="o-1"
        )

    assert len(contexts) == 1
    assert MARKER not in contexts[0]["title"]
    assert MARKER not in contexts[0]["content"]
    assert "<token>" in contexts[0]["content"]


async def test_hybrid_fallback_leaves_clean_content_intact() -> None:
    from src.services.agent._nodes_rag import _legacy_hybrid_search_fallback

    response = SimpleNamespace(results=[_fake_result("Plain title", "plain body text")])
    with patch(
        "src.services.search.hybrid_search_service.hybrid_search_service.search",
        return_value=response,
    ):
        contexts = await _legacy_hybrid_search_fallback(
            query="plain", user_id="u-1", organization_id="o-1"
        )

    assert contexts[0]["title"] == "Plain title"
    assert contexts[0]["content"] == "plain body text"
