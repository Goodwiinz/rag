"""search_documents returns titles into a model-visible ToolMessage; titles
are user-supplied and must pass redact_pii (audit 2026-08-07, gap 1)."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

MARKER = "gho_000000000000000000000000000000000000"


def _fake_doc(title: str) -> SimpleNamespace:
    return SimpleNamespace(
        id="22222222-2222-2222-2222-222222222222",
        title=title,
        document_type=None,
        processing_status=None,
        created_at=datetime(2026, 8, 7, tzinfo=timezone.utc),
    )


async def test_search_documents_redacts_titles() -> None:
    from src.services.agent.tools_impl import _tool_search_documents

    scalars = MagicMock()
    scalars.all.return_value = [_fake_doc(f"creds {MARKER}")]
    result_proxy = MagicMock()
    result_proxy.scalars.return_value = scalars
    db = SimpleNamespace(execute=AsyncMock(return_value=result_proxy))
    current_user = SimpleNamespace(organization_id="org-1")

    result = await _tool_search_documents({"query": "creds"}, db, current_user)

    assert "error" not in result
    assert MARKER not in result["documents"][0]["title"]
    assert "<token>" in result["documents"][0]["title"]
