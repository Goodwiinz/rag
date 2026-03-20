# NOUS — Multimodal Intelligence Platform

A production-ready, enterprise-grade multimodal RAG system that retrieves, reasons, and generates across documents, images, audio, and knowledge graphs. Built with Next.js 15 and FastAPI.

| Component  | Status           | Version                  |
| ---------- | ---------------- | ------------------------ |
| Frontend   | Production Ready | Next.js 15.1.3           |
| Backend    | Production Ready | FastAPI 0.104.1          |
| Testing    | Comprehensive    | Jest, Playwright, pytest |
| Deployment | Docker + K8s     | Helm charts available    |

## Quick Start

### Prerequisites

- Node.js 18.17+, Python 3.11+, Docker 24.0+
- 16GB RAM minimum
- API keys for OpenAI and/or Anthropic Claude

### Setup

```bash
# 1. Clone and configure
git clone https://github.com/yourusername/nous.git
cd nous
cp .env .env.local
# Add your API keys to .env.local:
#   OPENAI_API_KEY=sk-...
#   ANTHROPIC_API_KEY=sk-ant-...

# 2. Start all services
docker-compose -f docker-compose.development.yml up -d

# 3. Start frontend
cd frontend && npm install && npm run dev

# 4. Open the app
#   Frontend:  http://localhost:3000
#   API Docs:  http://localhost:8000/docs
```

### Default Users

| Role  | Email                    | Password |
| ----- | ------------------------ | -------- |
| Admin | admin@multimodal-rag.com | REDACTED |
| Demo  | demo@multimodal-rag.com  | demo123  |

### Health Check

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/infrastructure/worker-status
```

## Features

### AI Research Assistant

Full research workflow with citation management, project organization, and AI-powered literature reviews.

- **arXiv Integration** — Search and ingest academic papers with automatic metadata extraction
- **Citation Pipeline** — Hybrid extraction via arXiv API, Semantic Scholar, CrossRef, and PDF parsing
- **Citation Graph** — Interactive Cytoscape.js network visualization backed by Neo4j
- **Bibliography Export** — BibTeX, IEEE, APA, and MLA with incomplete-metadata warnings
- **Research Projects** — Named projects with documents, markdown notes, tags, deadlines, and status tracking
- **Literature Review Drafts** — Multi-agent AI generates versioned reviews organized by themes with inline citations
- **LaTeX Export** — `.tex` + `.bib` files ready for publication
- **Local AI (WebLLM)** — In-browser inference with Llama, Phi, Gemma, and Qwen

### LangGraph Agent System

Intent-based routing to specialized subgraphs with human-in-the-loop controls.

- **Graph Flow**: `rag_node → intent_classifier → memory_retrieval → [route by intent] → tool_node → memory_save → END`
- **12 Agent Tools**: arXiv search/ingest, semantic search, project management, notes, drafts, bibliography, summarization, document comparison, entity extraction, knowledge graph queries
- **4 Subgraphs**: Research (arXiv, search, projects), Writing (drafts, notes, bibliography), Data (entities, graph), General (full tool set)
- **Streaming**: SSE via `/api/v1/agent/stream` with token, tool_start, tool_end, rag_context events
- **Human-in-the-Loop**: `interrupt()` for destructive operations → client polls → `Command(resume=...)` to continue
- **Checkpointing**: AsyncPostgresSaver with MemorySaver fallback

### Multimodal Processing

- **Text**: PDF and TXT ingestion with OCR
- **Images**: Object detection, scene recognition, text extraction
- **Audio**: Speech-to-text with speaker diarization (Whisper)
- **Video**: Frame extraction and audio transcription

### Hybrid Search

- **Vector + Keyword + Graph**: Combined search with reranking
- **Cross-Modal Discovery**: Find related content across file types
- **Entity Navigation**: Interactive knowledge graph exploration
- **Sub-second Latency**: Real-time search response

### Enterprise Security

- JWT auth with secure WebSocket token handling
- Role-based access control (RBAC) with audit logging
- End-to-end encryption for sensitive fields
- SQL injection prevention via validated enums
- CORS with explicit allowlists, rate limiting

## Tech Stack

### Backend

- **Framework**: Python 3.11, FastAPI, Uvicorn/Gunicorn
- **Databases**: PostgreSQL, Neo4j 5.26, Qdrant v1.7.0, Redis 7
- **Processing**: Celery + Redis broker, MinIO (S3-compatible storage)
- **AI/ML**: OpenAI, Anthropic, Azure OpenAI, sentence-transformers, Cohere reranking, spaCy
- **Agent**: LangGraph StateGraph, AsyncPostgresSaver checkpointing
- **Observability**: Prometheus, LangSmith, structlog

### Frontend

- **Framework**: Next.js 15.1.3, React 18, TypeScript strict mode
- **UI**: Tailwind CSS, shadcn/ui, Radix UI
- **State**: Zustand, TanStack Query v5
- **Visualization**: Recharts, Cytoscape.js, vis-network
- **Testing**: Jest, React Testing Library, Playwright

### Infrastructure

- Docker Compose (development + production)
- Kubernetes with Helm charts
- Terraform for AWS resources
- GitHub Actions CI/CD

## Development

```bash
# Backend
cd backend && uvicorn src.main:app --reload --port 8000
pytest tests/ --cov=src

# Frontend
cd frontend
npm run dev          # Dev server
npm run test         # Unit tests
npm run test:e2e     # E2E tests
npm run type-check   # TypeScript validation
npm run validate     # Full suite: lint + type-check + test
```

## API Overview

| Endpoint Group                      | Description                                |
| ----------------------------------- | ------------------------------------------ |
| `POST /api/v1/auth/login`          | JWT authentication                         |
| `POST /api/v1/documents/upload`    | Document ingestion (PDF, text, image, etc) |
| `POST /api/v1/search/`             | Hybrid search (vector + keyword + graph)   |
| `POST /api/v1/agent/execute`       | Async agent execution (returns job_id)     |
| `POST /api/v1/agent/stream`        | SSE streaming agent execution              |
| `POST /api/v1/agent/confirm/{id}`  | Resume human-in-the-loop interrupts        |
| `GET  /api/v1/agent/threads`       | Thread management                          |
| `POST /api/v1/arxiv/search`        | arXiv paper search                         |
| `POST /api/v1/arxiv/import`        | Import papers into knowledge base          |
| `POST /api/v1/citations/extract`   | Extract citation metadata                  |
| `POST /api/v1/citations/export`    | Export bibliography (BibTeX/APA/IEEE/MLA)  |
| `POST /api/v1/projects/{id}/drafts`| Generate literature review                 |
| `GET  /api/v1/quality/metrics`     | RAG quality metrics                        |
| `GET  /health`                      | System health check                        |

Full API docs available at `http://localhost:8000/docs` when running.

## Service Connections

| Service    | Port | UI                              |
| ---------- | ---- | ------------------------------- |
| Frontend   | 3000 | http://localhost:3000            |
| Backend    | 8000 | http://localhost:8000/docs       |
| PostgreSQL | 5432 | —                               |
| Neo4j      | 7687 | http://localhost:7474            |
| Qdrant     | 6333 | http://localhost:6333/dashboard  |
| Redis      | 6379 | —                               |
| MinIO      | 9000 | http://localhost:9001            |
| Flower     | 5555 | http://localhost:5555            |
| Adminer    | 8080 | http://localhost:8080            |

## Quality Metrics

| Metric               | Threshold | Description                    |
| -------------------- | --------- | ------------------------------ |
| Answer Relevancy     | >70%      | Response relevance to query    |
| Faithfulness         | >90%      | Grounding in retrieved context |
| Contextual Relevancy | >70%      | Retrieved context relevance    |
| Latency              | <2000ms   | Response time target           |
| Hallucination Rate   | <10%      | Unsupported claims threshold   |

## Documentation

Detailed docs are organized in [`docs/`](docs/):

| Category                           | Description                              |
| ---------------------------------- | ---------------------------------------- |
| [Architecture](docs/architecture/) | System design and component architecture |
| [Database](docs/database/)         | Schema, Neo4j, Qdrant, migrations        |
| [Deployment](docs/deployment/)     | Docker, K8s, startup guides              |
| [Security](docs/security/)         | Auth, audit, encryption                  |
| [Testing](docs/testing/)           | Test reports and strategies              |
| [Observability](docs/observability/) | Tracing, metrics, dashboards           |
| [Monitoring](docs/monitoring/)     | Prometheus, alerting, runbooks           |
| [Guides](docs/guides/)            | Feature guides and integrations          |
| [API](docs/api/)                   | API docs and OpenAPI specs               |
| [Performance](docs/performance/)   | Optimization and benchmarks              |
| [Frontend](docs/frontend/)         | UI architecture and design audits        |
| [Plans](docs/plans/)              | Implementation plans and task boards     |

## Project Structure

```
.
├── backend/                  # FastAPI application
│   ├── src/
│   │   ├── api/              # Route handlers (auth, documents, search, agent, research)
│   │   ├── services/         # Business logic (agent, research, search, embedding)
│   │   ├── models/           # SQLAlchemy models
│   │   └── core/             # Config, auth, middleware
│   └── tests/
├── frontend/                 # Next.js 15 application
│   ├── app/                  # App router pages
│   ├── src/
│   │   ├── components/       # React components (research, chat, search)
│   │   ├── hooks/            # Custom hooks
│   │   ├── store/            # Zustand stores
│   │   ├── services/         # API clients
│   │   └── types/            # TypeScript types
│   └── tests/
├── brand/                    # Brand assets (logo, guidelines, landing page)
├── docs/                     # Documentation (organized by category)
├── infrastructure/           # Terraform, K8s configs
├── specs/                    # Feature specifications
└── docker-compose.*.yml      # Docker configurations
```

## Contributing

1. Create a feature branch from `develop`
2. Write tests for new functionality
3. Run `npm run validate` (frontend) and `pytest` (backend)
4. Submit a PR targeting `develop`

## License

MIT License — see [LICENSE](LICENSE) for details.
