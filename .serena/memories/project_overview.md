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
- Chat persistence with workspace/conversation/thread hierarchy
- ArXiv paper tracking and feature extraction
- Terminal Observatory theme (Dashboard, Settings, ArXiv)
- Settings page with profile, appearance, notifications, security controls
- **30-day session persistence with "Remember Me" functionality**
- **AI-generated follow-up suggestions** via `/api/v1/chat/suggestions` endpoint
- **Dynamic Context Panel** showing active document, related results, and suggestions

## Recent Security Fixes (2026-01-09)

### CodeRabbit Review Fixes
1. **API Key Security**: Removed hardcoded Linear API key from `.mcp.json`, now uses `${LINEAR_API_KEY}` env var
2. **Authentication**: Added `get_current_user` dependency to `/chat/suggestions` endpoint to prevent unauthorized LLM API consumption
3. **PII Logging**: Removed `user_email` from logging in cache stats/clear endpoints (GDPR/CCPA compliance)
4. **Thread Safety**: Added `asyncio.Lock()` to `LLMResponseCache` for safe concurrent cache modifications
5. **Timezone Handling**: Fixed timezone-naive datetime parsing in cache deserialization
6. **Config Validation**: Added Pydantic validators for LLM cache config (TTL, max_entries, similarity_threshold)
7. **Build Artifacts**: Added `*.tsbuildinfo` to `.gitignore`
8. **RAG Cache Consistency**: Cache now stores `retrieved_contexts` with responses to ensure citations match returned contexts
9. **Redis Hit Count Sync**: Redis cache hits now persist updated `hit_count` back to Redis with remaining TTL

### Docker Networking Fix
- Fixed Next.js rewrites to use `BACKEND_URL` env var for Docker container networking
- Frontend container now correctly proxies to backend via Docker service name (`http://backend:8000`)
