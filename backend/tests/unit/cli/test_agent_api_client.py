from __future__ import annotations

import httpx
import pytest


def test_build_stream_headers_includes_auth_and_org() -> None:
    from src.cli.agent_api_client import build_stream_headers

    headers = build_stream_headers(token="tok", organization_id="org-1")

    assert headers["Authorization"] == "Bearer tok"
    assert headers["X-Organization-ID"] == "org-1"
    assert headers["Content-Type"] == "application/json"


def test_agent_api_client_default_timeout_is_streaming_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.cli.agent_api_client import AgentAPIClient

    captured: dict[str, object] = {}

    class FakeAsyncClient:
        def __init__(self, *, base_url: str, timeout: object | None = None) -> None:
            captured["base_url"] = base_url
            captured["timeout"] = timeout

        async def aclose(self) -> None:
            pass

    monkeypatch.setattr("src.cli.agent_api_client.httpx.AsyncClient", FakeAsyncClient)

    client = AgentAPIClient(base_url="https://example.test/")

    timeout = captured["timeout"]
    assert captured["base_url"] == "https://example.test"
    assert timeout is not None
    assert getattr(timeout, "read", None) is None
    assert getattr(timeout, "connect", None) is not None

    # Sanity check that the client can still be closed.
    import asyncio

    asyncio.run(client.aclose())


@pytest.mark.asyncio
async def test_stream_message_yields_parsed_events_from_sse() -> None:
    from src.cli.agent_api_client import AgentAPIClient

    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = request.content.decode()
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=(
                b'event: trace\n'
                b'data: {"thread_id":"thread-1","cli_session_id":"cli-1","langsmith_run_id":"run-1","langsmith_url":"u1"}\n\n'
                b'event: token\n'
                b'data: {"content":"Hello"}\n\n'
            ),
        )

    client = AgentAPIClient(
        base_url="https://example.test",
        token="tok",
        organization_id="org-1",
        http_client=httpx.AsyncClient(
            base_url="https://example.test",
            transport=httpx.MockTransport(handler),
        ),
    )

    events = []
    async for event in client.stream_message(
        {
            "messages": [{"role": "user", "content": "hi"}],
            "page_context": {"type": "project", "project_id": "p-1"},
        }
    ):
        events.append(event)

    await client.aclose()

    assert captured["method"] == "POST"
    assert captured["url"] == "https://example.test/api/v1/agent/stream"
    assert captured["headers"]["authorization"] == "Bearer tok"
    assert captured["headers"]["x-organization-id"] == "org-1"
    assert captured["headers"]["content-type"] == "application/json"
    assert "hi" in captured["body"]
    assert events[0].type == "trace"
    assert events[0].data["langsmith_run_id"] == "run-1"
    assert events[1].type == "token"
    assert events[1].data["content"] == "Hello"


@pytest.mark.asyncio
async def test_stream_confirm_yields_parsed_events_and_sends_confirmation_payload() -> None:
    from src.cli.agent_api_client import AgentAPIClient

    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = request.content.decode()
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=(
                b'event: token\n'
                b'data: {"content":"Done"}\n\n'
            ),
        )

    client = AgentAPIClient(
        base_url="https://example.test",
        token="tok",
        organization_id="org-1",
        http_client=httpx.AsyncClient(
            base_url="https://example.test",
            transport=httpx.MockTransport(handler),
        ),
    )

    events = []
    async for event in client.stream_confirm(thread_id="thread-9", confirmed=True):
        events.append(event)

    await client.aclose()

    assert captured["method"] == "POST"
    assert captured["url"] == "https://example.test/api/v1/agent/stream/confirm"
    assert "thread-9" in captured["body"]
    assert "true" in captured["body"]
    assert events[0].type == "token"
    assert events[0].data["content"] == "Done"


@pytest.mark.asyncio
async def test_stream_message_raises_friendly_auth_error_for_403() -> None:
    from src.cli.agent_api_client import AgentAPIClient, AgentAPIClientError

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={"detail": "Not authenticated"},
        )

    client = AgentAPIClient(
        base_url="https://example.test",
        http_client=httpx.AsyncClient(
            base_url="https://example.test",
            transport=httpx.MockTransport(handler),
        ),
    )

    with pytest.raises(AgentAPIClientError) as exc_info:
        async for _ in client.stream_message(
            {"messages": [{"role": "user", "content": "hi"}]}
        ):
            pass

    await client.aclose()

    assert exc_info.value.status_code == 403
    assert "run /login" in str(exc_info.value).lower()
