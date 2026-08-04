"""Bounded, allow-listed metadata for root LangSmith traces."""

import pytest

from src.services.agent.trace_metadata import TraceSource, build_trace_metadata

pytestmark = pytest.mark.unit


def test_build_trace_metadata_emits_all_identifiers_and_release_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GIT_SHA", "sha-123")
    monkeypatch.setenv("APP_VERSION", "fallback-version")
    monkeypatch.setenv("IMAGE_TAG", "backend-456")

    assert build_trace_metadata(
        trace_source=TraceSource.GRAPH,
        user_id="user-1",
        org_id="org-1",
        thread_id="thread-1",
        request_id="request-1",
        agent_run_id="run-1",
        user_message_id="message-1",
        client_message_id="client-1",
    ) == {
        "trace_source": "graph",
        "user_id": "user-1",
        "org_id": "org-1",
        "thread_id": "thread-1",
        "request_id": "request-1",
        "agent_run_id": "run-1",
        "user_message_id": "message-1",
        "client_message_id": "client-1",
        "deployment_sha": "sha-123",
        "image_tag": "backend-456",
    }


def test_build_trace_metadata_falls_back_to_app_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GIT_SHA", raising=False)
    monkeypatch.setenv("APP_VERSION", "app-version-789")
    monkeypatch.delenv("IMAGE_TAG", raising=False)

    assert (
        build_trace_metadata(trace_source=TraceSource.GRAPH)["deployment_sha"]
        == "app-version-789"
    )


def test_build_trace_metadata_whitespace_git_sha_falls_back_to_stripped_app_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GIT_SHA", "   \t")
    monkeypatch.setenv("APP_VERSION", "  app-version-789  ")

    assert (
        build_trace_metadata(trace_source=TraceSource.GRAPH)["deployment_sha"]
        == "app-version-789"
    )


def test_build_trace_metadata_omits_missing_and_empty_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("GIT_SHA", "APP_VERSION", "IMAGE_TAG"):
        monkeypatch.delenv(name, raising=False)

    metadata = build_trace_metadata(
        trace_source=TraceSource.GRAPH,
        user_id=None,
        org_id="",
        thread_id=None,
        request_id="request-1",
        agent_run_id=None,
        user_message_id=None,
        client_message_id=None,
    )

    assert metadata == {"trace_source": "graph", "request_id": "request-1"}
    assert "None" not in metadata.values()


def test_build_trace_metadata_bounds_every_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GIT_SHA", "s" * 200)
    monkeypatch.setenv("IMAGE_TAG", "i" * 200)

    metadata = build_trace_metadata(
        trace_source=TraceSource.GRAPH,
        user_id="u" * 200,
        org_id="o" * 200,
        thread_id="t" * 200,
        request_id="q" * 200,
        agent_run_id="r" * 200,
        user_message_id="m" * 200,
        client_message_id="c" * 200,
    )

    assert metadata
    assert metadata["trace_source"] == TraceSource.GRAPH.value
    assert all(
        len(value) == 128 for key, value in metadata.items() if key != "trace_source"
    )


def test_build_trace_metadata_rejects_unknown_fields() -> None:
    with pytest.raises(TypeError):
        build_trace_metadata(  # type: ignore[call-arg]
            trace_source=TraceSource.GRAPH,
            prompt="must never enter trace metadata",
        )
