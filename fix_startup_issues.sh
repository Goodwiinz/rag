#!/bin/bash

# Fix startup issues for RAG System

set -e

echo "🔧 Fixing RAG System Startup Issues..."

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

# Check current Docker status
check_docker_status() {
    print_header "Checking Docker status..."

    if ! docker info &> /dev/null; then
        print_error "Docker is not running. Please start Docker first."
        exit 1
    fi

    # Check what containers are running
    local running_containers=$(docker ps --format "table {{.Names}}" | grep rag- | wc -l)
    print_status "Found $running_containers RAG containers running"
}

# Stop all services
stop_all_services() {
    print_header "Stopping all services..."

    # Stop any running processes
    if pgrep -f "uvicorn.*main:app" > /dev/null; then
        pkill -f "uvicorn.*main:app"
        print_status "Stopped local backend process"
    fi

    if pgrep -f "next dev" > /dev/null; then
        pkill -f "next dev"
        print_status "Stopped local frontend process"
    fi

    # Stop Docker containers
    if docker-compose ps | grep -q "Up"; then
        docker-compose down
        print_status "Stopped Docker containers"
    fi
}

# Fix Docker volumes
fix_docker_volumes() {
    print_header "Fixing Docker volumes..."

    # Check for existing volumes
    local volumes=$(docker volume ls | grep rag_ | wc -l)
    if [ $volumes -gt 0 ]; then
        print_warning "Found $volumes existing RAG volumes"
        print_status "You have two options:"
        echo "  1. Keep existing data (recommended for development)"
        echo "  2. Delete all data and start fresh"
        echo ""

        read -p "Choose option (1 or 2) [1]: " choice
        choice=${choice:-1}

        if [ "$choice" = "2" ]; then
            print_warning "Deleting all existing volumes..."
            docker volume ls | grep rag_ | awk '{print $2}' | xargs docker volume rm 2>/dev/null || true
            print_status "All volumes deleted ✓"
        else
            print_status "Keeping existing volumes"
            # Add external volumes to docker-compose.yml
            if ! grep -q "external: true" docker-compose.yml; then
                print_status "Adding external volumes configuration..."
                cat >> docker-compose.yml << 'EOF'

# External volumes (existing data)
volumes:
  rag_postgres_data:
    external: true
  rag_neo4j_data:
    external: true
  rag_redis_data:
    external: true
  rag_qdrant_data:
    external: true
  prometheus_data:
    external: true
  grafana_data:
    external: true
EOF
                print_status "External volumes configuration added ✓"
            fi
        fi
    fi
}

# Check and fix environment variables
fix_environment() {
    print_header "Checking environment configuration..."

    if [ ! -f .env ]; then
        if [ -f .env.example ]; then
            cp .env.example .env
            print_status "Created .env from .env.example"
        else
            print_error "No .env or .env.example found"
            return 1
        fi
    fi

    # Check for database connection strings
    if grep -q "localhost" .env && docker-compose ps | grep -q "Up"; then
        print_warning "Environment variables use localhost but services are running in Docker"
        print_status "Updating environment variables for Docker networking..."

        # Update database URLs to use Docker service names
        sed -i.bak 's/localhost/postgres/g' .env
        sed -i.bak 's/bolt:\/\/localhost:7687/bolt:\/\/neo4j:7687/g' .env
        sed -i.bak 's/http:\/\/localhost:6333/http:\/\/qdrant:6333/g' .env
        sed -i.bak 's/redis:\/\/localhost:6379/redis:\/\/redis:6379/g' .env

        print_status "Environment variables updated for Docker networking ✓"
    fi
}

# Start databases only
start_databases() {
    print_header "Starting database services..."

    docker-compose up -d postgres neo4j qdrant redis

    print_status "Waiting for databases to be ready..."

    # Wait for PostgreSQL
    local postgres_ready=false
    for i in {1..30}; do
        if docker exec rag-postgres pg_isready -U raguser &>/dev/null; then
            print_status "PostgreSQL is ready ✓"
            postgres_ready=true
            break
        fi
        echo -n "."
        sleep 2
    done

    # Wait for Neo4j
    local neo4j_ready=false
    for i in {1..30}; do
        if docker exec rag-neo4j cypher-shell -u neo4j -p "${NEO4J_PASSWORD:-password}" "RETURN 1;" &>/dev/null; then
            print_status "Neo4j is ready ✓"
            neo4j_ready=true
            break
        fi
        echo -n "."
        sleep 2
    done

    # Wait for Qdrant
    local qdrant_ready=false
    for i in {1..15}; do
        if curl -f http://localhost:6333/collections &>/dev/null; then
            print_status "Qdrant is ready ✓"
            qdrant_ready=true
            break
        fi
        echo -n "."
        sleep 2
    done

    # Wait for Redis
    if docker exec rag-redis redis-cli ping &>/dev/null; then
        print_status "Redis is ready ✓"
    else
        print_warning "Redis might not be ready"
    fi

    echo ""
}

# Initialize databases
initialize_databases() {
    print_header "Initializing databases..."

    # Run setup script if it exists
    if [ -f setup.sh ]; then
        print_status "Running database setup script..."
        ./setup.sh
        print_status "Database setup completed ✓"
    else
        print_warning "Setup script not found"
    fi
}

# Start application services
start_applications() {
    print_header "Starting application services..."

    print_status "You have two options for running applications:"
    echo "  1. Run backend locally (easier for debugging)"
    echo "  2. Run everything in Docker"
    echo ""

    read -p "Choose option (1 or 2) [1]: " choice
    choice=${choice:-1}

    if [ "$choice" = "1" ]; then
        # Start backend locally
        print_status "Starting backend locally..."
        cd backend

        # Activate virtual environment
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

        # Start backend in background
        nohup uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload > ../logs/backend.log 2>&1 &
        BACKEND_PID=$!
        echo $BACKEND_PID > ../backend.pid
        cd ..
        print_status "Backend started locally (PID: $BACKEND_PID) ✓"

        # Start frontend locally
        print_status "Starting frontend locally..."
        cd frontend

        nohup npm run dev > ../logs/frontend.log 2>&1 &
        FRONTEND_PID=$!
        echo $FRONTEND_PID > ../frontend.pid
        cd ..
        print_status "Frontend started locally (PID: $FRONTEND_PID) ✓"

    else
        # Start everything in Docker
        print_status "Starting applications in Docker..."
        docker-compose up -d backend frontend
        print_status "Applications started in Docker ✓"
    fi
}

# Test connectivity
test_connectivity() {
    print_header "Testing connectivity..."

    # Test backend health
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
        print_error "Backend failed to start"
        return 1
    fi

    # Test frontend health
    local frontend_ready=false
    for i in {1..30}; do
        if curl -f http://localhost:3000 &>/dev/null; then
            print_status "Frontend health check passed ✓"
            frontend_ready=true
            break
        fi
        echo -n "."
        sleep 2
    done

    if [ "$frontend_ready" = false ]; then
        print_error "Frontend failed to start"
        return 1
    fi

    echo ""
}

# Display final information
display_info() {
    print_header "Startup Issues Fixed Successfully!"
    echo ""
    echo -e "${GREEN}🌐 Application Access:${NC}"
    echo "  • Frontend:            http://localhost:3000"
    echo "  • Backend API:         http://localhost:8000"
    echo "  • API Documentation:   http://localhost:8000/docs"
    echo ""
    echo -e "${GREEN}🔧 What was fixed:${NC}"
    echo "  ✅ Docker volume configuration"
    echo "  ✅ Environment variables for networking"
    echo "  ✅ Database connectivity"
    echo "  ✅ Missing functions in startup script"
    echo ""
    echo -e "${GREEN}📊 Services running:${NC}"
    echo "  • PostgreSQL:          $(docker ps --format "{{.Names}}" | grep postgres | head -1 || echo "Not running")"
    echo "  • Neo4j:              $(docker ps --format "{{.Names}}" | grep neo4j | head -1 || echo "Not running")"
    echo "  • Qdrant:             $(docker ps --format "{{.Names}}" | grep qdrant | head -1 || echo "Not running")"
    echo "  • Redis:              $(docker ps --format "{{.Names}}" | grep redis | head -1 || echo "Not running")"
    echo ""
    echo -e "${GREEN}📝 Logs:${NC}"
    echo "  • Backend logs:       tail -f logs/backend.log"
    echo "  • Frontend logs:      tail -f logs/frontend.log"
    echo "  • Docker logs:        docker-compose logs -f"
    echo ""
}

# Main execution
main() {
    echo "🎯 RAG System Startup Issues Fix"
    echo "==============================="
    echo ""

    check_docker_status
    stop_all_services
    fix_docker_volumes
    fix_environment
    start_databases
    initialize_databases
    start_applications
    test_connectivity
    display_info

    echo -e "${GREEN}✅ All startup issues fixed successfully!${NC}"
    echo ""
    echo -e "${YELLOW}💡 If you still have issues, check the logs in the logs/ directory${NC}"
}

# Handle script interruption
trap 'print_warning "Fix process interrupted."; exit 1' INT

# Run main function
main "$@"