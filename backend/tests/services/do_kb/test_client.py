"""Unit tests for DOKnowledgeBaseClient.

Mocks httpx.AsyncClient.request to avoid network. Verifies retry on 429,
auth failure handling, and successful retrieve parsing.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.config import Settings
from src.services.do_kb.client import (
    DOKnowledgeBaseClient,
    DOKnowledgeBaseError,
)


def _make_settings(**overrides: Any) -> Settings:
    base = dict(
        DO_KB_ENABLED=True,
        DO_API_TOKEN="test-token",
        DO_KB_REGION="tor1",
        DO_KB_PROJECT_ID="test-project",
        DO_KB_EMBEDDING_MODEL_UUID="model-uuid",
        DO_KB_REQUEST_TIMEOUT_SECONDS=1.0,
    )
    base.update(overrides)
    return Settings(**base)


def _mock_response(status: int, json_body: dict[str, Any] | None = None) -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.json.return_value = json_body or {}
    response.text = "" if json_body is None else str(json_body)
    response.content = b"{}" if json_body is not None else b""
    return response


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pooled_client_reused_across_requests():
    """Audit A3: the AsyncClient is created once and reused, not rebuilt per call."""
    cfg = _make_settings()
    client = DOKnowledgeBaseClient(cfg=cfg)

    payload = {"job": {"uuid": "j", "status": "PENDING"}}
    with patch("httpx.AsyncClient") as mock_async_client:
        mock_async_client.return_value.request = AsyncMock(
            return_value=_mock_response(200, payload)
        )
        await client.start_indexing(kb_uuid="kb")
        await client.start_indexing(kb_uuid="kb")

    # Two requests, one client constructed.
    assert mock_async_client.call_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_kb_happy_path():
    cfg = _make_settings()
    client = DOKnowledgeBaseClient(cfg=cfg)

    payload = {
        "knowledge_base": {
            "uuid": "kb-123",
            "name": "nous-org-abc",
            "region": "tor1",
            "project_id": "test-project",
            "embedding_model_uuid": "model-uuid",
            "is_public": False,
        }
    }

    with patch("httpx.AsyncClient") as mock_async_client:
        request_mock = AsyncMock(return_value=_mock_response(200, payload))
        ctx = mock_async_client.return_value
        ctx.request = request_mock

        kb = await client.create_kb(
            name="nous-org-abc",
            region="tor1",
            project_id="test-project",
            embedding_model_uuid="model-uuid",
        )

    assert kb.uuid == "kb-123"
    assert kb.name == "nous-org-abc"
    request_mock.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retrieve_parses_chunks():
    cfg = _make_settings()
    client = DOKnowledgeBaseClient(cfg=cfg)

    # Mirror DO live wire format: `results[]` with `text_content` field
    # plus `total_results` at the top.
    payload = {
        "results": [
            {
                "text_content": "first",
                "score": 0.9,
                "metadata": {"item_name": "doc-1.pdf"},
            },
            {
                "text_content": "second",
                "score": 0.7,
                "metadata": {"item_name": "doc-2.pdf"},
            },
        ],
        "total_results": 2,
    }

    with patch("httpx.AsyncClient") as mock_async_client:
        request_mock = AsyncMock(return_value=_mock_response(200, payload))
        ctx = mock_async_client.return_value
        ctx.request = request_mock

        result = await client.retrieve(kb_uuid="kb-123", query="hello", top_k=2)

    assert result.total == 2
    assert result.chunks[0].text == "first"
    assert result.chunks[0].document_id == "doc-1.pdf"
    assert result.chunks[1].score == 0.7


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retrieve_synthesizes_score_when_absent():
    """DO retrieve Public Preview omits relevance scores. Verify the client
    falls back to a rank-position proxy (1.0 at rank 0, decay 0.05/step,
    floor 0.1) so downstream code can still rank/dedupe/threshold.
    """
    cfg = _make_settings()
    client = DOKnowledgeBaseClient(cfg=cfg)

    payload = {
        "results": [
            {"text_content": "a", "metadata": {"item_name": "doc-a.pdf"}},
            {"text_content": "b", "metadata": {"item_name": "doc-b.pdf"}},
            {"text_content": "c", "metadata": {"item_name": "doc-c.pdf"}},
        ],
        "total_results": 3,
    }

    with patch("httpx.AsyncClient") as mock_async_client:
        request_mock = AsyncMock(return_value=_mock_response(200, payload))
        ctx = mock_async_client.return_value
        ctx.request = request_mock

        result = await client.retrieve(kb_uuid="kb-123", query="x", top_k=3)

    scores = [c.score for c in result.chunks]
    assert scores[0] > scores[1] > scores[2]
    assert scores[0] == pytest.approx(1.0)
    assert scores[1] == pytest.approx(0.95)
    assert scores[2] == pytest.approx(0.90)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retrieve_uses_config_alpha():
    """When caller omits alpha, client sends DO_KB_RETRIEVE_ALPHA from config."""
    cfg = _make_settings(DO_KB_RETRIEVE_ALPHA=0.3)
    client = DOKnowledgeBaseClient(cfg=cfg)

    payload = {"results": [], "total_results": 0}

    with patch("httpx.AsyncClient") as mock_async_client:
        request_mock = AsyncMock(return_value=_mock_response(200, payload))
        ctx = mock_async_client.return_value
        ctx.request = request_mock

        await client.retrieve(kb_uuid="kb-123", query="test")

    sent_body = request_mock.call_args.kwargs.get("json") or request_mock.call_args[1].get("json")
    assert sent_body["alpha"] == 0.3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retrieve_explicit_alpha_overrides_config():
    """Caller-supplied alpha takes precedence over config default."""
    cfg = _make_settings(DO_KB_RETRIEVE_ALPHA=0.3)
    client = DOKnowledgeBaseClient(cfg=cfg)

    payload = {"results": [], "total_results": 0}

    with patch("httpx.AsyncClient") as mock_async_client:
        request_mock = AsyncMock(return_value=_mock_response(200, payload))
        ctx = mock_async_client.return_value
        ctx.request = request_mock

        await client.retrieve(kb_uuid="kb-123", query="test", alpha=0.8)

    sent_body = request_mock.call_args.kwargs.get("json") or request_mock.call_args[1].get("json")
    assert sent_body["alpha"] == 0.8


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retrieve_no_alpha_when_config_none():
    """When config alpha is None and caller omits it, no alpha in request body."""
    cfg = _make_settings(DO_KB_RETRIEVE_ALPHA=None)
    client = DOKnowledgeBaseClient(cfg=cfg)

    payload = {"results": [], "total_results": 0}

    with patch("httpx.AsyncClient") as mock_async_client:
        request_mock = AsyncMock(return_value=_mock_response(200, payload))
        ctx = mock_async_client.return_value
        ctx.request = request_mock

        await client.retrieve(kb_uuid="kb-123", query="test")

    sent_body = request_mock.call_args.kwargs.get("json") or request_mock.call_args[1].get("json")
    assert "alpha" not in sent_body


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retry_on_429_then_success(monkeypatch):
    cfg = _make_settings()
    client = DOKnowledgeBaseClient(cfg=cfg)

    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("asyncio.sleep", fake_sleep)

    success_payload = {"job": {"uuid": "job-1", "status": "PENDING"}}
    responses = [
        _mock_response(429),
        _mock_response(200, success_payload),
    ]

    with patch("httpx.AsyncClient") as mock_async_client:
        request_mock = AsyncMock(side_effect=responses)
        ctx = mock_async_client.return_value
        ctx.request = request_mock

        job = await client.start_indexing(kb_uuid="kb-123")

    assert job.uuid == "job-1"
    assert request_mock.await_count == 2
    assert sleeps  # backoff slept at least once


@pytest.mark.unit
@pytest.mark.asyncio
async def test_auth_failure_raises():
    cfg = _make_settings(DO_API_TOKEN=None, DO_KB_ENABLED=False)
    client = DOKnowledgeBaseClient(cfg=cfg)

    with pytest.raises(DOKnowledgeBaseError):
        await client.create_kb(
            name="x",
            region="tor1",
            project_id="p",
            embedding_model_uuid="m",
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retrieve_uses_config_default_top_k():
    cfg = _make_settings(DO_KB_DEFAULT_TOP_K=12)
    client = DOKnowledgeBaseClient(cfg=cfg)
    payload = {"results": [], "total_results": 0}
    with patch("httpx.AsyncClient") as mock_async_client:
        request_mock = AsyncMock(return_value=_mock_response(200, payload))
        ctx = mock_async_client.return_value
        ctx.request = request_mock
        await client.retrieve(kb_uuid="kb-123", query="test")
    sent_body = request_mock.call_args.kwargs.get("json") or request_mock.call_args[1].get("json")
    assert sent_body["num_results"] == 12


@pytest.mark.unit
@pytest.mark.asyncio
async def test_4xx_non_retryable_raises(monkeypatch):
    cfg = _make_settings()
    client = DOKnowledgeBaseClient(cfg=cfg)

    async def fake_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr("asyncio.sleep", fake_sleep)

    with patch("httpx.AsyncClient") as mock_async_client:
        request_mock = AsyncMock(return_value=_mock_response(404))
        ctx = mock_async_client.return_value
        ctx.request = request_mock

        with pytest.raises(DOKnowledgeBaseError) as exc_info:
            await client.get_indexing_job(kb_uuid="kb", job_uuid="job")

    assert exc_info.value.status_code == 404
    assert request_mock.await_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retrieve_sends_reranking_when_enabled():
    """When config enables reranking, the request body includes reranking=True."""
    cfg = _make_settings(DO_KB_RERANKING_ENABLED=True)
    client = DOKnowledgeBaseClient(cfg=cfg)

    payload = {"results": [], "total_results": 0}

    with patch("httpx.AsyncClient") as mock_async_client:
        request_mock = AsyncMock(return_value=_mock_response(200, payload))
        ctx = mock_async_client.return_value
        ctx.request = request_mock

        await client.retrieve(kb_uuid="kb-123", query="test")

    sent_body = request_mock.call_args.kwargs.get("json") or request_mock.call_args[1].get("json")
    assert sent_body["reranking"] is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retrieve_omits_reranking_when_none():
    """When config reranking is None, no reranking key in request body."""
    cfg = _make_settings(DO_KB_RERANKING_ENABLED=None)
    client = DOKnowledgeBaseClient(cfg=cfg)

    payload = {"results": [], "total_results": 0}

    with patch("httpx.AsyncClient") as mock_async_client:
        request_mock = AsyncMock(return_value=_mock_response(200, payload))
        ctx = mock_async_client.return_value
        ctx.request = request_mock

        await client.retrieve(kb_uuid="kb-123", query="test")

    sent_body = request_mock.call_args.kwargs.get("json") or request_mock.call_args[1].get("json")
    assert "reranking" not in sent_body


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retrieve_explicit_reranking_overrides_config():
    """Caller-supplied reranking=False overrides config True."""
    cfg = _make_settings(DO_KB_RERANKING_ENABLED=True)
    client = DOKnowledgeBaseClient(cfg=cfg)

    payload = {"results": [], "total_results": 0}

    with patch("httpx.AsyncClient") as mock_async_client:
        request_mock = AsyncMock(return_value=_mock_response(200, payload))
        ctx = mock_async_client.return_value
        ctx.request = request_mock

        await client.retrieve(kb_uuid="kb-123", query="test", reranking=False)

    sent_body = request_mock.call_args.kwargs.get("json") or request_mock.call_args[1].get("json")
    assert sent_body["reranking"] is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retrieve_sends_search_type_when_set():
    """When config sets search_type, the request body includes it."""
    cfg = _make_settings(DO_KB_SEARCH_TYPE="keyword")
    client = DOKnowledgeBaseClient(cfg=cfg)

    payload = {"results": [], "total_results": 0}

    with patch("httpx.AsyncClient") as mock_async_client:
        request_mock = AsyncMock(return_value=_mock_response(200, payload))
        ctx = mock_async_client.return_value
        ctx.request = request_mock

        await client.retrieve(kb_uuid="kb-123", query="test")

    sent_body = request_mock.call_args.kwargs.get("json") or request_mock.call_args[1].get("json")
    assert sent_body["search_type"] == "keyword"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retrieve_omits_search_type_when_none():
    """When config search_type is None and caller omits it, no search_type in body."""
    cfg = _make_settings(DO_KB_SEARCH_TYPE=None)
    client = DOKnowledgeBaseClient(cfg=cfg)

    payload = {"results": [], "total_results": 0}

    with patch("httpx.AsyncClient") as mock_async_client:
        request_mock = AsyncMock(return_value=_mock_response(200, payload))
        ctx = mock_async_client.return_value
        ctx.request = request_mock

        await client.retrieve(kb_uuid="kb-123", query="test")

    sent_body = request_mock.call_args.kwargs.get("json") or request_mock.call_args[1].get("json")
    assert "search_type" not in sent_body


@pytest.mark.unit
@pytest.mark.asyncio
async def test_all_429_raises_with_real_status(monkeypatch):
    """An all-retryable run must surface the actual HTTP status, not the old
    'exhausted retries: None' (audit A4)."""
    cfg = _make_settings()
    client = DOKnowledgeBaseClient(cfg=cfg)

    async def fake_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr("asyncio.sleep", fake_sleep)

    with patch("httpx.AsyncClient") as mock_async_client:
        request_mock = AsyncMock(return_value=_mock_response(429))
        ctx = mock_async_client.return_value
        ctx.request = request_mock

        with pytest.raises(DOKnowledgeBaseError) as exc_info:
            await client.start_indexing(kb_uuid="kb")

    assert exc_info.value.status_code == 429
    assert "429" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_honors_retry_after_header(monkeypatch):
    """A 429 with Retry-After: 5 should sleep 5s, not the 2**attempt backoff (A5)."""
    cfg = _make_settings()
    client = DOKnowledgeBaseClient(cfg=cfg)

    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("asyncio.sleep", fake_sleep)

    resp_429 = _mock_response(429)
    resp_429.headers = {"Retry-After": "5"}
    resp_ok = _mock_response(200, {"job": {"uuid": "job-1", "status": "PENDING"}})

    with patch("httpx.AsyncClient") as mock_async_client:
        request_mock = AsyncMock(side_effect=[resp_429, resp_ok])
        ctx = mock_async_client.return_value
        ctx.request = request_mock

        job = await client.start_indexing(kb_uuid="kb")

    assert job.uuid == "job-1"
    assert 5 in sleeps
