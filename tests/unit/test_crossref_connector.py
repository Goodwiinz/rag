"""Tests for Crossref source connector."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.research_engine.connectors.crossref_connector import CrossrefConnector

SAMPLE_CROSSREF_RESPONSE = {
    "status": "ok",
    "message": {
        "items": [
            {
                "DOI": "10.1234/test.2024.001",
                "title": ["Deep Learning for NLP"],
                "author": [
                    {"given": "John", "family": "Smith"},
                    {"given": "Jane", "family": "Doe"},
                ],
                "abstract": "<jats:p>This paper explores deep learning.</jats:p>",
                "URL": "https://doi.org/10.1234/test.2024.001",
                "container-title": ["Journal of AI Research"],
                "is-referenced-by-count": 42,
                "published-print": {"date-parts": [[2024, 3]]},
            }
        ],
        "total-results": 1,
    },
}


@pytest.mark.asyncio
async def test_crossref_search_parses_response():
    connector = CrossrefConnector(mailto="test@example.com")
    mock_response = MagicMock()
    mock_response.json.return_value = SAMPLE_CROSSREF_RESPONSE
    mock_response.raise_for_status = MagicMock()

    with patch(
        "httpx.AsyncClient.get",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        results = await connector.search("deep learning NLP", max_results=10)

    assert len(results) == 1
    doc = results[0]
    assert doc.connector_type == "crossref"
    assert doc.external_id == "10.1234/test.2024.001"
    assert doc.title == "Deep Learning for NLP"
    assert doc.authors == ["John Smith", "Jane Doe"]
    assert "deep learning" in doc.abstract.lower()


@pytest.mark.asyncio
async def test_crossref_strips_jats_xml_from_abstract():
    connector = CrossrefConnector(mailto="test@example.com")
    mock_response = MagicMock()
    mock_response.json.return_value = SAMPLE_CROSSREF_RESPONSE
    mock_response.raise_for_status = MagicMock()

    with patch(
        "httpx.AsyncClient.get",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        results = await connector.search("test", max_results=10)

    assert "<jats:" not in (results[0].abstract or "")


@pytest.mark.asyncio
async def test_crossref_empty_response():
    connector = CrossrefConnector(mailto="test@example.com")
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": "ok",
        "message": {"items": [], "total-results": 0},
    }
    mock_response.raise_for_status = MagicMock()

    with patch(
        "httpx.AsyncClient.get",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        results = await connector.search("nonexistent topic", max_results=10)

    assert results == []
