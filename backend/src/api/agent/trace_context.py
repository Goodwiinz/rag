"""Helpers for surfacing agent trace metadata to CLI and streaming clients."""

from __future__ import annotations


def build_trace_payload(
    *,
    thread_id: str,
    cli_session_id: str,
    langsmith_run_id: str = "",
) -> dict:
    """Build a compact trace payload for SSE and CLI consumers."""
    return {
        "thread_id": thread_id,
        "cli_session_id": cli_session_id,
        "langsmith_run_id": langsmith_run_id,
        "langsmith_url": "",
    }
