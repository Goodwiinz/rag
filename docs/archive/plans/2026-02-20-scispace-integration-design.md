# SciSpace Capabilities Integration Design

**Date:** 2026-02-20
**Target System:** RAG System v2.1.0
**Approach:** Feature-Parallel with shared foundation layer
**Branch:** TBD (feature/scispace-integration)

## Decisions Log

| Decision             | Choice                            | Rationale                                         |
| -------------------- | --------------------------------- | ------------------------------------------------- |
| Scope                | All 5 features                    | Full SciSpace capability set                      |
| Architecture         | Feature-Parallel                  | Independent vertical slices, parallel development |
| Feature 1 Agent      | Extend existing CrewAI crew       | Add STRUCTURED_EXTRACTION to existing agent types |
| Feature 4 Connectors | Crossref + PubMed                 | Semantic Scholar already exists                   |
| Feature 5 Detector   | Open-source RoBERTa               | Self-hosted, no vendor dependency                 |
| Feature 2 PDF        | Crop overlay on existing renderer | Inline PDF renderer already in place              |

## Shared Foundation

Before building the 5 features, establish a thin shared layer:

1. **New CrewAI Agent Type**: Add `STRUCTURED_EXTRACTION` to `AgentType` enum in `multi_agent_search_service_v2.py`
2. **Connector Registry**: Enhance connector base in `research_engine/connectors/base.py` with auto-registration pattern
3. **Shared Schemas**: New Pydantic schemas in `backend/src/schemas/` for extraction results, tone options, integrity scores

**Files affected:**

- `backend/src/services/search/multi_agent_search_service_v2.py`
- `backend/src/services/research_engine/connectors/base.py`
- `backend/src/schemas/scispace_schemas.py`

---

## Feature 1: Dynamic Literature Review Matrix

**Purpose:** Select documents in a Research Project, define custom extraction columns (e.g., Methodology, Sample Size, Limitations), and extract structured data into a comparison grid via CrewAI.

### Backend

| Component   | File                                                         | Description                                                                                        |
| ----------- | ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------- |
| API Router  | `backend/src/api/research/extraction_matrix.py`              | CRUD for matrices + trigger extraction                                                             |
| Service     | `backend/src/services/research/extraction_matrix_service.py` | Orchestrates CrewAI extraction, manages matrix state                                               |
| Model       | `backend/src/models/extraction_matrix.py`                    | `ExtractionMatrix` (columns, project_id) + `ExtractionCell` (document_id, column, value, citation) |
| Schema      | `backend/src/schemas/extraction_matrix.py`                   | Request/response Pydantic models                                                                   |
| Celery Task | `backend/src/tasks/extraction_tasks.py`                      | Background extraction per document                                                                 |
| Agent       | Extend `multi_agent_search_service_v2.py`                    | `STRUCTURED_EXTRACTION` agent with JSON-mode output                                                |

### Flow

1. User creates matrix: `POST /api/v1/research/projects/{id}/matrices` with column definitions
2. User triggers extraction: `POST /api/v1/research/matrices/{id}/extract` with document_ids
3. Each document dispatched as Celery task -> CrewAI agent retrieves relevant chunks -> LLM extracts structured JSON per column
4. Results stored in `ExtractionCell` table with inline citation references
5. Frontend polls `GET /api/v1/research/matrices/{id}` for progressive results

### LLM Structured Output

Enforce JSON schema via OpenAI `response_format: { type: "json_schema" }` or Anthropic tool_use for guaranteed grid cell population.

### Frontend

| Component     | File                                                    | Description                              |
| ------------- | ------------------------------------------------------- | ---------------------------------------- |
| Matrix Grid   | `frontend/src/components/research/ExtractionMatrix.tsx` | Editable data grid with TanStack Table   |
| Column Editor | `frontend/src/components/research/ColumnEditor.tsx`     | Add/edit/reorder column headers          |
| Cell Citation | `frontend/src/components/research/CellCitation.tsx`     | Inline citation link -> Document Preview |

### Export

CSV/JSON download from the matrix endpoint.

---

## Feature 2: Deep Tabular & Math Extraction

**Purpose:** Parse tables and math formulas from PDFs into machine-readable formats. Add a Crop & Extract overlay to the PDF viewer.

### Backend

| Component    | File                                                          | Description                               |
| ------------ | ------------------------------------------------------------- | ----------------------------------------- |
| API Router   | `backend/src/api/documents/table_extraction.py`               | Extract tables/math from documents        |
| Service      | `backend/src/services/processing/table_extraction_service.py` | Orchestrates table detection + extraction |
| Dependencies | `pyproject.toml`                                              | Add `camelot-py[cv]`, `tabula-py`         |

### Extraction Pipeline

1. **Auto-detect tables** during document ingestion (extend `multimodal_processing_service.py`):
   - Camelot (lattice mode) for well-structured tables
   - Tabula-py (stream mode) as fallback
   - Store detected table metadata (page, bounding box, row/col count) in document metadata JSON

2. **On-demand crop extraction** (`POST /api/v1/documents/{id}/extract-region`):
   - Accept bounding box coordinates `{ page, x1, y1, x2, y2 }`
   - Crop PDF region using PyMuPDF
   - Route to Camelot for table extraction
   - For math/complex layouts: send cropped image to GPT-4o Vision for transcription to LaTeX/Markdown
   - Return: `{ format: "csv"|"latex"|"markdown", content: "...", confidence: 0.95 }`

3. **Math formula extraction**:
   - Detect formulas via regex in extracted text (LaTeX `$...$`, `\begin{equation}`)
   - For image-based formulas: multimodal LLM transcription
   - Store as LaTeX alongside document chunks

### Frontend

| Component     | File                                                          | Description                               |
| ------------- | ------------------------------------------------------------- | ----------------------------------------- |
| Crop Overlay  | `frontend/src/components/documents/CropExtractOverlay.tsx`    | Drag-to-select region on PDF pages        |
| Table Preview | `frontend/src/components/documents/ExtractedTablePreview.tsx` | Preview + export buttons (CSV/JSON/Excel) |
| Math Display  | `frontend/src/components/documents/MathDisplay.tsx`           | Render LaTeX formulas (KaTeX or MathJax)  |

**Integration:** Add toolbar button "Extract Table/Math" to `DocumentPreview.tsx` that toggles crop overlay mode.

---

## Feature 3: Scholarly Tone Engine & Paraphraser

**Purpose:** Rewrite selected text with adjustable academic tone. Works within Notes and Draft views.

### Backend

| Component  | File                                                   | Description                                    |
| ---------- | ------------------------------------------------------ | ---------------------------------------------- |
| API Router | `backend/src/api/research/tone_engine.py`              | Text rewriting endpoints                       |
| Service    | `backend/src/services/research/tone_engine_service.py` | LLM-based rewriting with citation preservation |

### API

```
POST /api/v1/research/rewrite
{
  "text": "The original paragraph...",
  "tone": "academic" | "simplified" | "concise" | "expanded",
  "preserve_citations": true,
  "model": "claude-sonnet-4-6"
}

Response:
{
  "original": "...",
  "rewritten": "...",
  "tone_applied": "academic",
  "diff_markers": [...],
  "citations_preserved": ["[1]", "[3]"]
}
```

### Citation Preservation

Before sending to LLM, extract all citation markers and positions. System prompt instructs LLM to maintain citations. Post-process to verify all original citations appear in output.

### Tone System Prompts

Stored in `backend/src/core/prompts/tone_prompts.py`:

- **Academic**: Formal vocabulary, passive voice, hedging language, discipline-specific terminology
- **Simplified**: 8th-grade reading level, active voice, concrete examples, no jargon
- **Concise**: Remove redundancy, tighten sentences, preserve meaning in minimal words
- **Expanded**: Add context, examples, transitions, elaboration

### Frontend

| Component    | File                                                   | Description                                          |
| ------------ | ------------------------------------------------------ | ---------------------------------------------------- |
| Tone Toolbar | `frontend/src/components/research/ToneToolbar.tsx`     | Floating toolbar on text selection with tone options |
| Diff View    | `frontend/src/components/research/RewriteDiffView.tsx` | Side-by-side before/after comparison                 |

**Integration:** Selection listener in Notes editor and Draft view. On text selection > 10 words, show floating toolbar. User picks tone, sees diff, accepts or rejects.

---

## Feature 4: Crossref & PubMed Connectors

**Purpose:** Add Crossref and PubMed as source connectors alongside existing ArXiv and Semantic Scholar. Update frontend with source selector.

### Backend

| Component          | File                                                                    | Description                       |
| ------------------ | ----------------------------------------------------------------------- | --------------------------------- |
| Crossref Connector | `backend/src/services/research_engine/connectors/crossref_connector.py` | Crossref REST API                 |
| PubMed Connector   | `backend/src/services/research_engine/connectors/pubmed_connector.py`   | NCBI E-Utilities API              |
| Connector Registry | `backend/src/services/research_engine/connectors/__init__.py`           | Auto-registration                 |
| Celery Tasks       | `backend/src/tasks/research_tasks.py`                                   | Background ingestion per source   |
| KG Mapping         | Extend KG integration                                                   | Crossref/PubMed metadata -> Neo4j |

### Crossref Connector

- API: `https://api.crossref.org/works` (no API key, polite pool with `mailto` header)
- Maps to existing `SourceDocument` dataclass
- Fields: DOI, title, authors, abstract, publisher, journal, citations count, references
- Rate limiting: Respect `X-Rate-Limit-Limit` header
- Timeout: 60s

### PubMed Connector

- API: NCBI E-Utilities (`esearch.fcgi` + `efetch.fcgi`)
- Two-step: search PMIDs -> fetch full records
- Maps to `SourceDocument` with PubMed metadata (MeSH terms, publication type, PMCID)
- XML parsing
- API key optional (3/sec -> 10/sec rate limit)
- Timeout: 60s

### Knowledge Graph Integration

- Author metadata -> `PERSON` entities with `AUTHOR_OF` relationships
- Journal/venue -> `VENUE` entities with `PUBLISHES` relationships
- MeSH terms (PubMed) -> `CONCEPT` entities with `RELATED_TO` relationships
- Deduplication via DOI/PMID/ArXiv ID cross-references

### Frontend

| Component        | File                                                         | Description                                |
| ---------------- | ------------------------------------------------------------ | ------------------------------------------ |
| Source Selector  | `frontend/src/components/research-engine/SourceSelector.tsx` | Dropdown for source selection              |
| Blueprint Update | Update `TemplateSelector.tsx`                                | Blueprints specify which connectors to use |

**Note:** The `systematic_literature_review.yaml` blueprint already lists `semantic_scholar` and `pubmed` as search sources. Adding connectors makes these steps functional.

---

## Feature 5: AI Authorship & Integrity Detector

**Purpose:** Score documents/drafts for AI-generation likelihood using self-hosted RoBERTa classifier.

### Backend

| Component    | File                                                            | Description                       |
| ------------ | --------------------------------------------------------------- | --------------------------------- |
| API Router   | `backend/src/api/documents/integrity.py`                        | Integrity check endpoints         |
| Service      | `backend/src/services/documents/integrity_detection_service.py` | Model loading, inference, scoring |
| Model        | `backend/src/models/integrity_score.py`                         | `IntegrityScore` table            |
| Celery Task  | `backend/src/tasks/integrity_tasks.py`                          | Background scoring                |
| Dependencies | `pyproject.toml`                                                | `transformers`, `torch`           |

### Model

`roberta-base-openai-detector` from HuggingFace (~500MB, loads once on startup).

### API

```
POST /api/v1/documents/{id}/integrity-check
Response 202: { "task_id": "..." }

GET /api/v1/documents/{id}/integrity-score
Response: {
  "document_id": "...",
  "ai_probability": 0.73,
  "human_probability": 0.27,
  "method": "roberta-base-openai-detector",
  "analyzed_at": "2026-02-20T...",
  "segment_scores": [
    { "text_preview": "First 100 chars...", "ai_probability": 0.85 }
  ]
}
```

### Scoring Logic

1. Split document text into ~512-token segments (model max input)
2. Run each segment through RoBERTa classifier
3. Aggregate: weighted average by segment length
4. Store per-segment and aggregate scores
5. Optional: auto-run during ingestion (configurable flag)

### Integration with Draft Generation

After draft generation or tone rewriting, automatically run integrity check and store score.

### Frontend

| Component        | File                                                    | Description                       |
| ---------------- | ------------------------------------------------------- | --------------------------------- |
| Integrity Badge  | `frontend/src/components/documents/IntegrityBadge.tsx`  | Color-coded badge on DocumentCard |
| Integrity Detail | `frontend/src/components/documents/IntegrityDetail.tsx` | Segment-level breakdown           |
| Check Button     | Extend `DocumentPreview.tsx`                            | "Run Integrity Check" action      |

### Thresholds

- Green (< 0.3): Likely human-written
- Yellow (0.3 - 0.7): Mixed/uncertain
- Red (> 0.7): Likely AI-generated

---

## Testing Strategy

Each feature gets:

- **Unit tests**: Service-layer logic, schema validation
- **Integration tests**: API endpoint tests with test database
- **Evaluation metrics**: Feature-specific quality criteria added to DeepEval suite

| Feature       | Key Test Focus                                            |
| ------------- | --------------------------------------------------------- |
| 1. Matrix     | Extraction accuracy vs gold-standard annotations          |
| 2. Tables     | Table parsing accuracy (precision/recall on known tables) |
| 3. Tone       | Citation preservation rate, tone classifier validation    |
| 4. Connectors | API response mapping, deduplication, KG entity creation   |
| 5. Integrity  | Classifier accuracy on known AI/human text samples        |

---

## Database Migrations

New tables required:

- `extraction_matrices` (Feature 1)
- `extraction_cells` (Feature 1)
- `integrity_scores` (Feature 5)
- Extend `documents` metadata JSON for table detection results (Feature 2)

---

## New Dependencies

| Package          | Feature | Purpose                                  |
| ---------------- | ------- | ---------------------------------------- |
| `camelot-py[cv]` | 2       | Table extraction from PDFs               |
| `tabula-py`      | 2       | Fallback table extraction                |
| `transformers`   | 5       | HuggingFace model loading                |
| `torch`          | 5       | Model inference (may already be present) |
| `katex` (npm)    | 2       | LaTeX rendering in frontend              |
