# Architecture Detail

## Agent System (LangGraph)
- StateGraph with intent-based routing to specialized subgraphs
- Flow: rag_node → intent_classifier → memory_retrieval → [route by intent] → tool_node → memory_save → END
- Subgraphs: research, writing, data, general
- 12 tools, 30s timeout, max 3 concurrent via semaphore
- Destructive tools (ingest, create_note, create_draft) trigger interrupt() for HITL
- Checkpointing: AsyncPostgresSaver (postgresql://, NOT postgresql+asyncpg://)
- Key file: backend/src/services/agent/graph.py

## Agent Endpoints (/api/v1/agent/)
- POST /execute — async job-based (returns job_id, poll via GET /jobs/{job_id})
- POST /stream — SSE streaming (token, tool_start, tool_end, rag_context, done)
- POST /confirm/{job_id} — resume HITL interrupts
- GET /threads, /threads/{id}/messages — thread management

## Search
- Hybrid: parallel vector + graph + keyword with reranking
- Endpoint: /api/v1/search/hybrid

## Auth
- Production: Supabase SSR auth (cookie sessions, no localStorage)
- Dev: JWT-based with access (30min) + refresh (7/30 day) tokens
- WebSocket auth via Sec-WebSocket-Protocol header (NOT URL params)

## Multi-Tenancy
- Workspace-based isolation
- SQL injection prevention via validated enums (src/shared/enums.py)
- CORS explicit allowlists, no wildcards

## Background Jobs
- Trigger.dev v4 (NOT Celery — migrated)
- Tasks in trigger/ directory
- Scheduled: queue-depth-monitor (~5min), system-health-monitor (~15min)

## Observability
- LangSmith tracing for agent
- Prometheus metrics (agent_execution_duration_seconds, agent_tool_calls_total)
- structlog for structured logging
- Test markers: @unit, @integration, @e2e, @performance, @deepeval, @langsmith
