"""Async HTTP client for DigitalOcean Knowledge Base / GradientAI Platform.

Endpoints:
- Control plane: api.digitalocean.com/v2/gen-ai/knowledge-bases/...
- Retrieve plane: kbaas.do-ai.run/v1/{kb_uuid}/retrieve

Bearer auth, exponential backoff on 429/5xx (3 attempts), 30s default timeout.
Public Preview API — wrap parsing in permissive Pydantic models so field
additions don't break us.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

import httpx

from src.core.config import Settings, settings as global_settings

from .models import Chunk, DataSource, IndexingJob, KnowledgeBase, RetrieveResult

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 3


class DOKnowledgeBaseError(RuntimeError):
    """Raised on non-retryable DO KB API failures."""

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class DOKnowledgeBaseClient:
    """Async client for DO KB control + retrieve planes.

    Settings are injected so tests can swap them without touching env.
    """

    def __init__(self, cfg: Optional[Settings] = None) -> None:
        self._settings = cfg or global_settings

    @property
    def _api_base(self) -> str:
        return self._settings.DO_KB_API_HOST.rstrip("/")

    @property
    def _retrieve_base(self) -> str:
        return self._settings.DO_KB_RETRIEVE_HOST.rstrip("/")

    @property
    def _auth_headers(self) -> dict[str, str]:
        token = self._settings.DO_API_TOKEN
        if not token:
            raise DOKnowledgeBaseError("DO_API_TOKEN not configured")
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        url: str,
        *,
        json_body: Optional[dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        timeout_s = timeout or self._settings.DO_KB_REQUEST_TIMEOUT_SECONDS
        last_exc: Optional[Exception] = None

        for attempt in range(_MAX_ATTEMPTS):
            try:
                async with httpx.AsyncClient(timeout=timeout_s) as client:
                    response = await client.request(
                        method,
                        url,
                        headers=self._auth_headers,
                        json=json_body,
                    )
                if response.status_code in _RETRYABLE_STATUS:
                    wait = 2 ** attempt
                    logger.warning(
                        "do_kb retryable status",
                        extra={
                            "status": response.status_code,
                            "url": url,
                            "attempt": attempt + 1,
                        },
                    )
                    await asyncio.sleep(wait)
                    continue
                if response.status_code >= 400:
                    raise DOKnowledgeBaseError(
                        f"DO KB request failed: {response.status_code} {response.text[:300]}",
                        status_code=response.status_code,
                    )
                if not response.content:
                    return {}
                return response.json()
            except httpx.TimeoutException as exc:
                last_exc = exc
                logger.warning(
                    "do_kb timeout",
                    extra={"url": url, "attempt": attempt + 1},
                )
                await asyncio.sleep(2 ** attempt)
            except httpx.HTTPError as exc:
                last_exc = exc
                logger.warning(
                    "do_kb http error",
                    extra={"url": url, "attempt": attempt + 1, "error": str(exc)},
                )
                await asyncio.sleep(2 ** attempt)

        raise DOKnowledgeBaseError(
            f"DO KB request exhausted retries: {last_exc}"
        )

    # ── Control plane ────────────────────────────────────────────────────────

    async def create_kb(
        self,
        *,
        name: str,
        region: str,
        project_id: str,
        embedding_model_uuid: str,
        tags: Optional[list[str]] = None,
    ) -> KnowledgeBase:
        body: dict[str, Any] = {
            "name": name,
            "region": region,
            "project_id": project_id,
            "embedding_model_uuid": embedding_model_uuid,
        }
        if tags:
            body["tags"] = tags
        payload = await self._request(
            "POST",
            f"{self._api_base}/v2/gen-ai/knowledge-bases",
            json_body=body,
        )
        kb_data = payload.get("knowledge_base", payload)
        return KnowledgeBase.model_validate(kb_data)

    async def add_spaces_data_source(
        self,
        *,
        kb_uuid: str,
        bucket: str,
        key: str,
        region: Optional[str] = None,
    ) -> DataSource:
        body: dict[str, Any] = {
            "spaces_data_source": {
                "bucket_name": bucket,
                "item_path": key,
                "region": region or self._settings.DO_KB_REGION,
            }
        }
        payload = await self._request(
            "POST",
            f"{self._api_base}/v2/gen-ai/knowledge-bases/{kb_uuid}/data-sources",
            json_body=body,
        )
        ds_data = payload.get("knowledge_base_data_source", payload)
        return DataSource.model_validate(ds_data)

    async def start_indexing(self, *, kb_uuid: str) -> IndexingJob:
        payload = await self._request(
            "POST",
            f"{self._api_base}/v2/gen-ai/knowledge-bases/{kb_uuid}/indexing-jobs",
            json_body={},
            timeout=self._settings.DO_KB_INDEXING_TIMEOUT_SECONDS,
        )
        job_data = payload.get("job", payload)
        return IndexingJob.model_validate(job_data)

    async def get_indexing_job(self, *, kb_uuid: str, job_uuid: str) -> IndexingJob:
        payload = await self._request(
            "GET",
            f"{self._api_base}/v2/gen-ai/knowledge-bases/{kb_uuid}/indexing-jobs/{job_uuid}",
        )
        job_data = payload.get("job", payload)
        return IndexingJob.model_validate(job_data)

    # ── Retrieve plane ───────────────────────────────────────────────────────

    async def retrieve(
        self,
        *,
        kb_uuid: str,
        query: str,
        top_k: Optional[int] = None,
        alpha: Optional[float] = None,
    ) -> RetrieveResult:
        # DO KB retrieve body fields (per
        # docs.digitalocean.com/products/inference/how-to/create-manage-agent-knowledge-bases):
        #   query: str
        #   num_results: int 0-100 (NOT top_k)
        #   alpha: float 0-1 (lexical vs semantic balance)
        #   filters / reranking: optional, not exposed yet
        k = top_k or self._settings.DO_KB_DEFAULT_TOP_K
        body: dict[str, Any] = {"query": query, "num_results": max(1, min(k, 100))}
        if alpha is not None:
            body["alpha"] = alpha
        payload = await self._request(
            "POST",
            f"{self._retrieve_base}/v1/{kb_uuid}/retrieve",
            json_body=body,
        )
        raw_chunks = payload.get("chunks") or payload.get("results") or []
        chunks = [Chunk.model_validate(c) for c in raw_chunks]
        return RetrieveResult(chunks=chunks, total=len(chunks))


_default_client: Optional[DOKnowledgeBaseClient] = None


def get_do_kb_client() -> DOKnowledgeBaseClient:
    """Process-wide singleton. Tests should construct DOKnowledgeBaseClient
    directly rather than using this getter."""
    global _default_client
    if _default_client is None:
        _default_client = DOKnowledgeBaseClient()
    return _default_client
