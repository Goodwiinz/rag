# NOUS — Claude Code Config

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
- **Colors**: Ink `#0A0A0E`, Surface `#F7F7F5`, Accent `#6366F1`, Accent Soft `#818CF8`, Highlight `#A78BFA`
- **Fonts**: Inter (headings/UI), Source Serif 4 (body), JetBrains Mono (code)
- **Assets**: `brand/` directory — logos, guidelines, landing page

## Dev Users

- Admin: `admin@multimodal-rag.com` / `admin123`
- Demo: `demo@multimodal-rag.com` / `demo123`
