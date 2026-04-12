"""
Cohere Embedding Service

Uses Cohere embed-v4.0 API for multimodal (text + image) embeddings.
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
    """

    def __init__(self):
        self.endpoint = settings.COHERE_EMBED_ENDPOINT or "https://api.cohere.com/v2/embed"
        self.api_key = settings.COHERE_EMBED_API_KEY or settings.COHERE_RERANK_API_KEY
        self.model = settings.COHERE_EMBED_MODEL
        self.dimensions = settings.COHERE_EMBED_DIMENSIONS
        self.batch_size = settings.COHERE_EMBED_BATCH_SIZE
        self._enabled = bool(self.api_key)

        if self._enabled:
            logger.info(f"Cohere embedding enabled with model: {self.model} ({self.dimensions}d)")
        else:
            logger.warning("Cohere embedding disabled - missing API key")

    @property
    def is_enabled(self) -> bool:
        return self._enabled

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

        # Batch into groups of batch_size
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
        """Embed a single batch of texts (max 96)."""
        breaker = get_circuit_breaker("cohere_embed")

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.endpoint,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "texts": texts,
                        "input_type": input_type,
                        "embedding_types": ["float"],
                        "output_dimension": self.dimensions,
                    },
                )
                response.raise_for_status()
                result = response.json()

            return result["embeddings"]["float"]

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
        Generate embedding for a single image.

        Args:
            image_base64: Base64-encoded image data (without data URI prefix)
            input_type: "search_document" for indexing, "search_query" for queries

        Returns:
            Embedding vector (1024 floats)
        """
        if not self._enabled:
            raise RuntimeError("Cohere embedding service is not enabled")

        breaker = get_circuit_breaker("cohere_embed")
        if breaker and not breaker.can_execute():
            raise RuntimeError("Cohere embed circuit breaker is open")

        start_time = time.time()

        try:
            # Cohere expects data URI format for images
            data_uri = f"data:image/jpeg;base64,{image_base64}"

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.endpoint,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
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
