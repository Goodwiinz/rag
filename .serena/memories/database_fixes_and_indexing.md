# Database Fixes and Indexing

## Key Fixes Applied

### PostgreSQL Enum Case Fix (2026-01-09)
- Added lowercase enum values (workspacerole, threadstatus, messagerole)
- Updated existing records to lowercase

### Citations NOT NULL Fix (2026-01-09)
- Made citations.document_id nullable for external references (ArXiv papers)
- SQLAlchemy model already had nullable=True; DB was out of sync

### JWT Token Persistence (2026-01-10)
- JWT_SECRET_KEY now set in docker-compose (was random on restart → tokens invalidated)

### SQLAlchemy Async Greenlet Fix (2026-01-21)
- get_current_user must use selectinload(User.organization) for lazy relationships
- Pattern: any relationship accessed outside async context needs eager loading

### Full-Text Search (2026-01-12, GOO-50)
- search_vector (tsvector) columns on threads + chat_messages
- GIN indexes + auto-update triggers
- Migration: b2c3d4e5f6g7

## Document Indexing
```bash
source backend/.venv/bin/activate
python scripts/index_full_papers.py \
  --dataset "backend/data/arxiv/evaluation_dataset_improved.json" \
  --pdf-dir "backend/data/arxiv" --clear
```

## Current State
- Qdrant: document_chunks collection, 1536 dims (Azure OpenAI embeddings)
- Neo4j: entities, concepts, models, tasks, documents
- DB name: multimodal_rag_dev, container: rag-postgres-1

## Credentials
- Use environment variables (NEO4J_USER, NEO4J_PASSWORD)
- Never commit actual credentials to memory or code
