"""Backward-compatibility seam — implementation moved to the service layer.

The agent job runner (job-store access, thread resolution/project binding,
message persistence, server-side history seeding, dual-store divergence
guard, and the background graph runner) has no HTTP concerns; it lives in
``src.services.agent.agent_execution_service`` (audit findings B5 + C4-fold).

This module re-exports the legacy ``src.api.agent.jobs`` names so external
callers keep working, but it is a plain re-export — NOT a ``sys.modules``
alias. ``mock.patch("src.api.agent.jobs.<name>")`` only rebinds this module's
attribute and will NOT affect the service's runtime lookups; patch
``src.services.agent.agent_execution_service.<name>`` instead (every in-repo
caller and test has been repointed). New code must import from the service
module directly.
"""

from src.services.agent.agent_execution_service import (  # noqa: F401
    MAX_JOBS,
    _actor_fields,
    _chat_user_row_count,
    _checkpoint_human_count,
    _cleanup_jobs,
    _clear_stale_pending_confirmation,
    _coerce_citation_document_id,
    _delete_job_async,
    _detect_dualstore_divergence,
    _extract_pending_interrupt,
    _get_job,
    _get_job_async,
    _get_latest_user_content,
    _get_schemas,
    _jobs,
    _jobs_lock,
    _latest_user_client_message_id,
    _maybe_cleanup_jobs,
    _newest_user_message,
    _page_context_to_dict,
    _persist_assistant_message,
    _persist_assistant_message_safe,
    _persist_user_message,
    _persist_user_message_guarded,
    _resolve_and_bind_project,
    _resolve_project_for_thread,
    _resolve_thread,
    _resume_agent_graph,
    _run_agent_graph,
    _seed_has_id,
    _seed_message_id,
    _set_job,
    _set_job_async,
    _should_check_divergence,
    _sum_message_usage,
    build_graph_input_messages,
    build_thread_seed_messages,
    build_user_history_messages,
)
