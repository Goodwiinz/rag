#!/bin/bash

# Complete System Startup with Monitoring
# This script starts the entire RAG system with monitoring enabled

set -e

echo "🚀 Starting Complete RAG System with Monitoring..."

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

# Function to check if a service is running
check_service() {
    local url=$1
    local service_name=$2

    if curl -f $url &>/dev/null; then
        print_status "$service_name is running ✓"
        return 0
    else
        print_warning "$service_name is not responding"
        return 1
    fi
}

# Function to wait for service
wait_for_service() {
    local url=$1
    local service_name=$2
    local max_attempts=30
    local attempt=1

    print_status "Waiting for $service_name to start..."

    while [ $attempt -le $max_attempts ]; do
        if curl -f $url &>/dev/null; then
            print_status "$service_name is ready ✓"
            return 0
        fi

        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done

    echo ""
    print_error "$service_name failed to start"
    return 1
}

# 1. Start Core Services
start_core_services() {
    print_header "Starting Core RAG Services..."

    # Start databases and core infrastructure
    docker-compose up -d postgres neo4j qdrant redis

    print_status "Core services started ✓"
}

# 2. Initialize Databases
initialize_databases() {
    print_header "Initializing Databases..."

    # Wait for databases to be ready
    wait_for_service http://localhost:7687 "Neo4j"
    wait_for_service http://localhost:6333 "Qdrant"
    wait_for_service http://localhost:5432 "PostgreSQL"

    # Run setup script
    if [ -f setup.sh ]; then
        ./setup.sh
        print_status "Database initialization completed ✓"
    else
        print_warning "Setup script not found, skipping database initialization"
    fi
}

# 3. Start Monitoring Stack
start_monitoring() {
    print_header "Starting Monitoring Stack..."

    if [ -f QUICK_START_MONITORING.sh ]; then
        ./QUICK_START_MONITORING.sh
    else
        print_warning "Monitoring setup script not found, starting manually..."

        # Start monitoring with Docker Compose
        if [ -f monitoring/docker-compose.monitoring.yml ]; then
            cd monitoring
            docker-compose -f docker-compose.monitoring.yml up -d
            cd ..
        fi
    fi
}

# 4. Start Backend Application
start_backend() {
    print_header "Starting Backend Application..."

    cd backend

    # Check if virtual environment exists
    if [ ! -d "venv" ]; then
        print_status "Creating virtual environment..."
        python -m venv venv
    fi

    # Activate virtual environment
    source venv/bin/activate

    # Install dependencies
    pip install -r requirements.txt

    # Start backend in background
    nohup uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload > ../logs/backend.log 2>&1 &
    BACKEND_PID=$!
    echo $BACKEND_PID > ../backend.pid

    cd ..

    print_status "Backend started (PID: $BACKEND_PID) ✓"
}

# 5. Start Frontend Application
start_frontend() {
    print_header "Starting Frontend Application..."

    cd frontend

    # Install dependencies if needed
    if [ ! -d "node_modules" ]; then
        npm install
    fi

    # Start frontend in background
    nohup npm run dev > ../logs/frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > ../frontend.pid

    cd ..

    print_status "Frontend started (PID: $FRONTEND_PID) ✓"
}

# 6. Verify All Services
verify_services() {
    print_header "Verifying All Services..."

    # Check core services
    check_service http://localhost:7687 "Neo4j" || true
    check_service http://localhost:6333 "Qdrant" || true
    check_service http://localhost:6379 "Redis" || true

    # Check monitoring
    check_service http://localhost:9090 "Prometheus" || true
    check_service http://localhost:3001 "Grafana" || true
    check_service http://localhost:16686 "Jaeger" || true
    check_service http://localhost:5601 "Kibana" || true

    # Check applications
    check_service http://localhost:8000/health "Backend API" || true
    check_service http://localhost:3000 "Frontend" || true
}

# 7. Display Information
display_info() {
    print_header "System Status and Access Information"
    echo ""
    echo -e "${GREEN}🌐 Application Services:${NC}"
    echo "  • Frontend Application:   http://localhost:3000"
    echo "  • Backend API:          http://localhost:8000"
    echo "  • API Documentation:     http://localhost:8000/docs"
    echo ""
    echo -e "${GREEN}📊 Monitoring Services:${NC}"
    echo "  • Grafana Dashboards:    http://localhost:3001 (admin/admin)"
    echo "  • Prometheus:           http://localhost:9090"
    echo "  • Jaeger Tracing:       http://localhost:16686"
    echo "  • Kibana Logs:          http://localhost:5601"
    echo "  • AlertManager:         http://localhost:9093"
    echo ""
    echo -e "${GREEN}🗄️  Database Services:${NC}"
    echo "  • Neo4j Browser:        http://localhost:7474"
    echo "  • Qdrant Console:       http://localhost:6333/dashboard"
    echo ""
    echo -e "${GREEN}🔧 Management Commands:${NC}"
    echo "  • View backend logs:     tail -f logs/backend.log"
    echo "  • View frontend logs:    tail -f logs/frontend.log"
    echo "  • Stop all services:     ./STOP_ALL_SERVICES.sh"
    echo "  • Restart backend:       kill \$(cat backend.pid) && ./START_MONITORED_SYSTEM.sh"
    echo ""
    echo -e "${GREEN}📈 Quick Monitoring Checks:${NC}"
    echo "  • Check system metrics:  curl http://localhost:8000/metrics"
    echo "  • Check health status:   curl http://localhost:8000/health"
    echo "  • View active traces:    curl http://localhost:16686/api/traces"
    echo ""
}

# Create logs directory
mkdir -p logs

# Main execution
main() {
    echo "🎯 Complete RAG System Startup with Monitoring"
    echo "=========================================="
    echo ""

    # Check for existing processes
    if [ -f backend.pid ] && kill -0 $(cat backend.pid) 2>/dev/null; then
        print_warning "Backend is already running. Stop it first or use ./STOP_ALL_SERVICES.sh"
    fi

    if [ -f frontend.pid ] && kill -0 $(cat frontend.pid) 2>/dev/null; then
        print_warning "Frontend is already running. Stop it first or use ./STOP_ALL_SERVICES.sh"
    fi

    start_core_services
    initialize_databases
    start_monitoring
    start_backend
    start_frontend

    # Wait for applications to start
    sleep 10

    verify_services
    display_info

    echo -e "${GREEN}✅ Complete RAG System with Monitoring is now running!${NC}"
    echo ""
    echo -e "${YELLOW}💡 Pro Tip: Open Grafana (http://localhost:3001) to see real-time metrics and dashboards${NC}"
}

# Handle script interruption
trap 'print_warning "Startup interrupted. Some services may be running."; exit 1' INT

# Run main function
main "$@"