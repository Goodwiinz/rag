# Database Fixes and Document Indexing Guide

## PostgreSQL Enum Fixes (2026-01-09)

PostgreSQL enums had case-sensitivity issues. The database had UPPERCASE values, but Python sent lowercase.

### Fix Applied:
```sql
-- Add lowercase values to enums
ALTER TYPE workspacerole ADD VALUE IF NOT EXISTS 'owner';
ALTER TYPE workspacerole ADD VALUE IF NOT EXISTS 'admin';
ALTER TYPE workspacerole ADD VALUE IF NOT EXISTS 'member';
ALTER TYPE workspacerole ADD VALUE IF NOT EXISTS 'viewer';

ALTER TYPE threadstatus ADD VALUE IF NOT EXISTS 'active';
ALTER TYPE threadstatus ADD VALUE IF NOT EXISTS 'archived';
ALTER TYPE threadstatus ADD VALUE IF NOT EXISTS 'deleted';

ALTER TYPE messagerole ADD VALUE IF NOT EXISTS 'user';
ALTER TYPE messagerole ADD VALUE IF NOT EXISTS 'assistant';
ALTER TYPE messagerole ADD VALUE IF NOT EXISTS 'system';

-- Update existing records to lowercase
UPDATE workspace_members SET role = 'owner' WHERE role = 'OWNER';
UPDATE workspace_members SET role = 'admin' WHERE role = 'ADMIN';
UPDATE workspace_members SET role = 'member' WHERE role = 'MEMBER';
UPDATE workspace_members SET role = 'viewer' WHERE role = 'VIEWER';
```

### Citations Table Columns Added:
```sql
ALTER TABLE citations ADD COLUMN IF NOT EXISTS external_reference_id VARCHAR(255);
ALTER TABLE citations ADD COLUMN IF NOT EXISTS document_title VARCHAR(500);
ALTER TABLE citations ADD COLUMN IF NOT EXISTS document_type VARCHAR(50);
```

### Citations Table NOT NULL Fix (2026-01-09):
**Issue**: The `document_id` column had a NOT NULL constraint, preventing citations from being saved for external references (e.g., ArXiv papers that use `external_reference_id` instead of `document_id`).

**Symptom**: Assistant messages with citations disappeared after page refresh. The frontend showed a 500 error when trying to save the message with citations.

**Root Cause**: `NotNullViolation` on `citations.document_id` when saving citations with `external_reference_id` only.

**Fix Applied**:
```sql
-- Make document_id nullable to support external references (e.g., ArXiv papers)
ALTER TABLE citations ALTER COLUMN document_id DROP NOT NULL;
```

**Note**: The SQLAlchemy model at `backend/src/models/citation.py` already had `nullable=True`. The database schema was out of sync with the model.

## Document Indexing Instructions

### Index ArXiv Papers to Qdrant
```bash
# From project root, activate virtual environment
source .venv/bin/activate

# Index papers (uses Azure OpenAI for embeddings)
python scripts/index_full_papers.py \
  --dataset "backend/data/arxiv/evaluation_dataset_improved.json" \
  --pdf-dir "backend/data/arxiv" \
  --clear  # Optional: clears existing collection first

# Available options:
#   --chunk-size 1000  (default)
#   --overlap 200      (default)
#   --clear            (clear existing vectors first)
```

### Data Locations:
- PDFs: `backend/data/arxiv/` (83 PDFs) and `data/arxiv/` (180+ PDFs)
- Evaluation datasets: `backend/data/arxiv/evaluation_dataset_improved.json`
- Alternative datasets: `data/arxiv/evaluation_dataset_146.json`, `evaluation_dataset_indexed.json`

### Current Database Status (2026-01-09):
- **Qdrant**: `document_chunks` collection with **752 vectors** (1536 dimensions, Azure OpenAI)
  - 159 papers processed, 47 full PDFs extracted, 158 successfully indexed (99.4% success rate)
- **Neo4j**: 9,889 relations, 3,369+ nodes (Entities, Concepts, Models, Tasks, Documents)
- **PostgreSQL**: `multimodal_rag_dev` database

### Neo4j Credentials (Development):
- User: Environment variable `NEO4J_USER` (default: `neo4j` for dev)
- Password: Environment variable `NEO4J_PASSWORD` (set in docker-compose)
- Access via Docker: `docker exec docker-compose-neo4j-1 cypher-shell -u $NEO4J_USER -p $NEO4J_PASSWORD "QUERY"`

> **Note**: Never commit actual credentials. Use environment variables or a secrets manager.

### Service Verification Commands:
```bash
# Check Qdrant collections
curl -s http://localhost:6333/collections | python3 -m json.tool

# Check Qdrant vector count
curl -s http://localhost:6333/collections/document_chunks | python3 -m json.tool

# Check Neo4j relations
docker exec docker-compose-neo4j-1 cypher-shell -u ${NEO4J_USER:-neo4j} -p ${NEO4J_PASSWORD:-password} \
  "MATCH ()-[r]->() RETURN count(r) as relations"

# Check Neo4j nodes
docker exec docker-compose-neo4j-1 cypher-shell -u ${NEO4J_USER:-neo4j} -p ${NEO4J_PASSWORD:-password} \
  "MATCH (n) RETURN labels(n) as labels, count(n) as count ORDER BY count DESC LIMIT 10"
```

## SQLAlchemy Async Greenlet Fix (2026-01-21)

**Issue**: `greenlet_spawn has not been called; can't call await_only() here` error when accessing API endpoints that use `get_current_organization` dependency.

**Root Cause**: The `get_current_organization` function is synchronous but accesses `current_user.organization`, a lazy-loaded relationship on a User object obtained via an async session. SQLAlchemy cannot perform lazy loading outside the async context.

**Fix Applied**:
Modified `backend/src/core/dependencies.py` to eagerly load the `organization` relationship in `get_current_user`:

```python
from sqlalchemy.orm import selectinload

async def get_current_user(...) -> User:
    stmt = select(User).options(
        selectinload(User.organization)
    ).where(...)
```

**Files Modified**: `backend/src/core/dependencies.py`

**Note**: Similar fixes may be needed if other relationships are accessed in synchronous context from async-fetched objects. Always use `selectinload()` or `joinedload()` for relationships that will be accessed outside the async session context.

## JWT Token Persistence Fix (2026-01-10)

**Issue**: Refresh tokens became invalid after backend restarts
**Root Cause**: `JWT_SECRET_KEY` auto-generates random value when not set in docker-compose environment

**Fix Applied**:
Added persistent `JWT_SECRET_KEY` to `config/docker-compose/docker-compose.development.yml`:
```yaml
# Added to both backend and celery-worker services
- JWT_SECRET_KEY=${JWT_SECRET_KEY:-dev-jwt-persistent-secret-key-32chars!}
```

**Note**: Tokens generated before this fix will still be invalid. Users need to log in once after the fix is applied.

### Troubleshooting:

1. **Rate Limiting (Azure OpenAI)**: The indexing script handles 429 errors with automatic retry
2. **Backend 500 Errors after schema changes**: Restart backend container after enum fixes
3. **401 Unauthorized**: Re-login after backend restart (JWT tokens invalidated)
4. **Empty RAG responses**: Check if documents are indexed in Qdrant collection

### Setup All Databases (Full Reset):
```bash
python scripts/setup_databases.py
```
This initializes PostgreSQL, Neo4j, Qdrant, and Redis with proper schemas and collections.
