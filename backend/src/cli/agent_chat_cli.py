from __future__ import annotations

import argparse
import asyncio
import inspect
import sys
import uuid
from collections.abc import AsyncIterator, Callable
from copy import deepcopy
from dataclasses import replace
from typing import Any

from src.cli.agent_api_client import AgentAPIClient
from src.cli.agent_api_client import AgentAPIClientError
from src.cli.auth_loader import resolve_cli_auth
from src.cli.browser_auth import login_via_browser
from src.cli.agent_cli_renderer import render_event
from src.cli.types import CLIEvent
from src.cli.types import CLISessionState

HELP_TEXT = "\n".join(
    [
        "Commands:",
        "  /help                 Show this help.",
        "  /login                Sign in via the browser.",
        "  /new                  Start a new thread in this CLI session.",
        "  /thread [<id>]        Show or switch the active thread.",
        "  /status               Show current session state.",
        "  /context project <id> Set the active project context.",
        "  /context clear        Clear the active page context.",
        "  /debug on|off         Toggle debug output.",
        "  /quit                 Exit the CLI.",
    ]
)


def _format_page_context(page_context: dict[str, object]) -> str:
    context_type = str(page_context.get("type") or "unknown")
    if context_type == "project":
        project_id = str(page_context.get("project_id") or "")
        return f"project:{project_id}" if project_id else "project"
    return context_type


def _format_trace(latest_trace: dict[str, object]) -> str:
    if not latest_trace:
        return "none"

    parts: list[str] = []
    thread_id = str(latest_trace.get("thread_id") or "")
    cli_session_id = str(latest_trace.get("cli_session_id") or "")
    langsmith_run_id = str(latest_trace.get("langsmith_run_id") or "")

    if thread_id:
        parts.append(f"thread={thread_id}")
    if cli_session_id:
        parts.append(f"session={cli_session_id}")
    if langsmith_run_id:
        parts.append(f"run={langsmith_run_id}")

    return ", ".join(parts) if parts else "none"


def _status_text(state: CLISessionState) -> str:
    debug_text = "on" if state.debug else "off"
    return "\n".join(
        [
            "Session status:",
            f"  thread_id: {state.thread_id or '(empty)'}",
            f"  cli_session_id: {state.cli_session_id or '(empty)'}",
            f"  debug={debug_text}",
            f"  page_context: {_format_page_context(state.page_context)}",
            f"  latest_trace: {_format_trace(state.latest_trace)}",
            f"  quitting: {'yes' if state.should_quit else 'no'}",
        ]
    )


def _usage_text(command: str) -> str:
    return f"Usage error for {command}. Type /help for available commands."


def _clone_state_nested_data(state: CLISessionState) -> dict[str, dict[str, object]]:
    return {
        "page_context": deepcopy(state.page_context),
        "latest_trace": deepcopy(state.latest_trace),
    }


def _normalize_page_context(page_context: Any) -> dict[str, object]:
    if not isinstance(page_context, dict):
        return {"type": "unknown"}

    normalized = deepcopy(page_context)
    if normalized.get("type") != "project":
        normalized["type"] = "unknown"
    return normalized


def build_request_body(state: CLISessionState, prompt: str) -> dict[str, object]:
    request_body: dict[str, object] = {
        "messages": [{"role": "user", "content": prompt}],
        "page_context": _normalize_page_context(state.page_context),
        "use_rag": True,
    }
    if state.thread_id:
        request_body["thread_id"] = state.thread_id
    return request_body


def _parse_confirmation_input(user_input: str) -> bool:
    normalized = user_input.strip().lower()
    if normalized == "y":
        return True
    if normalized == "n":
        return False
    raise ValueError("Confirmation input must be 'y' or 'n'.")


async def handle_confirmation_event(
    confirmation_event: CLIEvent,
    resume_callback: Callable[..., AsyncIterator[CLIEvent] | object],
    user_input: str,
) -> AsyncIterator[CLIEvent]:
    thread_id = str(confirmation_event.data.get("thread_id") or "")
    if not thread_id:
        raise ValueError("Confirmation event is missing thread_id.")

    confirmed = _parse_confirmation_input(user_input)

    resumed = resume_callback(thread_id=thread_id, confirmed=confirmed)
    if inspect.isawaitable(resumed):
        resumed = await resumed

    if resumed is None:
        return

    if not hasattr(resumed, "__aiter__"):
        raise TypeError(
            "resume_callback must return None or an async iterator of CLIEvent"
        )

    async for event in resumed:
        yield event


async def run_turn(
    state: CLISessionState,
    prompt: str,
    *,
    stream_message: Callable[[dict[str, object]], AsyncIterator[CLIEvent] | object],
    stream_confirm: Callable[..., AsyncIterator[CLIEvent] | object] | None = None,
    input_hook: Callable[[str], str] = input,
    output_hook: Callable[[str], None] | None = None,
) -> CLISessionState:
    request_body = build_request_body(state, prompt)
    token_stream_open = False

    def emit_line(text: str) -> None:
        if output_hook is None:
            print(text)
            return
        output_hook(text)

    def emit_token(text: str) -> None:
        nonlocal token_stream_open
        if output_hook is None:
            if not token_stream_open:
                print("agent> ", end="", flush=True)
                token_stream_open = True
            print(text, end="", flush=True)
            return
        output_hook(text)

    def close_token_stream() -> None:
        nonlocal token_stream_open
        if token_stream_open and output_hook is None:
            print()
        token_stream_open = False

    async def process_event(event: CLIEvent) -> None:
        nonlocal state

        rendered = render_event(event, debug=state.debug)
        if event.type == "token":
            if rendered:
                emit_token(rendered)
        else:
            close_token_stream()
            if rendered:
                emit_line(rendered)

        if event.type == "trace":
            trace_data = deepcopy(event.data)
            thread_id = str(trace_data.get("thread_id") or state.thread_id)
            cli_session_id = str(trace_data.get("cli_session_id") or state.cli_session_id)
            state = replace(
                state,
                thread_id=thread_id,
                cli_session_id=cli_session_id,
                latest_trace=trace_data,
            )
            return

        if event.type == "confirmation":
            if stream_confirm is None:
                raise ValueError(
                    "stream_confirm is required to resume confirmation events."
                )

            while True:
                user_input = input_hook("confirm> ")
                try:
                    async for resumed_event in handle_confirmation_event(
                        event,
                        stream_confirm,
                        user_input,
                    ):
                        await process_event(resumed_event)
                    break
                except ValueError as exc:
                    if str(exc) != "Confirmation input must be 'y' or 'n'.":
                        raise
                    emit_line("Please enter y or n.")

    resumed_stream = stream_message(request_body)
    if inspect.isawaitable(resumed_stream):
        resumed_stream = await resumed_stream

    if not hasattr(resumed_stream, "__aiter__"):
        raise TypeError("stream_message must return an async iterator of CLIEvent")

    async for event in resumed_stream:
        await process_event(event)

    close_token_stream()
    return state


async def async_main(
    *,
    base_url: str,
    token: str = "",
    organization_id: str = "",
    auth_file: str = "",
    project_id: str = "",
    debug: bool = False,
    input_hook: Callable[[str], str] = input,
    output_hook: Callable[[str], None] | None = None,
) -> int:
    def emit_line(text: str) -> None:
        if output_hook is None:
            print(text)
            return
        output_hook(text)

    resolved_auth = resolve_cli_auth(
        token=token,
        organization_id=organization_id,
        auth_file=auth_file,
    )
    if resolved_auth.source_path is not None:
        emit_line(f"auth> loaded saved credentials from {resolved_auth.source_path}")

    client = AgentAPIClient(
        base_url=base_url,
        token=resolved_auth.token,
        organization_id=resolved_auth.organization_id,
    )

    state = CLISessionState(debug=debug, cli_session_id=uuid.uuid4().hex)
    if project_id:
        state = replace(
            state,
            page_context={"type": "project", "project_id": project_id},
        )
    if not resolved_auth.token:
        emit_line("auth> not signed in")
        emit_line("auth> run /login to connect this CLI")

    try:
        while not state.should_quit:
            try:
                raw_input = input_hook("nous> ")
            except (EOFError, KeyboardInterrupt):
                return 0
            if not raw_input.strip():
                continue

            if raw_input.strip().lower() == "/login":
                try:
                    login_result = await login_via_browser(
                        client=client,
                        output_hook=emit_line,
                    )
                except AgentAPIClientError as exc:
                    emit_line(str(exc))
                    continue
                if login_result is not None:
                    client.update_auth(
                        login_result.token,
                        login_result.organization_id,
                    )
                continue

            if raw_input.strip().startswith("/"):
                state, output = apply_command(state, raw_input)
                if output:
                    emit_line(output)
                continue

            try:
                state = await run_turn(
                    state,
                    raw_input,
                    stream_message=client.stream_message,
                    stream_confirm=client.stream_confirm,
                    input_hook=input_hook,
                    output_hook=output_hook,
                )
            except AgentAPIClientError as exc:
                emit_line(str(exc))

        return 0
    finally:
        await client.aclose()


async def login_main(
    *,
    base_url: str,
    token: str = "",
    organization_id: str = "",
    auth_file: str = "",
    output_hook: Callable[[str], None] | None = None,
) -> int:
    def emit_line(text: str) -> None:
        if output_hook is None:
            print(text)
            return
        output_hook(text)

    resolved_auth = resolve_cli_auth(
        token=token,
        organization_id=organization_id,
        auth_file=auth_file,
    )
    client = AgentAPIClient(
        base_url=base_url,
        token=resolved_auth.token,
        organization_id=resolved_auth.organization_id,
    )
    try:
        try:
            result = await login_via_browser(client=client, output_hook=emit_line)
        except AgentAPIClientError as exc:
            emit_line(str(exc))
            return 1
        if result is None:
            return 1
        client.update_auth(result.token, result.organization_id)
        return 0
    finally:
        await client.aclose()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interactive agent chat CLI")
    parser.add_argument(
        "command",
        nargs="?",
        choices=["login"],
        help="Optional CLI command.",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL for the agent API.",
    )
    parser.add_argument(
        "--token",
        default="",
        help="Bearer token for the agent API.",
    )
    parser.add_argument(
        "--org-id",
        default="",
        dest="organization_id",
        help="Organization ID for multi-tenant routing.",
    )
    parser.add_argument(
        "--auth-file",
        default="",
        help="Path to a saved NOUS CLI auth export. Defaults to ~/.nous/auth.json or the latest Downloads/nous-auth*.json export.",
    )
    parser.add_argument(
        "--project-id",
        default="",
        help="Initial project context for the session.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug rendering for streamed events.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "login":
        return asyncio.run(
            login_main(
                base_url=args.base_url,
                token=args.token,
                organization_id=args.organization_id,
                auth_file=args.auth_file,
            )
        )

    return asyncio.run(
        async_main(
            base_url=args.base_url,
            token=args.token,
            organization_id=args.organization_id,
            auth_file=args.auth_file,
            project_id=args.project_id,
            debug=args.debug,
        )
    )


def apply_command(state: CLISessionState, raw_input: str) -> tuple[CLISessionState, str]:
    text = raw_input.strip()
    if not text.startswith("/"):
        return state, ""

    parts = text.split()
    command = parts[0].lower()
    args = parts[1:]

    if command == "/help":
        return state, HELP_TEXT

    if command == "/new":
        nested = _clone_state_nested_data(state)
        return (
            replace(
                state,
                thread_id="",
                page_context=nested["page_context"],
                latest_trace={},
                should_quit=False,
            ),
            "Started a new thread for this CLI session.",
        )

    if command == "/thread":
        if not args:
            return state, f"Current thread: {state.thread_id or '(empty)'}."
        if len(args) != 1:
            return state, _usage_text("/thread [<id>]")
        nested = _clone_state_nested_data(state)
        return (
            replace(
                state,
                thread_id=args[0],
                page_context=nested["page_context"],
                latest_trace={},
                should_quit=False,
            ),
            f"Active thread set to {args[0]}.",
        )

    if command == "/status":
        return state, _status_text(state)

    if command == "/context":
        if len(args) == 2 and args[0].lower() == "project":
            project_id = args[1]
            nested = _clone_state_nested_data(state)
            nested["page_context"] = {"type": "project", "project_id": project_id}
            return (
                replace(
                    state,
                    page_context=nested["page_context"],
                    latest_trace=nested["latest_trace"],
                    should_quit=False,
                ),
                f"Project context set to {project_id}.",
            )
        if len(args) == 1 and args[0].lower() == "clear":
            nested = _clone_state_nested_data(state)
            nested["page_context"] = {"type": "unknown"}
            return (
                replace(
                    state,
                    page_context=nested["page_context"],
                    latest_trace=nested["latest_trace"],
                    should_quit=False,
                ),
                "Page context cleared.",
            )
        return state, _usage_text("/context project <id> | /context clear")

    if command == "/debug":
        if len(args) != 1:
            return state, _usage_text("/debug on | /debug off")
        setting = args[0].lower()
        if setting == "on":
            nested = _clone_state_nested_data(state)
            return (
                replace(
                    state,
                    debug=True,
                    page_context=nested["page_context"],
                    latest_trace=nested["latest_trace"],
                    should_quit=False,
                ),
                "Debug output enabled.",
            )
        if setting == "off":
            nested = _clone_state_nested_data(state)
            return (
                replace(
                    state,
                    debug=False,
                    page_context=nested["page_context"],
                    latest_trace=nested["latest_trace"],
                    should_quit=False,
                ),
                "Debug output disabled.",
            )
        return state, _usage_text("/debug on | /debug off")

    if command == "/quit":
        nested = _clone_state_nested_data(state)
        return (
            replace(
                state,
                page_context=nested["page_context"],
                latest_trace=nested["latest_trace"],
                should_quit=True,
            ),
            "Quit requested.",
        )

    return state, f"Unknown command: {command}. Type /help."


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
