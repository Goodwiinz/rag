"""Tests for Cohere Embedding Service"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.services.embedding.cohere_embed_service import CohereEmbedService


class TestCohereEmbedServiceInit:
    """Test service initialization and configuration"""

    def test_disabled_when_no_api_key(self):
        with patch("src.services.embedding.cohere_embed_service.settings") as mock_settings:
            mock_settings.COHERE_EMBED_ENDPOINT = None
            mock_settings.COHERE_EMBED_API_KEY = None
            mock_settings.COHERE_RERANK_API_KEY = None
            mock_settings.COHERE_EMBED_MODEL = "embed-v4.0"
            mock_settings.COHERE_EMBED_DIMENSIONS = 1024
            mock_settings.COHERE_EMBED_BATCH_SIZE = 96

            service = CohereEmbedService()
            assert not service.is_enabled

    def test_enabled_with_embed_api_key(self):
        with patch("src.services.embedding.cohere_embed_service.settings") as mock_settings:
            mock_settings.COHERE_EMBED_ENDPOINT = "https://api.cohere.com/v2/embed"
            mock_settings.COHERE_EMBED_API_KEY = "test-key"
            mock_settings.COHERE_RERANK_API_KEY = None
            mock_settings.COHERE_EMBED_MODEL = "embed-v4.0"
            mock_settings.COHERE_EMBED_DIMENSIONS = 1024
            mock_settings.COHERE_EMBED_BATCH_SIZE = 96

            service = CohereEmbedService()
            assert service.is_enabled
            assert service.api_key == "test-key"

    def test_falls_back_to_rerank_api_key(self):
        with patch("src.services.embedding.cohere_embed_service.settings") as mock_settings:
            mock_settings.COHERE_EMBED_ENDPOINT = "https://api.cohere.com/v2/embed"
            mock_settings.COHERE_EMBED_API_KEY = None
            mock_settings.COHERE_RERANK_API_KEY = "rerank-key"
            mock_settings.COHERE_EMBED_MODEL = "embed-v4.0"
            mock_settings.COHERE_EMBED_DIMENSIONS = 1024
            mock_settings.COHERE_EMBED_BATCH_SIZE = 96

            service = CohereEmbedService()
            assert service.is_enabled
            assert service.api_key == "rerank-key"


class TestCohereEmbedTexts:
    """Test text embedding"""

    @pytest.fixture
    def service(self):
        with patch("src.services.embedding.cohere_embed_service.settings") as mock_settings:
            mock_settings.COHERE_EMBED_ENDPOINT = "https://api.cohere.com/v2/embed"
            mock_settings.COHERE_EMBED_API_KEY = "test-key"
            mock_settings.COHERE_RERANK_API_KEY = None
            mock_settings.COHERE_EMBED_MODEL = "embed-v4.0"
            mock_settings.COHERE_EMBED_DIMENSIONS = 1024
            mock_settings.COHERE_EMBED_BATCH_SIZE = 96
            yield CohereEmbedService()

    @pytest.mark.asyncio
    async def test_embed_single_text(self, service):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "embeddings": {"float": [[0.1] * 1024]}
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with patch("src.services.embedding.cohere_embed_service.get_circuit_breaker") as mock_breaker:
                mock_breaker.return_value = MagicMock(can_execute=MagicMock(return_value=True))

                result = await service.embed_text_single("hello world")
                assert len(result) == 1024

    @pytest.mark.asyncio
    async def test_embed_texts_payload(self, service):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "embeddings": {"float": [[0.1] * 1024, [0.2] * 1024]}
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with patch("src.services.embedding.cohere_embed_service.get_circuit_breaker") as mock_breaker:
                mock_breaker.return_value = MagicMock(can_execute=MagicMock(return_value=True))

                result = await service.embed_texts(["hello", "world"])
                assert len(result) == 2

                # Verify payload
                call_args = mock_client.post.call_args
                payload = call_args.kwargs["json"]
                assert payload["model"] == "embed-v4.0"
                assert payload["texts"] == ["hello", "world"]
                assert payload["input_type"] == "search_document"
                assert payload["embedding_types"] == ["float"]

    @pytest.mark.asyncio
    async def test_raises_when_disabled(self):
        with patch("src.services.embedding.cohere_embed_service.settings") as mock_settings:
            mock_settings.COHERE_EMBED_ENDPOINT = None
            mock_settings.COHERE_EMBED_API_KEY = None
            mock_settings.COHERE_RERANK_API_KEY = None
            mock_settings.COHERE_EMBED_MODEL = "embed-v4.0"
            mock_settings.COHERE_EMBED_DIMENSIONS = 1024
            mock_settings.COHERE_EMBED_BATCH_SIZE = 96

            service = CohereEmbedService()
            with pytest.raises(RuntimeError, match="not enabled"):
                await service.embed_texts(["test"])

    @pytest.mark.asyncio
    async def test_circuit_breaker_open(self, service):
        with patch("src.services.embedding.cohere_embed_service.get_circuit_breaker") as mock_breaker:
            mock_breaker.return_value = MagicMock(can_execute=MagicMock(return_value=False))

            with pytest.raises(RuntimeError, match="circuit breaker"):
                await service.embed_texts(["test"])


class TestCohereEmbedImage:
    """Test image embedding"""

    @pytest.mark.asyncio
    async def test_embed_image_payload(self):
        with patch("src.services.embedding.cohere_embed_service.settings") as mock_settings:
            mock_settings.COHERE_EMBED_ENDPOINT = "https://api.cohere.com/v2/embed"
            mock_settings.COHERE_EMBED_API_KEY = "test-key"
            mock_settings.COHERE_RERANK_API_KEY = None
            mock_settings.COHERE_EMBED_MODEL = "embed-v4.0"
            mock_settings.COHERE_EMBED_DIMENSIONS = 1024
            mock_settings.COHERE_EMBED_BATCH_SIZE = 96

            service = CohereEmbedService()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {
                "embeddings": {"float": [[0.5] * 1024]}
            }

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                with patch("src.services.embedding.cohere_embed_service.get_circuit_breaker") as mock_breaker:
                    mock_breaker.return_value = MagicMock(can_execute=MagicMock(return_value=True))

                    result = await service.embed_image("base64data")
                    assert len(result) == 1024

                    # Verify image payload format
                    call_args = mock_client.post.call_args
                    payload = call_args.kwargs["json"]
                    assert "images" in payload
                    assert payload["images"][0].startswith("data:image/jpeg;base64,")
                    assert "texts" not in payload
