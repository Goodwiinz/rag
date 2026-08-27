from __future__ import annotations

import httpx
import pytest

from src.cli.agent_api_client import AgentAPIClient


@pytest.mark.asyncio
async def test_stream_message_skips_malformed_sse_and_continues() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=(
                b"event: token\n"
                b'data: {"content":\n\n'
                b"event: token\n"
                b'data: {"content":"survived"}\n\n'
            ),
        )

    client = AgentAPIClient(
        base_url="https://example.test",
        http_client=httpx.AsyncClient(
            base_url="https://example.test",
            transport=httpx.MockTransport(handler),
        ),
    )

    try:
        events = [event async for event in client.stream_message({"messages": []})]
    finally:
        await client.aclose()

    assert len(events) == 1
    assert events[0].type == "token"
    assert events[0].data == {"content": "survived"}
