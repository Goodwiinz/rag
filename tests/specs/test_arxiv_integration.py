"""
Test Suite for ArXiv Integration

Comprehensive tests for arXiv paper ingestion, search, and evaluation functionality.
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from src.services.arxiv_service import ArXivIngestionService
from src.services.arxiv_search_service import ArXivSearchService
from src.models.document import Document, DocumentMetadata, ProcessingStatus


class TestArXivIngestionService:
    """Test cases for ArXivIngestionService"""

    @pytest.fixture
    async def arxiv_service(self):
        """Create arxiv service for testing"""
        config = {
            'arxiv_download_dir': 'test_data/arxiv',
            'max_concurrent_downloads': 5
        }
        service = ArXivIngestionService(config)
        async with service:
            yield service

    @pytest.fixture
    def sample_paper_xml(self):
        """Sample arXiv XML response"""
        return """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
            <entry>
                <id>http://arxiv.org/abs/2301.07041</id>
                <updated>2023-01-18T15:45:08Z</updated>
                <published>2023-01-17T19:21:05Z</published>
                <title>Attention Is All You Need</title>
                <summary>Transformer architecture paper abstract...</summary>
                <author>
                    <name>Ashish Vaswani</name>
                </author>
                <author>
                    <name>Noam Shazeer</name>
                </author>
                <category term="cs.LG" scheme="http://arxiv.org/schemas/atom"/>
                <category term="cs.CL" scheme="http://arxiv.org/schemas/atom"/>
                <link href="http://arxiv.org/pdf/2301.07041.pdf" title="pdf" type="application/pdf"/>
            </entry>
        </feed>"""

    @pytest.mark.asyncio
    async def test_parse_arxiv_entry(self, arxiv_service, sample_paper_xml):
        """Test parsing arXiv XML entry"""
        import xml.etree.ElementTree as ET

        root = ET.fromstring(sample_paper_xml)
        namespaces = {
            'atom': 'http://www.w3.org/2005/Atom',
            'arxiv': 'http://arxiv.org/schemas/atom'
        }
        entry = root.find('atom:entry', namespaces)

        paper_data = arxiv_service._parse_arxiv_entry(entry, namespaces)

        assert paper_data['id'] == '2301.07041'
        assert paper_data['title'] == 'Attention Is All You Need'
        assert 'Ashish Vaswani' in paper_data['authors']
        assert 'cs.LG' in paper_data['categories']
        assert paper_data['links']['pdf'] == 'http://arxiv.org/pdf/2301.07041.pdf'

    @pytest.mark.asyncio
    async def test_search_papers(self, arxiv_service):
        """Test searching arXiv papers"""
        mock_response = Mock()
        mock_response.text = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
            <totalResults>1</totalResults>
            <entry>
                <id>http://arxiv.org/abs/test123</id>
                <title>Test Paper</title>
                <summary>Test abstract</summary>
                <published>2023-01-01T00:00:00Z</updated>
                <category term="cs.AI" scheme="http://arxiv.org/schemas/atom"/>
            </entry>
        </feed>"""

        with patch.object(arxiv_service.session, 'get') as mock_get:
            mock_get.return_value.__aenter__.return_value.raise_for_status = AsyncMock()
            mock_get.return_value.__aenter__.return_value.text = asyncio.create_task(
                asyncio.Future()
            )
            mock_get.return_value.__aenter__.return_value.text.set_result(mock_response.text)

            papers = await arxiv_service.search_papers(
                query="machine learning",
                max_results=10
            )

            assert len(papers) == 1
            assert papers[0]['title'] == 'Test Paper'

    @pytest.mark.asyncio
    async def test_download_paper_pdf(self, arxiv_service):
        """Test downloading paper PDF"""
        pdf_content = b"PDF content here"

        with patch.object(arxiv_service.session, 'get') as mock_get:
            mock_response = AsyncMock()
            mock_response.raise_for_status = AsyncMock()
            mock_response.read = AsyncMock(return_value=pdf_content)
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_response)

            # Mock path exists check
            with patch('pathlib.Path.exists', return_value=False):
                with patch('aiofiles.open', create=True) as mock_open:
                    mock_file = AsyncMock()
                    mock_open.return_value.__aenter__ = AsyncMock(return_value=mock_file)

                    content = await arxiv_service.download_paper_pdf("test123")

                    assert content == pdf_content

    @pytest.mark.asyncio
    async def test_extract_pdf_content(self, arxiv_service):
        """Test PDF content extraction"""
        # Create a simple PDF mock
        pdf_content = b"PDF content"

        with patch('PyPDF2.PdfReader') as mock_reader:
            mock_page = Mock()
            mock_page.extract_text.return_value = "Page 1 content"

            mock_pdf = Mock()
            mock_pdf.pages = [mock_page]
            mock_pdf.metadata = {'/Title': 'Test PDF'}

            mock_reader.return_value = mock_pdf

            with patch('io.BytesIO'):
                result = await arxiv_service.extract_pdf_content(pdf_content)

                assert 'full_text' in result
                assert 'Page 1 content' in result['full_text']
                assert result['num_pages'] == 1

    @pytest.mark.asyncio
    async def test_ingest_papers(self, arxiv_service):
        """Test paper ingestion"""
        papers = [{
            'id': 'test123',
            'title': 'Test Paper',
            'authors': ['Test Author'],
            'abstract': 'Test abstract',
            'published': '2023-01-01T00:00:00Z',
            'updated': '2023-01-01T00:00:00Z',
            'categories': ['cs.AI'],
            'links': {},
            'primary_category': 'cs.AI'
        }]

        with patch.object(arxiv_service, 'download_paper_pdf', return_value=None):
            with patch.object(arxiv_service, 'extract_pdf_content', return_value={}):
                documents = await arxiv_service.ingest_papers(
                    papers=papers,
                    download_pdfs=False,
                    extract_content=False,
                    batch_size=1
                )

                assert len(documents) == 1
                assert documents[0].metadata.title == 'Test Paper'
                assert documents[0].status == ProcessingStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_create_evaluation_dataset(self, arxiv_service):
        """Test evaluation dataset creation"""
        papers = [{
            'id': 'test123',
            'title': 'Test Paper on Machine Learning',
            'authors': ['Test Author'],
            'abstract': 'This paper presents a new ML algorithm.',
            'published': '2023-01-01T00:00:00Z',
            'updated': '2023-01-01T00:00:00Z',
            'categories': ['cs.LG', 'cs.AI'],
            'links': {},
            'primary_category': 'cs.LG'
        }]

        with patch('aiofiles.open', create=True) as mock_open:
            mock_file = AsyncMock()
            mock_open.return_value.__aenter__ = AsyncMock(return_value=mock_file)

            dataset = await arxiv_service.create_evaluation_dataset(
                papers=papers,
                num_questions=3
            )

            assert 'dataset_info' in dataset
            assert 'test_cases' in dataset
            assert len(dataset['test_cases']) == 1
            assert len(dataset['test_cases'][0]['questions']) == 3

    def test_get_category_statistics(self, arxiv_service):
        """Test category statistics calculation"""
        papers = [
            {
                'categories': ['cs.LG', 'cs.AI'],
                'primary_category': 'cs.LG'
            },
            {
                'categories': ['cs.CV', 'cs.LG'],
                'primary_category': 'cs.CV'
            },
            {
                'categories': ['math.OC', 'cs.LG'],
                'primary_category': 'math.OC'
            }
        ]

        stats = arxiv_service.get_category_statistics(papers)

        assert stats['total_papers'] == 3
        assert stats['unique_categories'] == 3
        assert 'cs.LG' in stats['category_distribution']
        assert stats['category_distribution']['cs.LG'] == 3


class TestArXivSearchService:
    """Test cases for ArXivSearchService"""

    @pytest.fixture
    def search_service(self):
        """Create arXiv search service"""
        return ArXivSearchService()

    @pytest.fixture
    def sample_elastic_response(self):
        """Sample Elasticsearch response"""
        return {
            'hits': {
                'hits': [
                    {
                        '_id': 'test123',
                        '_score': 0.95,
                        '_source': {
                            'title': 'Test Paper',
                            'abstract': 'Test abstract',
                            'authors': [{'name': 'Test Author'}],
                            'categories': ['cs.LG'],
                            'published': '2023-01-01T00:00:00Z',
                            'arxiv_id': 'test123',
                            'citation_count': 10
                        },
                        'highlight': {
                            'title': ['<em>Test Paper</em>'],
                            'abstract': ['<em>Test abstract</em>']
                        }
                    }
                ]
            }
        }

    @pytest.mark.asyncio
    async def test_search_papers(self, search_service, sample_elastic_response):
        """Test paper search"""
        with patch.object(search_service, 'es_client') as mock_es:
            mock_es.search.return_value = sample_elastic_response

            results = await search_service.search_papers(
                query="machine learning",
                filters={'categories': ['cs.LG']},
                limit=10
            )

            assert len(results) == 1
            assert results[0].title == 'Test Paper'
            assert results[0].score == 0.95

    @pytest.mark.asyncio
    async def test_build_arxiv_query(self, search_service):
        """Test Elasticsearch query building"""
        query = search_service._build_arxiv_query(
            query="machine learning",
            filters={'categories': ['cs.LG'], 'authors': ['Test Author']},
            limit=10,
            offset=0,
            sort_by="relevance",
            boost_recent=True,
            recency_days=30
        )

        assert 'query' in query
        assert 'bool' in query['query']
        assert 'size' in query
        assert query['size'] == 10
        assert query['from'] == 0

    @pytest.mark.asyncio
    async def test_get_similar_papers(self, search_service):
        """Test finding similar papers"""
        ref_doc = {
            '_source': {
                'title': 'Reference Paper',
                'abstract': 'Reference abstract',
                'content': 'Full content'
            }
        }

        with patch.object(search_service, 'es_client') as mock_es:
            mock_es.get.return_value = ref_doc
            mock_es.search.return_value = {
                'hits': {
                    'hits': [{'_score': 0.8, '_id': 'similar123'}]
                }
            }

            results = await search_service.get_similar_papers('test123')

            mock_es.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_category_hierarchy(self, search_service):
        """Test category hierarchy retrieval"""
        hierarchy = await search_service.get_category_hierarchy('cs.LG')

        assert hierarchy['category'] == 'cs.LG'
        assert hierarchy['main_category'] == 'cs'
        assert hierarchy['subcategory'] == 'LG'
        assert 'related_categories' in hierarchy

    @pytest.mark.asyncio
    async def test_get_author_papers(self, search_service):
        """Test getting papers by author"""
        with patch.object(search_service, 'es_client') as mock_es:
            mock_es.search.return_value = {
                'hits': {
                    'hits': [{'_id': 'paper123'}]
                }
            }
            mock_es.get.return_value = {
                '_source': {
                    'title': 'Author Paper',
                    'authors': [{'name': 'Test Author'}],
                    'published': '2023-01-01T00:00:00Z'
                }
            }

            results = await search_service.get_author_papers('Test Author')

            assert mock_es.search.called
            assert mock_es.get.called


class TestArXivIntegration:
    """Integration tests for ArXiv functionality"""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """Test complete workflow from search to evaluation"""
        # This test would require actual arXiv API calls
        # Use mock responses for CI/CD

        # 1. Search papers
        # 2. Download PDFs
        # 3. Extract content
        # 4. Ingest into system
        # 5. Create evaluation dataset
        # 6. Test search on ingested papers

        pytest.skip("Integration test - requires actual API calls")

    def test_cli_interface(self):
        """Test CLI interface"""
        from scripts.arxiv_cli import main
        import sys
        from io import StringIO

        # Capture output
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        try:
            # Test help
            with patch('sys.argv', ['arxiv_cli.py', '--help']):
                with pytest.raises(SystemExit):
                    main()
        finally:
            sys.stdout = old_stdout


@pytest.mark.asyncio
async def test_arxiv_api_endpoints():
    """Test arXiv API endpoints"""
    from fastapi.testclient import TestClient
    from src.main import app

    client = TestClient(app)

    # Test search endpoint (requires auth)
    response = client.post(
        "/api/v1/arxiv/search",
        json={"query": "machine learning", "max_results": 10}
    )
    # Should return 401 without auth
    assert response.status_code == 401

    # Test categories endpoint (requires auth)
    response = client.get("/api/v1/arxiv/categories")
    assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v"])