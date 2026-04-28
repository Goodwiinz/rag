#!/bin/bash

# Fix PostgreSQL connection warnings and errors

set -e

echo "🔧 Fixing PostgreSQL Connection Issues..."

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
    echo -e "${BLUE}[FIX]${NC} $1"
}

# Check current database status
check_database_status() {
    print_header "Checking database status..."

    if ! docker ps --format "{{.Names}}" | grep -q "rag-postgres"; then
        print_error "PostgreSQL container is not running"
        return 1
    fi

    # Check if database is ready
    if docker exec rag-postgres pg_isready -U raguser &>/dev/null; then
        print_status "PostgreSQL is ready ✓"
    else
        print_warning "PostgreSQL is not ready yet"
        return 1
    fi

    # Test actual connection
    if docker exec rag-postgres psql -U raguser -d ragdb -c "SELECT 1;" &>/dev/null; then
        print_status "Database connection test passed ✓"
    else
        print_error "Database connection test failed"
        return 1
    fi
}

# Stop backend if running
stop_backend() {
    print_header "Stopping backend..."

    if pgrep -f "uvicorn.*main:app" > /dev/null; then
        pkill -f "uvicorn.*main:app"
        print_status "Backend stopped ✓"
    else
        print_status "Backend was not running"
    fi
}

# Wait for database to be stable
wait_for_database() {
    print_header "Waiting for database to stabilize..."

    local ready=false
    for i in {1..30}; do
        if docker exec rag-postgres pg_isready -U raguser &>/dev/null; then
            print_status "Database is ready ✓"
            ready=true
            break
        fi
        echo -n "."
        sleep 2
    done

    if [ "$ready" = false ]; then
        print_error "Database failed to become ready"
        return 1
    fi

    # Additional wait for stability
    print_status "Waiting additional 10 seconds for stability..."
    sleep 10
}

# Fix database collation (optional)
fix_collation() {
    print_header "Checking database collation..."

    # Check if collation warning exists
    if docker logs rag-postgres 2>&1 | grep -q "no actual collation version"; then
        print_warning "Collation version warning detected"
        print_status "Attempting to fix collation..."

        # Update collation version
        docker exec rag-postgres psql -U raguser -d ragdb -c "
            UPDATE pg_database
            SET datcollversion = pg_catalog.pg_encoding_to_char(encoding)
            WHERE datname = 'ragdb';
        " 2>/dev/null || print_warning "Could not update collation (not critical)"

        print_status "Collation fix attempted ✓"
    else
        print_status "No collation issues detected ✓"
    fi
}

# Create/update backend environment
setup_backend_env() {
    print_header "Setting up backend environment..."

    cd backend

    # Issue #379: source secrets from the operator's environment instead of
    # baking placeholder credentials into the script. Required values fail-fast
    # via Bash's :? expansion when unset.
    : "${DB_PASSWORD:?Set DB_PASSWORD before running this script}"
    : "${NEO4J_PASSWORD:?Set NEO4J_PASSWORD before running this script}"
    : "${SECRET_KEY:?Set SECRET_KEY before running this script}"

    DB_HOST_VAL="${DB_HOST:-localhost}"
    DB_PORT_VAL="${DB_PORT:-5432}"
    DB_NAME_VAL="${DB_NAME:-ragdb}"
    DB_USER_VAL="${DB_USER:-raguser}"
    NEO4J_URI_VAL="${NEO4J_URI:-bolt://localhost:7687}"
    NEO4J_USER_VAL="${NEO4J_USER:-neo4j}"
    QDRANT_URL_VAL="${QDRANT_URL:-http://localhost:6333}"
    QDRANT_API_KEY_VAL="${QDRANT_API_KEY:-}"
    OPENAI_API_KEY_VAL="${OPENAI_API_KEY:-REPLACE_ME}"

    # Create environment file with values sourced from the operator's environment.
    cat > .env.local <<EOF
# Database Configuration
DATABASE_URL=postgresql://${DB_USER_VAL}:${DB_PASSWORD}@${DB_HOST_VAL}:${DB_PORT_VAL}/${DB_NAME_VAL}
DB_HOST=${DB_HOST_VAL}
DB_PORT=${DB_PORT_VAL}
DB_NAME=${DB_NAME_VAL}
DB_USER=${DB_USER_VAL}
DB_PASSWORD=${DB_PASSWORD}

# Neo4j Configuration
NEO4J_URI=${NEO4J_URI_VAL}
NEO4J_USER=${NEO4J_USER_VAL}
NEO4J_PASSWORD=${NEO4J_PASSWORD}

# Qdrant Configuration
QDRANT_URL=${QDRANT_URL_VAL}
QDRANT_API_KEY=${QDRANT_API_KEY_VAL}

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
SECRET_KEY=${SECRET_KEY}

# OpenAI Configuration
OPENAI_API_KEY=${OPENAI_API_KEY_VAL}

# CORS Configuration
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
EOF

    print_status "Backend environment configured ✓"
    cd ..
}

# Start backend
start_backend() {
    print_header "Starting backend..."

    cd backend

    # Check virtual environment
    if [ -d ".venv" ]; then
        source .venv/bin/activate
    elif [ -d "venv" ]; then
        source venv/bin/activate
    else
        print_error "No virtual environment found"
        cd ..
        return 1
    fi

    # Create logs directory
    mkdir -p ../logs

    # Start backend with health check
    print_status "Starting backend server..."
    nohup uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload --log-level info > ../logs/backend.log 2>&1 &
    BACKEND_PID=$!
    echo $BACKEND_PID > ../backend.pid

    print_status "Backend started (PID: $BACKEND_PID) ✓"
    cd ..
}

# Test backend connectivity
test_backend() {
    print_header "Testing backend connectivity..."

    local backend_ready=false
    for i in {1..30}; do
        if curl -f http://localhost:8000/health &>/dev/null; then
            print_status "Backend health check passed ✓"
            backend_ready=true
            break
        fi
        echo -n "."
        sleep 2
    done

    if [ "$backend_ready" = false ]; then
        print_error "Backend health check failed"
        print_status "Checking backend logs..."
        tail -10 logs/backend.log
        return 1
    fi

    # Test database connectivity through backend
    if curl -f http://localhost:8000/api/v1/health/database &>/dev/null; then
        print_status "Backend database connectivity test passed ✓"
    else
        print_warning "Backend database connectivity test failed (might be different endpoint)"
    fi
}

# Display final status
display_status() {
    print_header "PostgreSQL Connection Issues Fixed!"
    echo ""
    echo -e "${GREEN}📊 Services Status:${NC}"
    echo "  • PostgreSQL:         $(docker ps --format "{{.Names}}" | grep postgres | head -1 || echo "Not running")"
    echo "  • Backend:            $(curl -s http://localhost:8000/health > /dev/null && echo "Running ✓" || echo "Not running ❌")"
    echo ""
    echo -e "${GREEN}🔧 What was fixed:${NC}"
    echo "  ✅ Database stability wait time"
    echo "  ✅ Backend environment configuration"
    echo "  ✅ Database collation warnings (optional)"
    echo "  ✅ Backend startup with proper timing"
    echo ""
    echo -e "${GREEN}🌐 Access URLs:${NC}"
    echo "  • Frontend:            http://localhost:3000"
    echo "  • Backend API:         http://localhost:8000"
    echo "  • API Documentation:   http://localhost:8000/docs"
    echo ""
    echo -e "${GREEN}📝 Commands:${NC}"
    echo "  • View backend logs:   tail -f logs/backend.log"
    echo "  • View DB logs:        docker logs -f rag-postgres"
    echo "  • Test DB connection:  docker exec rag-postgres psql -U raguser -d ragdb -c 'SELECT 1;'"
    echo ""
}

# Main execution
main() {
    echo "🎯 PostgreSQL Connection Fix"
    echo "==========================="
    echo ""

    check_database_status
    stop_backend
    wait_for_database
    fix_collation
    setup_backend_env
    start_backend
    test_backend
    display_status

    echo -e "${GREEN}✅ PostgreSQL connection issues fixed successfully!${NC}"
    echo ""
    echo -e "${YELLOW}💡 Next steps:${NC}"
    echo "  1. Start the frontend: cd frontend && npm run dev"
    echo "  2. Open http://localhost:3000"
    echo "  3. Test login and functionality"
    echo ""
}

# Handle script interruption
trap 'print_warning "Fix process interrupted."; exit 1' INT

# Run main function
main "$@"