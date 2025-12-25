# RAG_system Project Overview

## Purpose
Multimodal Enterprise RAG (Retrieval-Augmented Generation) System that processes text, images, audio, and video files. Features evaluation-first architecture with comprehensive testing and metrics tracking.

## Tech Stack

### Backend (Python 3.11)
- **Web Framework**: FastAPI 0.104.1 with Uvicorn/Gunicorn
- **Database**: PostgreSQL (SQLAlchemy 2.0, Alembic migrations)
- **Vector Store**: Qdrant
- **Graph Database**: Neo4j 5.15
- **Cache/Queue**: Redis, Celery 5.3.4
- **AI/ML**: OpenAI, Anthropic, sentence-transformers, Whisper, spaCy
- **Multimodal**: PyMuPDF, pytesseract, OpenCV, Whisper
- **Observability**: Prometheus, OpenTelemetry, Sentry, structlog

### Frontend (TypeScript/Node 18+)
- **Framework**: Next.js 15.1.3
- **UI**: React 18, Radix UI, Tailwind CSS, shadcn/ui
- **State**: Zustand, TanStack Query v5
- **Forms**: react-hook-form, zod
- **Visualization**: Recharts, Cytoscape, vis-network
- **Testing**: Jest, Playwright

### Infrastructure
- Docker Compose (development, production, Azure variants)
- Kubernetes/Helm charts
- Terraform
- GitHub Actions CI/CD

## Key Features
- Multi-agent orchestration (CrewAI)
- Hybrid search (vector + graph + keyword)
- Real-time WebSocket document processing
- RAG evaluation with DeepEval
- Multimodal file processing (PDF, images, audio, video)
