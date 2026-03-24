# NOUS — Multimodal Intelligence Platform

**Codename:** NOUS (Greek: νοῦς — mind/intellect)
**Also called:** "the RAG system", "multimodal rag"
**Status:** Active, production-ready core, roadmap in progress
**Repo:** github.com/goodwiins/rag

## What It Is

Enterprise-grade multimodal RAG system that retrieves, reasons, and generates across documents, images, audio, and knowledge graphs. Built with Next.js 15 + FastAPI.

## Tech Stack

- **Frontend**: Next.js 15.1.3, React 18, TypeScript, shadcn/ui, Zustand, TanStack Query
- **Backend**: FastAPI, Python 3.11, Celery, structlog
- **Databases**: PostgreSQL, Neo4j 5.26, Qdrant v1.7.0, Redis 7, MinIO
- **Agent**: LangGraph StateGraph, 12 tools, 4 subgraphs, AsyncPostgresSaver
- **AI**: OpenAI, Anthropic, Azure OpenAI, sentence-transformers, Cohere reranking

## Key Features

- LangGraph agent with intent routing + human-in-the-loop
- Hybrid search (vector + keyword + graph)
- arXiv integration, citation pipeline, bibliography export
- Literature review draft generation
- Knowledge graph (Neo4j) with entity extraction
- SSE streaming + WebSocket real-time
- Enterprise security (JWT, RBAC, audit logs, encryption)

## Brand

- Colors: Ink #0A0A0E, Surface #F7F7F5, Accent #6366F1
- Fonts: Inter (headings), Source Serif 4 (body), JetBrains Mono (code)
- Assets in `brand/` directory

## Roadmap (from K-Dense gap analysis)

| Phase | Timeline | Focus |
|-------|----------|-------|
| Phase 1 | Weeks 1-4 | Code execution sandbox + extended autonomy |
| Phase 2 | Weeks 5-8 | Database connectors + file format parsers |
| Phase 3 | Weeks 9-12 | Publication outputs + domain verticals |
| Phase 4 | Weeks 13-16 | Multi-agent architecture + enterprise compliance |

## Key Decisions

- Brand name NOUS chosen March 2026 (Greek/planetary inspiration, clean & modern vibe)
- Gap analysis vs K-Dense completed March 2026 — 11 issues created in Linear
- Docs reorganized: 51 loose files sorted into 19 categorized subdirectories
- Daily sync scheduled (weekdays 9am) for GitHub + Linear + Obsidian memory

## Connections

| Service | Port |
|---------|------|
| Frontend | 3000 |
| Backend | 8000 |
| PostgreSQL | 5432 |
| Neo4j | 7687 |
| Qdrant | 6333 |
| Redis | 6379 |

## Dev Users

- Admin: admin@multimodal-rag.com / REDACTED
- Demo: demo@multimodal-rag.com / demo123
