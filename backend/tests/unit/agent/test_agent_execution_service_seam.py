"""Compat-seam tests for the B5 extraction (jobs.py → agent_execution_service).

The implementation moved to ``src.services.agent.agent_execution_service``;
``src.api.agent.jobs`` stays behind as a plain re-export seam and
``src.api.agent.execute`` re-exports the wire schemas that moved to
``src.services.agent.schemas``. These tests pin that every legacy name still
resolves AND resolves to the *same object* as the canonical module — so a
drifted copy (shadow definition, stale duplicate) fails loudly.

Unlike the deleted #1151 shims, ``src.api.agent.jobs`` is NOT a ``sys.modules``
alias: patching the legacy path does not affect the service's runtime lookups.
That is intentional (in-repo callers/tests were repointed); the seam only has
to keep imports working.
"""

import importlib

import pytest

pytestmark = pytest.mark.unit

# Every name the legacy seam re-exports (mirror of src/api/agent/jobs.py).
_JOBS_SEAM_NAMES = [
    "MAX_JOBS",
    "_actor_fields",
    "_cleanup_jobs",
    "_clear_stale_pending_confirmation",
    "_coerce_citation_document_id",
    "_extract_pending_interrupt",
    "_get_job",
    "_get_latest_user_content",
    "_jobs",
    "_jobs_lock",
    "_latest_user_client_message_id",
    "_page_context_to_dict",
    "_persist_assistant_message",
    "_persist_assistant_message_safe",
    "_persist_user_message",
    "_persist_user_message_guarded",
    "_resolve_and_bind_project",
    "_resolve_project_for_thread",
    "_resolve_thread",
    "_resume_agent_graph",
    "_run_agent_graph",
    "_set_job",
    "_sum_message_usage",
    "build_graph_input_messages",
    "build_thread_seed_messages",
    "build_user_history_messages",
]

_SCHEMA_NAMES = [
    "SUPPORTED_MODELS",
    "AgentExecuteRequest",
    "AgentExecuteResponse",
    "AgentMessage",
    "PageContextRequest",
    "RetrievedContextResponse",
    "ToolExecutionResponse",
]


def test_jobs_seam_reexports_service_objects():
    legacy = importlib.import_module("src.api.agent.jobs")
    canonical = importlib.import_module("src.services.agent.agent_execution_service")
    for name in _JOBS_SEAM_NAMES:
        assert getattr(legacy, name) is getattr(canonical, name), (
            f"src.api.agent.jobs.{name} is not the canonical "
            f"agent_execution_service object — the seam drifted"
        )


def test_execute_reexports_service_schemas():
    execute = importlib.import_module("src.api.agent.execute")
    schemas = importlib.import_module("src.services.agent.schemas")
    for name in _SCHEMA_NAMES:
        assert getattr(execute, name) is getattr(schemas, name), (
            f"src.api.agent.execute.{name} is not the canonical "
            f"src.services.agent.schemas object — the re-export drifted"
        )


def test_execute_reexports_canonical_tools():
    """The #1151 api shims are gone; execute must re-export the service tools."""
    execute = importlib.import_module("src.api.agent.execute")
    tools_impl = importlib.import_module("src.services.agent.tools_impl")
    for name in ("AGENT_TOOLS", "execute_tool", "_tool_search_documents"):
        assert getattr(execute, name) is getattr(tools_impl, name)


def test_api_shim_modules_are_deleted():
    """The legacy shim import paths must no longer resolve (audit C4-fold)."""
    for legacy_path in ("src.api.agent.tools_impl", "src.api.agent.tool_helpers"):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(legacy_path)


def test_graph_runner_lives_in_service_layer():
    canonical = importlib.import_module("src.services.agent.agent_execution_service")
    assert canonical._run_agent_graph.__module__ == (
        "src.services.agent.agent_execution_service"
    )
    assert canonical._resume_agent_graph.__module__ == (
        "src.services.agent.agent_execution_service"
    )
