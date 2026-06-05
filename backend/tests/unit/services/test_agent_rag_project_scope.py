"""Audit #7: the active project context must take precedence over a UUID
parsed from the user's message text, so a stale/quoted /projects/<uuid> URL
cannot silently re-scope RAG retrieval to another project.
"""

from __future__ import annotations

import pytest

from src.services.agent._nodes_rag import _resolve_active_project_id

pytestmark = pytest.mark.unit


def test_active_context_wins_over_extracted_url():
    assert _resolve_active_project_id("proj-A", "proj-B") == "proj-A"


def test_extracted_used_when_no_active_context():
    assert _resolve_active_project_id(None, "proj-B") == "proj-B"


def test_none_when_neither_present():
    assert _resolve_active_project_id(None, None) is None
