# RAG System Codebase Context

## Project Overview

This is a **Multimodal Enterprise RAG (Retrieval-Augmented Generation) System** - a production-ready, enterprise-grade application that processes and analyzes multimodal content (text, images, audio, video) with advanced knowledge graph capabilities, hybrid search, and comprehensive evaluation frameworks.

The system is built with **Next.js 15** for the frontend and **FastAPI** for the backend, featuring a sophisticated multi-database architecture with PostgreSQL, Neo4j, Qdrant, and Redis.

## Architecture Overview

```mermaid
graph TB
    subgraph "Frontend Layer - Next.js 15"
        UI[React UI Components]
        Store[Zustand State Management]
        Query[TanStack Query v5]
        WS[WebSocket Client]
    end
    
    subgraph "API Gateway - FastAPI"
        API[REST API Endpoints]
        WSS[WebSocket Server]
        Auth[JWT Authentication]
        RBAC[Role-Based Access Control]
    end
    
    subgraph "Processing Layer"
        Celery[Background Jobs]
        Crew[CrewAI Agents]
        Pipeline[AI Processing Pipeline]
    end
    
    subgraph "Database Layer"
        PG[(PostgreSQL)]
        Neo4j[(Neo4j)]
        Qdrant[(Vector DB)]
        Redis[(Cache/Sessions)]
    end
    
    subgraph "AI Services"
        OpenAI[OpenAI GPT]
        Anthropic[Claude]
        Whisper[Audio Processing]
        CV[Computer Vision]
    end
    
    UI --> Store
    Store --> Query
    Query --> API
    WS --> WSS
    
    API --> Auth
    API --> Celery
    Auth --> RBAC
    
    Celery --> Pipeline
    Pipeline --> Crew
    Pipeline --> AI Services
    
    API --> PG
    API --> Neo4j
    API --> Qdrant
    API --> Redis
    
    Crew --> OpenAI
    Crew --> Anthropic
    Pipeline --> Whisper
    Pipeline --> CV
```

## Key Directories and Their Purposes

### Root Level
```
/home/clawdbot/clawd/rag/
├── backend/              # FastAPI backend application
├── frontend/             # Next.js 15 frontend application
├── docs/                 # Comprehensive project documentation
├── database/             # Database schemas and migrations
├── config/               # Configuration files for different environments
├── infrastructure/       # Terraform, Kubernetes, Helm charts
├── monitoring/           # Prometheus, Grafana, observability configs
├── scripts/              # Utility scripts for development and operations
├── tests/                # Cross-cutting test suite
├── notebooks/            # Jupyter notebooks for experiments
└── shared/               # Shared models and utilities
```

### Backend Structure (`/backend/src/`)
```
backend/src/
├── api/                  # FastAPI route handlers organized by domain
│   ├── auth/            # Authentication and user management
│   ├── documents/       # Document upload, processing, management
│   ├── search/          # All search-related endpoints
│   ├── quality/         # RAG quality metrics and monitoring
│   ├── realtime/        # WebSocket endpoints and real-time features
│   ├── arxiv/           # ArXiv paper processing
│   ├── infrastructure/  # System monitoring and worker management
│   └── security/        # Security, encryption, compliance
├── services/            # Business logic layer
├── models/              # SQLAlchemy database models
├── core/                # Core application configuration and utilities
├── auth/                # Authentication middleware and RBAC
├── tasks/               # Celery background tasks
├── migrations/          # Database migration scripts
└── websocket/           # WebSocket connection management
```

### Frontend Structure (`/frontend/src/`)
```
frontend/src/
├── page-components/     # Page-level components organized by feature
│   ├── auth/           # Login, registration pages
│   ├── documents/      # Document management UI
│   ├── search/         # Search interface
│   ├── analytics/      # Analytics dashboards
│   ├── monitoring/     # System monitoring UI
│   └── evaluation/     # RAG evaluation interface
├── components/         # Reusable UI components
├── hooks/             # Custom React hooks
├── store/             # Zustand state stores
├── services/          # API client services
├── types/             # TypeScript type definitions
└── utils/             # Utility functions
```

## Tech Stack Summary

### Frontend Stack
- **Framework**: Next.js 15.1.3 (App Router)
- **UI Framework**: React 18 with TypeScript
- **Styling**: Tailwind CSS with shadcn/ui and Radix UI primitives
- **State Management**: Zustand for client state
- **Data Fetching**: TanStack Query v5 for server state
- **Visualizations**: 
  - Recharts for analytics dashboards
  - Cytoscape for knowledge graph visualization
  - vis-network for network diagrams
- **Rich Text**: TipTap editor
- **Testing**: Jest, React Testing Library, Playwright E2E

### Backend Stack
- **Framework**: FastAPI 0.104.1 with Python 3.11
- **Web Server**: Uvicorn/Gunicorn
- **Background Jobs**: Celery with Redis broker
- **Authentication**: JWT with role-based access control
- **AI Integration**: OpenAI, Anthropic Claude, sentence-transformers
- **Multi-Agent System**: CrewAI for specialized agent workflows
- **Audio Processing**: OpenAI Whisper for speech-to-text
- **Computer Vision**: Various CV models for image analysis
- **Observability**: Prometheus metrics, OpenTelemetry, Sentry error tracking
- **Testing**: pytest, FastAPI TestClient

### Database Architecture
- **Primary Database**: PostgreSQL (user data, documents, metadata)
- **Vector Database**: Qdrant (semantic embeddings)
- **Graph Database**: Neo4j 5.15 (knowledge graph, relationships)
- **Cache/Sessions**: Redis (caching, Celery broker, session storage)

### Infrastructure
- **Containerization**: Docker with multi-stage builds
- **Orchestration**: Kubernetes with Helm charts
- **IaC**: Terraform for AWS resources
- **CI/CD**: GitHub Actions
- **Monitoring**: Prometheus + Grafana + OpenTelemetry

## Database Schema Overview

### PostgreSQL Schema
- **Users & Authentication**: User accounts, roles, permissions
- **Documents**: Document metadata, upload tracking, processing status
- **Search**: Query logs, search analytics, quality metrics
- **Quality Metrics**: RAG evaluation results, performance tracking
- **AB Testing**: Experiment configurations and results
- **Analytics**: User behavior, system performance metrics

### Neo4j Graph Schema
- **Entities**: Documents, concepts, people, organizations
- **Relationships**: Citations, references, semantic relationships
- **Knowledge Graph**: Hierarchical knowledge structure with typed relationships

### Qdrant Vector Collections
- **Document Embeddings**: Semantic vectors for document chunks
- **Query Embeddings**: Search query vectors for similarity matching
- **Multimodal Embeddings**: Image and audio content vectors

### Redis Data Structures
- **Sessions**: User session data and WebSocket connections
- **Cache**: API response caching with TTL
- **Background Jobs**: Celery task queues and results

## API Endpoints Summary

### Core API Groups
```
/api/v1/
├── auth/              # Authentication and user management
├── documents/         # Document CRUD and file operations
├── search/            # Search endpoints (vector, hybrid, graph)
├── quality/           # RAG quality metrics and evaluation
├── realtime/          # WebSocket endpoints for real-time features
├── infrastructure/    # System monitoring and worker status
├── security/          # Encryption, compliance, RBAC
└── arxiv/             # ArXiv paper processing and analysis
```

### Key WebSocket Endpoints
- `/ws/document-processing` - Real-time document processing status
- `/ws/search-results` - Streaming search results
- `/ws/system-monitoring` - Live system metrics

## Development Workflow Notes

### Local Development Setup
1. **Prerequisites**: Node.js 18.17+, Python 3.11+, Docker 24.0+, 16GB RAM
2. **Quick Start**: `docker-compose -f docker-compose.development.yml up -d`
3. **Frontend Dev**: `cd frontend && npm run dev` (http://localhost:3000)
4. **Backend Dev**: `uvicorn src.main:app --reload` (http://localhost:8000)

### Testing Strategy
- **Frontend**: Unit tests with Jest, integration tests with React Testing Library
- **E2E Tests**: Playwright with multiple browser configurations
- **Backend**: Unit tests with pytest, integration tests with TestClient
- **Contract Tests**: API contract validation
- **Load Tests**: Performance testing with custom load test suite

### Code Quality Tools
- **Frontend**: ESLint, Prettier, TypeScript strict mode
- **Backend**: Black (formatting), isort (imports), mypy (type checking), ruff (linting)
- **Pre-commit Hooks**: Automated formatting and linting

### Deployment Environments
- **Development**: Local Docker Compose setup
- **Staging**: Kubernetes cluster with Helm
- **Production**: Multi-region Kubernetes with auto-scaling

## Key Features

### Multimodal Processing
- **Text Processing**: PDF and TXT with OCR capabilities
- **Image Analysis**: Object detection, scene recognition, text extraction
- **Audio Processing**: Speech-to-text with speaker diarization
- **Video Processing**: Frame extraction and audio transcription

### AI-Powered Search
- **Hybrid Search**: Vector + keyword + graph search with reranking
- **Cross-Modal Discovery**: Find related content across different media types
- **Entity Navigation**: Interactive knowledge graph exploration
- **Real-time Results**: Sub-second search response times

### Multi-Agent System
- **CrewAI Integration**: Specialized agents for different tasks
- **Agent Types**: Orchestrator, retrieval, graph, vector, QA, synthesis
- **Workflow Types**: Factual lookup, reasoning, multimodal analysis

### Enterprise Security
- **Authentication**: JWT with secure WebSocket token handling
- **Authorization**: Role-based access control with fine-grained permissions
- **Data Protection**: Encryption at rest and in transit
- **Compliance**: Audit logging and data governance features

## Performance Metrics

### RAG Quality (RAG Triad)
- **Answer Relevancy**: >70% (response relevance to query)
- **Faithfulness**: >90% (grounding in retrieved context)
- **Contextual Relevancy**: >70% (retrieved context relevance)
- **Response Latency**: <2000ms target
- **Hallucination Rate**: <10% threshold

### System Performance
- **WebSocket Connections**: Supports 10,000+ concurrent connections
- **Search Response Time**: Sub-second for most queries
- **Document Processing**: Parallel processing with status tracking
- **Auto-scaling**: Kubernetes HPA based on CPU/memory usage

## Notable Dependencies

### Frontend Key Dependencies
- `@tanstack/react-query@5.90.5` - Server state management
- `@radix-ui/*` - Accessible UI primitives
- `cytoscape@3.28.1` - Knowledge graph visualization
- `@tiptap/*` - Rich text editor
- `framer-motion@12.23.26` - Animations and gestures
- `zustand@5.0.8` - Client state management

### Backend Key Dependencies
- `fastapi@0.104.1` - Web framework
- `celery` - Background task processing
- `crewai` - Multi-agent AI framework
- `qdrant-client` - Vector database client
- `neo4j` - Graph database driver
- `sqlalchemy` - ORM for PostgreSQL
- `prometheus-client` - Metrics collection

This codebase represents a mature, enterprise-ready RAG system with comprehensive testing, monitoring, and deployment infrastructure. The modular architecture supports independent scaling of components and provides clear separation of concerns across the stack.

## Recent Updates & Current Status (January 2025)

### Latest Enhancements
- **Enhanced WebSocket Infrastructure**: Real-time document processing with improved connection handling
- **Advanced RAG Quality Metrics**: Comprehensive evaluation framework with RAG Triad metrics
- **Multi-Agent CrewAI System**: Specialized agents for orchestration, retrieval, synthesis, and QA
- **Cross-Modal Search Capabilities**: Search across text, images, audio, and video content
- **Performance Optimizations**: Achieved sub-second search response times
- **Enterprise Security**: Enhanced RBAC, audit logging, and data protection features

### Development Focus Areas
- **API Standardization**: Consistent REST API patterns across all endpoints
- **Testing Infrastructure**: Comprehensive Jest, Playwright, and pytest coverage
- **Documentation**: Active maintenance of technical documentation and developer guides
- **Monitoring & Observability**: Prometheus metrics, OpenTelemetry, and Sentry integration
- **Deployment Automation**: Docker, Kubernetes, and Terraform infrastructure as code

### Key Integrations
- **AI Providers**: OpenAI GPT models and Anthropic Claude integration
- **Vector Database**: Qdrant for semantic similarity search
- **Graph Database**: Neo4j for knowledge graph navigation and entity relationships
- **Real-time Features**: WebSocket-based live updates for processing and search

This system is actively maintained and represents current best practices for enterprise RAG implementations.