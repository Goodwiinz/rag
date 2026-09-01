"""R7-M2: project-memory recall must be gated on a verified project.

``_resolve_and_bind_project`` is the single ownership helper on both the
/execute and the streaming path. These tests lock in the contract both call
sites now depend on: it returns the *verified* project id (``None`` when the
client-supplied id is not the caller's), and it nulls the unverified value out
of ``page_context`` so nothing downstream can scope on it either.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.services.agent.agent_execution_service import _resolve_and_bind_project

_FOREIGN_PROJECT = "11111111-1111-1111-1111-111111111111"


class _DB:
    """AsyncSession stub whose SELECTs never match (unowned project)."""

    def __init__(self, first=None, scalar=None):
        self._first = first
        self._scalar = scalar

    async def execute(self, *_a, **_k):
        result = MagicMock()
        result.first.return_value = self._first
        result.scalar_one_or_none.return_value = self._scalar
        return result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_foreign_project_id_is_rejected_and_not_returned():
    page_context = {"project_id": _FOREIGN_PROJECT}
    user = MagicMock(id="user-a", organization_id="org-a")

    verified = await _resolve_and_bind_project(_DB(), user, None, page_context)

    assert verified is None
    assert page_context["project_id"] is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_owned_project_id_is_returned():
    page_context = {"project_id": _FOREIGN_PROJECT}
    user = MagicMock(id="user-a", organization_id="org-a")
    db = _DB(first=(_FOREIGN_PROJECT, "My Project"))

    verified = await _resolve_and_bind_project(db, user, None, page_context)

    assert verified == _FOREIGN_PROJECT
    assert page_context["project_id"] == _FOREIGN_PROJECT


@pytest.mark.unit
@pytest.mark.parametrize(
    "module",
    ["src.services.agent.agent_execution_service", "src.api.agent.streaming"],
)
def test_both_call_sites_scope_project_memories_by_org(module):
    """Both recall sites must pass organization_id (R7-M2).

    A source assertion rather than a behavioural one: the surrounding code is
    a 700-line request handler, and the only thing worth locking down is that
    the tenancy kwarg is present on the call.
    """
    import importlib
    import inspect
    import re

    src = inspect.getsource(importlib.import_module(module))
    calls = re.findall(r"load_project_memories\((.*?)\n\s*\)", src, flags=re.S)
    assert calls, f"no load_project_memories call found in {module}"
    for args in calls:
        assert "organization_id" in args, f"{module} recall is not org-scoped"
