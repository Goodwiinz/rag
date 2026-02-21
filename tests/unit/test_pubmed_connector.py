"""Tests for PubMed source connector."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.services.research_engine.connectors.pubmed_connector import PubMedConnector
from src.services.research_engine.connectors.base import SourceDocument


SAMPLE_ESEARCH_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<eSearchResult>
    <Count>1</Count>
    <IdList>
        <Id>12345678</Id>
    </IdList>
</eSearchResult>"""


SAMPLE_EFETCH_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
    <PubmedArticle>
        <MedlineCitation>
            <PMID>12345678</PMID>
            <Article>
                <ArticleTitle>Neural Networks in Medicine</ArticleTitle>
                <Abstract>
                    <AbstractText>This study examines neural network applications.</AbstractText>
                </Abstract>
                <AuthorList>
                    <Author>
                        <ForeName>Alice</ForeName>
                        <LastName>Johnson</LastName>
                    </Author>
                </AuthorList>
            </Article>
            <MeshHeadingList>
                <MeshHeading>
                    <DescriptorName>Neural Networks, Computer</DescriptorName>
                </MeshHeading>
            </MeshHeadingList>
        </MedlineCitation>
    </PubmedArticle>
</PubmedArticleSet>"""


@pytest.fixture
def pubmed_mocks():
    mock_search_resp = MagicMock()
    mock_search_resp.text = SAMPLE_ESEARCH_RESPONSE
    mock_search_resp.raise_for_status = MagicMock()

    mock_fetch_resp = MagicMock()
    mock_fetch_resp.text = SAMPLE_EFETCH_RESPONSE
    mock_fetch_resp.raise_for_status = MagicMock()

    return mock_search_resp, mock_fetch_resp


@pytest.mark.asyncio
async def test_pubmed_search_two_step(pubmed_mocks):
    connector = PubMedConnector()
    mock_search_resp, mock_fetch_resp = pubmed_mocks

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=[mock_search_resp, mock_fetch_resp]):
        results = await connector.search("neural networks medicine", max_results=10)

    assert len(results) == 1
    doc = results[0]
    assert doc.connector_type == "pubmed"
    assert doc.external_id == "12345678"
    assert doc.title == "Neural Networks in Medicine"
    assert doc.authors == ["Alice Johnson"]
    assert "neural network" in doc.abstract.lower()


@pytest.mark.asyncio
async def test_pubmed_extracts_mesh_terms(pubmed_mocks):
    connector = PubMedConnector()
    mock_search_resp, mock_fetch_resp = pubmed_mocks

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=[mock_search_resp, mock_fetch_resp]):
        results = await connector.search("test", max_results=10)

    assert "Neural Networks, Computer" in results[0].metadata.get("mesh_terms", [])


@pytest.mark.asyncio
async def test_pubmed_empty_search_returns_empty_list():
    connector = PubMedConnector()
    empty_esearch = '<?xml version="1.0"?><eSearchResult><IdList/></eSearchResult>'
    mock_resp = MagicMock()
    mock_resp.text = empty_esearch
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        results = await connector.search("nothing", max_results=10)

    assert results == []
