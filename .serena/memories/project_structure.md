# Project Structure

```
RAG_system/
├── backend/src/
│   ├── api/                 # FastAPI route handlers
│   │   ├── agent/           # Agent endpoints (execute, stream, confirm)
│   │   ├── documents/       # Document management (files.py, etc.)
│   │   ├── research/        # Research projects, drafts, project_chat
│   │   ├── auth.py, chat.py, search.py, threads.py
│   │   └── websocket*.py, arxiv*.py
│   ├── services/
│   │   ├── agent/           # LangGraph agent (graph.py, subgraphs, tools)
│   │   ├── research/        # Draft generation, export
│   │   ├── knowledge_graph/ # Neo4j dual-service (KGQueryService, KGWriteService)
│   │   └── chat_service.py, search_service.py, auth_service.py
│   ├── models/              # SQLAlchemy models
│   ├── schemas/             # Pydantic schemas
│   ├── middleware/          # Multi-tenancy, rate limiting
│   ├── core/                # Config, security, dependencies
│   ├── migrations/          # Alembic
│   └── main.py
├── frontend/
│   ├── app/(dashboard)/     # Next.js App Router (grouped layout)
│   │   ├── projects/[id]/   # Project detail page
│   │   ├── chat/, documents/, entities/, search/
│   │   └── settings/
│   ├── src/
│   │   ├── components/      # React components (ui/, chat/, documents/, etc.)
│   │   ├── hooks/           # Custom hooks (useDocumentUpload, useChatPersistence)
│   │   ├── stores/          # Zustand stores
│   │   ├── services/        # API client layer
│   │   └── page-components/ # Page-level components
│   └── package.json         # pnpm
├── trigger/                 # Trigger.dev v4 tasks
├── tests/                   # specs/, unit/, integration/, e2e/
├── k8s/                     # Kubernetes/Helm
├── brand/                   # Logo, guidelines
└── docker-compose.development.yml
```

## Key Entry Points
- Backend: backend/src/main.py
- Frontend: frontend/app/ (Next.js App Router)
- Agent: backend/src/services/agent/graph.py
- Trigger: trigger/ directory
- Docker: docker-compose.development.yml
