# Multimodal Enterprise RAG System

A production-ready, enterprise-grade Retrieval-Augmented Generation system built with Next.js 15 and FastAPI. Processes and analyzes multimodal content (text, images, audio, video) with advanced knowledge graph capabilities, hybrid search, and comprehensive evaluation frameworks.

## Status

| Component  | Status           | Version                  |
| ---------- | ---------------- | ------------------------ |
| Frontend   | Production Ready | Next.js 15.1.3           |
| Backend    | Production Ready | FastAPI 0.104.1          |
| Testing    | Comprehensive    | Jest, Playwright, pytest |
| Deployment | Docker + K8s     | Helm charts available    |

## Features

### AI Research Assistant

A comprehensive research workflow built on top of the RAG system, helping researchers manage citations, organize projects, and generate literature reviews.

- **Citation Extraction**: Hybrid pipeline — ArXiv API, Semantic Scholar, CrossRef, PDF parsing, with manual fallback
- **Citation Graph**: Interactive Cytoscape.js network visualization of paper relationships stored in Neo4j
- **Bibliography Export**: BibTeX, IEEE, APA, and MLA format export with incomplete-metadata warnings
- **Research Projects**: Create named projects with documents, markdown notes, tags, deadlines, and status tracking
- **Literature Review Drafts**: Multi-agent AI generates versioned literature reviews organized by user-specified themes, with inline `[Doc N]` citations
- **LaTeX Export**: Export drafts as `.tex` + `.bib` files ready for publication
- **Project Chat**: Chat with your documents within project context, with persistent citations across sessions
- **Local AI (WebLLM)**: Run queries against uploaded papers using in-browser models (Llama, Phi, Gemma, Qwen) with model-aware context sizing

### Multimodal Processing

- **Text**: PDF and TXT ingestion with OCR capabilities
- **Images**: Object detection, scene recognition, text extraction
- **Audio**: Speech-to-text with speaker diarization (Whisper)
- **Video**: Frame extraction and audio transcription

### AI-Powered Search

- **Hybrid Search**: Combines vector, graph, and keyword search with reranking
- **Cross-Modal Discovery**: Find related content across different file types
- **Entity Navigation**: Interactive knowledge graph exploration
- **Real-time Results**: Sub-second search response times

### Multi-Agent System

- CrewAI-powered specialized agents (orchestrator, retrieval, graph, vector, QA, synthesis)
- Workflow types: factual lookup, reasoning, multimodal
- Automatic query classification and routing

### Real-time Processing

- WebSocket infrastructure supporting 10,000+ concurrent connections
- Live document processing status with multi-stage visualization
- Automatic reconnection with heartbeat monitoring

### Enterprise Security

- JWT authentication with secure WebSocket token handling
- SQL injection prevention via validated enums
- Role-based access control with audit logging
- CORS protection with explicit allowlists

## Tech Stack

### Backend

- **Framework**: Python 3.11, FastAPI, Uvicorn/Gunicorn
- **Databases**: PostgreSQL, Neo4j 5.15, Qdrant, Redis
- **Processing**: Celery for background jobs
- **AI/ML**: OpenAI, Anthropic, sentence-transformers, Whisper, spaCy, CrewAI
- **Observability**: Prometheus, OpenTelemetry, Sentry, structlog

### Frontend

- **Framework**: Next.js 15.1.3, React 18, TypeScript
- **UI**: Tailwind CSS, shadcn/ui, Radix UI
- **State**: Zustand, TanStack Query v5
- **Visualization**: Recharts, Cytoscape, vis-network
- **Testing**: Jest, React Testing Library, Playwright

### Infrastructure

- Docker Compose (development/production)
- Kubernetes with Helm charts
- Terraform for AWS resources
- GitHub Actions CI/CD

## Quick Start

### Prerequisites

- Node.js 18.17+
- Python 3.11+
- Docker 24.0+ and Docker Compose
- 16GB RAM minimum
- API keys for OpenAI and/or Anthropic Claude

### Environment Setup

1. **Copy environment file**:

```bash
cp .env .env.local
```

2. **Add your AI API keys** to `.env.local`:

```bash
# Required: Add at least one AI provider
OPENAI_API_KEY=sk-your-openai-key-here
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here
```

3. **Optional: Customize other environment variables**:

```bash
# Database URLs (defaults work for Docker setup)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/multimodal_rag_dev
REDIS_URL=redis://localhost:6379/0
NEO4J_URI=bolt://localhost:7687
QDRANT_URL=http://localhost:6333

# Application settings
MAX_CONCURRENT_JOBS=5
LOG_LEVEL=DEBUG
ENVIRONMENT=development
```

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/multimodal-rag-system.git
cd multimodal-rag-system

# Start all services with Docker
docker-compose -f docker-compose.development.yml up -d

# Wait for services to be ready (check with docker-compose ps)
# Then setup frontend
cd frontend
npm install
npm run dev

# Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Quick Health Check

```bash
# Check if all services are running
curl http://localhost:8000/health

# Check database connectivity
curl http://localhost:8000/api/v1/infrastructure/worker-status
```

### Default Development Users

| Role  | Email                    | Password |
| ----- | ------------------------ | -------- |
| Admin | admin@multimodal-rag.com | admin123 |
| Demo  | demo@multimodal-rag.com  | demo123  |

## Development

### Backend Commands

```bash
# Run backend tests
pytest tests/ --cov=src

# Start backend locally
uvicorn src.main:app --reload --port 8000

# View logs
docker-compose -f docker-compose.development.yml logs -f backend
```

### Frontend Commands

```bash
cd frontend

npm run dev          # Development server
npm run build        # Production build
npm run test         # Unit tests
npm run test:e2e     # E2E tests with Playwright
npm run type-check   # TypeScript validation
npm run validate     # Full validation suite
```

## Documentation

Comprehensive documentation is available in the [`docs/`](docs/) directory:

| Category                           | Description                                   |
| ---------------------------------- | --------------------------------------------- |
| [Architecture](docs/architecture/) | System design and component architecture      |
| [Deployment](docs/deployment/)     | Deployment strategies and CI/CD guides        |
| [Database](docs/database/)         | Schema documentation and migration guides     |
| [Security](docs/security/)         | Security audits and authentication strategies |
| [Testing](docs/testing/)           | Testing guides and validation reports         |
| [Operations](docs/operations/)     | Monitoring, runbooks, and observability       |
| [API](docs/api/)                   | API documentation and OpenAPI specs           |
| [Guides](docs/guides/)             | Quick start and usage guides                  |

## Evaluation Metrics

The system tracks RAG quality using the RAG Triad:

| Metric               | Threshold | Description                    |
| -------------------- | --------- | ------------------------------ |
| Answer Relevancy     | >70%      | Response relevance to query    |
| Faithfulness         | >90%      | Grounding in retrieved context |
| Contextual Relevancy | >70%      | Retrieved context relevance    |
| Latency              | <2000ms   | Response time target           |
| Hallucination Rate   | <10%      | Unsupported claims threshold   |

## Environment Variables

### Required Variables

| Variable            | Description                         | Example Value |
| ------------------- | ----------------------------------- | ------------- |
| `OPENAI_API_KEY`    | OpenAI API key for GPT models       | `sk-proj-...` |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude models | `sk-ant-...`  |

### Database Configuration

| Variable         | Description                  | Default (Development)                                              |
| ---------------- | ---------------------------- | ------------------------------------------------------------------ |
| `DATABASE_URL`   | PostgreSQL connection string | `postgresql://postgres:postgres@localhost:5432/multimodal_rag_dev` |
| `REDIS_URL`      | Redis connection string      | `redis://localhost:6379/0`                                         |
| `NEO4J_URI`      | Neo4j connection URI         | `bolt://localhost:7687`                                            |
| `NEO4J_USER`     | Neo4j username               | `neo4j`                                                            |
| `NEO4J_PASSWORD` | Neo4j password               | `password`                                                         |
| `QDRANT_URL`     | Qdrant vector database URL   | `http://localhost:6333`                                            |

### Application Settings

| Variable              | Description             | Default                                       | Options                                |
| --------------------- | ----------------------- | --------------------------------------------- | -------------------------------------- |
| `ENVIRONMENT`         | Application environment | `development`                                 | `development`, `staging`, `production` |
| `DEBUG`               | Enable debug mode       | `true`                                        | `true`, `false`                        |
| `SECRET_KEY`          | Application secret key  | Auto-generated                                | 32+ character string                   |
| `JWT_SECRET_KEY`      | JWT signing secret      | Auto-generated                                | 32+ character string                   |
| `CORS_ORIGINS`        | Allowed CORS origins    | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated URLs                   |
| `LOG_LEVEL`           | Logging level           | `DEBUG`                                       | `DEBUG`, `INFO`, `WARNING`, `ERROR`    |
| `MAX_CONCURRENT_JOBS` | Max background jobs     | `5`                                           | Integer                                |

### AI Model Configuration

| Variable             | Description              | Default                                  |
| -------------------- | ------------------------ | ---------------------------------------- |
| `EMBEDDING_PROVIDER` | Embedding model provider | `sentence_transformers`                  |
| `EMBEDDING_MODEL`    | Specific embedding model | `sentence-transformers/all-MiniLM-L6-v2` |

## API Endpoints Overview

### Authentication (`/api/v1/auth/`)

- `POST /login` - User login with JWT token
- `POST /register` - User registration
- `POST /logout` - User logout
- `GET /me` - Current user profile
- `GET /users` - List users (admin only)

### Document Management (`/api/v1/documents/`)

- `POST /upload` - Upload documents (PDF, TXT, images, audio, video)
- `GET /` - List user documents with metadata
- `GET /{document_id}` - Get document details
- `DELETE /{document_id}` - Delete document
- `GET /{document_id}/status` - Processing status
- `GET /{document_id}/chunks` - Document text chunks

### Search (`/api/v1/search/`)

- `POST /` - Primary search endpoint (hybrid: vector + keyword + graph)
- `POST /vector` - Vector-only search
- `POST /keyword` - Keyword-only search
- `POST /graph` - Graph-based entity search
- `POST /multimodal` - Cross-modal search (find text via image, etc.)
- `GET /suggestions` - Search query suggestions

### Quality & Evaluation (`/api/v1/quality/`)

- `GET /metrics` - RAG quality metrics (relevancy, faithfulness, etc.)
- `POST /evaluate` - Run quality evaluation on search results
- `GET /reports` - Quality evaluation reports
- `POST /feedback` - Submit search result feedback

### Real-time Features (`/api/v1/realtime/`)

- `GET /document-processing-status` - WebSocket for live processing updates
- `GET /search-stream` - WebSocket for streaming search results
- `GET /system-metrics` - WebSocket for live system monitoring

### Research Projects (`/api/v1/projects/`)

- `GET /` - List research projects with filtering
- `POST /` - Create a new research project
- `GET /{id}` - Get project details
- `PATCH /{id}` - Update project metadata
- `DELETE /{id}` - Delete project (cascades to notes and drafts)
- `POST /{id}/notes` - Create a project note (markdown)
- `GET /{id}/notes` - List project notes

### Citations (`/api/v1/citations/`)

- `POST /` - Create a citation manually
- `GET /` - List citations with filtering
- `POST /extract` - Extract citation metadata from a document
- `GET /graph` - Get citation network graph data
- `POST /export` - Export bibliography (BibTeX, IEEE, APA, MLA)

### Draft Generation (`/api/v1/projects/{id}/drafts/`)

- `POST /` - Generate a new literature review draft
- `GET /` - List draft versions
- `GET /{draft_id}` - Get draft content with citations
- `POST /{draft_id}/export` - Export draft (LaTeX + BibTeX, Markdown)

### ArXiv Integration (`/api/v1/arxiv/`)

- `POST /search` - Search ArXiv papers
- `POST /import` - Import ArXiv papers into knowledge base
- `GET /papers` - List imported papers

### Infrastructure & Monitoring (`/api/v1/infrastructure/`)

- `GET /health` - System health check
- `GET /worker-status` - Background job worker status
- `GET /metrics` - Prometheus metrics endpoint
- `GET /stats` - System statistics

### Security (`/api/v1/security/`)

- `GET /audit-logs` - Security audit logs
- `POST /encrypt` - Encrypt sensitive data
- `GET /permissions` - User permissions matrix

### WebSocket Endpoints

- `/ws/document-processing` - Real-time document processing status
- `/ws/search-results` - Streaming search results
- `/ws/system-monitoring` - Live system metrics and health

## Database Connections

| Service    | URL               | Port | UI Access                       |
| ---------- | ----------------- | ---- | ------------------------------- |
| PostgreSQL | localhost         | 5432 | -                               |
| Neo4j      | bolt://localhost  | 7687 | http://localhost:7474           |
| Qdrant     | http://localhost  | 6333 | http://localhost:6333/dashboard |
| Redis      | redis://localhost | 6379 | -                               |

## Research Assistant Architecture

```
Upload Papers ──► Citation Extraction ──► Citation Graph (Neo4j)
                     │                        │
                     ▼                        ▼
              Bibliography Export      Graph Visualization
                                      (Cytoscape.js)

Create Project ──► Add Documents ──► Generate Draft
                   Add Notes          │
                   Project Chat       ▼
                                 Literature Review
                                 (multi-agent pipeline)
                                      │
                                      ▼
                                 Export LaTeX/BibTeX
```

**Citation Extraction Pipeline**:
ArXiv paper → ArXiv API (~90% accuracy) → Semantic Scholar/CrossRef fallback → PDF text parsing → Manual entry

**Draft Generation Pipeline** (CrewAI multi-agent):

1. Orchestrator parses themes and selects documents
2. Retrieval agent fetches relevant sections
3. QA agent extracts key findings per theme
4. Synthesis agent combines into narrative with `[Doc N]` citations
5. Formatter structures output with bibliography

**RAG Context Sizing** (model-aware):

| Model Size         | Documents | Tokens | History     |
| ------------------ | --------- | ------ | ----------- |
| 1B (Phi, Qwen)     | 2         | 600    | 2 messages  |
| 3B (Llama, Gemma)  | 3         | 1,000  | 4 messages  |
| 7B+                | 5         | 2,000  | 8 messages  |
| Cloud (GPT/Claude) | 8         | 4,000  | 20 messages |

## Project Structure

```
.
├── backend/                # FastAPI application
│   ├── src/
│   │   ├── api/
│   │   │   └── research/   # Projects, citations, drafts, chat routes
│   │   ├── services/
│   │   │   └── research/   # Citation, bibliography, draft, graph services
│   │   ├── models/         # SQLAlchemy models (citation, draft, project_note...)
│   │   └── core/           # Configuration, auth, middleware
│   └── tests/              # Backend tests
├── frontend/               # Next.js application
│   ├── app/
│   │   └── (dashboard)/
│   │       └── research/   # Research project pages
│   ├── src/
│   │   ├── components/
│   │   │   └── research/   # Project, citation, draft, note components
│   │   ├── hooks/          # Custom React hooks
│   │   ├── store/          # Zustand stores (citationStore...)
│   │   ├── services/       # API clients (projectService, citationService...)
│   │   └── types/          # TypeScript types (research.ts)
│   └── tests/              # Frontend tests
├── specs/                  # Feature specifications
│   └── 004-research-assistant-feature/
├── docs/                   # Documentation
├── infrastructure/         # Terraform, K8s configs
└── docker-compose.*.yml    # Docker configurations
```

## Contributing

1. Create a feature branch from `develop`
2. Write tests for new functionality
3. Ensure all tests pass: `npm run validate` and `pytest`
4. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) for details.
