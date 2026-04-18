"""Citation Extraction Service for Research Assistant.

Implements hybrid citation extraction pipeline:
1. ArXiv API (for ArXiv papers)
2. Semantic Scholar API (for citation metadata and networks)
3. CrossRef API (for DOI-based lookup)
4. PDF parsing (fallback)
5. Manual entry (last resort)
"""

import re
import time
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import aiohttp
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Document
from src.services.arxiv.arxiv_service import ArXivIngestionService
from src.shared.research_schemas import CitationCreate

logger = structlog.get_logger()


_citation_metrics_initialized = False
_citation_metrics_disabled = False


def _ensure_citation_metrics() -> None:
    """Create citation extraction metrics once."""
    global _citation_metrics_initialized, _citation_metrics_disabled

    if _citation_metrics_initialized or _citation_metrics_disabled:
        return

    try:
        from src.observability.metrics import MetricConfig, create_metrics

        create_metrics(
            [
                MetricConfig(
                    name="citation_extraction_duration_seconds",
                    description="Citation extraction duration in seconds",
                    unit="seconds",
                ),
                MetricConfig(
                    name="citation_extraction_total",
                    description="Total citation extraction attempts by status/source",
                    unit="requests",
                ),
            ]
        )
        _citation_metrics_initialized = True
    except Exception as exc:  # pragma: no cover - defensive observability guard
        _citation_metrics_disabled = True
        logger.warning("citation_metrics_init_failed", error=str(exc))


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
                    logger.warning(
                        "semantic_scholar_lookup_failed",
                        doi=doi,
                        status=response.status,
                    )
                    return None

        except Exception as e:
            logger.error("semantic_scholar_error", doi=doi, error=str(e))
            return None

    async def lookup_by_title(self, title: str) -> Optional[Dict[str, Any]]:
        """Lookup paper by title search and return best match."""
        try:
            url = f"{self.BASE_URL}/paper/search"
            params = {
                "query": title,
                "limit": 1,
                "fields": "title,authors,year,venue,citationCount,abstract,externalIds",
            }

            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    logger.warning(
                        "semantic_scholar_title_lookup_failed",
                        title=title[:120],
                        status=response.status,
                    )
                    return None

                data = await response.json()
                results = data.get("data") or []
                return results[0] if results else None

        except Exception as e:
            logger.error("semantic_scholar_error", title=title[:120], error=str(e))
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
                    logger.warning(
                        "crossref_lookup_failed", doi=doi, status=response.status
                    )
                    return None

        except Exception as e:
            logger.error("crossref_error", doi=doi, error=str(e))
            return None

    async def lookup_by_title(self, title: str) -> Optional[Dict[str, Any]]:
        """Lookup paper by title and return the best match."""
        try:
            url = f"{self.BASE_URL}/works"
            params = {
                "query.title": title,
                "rows": 1,
                "select": "title,author,published-print,published-online,container-title,DOI",
            }

            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    logger.warning(
                        "crossref_title_lookup_failed",
                        title=title[:120],
                        status=response.status,
                    )
                    return None

                data = await response.json()
                items = data.get("message", {}).get("items", [])
                return items[0] if items else None

        except Exception as e:
            logger.error("crossref_error", title=title[:120], error=str(e))
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
    4. PDF parsing - extract metadata from PDF file
    5. Manual entry - fallback
    """

    VALID_STRATEGIES = {"auto", "arxiv", "semantic_scholar", "crossref", "pdf", "manual"}

    def __init__(self, db: AsyncSession):
        """Initialize extraction service.

        Args:
            db: Database session
        """
        self.db = db

    @staticmethod
    def _normalize_arxiv_id(value: Optional[str]) -> Optional[str]:
        """Normalize ArXiv identifiers to canonical form like 2101.00001."""
        if not value:
            return None

        normalized = str(value).strip()
        normalized = normalized.replace("https://arxiv.org/abs/", "")
        normalized = normalized.replace("http://arxiv.org/abs/", "")
        normalized = normalized.replace("arXiv:", "").replace("arxiv:", "")
        return normalized or None

    @staticmethod
    def _extract_doi(value: Optional[str]) -> Optional[str]:
        """Extract DOI from raw text/URL when possible."""
        if not value:
            return None

        text = str(value).strip()
        match = re.search(r"(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)", text)
        if match:
            return match.group(1).rstrip(".,;")
        return None

    def _manual_fallback(
        self,
        title: Optional[str],
        arxiv_id: Optional[str] = None,
        doi: Optional[str] = None,
    ) -> Optional[CitationCreate]:
        """Create a manual citation fallback when remote sources fail."""
        clean_title = (title or "").strip()
        if not clean_title and not arxiv_id and not doi:
            return None

        return CitationCreate(
            document_title=clean_title or "Untitled paper",
            arxiv_id=self._normalize_arxiv_id(arxiv_id),
            doi=self._extract_doi(doi),
            metadata_source="manual",
            needs_review=True,
        )

    async def _resolve_document_identifiers(
        self, document_id: UUID
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Resolve arXiv/DOI/title hints from document metadata."""
        query = select(Document).where(Document.id == document_id)
        result = await self.db.execute(query)
        document = result.scalar_one_or_none()

        if not document:
            return None, None, None

        metadata = document.document_metadata or {}
        arxiv_candidates = [
            metadata.get("arxiv_id"),
            metadata.get("arxivId"),
            metadata.get("arxiv"),
            metadata.get("arxiv_url"),
            metadata.get("source_url"),
            metadata.get("url"),
        ]
        doi_candidates = [
            metadata.get("doi"),
            metadata.get("DOI"),
            metadata.get("doi_url"),
            metadata.get("url"),
            metadata.get("source_url"),
        ]

        arxiv_id = None
        for value in arxiv_candidates:
            normalized = self._normalize_arxiv_id(value)
            if normalized:
                arxiv_id = normalized
                break

        doi = None
        for value in doi_candidates:
            normalized = self._extract_doi(value)
            if normalized:
                doi = normalized
                break

        title = (metadata.get("title") or document.title or "").strip() or None

        return arxiv_id, doi, title

    def _record_extraction_metrics(
        self, status: str, source: str, duration: float, strategy: str
    ) -> None:
        """Record citation extraction metrics."""
        _ensure_citation_metrics()
        if _citation_metrics_disabled:
            return

        attributes = {
            "status": status,
            "source": source or "none",
            "strategy": strategy or "auto",
        }

        try:
            from src.observability.metrics import increment_counter, record_histogram

            increment_counter("citation_extraction_total", attributes=attributes)
            record_histogram(
                "citation_extraction_duration_seconds",
                duration,
                attributes=attributes,
            )
        except Exception as exc:  # pragma: no cover - defensive observability guard
            logger.warning(
                "citation_metrics_record_failed",
                error=str(exc),
                status=status,
                source=source,
            )

    async def extract_for_document(
        self, document_id: UUID, strategy: str = "auto"
    ) -> Tuple[Optional[CitationCreate], str]:
        """Extract citation metadata for a stored document."""
        arxiv_id, doi, title = await self._resolve_document_identifiers(document_id)

        if not arxiv_id and not doi and not title:
            logger.warning("document_metadata_missing_for_extraction", document_id=str(document_id))
            return None, "none"

        citation, source = await self.extract_hybrid(
            arxiv_id=arxiv_id,
            doi=doi,
            title=title,
            strategy=strategy,
            document_id=document_id,
        )

        if citation:
            citation.document_id = document_id

        return citation, source

    async def extract_from_arxiv(self, arxiv_id: str) -> Optional[CitationCreate]:
        """Extract citation metadata from ArXiv API.

        Args:
            arxiv_id: ArXiv identifier (e.g., "2101.00001")

        Returns:
            CitationCreate schema or None
        """
        try:
            normalized_arxiv_id = self._normalize_arxiv_id(arxiv_id)
            if not normalized_arxiv_id:
                return None

            async with ArXivIngestionService(self.db) as arxiv_service:
                # Search for the specific paper
                results = await arxiv_service.search_papers(
                    query=f"id:{normalized_arxiv_id}", max_results=1
                )

                if not results:
                    logger.warning("arxiv_paper_not_found", arxiv_id=normalized_arxiv_id)
                    return None

                paper = results[0]

                # Parse metadata
                citation = CitationCreate(
                    document_title=paper.get("title", ""),
                    authors=paper.get("authors", []),
                    year=paper.get("year"),
                    arxiv_id=normalized_arxiv_id,
                    abstract=paper.get("summary", ""),
                    venue=paper.get("primary_category", ""),  # ArXiv category as venue
                    metadata_source="arxiv",
                    needs_review=False,
                )

                logger.info(
                    "arxiv_extraction_success",
                    arxiv_id=normalized_arxiv_id,
                    title=(citation.document_title or "")[:50],
                )

                return citation

        except Exception as e:
            logger.error("arxiv_extraction_failed", arxiv_id=arxiv_id, error=str(e))
            return None

    async def extract_from_semantic_scholar(
        self,
        arxiv_id: Optional[str] = None,
        doi: Optional[str] = None,
        title: Optional[str] = None,
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
                    data = await client.lookup_by_arxiv_id(
                        self._normalize_arxiv_id(arxiv_id) or arxiv_id
                    )
                elif doi:
                    normalized_doi = self._extract_doi(doi) or doi
                    data = await client.lookup_by_doi(normalized_doi)
                elif title:
                    data = await client.lookup_by_title(title)
                else:
                    return None

                if not data:
                    return None

                # Extract external IDs
                external_ids = data.get("externalIds", {})

                # Parse author names
                authors = [author.get("name", "") for author in data.get("authors", [])]

                citation = CitationCreate(
                    document_title=data.get("title", ""),
                    authors=authors,
                    year=data.get("year"),
                    venue=data.get("venue", ""),
                    doi=external_ids.get("DOI"),
                    arxiv_id=self._normalize_arxiv_id(external_ids.get("ArXiv")),
                    abstract=data.get("abstract", ""),
                    metadata_source="semantic_scholar",
                    needs_review=False,
                )

                logger.info(
                    "semantic_scholar_extraction_success",
                    title=(citation.document_title or "")[:50],
                    citation_count=data.get("citationCount"),
                )

                return citation

        except Exception as e:
            logger.error("semantic_scholar_extraction_failed", error=str(e))
            return None

    async def extract_from_crossref(
        self,
        doi: Optional[str] = None,
        title: Optional[str] = None,
    ) -> Optional[CitationCreate]:
        """Extract citation metadata from CrossRef.

        Args:
            doi: Digital Object Identifier

        Returns:
            CitationCreate schema or None
        """
        try:
            async with CrossRefClient() as client:
                normalized_doi = self._extract_doi(doi) if doi else None
                if normalized_doi:
                    data = await client.lookup_by_doi(normalized_doi)
                elif title:
                    data = await client.lookup_by_title(title)
                else:
                    return None

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
                raw_venue = data.get("container-title")
                if isinstance(raw_venue, list):
                    venue = raw_venue[0] if raw_venue else ""
                else:
                    venue = str(raw_venue or "")

                raw_title = data.get("title")
                if isinstance(raw_title, list):
                    title_value = raw_title[0] if raw_title else ""
                else:
                    title_value = str(raw_title or "")

                citation = CitationCreate(
                    document_title=title_value,
                    authors=authors,
                    year=year,
                    venue=venue,
                    doi=normalized_doi or data.get("DOI"),
                    metadata_source="crossref",
                    needs_review=False,
                )

                logger.info(
                    "crossref_extraction_success",
                    doi=normalized_doi,
                    title=(citation.document_title or "")[:50],
                )

                return citation

        except Exception as e:
            logger.error("crossref_extraction_failed", doi=doi, error=str(e))
            return None

    async def extract_from_pdf(self, document_id: UUID) -> Optional[CitationCreate]:
        """Extract citation metadata from the PDF file itself using PyMuPDF.

        Reads the PDF's embedded metadata (title, author, creationDate) and
        scans the first page text for DOI/ArXiv identifiers and year.

        Args:
            document_id: Database document UUID

        Returns:
            CitationCreate with needs_review=True, or None on failure
        """
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.warning("pdf_extraction_fitz_unavailable")
            return None

        try:
            query = select(Document).where(Document.id == document_id)
            result = await self.db.execute(query)
            document = result.scalar_one_or_none()

            if not document or not document.file_path:
                logger.debug("pdf_extraction_no_document", document_id=str(document_id))
                return None

            pdf_doc = fitz.open(document.file_path)
            try:
                pdf_metadata = pdf_doc.metadata or {}
                first_page_text = ""
                if len(pdf_doc) > 0:
                    first_page_text = pdf_doc[0].get_text()
            finally:
                pdf_doc.close()

            # Title: prefer PDF metadata, fall back to document DB title
            title = (pdf_metadata.get("title") or "").strip()
            if not title:
                title = (document.title or "").strip()

            # Authors: split on ; or " and " (author delimiters), keep commas
            # intact so "Last, First" names stay together.
            raw_author = (pdf_metadata.get("author") or "").strip()
            authors: List[str] = []
            if raw_author:
                for part in re.split(r";|\band\b", raw_author):
                    name = part.strip()
                    if name:
                        authors.append(name)

            # DOI / ArXiv from first-page text
            doi = self._extract_doi(first_page_text)
            arxiv_id = None
            arxiv_match = re.search(
                r"arXiv:\s*(\d{4}\.\d{4,5}(?:v\d+)?)", first_page_text
            )
            if arxiv_match:
                arxiv_id = arxiv_match.group(1)
            if not arxiv_id:
                # Try arxiv.org URL pattern
                url_match = re.search(
                    r"arxiv\.org/abs/(\d{4}\.\d{4,5}(?:v\d+)?)", first_page_text
                )
                if url_match:
                    arxiv_id = url_match.group(1)

            # Year: from PDF creationDate (D:YYYYmmdd...) or first-page text
            year = None
            creation_date = pdf_metadata.get("creationDate") or ""
            date_match = re.search(r"D:(\d{4})", creation_date)
            if date_match:
                year = int(date_match.group(1))
            if not year:
                # Try 4-digit year near a copyright or date pattern on first page
                year_match = re.search(r"\b(19|20)\d{2}\b", first_page_text[:2000])
                if year_match:
                    year = int(year_match.group(0))

            if not title and not doi and not arxiv_id:
                return None

            citation = CitationCreate(
                document_title=title or "Untitled paper",
                authors=authors or None,
                year=year,
                doi=doi,
                arxiv_id=arxiv_id,
                metadata_source="pdf",
                needs_review=True,
            )

            logger.info(
                "pdf_extraction_success",
                document_id=str(document_id),
                title=(citation.document_title or "")[:50],
            )
            return citation

        except Exception as e:
            logger.error(
                "pdf_extraction_failed", document_id=str(document_id), error=str(e)
            )
            return None

    async def extract_hybrid(
        self,
        arxiv_id: Optional[str] = None,
        doi: Optional[str] = None,
        title: Optional[str] = None,
        strategy: str = "auto",
        document_id: Optional[UUID] = None,
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
        start_time = time.time()
        normalized_strategy = (strategy or "auto").lower()
        if normalized_strategy not in self.VALID_STRATEGIES:
            normalized_strategy = "auto"

        normalized_arxiv_id = self._normalize_arxiv_id(arxiv_id)
        normalized_doi = self._extract_doi(doi) if doi else None
        normalized_title = (title or "").strip() or None

        result: Optional[CitationCreate] = None
        source = "none"

        if normalized_strategy == "arxiv":
            if normalized_arxiv_id:
                result = await self.extract_from_arxiv(normalized_arxiv_id)
                source = "arxiv" if result else "none"
        elif normalized_strategy == "semantic_scholar":
            result = await self.extract_from_semantic_scholar(
                arxiv_id=normalized_arxiv_id,
                doi=normalized_doi,
                title=normalized_title,
            )
            source = "semantic_scholar" if result else "none"
        elif normalized_strategy == "crossref":
            result = await self.extract_from_crossref(
                doi=normalized_doi,
                title=normalized_title,
            )
            source = "crossref" if result else "none"
        elif normalized_strategy == "pdf":
            if document_id:
                result = await self.extract_from_pdf(document_id)
                source = "pdf" if result else "none"
        elif normalized_strategy == "manual":
            result = self._manual_fallback(
                title=normalized_title,
                arxiv_id=normalized_arxiv_id,
                doi=normalized_doi,
            )
            source = "manual" if result else "none"
        else:
            # AUTO strategy:
            # 1) ArXiv -> 2) Semantic Scholar -> 3) CrossRef -> 4) PDF -> 5) Manual
            if normalized_arxiv_id:
                result = await self.extract_from_arxiv(normalized_arxiv_id)
                if result:
                    source = "arxiv"

            if not result and (normalized_arxiv_id or normalized_doi or normalized_title):
                result = await self.extract_from_semantic_scholar(
                    arxiv_id=normalized_arxiv_id,
                    doi=normalized_doi,
                    title=normalized_title,
                )
                if result:
                    source = "semantic_scholar"

            if not result and (normalized_doi or normalized_title):
                result = await self.extract_from_crossref(
                    doi=normalized_doi,
                    title=normalized_title,
                )
                if result:
                    source = "crossref"

            if not result and document_id:
                result = await self.extract_from_pdf(document_id)
                if result:
                    source = "pdf"

            if not result:
                result = self._manual_fallback(
                    title=normalized_title,
                    arxiv_id=normalized_arxiv_id,
                    doi=normalized_doi,
                )
                if result:
                    source = "manual"

        duration = time.time() - start_time
        status = "success" if result else "failure"
        self._record_extraction_metrics(
            status=status,
            source=source,
            duration=duration,
            strategy=normalized_strategy,
        )

        if result:
            logger.info(
                "citation_extraction_success",
                source=source,
                strategy=normalized_strategy,
                duration_seconds=duration,
                arxiv_id=normalized_arxiv_id,
                doi=normalized_doi,
                title=(normalized_title or "")[:120],
            )
            return result, source

        logger.warning(
            "citation_extraction_failed_all_strategies",
            strategy=normalized_strategy,
            duration_seconds=duration,
            arxiv_id=normalized_arxiv_id,
            doi=normalized_doi,
            title=normalized_title,
        )
        return None, "none"
