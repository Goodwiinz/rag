# SciSpace AI Writer Integration Design

**Date:** 2026-03-01
**Branch:** feature/scispace-frontend-wiring
**Status:** Approved

## Overview

Extend the existing SciSpace frontend wiring (ToneToolbar, RewriteDiffView, IntegrityBadge) with an AI Writer integration that enables inline text completion, section generation, and outline generation within DraftViewer and NoteEditor.

## Approach

**Hybrid:** Floating toolbar for inline completions + section generation. Modal dialog for outline generation. Backend API only (no WebLLM).

## Types & API Contract

### New Types (`frontend/src/types/scispace.ts`)

```typescript
type WriterAction = "complete" | "generate_section" | "generate_outline";
type SectionType =
  | "introduction"
  | "methodology"
  | "results"
  | "discussion"
  | "conclusion"
  | "abstract"
  | "custom";

interface WriteRequest {
  action: WriterAction;
  context: string;
  section_type?: SectionType;
  research_question?: string;
  document_ids?: string[];
  max_tokens?: number;
  style?: "academic" | "technical" | "summary";
}

interface WriteResponse {
  generated: string;
  citations_used: string[];
  section_type?: SectionType;
  confidence: number;
}

interface OutlineRequest {
  research_question: string;
  document_ids?: string[];
  sections?: SectionType[];
  style?: "academic" | "technical" | "summary";
}

interface OutlineResponse {
  outline: OutlineSection[];
  research_question: string;
  document_count: number;
}

interface OutlineSection {
  title: string;
  description: string;
  section_type: SectionType;
  suggested_citations: string[];
}
```

### New API Endpoints (`frontend/src/services/scispaceService.ts`)

- `POST /api/v1/research/write` - Inline completion + section generation
- `POST /api/v1/research/outline` - Outline generation

## Components

### WriterToolbar (`src/components/research/WriterToolbar.tsx`)

Floating toolbar appearing on cursor click in DraftViewer/NoteEditor content areas. Three action buttons:

- **Complete** - Generates continuation from cursor context (~500 chars surrounding)
- **Section** - Dropdown to select section type, generates full section with citations
- **Outline** - Opens OutlineDialog modal

Appears alongside existing ToneToolbar (which triggers on text selection). WriterToolbar triggers on cursor position without selection.

### OutlineDialog (`src/components/research/OutlineDialog.tsx`)

Modal dialog for configuring and generating document outlines:

- Research question input
- Style selector (academic/technical/summary)
- Document scope checkboxes (from project documents)
- Generate button with loading state
- Result panel showing structured outline sections
- Insert into Draft / Copy / Cancel actions

### InsertPreview (`src/components/research/InsertPreview.tsx`)

Preview panel for generated content (similar to RewriteDiffView but for new content):

- Shows generated text with section type label
- Citation count indicator
- Accept / Edit First / Discard buttons
- Scrollable content area

## Integration Points

| Component         | Change                                                        |
| ----------------- | ------------------------------------------------------------- |
| DraftViewer.tsx   | Wire WriterToolbar on cursor click, InsertPreview for results |
| NoteEditor.tsx    | Wire WriterToolbar in edit mode textarea                      |
| Project [id] page | Add "Generate Outline" button in Drafts tab header            |

## Data Flow

```
User Action -> WriterToolbar / OutlineDialog
    |
scispaceService.write() / .generateOutline()
    |
POST /api/v1/research/write  or  /outline
    |
Backend: RAG retrieval (scoped to document_ids) -> LLM generation -> citation mapping
    |
WriteResponse / OutlineResponse
    |
InsertPreview / OutlineDialog result panel
    |
User accepts -> content inserted into DraftViewer/NoteEditor state
```

## Files to Create

### Frontend

- `src/components/research/WriterToolbar.tsx` - Floating toolbar
- `src/components/research/OutlineDialog.tsx` - Outline modal
- `src/components/research/InsertPreview.tsx` - Generated content preview

### Backend (stub endpoints)

- `backend/src/api/research/writer.py` - /write and /outline endpoints

## Files to Modify

### Frontend

- `src/types/scispace.ts` - Add writer types
- `src/services/scispaceService.ts` - Add write() and generateOutline() methods
- `src/components/research/DraftViewer.tsx` - Wire WriterToolbar + InsertPreview
- `src/components/research/NoteEditor.tsx` - Wire WriterToolbar

### Backend

- `backend/src/shared/research_schemas.py` - Add request/response schemas
- `backend/src/main.py` - Register writer router

## Error Handling

- Loading state with cancel button during generation
- Graceful fallback on backend errors (display message, allow retry)
- Toast notification on successful insert

## Testing

- Unit tests for WriterToolbar, OutlineDialog, InsertPreview
- Integration test for DraftViewer + WriterToolbar wiring
- Mock API responses in tests

## Success Criteria

1. User can place cursor in DraftViewer and generate a paragraph continuation
2. User can select a section type and generate a full section with citations
3. User can open outline dialog, configure research question + documents, and generate a structured outline
4. Generated content appears in InsertPreview with accept/edit/discard actions
5. Accepted content is inserted into the draft/note at the correct position
6. All existing ToneToolbar and RewriteDiffView functionality continues working

## References

- SciSpace AI Writer: https://scispace.com/ai-writer
- SciSpace features review: https://effortlessacademic.com/scispace-an-all-in-one-ai-tool-for-literature-reviews/
- SciSpace 2026 review: https://aicurator.io/scispace-review/
