"""Unit tests for SemanticScholarClient and CrossRefClient.

Tests HTTP interactions with mocked aiohttp sessions covering success,
not-found, error, and title-search paths.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.research.citation_extraction_service import (
    CrossRefClient,
    SemanticScholarClient,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(status: int, json_data: dict | None = None) -> MagicMock:
    """Create a mock aiohttp response with async context-manager support."""
    resp = AsyncMock()
    resp.status = status
    if json_data is not None:
        resp.json = AsyncMock(return_value=json_data)
    # Support `async with session.get(...) as response:`
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=resp)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


# ===========================================================================
# SemanticScholarClient
# ===========================================================================


class TestSemanticScholarClient:
    """Tests for SemanticScholarClient HTTP interactions."""

    @pytest.mark.asyncio
    async def test_lookup_by_arxiv_id_success(self) -> None:
        paper = {
            "title": "Test Paper",
            "authors": [{"name": "A. Author"}],
            "year": 2023,
            "venue": "NeurIPS",
            "citationCount": 42,
            "externalIds": {"ArXiv": "2301.07041", "DOI": "10.1000/test"},
        }

        client = SemanticScholarClient()
        client.session = MagicMock()
        client.session.get = MagicMock(return_value=_mock_response(200, paper))

        result = await client.lookup_by_arxiv_id("2301.07041")

        assert result is not None
        assert result["title"] == "Test Paper"
        assert result["citationCount"] == 42

    @pytest.mark.asyncio
    async def test_lookup_by_arxiv_id_not_found(self) -> None:
        client = SemanticScholarClient()
        client.session = MagicMock()
        client.session.get = MagicMock(return_value=_mock_response(404))

        result = await client.lookup_by_arxiv_id("0000.00000")

        assert result is None

    @pytest.mark.asyncio
    async def test_lookup_by_arxiv_id_server_error(self) -> None:
        client = SemanticScholarClient()
        client.session = MagicMock()
        client.session.get = MagicMock(return_value=_mock_response(500))

        result = await client.lookup_by_arxiv_id("2301.07041")

        assert result is None

    @pytest.mark.asyncio
    async def test_lookup_by_arxiv_id_network_exception(self) -> None:
        client = SemanticScholarClient()
        client.session = MagicMock()
        client.session.get = MagicMock(side_effect=ConnectionError("timeout"))

        result = await client.lookup_by_arxiv_id("2301.07041")

        assert result is None

    @pytest.mark.asyncio
    async def test_lookup_by_doi_success(self) -> None:
        paper = {
            "title": "DOI Paper",
            "authors": [],
            "year": 2022,
            "externalIds": {"DOI": "10.1000/test"},
        }

        client = SemanticScholarClient()
        client.session = MagicMock()
        client.session.get = MagicMock(return_value=_mock_response(200, paper))

        result = await client.lookup_by_doi("10.1000/test")

        assert result is not None
        assert result["title"] == "DOI Paper"

    @pytest.mark.asyncio
    async def test_lookup_by_doi_not_found(self) -> None:
        client = SemanticScholarClient()
        client.session = MagicMock()
        client.session.get = MagicMock(return_value=_mock_response(404))

        result = await client.lookup_by_doi("10.9999/missing")

        assert result is None

    @pytest.mark.asyncio
    async def test_lookup_by_title_success(self) -> None:
        search_result = {
            "data": [
                {
                    "title": "Matched Paper",
                    "authors": [{"name": "B. Author"}],
                    "year": 2021,
                    "externalIds": {},
                }
            ]
        }

        client = SemanticScholarClient()
        client.session = MagicMock()
        client.session.get = MagicMock(return_value=_mock_response(200, search_result))

        result = await client.lookup_by_title("Matched Paper")

        assert result is not None
        assert result["title"] == "Matched Paper"

    @pytest.mark.asyncio
    async def test_lookup_by_title_no_results(self) -> None:
        client = SemanticScholarClient()
        client.session = MagicMock()
        client.session.get = MagicMock(
            return_value=_mock_response(200, {"data": []})
        )

        result = await client.lookup_by_title("Nonexistent Paper")

        assert result is None

    @pytest.mark.asyncio
    async def test_lookup_by_title_api_error(self) -> None:
        client = SemanticScholarClient()
        client.session = MagicMock()
        client.session.get = MagicMock(return_value=_mock_response(429))

        result = await client.lookup_by_title("Rate Limited")

        assert result is None

    @pytest.mark.asyncio
    async def test_context_manager_sets_api_key_header(self) -> None:
        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value = mock_session

            async with SemanticScholarClient(api_key="test-key") as client:
                assert client.session is not None

            mock_session_cls.assert_called_once()
            call_kwargs = mock_session_cls.call_args
            assert call_kwargs.kwargs.get("headers", {}).get("x-api-key") == "test-key"


# ===========================================================================
# CrossRefClient
# ===========================================================================


class TestCrossRefClient:
    """Tests for CrossRefClient HTTP interactions."""

    @pytest.mark.asyncio
    async def test_lookup_by_doi_success(self) -> None:
        work = {
            "title": ["CrossRef Paper"],
            "author": [{"given": "Alice", "family": "Smith"}],
            "published-print": {"date-parts": [[2022, 1, 15]]},
            "container-title": ["Nature"],
            "DOI": "10.1038/test",
        }

        client = CrossRefClient()
        client.session = MagicMock()
        client.session.get = MagicMock(
            return_value=_mock_response(200, {"message": work})
        )

        result = await client.lookup_by_doi("10.1038/test")

        assert result is not None
        assert result["DOI"] == "10.1038/test"

    @pytest.mark.asyncio
    async def test_lookup_by_doi_not_found(self) -> None:
        client = CrossRefClient()
        client.session = MagicMock()
        client.session.get = MagicMock(return_value=_mock_response(404))

        result = await client.lookup_by_doi("10.9999/missing")

        assert result is None

    @pytest.mark.asyncio
    async def test_lookup_by_doi_server_error(self) -> None:
        client = CrossRefClient()
        client.session = MagicMock()
        client.session.get = MagicMock(return_value=_mock_response(503))

        result = await client.lookup_by_doi("10.1000/test")

        assert result is None

    @pytest.mark.asyncio
    async def test_lookup_by_doi_network_exception(self) -> None:
        client = CrossRefClient()
        client.session = MagicMock()
        client.session.get = MagicMock(side_effect=ConnectionError("DNS failure"))

        result = await client.lookup_by_doi("10.1000/test")

        assert result is None

    @pytest.mark.asyncio
    async def test_lookup_by_title_success(self) -> None:
        search_result = {
            "message": {
                "items": [
                    {
                        "title": ["Found via Title"],
                        "author": [{"given": "Bob", "family": "Jones"}],
                        "DOI": "10.1000/found",
                    }
                ]
            }
        }

        client = CrossRefClient()
        client.session = MagicMock()
        client.session.get = MagicMock(return_value=_mock_response(200, search_result))

        result = await client.lookup_by_title("Found via Title")

        assert result is not None
        assert result["DOI"] == "10.1000/found"

    @pytest.mark.asyncio
    async def test_lookup_by_title_no_results(self) -> None:
        client = CrossRefClient()
        client.session = MagicMock()
        client.session.get = MagicMock(
            return_value=_mock_response(200, {"message": {"items": []}})
        )

        result = await client.lookup_by_title("Nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_context_manager_sets_mailto_header(self) -> None:
        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value = mock_session

            async with CrossRefClient(mailto="test@example.com") as client:
                assert client.session is not None

            call_kwargs = mock_session_cls.call_args
            user_agent = call_kwargs.kwargs.get("headers", {}).get("User-Agent", "")
            assert "test@example.com" in user_agent
