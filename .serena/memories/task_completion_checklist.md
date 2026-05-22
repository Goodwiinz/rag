# Task Completion Checklist

## Before Committing

### Backend
1. `black backend/src/ && isort backend/src/`
2. `cd backend && alembic upgrade head` (if DB changes)
3. `pytest tests/ -v`

### Frontend
1. `cd frontend && pnpm run validate` (lint + type-check + test)
2. Or individually: `pnpm run lint:fix`, `pnpm run type-check`, `pnpm run test`

### Docker
- Rebuild if Dockerfile changed: `docker-compose -f docker-compose.development.yml up -d --build <service>`
- Verify health: `docker-compose -f docker-compose.development.yml ps`

## Evaluation Thresholds
- Answer Relevancy >70%, Faithfulness >90%, Context Relevancy >70%
- Latency <2000ms, Hallucination Rate <10%

## Ports
Backend 8000, Frontend 3000, PostgreSQL 5432, Neo4j 7474/7687, Qdrant 6333, Redis 6379
