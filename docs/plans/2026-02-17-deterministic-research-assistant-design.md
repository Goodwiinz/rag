# Deterministic Research AI Assistant — Design Document

**Date**: 2026-02-17
**Status**: Approved
**Approach**: Workflow Engine as Backend Service (Approach A)

## Overview

A Research AI Assistant built as a "Research Mode" extension to the existing Multimodal RAG system. It prioritizes determinism and reproducibility over probabilistic flexibility, using explicit workflow blueprints where the LLM handles only bounded sub-tasks within a code-governed pipeline.

## Core Architecture

Four new components extend the existing system:

### 1. Workflow Engine (`backend/src/research/engine/`)

- Executes research blueprints step-by-step
- Step types: `search`, `screen`, `extract`, `synthesize`, `verify`, `export`
- Enforces deterministic defaults: temperature 0, fixed seeds, version-locked model IDs
- Logs every step's inputs, outputs, parameters, and timing to PostgreSQL
- Supports pause/resume

### 2. Blueprint System (`backend/src/research/blueprints/`)

- YAML definitions describing a sequence of steps with parameters
- Pre-built templates: Systematic Literature Review, Evidence Synthesis, Data Extraction, Meta-Analysis
- Users clone and customize templates via a step editor in the UI
- Versioned and immutable once executed (edits create new versions)

### 3. Source Connectors (`backend/src/research/connectors/`)

- Pluggable adapters: arXiv, Semantic Scholar, PubMed, Google Scholar, web search, structured APIs
- Plus existing RAG document store (user uploads via Qdrant/Neo4j)
- All results normalized into a common `SourceDocument` schema

### 4. Evidence Graph (extends existing Neo4j)

- Node types: `ResearchQuestion`, `SubQuestion`, `Evidence`, `Source`, `Claim`
- Relationships: `DECOMPOSED_INTO`, `SUPPORTED_BY`, `CONTRADICTED_BY`, `EXTRACTED_FROM`, `CITED_IN`
- Cross-references PostgreSQL IDs

## Determinism & Reproducibility Layer

### Execution Modes

- **Deterministic (default)**: Temperature 0, fixed random seed per workflow run, version-locked model IDs. Identical inputs produce identical outputs.
- **Exploratory**: User opts in per-step. Higher temperature, clearly watermarked as `non-reproducible` in UI and audit log. For brainstorming and hypothesis generation.

### Audit Trail (`research_audit_log` table)

Every step execution records: step ID, blueprint version, input hash, output hash, full prompt text, model ID + version, temperature, seed, timestamp, duration, token counts. Completed workflows produce a **Reproducibility Manifest** — a JSON file containing everything needed to re-run and verify.

### Verification Layer

Automated deterministic checks after each LLM step:

- **Source grounding**: Claims checked against source documents
- **Schema validation**: Extracted data matches expected types/ranges
- **Consistency check**: Cross-references between steps don't contradict

Each check produces a pass/fail **quality mark**. Failed checks pause the workflow for user review.

### Bounded LLM Tasks

- The LLM never decides the research path — the blueprint does
- Each LLM call is scoped to a single operation: "summarize this abstract", "extract these 5 fields", "synthesize findings from these 3 papers on X"
- System prompts are templated and versioned as part of the blueprint

## Data Model

### New PostgreSQL Tables

- `research_projects` — id, name, description, owner_id, status, created/updated timestamps
- `research_blueprints` — id, project_id, name, template_source, version, steps (JSONB), parameters (JSONB), is_immutable
- `research_runs` — id, blueprint_id, blueprint_version, status (pending/running/paused/completed/failed), started_at, completed_at, reproducibility_manifest (JSONB)
- `research_steps` — id, run_id, step_index, step_type, mode (deterministic/exploratory), inputs_hash, outputs_hash, full_prompt, model_id, model_version, temperature, seed, output (JSONB), quality_marks (JSONB), started_at, completed_at, token_count
- `research_sources` — id, run_id, connector_type, external_id, title, authors, abstract, url, metadata (JSONB), content_hash
- `research_evidence` — id, step_id, source_id, claim_text, confidence, grounding_status (verified/unverified/failed), page_reference

### Neo4j Extensions

- New node types: `ResearchQuestion`, `SubQuestion`, `Evidence`, `Source`, `Claim`
- New relationships: `DECOMPOSED_INTO`, `SUPPORTED_BY`, `CONTRADICTED_BY`, `EXTRACTED_FROM`, `CITED_IN`
- Links back to PostgreSQL IDs

### Qdrant

- New collection `research_sources` for semantic search over ingested papers
- Metadata filters by project_id, connector_type, date range

## API Design

All routes under `/api/v1/research/`.

### Projects

- `POST /projects` — Create project
- `GET /projects` — List user's projects
- `GET /projects/{id}` — Project details with run history

### Blueprints

- `GET /blueprints/templates` — List pre-built templates
- `POST /projects/{id}/blueprints` — Create/clone blueprint
- `PUT /blueprints/{id}` — Edit blueprint (new version if previously executed)
- `GET /blueprints/{id}` — Get blueprint with step definitions

### Runs

- `POST /blueprints/{id}/runs` — Start execution
- `GET /runs/{id}` — Run status with step progress
- `POST /runs/{id}/pause` — Pause workflow
- `POST /runs/{id}/resume` — Resume workflow
- `GET /runs/{id}/manifest` — Download reproducibility manifest

### Steps

- `GET /runs/{id}/steps` — List step executions with quality marks
- `GET /steps/{id}` — Full step detail (prompt, output, audit data)
- `POST /steps/{id}/retry` — Re-run a failed step

### Evidence & Sources

- `GET /runs/{id}/sources` — Sources discovered/used
- `GET /runs/{id}/evidence` — Evidence graph data
- `GET /projects/{id}/graph` — Full Neo4j evidence graph

### Export

- `POST /runs/{id}/export` — Generate report (PDF/Markdown)
- `GET /runs/{id}/export/{format}` — Download report

### Streaming

- `POST /runs/{id}/stream` — SSE stream of step progress, live outputs, quality marks

## Frontend UI

### Research Dashboard (`/research`)

- Project list with status cards
- Quick-start buttons for each template
- Recent activity feed

### Blueprint Editor (`/research/projects/{id}/blueprint`)

- Ordered step list with expandable cards: step type, description, parameters, model selection, mode toggle
- Add/remove/reorder steps via simple controls
- Template selector, parameter panel for global settings

### Run View (`/research/runs/{id}`)

- Live SSE progress: current step with spinner, completed steps with quality marks
- Expandable step details: output, sources, quality checks, full prompt
- Pause/resume controls
- Mode badges: green (deterministic), amber (exploratory)

### Evidence Map (`/research/projects/{id}/graph`)

- Interactive graph visualization of Neo4j evidence network
- Nodes: research question (center), sub-questions, evidence, sources
- Edges colored by relationship: supports (PHOSPHOR_GREEN), contradicts (red), relates (CYAN)
- Click nodes/edges for detail

### Report Export

- Preview pane with inline citations
- PDF and Markdown export
- Auto-generated reproducibility appendix from audit trail

### Integration

- New "Research" nav item in sidebar
- Research sources feed into existing RAG document store

## LLM Provider Integration

### Provider Architecture (`backend/src/research/providers/`)

- Abstract `LLMProvider` base class: `complete(prompt, params) -> Response`
- Implementations: `ClaudeProvider`, `OpenAIProvider`, `OllamaProvider`
- All enforce deterministic params by default

### Recommended Defaults

- **Synthesis & reasoning**: Claude (claude-sonnet-4-6) — strongest at nuanced analysis
- **Data extraction**: OpenAI (gpt-4o, pinned version) — strong at structured output
- **Summarization & screening**: Local model via Ollama (e.g., Llama 3) — fast, free, fully reproducible
- Users can override per-step

### Version Locking

- Blueprint stores exact model ID strings (e.g., `claude-sonnet-4-6-20250514`)
- Deprecation warnings preserved in audit trail
- Provider wrapper validates model version availability before execution

### Cost Control

- Per-project token budget with configurable limits
- Step-level token estimates in blueprint editor
- Cost breakdown in run summary

## Testing Strategy

### Determinism Tests

- Golden tests: Same blueprint + same inputs twice = identical outputs
- Seed stability: Fixed seed + temperature 0 = identical results across runs
- Blueprint immutability: Edits to executed blueprints create new versions

### Verification Layer Tests

- Source grounding against known documents
- Schema validation against malformed inputs
- Contradiction injection to verify consistency checks

### Integration Tests

- Full workflow end-to-end against mock source connectors
- Pause/resume continuity
- SSE streaming step progress

### Source Connector Tests

- Mock responses per external API
- Normalization to `SourceDocument` schema
- Error handling: timeouts, rate limits, malformed responses

### Frontend Tests

- Blueprint editor: step manipulation, parameter persistence
- Run view: SSE event rendering
- Evidence map: graph node/edge rendering

## Target User

Individual researchers first. Collaboration features (shared projects, role-based access, peer review) planned for a later phase.

## Key Design Principles

1. **Blueprint first, model second** — The workflow is explicit code-like definition, not emergent agent behavior
2. **Deterministic by default** — Exploratory mode is an explicit opt-in, clearly marked
3. **Process reproducibility always** — Even exploratory steps have full audit trails
4. **Bounded LLM tasks** — The AI never decides the research path
5. **Verification at every step** — Automated quality marks, not blind trust
