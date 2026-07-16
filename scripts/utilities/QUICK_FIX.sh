#!/bin/bash

# Quick fix for immediate startup issues

echo "🔧 Quick Fix for RAG System Startup Issues"

# 1. Add missing print_error function to startup script
echo "Fixing startup script..."
sed -i.bak '/print_warning() {/,/}/a\
print_error() {\
    echo -e "${RED}[ERROR]${NC} $1"\
}' START_MONITORED_SYSTEM.sh

# 2. Stop services and restart with proper networking
echo "Stopping services..."
docker-compose down

# 3. Start databases only
echo "Starting databases..."
docker-compose up -d postgres neo4j qdrant redis

# 4. Wait for databases to be ready
echo "Waiting for databases..."
sleep 10

# 5. Start backend locally with correct database URLs
echo "Starting backend locally..."
cd backend

# Create local environment file if needed
cat > .env.local << 'EOF'
DATABASE_URL=postgresql://raguser:rag_password@localhost:5432/ragdb
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=neo4j_password
QDRANT_URL=http://localhost:6333
REDIS_URL=redis://localhost:6379/0
EOF

# Start backend
source .venv/bin/activate
nohup uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > ../backend.pid
cd ..

echo "Backend started (PID: $BACKEND_PID)"
echo ""
echo "Next:"
echo "1. Wait 10 seconds for backend to start"
echo "2. Start frontend: cd frontend && npm run dev"
echo "3. Open http://localhost:3000"
echo ""
echo "Check logs: tail -f logs/backend.log"