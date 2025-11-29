#!/bin/bash

# Start RAG Backend in Docker

set -e

echo "🐳 Starting RAG Backend in Docker..."

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

# Check Docker status
check_docker() {
    if ! docker info &> /dev/null; then
        print_error "Docker is not running. Please start Docker first."
        exit 1
    fi
    print_status "Docker is running ✓"
}

# Check if backend container is already running
check_existing_backend() {
    if docker ps --format "{{.Names}}" | grep -q "rag-backend"; then
        print_warning "Backend container is already running"
        print_status "Stopping existing backend..."
        docker stop rag-backend || true
        docker rm rag-backend || true
    fi
}

# Build backend image if needed
build_backend() {
    print_header "Building backend Docker image..."

    if docker images | grep -q "rag-system/backend"; then
        print_status "Backend image already exists ✓"
    else
        print_status "Building backend image..."
        docker build -t rag-system/backend -f backend/Dockerfile ./backend
        print_status "Backend image built ✓"
    fi
}

# Start backend container
start_backend() {
    print_header "Starting backend container..."

    # Create network if it doesn't exist
    if ! docker network ls | grep -q "rag_rag-network"; then
        docker network create rag_rag-network
        print_status "Created Docker network ✓"
    fi

    # Start backend container
    docker run -d \
        --name rag-backend \
        --network rag_rag-network \
        -p 8000:8000 \
        -e DATABASE_URL=postgresql://raguser:rag_password@postgres:5432/ragdb \
        -e NEO4J_URI=bolt://neo4j:7687 \
        -e NEO4J_USER=neo4j \
        -e NEO4J_PASSWORD=neo4j_password \
        -e QDRANT_URL=http://qdrant:6333 \
        -e REDIS_URL=redis://redis:6379/0 \
        -e ENVIRONMENT=development \
        -e LOG_LEVEL=info \
        -e SECRET_KEY=dev-secret-key-change-in-production \
        -e CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000 \
        -v $(pwd)/logs:/app/logs \
        rag-system/backend

    print_status "Backend container started ✓"
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
        docker logs rag-backend | tail -20
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

    # Test database connection through backend
    if curl -f http://localhost:8000/api/v1/health/database &>/dev/null; then
        print_status "Database health check passed ✓"
    else
        print_warning "Database health check endpoint not available (normal)"
    fi
}

# Display status
display_status() {
    print_header "Backend Started Successfully in Docker!"
    echo ""
    echo -e "${GREEN}🐳 Container Status:${NC}"
    echo "  • Backend Container:   $(docker ps --format "{{.Names}}\t{{.Status}}" | grep rag-backend || echo "Not running")"
    echo ""
    echo -e "${GREEN}🌐 Backend Access:${NC}"
    echo "  • API Server:         http://localhost:8000"
    echo "  • API Documentation:  http://localhost:8000/docs"
    echo "  • Health Check:       http://localhost:8000/health"
    echo ""
    echo -e "${GREEN}📝 Management:${NC}"
    echo "  • View logs:          docker logs -f rag-backend"
    echo "  • Stop backend:       docker stop rag-backend"
    echo "  • Restart backend:    docker restart rag-backend"
    echo "  • Remove container:   docker rm rag-backend"
    echo ""
    echo -e "${GREEN}🎯 Next Steps:${NC}"
    echo "  1. Start frontend: cd frontend && npm run dev"
    echo "  2. Open browser: http://localhost:3000"
    echo "  3. Test login and functionality"
    echo ""
}

# Main execution
main() {
    echo "🎯 Start RAG Backend in Docker"
    echo "============================="
    echo ""

    check_docker
    check_existing_backend
    build_backend
    start_backend
    wait_for_backend
    test_backend
    display_status

    echo -e "${GREEN}✅ Backend started successfully in Docker!${NC}"
    echo ""
    echo -e "${YELLOW}💡 Backend is running in Docker container 'rag-backend'${NC}"
}

# Handle script interruption
trap 'print_warning "Backend startup interrupted."; exit 1' INT

# Run main function
main "$@"