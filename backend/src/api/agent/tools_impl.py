"""Backward-compatibility shim — implementation moved to the service layer.

Agent tool implementations have no HTTP concerns; they now live in
``src.services.agent.tools_impl`` (audit finding B1). This module keeps the
legacy ``src.api.agent.tools_impl`` import path working for callers that
still reference it (notably ``execute.py``).

The ``sys.modules`` self-replacement at the bottom makes the legacy path
*identical* to the canonical module
(``src.api.agent.tools_impl is src.services.agent.tools_impl``), so
``unittest.mock.patch("src.api.agent.tools_impl.<name>")`` in existing tests
still patches the namespace the implementations actually execute in. The
explicit re-imports exist for static analysis (mypy/IDEs), which does not
model the ``sys.modules`` swap; ``__getattr__`` covers direct
``spec_from_file_location`` loads that keep a reference to this stub module
object (see ``tests/unit/services/test_sandbox.py``).

New code must import from ``src.services.agent.tools_impl`` directly.
"""

import sys
from typing import Any

from src.services.agent import tools_impl as _impl
from src.services.agent.tools_impl import (  # noqa: F401
    AGENT_TOOLS,
    _citations_from_documents,
    _sanitize_arxiv_query,
    _tool_add_document_to_project,
    _tool_compare_documents,
    _tool_create_draft,
    _tool_create_project,
    _tool_create_project_note,
    _tool_do_kb_retrieve,
    _tool_execute_code,
    _tool_explore_entity_neighborhood,
    _tool_export_bibliography,
    _tool_extract_entities,
    _tool_find_entity_paths,
    _tool_forget_memory,
    _tool_get_graph_stats,
    _tool_ingest_arxiv,
    _tool_list_external_databases,
    _tool_list_project_documents,
    _tool_list_projects,
    _tool_search_arxiv,
    _tool_search_documents,
    _tool_search_external_database,
    _tool_search_knowledge_graph,
    _tool_summarize_document,
    execute_tool,
)


def __getattr__(name: str) -> Any:  # pragma: no cover — normal imports bypass this
    return getattr(_impl, name)


# Alias the legacy module path to the canonical module. The import system
# re-reads sys.modules after executing a module, so importers (and
# mock.patch target resolution) receive the canonical module object.
sys.modules[__name__] = _impl
