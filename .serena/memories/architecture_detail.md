# Architecture Detail

## Stack
- **Backend**: Python 3.11, FastAPI 0.104.1, SQLAlchemy, Celery+Redis, Gunicorn/Uvicorn
- **Frontend**: Next.js 15.1.3, React 18, TypeScript, shadcn/ui+Radix, Zustand 5.0.8, TanStack Query v5, Cytoscape, Recharts
- **AI/ML**: OpenAI GPT-4, Anthropic Claude, CrewAI, sentence-transformers, Whisper, spaCy, custom CV
- **Databases**: PostgreSQL (primary), Qdrant (vectors), Neo4j 5.15 (graph), Redis (cache/jobs)

## Key Components
- Multi-Agent Orchestration (`src/agents/`): CrewAI agents - orchestrator, retrieval, graph, vector, QA, synthesis
- Multimodal Ingestion (`src/ingestion/`): PDF, TXT, JPG/PNG, MP3/MP4 with OCR, transcription, frame extraction
- Knowledge Graph (`src/knowledge_graph/`): Neo4j entity/relationship management
- Vector Store (`src/vector_store/`): Qdrant semantic similarity
- Hybrid Search (`src/search/`): Parallel vector+graph+keyword with reranking
- Real-time (`src/services/`): WebSocket status updates, 10k+ concurrent connections
- Evaluation (`src/evaluation/`): DeepEval RAG Triad metrics

## RAG Quality Targets
- Answer Relevancy >70%, Faithfulness >90%, Context Relevancy >70%
- Latency <2000ms, Hallucination Rate <10%

## Security
- WebSocket auth via Sec-WebSocket-Protocol header (NOT URL params)
- SQL injection prevention via validated enums (`src/shared/enums.py`)
- CORS explicit allowlists (no wildcards)
- IconButton enforces aria-label
- RBAC in `src/security/`

## API Endpoints
- Health: `/api/v1/infrastructure/health`
- Documents: `/api/v1/documents/`
- Search: `/api/v1/search/`
- WebSocket: `ws://localhost:8000/api/v2/ws/connect`
- Real-time status: `/api/v2/realtime/documents/{id}/status`
- WS health: `/api/v2/ws/status`
