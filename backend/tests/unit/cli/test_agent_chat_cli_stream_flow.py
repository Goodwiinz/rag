from __future__ import annotations

from pathlib import Path
import builtins
from collections.abc import AsyncIterator
import runpy
import sys
from types import SimpleNamespace
from uuid import UUID

import pytest


@pytest.mark.asyncio
async def test_run_turn_updates_trace_and_resumes_confirmation_flow() -> None:
    from src.cli import agent_chat_cli as cli
    from src.cli.types import CLIEvent, CLISessionState

    captured_request_body: dict[str, object] = {}
    stream_confirm_calls: list[dict[str, object]] = []
    rendered_output: list[str] = []

    async def stream_message(request_body: dict[str, object]) -> AsyncIterator[CLIEvent]:
        captured_request_body.update(request_body)
        yield CLIEvent(
            type="trace",
            data={
                "thread_id": "thread-1",
                "cli_session_id": "cli-1",
                "langsmith_run_id": "run-1",
            },
        )
        yield CLIEvent(type="token", data={"content": "Hello"})
        yield CLIEvent(
            type="confirmation",
            data={
                "thread_id": "thread-1",
                "confirmation": {"message": "Continue?"},
            },
        )

    async def stream_confirm(*, thread_id: str, confirmed: bool) -> AsyncIterator[CLIEvent]:
        stream_confirm_calls.append(
            {"thread_id": thread_id, "confirmed": confirmed}
        )
        yield CLIEvent(
            type="trace",
            data={
                "thread_id": thread_id,
                "cli_session_id": "cli-2",
                "langsmith_run_id": "run-2",
            },
        )
        yield CLIEvent(type="token", data={"content": "Resumed"})

    def output_hook(text: str) -> None:
        rendered_output.append(text)

    def input_hook(_: str) -> str:
        return "y"

    initial_state = CLISessionState(
        page_context={
            "type": "project",
            "project_id": "proj-123",
            "project_name": "Atlas",
        }
    )

    new_state = await cli.run_turn(
        initial_state,
        "summarize the project",
        stream_message=stream_message,
        stream_confirm=stream_confirm,
        input_hook=input_hook,
        output_hook=output_hook,
    )

    sent_messages = captured_request_body["messages"]
    assert len(sent_messages) == 1
    sent_msg = sent_messages[0]
    assert sent_msg["role"] == "user"
    assert sent_msg["content"] == "summarize the project"
    UUID(sent_msg["client_message_id"])
    assert captured_request_body["use_rag"] is True
    assert captured_request_body["page_context"] == {
        "type": "project",
        "project_id": "proj-123",
        "project_name": "Atlas",
    }
    assert stream_confirm_calls == [{"thread_id": "thread-1", "confirmed": True}]
    assert new_state.thread_id == "thread-1"
    assert new_state.cli_session_id == "cli-2"
    assert new_state.latest_trace == {
        "thread_id": "thread-1",
        "cli_session_id": "cli-2",
        "langsmith_run_id": "run-2",
    }
    assert initial_state.thread_id == ""
    assert initial_state.latest_trace == {}
    assert any("trace>" in text for text in rendered_output)
    assert any(text == "Hello" for text in rendered_output)
    assert any("confirmation>" in text for text in rendered_output)
    assert any(text == "Resumed" for text in rendered_output)


@pytest.mark.asyncio
async def test_run_turn_repompts_after_invalid_confirmation_input() -> None:
    from src.cli import agent_chat_cli as cli
    from src.cli.types import CLIEvent, CLISessionState

    prompts: list[str] = []
    stream_confirm_calls: list[dict[str, object]] = []

    async def stream_message(_: dict[str, object]) -> AsyncIterator[CLIEvent]:
        yield CLIEvent(
            type="confirmation",
            data={"thread_id": "thread-9", "confirmation": {"message": "Proceed?"}},
        )

    async def stream_confirm(*, thread_id: str, confirmed: bool) -> AsyncIterator[CLIEvent]:
        stream_confirm_calls.append(
            {"thread_id": thread_id, "confirmed": confirmed}
        )
        yield CLIEvent(type="token", data={"content": "ok"})

    answers = iter(["maybe", "n"])

    def input_hook(prompt: str) -> str:
        prompts.append(prompt)
        return next(answers)

    state = await cli.run_turn(
        CLISessionState(),
        "check the confirmation path",
        stream_message=stream_message,
        stream_confirm=stream_confirm,
        input_hook=input_hook,
        output_hook=lambda _: None,
    )

    assert prompts == ["confirm> ", "confirm> "]
    assert stream_confirm_calls == [{"thread_id": "thread-9", "confirmed": False}]
    assert state.thread_id == ""


@pytest.mark.asyncio
async def test_run_turn_streams_default_token_output_on_one_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from src.cli import agent_chat_cli as cli
    from src.cli.types import CLIEvent, CLISessionState

    async def stream_message(_: dict[str, object]) -> AsyncIterator[CLIEvent]:
        yield CLIEvent(type="token", data={"content": "Hel"})
        yield CLIEvent(type="token", data={"content": "lo"})

    state = await cli.run_turn(
        CLISessionState(),
        "say hello",
        stream_message=stream_message,
    )

    assert state.thread_id == ""
    assert capsys.readouterr().out == "agent> Hello\n"


def test_build_request_body_defaults_page_context_to_unknown() -> None:
    from src.cli.agent_chat_cli import build_request_body
    from src.cli.types import CLISessionState

    request_body = build_request_body(CLISessionState(page_context={}), "hello")

    assert request_body["page_context"] == {"type": "unknown"}
    assert request_body["use_rag"] is True


def test_build_request_body_normalizes_general_page_context_to_unknown() -> None:
    from src.cli.agent_chat_cli import build_request_body
    from src.cli.types import CLISessionState

    request_body = build_request_body(
        CLISessionState(page_context={"type": "general"}),
        "hello",
    )

    assert request_body["page_context"] == {"type": "unknown"}


@pytest.mark.parametrize("error_type", [EOFError, KeyboardInterrupt])
@pytest.mark.asyncio
async def test_async_main_exits_cleanly_on_terminal_interrupt(
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[BaseException],
) -> None:
    from src.cli import agent_chat_cli as cli

    class FakeAgentAPIClient:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs
            self.closed = False

        async def aclose(self) -> None:
            self.closed = True

    fake_client = FakeAgentAPIClient()
    monkeypatch.setattr(cli, "AgentAPIClient", lambda **kwargs: fake_client)

    def input_hook(_: str) -> str:
        raise error_type()

    exit_code = await cli.async_main(
        base_url="https://example.test",
        input_hook=input_hook,
        output_hook=lambda _: None,
    )

    assert exit_code == 0
    assert fake_client.closed is True


@pytest.mark.asyncio
async def test_async_main_uses_nous_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.cli import agent_chat_cli as cli

    prompts: list[str] = []

    class FakeAgentAPIClient:
        async def aclose(self) -> None:
            pass

    monkeypatch.setattr(cli, "AgentAPIClient", lambda **kwargs: FakeAgentAPIClient())

    def input_hook(prompt: str) -> str:
        prompts.append(prompt)
        raise EOFError()

    exit_code = await cli.async_main(
        base_url="https://example.test",
        input_hook=input_hook,
        output_hook=lambda _: None,
    )

    assert exit_code == 0
    assert prompts == ["nous> "]


@pytest.mark.asyncio
async def test_async_main_login_command_updates_auth_and_continues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.cli import agent_chat_cli as cli
    from src.cli.types import CLIEvent

    stream_bodies: list[dict[str, object]] = []
    updated_auth: list[tuple[str, str]] = []

    class FakeAgentAPIClient:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

        def update_auth(self, token: str, organization_id: str) -> None:
            updated_auth.append((token, organization_id))

        async def stream_message(
            self, request_body: dict[str, object]
        ) -> AsyncIterator[CLIEvent]:
            stream_bodies.append(request_body)
            yield CLIEvent(type="token", data={"content": "ok"})

        async def stream_confirm(self, **kwargs: object) -> AsyncIterator[CLIEvent]:
            if False:
                yield CLIEvent(type="token", data={"content": ""})
            return

        async def aclose(self) -> None:
            return None

    async def fake_login_via_browser(**kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(token="cli-token", organization_id="org-1")

    monkeypatch.setattr(cli, "AgentAPIClient", lambda **kwargs: FakeAgentAPIClient(**kwargs))
    monkeypatch.setattr(cli, "login_via_browser", fake_login_via_browser)

    inputs = iter(["/login", "summarize my projects"])

    def input_hook(_: str) -> str:
        try:
            return next(inputs)
        except StopIteration as exc:
            raise EOFError() from exc

    exit_code = await cli.async_main(
        base_url="https://example.test",
        input_hook=input_hook,
        output_hook=lambda _: None,
    )

    assert exit_code == 0
    assert updated_auth == [("cli-token", "org-1")]
    sent_messages = stream_bodies[0]["messages"]
    assert len(sent_messages) == 1
    sent_msg = sent_messages[0]
    assert sent_msg["role"] == "user"
    assert sent_msg["content"] == "summarize my projects"
    UUID(sent_msg["client_message_id"])


@pytest.mark.asyncio
async def test_async_main_prints_friendly_auth_errors_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.cli import agent_chat_cli as cli
    from src.cli.agent_api_client import AgentAPIClientError

    outputs: list[str] = []

    class FakeAgentAPIClient:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

        async def stream_message(self, _: dict[str, object]) -> AsyncIterator[object]:
            raise AgentAPIClientError("auth> backend rejected credentials. Run /login.", 403)
            yield  # pragma: no cover

        async def stream_confirm(self, **kwargs: object) -> AsyncIterator[object]:
            if False:
                yield kwargs  # pragma: no cover

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(cli, "AgentAPIClient", lambda **kwargs: FakeAgentAPIClient())

    answers = iter(["summarize projects"])

    def input_hook(_: str) -> str:
        try:
            return next(answers)
        except StopIteration as exc:
            raise EOFError() from exc

    exit_code = await cli.async_main(
        base_url="https://example.test",
        input_hook=input_hook,
        output_hook=outputs.append,
    )

    assert exit_code == 0
    assert any("run /login" in line.lower() for line in outputs)


def test_nous_launcher_script_exists_and_targets_cli_module() -> None:
    launcher = (
        Path(__file__).resolve().parents[3] / "nous"
    )

    assert launcher.exists()
    content = launcher.read_text()
    assert "src.cli.agent_chat_cli" in content


def test_main_launch_path_handles_slash_commands_without_name_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import src.cli.agent_api_client as api_client_module

    class FakeAgentAPIClient:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

        async def aclose(self) -> None:
            pass

    monkeypatch.setattr(api_client_module, "AgentAPIClient", FakeAgentAPIClient)
    answers = iter(["/help", "/quit"])

    def fake_input(prompt: str = "") -> str:
        return next(answers)

    monkeypatch.setattr(builtins, "input", fake_input)
    monkeypatch.delitem(sys.modules, "src.cli.agent_chat_cli", raising=False)
    monkeypatch.setattr(sys, "argv", ["python"])

    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("src.cli.agent_chat_cli", run_name="__main__")

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert "Commands:" in output
    assert "Quit requested." in output


def test_main_parses_cli_flags_and_invokes_async_main(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.cli import agent_chat_cli as cli

    captured: dict[str, object] = {}

    async def fake_async_main(**kwargs: object) -> int:
        captured.update(kwargs)
        return 17

    monkeypatch.setattr(cli, "async_main", fake_async_main)

    exit_code = cli.main(
        [
            "--base-url",
            "https://example.test",
            "--token",
            "tok",
            "--org-id",
            "org-1",
            "--project-id",
            "proj-9",
            "--debug",
        ]
    )

    assert exit_code == 17
    assert captured == {
        "base_url": "https://example.test",
        "token": "tok",
        "organization_id": "org-1",
        "auth_file": "",
        "project_id": "proj-9",
        "debug": True,
    }
