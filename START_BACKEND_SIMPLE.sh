#!/bin/bash

# Simple Backend Startup using Docker Compose

set -e

echo "🚀 Starting RAG Backend (Simple Mode)..."

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

# Check if PostgreSQL is running
check_database() {
    print_header "Checking database status..."

    if ! docker ps --format "{{.Names}}" | grep -q "rag-postgres"; then
        print_error "PostgreSQL is not running"
        print_status "Please start databases first: docker-compose up -d postgres"
        exit 1
    fi

    if docker exec rag-postgres pg_isready -U raguser &>/dev/null; then
        print_status "PostgreSQL is ready ✓"
    else
        print_warning "PostgreSQL might not be ready yet"
        sleep 5
    fi
}

# Check if backend is already running
check_existing_backend() {
    if docker ps --format "{{.Names}}" | grep -q "rag-backend"; then
        print_warning "Backend container is already running"
        print_status "Stopping existing backend..."
        docker-compose stop backend || true
        docker-compose rm -f backend || true
    fi
}

# Create/update backend environment in docker-compose
update_docker_compose() {
    print_header "Updating Docker Compose configuration..."

    # Update backend service environment
    sed -i.bak '/container_name: rag-backend/,/container_name: rag-backend\
    /image: rag-system\/backend:latest,/\
    /environment:/,/environment:' >>' backend/Dockerfile.tmp && \
        cat backend/Dockerfile.tmp >> backend/Dockerfile && \
        mv backend/Dockerfile backend/Dockerfile.new && \
        rm backend/Dockerfile.tmp backend/Dockerfile.bak 2>/dev/null || true

    # Add or update backend service in docker-compose.yml
    if ! grep -q "rag-backend:" docker-compose.yml; then
        print_status "Adding backend service to docker-compose.yml..."
        cat >> docker-compose.yml << 'EOF'

  # Backend API Service
  rag-backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.production
    container_name: rag-backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://raguser:rag_password@postgres:5432/ragdb
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=neo4j_password
      - QDRANT_URL=http://qdrant:6333
      - REDIS_URL=redis://redis:6379/0
      - ENVIRONMENT=development
      - LOG_LEVEL=INFO
      - SECRET_KEY=dev-secret-key-change-in-production
      - CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
    depends_on:
      - postgres
      - neo4j
      - qdrant
      - redis
    networks:
      - rag-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
EOF
        print_status "Backend service added to docker-compose.yml ✓"
    else
        print_status "Backend service already exists in docker-compose.yml ✓"
    fi
}

# Start backend using docker-compose
start_backend() {
    print_header "Starting backend service..."

    # Build and start backend
    print_status "Building and starting backend..."
    docker-compose up -d --build backend

    print_status "Backend service started ✓"
}

# Wait for backend to be ready
wait_for_backend() {
    print_header "Waiting for backend to be ready..."

    local backend_ready=false
    for i in {1..60}; do
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
        print_status "Checking container logs..."
        docker-compose logs backend | tail -20
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
        print_warning "API docs not accessible (normal during startup)"
    fi
}

# Display status
display_status() {
    print_header "Backend Started Successfully!"
    echo ""
    echo -e "${GREEN}📊 Services Status:${NC}"
    echo "  • Backend:            $(docker ps --format "{{.Names}}\t{{.Status}}" | grep rag-backend || echo "Not running")"
    echo "  • PostgreSQL:         $(docker ps --format "{{.Names}}\t{{.Status}}" | grep postgres || echo "Not running")"
    echo "  • Neo4j:              $(docker ps --format "{{.Names}}\t{{.Status}}" | grep neo4j || echo "Not running")"
    echo "  • Qdrant:             $(docker ps --format "{{.Names}}\t{{.Status}}" | grep qdrant || echo "Not running")"
    echo "  • Redis:              $(docker ps --format "{{.Names}}\t{{.Status}}" | grep redis || echo "Not running")"
    echo ""
    echo -e "${GREEN}🌐 Backend Access:${NC}"
    echo "  • API Server:         http://localhost:8000"
    echo "  • API Documentation:  http://localhost:8000/docs"
    echo "  • Health Check:       http://localhost:8000/health"
    echo ""
    echo -e "${GREEN}📝 Management:${NC}"
    echo "  • View logs:          docker-compose logs -f backend"
    echo "  • Stop backend:       docker-compose stop backend"
    echo "  • Restart backend:    docker-compose restart backend"
    echo "  • View status:        docker-compose ps backend"
    echo ""
    echo -e "${GREEN}🎯 Next Steps:${NC}"
    echo "  1. Start frontend: cd frontend && npm run dev"
    echo "   2. Open browser: http://localhost:3000"
    echo "   3. Test login and functionality"
    echo ""
}

# Main execution
main() {
    echo "🎯 Start RAG Backend (Simple Mode)"
    echo "==============================="
    echo ""

    check_database
    check_existing_backend
    update_docker_compose
    start_backend
    wait_for_backend
    test_backend
    display_status

    echo -e "${GREEN}✅ Backend started successfully!${NC}"
    echo ""
    echo -e "${YELLOW}💡 Backend is running in Docker Compose service 'rag-backend'${NC}"
}

# Handle script interruption
trap 'print_warning "Backend startup interrupted."; exit 1' INT

# Run main function
main "$@"