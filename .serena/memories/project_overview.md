# NOUS Platform Overview

## Purpose
Multimodal Intelligence Platform — RAG system processing text, images, audio, video. Evaluation-first architecture.

## Tech Stack

### Backend (Python 3.12)
- **Web**: FastAPI, Uvicorn/Gunicorn
- **Database**: PostgreSQL (SQLAlchemy 2.0, Alembic), Qdrant (vectors), Neo4j (graph), Redis/Valkey (cache)
- **Agent**: LangGraph StateGraph with intent routing → specialized subgraphs (research, writing, data, general)
- **AI/ML**: OpenAI, Anthropic, Azure OpenAI, sentence-transformers, spaCy
- **Background Jobs**: Trigger.dev v4
- **Observability**: LangSmith, Prometheus, structlog

### Frontend (TypeScript)
- **Framework**: Next.js 15, React 18
- **UI**: shadcn/ui, Radix, Tailwind CSS
- **State**: Zustand, TanStack Query v5
- **Package Manager**: pnpm (not npm)

### Infrastructure
- Docker Compose (dev), DigitalOcean DOKS (staging/prod)
- ArgoCD GitOps, Helm charts, Depot CI
- Supabase (auth in production)

## Key Features
- LangGraph agent with HITL (human-in-the-loop) for destructive tools
- Hybrid search (vector + graph + keyword with reranking)
- Research projects with literature review drafts
- Project-chat integration (threads scoped to project documents)
- ArXiv paper tracking and ingestion
- SSE streaming for agent responses
- Multi-tenant architecture

## Brand
- **Name**: NOUS (Greek: νοῦς — mind/intellect)
- **Colors**: Erebus #0A0A0E, Selene #F7F7F5, Sol #D4A039
- **Fonts**: Inter (headings), Source Serif 4 (body), JetBrains Mono (code)

## Connections
| Service | Port |
|---------|------|
| PostgreSQL | 5432 |
| Neo4j | 7687 |
| Qdrant | 6333 |
| Redis/Valkey | 6379 |
| Backend | 8000 |
| Frontend | 3000 |

## Dev Credentials
- Admin: admin@multimodal-rag.com / admin123
- Demo: demo@multimodal-rag.com / demo123
