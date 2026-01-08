# Task Completion Checklist

## Recent Fixes (2026-01-07)

### Citation UI & Data Persistence Fix
**Status**: ✅ Completed

**Issues Fixed**:
1. **Citation Data Persistence** - Citations now save `document_title`, `document_type`, `external_reference_id` to database
2. **Terminal Observatory Theme** - All citation components updated with phosphor green (#00ff9f) and amber (#ffb700) colors

**Files Modified**:
- `backend/src/services/chat_service.py` - Added missing fields to Citation creation
- `frontend/src/components/chat/CitationPreview.tsx` - Sources panel cards
- `frontend/src/components/chat/CitationPanel.tsx` - Sources sidebar panel
- `frontend/src/components/chat/CitationLink.tsx` - Inline [1] hover preview
- `frontend/app/chat/layout.tsx` - Citations tab in Context Panel

**Note**: Old citations in DB won't have titles; only new messages will display properly.

---


## Before Committing Code

### Backend (Python)
1. **Format code**
   ```bash
   black backend/src/
   isort backend/src/
   ```

2. **Type check**
   ```bash
   mypy backend/src/
   ```

3. **Run tests**
   ```bash
   pytest tests/ -v
   ```

4. **If database changes**
   ```bash
   cd backend && alembic revision --autogenerate -m "description"
   cd backend && alembic upgrade head
   ```

### Frontend (TypeScript)
1. **Lint and format**
   ```bash
   cd frontend && npm run lint:fix
   cd frontend && npm run format
   ```

2. **Type check**
   ```bash
   cd frontend && npm run type-check
   ```

3. **Run tests**
   ```bash
   cd frontend && npm run test
   ```

4. **Full validation**
   ```bash
   cd frontend && npm run validate
   ```

### Docker Services
1. **Rebuild if Dockerfile changed**
   ```bash
   docker-compose -f docker-compose.development.yml up -d --build <service>
   ```

2. **Verify service health**
   ```bash
   docker-compose -f docker-compose.development.yml ps
   docker-compose -f docker-compose.development.yml logs <service>
   ```

## Evaluation Thresholds
The system tracks these metrics (from CLAUDE.md):
- Answer Relevancy: >70%
- Faithfulness: >90%
- Contextual Relevancy: >70%
- Latency: <2000ms
- Hallucination Rate: <10%

## Common Ports to Verify
- Backend API: 8000
- Frontend: 3000
- PostgreSQL: 5432
- Neo4j: 7474/7687
- Qdrant: 6333/6334
- Redis: 6379
