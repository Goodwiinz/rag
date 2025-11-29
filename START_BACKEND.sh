#!/bin/bash

# Quick Backend Startup for RAG System

set -e

echo "🚀 Starting RAG Backend..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}[SETUP]${NC} $1"
}

# Check PostgreSQL is ready
check_database() {
    print_header "Checking database connectivity..."

    if docker exec rag-postgres pg_isready -U raguser &>/dev/null; then
        print_status "PostgreSQL is ready ✓"
    else
        print_error "PostgreSQL is not ready"
        print_status "Please run: ./START_DATABASES.sh"
        exit 1
    fi

    if docker exec rag-postgres psql -U raguser -d ragdb -c "SELECT 1;" &>/dev/null; then
        print_status "Database connection test passed ✓"
    else
        print_error "Database connection test failed"
        exit 1
    fi
}

# Create backend environment
create_env() {
    print_header "Setting up backend environment..."

    cd backend

    # Create environment file
    cat > .env.local << 'EOF'
# Database Configuration
DATABASE_URL=postgresql://raguser:rag_password@localhost:5432/ragdb
DB_HOST=localhost
DB_PORT=5432
DB_NAME=ragdb
DB_USER=raguser
DB_PASSWORD=rag_password

# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=neo4j_password

# Qdrant Configuration
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=

# Redis Configuration
REDIS_URL=redis://localhost:6379/0
REDIS_HOST=localhost
REDIS_PORT=6379

# Application Configuration
ENVIRONMENT=development
LOG_LEVEL=INFO
DEBUG=false

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
SECRET_KEY=dev-secret-key-change-in-production

# CORS Configuration
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# OpenAI Configuration (optional)
OPENAI_API_KEY=your-openai-key-here
ANTHROPIC_API_KEY=your-anthropic-key-here
EOF

    print_status "Environment file created ✓"
}

# Setup Python environment
setup_python() {
    print_header "Setting up Python environment..."

    # Check if we can use the system Python
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        print_error "Python not found"
        exit 1
    fi

    print_status "Using Python: $($PYTHON_CMD --version)"

    # Install requirements if needed
    if [ -f "requirements.txt" ]; then
        print_status "Installing Python dependencies..."
        $PYTHON_CMD -m pip install -r requirements.txt
        print_status "Dependencies installed ✓"
    else
        print_warning "requirements.txt not found"
    fi
}

# Start backend
start_backend() {
    print_header "Starting backend server..."

    # Create logs directory
    mkdir -p ../logs

    # Start backend with uvicorn
    print_status "Starting backend on http://localhost:8000..."
    nohup $PYTHON_CMD -m uvicorn src.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --reload \
        --log-level info \
        > ../logs/backend.log 2>&1 &

    BACKEND_PID=$!
    echo $BACKEND_PID > ../backend.pid

    print_status "Backend started (PID: $BACKEND_PID) ✓"
    cd ..
}

# Wait for backend to be ready
wait_for_backend() {
    print_header "Waiting for backend to be ready..."

    local backend_ready=false
    for i in {1..30}; do
        if curl -f http://localhost:8000/health &>/dev/null; then
            print_status "Backend is ready ✓"
            backend_ready=true
            break
        fi
        echo -n "."
        sleep 2
    done

    if [ "$backend_ready" = false ]; then
        print_error "Backend failed to start"
        print_status "Checking logs..."
        tail -10 logs/backend.log
        return 1
    fi
}

# Test backend functionality
test_backend() {
    print_header "Testing backend functionality..."

    # Test health endpoint
    if curl -f http://localhost:8000/health &>/dev/null; then
        print_status "Health check passed ✓"
    else
        print_error "Health check failed"
        return 1
    fi

    # Test API docs
    if curl -f http://localhost:8000/docs &>/dev/null; then
        print_status "API docs accessible ✓"
    else
        print_warning "API docs not accessible"
    fi
}

# Display status
display_status() {
    print_header "Backend Started Successfully!"
    echo ""
    echo -e "${GREEN}🌐 Backend Access:${NC}"
    echo "  • API Server:         http://localhost:8000"
    echo "  • API Documentation:  http://localhost:8000/docs"
    echo "  • Health Check:       http://localhost:8000/health"
    echo ""
    echo -e "${GREEN}📝 Management:${NC}"
    echo "  • View logs:          tail -f logs/backend.log"
    echo "  • Stop backend:       pkill -f 'uvicorn.*main:app'"
    echo "  • Restart backend:    ./START_BACKEND.sh"
    echo ""
    echo -e "${GREEN}🎯 Next Steps:${NC}"
    echo "  1. Start frontend: cd frontend && npm run dev"
    echo "  2. Open browser: http://localhost:3000"
    echo "  3. Test login and functionality"
    echo ""
}

# Main execution
main() {
    echo "🎯 Start RAG Backend"
    echo "==================="
    echo ""

    check_database
    create_env
    setup_python
    start_backend
    wait_for_backend
    test_backend
    display_status

    echo -e "${GREEN}✅ Backend started successfully!${NC}"
    echo ""
    echo -e "${YELLOW}💡 Backend PID: $(cat backend.pid 2>/dev/null || echo "Unknown")${NC}"
}

# Handle script interruption
trap 'print_warning "Backend startup interrupted."; exit 1' INT

# Run main function
main "$@"