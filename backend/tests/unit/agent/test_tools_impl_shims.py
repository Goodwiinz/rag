"""Legacy agent tool import paths must keep working after the B1 move.

``tools_impl.py`` and ``tool_helpers.py`` moved from ``src/api/agent/`` to
``src/services/agent/`` (audit finding B1). Shims at the old paths alias the
legacy module names to the canonical service modules via a ``sys.modules``
swap, so:

- ``from src.api.agent.tools_impl import X`` still resolves, and
- ``mock.patch("src.api.agent.tools_impl.X")`` still patches the namespace
  the implementations execute in (module identity, not a copy).

These tests pin that contract for the callers that must not change in this
PR (``execute.py`` / ``jobs.py``, owned by an in-flight PR) and for the
existing test suite's patch targets.
"""

import importlib
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit


def test_legacy_tools_impl_path_is_the_canonical_module() -> None:
    legacy = importlib.import_module("src.api.agent.tools_impl")
    canonical = importlib.import_module("src.services.agent.tools_impl")
    assert legacy is canonical


def test_legacy_tool_helpers_path_is_the_canonical_module() -> None:
    legacy = importlib.import_module("src.api.agent.tool_helpers")
    canonical = importlib.import_module("src.services.agent.tool_helpers")
    assert legacy is canonical


def test_legacy_from_imports_yield_identical_objects() -> None:
    from src.api.agent.tool_helpers import (
        _resolve_document_id as legacy_resolve_document_id,
    )
    from src.api.agent.tools_impl import AGENT_TOOLS as legacy_agent_tools
    from src.api.agent.tools_impl import (
        _tool_search_documents as legacy_search_documents,
    )
    from src.api.agent.tools_impl import execute_tool as legacy_execute_tool
    from src.services.agent import tool_helpers, tools_impl

    assert legacy_agent_tools is tools_impl.AGENT_TOOLS
    assert legacy_execute_tool is tools_impl.execute_tool
    assert legacy_search_documents is tools_impl._tool_search_documents
    assert legacy_resolve_document_id is tool_helpers._resolve_document_id


def test_moved_functions_live_in_the_service_namespace() -> None:
    """The implementations must execute in the services module, not the shim."""
    from src.services.agent import tools_impl

    assert tools_impl.execute_tool.__module__ == "src.services.agent.tools_impl"
    assert tools_impl._tool_search_documents.__globals__ is vars(
        tools_impl
    ), "tool impls must resolve globals against the canonical service module"


def test_patching_legacy_path_patches_canonical_module() -> None:
    """mock.patch on the old dotted path must affect the real module.

    Several existing tests patch ``src.api.agent.tools_impl.<name>``; if the
    shim were a plain re-export copy those patches would silently stop
    reaching the namespace the tool implementations read at call time.
    """
    from src.services.agent import tools_impl

    sentinel = object()
    with patch("src.api.agent.tools_impl._resolve_document_id", sentinel):
        assert tools_impl._resolve_document_id is sentinel
    assert tools_impl._resolve_document_id is not sentinel


def test_execute_module_reexports_canonical_objects() -> None:
    """execute.py (unchanged, PR #1141 territory) re-exports via the shim."""
    fastapi = pytest.importorskip("fastapi")  # noqa: F841 — execute.py needs it
    pytest.importorskip("langgraph")
    execute = importlib.import_module("src.api.agent.execute")
    from src.services.agent import tools_impl

    assert execute.execute_tool is tools_impl.execute_tool
    assert execute.AGENT_TOOLS is tools_impl.AGENT_TOOLS
    assert execute._tool_ingest_arxiv is tools_impl._tool_ingest_arxiv
