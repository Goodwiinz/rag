"""Citation Extraction Service for Research Assistant.

Implements hybrid citation extraction pipeline:
1. ArXiv API (for ArXiv papers)
2. Semantic Scholar API (for citation metadata and networks)
3. CrossRef API (for DOI-based lookup)
4. PDF parsing (fallback)
5. Manual entry (last resort)
"""

import aiohttp
import asyncio
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models import Citation, Document
from src.services.arxiv_service import ArXivIngestionService
from src.shared.research_schemas import CitationCreate, CitationResponse

logger = structlog.get_logger()


# ============================================================================
# Semantic Scholar Client
# ============================================================================

class SemanticScholarClient:
    """Client for Semantic Scholar Academic Graph API.
    
    Rate limits: 100 requests/second (10,000/day for free tier)
    Docs: https://api.semanticscholar.org/api-docs/
    """
    
    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Semantic Scholar client.
        
        Args:
            api_key: Optional API key for higher rate limits
        """
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        """Async context manager entry."""
        headers = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key
            
        self.session = aiohttp.ClientSession(headers=headers)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
            
    async def lookup_by_arxiv_id(self, arxiv_id: str) -> Optional[Dict[str, Any]]:
        """Lookup paper by ArXiv ID.
        
        Args:
            arxiv_id: ArXiv identifier (e.g., "2101.00001")
            
        Returns:
            Paper metadata or None if not found
        """
        try:
            url = f"{self.BASE_URL}/paper/ARXIV:{arxiv_id}"
            params = {
                "fields": "title,authors,year,venue,citationCount,influentialCitationCount,abstract,externalIds"
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(
                        "semantic_scholar_lookup_success",
                        arxiv_id=arxiv_id,
                        citation_count=data.get("citationCount"),
                    )
                    return data
                elif response.status == 404:
                    logger.debug("semantic_scholar_not_found", arxiv_id=arxiv_id)
                    return None
                else:
                    logger.warning(
                        "semantic_scholar_lookup_failed",
                        arxiv_id=arxiv_id,
                        status=response.status,
                    )
                    return None
                    
        except Exception as e:
            logger.error("semantic_scholar_error", arxiv_id=arxiv_id, error=str(e))
            return None
            
    async def lookup_by_doi(self, doi: str) -> Optional[Dict[str, Any]]:
        """Lookup paper by DOI.
        
        Args:
            doi: Digital Object Identifier
            
        Returns:
            Paper metadata or None if not found
        """
        try:
            url = f"{self.BASE_URL}/paper/DOI:{doi}"
            params = {
                "fields": "title,authors,year,venue,citationCount,abstract,externalIds"
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 404:
                    logger.debug("semantic_scholar_not_found", doi=doi)
                    return None
                else:
                    logger.warning("semantic_scholar_lookup_failed", doi=doi, status=response.status)
                    return None
                    
        except Exception as e:
            logger.error("semantic_scholar_error", doi=doi, error=str(e))
            return None


# ============================================================================
# CrossRef Client
# ============================================================================

class CrossRefClient:
    """Client for CrossRef REST API.
    
    Rate limits: 50 requests/second (with mailto header)
    Docs: https://www.crossref.org/documentation/retrieve-metadata/rest-api/
    """
    
    BASE_URL = "https://api.crossref.org"
    
    def __init__(self, mailto: str = "research-assistant@example.com"):
        """Initialize CrossRef client.
        
        Args:
            mailto: Email for polite pool (higher rate limit)
        """
        self.mailto = mailto
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        """Async context manager entry."""
        headers = {"User-Agent": f"ResearchAssistant/1.0 (mailto:{self.mailto})"}
        self.session = aiohttp.ClientSession(headers=headers)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
            
    async def lookup_by_doi(self, doi: str) -> Optional[Dict[str, Any]]:
        """Lookup paper by DOI.
        
        Args:
            doi: Digital Object Identifier
            
        Returns:
            Paper metadata or None if not found
        """
        try:
            url = f"{self.BASE_URL}/works/{doi}"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("message")
                elif response.status == 404:
                    logger.debug("crossref_not_found", doi=doi)
                    return None
                else:
                    logger.warning("crossref_lookup_failed", doi=doi, status=response.status)
                    return None
                    
        except Exception as e:
            logger.error("crossref_error", doi=doi, error=str(e))
            return None


# ============================================================================
# Citation Extraction Service
# ============================================================================

class CitationExtractionService:
    """Hybrid citation extraction service.
    
    Extraction strategies (in order of priority):
    1. ArXiv API - for ArXiv papers (90%+ accuracy)
    2. Semantic Scholar - for citation networks and metadata
    3. CrossRef - for DOI-based lookup
    4. PDF parsing - for references section (TODO)
    5. Manual entry - fallback
    """
    
    def __init__(self, db: AsyncSession):
        """Initialize extraction service.
        
        Args:
            db: Database session
        """
        self.db = db
        
    async def extract_from_arxiv(self, arxiv_id: str) -> Optional[CitationCreate]:
        """Extract citation metadata from ArXiv API.
        
        Args:
            arxiv_id: ArXiv identifier (e.g., "2101.00001")
            
        Returns:
            CitationCreate schema or None
        """
        try:
            async with ArXivIngestionService(self.db) as arxiv_service:
                # Search for the specific paper
                results = await arxiv_service.search_papers(
                    query=f"id:{arxiv_id}",
                    max_results=1
                )
                
                if not results:
                    logger.warning("arxiv_paper_not_found", arxiv_id=arxiv_id)
                    return None
                    
                paper = results[0]
                
                # Parse metadata
                citation = CitationCreate(
                    documentTitle=paper.get("title", ""),
                    authors=paper.get("authors", []),
                    year=paper.get("year"),
                    arxivId=arxiv_id,
                    abstract=paper.get("summary", ""),
                    venue=paper.get("primary_category", ""),  # ArXiv category as venue
                    metadataSource="arxiv",
                    needsReview=False,
                )
                
                logger.info(
                    "arxiv_extraction_success",
                    arxiv_id=arxiv_id,
                    title=citation.documentTitle[:50],
                )
                
                return citation
                
        except Exception as e:
            logger.error("arxiv_extraction_failed", arxiv_id=arxiv_id, error=str(e))
            return None
            
    async def extract_from_semantic_scholar(
        self,
        arxiv_id: Optional[str] = None,
        doi: Optional[str] = None
    ) -> Optional[CitationCreate]:
        """Extract citation metadata from Semantic Scholar.
        
        Args:
            arxiv_id: Optional ArXiv ID
            doi: Optional DOI
            
        Returns:
            CitationCreate schema or None
        """
        try:
            async with SemanticScholarClient() as client:
                if arxiv_id:
                    data = await client.lookup_by_arxiv_id(arxiv_id)
                elif doi:
                    data = await client.lookup_by_doi(doi)
                else:
                    return None
                    
                if not data:
                    return None
                    
                # Extract external IDs
                external_ids = data.get("externalIds", {})
                
                # Parse author names
                authors = [
                    author.get("name", "")
                    for author in data.get("authors", [])
                ]
                
                citation = CitationCreate(
                    documentTitle=data.get("title", ""),
                    authors=authors,
                    year=data.get("year"),
                    venue=data.get("venue", ""),
                    doi=external_ids.get("DOI"),
                    arxivId=external_ids.get("ArXiv"),
                    abstract=data.get("abstract", ""),
                    metadataSource="semantic_scholar",
                    needsReview=False,
                )
                
                logger.info(
                    "semantic_scholar_extraction_success",
                    title=citation.documentTitle[:50],
                    citation_count=data.get("citationCount"),
                )
                
                return citation
                
        except Exception as e:
            logger.error("semantic_scholar_extraction_failed", error=str(e))
            return None
            
    async def extract_from_crossref(self, doi: str) -> Optional[CitationCreate]:
        """Extract citation metadata from CrossRef.
        
        Args:
            doi: Digital Object Identifier
            
        Returns:
            CitationCreate schema or None
        """
        try:
            async with CrossRefClient() as client:
                data = await client.lookup_by_doi(doi)
                
                if not data:
                    return None
                    
                # Parse author names
                authors = []
                for author in data.get("author", []):
                    given = author.get("given", "")
                    family = author.get("family", "")
                    authors.append(f"{given} {family}".strip())
                    
                # Extract year from published date
                year = None
                published = data.get("published-print") or data.get("published-online")
                if published and "date-parts" in published:
                    date_parts = published["date-parts"][0]
                    if date_parts:
                        year = date_parts[0]
                        
                # Get venue (journal or conference)
                venue = data.get("container-title", [""])[0] if data.get("container-title") else ""
                
                citation = CitationCreate(
                    documentTitle=data.get("title", [""])[0],
                    authors=authors,
                    year=year,
                    venue=venue,
                    doi=doi,
                    metadataSource="crossref",
                    needsReview=False,
                )
                
                logger.info("crossref_extraction_success", doi=doi, title=citation.documentTitle[:50])
                
                return citation
                
        except Exception as e:
            logger.error("crossref_extraction_failed", doi=doi, error=str(e))
            return None
            
    async def extract_hybrid(
        self,
        arxiv_id: Optional[str] = None,
        doi: Optional[str] = None,
        title: Optional[str] = None,
    ) -> Tuple[Optional[CitationCreate], str]:
        """Hybrid extraction using multiple sources.

        Strategy:
        1. Try ArXiv if arxiv_id provided
        2. Try Semantic Scholar (works for both ArXiv and DOI)
        3. Try CrossRef if DOI provided
        4. Return best result with confidence score

        Args:
            arxiv_id: Optional ArXiv identifier
            doi: Optional DOI
            title: Optional paper title (not yet implemented)

        Returns:
            Tuple of (CitationCreate or None, extraction_source)
        """
        import time
        start_time = time.time()

        # Strategy 1: ArXiv (highest accuracy for ArXiv papers)
        if arxiv_id:
            result = await self.extract_from_arxiv(arxiv_id)
            if result:
                duration = time.time() - start_time
                logger.info(
                    "citation_extraction_success",
                    source="arxiv",
                    duration_seconds=duration,
                    arxiv_id=arxiv_id,
                )
                return result, "arxiv"

        # Strategy 2: Semantic Scholar (good for both ArXiv and DOI)
        if arxiv_id or doi:
            result = await self.extract_from_semantic_scholar(arxiv_id=arxiv_id, doi=doi)
            if result:
                duration = time.time() - start_time
                logger.info(
                    "citation_extraction_success",
                    source="semantic_scholar",
                    duration_seconds=duration,
                    arxiv_id=arxiv_id,
                    doi=doi,
                )
                return result, "semantic_scholar"

        # Strategy 3: CrossRef (DOI-based)
        if doi:
            result = await self.extract_from_crossref(doi)
            if result:
                duration = time.time() - start_time
                logger.info(
                    "citation_extraction_success",
                    source="crossref",
                    duration_seconds=duration,
                    doi=doi,
                )
                return result, "crossref"

        # Strategy 4: PDF parsing (TODO)
        # Strategy 5: Manual entry (handled by frontend)

        duration = time.time() - start_time
        logger.warning(
            "citation_extraction_failed_all_strategies",
            duration_seconds=duration,
            arxiv_id=arxiv_id,
            doi=doi,
            title=title,
        )

        return None, "none"
