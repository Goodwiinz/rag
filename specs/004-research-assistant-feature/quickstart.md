# Quickstart: Research Assistant

**Feature**: Research Assistant | **Branch**: `004-research-assistant-feature`

## Overview

The Research Assistant transforms your RAG system into a comprehensive research tool for academics and researchers. It enables:

1. **Local AI with Citations** - Ask questions about papers using privacy-preserving local models
2. **Citation Management** - Extract, visualize, and export citations
3. **Research Projects** - Organize documents with notes and tags
4. **Draft Generation** - AI-powered literature review drafts

## Prerequisites

### System Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| Browser | Chrome 113+ / Edge 113+ | Latest Chrome |
| RAM | 4GB (1B models) | 8GB+ (3B+ models) |
| GPU | WebGPU-capable | Dedicated GPU |
| Storage | 2GB free | 10GB+ free |

### Services Required

```bash
# Start all services
docker-compose -f docker-compose.development.yml up -d

# Verify services
curl http://localhost:8000/health  # Backend
curl http://localhost:6333/health  # Qdrant
curl http://localhost:7474         # Neo4j
```

## Quick Setup

### 1. Database Migrations

Run the new migrations for citation and project tables:

```bash
cd backend
alembic upgrade head
```

### 2. Install New Dependencies

**Backend**:
```bash
pip install pybtex==0.24.0 aiohttp-retry==2.8.3
```

**Frontend**:
```bash
npm install cytoscape-popper@2.0.0 cytoscape-context-menus@4.1.0
```

### 3. Environment Configuration

Add to `.env`:

```env
# Citation Extraction (optional - enhances accuracy)
SEMANTIC_SCHOLAR_API_KEY=your_key_here
CROSSREF_API_KEY=your_key_here

# Rate Limiting
CITATION_EXTRACTION_RATE_LIMIT=10  # requests per second
```

## Feature Walkthrough

### Phase 1: Local AI with RAG

**What it does**: Enables local AI models (WebLLM) to answer questions about your uploaded documents with proper citations.

**Quick test**:
1. Upload a PDF research paper
2. Select a local model (e.g., Llama-3.2-1B)
3. Enable RAG toggle
4. Ask: "What are the key findings in this paper?"
5. Verify response includes `[Doc 1]` citations

**Key files**:
- `frontend/app/(dashboard)/chat/page.tsx` - WebLLM integration
- `frontend/src/services/ragService.ts` - Model-aware retrieval
- `backend/src/api/citations.py` - Citation persistence

**Model Context Limits**:

| Model Size | Documents | Tokens | History |
|------------|-----------|--------|---------|
| 1B | 2 | 600 | 2 messages |
| 3B | 3 | 1000 | 4 messages |
| 7B+ | 5 | 2000 | 8 messages |
| Cloud | 8 | 4000 | 20 messages |

### Phase 2: Citation Management

**What it does**: Extracts citation metadata from papers and visualizes citation networks.

**Quick test**:
1. Navigate to a document detail page
2. Click "Extract Citations"
3. Wait for extraction (uses ArXiv/Semantic Scholar/CrossRef)
4. Click "View Citation Graph"
5. Export bibliography as BibTeX

**Extraction Strategy**:
```
ArXiv paper → ArXiv API (90%+ accuracy)
         ↓ (if not ArXiv)
DOI/Title → Semantic Scholar / CrossRef lookup
         ↓ (if lookup fails)
PDF → Text parsing with regex patterns
         ↓ (if parsing fails)
Manual entry → User correction UI
```

**Key files**:
- `backend/src/services/citation_extraction_service.py` - Hybrid extraction
- `backend/src/services/bibliography_service.py` - Format exports
- `frontend/src/components/citations/CitationGraph.tsx` - Visualization

### Phase 3: Research Projects

**What it does**: Organize documents into named projects with notes and tags.

**Quick test**:
1. Go to `/research`
2. Click "Create Project"
3. Name it "My Literature Review"
4. Add 3-5 documents to the project
5. Create a note with markdown
6. Generate project bibliography

**Project states**:
```
active → paused → active (toggle)
active → completed (mark done)
completed → archived (cleanup)
archived → active (reopen)
```

**Key files**:
- `frontend/app/(dashboard)/research/page.tsx` - Project listing
- `frontend/app/(dashboard)/research/[id]/page.tsx` - Project detail
- `backend/src/api/projects.py` - Project CRUD

### Phase 4: Draft Generation

**What it does**: Generates AI-powered literature review drafts from project documents.

**Quick test**:
1. Open a project with 5+ documents
2. Click "Generate Literature Review"
3. Optionally specify themes (e.g., "methodology", "findings")
4. Wait 30-60 seconds
5. Review draft with `[Doc N]` citations
6. Export to LaTeX

**Generation workflow**:
```
1. Orchestrator Agent → Parse themes, select documents
2. Retrieval Agent → Fetch relevant sections
3. QA Agent → Extract key findings per theme
4. Synthesis Agent → Combine into narrative
5. Citation Agent → Inject [Doc N] citations
6. Format Agent → Structure with bibliography
```

**Key files**:
- `backend/src/services/draft_generation_service.py` - Multi-agent orchestration
- `frontend/src/components/research/DraftViewer.tsx` - Version comparison

## API Quick Reference

### Citations

```bash
# Extract citations from document
POST /api/v1/citations/extract
{
  "document_id": "uuid",
  "strategy": "auto"
}

# Get citation graph
GET /api/v1/citations/graph?project_id=uuid&depth=2

# Export bibliography
POST /api/v1/citations/export
{
  "format": "bibtex",
  "project_id": "uuid"
}
```

### Projects

```bash
# Create project
POST /api/v1/projects
{
  "name": "My Research",
  "project_type": "literature_review"
}

# Add document to project
POST /api/v1/projects/{id}/documents
{
  "document_id": "uuid"
}

# Create note
POST /api/v1/projects/{id}/notes
{
  "title": "Key Observations",
  "content": "## Findings\n- Finding 1..."
}
```

### Drafts

```bash
# Generate draft
POST /api/v1/projects/{id}/drafts
{
  "themes": ["methodology", "results"],
  "style": "academic"
}

# Check generation status
GET /api/v1/projects/{id}/drafts/status

# Export to LaTeX
POST /api/v1/projects/{id}/drafts/{draft_id}/export
{
  "format": "latex"
}
```

## Performance Expectations

| Operation | Target | Notes |
|-----------|--------|-------|
| Document retrieval | <2s | Warm cache |
| 1B model generation | 10-20s | Per response |
| 3B model generation | 20-40s | Per response |
| 7B model generation | 40-60s | Per response |
| Citation extraction | <5s | Per paper (ArXiv) |
| Graph rendering | <3s | 100 nodes |
| Draft generation | <60s | 10 documents |

**Note**: Model load time (30-60s on first use) is excluded from targets.

## Troubleshooting

### WebLLM not loading

```javascript
// Check WebGPU support
if (!navigator.gpu) {
  console.error('WebGPU not supported');
}
```

**Solution**: Use Chrome 113+ or Edge 113+. Ensure hardware acceleration is enabled.

### Citation extraction fails

**Symptoms**: "No citations found" or timeout errors

**Solutions**:
1. Check document is a valid PDF with extractable text
2. Verify API keys are set for Semantic Scholar/CrossRef
3. For ArXiv papers, ensure ArXiv ID is detected
4. Fall back to manual entry if automated extraction fails

### Graph rendering slow

**Symptoms**: Graph takes >5s to render or browser freezes

**Solutions**:
1. Reduce `depth` parameter (default: 2)
2. Set `include_external: false` to limit nodes
3. For 500+ nodes, use clustering view

### Draft generation timeout

**Symptoms**: Generation exceeds 60s or fails

**Solutions**:
1. Reduce number of documents (max 10 recommended)
2. Check backend logs for agent errors
3. Verify document content is extractable
4. Try regenerating with fewer themes

## Next Steps

After setup:
1. Upload 5-10 research papers
2. Try local AI Q&A with RAG
3. Extract citations and explore the graph
4. Create a research project
5. Generate your first literature review draft

For detailed API documentation, see the OpenAPI specs in `specs/004-research-assistant-feature/contracts/`.
