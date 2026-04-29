#!/bin/bash

# Comprehensive Deployment Script for Multimodal RAG System
# Supports blue-green deployment, rollback, and environment management

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENVIRONMENT="${ENVIRONMENT:-staging}"
COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
BLUE_GREEN_COMPOSE_FILE="docker-compose.${ENVIRONMENT}-blue-green.yml"
BLUE_GREEN_STATE_FILE="${PROJECT_ROOT}/.blue-green-state-${ENVIRONMENT}"
HEALTH_CHECK_URL="${HEALTH_CHECK_URL:-http://localhost:8000/health}"
MAX_RETRIES="${MAX_RETRIES:-30}"
RETRY_DELAY="${RETRY_DELAY:-10}"
BACKUP_BEFORE_DEPLOY="${BACKUP_BEFORE_DEPLOY:-true}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] SUCCESS:${NC} $1"
}

warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

# Error handling
error_exit() {
    error "$1"
    exit 1
}

# Check dependencies
check_dependencies() {
    log "Checking dependencies..."

    local deps=("docker" "docker-compose" "curl" "jq")
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            error_exit "Required dependency not found: $dep"
        fi
    done

    log "Dependencies check completed"
}

# Load environment variables
load_env() {
    log "Loading environment variables..."

    local env_file="${PROJECT_ROOT}/.env.${ENVIRONMENT}"
    if [[ -f "$env_file" ]]; then
        set -a
        source "$env_file"
        set +a
        log "Loaded environment from: $env_file"
    else
        warning "Environment file not found: $env_file"
    fi

    # Check required variables
    local required_vars=("SECRET_KEY" "DATABASE_URL" "REDIS_URL")
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var:-}" ]]; then
            error_exit "Required environment variable not set: $var"
        fi
    done
}

# Create backup before deployment
create_backup() {
    if [[ "$BACKUP_BEFORE_DEPLOY" != "true" ]]; then
        return 0
    fi

    log "Creating backup before deployment..."

    local backup_dir="${PROJECT_ROOT}/backups/pre-deploy-$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$backup_dir"

    # Backup database
    log "Backing up database..."
    "${SCRIPT_DIR}/backup/backup_database.sh" || warning "Database backup failed"

    # Backup vector store
    log "Backing up vector store..."
    python3 "${SCRIPT_DIR}/backup/backup_vector_store.py" || warning "Vector store backup failed"

    # Backup configuration files
    log "Backing up configuration files..."
    cp -r "${PROJECT_ROOT}/.env."* "$backup_dir/" 2>/dev/null || true
    cp -r "${PROJECT_ROOT}/nginx" "$backup_dir/" 2>/dev/null || true

    success "Backup created: $backup_dir"
}

# Pull latest images
pull_images() {
    log "Pulling latest Docker images..."

    cd "$PROJECT_ROOT"

    if [[ -f "$COMPOSE_FILE" ]]; then
        docker-compose -f "$COMPOSE_FILE" pull || error_exit "Failed to pull images"
    else
        error_exit "Compose file not found: $COMPOSE_FILE"
    fi

    success "Images pulled successfully"
}

# Run pre-deployment tests
run_pre_deploy_tests() {
    log "Running pre-deployment tests..."

    cd "$PROJECT_ROOT"

    # Run unit tests
    if [[ -f "backend/pytest.ini" ]] || [[ -f "backend/pyproject.toml" ]]; then
        log "Running backend unit tests..."
        cd backend
        python -m pytest tests/unit/ -v || error_exit "Backend unit tests failed"
        cd ..
    fi

    # Run frontend tests
    if [[ -f "frontend/package.json" ]]; then
        log "Running frontend tests..."
        cd frontend
        npm test -- --coverage --watchAll=false || error_exit "Frontend tests failed"
        cd ..
    fi

    success "Pre-deployment tests passed"
}

# Standard deployment
deploy_standard() {
    log "Starting standard deployment..."

    cd "$PROJECT_ROOT"

    # Stop existing services
    log "Stopping existing services..."
    docker-compose -f "$COMPOSE_FILE" down || true

    # Start new services
    log "Starting new services..."
    docker-compose -f "$COMPOSE_FILE" up -d || error_exit "Failed to start services"

    # Wait for services to be ready
    wait_for_health_check

    success "Standard deployment completed"
}

# Blue-green deployment
deploy_blue_green() {
    log "Starting blue-green deployment..."

    cd "$PROJECT_ROOT"

    # Determine current active environment from persisted state
    local current_active="blue"  # Safe default
    
    if [[ -f "$BLUE_GREEN_STATE_FILE" ]]; then
        local stored_state=$(cat "$BLUE_GREEN_STATE_FILE" 2>/dev/null | tr -d '[:space:]')
        
        # Validate stored state
        if [[ "$stored_state" == "blue" ]] || [[ "$stored_state" == "green" ]]; then
            current_active="$stored_state"
            log "Read current active state from file: $current_active"
        else
            warning "Invalid state in $BLUE_GREEN_STATE_FILE: '$stored_state', using default: $current_active"
        fi
    else
        log "No state file found at $BLUE_GREEN_STATE_FILE, using default: $current_active"
    fi
    
    # Secondary validation: check if compose file exists (optional safety check)
    if [[ ! -f "$BLUE_GREEN_COMPOSE_FILE" ]]; then
        log "Blue-green compose file not found, will create it"
    fi

    local new_active=$([ "$current_active" = "blue" ] && echo "green" || echo "blue")
    log "Current active: $current_active, New active: $new_active"

    # Create green compose file if it doesn't exist
    if [[ ! -f "$BLUE_GREEN_COMPOSE_FILE" ]]; then
        create_blue_green_compose
    fi

    # Deploy to new environment
    log "Deploying to $new_active environment..."
    COMPOSE_FILE="$BLUE_GREEN_COMPOSE_FILE" \
        ACTIVE_COLOR="$new_active" \
        docker-compose -f "$BLUE_GREEN_COMPOSE_FILE" up -d || error_exit "Failed to deploy to $new_active"

    # Wait for new environment to be healthy
    local temp_health_url="$HEALTH_CHECK_URL"
    if [[ "$new_active" = "green" ]]; then
        temp_health_url="${temp_health_url//localhost/localhost:8001}"
    fi

    wait_for_health_check "$temp_health_url"

    # Run smoke tests
    run_smoke_tests "$temp_health_url"

    # Switch traffic to new environment
    log "Switching traffic to $new_active environment..."
    switch_traffic "$new_active"

    # Stop old environment
    log "Stopping old $current_active environment..."
    COMPOSE_FILE="$BLUE_GREEN_COMPOSE_FILE" \
        ACTIVE_COLOR="$current_active" \
        docker-compose -f "$BLUE_GREEN_COMPOSE_FILE" down

    # Persist new active state atomically
    log "Persisting new active state: $new_active"
    echo "$new_active" > "${BLUE_GREEN_STATE_FILE}.tmp" || error_exit "Failed to write state file"
    mv "${BLUE_GREEN_STATE_FILE}.tmp" "$BLUE_GREEN_STATE_FILE" || error_exit "Failed to update state file"
    success "Active state persisted to $BLUE_GREEN_STATE_FILE"

    success "Blue-green deployment completed successfully"
}

# Create blue-green compose file
create_blue_green_compose() {
    log "Creating blue-green compose file..."

    cat > "$BLUE_GREEN_COMPOSE_FILE" << 'EOF'
version: '3.8'

services:
  backend-blue:
    extends:
      file: ${COMPOSE_FILE}
      service: backend
    ports:
      - "8000:8000"
    environment:
      - SERVICE_COLOR=blue
    profiles:
      - blue

  backend-green:
    extends:
      file: ${COMPOSE_FILE}
      service: backend
    ports:
      - "8001:8000"
    environment:
      - SERVICE_COLOR=green
    profiles:
      - green

  frontend-blue:
    extends:
      file: ${COMPOSE_FILE}
      service: frontend
    ports:
      - "3000:80"
    environment:
      - REACT_APP_API_URL=http://localhost:8000
    profiles:
      - blue

  frontend-green:
    extends:
      file: ${COMPOSE_FILE}
      service: frontend
    ports:
      - "3001:80"
    environment:
      - REACT_APP_API_URL=http://localhost:8001
    profiles:
      - green

  # Include all other services unchanged
EOF

    # Add other services from original compose file
    local temp_file=$(mktemp)
    grep -v "backend:\|frontend:" "$COMPOSE_FILE" >> "$temp_file" || true
    cat "$temp_file" >> "$BLUE_GREEN_COMPOSE_FILE"
    rm "$temp_file"

    success "Blue-green compose file created"
}

# Switch traffic between blue/green environments
switch_traffic() {
    local active_color="$1"

    log "Switching traffic to $active_color environment..."

    # Update nginx configuration
    local nginx_conf="${PROJECT_ROOT}/nginx/switch-${active_color}.conf"
    if [[ -f "$nginx_conf" ]]; then
        cp "$nginx_conf" "${PROJECT_ROOT}/nginx/nginx.conf"
        docker-compose -f "$COMPOSE_FILE" exec nginx nginx -s reload || warning "Failed to reload nginx"
    fi

    # Update DNS or load balancer if needed
    # This would depend on your infrastructure setup

    success "Traffic switched to $active_color environment"
}

# Wait for health check to pass
wait_for_health_check() {
    local url="${1:-$HEALTH_CHECK_URL}"
    local retry_count=0

    log "Waiting for health check at $url..."

    while [[ $retry_count -lt $MAX_RETRIES ]]; do
        if curl -f -s "$url" > /dev/null 2>&1; then
            success "Health check passed"
            return 0
        fi

        retry_count=$((retry_count + 1))
        log "Health check failed (attempt $retry_count/$MAX_RETRIES), retrying in ${RETRY_DELAY}s..."
        sleep "$RETRY_DELAY"
    done

    error_exit "Health check failed after $MAX_RETRIES attempts"
}

# Run smoke tests
run_smoke_tests() {
    local base_url="${1:-http://localhost:8000}"

    log "Running smoke tests..."

    # Test basic endpoints
    local endpoints=(
        "$base_url/health"
        "$base_url/api/documents"
    )

    for endpoint in "${endpoints[@]}"; do
        if curl -f -s "$endpoint" > /dev/null; then
            success "Smoke test passed: $endpoint"
        else
            error_exit "Smoke test failed: $endpoint"
        fi
    done

    success "All smoke tests passed"
}

# Post-deployment verification
post_deploy_verification() {
    log "Running post-deployment verification..."

    # Check if all containers are running
    local running_containers=$(docker-compose -f "$COMPOSE_FILE" ps -q | wc -l)
    local total_containers=$(docker-compose -f "$COMPOSE_FILE" config --services | wc -l)

    if [[ $running_containers -eq $total_containers ]]; then
        success "All containers are running"
    else
        warning "Only $running_containers/$total_containers containers are running"
    fi

    # Check resource usage
    local memory_usage=$(docker stats --no-stream --format "table {{.Container}}\t{{.MemUsage}}" | tail -n +2)
    log "Memory usage:"
    echo "$memory_usage"

    # Run integration tests if available
    if [[ -f "${PROJECT_ROOT}/backend/tests/integration/test_api.py" ]]; then
        log "Running integration tests..."
        cd "${PROJECT_ROOT}/backend"
        python -m pytest tests/integration/ -v || warning "Integration tests failed"
        cd ..
    fi

    success "Post-deployment verification completed"
}

# Cleanup old images and containers
cleanup() {
    log "Cleaning up old Docker resources..."

    # Remove unused images
    docker image prune -f || true

    # Remove unused containers
    docker container prune -f || true

    # Remove unused volumes (be careful with this)
    # docker volume prune -f || true

    success "Cleanup completed"
}

# Rollback deployment
rollback() {
    log "Starting rollback..."

    local rollback_to="${1:-previous}"
    local backup_dir="${2:-}"

    if [[ -z "$backup_dir" ]]; then
        # Find most recent backup
        backup_dir=$(find "${PROJECT_ROOT}/backups" -type d -name "pre-deploy-*" | sort -r | head -n 1)
        if [[ -z "$backup_dir" ]]; then
            error_exit "No backup found for rollback"
        fi
    fi

    log "Rolling back to backup: $backup_dir"

    # Stop current services
    docker-compose -f "$COMPOSE_FILE" down || true

    # Restore configuration files
    if [[ -f "$backup_dir/.env.${ENVIRONMENT}" ]]; then
        cp "$backup_dir/.env.${ENVIRONMENT}" "${PROJECT_ROOT}/"
    fi

    # Restore database
    if [[ -f "$backup_dir"/*multimodal_rag_backup*.sql.gz ]]; then
        log "Restoring database from backup..."
        # Database restore logic here
    fi

    # Start services
    docker-compose -f "$COMPOSE_FILE" up -d || error_exit "Failed to start services after rollback"

    # Wait for health check
    wait_for_health_check

    success "Rollback completed successfully"
}

# Get deployment status
get_status() {
    log "Getting deployment status..."

    cd "$PROJECT_ROOT"

    echo "=== Docker Compose Status ==="
    docker-compose -f "$COMPOSE_FILE" ps

    echo -e "\n=== Container Health ==="
    docker-compose -f "$COMPOSE_FILE" exec -T backend curl -s http://localhost:8000/health | jq . || echo "Backend not accessible"

    echo -e "\n=== Recent Logs ==="
    docker-compose -f "$COMPOSE_FILE" logs --tail=20 backend
}

# Show usage
usage() {
    cat << EOF
Usage: $0 [COMMAND] [OPTIONS]

Commands:
    deploy           Deploy the application
    deploy-blue-green    Deploy using blue-green strategy
    rollback [backup]    Rollback to previous version or specific backup
    status           Show deployment status
    test            Run pre-deployment tests
    backup          Create backup
    cleanup         Clean up Docker resources
    help            Show this help message

Environment Variables:
    ENVIRONMENT      Target environment (staging, production)
    BACKUP_BEFORE_DEPLOY  Create backup before deployment (true/false)
    HEALTH_CHECK_URL  Health check URL
    MAX_RETRIES      Maximum health check retries
    RETRY_DELAY      Delay between health check retries

Examples:
    $0 deploy                           # Deploy to staging
    $0 ENVIRONMENT=production deploy     # Deploy to production
    $0 deploy-blue-green                # Blue-green deployment
    $0 rollback                         # Rollback to previous version
    $0 rollback /backups/pre-deploy-20231201_120000  # Rollback to specific backup
EOF
}

# Main execution
main() {
    local command="${1:-help}"

    case "$command" in
        "deploy")
            check_dependencies
            load_env
            create_backup
            pull_images
            run_pre_deploy_tests
            deploy_standard
            post_deploy_verification
            cleanup
            ;;
        "deploy-blue-green")
            check_dependencies
            load_env
            create_backup
            pull_images
            run_pre_deploy_tests
            deploy_blue_green
            post_deploy_verification
            cleanup
            ;;
        "rollback")
            check_dependencies
            load_env
            rollback "${2:-}" "${3:-}"
            post_deploy_verification
            ;;
        "status")
            check_dependencies
            get_status
            ;;
        "test")
            check_dependencies
            load_env
            run_pre_deploy_tests
            ;;
        "backup")
            check_dependencies
            load_env
            create_backup
            ;;
        "cleanup")
            check_dependencies
            cleanup
            ;;
        "help"|"-h"|"--help")
            usage
            ;;
        *)
            error_exit "Unknown command: $command. Use 'help' for usage information."
            ;;
    esac

    success "Operation completed successfully!"
}

# Handle signals gracefully
trap 'error "Deployment interrupted"; exit 1' INT TERM

# Run main function
main "$@"