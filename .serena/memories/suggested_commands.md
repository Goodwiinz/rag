# Suggested Commands

## Docker (Development)
```bash
docker-compose -f docker-compose.development.yml up -d
docker-compose -f docker-compose.development.yml logs -f backend
docker-compose -f docker-compose.development.yml up -d --build backend
docker-compose -f docker-compose.development.yml down
```

## Backend
```bash
cd backend && uvicorn src.main:app --reload --port 8000
pytest tests/ --cov=src
pytest tests/ -k "test_name"
black backend/src/ && isort backend/src/
cd backend && alembic upgrade head
cd backend && alembic revision --autogenerate -m "description"
```

## Frontend (pnpm, NOT npm)
```bash
cd frontend && pnpm dev
cd frontend && pnpm run type-check
cd frontend && pnpm run test
cd frontend && pnpm run lint
cd frontend && pnpm run validate  # lint + type-check + test
cd frontend && pnpm run build
```

## Database Checks
```bash
curl -s http://localhost:6333/collections | python3 -m json.tool
docker exec rag-postgres-1 psql -U postgres -d multimodal_rag_dev -c "SELECT count(*) FROM documents"
```

## Git
```bash
# Feature branches from develop, PRs target develop
git checkout develop && git pull && git checkout -b feature/name
```
