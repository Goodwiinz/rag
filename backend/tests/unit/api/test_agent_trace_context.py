from src.api.agent.trace_context import build_trace_payload
from src.services.agent.observability import get_langsmith_base_url


def test_build_trace_payload_includes_ids_and_optional_url() -> None:
    payload = build_trace_payload(
        thread_id="thread-1",
        cli_session_id="cli-1",
        langsmith_run_id="run-1",
    )

    assert payload["thread_id"] == "thread-1"
    assert payload["cli_session_id"] == "cli-1"
    assert payload["langsmith_run_id"] == "run-1"
    assert payload["langsmith_url"] == ""


def test_get_langsmith_base_url_prefers_environment_override(
    monkeypatch,
) -> None:
    monkeypatch.setenv("LANGCHAIN_ENDPOINT", "https://smith.example.com")

    assert get_langsmith_base_url() == "https://smith.example.com"
