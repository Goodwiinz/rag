# Multimodal Enterprise RAG System

A production-ready, enterprise-grade Retrieval-Augmented Generation system built with Next.js 15 and FastAPI. Processes and analyzes multimodal content (text, images, audio, video) with advanced knowledge graph capabilities, hybrid search, and comprehensive evaluation frameworks.

## Status

| Component | Status | Version |
|-----------|--------|---------|
| Frontend | Production Ready | Next.js 15.1.3 |
| Backend | Production Ready | FastAPI 0.104.1 |
| Testing | Comprehensive | Jest, Playwright, pytest |
| Deployment | Docker + K8s | Helm charts available |

## Features

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

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/multimodal-rag-system.git
cd multimodal-rag-system

# Start all services with Docker
docker-compose -f docker-compose.development.yml up -d

# Frontend development
cd frontend
npm install
npm run dev

# Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Default Development Users
| Role | Email | Password |
|------|-------|----------|
| Admin | admin@multimodal-rag.com | admin123 |
| Demo | demo@multimodal-rag.com | demo123 |

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

| Category | Description |
|----------|-------------|
| [Architecture](docs/architecture/) | System design and component architecture |
| [Deployment](docs/deployment/) | Deployment strategies and CI/CD guides |
| [Database](docs/database/) | Schema documentation and migration guides |
| [Security](docs/security/) | Security audits and authentication strategies |
| [Testing](docs/testing/) | Testing guides and validation reports |
| [Operations](docs/operations/) | Monitoring, runbooks, and observability |
| [API](docs/api/) | API documentation and OpenAPI specs |
| [Guides](docs/guides/) | Quick start and usage guides |

## Evaluation Metrics

The system tracks RAG quality using the RAG Triad:

| Metric | Threshold | Description |
|--------|-----------|-------------|
| Answer Relevancy | >70% | Response relevance to query |
| Faithfulness | >90% | Grounding in retrieved context |
| Contextual Relevancy | >70% | Retrieved context relevance |
| Latency | <2000ms | Response time target |
| Hallucination Rate | <10% | Unsupported claims threshold |

## Database Connections

| Service | URL | Port |
|---------|-----|------|
| PostgreSQL | localhost | 5432 |
| Neo4j | bolt://localhost | 7687 |
| Qdrant | http://localhost | 6333 |
| Redis | redis://localhost | 6379 |

## Project Structure

```
.
├── backend/           # FastAPI application
│   ├── src/
│   │   ├── api/       # Route handlers
│   │   ├── services/  # Business logic
│   │   ├── models/    # SQLAlchemy models
│   │   └── core/      # Configuration, auth, middleware
│   └── tests/         # Backend tests
├── frontend/          # Next.js application
│   ├── app/           # App Router pages
│   ├── src/
│   │   ├── components/  # React components
│   │   ├── hooks/       # Custom hooks
│   │   ├── store/       # Zustand stores
│   │   └── services/    # API clients
│   └── tests/           # Frontend tests
├── docs/              # Documentation
├── infrastructure/    # Terraform, K8s configs
└── docker-compose.*.yml  # Docker configurations
```

## Contributing

1. Create a feature branch from `develop`
2. Write tests for new functionality
3. Ensure all tests pass: `npm run validate` and `pytest`
4. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) for details.
