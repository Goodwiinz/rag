#!/bin/bash

# Start Database Services for RAG System

set -e

echo "🗄️ Starting Database Services..."

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

# Check existing containers
check_existing_containers() {
    print_header "Checking existing containers..."

    local running_containers=$(docker ps --format "table {{.Names}}\t{{.Status}}" | grep rag-)
    if [ -n "$running_containers" ]; then
        echo "$running_containers"
        print_warning "Some RAG containers are already running"
        read -p "Stop existing containers? (y/N): " stop_containers
        if [[ $stop_containers =~ ^[Yy]$ ]]; then
            docker-compose down
            print_status "Existing containers stopped ✓"
        fi
    else
        print_status "No existing RAG containers found ✓"
    fi
}

# Clean up any issues
cleanup_issues() {
    print_header "Cleaning up potential issues..."

    # Remove any orphaned containers
    if docker ps -a --filter "name=rag-" -q | grep -q .; then
        print_status "Removing orphaned containers..."
        docker rm $(docker ps -a --filter "name=rag-" -q) 2>/dev/null || true
    fi

    # Remove any conflicting networks
    if docker network ls | grep -q rag_rag-network; then
        print_status "Removing existing network..."
        docker network rm rag_rag-network 2>/dev/null || true
    fi

    print_status "Cleanup completed ✓"
}

# Start database services
start_databases() {
    print_header "Starting database services..."

    # Start core databases
    print_status "Starting PostgreSQL..."
    docker-compose up -d postgres

    print_status "Starting Neo4j..."
    docker-compose up -d neo4j

    print_status "Starting Qdrant..."
    docker-compose up -d qdrant

    print_status "Starting Redis..."
    docker-compose up -d redis

    print_status "All database services started ✓"
}

# Wait for databases to be ready
wait_for_databases() {
    print_header "Waiting for databases to be ready..."

    # Wait for PostgreSQL
    print_status "Waiting for PostgreSQL..."
    local postgres_ready=false
    for i in {1..60}; do
        if docker exec rag-postgres pg_isready -U raguser &>/dev/null; then
            print_status "PostgreSQL is ready ✓"
            postgres_ready=true
            break
        fi
        echo -n "."
        sleep 2
    done

    if [ "$postgres_ready" = false ]; then
        print_error "PostgreSQL failed to start"
        docker logs rag-postgres | tail -10
        return 1
    fi

    # Wait for Neo4j
    print_status "Waiting for Neo4j..."
    local neo4j_ready=false
    for i in {1..60}; do
        if curl -f http://localhost:7474 &>/dev/null; then
            print_status "Neo4j is ready ✓"
            neo4j_ready=true
            break
        fi
        echo -n "."
        sleep 2
    done

    if [ "$neo4j_ready" = false ]; then
        print_warning "Neo4j might not be ready yet"
        docker logs rag-neo4j | tail -5
    fi

    # Wait for Qdrant
    print_status "Waiting for Qdrant..."
    local qdrant_ready=false
    for i in {1..30}; do
        if curl -f http://localhost:6333/collections &>/dev/null; then
            print_status "Qdrant is ready ✓"
            qdrant_ready=true
            break
        fi
        echo -n "."
        sleep 2
    done

    if [ "$qdrant_ready" = false ]; then
        print_warning "Qdrant might not be ready yet"
        docker logs rag-qdrant | tail -5
    fi

    # Wait for Redis
    if docker exec rag-redis redis-cli ping &>/dev/null; then
        print_status "Redis is ready ✓"
    else
        print_warning "Redis might not be ready yet"
        docker logs rag-redis | tail -5
    fi

    echo ""
}

# Test database connections
test_connections() {
    print_header "Testing database connections..."

    # Test PostgreSQL
    if docker exec rag-postgres psql -U raguser -d ragdb -c "SELECT 1;" &>/dev/null; then
        print_status "PostgreSQL connection test passed ✓"
    else
        print_error "PostgreSQL connection test failed"
        print_status "Trying to create database..."
        docker exec rag-postgres psql -U raguser -c "CREATE DATABASE ragdb;" 2>/dev/null || true
    fi

    # Test Redis
    if docker exec rag-redis redis-cli ping &>/dev/null; then
        print_status "Redis connection test passed ✓"
    else
        print_warning "Redis connection test failed"
    fi

    # Test Qdrant
    if curl -f http://localhost:6333/collections &>/dev/null; then
        print_status "Qdrant connection test passed ✓"
    else
        print_warning "Qdrant connection test failed"
    fi
}

# Display status
display_status() {
    print_header "Database Services Started Successfully!"
    echo ""
    echo -e "${GREEN}📊 Services Status:${NC}"
    echo "  • PostgreSQL:          $(docker ps --format "{{.Names}}" | grep postgres | head -1 || echo "Not running")"
    echo "  • Neo4j:              $(docker ps --format "{{.Names}}" | grep neo4j | head -1 || echo "Not running")"
    echo "  • Qdrant:             $(docker ps --format "{{.Names}}" | grep qdrant | head -1 || echo "Not running")"
    echo "  • Redis:              $(docker ps --format "{{.Names}}" | grep redis | head -1 || echo "Not running")"
    echo ""
    echo -e "${GREEN}🌐 Access URLs:${NC}"
    echo "  • PostgreSQL:          localhost:5432"
    echo "  • Neo4j Browser:       http://localhost:7474"
    echo "  • Neo4j Bolt:         bolt://localhost:7687"
    echo "  • Qdrant Dashboard:    http://localhost:6333"
    echo "  • Redis CLI:          docker exec -it rag-redis redis-cli"
    echo ""
    echo -e "${GREEN}📝 Next Steps:${NC}"
    echo "  1. Run the connection fix: ./fix_postgresql_connection.sh"
    echo "  2. Start frontend: cd frontend && npm run dev"
    echo "  3. Open http://localhost:3000"
    echo ""
    echo -e "${GREEN}🔧 Management Commands:${NC}"
    echo "  • View logs:          docker-compose logs -f postgres"
    echo "  • Stop databases:     docker-compose down"
    echo "  • Restart service:    docker-compose restart [service]"
    echo ""
}

# Main execution
main() {
    echo "🎯 Start Database Services"
    echo "========================="
    echo ""

    check_docker
    check_existing_containers
    cleanup_issues
    start_databases
    wait_for_databases
    test_connections
    display_status

    echo -e "${GREEN}✅ All database services started successfully!${NC}"
    echo ""
    echo -e "${YELLOW}💡 You can now run: ./fix_postgresql_connection.sh${NC}"
}

# Handle script interruption
trap 'print_warning "Database startup interrupted."; exit 1' INT

# Run main function
main "$@"