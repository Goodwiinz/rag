#!/bin/bash

# Deployment script for the corrected Knowledge Graph Services Architecture
# This script deploys the three microservices that resolve the architectural violation

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Configuration
COMPOSE_FILE="docker-compose.graph-services-corrected.yml"
ENV_FILE=".env"
PROJECT_NAME="rag-graph"

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."

    # Check Docker
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed or not in PATH"
    fi

    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose is not installed or not in PATH"
    fi

    # Check if compose file exists
    if [ ! -f "$COMPOSE_FILE" ]; then
        error "Docker Compose file not found: $COMPOSE_FILE"
    fi

    success "Prerequisites check passed"
}

# Setup environment
setup_environment() {
    log "Setting up environment..."

    # Create .env file if it doesn't exist
    if [ ! -f "$ENV_FILE" ]; then
        log "Creating .env file with default values..."
        cat > "$ENV_FILE" << EOF
# Environment Variables for Graph Services
JWT_SECRET_KEY=your-super-secret-jwt-key-change-in-production-$(date +%s)
DEBUG=false
LOG_LEVEL=INFO

# Flower credentials (optional)
FLOWER_USER=admin
FLOWER_PASSWORD=admin-$(date +%s)

# Additional configuration
NEO4J_PASSWORD=ragpassword2024
POSTGRES_PASSWORD=rag_password2024
EOF
        warning "Created .env file with default values. Please review and update as needed."
    fi

    # Create necessary directories
    mkdir -p logs
    mkdir -p nginx
    mkdir -p monitoring
    mkdir -p database

    success "Environment setup completed"
}

# Build and deploy services
deploy_services() {
    log "Building and deploying graph services..."

    # Stop existing services
    log "Stopping existing services..."
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" down --remove-orphans || true

    # Pull latest images
    log "Pulling latest base images..."
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" pull

    # Build custom images
    log "Building custom service images..."
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" build --no-cache

    # Start services
    log "Starting services..."
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" up -d

    success "Services deployed successfully"
}

# Wait for services to be healthy
wait_for_health() {
    log "Waiting for services to become healthy..."

    local services=("knowledge-graph-service" "graph-analytics-service" "graph-visualization-service")
    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        log "Health check attempt $attempt/$max_attempts..."

        all_healthy=true

        for service in "${services[@]}"; do
            if ! docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" ps "$service" | grep -q "healthy\|Up"; then
                log "Service $service is not healthy yet..."
                all_healthy=false
            fi
        done

        if [ "$all_healthy" = true ]; then
            success "All services are healthy!"
            return 0
        fi

        sleep 10
        ((attempt++))
    done

    error "Services did not become healthy within $max_attempts attempts"
}

# Run health checks
run_health_checks() {
    log "Running comprehensive health checks..."

    # Check Knowledge Graph Service
    log "Checking Knowledge Graph Service (Port 8003)..."
    if curl -f http://localhost:8003/health &> /dev/null; then
        success "Knowledge Graph Service is healthy"
    else
        error "Knowledge Graph Service health check failed"
    fi

    # Check Graph Analytics Service
    log "Checking Graph Analytics Service (Port 8009)..."
    if curl -f http://localhost:8009/health &> /dev/null; then
        success "Graph Analytics Service is healthy"
    else
        error "Graph Analytics Service health check failed"
    fi

    # Check Graph Visualization Service
    log "Checking Graph Visualization Service (Port 8010)..."
    if curl -f http://localhost:8010/health &> /dev/null; then
        success "Graph Visualization Service is healthy"
    else
        error "Graph Visualization Service health check failed"
    fi

    # Check database connectivity
    log "Checking Neo4j connectivity..."
    if docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T neo4j-graph cypher-shell -u neo4j -p ragpassword2024 "RETURN 1" &> /dev/null; then
        success "Neo4j is accessible"
    else
        error "Neo4j connectivity check failed"
    fi

    # Check PostgreSQL connectivity
    log "Checking PostgreSQL connectivity..."
    if docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T postgres-graph pg_isready -U rag_user -d rag_graph &> /dev/null; then
        success "PostgreSQL is accessible"
    else
        error "PostgreSQL connectivity check failed"
    fi

    # Check Redis connectivity
    log "Checking Redis connectivity..."
    if docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T redis-graph redis-cli ping &> /dev/null; then
        success "Redis is accessible"
    else
        error "Redis connectivity check failed"
    fi

    success "All health checks passed!"
}

# Show deployment information
show_deployment_info() {
    log "Deployment Information:"
    echo ""
    echo "📊 Services deployed:"
    echo "  • Knowledge Graph Service: http://localhost:8003"
    echo "  • Graph Analytics Service: http://localhost:8009"
    echo "  • Graph Visualization Service: http://localhost:8010"
    echo ""
    echo "🗄️  Databases:"
    echo "  • Neo4j: http://localhost:7474 (neo4j/ragpassword2024)"
    echo "  • PostgreSQL: localhost:5433 (rag_user/rag_password2024)"
    echo "  • Redis: localhost:6380"
    echo ""
    echo "📚 API Documentation:"
    echo "  • Knowledge Graph: http://localhost:8003/docs"
    echo "  • Graph Analytics: http://localhost:8009/docs"
    echo "  • Graph Visualization: http://localhost:8010/docs"
    echo ""
    echo "🔧 Management Commands:"
    echo "  • View logs: docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME logs -f [service-name]"
    echo "  • Stop services: docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME down"
    echo "  • Restart service: docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME restart [service-name]"
    echo ""
}

# Show logs
show_logs() {
    local service=$1
    if [ -z "$service" ]; then
        log "Showing logs for all services..."
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" logs -f
    else
        log "Showing logs for $service..."
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" logs -f "$service"
    fi
}

# Cleanup function
cleanup() {
    log "Cleaning up..."
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" down --volumes --remove-orphans
    docker system prune -f
    success "Cleanup completed"
}

# Main function
main() {
    local command=${1:-deploy}

    case "$command" in
        "deploy")
            log "Starting deployment of corrected Knowledge Graph Services Architecture..."
            check_prerequisites
            setup_environment
            deploy_services
            wait_for_health
            run_health_checks
            show_deployment_info
            ;;
        "health")
            run_health_checks
            ;;
        "logs")
            show_logs "$2"
            ;;
        "stop")
            log "Stopping services..."
            docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" down
            success "Services stopped"
            ;;
        "restart")
            log "Restarting services..."
            docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" restart
            wait_for_health
            run_health_checks
            success "Services restarted"
            ;;
        "cleanup")
            cleanup
            ;;
        "status")
            docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" ps
            ;;
        *)
            echo "Usage: $0 {deploy|health|logs|stop|restart|cleanup|status} [service-name]"
            echo ""
            echo "Commands:"
            echo "  deploy    - Deploy all services (default)"
            echo "  health    - Run health checks"
            echo "  logs      - Show logs (all services or specific service)"
            echo "  stop      - Stop all services"
            echo "  restart   - Restart all services"
            echo "  cleanup   - Stop services and remove volumes"
            echo "  status    - Show service status"
            echo ""
            echo "Examples:"
            echo "  $0 deploy                    # Deploy all services"
            echo "  $0 logs knowledge-graph     # Show logs for knowledge graph service"
            echo "  $0 health                    # Run health checks"
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"