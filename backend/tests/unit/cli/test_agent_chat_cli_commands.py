from __future__ import annotations


def test_clisessionstate_defaults_to_valid_baseline() -> None:
    from src.cli.types import CLISessionState

    state = CLISessionState()

    assert state.thread_id == ""
    assert state.cli_session_id == ""
    assert state.debug is False
    assert state.page_context == {"type": "unknown"}
    assert state.latest_trace == {}
    assert state.should_quit is False
    assert state.model == ""


def test_apply_command_help_returns_available_commands() -> None:
    from src.cli.agent_chat_cli import apply_command
    from src.cli.types import CLISessionState

    state = CLISessionState()

    new_state, output = apply_command(state, "/help")

    assert new_state == state
    assert "/new" in output
    assert "/context project <id>" in output
    assert "/model" in output
    assert "/quit" in output


def test_apply_command_new_resets_thread_and_trace() -> None:
    from src.cli.agent_chat_cli import apply_command
    from src.cli.types import CLISessionState

    state = CLISessionState(
        thread_id="thread-1",
        cli_session_id="cli-1",
        debug=False,
        page_context={"type": "project", "project_id": "proj-1"},
        latest_trace={"thread_id": "thread-1", "cli_session_id": "cli-1"},
    )

    new_state, output = apply_command(state, "/new")

    assert new_state.thread_id == ""
    assert new_state.cli_session_id == "cli-1"
    assert new_state.page_context == {"type": "project", "project_id": "proj-1"}
    assert new_state.latest_trace == {}
    assert "new thread" in output.lower()


def test_apply_command_thread_without_args_reports_current_thread() -> None:
    from src.cli.agent_chat_cli import apply_command
    from src.cli.types import CLISessionState

    state = CLISessionState(thread_id="thread-9")

    new_state, output = apply_command(state, "/thread")

    assert new_state == state
    assert "thread-9" in output


def test_apply_command_thread_sets_active_thread() -> None:
    from src.cli.agent_chat_cli import apply_command
    from src.cli.types import CLISessionState

    state = CLISessionState()

    new_state, output = apply_command(state, "/thread thread-9")

    assert new_state.thread_id == "thread-9"
    assert "thread-9" in output


def test_apply_command_status_summarizes_current_state() -> None:
    from src.cli.agent_chat_cli import apply_command
    from src.cli.types import CLISessionState

    state = CLISessionState(
        thread_id="thread-1",
        cli_session_id="cli-1",
        debug=True,
        page_context={"type": "project", "project_id": "proj-7"},
        latest_trace={"thread_id": "thread-1", "langsmith_run_id": "run-1"},
    )

    new_state, output = apply_command(state, "/status")

    assert new_state == state
    assert "thread-1" in output
    assert "cli-1" in output
    assert "debug=on" in output
    assert "proj-7" in output
    assert "run-1" in output


def test_apply_command_context_project_sets_project_context() -> None:
    from src.cli.agent_chat_cli import apply_command
    from src.cli.types import CLISessionState

    state = CLISessionState(
        latest_trace={"thread_id": "thread-old", "langsmith_run_id": "run-old"}
    )

    new_state, output = apply_command(state, "/context project proj-7")

    assert new_state.page_context == {"type": "project", "project_id": "proj-7"}
    assert "proj-7" in output


def test_apply_command_transitions_use_fresh_nested_dicts() -> None:
    from src.cli.agent_chat_cli import apply_command
    from src.cli.types import CLISessionState

    state = CLISessionState(
        page_context={"type": "project", "project_id": "proj-old"},
        latest_trace={"thread_id": "thread-old", "langsmith_run_id": "run-old"},
    )

    new_state, _ = apply_command(state, "/context project proj-7")

    assert new_state.page_context is not state.page_context
    assert new_state.latest_trace is not state.latest_trace

    new_state.page_context["project_id"] = "proj-mutated"
    new_state.latest_trace["langsmith_run_id"] = "run-mutated"

    assert state.page_context == {"type": "project", "project_id": "proj-old"}
    assert state.latest_trace == {
        "thread_id": "thread-old",
        "langsmith_run_id": "run-old",
    }


def test_apply_command_transitions_deep_copy_nested_mappings() -> None:
    from src.cli.agent_chat_cli import apply_command
    from src.cli.types import CLISessionState

    state = CLISessionState(
        page_context={
            "type": "project",
            "project_id": "p1",
            "metadata": {"tab": "docs"},
        },
        latest_trace={
            "thread_id": "thread-1",
            "langsmith_run_id": "run-1",
            "metadata": {"phase": "stream"},
        },
    )

    new_state, _ = apply_command(state, "/debug on")

    assert new_state.page_context is not state.page_context
    assert new_state.latest_trace is not state.latest_trace
    assert new_state.page_context["metadata"] is not state.page_context["metadata"]
    assert new_state.latest_trace["metadata"] is not state.latest_trace["metadata"]

    new_state.page_context["metadata"]["tab"] = "code"
    new_state.latest_trace["metadata"]["phase"] = "done"

    assert state.page_context["metadata"] == {"tab": "docs"}
    assert state.latest_trace["metadata"] == {"phase": "stream"}


def test_apply_command_context_clear_resets_page_context() -> None:
    from src.cli.agent_chat_cli import apply_command
    from src.cli.types import CLISessionState

    state = CLISessionState(
        thread_id="thread-1",
        cli_session_id="cli-1",
        debug=False,
        page_context={"type": "project", "project_id": "proj-7"},
        latest_trace={},
    )

    new_state, output = apply_command(state, "/context clear")

    assert new_state.page_context == {"type": "unknown"}
    assert "cleared" in output.lower()


def test_apply_command_debug_toggles_debug_flag() -> None:
    from src.cli.agent_chat_cli import apply_command
    from src.cli.types import CLISessionState

    state = CLISessionState()

    debug_on_state, output_on = apply_command(state, "/debug on")
    debug_off_state, output_off = apply_command(debug_on_state, "/debug off")

    assert debug_on_state.debug is True
    assert "enabled" in output_on.lower()
    assert debug_off_state.debug is False
    assert "disabled" in output_off.lower()


def test_apply_command_thread_switch_clears_latest_trace() -> None:
    from src.cli.agent_chat_cli import apply_command
    from src.cli.types import CLISessionState

    state = CLISessionState(
        thread_id="thread-old",
        latest_trace={"thread_id": "thread-old", "langsmith_run_id": "run-old"},
    )

    new_state, output = apply_command(state, "/thread thread-new")

    assert new_state.thread_id == "thread-new"
    assert new_state.latest_trace == {}
    assert "thread-new" in output


def test_apply_command_model_without_args_reports_server_default() -> None:
    from src.cli.agent_chat_cli import apply_command
    from src.cli.types import CLISessionState

    state = CLISessionState()

    new_state, output = apply_command(state, "/model")

    assert new_state == state
    assert "(server default)" in output


def test_apply_command_model_without_args_reports_current_model() -> None:
    from src.cli.agent_chat_cli import apply_command
    from src.cli.types import CLISessionState

    state = CLISessionState(model="gpt-4o")

    new_state, output = apply_command(state, "/model")

    assert new_state == state
    assert "gpt-4o" in output


def test_apply_command_model_sets_known_model_without_warning() -> None:
    from src.cli.agent_chat_cli import apply_command
    from src.cli.types import CLISessionState

    state = CLISessionState()

    new_state, output = apply_command(state, "/model gpt-4o-mini")

    assert new_state.model == "gpt-4o-mini"
    assert "gpt-4o-mini" in output
    assert "may reject" not in output


def test_apply_command_model_accepts_claude_sonnet_without_warning() -> None:
    from src.cli.agent_chat_cli import apply_command
    from src.cli.types import CLISessionState

    state = CLISessionState()

    new_state, output = apply_command(state, "/model claude-sonnet-4-5")

    assert new_state.model == "claude-sonnet-4-5"
    assert "claude-sonnet-4-5" in output
    assert "may reject" not in output


def test_apply_command_model_warns_on_unrecognized_model() -> None:
    from src.cli.agent_chat_cli import apply_command
    from src.cli.types import CLISessionState

    state = CLISessionState()

    new_state, output = apply_command(state, "/model claude-opus-4-7")

    assert new_state.model == "claude-opus-4-7"
    assert "may reject" in output


def test_apply_command_model_clear_resets_to_server_default() -> None:
    from src.cli.agent_chat_cli import apply_command
    from src.cli.types import CLISessionState

    state = CLISessionState(model="gpt-4o-mini")

    new_state, output = apply_command(state, "/model clear")

    assert new_state.model == ""
    assert "default" in output.lower()


def test_apply_command_model_too_many_args_returns_usage_error() -> None:
    from src.cli.agent_chat_cli import apply_command
    from src.cli.types import CLISessionState

    state = CLISessionState()

    new_state, output = apply_command(state, "/model gpt-4o extra")

    assert new_state == state
    assert "Usage error" in output


def test_status_includes_model_line() -> None:
    from src.cli.agent_chat_cli import apply_command
    from src.cli.types import CLISessionState

    state = CLISessionState(model="gpt-4o-mini")

    _, output = apply_command(state, "/status")

    assert "model: gpt-4o-mini" in output


def test_build_request_body_includes_model_when_set() -> None:
    from src.cli.agent_chat_cli import build_request_body
    from src.cli.types import CLISessionState

    state = CLISessionState(model="gpt-4o-mini")

    body = build_request_body(state, "hello")

    assert body["model"] == "gpt-4o-mini"


def test_build_request_body_omits_model_when_unset() -> None:
    from src.cli.agent_chat_cli import build_request_body
    from src.cli.types import CLISessionState

    state = CLISessionState()

    body = build_request_body(state, "hello")

    assert "model" not in body


def test_apply_command_quit_sets_exit_signal() -> None:
    from src.cli.agent_chat_cli import apply_command
    from src.cli.types import CLISessionState

    state = CLISessionState()

    new_state, output = apply_command(state, "/quit")

    assert new_state.should_quit is True
    assert "quit" in output.lower()
