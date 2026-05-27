from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.cli.types import CLIEvent


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def render_trace(data: Mapping[str, Any]) -> str:
    parts = ["trace>"]

    thread_id = _as_text(data.get("thread_id"))
    cli_session_id = _as_text(data.get("cli_session_id"))
    langsmith_run_id = _as_text(data.get("langsmith_run_id"))
    langsmith_url = _as_text(data.get("langsmith_url"))

    if thread_id:
        parts.append(f"thread={thread_id}")
    if cli_session_id:
        parts.append(f"session={cli_session_id}")
    if langsmith_run_id:
        parts.append(f"run={langsmith_run_id}")

    text = " ".join(parts)
    if langsmith_url:
        text = f"{text}\n{langsmith_url}"
    return text


def render_tool_start(data: Mapping[str, Any]) -> str:
    tool = _as_text(data.get("tool")) or "unknown_tool"
    return f"tool> {tool} started"


def render_tool_end(data: Mapping[str, Any]) -> str:
    tool = _as_text(data.get("tool")) or "unknown_tool"
    result = _as_text(data.get("result"))
    if result:
        return f"tool> {tool} done: {result}"
    return f"tool> {tool} done"


def render_plan(data: Mapping[str, Any], *, debug: bool = False) -> str:
    steps = data.get("steps") or []
    lines = ["plan>"]

    for step in steps:
        if isinstance(step, Mapping):
            step_number = _as_text(step.get("step"))
            description = _as_text(step.get("description"))
            lines.append(f"{step_number}. {description}".rstrip())

    reasoning = _as_text(data.get("reasoning"))
    if debug and reasoning:
        lines.append(f"reasoning: {reasoning}")

    return "\n".join(lines)


def render_reflection(data: Mapping[str, Any]) -> str:
    passed = bool(data.get("passed", True))
    round_number = _as_text(data.get("round"))
    issues = data.get("issues") or []
    issue_text = "; ".join(_as_text(issue) for issue in issues if _as_text(issue))

    status = "passed" if passed else "needs revision"
    parts = [f"reflection> round {round_number}", status]
    if issue_text:
        parts.append(issue_text)
    return " - ".join(parts)


def render_confirmation(data: Mapping[str, Any]) -> str:
    confirmation = data.get("confirmation") or {}
    message = ""
    if isinstance(confirmation, Mapping):
        message = _as_text(confirmation.get("message"))
    thread_id = _as_text(data.get("thread_id"))

    parts = ["confirmation>"]
    if thread_id:
        parts.append(f"thread={thread_id}")
    if message:
        parts.append(message)
    parts.append("respond with y/n")
    return " - ".join(parts)


def render_error(data: Mapping[str, Any]) -> str:
    error = _as_text(data.get("error")) or "unknown error"
    return f"error> {error}"


def render_token(data: Mapping[str, Any]) -> str:
    return _as_text(data.get("content"))


def render_event(event: CLIEvent, *, debug: bool = False) -> str:
    if event.type == "trace":
        return render_trace(event.data)
    if event.type == "tool_start":
        return render_tool_start(event.data)
    if event.type == "tool_end":
        return render_tool_end(event.data)
    if event.type == "plan":
        return render_plan(event.data, debug=debug)
    if event.type == "reflection":
        return render_reflection(event.data)
    if event.type == "confirmation":
        return render_confirmation(event.data)
    if event.type == "error":
        return render_error(event.data)
    if event.type == "token":
        return render_token(event.data)
    return ""
