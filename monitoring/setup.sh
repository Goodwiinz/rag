#!/bin/bash

# Knowledge Graph Analytics - Monitoring Stack Setup Script
# This script sets up the complete observability and monitoring stack

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
MONITORING_DIR="$SCRIPT_DIR"
COMPOSE_FILE="$MONITORING_DIR/docker-compose.monitoring.yml"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if Docker is installed and running
check_docker() {
    print_status "Checking Docker installation..."

    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        echo "Visit: https://docs.docker.com/get-docker/"
        exit 1
    fi

    if ! docker info &> /dev/null; then
        print_error "Docker daemon is not running. Please start Docker."
        exit 1
    fi

    print_success "Docker is installed and running"
}

# Function to check if Docker Compose is installed
check_docker_compose() {
    print_status "Checking Docker Compose installation..."

    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi

    print_success "Docker Compose is installed"
}

# Function to create necessary directories
create_directories() {
    print_status "Creating necessary directories..."

    directories=(
        "$MONITORING_DIR/grafana/provisioning/datasources"
        "$MONITORING_DIR/grafana/provisioning/dashboards"
        "$MONITORING_DIR/grafana/dashboards"
        "$MONITORING_DIR/prometheus-rules"
        "$MONITORING_DIR/data/grafana"
        "$MONITORING_DIR/data/prometheus"
        "$MONITORING_DIR/data/loki"
        "$MONITORING_DIR/data/redis"
        "$PROJECT_ROOT/logs/knowledge-graph/api"
        "$PROJECT_ROOT/logs/knowledge-graph/search"
        "$PROJECT_ROOT/logs/knowledge-graph/graph"
        "$PROJECT_ROOT/logs/knowledge-graph/ml"
        "$PROJECT_ROOT/logs/knowledge-graph/database"
        "$PROJECT_ROOT/logs/knowledge-graph/cache"
        "$PROJECT_ROOT/logs/knowledge-graph/security"
        "$PROJECT_ROOT/logs/knowledge-graph/performance"
    )

    for dir in "${directories[@]}"; do
        mkdir -p "$dir"
        print_status "Created directory: $dir"
    done

    print_success "All directories created"
}

# Function to create environment file
create_env_file() {
    local env_file="$MONITORING_DIR/.env"

    if [[ -f "$env_file" ]]; then
        print_warning ".env file already exists. Skipping creation."
        return
    fi

    print_status "Creating .env file with default configuration..."

    cat > "$env_file" << 'EOF'
# Environment Configuration
ENVIRONMENT=development
SERVICE_NAME=knowledge-graph-analytics
VERSION=1.0.0
TZ=UTC

# Grafana Configuration
GRAFANA_ADMIN_PASSWORD=admin123
GRAFANA_SMTP_ENABLED=false

# Prometheus Configuration
PROMETHEUS_RETENTION=15d
PROMETHEUS_WEB_ENABLE_ADMIN_API=true

# Alert Configuration
ALERT_EMAIL_ENABLED=false
SMTP_SERVER=localhost
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
ALERT_FROM_EMAIL=alerts@knowledge-graph.dev
ALERT_TO_EMAILS=admin@company.com

# Slack Configuration
ALERT_SLACK_ENABLED=false
SLACK_WEBHOOK_URL=
SLACK_CHANNEL=#alerts

# PagerDuty Configuration
ALERT_PAGERDUTY_ENABLED=false
PAGERDUTY_INTEGRATION_KEY=
PAGERDUTY_SERVICE_KEY=

# OpenTelemetry Configuration
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_SERVICE_NAME=knowledge-graph-analytics
OTEL_SERVICE_VERSION=1.0.0
OTEL_DEPLOYMENT_ENVIRONMENT=development
EOF

    print_success "Created .env file. Please review and update with your configuration."
}

# Function to check if ports are available
check_ports() {
    print_status "Checking if required ports are available..."

    ports=(3001 9090 16686 3100 4317 4318 6379)
    unavailable_ports=()

    for port in "${ports[@]}"; do
        if lsof -i :"$port" &>/dev/null; then
            unavailable_ports+=("$port")
        fi
    done

    if [[ ${#unavailable_ports[@]} -gt 0 ]]; then
        print_error "The following ports are already in use: ${unavailable_ports[*]}"
        print_error "Please stop the services using these ports or modify the configuration."
        exit 1
    fi

    print_success "All required ports are available"
}

# Function to pull Docker images
pull_images() {
    print_status "Pulling Docker images..."

    images=(
        "otel/opentelemetry-collector-contrib:0.102.0"
        "jaegertracing/all-in-one:1.55"
        "prom/prometheus:v2.53.0"
        "grafana/grafana-oss:11.1.0"
        "grafana/loki:2.9.10"
        "grafana/promtail:2.9.10"
        "redis:7.2.5-alpine"
        "prom/node-exporter:v1.8.1"
        "gcr.io/cadvisor/cadvisor:v0.51.0"
    )

    for image in "${images[@]}"; do
        print_status "Pulling $image..."
        docker pull "$image"
    done

    print_success "All Docker images pulled"
}

# Function to start monitoring services
start_services() {
    print_status "Starting monitoring services..."

    cd "$MONITORING_DIR"

    # Start services
    if command -v docker-compose &> /dev/null; then
        docker-compose -f docker-compose.monitoring.yml up -d
    else
        docker compose -f docker-compose.monitoring.yml up -d
    fi

    print_success "Monitoring services started"
}

# Function to wait for services to be healthy
wait_for_services() {
    print_status "Waiting for services to be healthy..."

    # Wait for Grafana
    print_status "Waiting for Grafana to be ready..."
    for i in {1..30}; do
        if curl -f http://localhost:3001/api/health &>/dev/null; then
            print_success "Grafana is ready"
            break
        fi
        sleep 2
        if [[ $i -eq 30 ]]; then
            print_warning "Grafana is taking longer to start. Please check manually."
        fi
    done

    # Wait for Prometheus
    print_status "Waiting for Prometheus to be ready..."
    for i in {1..30}; do
        if curl -f http://localhost:9090/-/healthy &>/dev/null; then
            print_success "Prometheus is ready"
            break
        fi
        sleep 2
        if [[ $i -eq 30 ]]; then
            print_warning "Prometheus is taking longer to start. Please check manually."
        fi
    done

    # Wait for Jaeger
    print_status "Waiting for Jaeger to be ready..."
    for i in {1..30}; do
        if curl -f http://localhost:16686 &>/dev/null; then
            print_success "Jaeger is ready"
            break
        fi
        sleep 2
        if [[ $i -eq 30 ]]; then
            print_warning "Jaeger is taking longer to start. Please check manually."
        fi
    done
}

# Function to display access information
display_access_info() {
    print_success "Monitoring stack is now running!"
    echo
    echo "Access URLs:"
    echo "  Grafana:       http://localhost:3001 (admin/admin123)"
    echo "  Prometheus:    http://localhost:9090"
    echo "  Jaeger:        http://localhost:16686"
    echo "  Loki:          http://localhost:3100"
    echo
    echo "Service Endpoints:"
    echo "  OpenTelemetry Collector:"
    echo "    gRPC:  localhost:4317"
    echo "    HTTP:  localhost:4318"
    echo "  Redis: localhost:6379"
    echo
    echo "Next Steps:"
    echo "  1. Update .env file with your configuration"
    echo "  2. Configure your applications to send metrics to the OpenTelemetry Collector"
    echo "  3. Import Grafana dashboards from monitoring/grafana/dashboards/"
    echo "  4. Configure alert notifications in .env file"
    echo
    echo "Management Commands:"
    echo "  View logs:     cd $MONITORING_DIR && docker-compose logs -f [service-name]"
    echo "  Stop services: cd $MONITORING_DIR && docker-compose down"
    echo "  Restart:       cd $MONITORING_DIR && docker-compose restart"
    echo
}

# Function to verify setup
verify_setup() {
    print_status "Verifying setup..."

    # Check if all containers are running
    cd "$MONITORING_DIR"

    if command -v docker-compose &> /dev/null; then
        running_containers=$(docker-compose -f docker-compose.monitoring.yml ps -q | wc -l)
    else
        running_containers=$(docker compose -f docker-compose.monitoring.yml ps -q | wc -l)
    fi

    if [[ $running_containers -ge 8 ]]; then
        print_success "All monitoring containers are running"
    else
        print_warning "Only $running_containers containers are running. Expected 8+"
    fi

    # Test basic connectivity
    if curl -f http://localhost:3001/api/health &>/dev/null; then
        print_success "Grafana is accessible"
    else
        print_warning "Grafana is not accessible"
    fi

    if curl -f http://localhost:9090/-/healthy &>/dev/null; then
        print_success "Prometheus is accessible"
    else
        print_warning "Prometheus is not accessible"
    fi
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  -h, --help     Show this help message"
    echo "  -v, --verbose  Enable verbose output"
    echo "  -q, --quiet    Suppress non-error output"
    echo "  --skip-pulls  Skip pulling Docker images"
    echo "  --check-only   Only check prerequisites and exit"
    echo "  --stop         Stop all monitoring services"
    echo "  --restart      Restart all monitoring services"
    echo "  --status       Show status of monitoring services"
    echo "  --logs         Show logs for all services"
    echo
}

# Function to stop services
stop_services() {
    print_status "Stopping monitoring services..."

    cd "$MONITORING_DIR"

    if command -v docker-compose &> /dev/null; then
        docker-compose -f docker-compose.monitoring.yml down
    else
        docker compose -f docker-compose.monitoring.yml down
    fi

    print_success "All monitoring services stopped"
}

# Function to restart services
restart_services() {
    print_status "Restarting monitoring services..."

    cd "$MONITORING_DIR"

    if command -v docker-compose &> /dev/null; then
        docker-compose -f docker-compose.monitoring.yml restart
    else
        docker compose -f docker-compose.monitoring.yml restart
    fi

    print_success "Monitoring services restarted"
}

# Function to show status
show_status() {
    print_status "Monitoring Services Status:"
    echo

    cd "$MONITORING_DIR"

    if command -v docker-compose &> /dev/null; then
        docker-compose -f docker-compose.monitoring.yml ps
    else
        docker compose -f docker-compose.monitoring.yml ps
    fi
}

# Function to show logs
show_logs() {
    print_status "Showing logs for all monitoring services..."
    echo

    cd "$MONITORING_DIR"

    if command -v docker-compose &> /dev/null; then
        docker-compose -f docker-compose.monitoring.yml logs -f
    else
        docker compose -f docker-compose.monitoring.yml logs -f
    fi
}

# Main execution
main() {
    local skip_pulls=false
    local check_only=false

    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_usage
                exit 0
                ;;
            -v|--verbose)
                set -x
                shift
                ;;
            -q|--quiet)
                exec 1>/dev/null
                shift
                ;;
            --skip-pulls)
                skip_pulls=true
                shift
                ;;
            --check-only)
                check_only=true
                shift
                ;;
            --stop)
                stop_services
                exit 0
                ;;
            --restart)
                restart_services
                exit 0
                ;;
            --status)
                show_status
                exit 0
                ;;
            --logs)
                show_logs
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done

    echo "🔍 Knowledge Graph Analytics - Monitoring Setup"
    echo "=============================================="
    echo

    # Check prerequisites
    check_docker
    check_docker_compose

    if [[ $check_only == true ]]; then
        print_success "All prerequisites are met!"
        exit 0
    fi

    # Setup process
    create_directories
    create_env_file
    check_ports

    if [[ $skip_pulls == false ]]; then
        pull_images
    fi

    start_services
    wait_for_services
    verify_setup
    display_access_info

    print_success "Setup completed successfully! 🎉"
}

# Run main function with all arguments
main "$@"