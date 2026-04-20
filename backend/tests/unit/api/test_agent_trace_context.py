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


def test_configure_langsmith_accepts_langsmith_prefixed_env(monkeypatch) -> None:
    from src.services.agent.observability import configure_langsmith

    for key in (
        "LANGSMITH_API_KEY",
        "LANGCHAIN_API_KEY",
        "LANGSMITH_TRACING",
        "LANGCHAIN_TRACING_V2",
        "LANGSMITH_PROJECT",
        "LANGCHAIN_PROJECT",
    ):
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv("LANGSMITH_API_KEY", "lsv2_test_key")
    monkeypatch.setenv("LANGSMITH_PROJECT", "custom-project")

    configure_langsmith()

    import os

    assert os.environ["LANGCHAIN_API_KEY"] == "lsv2_test_key"
    assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGCHAIN_PROJECT"] == "custom-project"


def test_configure_langsmith_noop_without_api_key(monkeypatch) -> None:
    from src.services.agent.observability import configure_langsmith

    for key in (
        "LANGSMITH_API_KEY",
        "LANGCHAIN_API_KEY",
        "LANGSMITH_TRACING",
        "LANGCHAIN_TRACING_V2",
    ):
        monkeypatch.delenv(key, raising=False)

    configure_langsmith()

    import os

    assert "LANGCHAIN_TRACING_V2" not in os.environ
    assert "LANGSMITH_TRACING" not in os.environ
