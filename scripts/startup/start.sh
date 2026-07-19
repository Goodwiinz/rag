#!/bin/bash

# Multimodal Enterprise RAG System Startup Script
# Supports different configurations: development, azure, cloud

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
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
    echo -e "${BLUE}[RAG SYSTEM]${NC} $1"
}

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker first."
        exit 1
    fi
}

# Function to check if .env file exists
check_env_file() {
    local env_file="$1"
    if [ ! -f "$env_file" ]; then
        print_error "Environment file $env_file not found!"
        print_warning "Please create $env_file with your configuration."
        print_status "You can copy from .env.example or .env.azure"
        exit 1
    fi
}

# Function to validate Azure OpenAI configuration
validate_azure_config() {
    local env_file="$1"

    print_status "Validating Azure OpenAI configuration..."

    # Check for required Azure OpenAI variables
    local required_vars=("AZURE_OPENAI_API_KEY" "AZURE_OPENAI_ENDPOINT" "AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME")
    local missing_vars=()

    for var in "${required_vars[@]}"; do
        if ! grep -q "^${var}=" "$env_file" || grep -q "^${var}=$" "$env_file"; then
            missing_vars+=("$var")
        fi
    done

    if [ ${#missing_vars[@]} -gt 0 ]; then
        print_error "Missing required Azure OpenAI configuration:"
        for var in "${missing_vars[@]}"; do
            echo "  - $var"
        done
        print_warning "Please update your $env_file file with the missing values."
        exit 1
    fi

    print_status "Azure OpenAI configuration validated!"
}

# Function to validate Qdrant configuration
validate_qdrant_config() {
    local env_file="$1"

    if grep -q "^QDRANT_URL=https://.*qdrant.io" "$env_file"; then
        print_status "Using Qdrant Cloud configuration"

        if ! grep -q "^QDRANT_API_KEY=" "$env_file" || grep -q "^QDRANT_API_KEY=$" "$env_file"; then
            print_error "QDRANT_API_KEY is required for Qdrant Cloud"
            exit 1
        fi
    else
        print_status "Using local Qdrant configuration"
    fi
}

# Function to start services
start_services() {
    local compose_file="$1"
    local env_file="$2"

    print_header "Starting Multimodal RAG System..."
    print_status "Using Docker Compose file: $compose_file"
    print_status "Using environment file: $env_file"

    # Load environment variables
    set -a
    source "$env_file"
    set +a

    # Start services
    print_status "Starting all services..."
    docker-compose -f "$compose_file" --env-file "$env_file" up -d

    # Wait for services to be ready
    print_status "Waiting for services to be ready..."
    sleep 20

    # Check service health
    check_service_health
}

# Function to check service health
check_service_health() {
    print_status "Checking service health..."

    local services=("postgres" "redis" "neo4j" "backend")
    local unhealthy_services=()

    for service in "${services[@]}"; do
        local health=$(docker-compose ps "$service" | grep -q "healthy" && echo "healthy" || echo "unhealthy")
        if [ "$health" = "unhealthy" ]; then
            unhealthy_services+=("$service")
        fi
    done

    if [ ${#unhealthy_services[@]} -gt 0 ]; then
        print_warning "Some services may not be fully healthy yet:"
        for service in "${unhealthy_services[@]}"; do
            echo "  - $service"
        done
        print_status "Services are still starting up. Please wait a moment and check manually."
    else
        print_status "All services are healthy!"
    fi
}

# Function to show service URLs
show_service_urls() {
    print_header "Service URLs"
    echo "🌐 Frontend: http://localhost:3000"
    echo "🔧 Backend API: http://localhost:8000"
    echo "📊 API Documentation: http://localhost:8000/docs"
    echo "🗄️  Neo4j Browser: http://localhost:7474"
    echo "📡 Redis Commander: http://localhost:8081"
    echo "🌸 Flower (Celery Monitor): http://localhost:5555"
    echo ""
    print_status "Use 'docker-compose logs -f [service-name]' to view logs"
}

# Function to stop services
stop_services() {
    local compose_file="$1"

    print_header "Stopping Multimodal RAG System..."
    docker-compose -f "$compose_file" down
    print_status "All services stopped."
}

# Function to show logs
show_logs() {
    local compose_file="$1"
    local service="$2"

    if [ -z "$service" ]; then
        print_header "Showing logs for all services..."
        docker-compose -f "$compose_file" logs -f
    else
        print_header "Showing logs for $service..."
        docker-compose -f "$compose_file" logs -f "$service"
    fi
}

# Main script logic
case "${1:-help}" in
    "dev"|"development")
        print_header "Starting in Development Mode"
        check_docker
        check_env_file ".env"
        validate_qdrant_config ".env"
        start_services "docker-compose.development.yml" ".env"
        show_service_urls
        ;;

    "azure")
        print_header "Starting in Azure OpenAI Mode"
        check_docker
        check_env_file ".env"
        validate_azure_config ".env"
        validate_qdrant_config ".env"
        start_services "docker-compose.azure.yml" ".env"
        show_service_urls
        ;;

    "cloud")
        print_header "Starting in Cloud Mode (Qdrant Cloud + Azure OpenAI)"
        check_docker
        check_env_file ".env"
        validate_azure_config ".env"
        validate_qdrant_config ".env"
        start_services "docker-compose.azure.yml" ".env"
        show_service_urls
        ;;

    "stop")
        print_header "Stopping Services"
        if [ -f "docker-compose.development.yml" ]; then
            stop_services "docker-compose.development.yml"
        fi
        if [ -f "docker-compose.azure.yml" ]; then
            stop_services "docker-compose.azure.yml"
        fi
        ;;

    "logs")
        compose_file="docker-compose.development.yml"
        if [ -f "docker-compose.azure.yml" ] && [ -f ".env" ] && grep -q "AZURE_OPENAI_API_KEY=" ".env"; then
            compose_file="docker-compose.azure.yml"
        fi
        show_logs "$compose_file" "$2"
        ;;

    "status")
        print_header "Service Status"
        docker-compose ps
        ;;

    "test-azure")
        print_header "Testing Azure OpenAI Integration"
        check_env_file ".env"
        validate_azure_config ".env"
        cd backend
        python test_azure_openai.py
        ;;

    "help"|*)
        echo "Multimodal Enterprise RAG System Startup Script"
        echo ""
        echo "Usage: $0 [COMMAND]"
        echo ""
        echo "Commands:"
        echo "  dev, development    Start with local services and optional Azure OpenAI"
        echo "  azure              Start with Azure OpenAI and local databases"
        echo "  cloud              Start with Azure OpenAI and Qdrant Cloud"
        echo "  stop               Stop all running services"
        echo "  logs [service]     Show logs for all services or specific service"
        echo "  status             Show status of all services"
        echo "  test-azure         Test Azure OpenAI integration"
        echo "  help               Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0 dev             # Start development environment"
        echo "  $0 azure           # Start with Azure OpenAI"
        echo "  $0 logs backend    # Show backend logs"
        echo "  $0 test-azure      # Test Azure OpenAI configuration"
        echo ""
        echo "Configuration Files:"
        echo "  .env.example       # Example configuration"
        echo "  .env.azure         # Azure OpenAI configuration template"
        echo "  .env               # Your actual configuration (create from templates)"
        ;;
esac