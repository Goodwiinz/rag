# Suggested Commands for RAG_system

## Docker Services (Development)
```bash
# Start all services
docker-compose -f docker-compose.development.yml up -d

# Start specific service
docker-compose -f docker-compose.development.yml up -d backend
docker-compose -f docker-compose.development.yml up -d frontend

# View logs
docker-compose -f docker-compose.development.yml logs -f backend
docker-compose -f docker-compose.development.yml logs -f frontend

# Rebuild service
docker-compose -f docker-compose.development.yml up -d --build backend

# Stop services
docker-compose -f docker-compose.development.yml down
```

## Backend (Python)
```bash
# Local development (from backend/)
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# Run tests
pytest tests/ --cov=src --cov-report=html
pytest tests/specs/ -v  # Specific test suites
pytest tests/ -k "test_name"  # Single test

# Linting & Formatting
black backend/src/
isort backend/src/
mypy backend/src/

# Database migrations
cd backend && alembic upgrade head
cd backend && alembic revision --autogenerate -m "description"
```

## Frontend (TypeScript/Next.js)
```bash
# Development (from frontend/)
npm run dev

# Build
npm run build

# Testing
npm run test              # Jest unit tests
npm run test:e2e          # Playwright E2E tests
npm run test:e2e:ui       # Playwright with UI

# Linting & Formatting
npm run lint
npm run lint:fix
npm run format
npm run type-check

# Validate all
npm run validate
```

## Monorepo (from root)
```bash
npm run dev              # Start frontend dev
npm run build            # Build frontend
npm run lint             # Lint all workspaces
npm run test             # Test all workspaces
npm run test:e2e         # E2E tests
```

## System Utilities (macOS/Darwin)
```bash
# File operations
ls -la                   # List files
find . -name "*.py"      # Find files
grep -r "pattern" .      # Search in files

# Git
git status
git diff
git log --oneline -10

# Process management
lsof -i :8000            # Check port usage
kill -9 <PID>            # Kill process

# Docker
docker ps                # Running containers
docker logs <container>  # Container logs
```
