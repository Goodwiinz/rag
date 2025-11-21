# Fix PostgreSQL Connection Warnings

## Issue Analysis

From the PostgreSQL logs, I can see:

### ✅ **Database is Working**
- PostgreSQL 15.14 started successfully
- Database system is ready to accept connections
- Existing database "ragdb" detected and skipped initialization

### ⚠️ **Warnings Detected**
```
WARNING: database "ragdb" has no actual collation version, but a version was recorded
LOG: invalid length of startup packet
```

## Root Causes

### 1. **Collation Version Warning**
This happens when PostgreSQL was upgraded or the database was created with a different version. It's a minor warning that doesn't affect functionality.

### 2. **Invalid Startup Packet Error**
This indicates connection attempts that are failing mid-connection, usually due to:
- Backend trying to connect with wrong credentials
- Network connectivity issues between local backend and Docker container
- Backend starting up before database is fully ready

## 🛠️ Solutions

### Solution 1: Fix Backend Connection Timing (Recommended)

The backend is trying to connect before the database is fully ready. Add a delay:

```bash
# Stop the backend
pkill -f "uvicorn.*main:app"

# Wait for database to be fully ready
echo "Waiting for PostgreSQL to be fully ready..."
sleep 15

# Start backend again
cd backend
source .venv/bin/activate
nohup uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload > ../logs/backend.log 2>&1 &
```

### Solution 2: Fix Database Credentials

Check if the backend is using the correct database credentials:

```bash
# Check database connection
docker exec rag-postgres psql -U raguser -d ragdb -c "SELECT 1;"

# If this fails, check your .env.local file:
cat backend/.env.local
```

### Solution 3: Fix Collation Warning (Optional)

This warning is cosmetic but can be fixed by updating the database collation:

```bash
# Connect to PostgreSQL
docker exec -it rag-postgres psql -U raguser -d ragdb

# Update collation version
UPDATE pg_database SET datcollversion = pg_catalog.pg_encoding_to_char(encoding) WHERE datname = 'ragdb';

# Exit PostgreSQL
\q
```

## 🚀 Quick Fix Script

```bash
#!/bin/bash
echo "🔧 Fixing PostgreSQL connection issues..."

# 1. Stop any running backend
pkill -f "uvicorn.*main:app" || true

# 2. Wait for database to be fully ready
echo "Waiting for PostgreSQL to stabilize..."
sleep 15

# 3. Test database connection
if docker exec rag-postgres psql -U raguser -d ragdb -c "SELECT 1;" &>/dev/null; then
    echo "✅ Database connection test passed"
else
    echo "❌ Database connection test failed"
    echo "Checking database status..."
    docker exec rag-postgres pg_isready -U raguser
fi

# 4. Start backend with proper environment
cd backend

# Ensure correct environment
cat > .env.local << 'EOF'
DATABASE_URL=postgresql://raguser:rag_password@localhost:5432/ragdb
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=neo4j_password
QDRANT_URL=http://localhost:6333
REDIS_URL=redis://localhost:6379/0
ENVIRONMENT=development
LOG_LEVEL=INFO
EOF

# Start backend
source .venv/bin/activate
echo "Starting backend..."
nohup uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > ../backend.pid

echo "Backend started with PID: $BACKEND_PID"
echo "Check logs: tail -f ../logs/backend.log"

cd ..
```

## 📊 Verification Steps

After applying the fix:

### 1. Check Backend Health
```bash
curl http://localhost:8000/health
```

### 2. Check Database Connection
```bash
# Test direct database connection
docker exec rag-postgres psql -U raguser -d ragdb -c "SELECT version();"

# Test backend database connection
curl http://localhost:8000/api/v1/health/database
```

### 3. Monitor Logs
```bash
# Watch backend logs for connection errors
tail -f logs/backend.log

# Watch PostgreSQL logs for new warnings
docker logs -f rag-postgres
```

## 🎯 Expected Results

After fixing these issues, you should see:

- ✅ No more "invalid length of startup packet" errors
- ✅ Backend connects to database successfully
- ✅ Application health checks pass
- ✅ Login and authentication work properly
- ✅ Document upload and search functionality works

## 💡 Additional Tips

1. **Check Database Credentials**: Ensure `.env.local` has the correct password
2. **Port Conflicts**: Make sure port 5432 isn't used by another PostgreSQL instance
3. **Firewall**: Ensure Docker can communicate with localhost
4. **Resource Limits**: Give Docker enough memory (recommended: 2GB+ for PostgreSQL)

The collation warnings are cosmetic and won't affect functionality, but the connection errors need to be resolved for the application to work properly.