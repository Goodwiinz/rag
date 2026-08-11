"""Preserve agent-stream disconnects across middleware receive wrappers."""

import asyncio

from starlette.types import ASGIApp, Message, Receive, Scope, Send

AGENT_DISCONNECT_EVENT = "agent_disconnect_event"


class AgentDisconnectSignalMiddleware:
    """Expose a shared event no matter which middleware consumes disconnect."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope.get("path", "").startswith(
            "/api/v1/agent/stream"
        ):
            await self.app(scope, receive, send)
            return

        disconnected = asyncio.Event()
        scope.setdefault("state", {})[AGENT_DISCONNECT_EVENT] = disconnected

        async def receive_with_signal() -> Message:
            message = await receive()
            if message["type"] == "http.disconnect":
                disconnected.set()
            return message

        await self.app(scope, receive_with_signal, send)
