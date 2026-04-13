"""
Cohere Embedding Service

Uses Cohere embed-v4.0 API for multimodal (text + image) embeddings.
Supports both direct Cohere API and Azure AI deployments (OpenAI-compatible).
Follows the same httpx + circuit breaker pattern as cohere_rerank_service.
"""

import logging
import time
from typing import List

import httpx

from src.core.circuit_breaker import get_circuit_breaker
from src.core.config import settings

logger = logging.getLogger(__name__)


class CohereEmbedService:
    """
    Service for generating text and image embeddings using Cohere embed-v4.0.

    Supports multimodal embedding: text and images are mapped into the same
    1024-dimensional vector space, enabling cross-modal similarity search.

    Detects Azure AI endpoints automatically and uses the OpenAI-compatible
    API format (api-key header, input field) vs Cohere native format.
    """

    def __init__(self):
        self.endpoint = settings.COHERE_EMBED_ENDPOINT or "https://api.cohere.com/v2/embed"
        self.api_key = settings.COHERE_EMBED_API_KEY or settings.COHERE_RERANK_API_KEY
        self.model = settings.COHERE_EMBED_MODEL
        self.dimensions = settings.COHERE_EMBED_DIMENSIONS
        self.batch_size = settings.COHERE_EMBED_BATCH_SIZE
        self._enabled = bool(self.api_key)

        # Detect Azure AI endpoint (uses OpenAI-compatible API format)
        self._is_azure = "azure" in self.endpoint.lower() or "services.ai" in self.endpoint.lower()

        if self._enabled:
            mode = "Azure AI (OpenAI-compat)" if self._is_azure else "Cohere native"
            logger.info(
                f"Cohere embedding enabled: {mode}, model={self.model}, dims={self.dimensions}"
            )
        else:
            logger.warning("Cohere embedding disabled - missing API key")

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def _get_headers(self) -> dict:
        if self._is_azure:
            return {
                "api-key": self.api_key,
                "Content-Type": "application/json",
            }
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_text_payload(self, texts: List[str]) -> dict:
        if self._is_azure:
            return {
                "model": self.model,
                "input": texts,
                "dimensions": self.dimensions,
            }
        return {
            "model": self.model,
            "texts": texts,
            "input_type": "search_document",
            "embedding_types": ["float"],
            "output_dimension": self.dimensions,
        }

    def _parse_embeddings(self, result: dict) -> List[List[float]]:
        if self._is_azure:
            # OpenAI format: {"data": [{"embedding": [...], "index": 0}, ...]}
            sorted_data = sorted(result["data"], key=lambda x: x["index"])
            return [item["embedding"] for item in sorted_data]
        # Cohere native format: {"embeddings": {"float": [[...], ...]}}
        return result["embeddings"]["float"]

    async def embed_texts(
        self,
        texts: List[str],
        input_type: str = "search_document",
    ) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed (max 96 per batch)
            input_type: "search_document" for indexing, "search_query" for queries

        Returns:
            List of embedding vectors (each 1024 floats)
        """
        if not self._enabled:
            raise RuntimeError("Cohere embedding service is not enabled")

        breaker = get_circuit_breaker("cohere_embed")
        if breaker and not breaker.can_execute():
            raise RuntimeError("Cohere embed circuit breaker is open")

        all_embeddings: List[List[float]] = []
        start_time = time.time()

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            batch_embeddings = await self._embed_texts_batch(batch, input_type)
            all_embeddings.extend(batch_embeddings)

        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Cohere embed completed in {elapsed_ms:.0f}ms for {len(texts)} texts"
        )

        if breaker:
            breaker.record_success()

        return all_embeddings

    async def _embed_texts_batch(
        self,
        texts: List[str],
        input_type: str,
    ) -> List[List[float]]:
        """Embed a single batch of texts."""
        breaker = get_circuit_breaker("cohere_embed")

        try:
            payload = self._build_text_payload(texts)
            # For native Cohere, override input_type per call
            if not self._is_azure:
                payload["input_type"] = input_type

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.endpoint,
                    headers=self._get_headers(),
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()

            return self._parse_embeddings(result)

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Cohere embed API error: {e.response.status_code} - {e.response.text[:500]}"
            )
            if breaker:
                breaker.record_failure(e)
            raise

        except Exception as e:
            logger.error(f"Cohere embed failed: {e}")
            if breaker:
                breaker.record_failure(e)
            raise

    async def embed_image(
        self,
        image_base64: str,
        input_type: str = "search_document",
    ) -> List[float]:
        """
        Generate embedding for a single image (Cohere native API only).

        Args:
            image_base64: Base64-encoded image data (without data URI prefix)
            input_type: "search_document" for indexing, "search_query" for queries

        Returns:
            Embedding vector (1024 floats)
        """
        if not self._enabled:
            raise RuntimeError("Cohere embedding service is not enabled")

        if self._is_azure:
            raise RuntimeError(
                "Image embedding not supported via Azure AI OpenAI-compatible endpoint. "
                "Use the direct Cohere API for image embeddings."
            )

        breaker = get_circuit_breaker("cohere_embed")
        if breaker and not breaker.can_execute():
            raise RuntimeError("Cohere embed circuit breaker is open")

        start_time = time.time()

        try:
            data_uri = f"data:image/jpeg;base64,{image_base64}"

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.endpoint,
                    headers=self._get_headers(),
                    json={
                        "model": self.model,
                        "images": [data_uri],
                        "input_type": input_type,
                        "embedding_types": ["float"],
                        "output_dimension": self.dimensions,
                    },
                )
                response.raise_for_status()
                result = response.json()

            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(f"Cohere image embed completed in {elapsed_ms:.0f}ms")

            if breaker:
                breaker.record_success()

            return result["embeddings"]["float"][0]

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Cohere image embed API error: {e.response.status_code} - {e.response.text[:500]}"
            )
            if breaker:
                breaker.record_failure(e)
            raise

        except Exception as e:
            logger.error(f"Cohere image embed failed: {e}")
            if breaker:
                breaker.record_failure(e)
            raise

    async def embed_text_single(
        self,
        text: str,
        input_type: str = "search_query",
    ) -> List[float]:
        """Convenience: embed a single text string."""
        embeddings = await self.embed_texts([text], input_type)
        return embeddings[0]


# Global service instance
cohere_embed_service = CohereEmbedService()
