# SciSpace Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add 5 SciSpace-inspired features to the RAG system: Literature Review Matrix, Deep Table/Math Extraction, Scholarly Tone Engine, Crossref/PubMed Connectors, and AI Integrity Detector.

**Architecture:** Feature-parallel vertical slices. Each feature is an independent module (model + service + API + frontend) that hooks into existing infrastructure. Shared foundation layer adds new agent type and connector registry first.

**Tech Stack:** FastAPI, SQLAlchemy, Celery, CrewAI, httpx, Camelot/Tabula, HuggingFace transformers, TanStack Table, KaTeX

**Design Doc:** `docs/plans/2026-02-20-scispace-integration-design.md`

---

## Task 0: Shared Foundation

### Task 0.1: Add STRUCTURED_EXTRACTION Agent Type

**Files:**

- Modify: `backend/src/services/search/multi_agent_search_service_v2.py:53-62`

**Step 1: Add the new agent type to the enum**

In `multi_agent_search_service_v2.py`, add to the `AgentType` enum:

```python
class AgentType(Enum):
    """Types of search agents"""

    RETRIEVAL = "retrieval"
    GRAPH_NAVIGATION = "graph_navigation"
    QUALITY_ASSURANCE = "quality_assurance"
    ANSWER_SYNTHESIS = "answer_synthesis"
    QUERY_UNDERSTANDING = "query_understanding"
    RESULT_ENRICHMENT = "result_enrichment"
    CONTEXT_ANALYSIS = "context_analysis"
    STRUCTURED_EXTRACTION = "structured_extraction"  # SciSpace: extraction matrix
```

**Step 2: Verify no regressions**

Run: `cd /Users/goodwiinz/development/RAG_system && python -c "from src.services.search.multi_agent_search_service_v2 import AgentType; print(AgentType.STRUCTURED_EXTRACTION)"`
Expected: `AgentType.STRUCTURED_EXTRACTION`

**Step 3: Commit**

```bash
git add backend/src/services/search/multi_agent_search_service_v2.py
git commit -m "feat: add STRUCTURED_EXTRACTION agent type for extraction matrix"
```

### Task 0.2: Add Crossref/PubMed Connectors to Registry

**Files:**

- Modify: `backend/src/services/research_engine/connectors/__init__.py`

This will be done as part of Task 4 (Feature 4). No separate action needed here — the registry updates when we create the connectors.

### Task 0.3: Add SciSpace Schemas

**Files:**

- Create: `backend/src/shared/scispace_schemas.py`
- Test: `tests/unit/test_scispace_schemas.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_scispace_schemas.py
"""Tests for SciSpace shared schemas."""

import pytest
from pydantic import ValidationError


def test_tone_option_valid():
    from src.shared.scispace_schemas import ToneOption
    assert ToneOption.ACADEMIC == "academic"
    assert ToneOption.SIMPLIFIED == "simplified"
    assert ToneOption.CONCISE == "concise"
    assert ToneOption.EXPANDED == "expanded"


def test_rewrite_request_valid():
    from src.shared.scispace_schemas import RewriteRequest
    req = RewriteRequest(text="Some text to rewrite here.", tone="academic")
    assert req.preserve_citations is True  # default


def test_rewrite_request_short_text_rejected():
    from src.shared.scispace_schemas import RewriteRequest
    with pytest.raises(ValidationError):
        RewriteRequest(text="Too short", tone="academic")


def test_integrity_score_response():
    from src.shared.scispace_schemas import IntegrityScoreResponse
    resp = IntegrityScoreResponse(
        document_id="550e8400-e29b-41d4-a716-446655440000",
        ai_probability=0.73,
        human_probability=0.27,
        method="roberta-base-openai-detector",
    )
    assert resp.ai_probability == 0.73


def test_extraction_column_schema():
    from src.shared.scispace_schemas import ExtractionColumn
    col = ExtractionColumn(name="Methodology", description="Research methodology used")
    assert col.name == "Methodology"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/goodwiinz/development/RAG_system && python -m pytest tests/unit/test_scispace_schemas.py -v`
Expected: FAIL (ImportError)

**Step 3: Write implementation**

```python
# backend/src/shared/scispace_schemas.py
"""SciSpace integration schemas shared across features."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator


# ============================================================================
# Feature 1: Extraction Matrix
# ============================================================================


class ExtractionColumn(BaseModel):
    """A column definition for the extraction matrix."""

    name: str = Field(..., min_length=1, max_length=100, description="Column header name")
    description: Optional[str] = Field(None, max_length=500, description="What to extract")


class ExtractionCellResponse(BaseModel):
    """A single cell in the extraction matrix."""

    document_id: UUID
    column_name: str
    value: Optional[str] = None
    citation_snippet: Optional[str] = None
    confidence: Optional[float] = None


class CreateMatrixRequest(BaseModel):
    """Request to create an extraction matrix."""

    name: str = Field(..., min_length=1, max_length=255)
    columns: List[ExtractionColumn] = Field(..., min_length=1, max_length=20)


class TriggerExtractionRequest(BaseModel):
    """Request to trigger extraction on selected documents."""

    document_ids: List[UUID] = Field(..., min_length=1, max_length=100)


# ============================================================================
# Feature 3: Tone Engine
# ============================================================================


class ToneOption(str, Enum):
    """Available tone adjustment options."""

    ACADEMIC = "academic"
    SIMPLIFIED = "simplified"
    CONCISE = "concise"
    EXPANDED = "expanded"


class RewriteRequest(BaseModel):
    """Request to rewrite text with a specific tone."""

    text: str = Field(..., min_length=20, description="Text to rewrite (min 20 chars)")
    tone: ToneOption
    preserve_citations: bool = Field(True, description="Maintain citation markers [1], [2], etc.")
    model: Optional[str] = Field(None, description="LLM model override")

    @validator("text")
    def text_not_too_short(cls, v):
        if len(v.split()) < 5:
            raise ValueError("Text must contain at least 5 words")
        return v


class RewriteResponse(BaseModel):
    """Response from the tone engine."""

    original: str
    rewritten: str
    tone_applied: ToneOption
    citations_preserved: List[str] = Field(default_factory=list)


# ============================================================================
# Feature 5: Integrity Detector
# ============================================================================


class IntegritySegmentScore(BaseModel):
    """AI detection score for a text segment."""

    text_preview: str = Field(..., max_length=200)
    ai_probability: float = Field(..., ge=0.0, le=1.0)


class IntegrityScoreResponse(BaseModel):
    """Full integrity score for a document."""

    document_id: str
    ai_probability: float = Field(..., ge=0.0, le=1.0)
    human_probability: float = Field(..., ge=0.0, le=1.0)
    method: str = "roberta-base-openai-detector"
    analyzed_at: Optional[datetime] = None
    segment_scores: List[IntegritySegmentScore] = Field(default_factory=list)
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/goodwiinz/development/RAG_system && python -m pytest tests/unit/test_scispace_schemas.py -v`
Expected: PASS (all 5 tests)

**Step 5: Commit**

```bash
git add backend/src/shared/scispace_schemas.py tests/unit/test_scispace_schemas.py
git commit -m "feat: add SciSpace shared schemas for extraction, tone, and integrity"
```

---

## Task 1: Feature 4 — Crossref & PubMed Connectors

Start with Feature 4 because it follows the existing connector pattern most closely.

### Task 1.1: Crossref Connector

**Files:**

- Create: `backend/src/services/research_engine/connectors/crossref_connector.py`
- Test: `tests/unit/test_crossref_connector.py`

**Reference:** Copy pattern from `semantic_scholar_connector.py` and `arxiv_connector.py`.

**Step 1: Write the failing test**

```python
# tests/unit/test_crossref_connector.py
"""Tests for Crossref source connector."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from src.services.research_engine.connectors.crossref_connector import CrossrefConnector
from src.services.research_engine.connectors.base import SourceDocument


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

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
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

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
        results = await connector.search("test", max_results=10)

    # Should strip <jats:p> tags
    assert "<jats:" not in (results[0].abstract or "")


@pytest.mark.asyncio
async def test_crossref_empty_response():
    connector = CrossrefConnector(mailto="test@example.com")

    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "ok", "message": {"items": [], "total-results": 0}}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
        results = await connector.search("nonexistent topic", max_results=10)

    assert results == []
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/goodwiinz/development/RAG_system && python -m pytest tests/unit/test_crossref_connector.py -v`
Expected: FAIL (ImportError)

**Step 3: Write implementation**

```python
# backend/src/services/research_engine/connectors/crossref_connector.py
"""Crossref source connector."""

import re
from typing import Any, Dict, List, Optional

import httpx

from src.services.research_engine.connectors.base import SourceConnector, SourceDocument

# Strip JATS XML tags from abstracts
JATS_TAG_RE = re.compile(r"<[^>]+>")


class CrossrefConnector(SourceConnector):
    """Connector for the Crossref REST API."""

    def __init__(self, mailto: Optional[str] = None) -> None:
        self.mailto = mailto

    async def search(
        self, query: str, max_results: int = 50, **kwargs: Any
    ) -> List[SourceDocument]:
        """Search Crossref for works matching the query."""
        params: Dict[str, Any] = {
            "query": query,
            "rows": max_results,
        }

        headers: Dict[str, str] = {}
        if self.mailto:
            headers["User-Agent"] = f"RAGSystem/2.1 (mailto:{self.mailto})"

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                "https://api.crossref.org/works",
                params=params,
                headers=headers,
            )
            response.raise_for_status()

        data = response.json()
        items = data.get("message", {}).get("items", [])
        documents: List[SourceDocument] = []

        for item in items:
            # Title is a list in Crossref API
            title_list = item.get("title", [])
            title = title_list[0] if title_list else ""

            # Authors: combine given + family names
            authors = []
            for author in item.get("author", []):
                given = author.get("given", "")
                family = author.get("family", "")
                name = f"{given} {family}".strip()
                if name:
                    authors.append(name)

            # Abstract: strip JATS XML tags
            abstract = item.get("abstract", "")
            if abstract:
                abstract = JATS_TAG_RE.sub("", abstract).strip()

            documents.append(
                SourceDocument(
                    connector_type="crossref",
                    external_id=item.get("DOI"),
                    title=title,
                    authors=authors,
                    abstract=abstract or None,
                    url=item.get("URL"),
                    metadata={
                        "doi": item.get("DOI"),
                        "journal": (item.get("container-title") or [None])[0],
                        "citation_count": item.get("is-referenced-by-count"),
                        "published": item.get("published-print", {}).get("date-parts"),
                    },
                )
            )

        return documents
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/goodwiinz/development/RAG_system && python -m pytest tests/unit/test_crossref_connector.py -v`
Expected: PASS (all 3 tests)

**Step 5: Commit**

```bash
git add backend/src/services/research_engine/connectors/crossref_connector.py tests/unit/test_crossref_connector.py
git commit -m "feat: add Crossref source connector"
```

### Task 1.2: PubMed Connector

**Files:**

- Create: `backend/src/services/research_engine/connectors/pubmed_connector.py`
- Test: `tests/unit/test_pubmed_connector.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_pubmed_connector.py
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


@pytest.mark.asyncio
async def test_pubmed_search_two_step():
    connector = PubMedConnector()

    mock_search_resp = MagicMock()
    mock_search_resp.text = SAMPLE_ESEARCH_RESPONSE
    mock_search_resp.raise_for_status = MagicMock()

    mock_fetch_resp = MagicMock()
    mock_fetch_resp.text = SAMPLE_EFETCH_RESPONSE
    mock_fetch_resp.raise_for_status = MagicMock()

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
async def test_pubmed_extracts_mesh_terms():
    connector = PubMedConnector()

    mock_search_resp = MagicMock()
    mock_search_resp.text = SAMPLE_ESEARCH_RESPONSE
    mock_search_resp.raise_for_status = MagicMock()

    mock_fetch_resp = MagicMock()
    mock_fetch_resp.text = SAMPLE_EFETCH_RESPONSE
    mock_fetch_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=[mock_search_resp, mock_fetch_resp]):
        results = await connector.search("test", max_results=10)

    assert "Neural Networks, Computer" in results[0].metadata.get("mesh_terms", [])
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/goodwiinz/development/RAG_system && python -m pytest tests/unit/test_pubmed_connector.py -v`
Expected: FAIL (ImportError)

**Step 3: Write implementation**

```python
# backend/src/services/research_engine/connectors/pubmed_connector.py
"""PubMed source connector via NCBI E-Utilities."""

import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

import httpx

from src.services.research_engine.connectors.base import SourceConnector, SourceDocument

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


class PubMedConnector(SourceConnector):
    """Connector for the PubMed/NCBI E-Utilities API."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key

    async def search(
        self, query: str, max_results: int = 50, **kwargs: Any
    ) -> List[SourceDocument]:
        """Search PubMed: esearch for PMIDs, then efetch for full records."""
        base_params: Dict[str, Any] = {}
        if self.api_key:
            base_params["api_key"] = self.api_key

        # Step 1: Search for PMIDs
        search_params = {
            **base_params,
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "xml",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            search_resp = await client.get(ESEARCH_URL, params=search_params)
            search_resp.raise_for_status()

            root = ET.fromstring(search_resp.text)
            pmids = [el.text for el in root.findall(".//IdList/Id") if el.text]

            if not pmids:
                return []

            # Step 2: Fetch full records
            fetch_params = {
                **base_params,
                "db": "pubmed",
                "id": ",".join(pmids),
                "retmode": "xml",
                "rettype": "abstract",
            }
            fetch_resp = await client.get(EFETCH_URL, params=fetch_params)
            fetch_resp.raise_for_status()

        return self._parse_articles(fetch_resp.text)

    def _parse_articles(self, xml_text: str) -> List[SourceDocument]:
        """Parse PubMed XML into SourceDocument list."""
        root = ET.fromstring(xml_text)
        documents: List[SourceDocument] = []

        for article_el in root.findall(".//PubmedArticle"):
            citation = article_el.find("MedlineCitation")
            if citation is None:
                continue

            pmid = citation.findtext("PMID", default="")
            article = citation.find("Article")
            if article is None:
                continue

            title = article.findtext("ArticleTitle", default="")
            abstract = article.findtext(".//AbstractText", default="")

            # Authors
            authors: List[str] = []
            for author_el in article.findall(".//Author"):
                fore = author_el.findtext("ForeName", default="")
                last = author_el.findtext("LastName", default="")
                name = f"{fore} {last}".strip()
                if name:
                    authors.append(name)

            # MeSH terms
            mesh_terms: List[str] = []
            for mesh_el in citation.findall(".//MeshHeading/DescriptorName"):
                if mesh_el.text:
                    mesh_terms.append(mesh_el.text)

            documents.append(
                SourceDocument(
                    connector_type="pubmed",
                    external_id=pmid,
                    title=title,
                    authors=authors,
                    abstract=abstract or None,
                    url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None,
                    metadata={
                        "pmid": pmid,
                        "mesh_terms": mesh_terms,
                    },
                )
            )

        return documents
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/goodwiinz/development/RAG_system && python -m pytest tests/unit/test_pubmed_connector.py -v`
Expected: PASS (all 2 tests)

**Step 5: Commit**

```bash
git add backend/src/services/research_engine/connectors/pubmed_connector.py tests/unit/test_pubmed_connector.py
git commit -m "feat: add PubMed source connector via NCBI E-Utilities"
```

### Task 1.3: Register Connectors and Update Research Tasks

**Files:**

- Modify: `backend/src/services/research_engine/connectors/__init__.py`
- Modify: `backend/src/tasks/research_tasks.py:132-142`

**Step 1: Update connector registry**

Replace `__init__.py` content:

```python
"""Source connectors for the research engine."""

from src.services.research_engine.connectors.arxiv_connector import ArxivConnector
from src.services.research_engine.connectors.base import SourceConnector, SourceDocument
from src.services.research_engine.connectors.crossref_connector import CrossrefConnector
from src.services.research_engine.connectors.pubmed_connector import PubMedConnector
from src.services.research_engine.connectors.rag_store_connector import RagStoreConnector
from src.services.research_engine.connectors.semantic_scholar_connector import (
    SemanticScholarConnector,
)

__all__ = [
    "ArxivConnector",
    "CrossrefConnector",
    "PubMedConnector",
    "RagStoreConnector",
    "SemanticScholarConnector",
    "SourceConnector",
    "SourceDocument",
]
```

**Step 2: Update `_build_connectors` in research_tasks.py**

Replace the existing `_build_connectors` function (line ~132) and update imports:

Add to imports:

```python
from src.services.research_engine.connectors import (
    ArxivConnector,
    CrossrefConnector,
    PubMedConnector,
    RagStoreConnector,
    SemanticScholarConnector,
)
```

Replace function:

```python
def _build_connectors() -> dict:
    """Create connector instances for the workflow."""
    return {
        "arxiv": ArxivConnector(),
        "semantic_scholar": SemanticScholarConnector(),
        "crossref": CrossrefConnector(mailto="admin@multimodal-rag.com"),
        "pubmed": PubMedConnector(),
        "web": SemanticScholarConnector(),  # fallback alias
        "rag_store": RagStoreConnector(search_fn=_search_rag_store),
    }
```

**Step 3: Commit**

```bash
git add backend/src/services/research_engine/connectors/__init__.py backend/src/tasks/research_tasks.py
git commit -m "feat: register Crossref and PubMed connectors in workflow engine"
```

---

## Task 2: Feature 3 — Scholarly Tone Engine

### Task 2.1: Tone Prompts

**Files:**

- Create: `backend/src/core/prompts/__init__.py`
- Create: `backend/src/core/prompts/tone_prompts.py`

**Step 1: Write the prompts module**

```python
# backend/src/core/prompts/tone_prompts.py
"""System prompts for the Scholarly Tone Engine."""

CITATION_INSTRUCTION = (
    "CRITICAL: Preserve ALL citation markers (e.g. [1], [2], [3]) in their "
    "semantically equivalent positions. Do NOT remove, add, or renumber citations."
)

TONE_PROMPTS = {
    "academic": (
        "Rewrite the following text in a formal academic tone. Use precise vocabulary, "
        "hedging language (e.g., 'suggests', 'appears to'), passive voice where appropriate, "
        "and discipline-specific terminology. Maintain the original meaning and all factual claims.\n\n"
        f"{CITATION_INSTRUCTION}"
    ),
    "simplified": (
        "Rewrite the following text for a general audience at an 8th-grade reading level. "
        "Use active voice, short sentences, concrete examples, and avoid jargon. "
        "Replace technical terms with plain-language equivalents.\n\n"
        f"{CITATION_INSTRUCTION}"
    ),
    "concise": (
        "Rewrite the following text to be as concise as possible without losing meaning. "
        "Remove redundancy, tighten sentences, eliminate filler words, and merge related ideas. "
        "The result should be significantly shorter than the original.\n\n"
        f"{CITATION_INSTRUCTION}"
    ),
    "expanded": (
        "Expand the following text by adding context, examples, transitions, and elaboration. "
        "Flesh out implicit assumptions, provide supporting details, and improve flow between ideas. "
        "The result should be more thorough and accessible.\n\n"
        f"{CITATION_INSTRUCTION}"
    ),
}
```

**Step 2: Commit**

```bash
mkdir -p backend/src/core/prompts && touch backend/src/core/prompts/__init__.py
git add backend/src/core/prompts/
git commit -m "feat: add tone system prompts for scholarly rewriting"
```

### Task 2.2: Tone Engine Service

**Files:**

- Create: `backend/src/services/research/tone_engine_service.py`
- Test: `tests/unit/test_tone_engine_service.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_tone_engine_service.py
"""Tests for the Scholarly Tone Engine service."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.services.research.tone_engine_service import ToneEngineService


@pytest.mark.asyncio
async def test_rewrite_preserves_citations():
    service = ToneEngineService()

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="The findings [1] suggest improvements [3]."))]

    with patch("openai.AsyncOpenAI") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await service.rewrite(
            text="Results [1] show that this works [3].",
            tone="academic",
        )

    assert "[1]" in result["rewritten"]
    assert "[3]" in result["rewritten"]
    assert result["tone_applied"] == "academic"
    assert "[1]" in result["citations_preserved"]
    assert "[3]" in result["citations_preserved"]


def test_extract_citations():
    service = ToneEngineService()
    citations = service._extract_citations("This [1] is a test [2] with [15] citations.")
    assert citations == ["[1]", "[2]", "[15]"]


def test_extract_citations_empty():
    service = ToneEngineService()
    citations = service._extract_citations("No citations here.")
    assert citations == []
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/goodwiinz/development/RAG_system && python -m pytest tests/unit/test_tone_engine_service.py -v`
Expected: FAIL (ImportError)

**Step 3: Write implementation**

```python
# backend/src/services/research/tone_engine_service.py
"""Scholarly Tone Engine service for text rewriting with citation preservation."""

import re
from typing import Any, Dict, List, Optional

import structlog

from src.core.config import settings
from src.core.prompts.tone_prompts import TONE_PROMPTS

logger = structlog.get_logger()

CITATION_RE = re.compile(r"\[\d+\]")


class ToneEngineService:
    """Service for rewriting text with adjustable academic tone."""

    def _extract_citations(self, text: str) -> List[str]:
        """Extract all citation markers from text."""
        return CITATION_RE.findall(text)

    async def rewrite(
        self,
        text: str,
        tone: str,
        model: Optional[str] = None,
        preserve_citations: bool = True,
    ) -> Dict[str, Any]:
        """Rewrite text with the specified tone."""
        import openai

        original_citations = self._extract_citations(text) if preserve_citations else []

        system_prompt = TONE_PROMPTS.get(tone)
        if not system_prompt:
            raise ValueError(f"Unknown tone: {tone}. Valid: {list(TONE_PROMPTS.keys())}")

        model_id = model or "gpt-4o"

        client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            temperature=0.7,
        )

        rewritten = response.choices[0].message.content or ""

        # Verify citation preservation
        rewritten_citations = self._extract_citations(rewritten)
        preserved = [c for c in original_citations if c in rewritten_citations]

        if preserve_citations and set(original_citations) != set(rewritten_citations):
            logger.warning(
                "citation_mismatch",
                original=original_citations,
                rewritten=rewritten_citations,
            )

        return {
            "original": text,
            "rewritten": rewritten,
            "tone_applied": tone,
            "citations_preserved": preserved,
        }
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/goodwiinz/development/RAG_system && python -m pytest tests/unit/test_tone_engine_service.py -v`
Expected: PASS (all 3 tests)

**Step 5: Commit**

```bash
git add backend/src/services/research/tone_engine_service.py tests/unit/test_tone_engine_service.py
git commit -m "feat: add tone engine service with citation preservation"
```

### Task 2.3: Tone Engine API Router

**Files:**

- Create: `backend/src/api/research/tone_engine.py`
- Modify: `backend/src/main.py` (add router import + registration)

**Step 1: Write the API router**

```python
# backend/src/api/research/tone_engine.py
"""Tone Engine API Router - text rewriting with academic tone adjustment."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.core.database import get_db
from src.models.user import User
from src.services.research.tone_engine_service import ToneEngineService
from src.services.security.user_management import get_current_user
from src.shared.scispace_schemas import RewriteRequest, RewriteResponse

logger = get_logger()
router = APIRouter(prefix="/api/v1/research", tags=["tone-engine"])

_service = ToneEngineService()


@router.post("/rewrite", response_model=RewriteResponse)
async def rewrite_text(
    request: RewriteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Rewrite text with the specified academic tone."""
    try:
        result = await _service.rewrite(
            text=request.text,
            tone=request.tone.value,
            model=request.model,
            preserve_citations=request.preserve_citations,
        )
        return RewriteResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("rewrite_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to rewrite text",
        )
```

**Step 2: Register router in main.py**

Add import and `app.include_router(tone_engine_router)` alongside the other research routers (around line 343).

**Step 3: Commit**

```bash
git add backend/src/api/research/tone_engine.py backend/src/main.py
git commit -m "feat: add tone engine API endpoint POST /api/v1/research/rewrite"
```

---

## Task 3: Feature 1 — Literature Review Extraction Matrix

### Task 3.1: Database Model and Migration

**Files:**

- Create: `backend/src/models/extraction_matrix.py`
- Create: `backend/alembic/versions/j5l9m0n1o2p3_create_extraction_matrices.py`
- Modify: `backend/src/models/__init__.py`

**Step 1: Write the model**

```python
# backend/src/models/extraction_matrix.py
"""ExtractionMatrix and ExtractionCell models for Literature Review Matrix."""

from sqlalchemy import Column, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .base import GUID, BaseModel


class ExtractionMatrix(BaseModel):
    """A structured extraction matrix for comparing documents in a project."""

    __tablename__ = "extraction_matrices"

    project_id = Column(
        GUID(),
        ForeignKey("collections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(255), nullable=False)
    columns = Column(JSONB, nullable=False, server_default="[]")

    project = relationship("Collection", backref="extraction_matrices")
    cells = relationship("ExtractionCell", back_populates="matrix", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ExtractionMatrix(id={self.id}, name={self.name})>"


class ExtractionCell(BaseModel):
    """A single extracted value in the matrix grid."""

    __tablename__ = "extraction_cells"

    matrix_id = Column(
        GUID(),
        ForeignKey("extraction_matrices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id = Column(
        GUID(),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    column_name = Column(String(100), nullable=False)
    value = Column(Text, nullable=True)
    citation_snippet = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)

    matrix = relationship("ExtractionMatrix", back_populates="cells")
    document = relationship("Document")

    def __repr__(self):
        return f"<ExtractionCell(matrix={self.matrix_id}, col={self.column_name})>"
```

**Step 2: Write the migration**

See design doc for full migration SQL. Use revision `j5l9m0n1o2p3`, down_revision `add_org_id_api_keys`.

**Step 3: Register models in `__init__.py`**

Add imports and `__all__` entries for `ExtractionMatrix` and `ExtractionCell`.

**Step 4: Commit**

```bash
git add backend/src/models/extraction_matrix.py backend/alembic/versions/j5l9m0n1o2p3_create_extraction_matrices.py backend/src/models/__init__.py
git commit -m "feat: add ExtractionMatrix and ExtractionCell models with migration"
```

### Task 3.2: Extraction Matrix Service

**Files:**

- Create: `backend/src/services/research/extraction_matrix_service.py`
- Test: `tests/unit/test_extraction_matrix_service.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_extraction_matrix_service.py
"""Tests for the Extraction Matrix service."""

import pytest
from src.services.research.extraction_matrix_service import ExtractionMatrixService


def test_build_extraction_prompt():
    service = ExtractionMatrixService()
    columns = [
        {"name": "Methodology", "description": "Research methodology used"},
        {"name": "Sample Size", "description": "Number of participants"},
    ]
    prompt = service._build_extraction_prompt(columns, "This study used a randomized trial with 500 participants.")
    assert "Methodology" in prompt
    assert "Sample Size" in prompt
    assert "randomized trial" in prompt


def test_parse_extraction_result_valid_json():
    service = ExtractionMatrixService()
    columns = [{"name": "Methodology"}, {"name": "Sample Size"}]
    raw = '{"Methodology": {"value": "RCT", "citation": "p.3"}, "Sample Size": {"value": "500", "citation": "p.5"}}'
    result = service._parse_extraction_result(raw, columns)
    assert result["Methodology"]["value"] == "RCT"
    assert result["Sample Size"]["value"] == "500"


def test_parse_extraction_result_missing_column():
    service = ExtractionMatrixService()
    columns = [{"name": "Methodology"}, {"name": "Missing"}]
    raw = '{"Methodology": {"value": "RCT"}}'
    result = service._parse_extraction_result(raw, columns)
    assert result["Methodology"]["value"] == "RCT"
    assert result["Missing"]["value"] is None
```

**Step 2: Write implementation** (see design doc for full code)

**Step 3: Commit**

```bash
git add backend/src/services/research/extraction_matrix_service.py tests/unit/test_extraction_matrix_service.py
git commit -m "feat: add extraction matrix service with structured LLM extraction"
```

### Task 3.3: Extraction Matrix API Router

**Files:**

- Create: `backend/src/api/research/extraction_matrix.py`
- Modify: `backend/src/main.py`

See design doc for full router implementation with CRUD + extraction trigger.

**Commit:**

```bash
git add backend/src/api/research/extraction_matrix.py backend/src/main.py
git commit -m "feat: add extraction matrix API with CRUD and extraction trigger"
```

---

## Task 4: Feature 5 — AI Integrity Detector

### Task 4.1: Database Model and Migration

**Files:**

- Create: `backend/src/models/integrity_score.py`
- Create: `backend/alembic/versions/k6m0n1o2p3q4_create_integrity_scores.py`
- Modify: `backend/src/models/__init__.py`

Model and migration follow same pattern as ExtractionMatrix. See design doc.

**Commit:**

```bash
git add backend/src/models/integrity_score.py backend/alembic/versions/k6m0n1o2p3q4_create_integrity_scores.py backend/src/models/__init__.py
git commit -m "feat: add IntegrityScore model with migration"
```

### Task 4.2: Integrity Detection Service

**Files:**

- Create: `backend/src/services/documents/integrity_detection_service.py`
- Test: `tests/unit/test_integrity_detection_service.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_integrity_detection_service.py
"""Tests for the AI Integrity Detection service."""

import pytest
from src.services.documents.integrity_detection_service import IntegrityDetectionService


def test_split_into_segments():
    service = IntegrityDetectionService.__new__(IntegrityDetectionService)
    text = " ".join(["word"] * 1000)
    segments = service._split_into_segments(text, max_tokens=100)
    assert len(segments) > 1
    for seg in segments:
        assert len(seg.split()) <= 100


def test_split_short_text():
    service = IntegrityDetectionService.__new__(IntegrityDetectionService)
    text = "This is a short text."
    segments = service._split_into_segments(text, max_tokens=100)
    assert len(segments) == 1


def test_aggregate_scores():
    service = IntegrityDetectionService.__new__(IntegrityDetectionService)
    segment_scores = [
        {"text_preview": "First...", "ai_probability": 0.8, "length": 100},
        {"text_preview": "Second...", "ai_probability": 0.4, "length": 200},
    ]
    avg = service._aggregate_scores(segment_scores)
    # Weighted: (0.8 * 100 + 0.4 * 200) / 300 = 160/300 = 0.533...
    assert abs(avg - 0.5333) < 0.01
```

**Step 2: Write implementation**

The service lazy-loads `roberta-base-openai-detector` from HuggingFace. Key method: `analyze(text)` splits text into 512-token segments, runs each through the classifier, and returns weighted-average scores.

See design doc for full implementation. The model is loaded once on first call via a module-level `_load_model()` function.

**Step 3: Commit**

```bash
git add backend/src/services/documents/integrity_detection_service.py tests/unit/test_integrity_detection_service.py
git commit -m "feat: add integrity detection service with RoBERTa classifier"
```

### Task 4.3: Integrity API Router

**Files:**

- Create: `backend/src/api/documents/integrity.py`
- Modify: `backend/src/main.py`

Two endpoints: `POST /documents/{id}/integrity-check` (triggers analysis) and `GET /documents/{id}/integrity-score` (retrieves result).

See design doc for full implementation.

**Commit:**

```bash
git add backend/src/api/documents/integrity.py backend/src/main.py
git commit -m "feat: add integrity check API endpoints"
```

---

## Task 5: Feature 2 — Deep Tabular & Math Extraction

### Task 5.1: Table Extraction Service

**Files:**

- Create: `backend/src/services/processing/table_extraction_service.py`
- Test: `tests/unit/test_table_extraction_service.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_table_extraction_service.py
"""Tests for the Table Extraction service."""

import pytest
from src.services.processing.table_extraction_service import TableExtractionService


def test_crop_coordinates_validation():
    service = TableExtractionService()
    assert service._validate_coordinates(1, 0, 0, 100, 100) is True
    assert service._validate_coordinates(1, -1, 0, 100, 100) is False
    assert service._validate_coordinates(1, 100, 0, 50, 100) is False


def test_csv_to_markdown():
    service = TableExtractionService()
    csv_data = "Name,Age,City\nAlice,30,NYC\nBob,25,LA"
    md = service._csv_to_markdown(csv_data)
    assert "| Name | Age | City |" in md
    assert "| Alice | 30 | NYC |" in md
    assert "---" in md
```

**Step 2: Write implementation**

The service uses Camelot (lattice mode) as primary, Tabula as fallback, and GPT-4o Vision for image-based extraction. Key methods: `extract_tables_from_pdf()`, `extract_region()`, `_transcribe_image()`.

See design doc for full implementation.

**Step 3: Commit**

```bash
git add backend/src/services/processing/table_extraction_service.py tests/unit/test_table_extraction_service.py
git commit -m "feat: add table extraction service with Camelot/Tabula/LLM pipeline"
```

### Task 5.2: Table Extraction API Router

**Files:**

- Create: `backend/src/api/documents/table_extraction.py`
- Modify: `backend/src/main.py`

Two endpoints: `GET /documents/{id}/tables` (extract all tables) and `POST /documents/{id}/extract-region` (crop extraction).

See design doc for full implementation.

**Commit:**

```bash
git add backend/src/api/documents/table_extraction.py backend/src/main.py
git commit -m "feat: add table extraction API endpoints"
```

### Task 5.3: Add Python Dependencies

Add `camelot-py[cv]`, `tabula-py`, `transformers`, `torch` to project dependencies.

```bash
git add pyproject.toml
git commit -m "feat: add camelot, tabula, transformers dependencies for SciSpace"
```

---

## Task 6: Integration and Smoke Testing

### Task 6.1: Run All Unit Tests

Run: `cd /Users/goodwiinz/development/RAG_system && python -m pytest tests/unit/test_scispace_schemas.py tests/unit/test_crossref_connector.py tests/unit/test_pubmed_connector.py tests/unit/test_tone_engine_service.py tests/unit/test_extraction_matrix_service.py tests/unit/test_integrity_detection_service.py tests/unit/test_table_extraction_service.py -v`
Expected: All PASS

### Task 6.2: Run Database Migrations

Run: `cd /Users/goodwiinz/development/RAG_system/backend && alembic upgrade head`

### Task 6.3: Backend Smoke Test

Start backend and verify all new endpoints return appropriate responses (400/401 for unauthenticated, 200/202 for authenticated).

---

## Task 7: Frontend Components (Outline)

Frontend tasks should be implemented in a follow-up phase. Components needed:

| Component                 | File                                       | Feature |
| ------------------------- | ------------------------------------------ | ------- |
| ExtractionMatrix.tsx      | `frontend/src/components/research/`        | 1       |
| ColumnEditor.tsx          | `frontend/src/components/research/`        | 1       |
| CellCitation.tsx          | `frontend/src/components/research/`        | 1       |
| CropExtractOverlay.tsx    | `frontend/src/components/documents/`       | 2       |
| ExtractedTablePreview.tsx | `frontend/src/components/documents/`       | 2       |
| MathDisplay.tsx           | `frontend/src/components/documents/`       | 2       |
| ToneToolbar.tsx           | `frontend/src/components/research/`        | 3       |
| RewriteDiffView.tsx       | `frontend/src/components/research/`        | 3       |
| SourceSelector.tsx        | `frontend/src/components/research-engine/` | 4       |
| IntegrityBadge.tsx        | `frontend/src/components/documents/`       | 5       |
| IntegrityDetail.tsx       | `frontend/src/components/documents/`       | 5       |

---

**Total backend tasks: ~20 steps across 7 task groups**
**New files created: ~15**
**Files modified: ~5**
**New unit tests: ~17**
