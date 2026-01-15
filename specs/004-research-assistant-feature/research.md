# Research: Research Assistant Feature

**Date**: 2026-01-14
**Feature**: Research Assistant (WebLLM RAG, Citations, Projects, Drafts)

## 1. WebLLM RAG Integration

### Decision
Extend existing RAG service to inject context into WebLLM prompts using model-aware configuration.

### Rationale
The codebase already has excellent infrastructure:
- `ragService.ts` has model-aware context sizing (1B/3B/7B/Cloud)
- Token-based budgeting with document truncation
- Citation format enforcement (`[Doc N]`)
- Few-shot examples for citation compliance

### Current Implementation (Already Exists)
```typescript
// frontend/src/services/ragService.ts
Model Configs:
- 1B models:  2 docs, 600 tokens, 2 history messages, simple prompts
- 3B models:  3 docs, 1000 tokens, 4 history messages, few-shot examples
- 7B+ models: 5 docs, 2000 tokens, 8 history messages, detailed instructions
- Cloud:      8 docs, 4000 tokens, 20 history messages
```

### Implementation Required
1. **Modify chat/page.tsx** (lines ~800-900): Add RAG retrieval before WebLLM inference
2. **Add citation persistence**: Save citations to database after WebLLM responses
3. **Post-processing**: Validate citation format compliance, add fallback citations

### Alternatives Considered
| Option | Rejected Because |
|--------|------------------|
| Full browser-side retrieval | Too complex; requires local vector index |
| Skip RAG for local models | Defeats privacy-conscious use case |
| New RAG service for WebLLM | Duplicates existing well-designed service |

---

## 2. Citation Extraction APIs

### Decision
Hybrid extraction pipeline: ArXiv API → Semantic Scholar → CrossRef → PDF parsing → Manual entry

### Rationale
- ArXiv API provides 90%+ accuracy for ArXiv papers
- Semantic Scholar has native ArXiv ID support and citation networks
- CrossRef provides DOI-based lookup as fallback
- PDF parsing (via existing PyMuPDF) handles edge cases

### API Comparison

| API | Rate Limit | Auth Required | Best For |
|-----|------------|---------------|----------|
| **ArXiv** | 3 req/sec | No | Paper metadata, PDF download |
| **Semantic Scholar** | 100/sec (10K/day free) | Optional | Citation networks, ArXiv lookup |
| **CrossRef** | 50/sec (500 with key) | Optional | DOI verification, venue metadata |
| **Grobid** | Self-hosted | No | PDF bibliography parsing |

### Existing Codebase Assets
- `backend/src/services/arxiv_service.py` (781 lines) - Full ArXiv integration
- `backend/src/models/citation.py` - Citation model with external_reference_id
- PyMuPDF already in requirements.txt

### Implementation Required
1. **Add Semantic Scholar client**: `/backend/src/services/semantic_scholar_service.py`
2. **Add CrossRef client**: `/backend/src/services/crossref_service.py`
3. **Create hybrid extractor**: `/backend/src/services/citation_extraction_service.py`
4. **Add rate limiting**: Use `asyncio-contextmanager` for API throttling

### Rate Limiting Strategy
```python
# Bulk operations: Queue with rate limiting
async with AsyncLimiter(max_rate=10, time_period=1):  # 10/sec
    tasks = [get_semantic_scholar_data(paper['id']) for paper in papers]
    results = await asyncio.gather(*tasks)
```

---

## 3. Citation Graph Visualization (Cytoscape.js)

### Decision
Use existing Cytoscape.js integration with preset layout (backend-computed positions).

### Rationale
- Cytoscape.js 3.28.1 already installed
- Backend graph services compute optimized layouts
- Existing `KnowledgeGraphViewer` component handles 1000+ nodes

### Existing Infrastructure
- **Frontend**: `KnowledgeGraphViewer.tsx` (Cytoscape.js), `EnhancedKnowledgeGraphViewer.tsx` (vis-network)
- **Backend Services**:
  - Port 8003: Knowledge Graph Main (entity extraction)
  - Port 8009: Graph Analytics (centrality, clustering)
  - Port 8010: Graph Visualization (layout computation)
- **Features**: Virtual rendering, viewport culling, export (PNG/SVG/JSON)

### Performance Targets

| Graph Size | Strategy | Target Render Time |
|------------|----------|-------------------|
| 100-300 nodes | Full rendering | <500ms |
| 300-800 nodes | Smart culling | <1.5s |
| 800-1500 nodes | Clustering + LOD | <3s |
| 1500-2000 nodes | Hierarchical LOD | <5s |

### Implementation Required
1. **Create CitationGraph.tsx**: Extend `KnowledgeGraphViewer` with citation metadata
2. **Add citation styling**: Node size by citation count, edge weight by relationship
3. **Add interactivity**: Click for details, path finding, filtering by year/author

### Optimization Settings
```typescript
// For 1000-2000 node citation graphs
const config = {
  pixelRatio: 1,                    // Reduce from 'auto'
  textureOnViewport: true,          // Faster viewport scrolling
  hideEdgesOnViewport: nodeCount > 500,
  hideLabelsOnViewport: nodeCount > 1000,
};
```

---

## 4. Bibliography Export Formats

### Decision
Use `pybtex` for BibTeX generation with custom formatters for IEEE/APA/MLA.

### Rationale
- `pybtex` is mature, well-maintained Python library
- Handles BibTeX parsing and generation
- Custom formatters allow consistent output

### Format Specifications

| Format | Entry Structure | Citation Style |
|--------|-----------------|----------------|
| **BibTeX** | `@article{key, title={...}, author={...}}` | `\cite{key}` |
| **IEEE** | `[1] A. Author, "Title," Journal, vol. X, pp. Y-Z, Year.` | `[1]` |
| **APA** | `Author, A. (Year). Title. Journal, Volume(Issue), pages.` | `(Author, Year)` |
| **MLA** | `Author. "Title." Journal, vol. X, no. Y, Year, pp. Z.` | `(Author page)` |

### Implementation Required
1. **Create bibliography_service.py**: Format-specific generators
2. **Handle incomplete metadata**: Mark fields as "Unknown" with review flag
3. **Export endpoints**: `POST /citations/export` with format parameter

---

## 5. Research Project Data Model

### Decision
Extend existing `collections` table with research-specific fields; add `project_notes` and `generated_drafts` tables.

### Rationale
- Collections infrastructure already exists
- Minimal schema changes for Phase 3 features
- Versioned drafts support comparison workflow

### Schema Design
```sql
-- Extend collections for research projects
ALTER TABLE collections ADD COLUMN project_type VARCHAR(50);
ALTER TABLE collections ADD COLUMN research_status VARCHAR(50);
ALTER TABLE collections ADD COLUMN deadline TIMESTAMP;
ALTER TABLE collections ADD COLUMN tags TEXT[];

-- New table for project notes
CREATE TABLE project_notes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES collections(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id),
    title VARCHAR(255),
    content TEXT,  -- Markdown
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- New table for versioned drafts
CREATE TABLE generated_drafts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES collections(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    content TEXT,  -- Markdown with citations
    themes TEXT[],
    generation_params JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_drafts_project_version ON generated_drafts(project_id, version DESC);
```

---

## 6. Draft Generation Architecture

### Decision
Leverage existing multi-agent orchestration system with specialized prompts for literature review.

### Rationale
- 6-agent system already exists (orchestrator, retrieval, graph, vector, QA, synthesis)
- Agents are specialized for RAG workflows
- Minor prompt adjustments enable literature review generation

### Agent Workflow for Literature Review
```
1. Orchestrator: Parse themes, select documents
2. Retrieval Agent: Fetch relevant sections from each document
3. QA Agent: Extract key findings per theme
4. Synthesis Agent: Combine findings into coherent narrative
5. Citation Agent: Inject [Doc N] citations into output
6. Format Agent: Structure into sections with bibliography
```

### Implementation Required
1. **Add literature review template**: `/backend/templates/research/literature_review.md`
2. **Create draft_generation_service.py**: Orchestrate agents with research-specific prompts
3. **Add versioning logic**: Save each generation as new version (max 10)

---

## 7. Observability Requirements

### Decision
Add structured logging for citation extraction and metrics for draft generation.

### Rationale
Constitution principle VII (Observability) requires monitoring all system behavior.

### Metrics to Add
```python
# Citation extraction metrics
citation_extraction_duration = Histogram(
    'citation_extraction_duration_seconds',
    'Time to extract citations from paper',
    ['source']  # arxiv, semantic_scholar, crossref, pdf
)
citation_extraction_success = Counter(
    'citation_extraction_success_total',
    'Successful citation extractions',
    ['source']
)

# Draft generation metrics
draft_generation_duration = Histogram(
    'draft_generation_duration_seconds',
    'Time to generate literature review draft',
    ['num_documents']
)
```

### Logging Pattern
```python
import structlog
logger = structlog.get_logger()

logger.info(
    "citation_extracted",
    paper_id=paper_id,
    source="semantic_scholar",
    citations_count=len(citations),
    duration_ms=elapsed_ms
)
```

---

## 8. Dependencies to Add

### Backend (requirements.txt)
```
pybtex==0.24.0           # BibTeX generation
grobid-client-py==0.0.16 # Optional: PDF parsing
aiohttp-retry==2.8.3     # API retry logic
```

### Frontend (package.json)
```json
{
  "cytoscape-popper": "^2.0.0",      // Tooltips for citation nodes
  "cytoscape-context-menus": "^4.1.0" // Right-click menu
}
```

---

## Summary: All Technical Unknowns Resolved

| Unknown | Resolution |
|---------|------------|
| WebLLM RAG integration | Extend existing ragService with persistence |
| Citation extraction APIs | Hybrid: Semantic Scholar + CrossRef + PDF |
| Graph visualization | Cytoscape.js with backend-computed layout |
| Bibliography formats | pybtex + custom formatters |
| Project data model | Extend collections + new tables |
| Draft generation | Existing multi-agent with research prompts |
| Observability | Structured logging + Prometheus metrics |
