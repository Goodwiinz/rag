# NOUS — Claude Code Config

## Memory System

This project uses a **two-tier memory system**. Always read relevant memory files before starting any non-trivial task.

### Tier 1 — Hot Cache (this file)
Quick-reference tables for people, terms, projects, and connections. Keep it concise — pointers only, not full logs.

### Tier 2 — Memory Directory (`memory/`)
Full knowledge base. Read the relevant file(s) before working:

| File | When to read |
|------|-------------|
| `memory/people/abdel.md` | Any task involving preferences, context, or ownership |
| `memory/projects/nous-platform.md` | Any NOUS codebase work |
| `memory/projects/gap-analysis.md` | Anything related to K-Dense gaps or GOO-187→197 |
| `memory/context/tooling.md` | MCP connections, branch strategy, local paths |
| `memory/glossary.md` | Unfamiliar terms (NOUS, HITL, KG, etc.) |
| `memory/claude-md-updates.md` | Recent changes to memory/CLAUDE.md |
| `daily-logs/YYYY-MM-DD.md` | Yesterday's shipped work and active WIP |

### Updating Memory
When you complete work, make decisions, or discover new context:
1. Update the relevant `memory/` file with what changed
2. Update the hot-cache tables below if the change affects people, terms, or projects
3. Keep updates factual and concise — no narrative fluff
4. Run `./sync-to-obsidian.sh` (on macOS) to push changes to the Obsidian vault

---

## People

| Who | Role |
|-----|------|
| **Abdel** | Owner/developer, goodwiins (GitHub), allocs16@gmail.com |
→ Full profile: memory/people/abdel.md

## Terms

| Term | Meaning |
|------|---------|
| NOUS | Multimodal Intelligence Platform (Greek: νοῦς — mind/intellect) |
| RAG | Retrieval-Augmented Generation |
| HITL | Human-in-the-loop (agent interrupt pattern) |
| KG | Knowledge Graph (Neo4j) |
| subgraph | Specialized agent routing (research, writing, data, general) |
| tool loop | One agent tool call iteration (max 8-10 currently) |
| destructive tool | ingest, create_note, create_draft — triggers HITL interrupt |
| circuit breaker | Resilience pattern for Neo4j/Qdrant/Cohere |
→ Full glossary: memory/glossary.md

## Projects

| Name | What |
|------|------|
| **NOUS Platform** | Multimodal RAG — Next.js 15 + FastAPI + PG/Qdrant/Neo4j/Redis |
| **Gap Analysis** | K-Dense competitive analysis — 11 Linear issues (GOO-187→GOO-197) |
| **Daily Sync** | Scheduled task: GitHub + Linear + Obsidian (weekdays 9:10am) |
→ Details: memory/projects/

## Connections

| Service | Config |
|---------|--------|
| **Linear** | Team: Goodwiinz |
| **GitHub** | Repo: goodwiins/rag |
| **Obsidian** | Vault: Mysynic @ `/Users/goodwiinz/Documents/claude-memory` — sync via `./sync-to-obsidian.sh` |
→ Full tooling: memory/context/tooling.md

## Serena Memories

Read relevant memories before starting tasks:

- `project_structure` — Codebase organization
- `project_overview` — System architecture
- `design_patterns` — Patterns used in codebase
- `code_style_conventions` — Coding standards
- `architecture_detail` — Full stack/component details
- `fix_history` — Past bug fixes and lessons learned
- `coderabbit_findings` — Code review findings
- `auto_fix_patterns` — Reusable fix templates
- `database_fixes_and_indexing` — DB optimization notes
- `thread_workflow_analysis` — Thread/conversation workflow
- `task_completion_checklist` — Task verification checklist

## Agent System Quick Ref

- **Architecture**: LangGraph StateGraph with intent routing → specialized subgraphs (research, writing, data, general)
- **Checkpointing**: AsyncPostgresSaver (fallback: MemorySaver)
- **Tools**: 12 tools with filtered tool nodes per subgraph, 30s timeout, max 3 concurrent via semaphore
- **Human-in-the-loop**: `interrupt()` for destructive tools → client polls → `Command(resume=...)` to continue
- **Streaming**: SSE via `/api/v1/agent/stream` (events: token, tool_start, tool_end, rag_context, done, error)
- **Observability**: LangSmith tracing + Prometheus metrics (`agent_execution_duration_seconds`, `agent_tool_calls_total`)
- **Test markers**: `@unit`, `@integration`, `@e2e`, `@performance`, `@deepeval`, `@langsmith`
- **Key files**: `backend/src/services/agent/graph.py` (main graph), `backend/src/api/agent/execute.py` (endpoints + tool impls)

## Brand

- **Name**: NOUS (Greek: νοῦς — mind/intellect)
- **Colors**: Erebus `#0A0A0E`, Selene `#F7F7F5`, Sol `#D4A039`, Helios `#E8B84A`, Apollo `#F5D680`
- **Fonts**: Inter (headings/UI), Source Serif 4 (body), JetBrains Mono (code)
- **Assets**: `brand/` directory — logos, guidelines, landing page

## Dev Users

- Admin: `admin@multimodal-rag.com` / `admin123`
- Demo: `demo@multimodal-rag.com` / `demo123`

## Preferences

- Clean & modern design aesthetic
- Greek/planetary naming inspiration
- Feature branches from `develop`, PRs target `develop`
