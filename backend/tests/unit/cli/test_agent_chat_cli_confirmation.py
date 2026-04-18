from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_handle_confirmation_event_routes_y_to_confirmed_true() -> None:
    from src.cli.agent_chat_cli import handle_confirmation_event
    from src.cli.types import CLIEvent

    captured: dict[str, object] = {}

    def resume_callback(*, thread_id: str, confirmed: bool):
        captured["thread_id"] = thread_id
        captured["confirmed"] = confirmed

        async def stream():
            yield CLIEvent(type="token", data={"content": "resumed"})

        return stream()

    event = CLIEvent(
        type="confirmation",
        data={"thread_id": "thread-9", "confirmation": {"message": "Continue?"}},
    )

    events: list[CLIEvent] = []
    async for resumed_event in handle_confirmation_event(
        event,
        resume_callback,
        "y",
    ):
        events.append(resumed_event)

    assert captured == {"thread_id": "thread-9", "confirmed": True}
    assert len(events) == 1
    assert events[0].type == "token"
    assert events[0].data == {"content": "resumed"}


@pytest.mark.asyncio
async def test_handle_confirmation_event_routes_n_to_confirmed_false() -> None:
    from src.cli.agent_chat_cli import handle_confirmation_event
    from src.cli.types import CLIEvent

    captured: dict[str, object] = {}

    def resume_callback(*, thread_id: str, confirmed: bool):
        captured["thread_id"] = thread_id
        captured["confirmed"] = confirmed

        async def stream():
            yield CLIEvent(type="token", data={"content": "stopped"})

        return stream()

    event = CLIEvent(type="confirmation", data={"thread_id": "thread-10"})

    events: list[CLIEvent] = []
    async for resumed_event in handle_confirmation_event(
        event,
        resume_callback,
        "n",
    ):
        events.append(resumed_event)

    assert captured == {"thread_id": "thread-10", "confirmed": False}
    assert len(events) == 1
    assert events[0].type == "token"
    assert events[0].data == {"content": "stopped"}


@pytest.mark.asyncio
async def test_handle_confirmation_event_supports_async_callback_without_stream() -> None:
    from src.cli.agent_chat_cli import handle_confirmation_event
    from src.cli.types import CLIEvent

    captured: dict[str, object] = {}

    async def resume_callback(*, thread_id: str, confirmed: bool) -> None:
        captured["thread_id"] = thread_id
        captured["confirmed"] = confirmed

    event = CLIEvent(type="confirmation", data={"thread_id": "thread-12"})

    events: list[CLIEvent] = []
    async for resumed_event in handle_confirmation_event(
        event,
        resume_callback,
        "y",
    ):
        events.append(resumed_event)

    assert captured == {"thread_id": "thread-12", "confirmed": True}
    assert events == []


@pytest.mark.asyncio
async def test_handle_confirmation_event_rejects_invalid_input_before_callback() -> None:
    from src.cli.agent_chat_cli import handle_confirmation_event
    from src.cli.types import CLIEvent

    def resume_callback(*, thread_id: str, confirmed: bool):
        raise AssertionError("resume_callback should not be called for invalid input")

    event = CLIEvent(type="confirmation", data={"thread_id": "thread-13"})

    with pytest.raises(ValueError, match="Confirmation input must be 'y' or 'n'"):
        async for _ in handle_confirmation_event(event, resume_callback, "maybe"):
            pass


@pytest.mark.parametrize("bad_result", [["x"], "oops", object()])
@pytest.mark.asyncio
async def test_handle_confirmation_event_rejects_miswired_callback_results(
    bad_result: object,
) -> None:
    from src.cli.agent_chat_cli import handle_confirmation_event
    from src.cli.types import CLIEvent

    def resume_callback(*, thread_id: str, confirmed: bool):
        return bad_result

    event = CLIEvent(type="confirmation", data={"thread_id": "thread-14"})

    with pytest.raises(TypeError, match="resume_callback must return None or an async iterator"):
        async for _ in handle_confirmation_event(event, resume_callback, "y"):
            pass


@pytest.mark.parametrize("user_input", ["", "maybe", "yes", "1"])
@pytest.mark.asyncio
async def test_handle_confirmation_event_rejects_invalid_input(
    user_input: str,
) -> None:
    from src.cli.agent_chat_cli import handle_confirmation_event
    from src.cli.types import CLIEvent

    def resume_callback(*, thread_id: str, confirmed: bool):
        async def stream():
            yield CLIEvent(type="token", data={"content": "unexpected"})

        return stream()

    event = CLIEvent(type="confirmation", data={"thread_id": "thread-11"})

    with pytest.raises(ValueError, match="Confirmation input must be 'y' or 'n'"):
        async for _ in handle_confirmation_event(event, resume_callback, user_input):
            pass
