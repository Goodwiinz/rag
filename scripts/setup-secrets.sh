#!/bin/bash
# =============================================================================
# Secrets Setup Script for Knowledge Graph Analytics Dashboard
# =============================================================================
# This script helps set up and manage secrets for different environments

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENVIRONMENT="${ENVIRONMENT:-development}"
NAMESPACE="${NAMESPACE:-knowledge-graph-analytics}"
SEED_FILE="$PROJECT_ROOT/scripts/seed-secrets.env"
AWS_REGION="${AWS_REGION:-us-west-2}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Generate random string
generate_random_string() {
    local length=${1:-32}
    openssl rand -base64 $length | tr -d "=+/" | cut -c1-$length
}

# Generate base64 encoded random string
generate_base64_string() {
    local length=${1:-32}
    generate_random_string $length | base64 -w 0
}

# Check if kubectl is available
check_kubectl() {
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed or not in PATH"
        exit 1
    fi
}

# Check if AWS CLI is available
check_aws() {
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed or not in PATH"
        exit 1
    fi
}

# Create namespace if it doesn't exist
create_namespace() {
    log_info "Creating namespace: $NAMESPACE"
    kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
    log_success "Namespace $NAMESPACE created or already exists"
}

# Generate secrets file
generate_seeds() {
    log_info "Generating secrets seed file..."

    cat > "$SEED_FILE" << EOF
# =============================================================================
# Secrets Configuration for Knowledge Graph Analytics Dashboard
# =============================================================================
# Generated: $(date)
# Environment: $ENVIRONMENT
# WARNING: This file contains sensitive information. Do not commit to version control.

# Database Configuration
DB_PASSWORD=$(generate_random_string 24)
DB_USERNAME=raguser
DB_NAME=ragdb

# Redis Configuration
REDIS_PASSWORD=$(generate_random_string 32)

# Neo4j Configuration
NEO4J_PASSWORD=$(generate_random_string 32)
NEO4J_USERNAME=neo4j

# Qdrant Configuration
QDRANT_API_KEY=$(generate_random_string 64)

# Backend Security
BACKEND_SECRET_KEY=$(generate_random_string 64)
JWT_SECRET=$(generate_random_string 64)
ENCRYPTION_KEY=$(generate_random_string 32)

# AI Service Keys
OPENAI_API_KEY=set_your_openai_api_key_here
ANTHROPIC_API_KEY=set_your_anthropic_api_key_here

# Monitoring
GRAFANA_ADMIN_PASSWORD=$(generate_random_string 16)
ALERTMANAGER_SMTP_PASSWORD=set_your_smtp_password_here

# SSL Certificates (set these paths to your certificate files)
SSL_CERT_PATH=path/to/your/certificate.crt
SSL_KEY_PATH=path/to/your/private.key

# Backup Configuration
AWS_ACCESS_KEY_ID=set_your_aws_access_key
AWS_SECRET_ACCESS_KEY=set_your_aws_secret_key
BACKUP_BUCKET=knowledge-graph-analytics-backups-$ENVIRONMENT

# AWS Region
AWS_REGION=$AWS_REGION
EOF

    log_success "Secrets seed file created: $SEED_FILE"
    log_warning "Please edit $SEED_FILE and set your actual API keys and certificates"
}

# Create Kubernetes secrets from environment variables
create_k8s_secrets() {
    local env_file="$1"

    if [ ! -f "$env_file" ]; then
        log_error "Environment file not found: $env_file"
        return 1
    fi

    log_info "Loading environment variables from: $env_file"
    set -a
    source "$env_file"
    set +a

    # Create database credentials secret
    log_info "Creating database credentials secret..."
    kubectl create secret generic database-credentials \
        --from-literal=username="$DB_USERNAME" \
        --from-literal=password="$DB_PASSWORD" \
        --from-literal=url="postgresql://$DB_USERNAME:$DB_PASSWORD@postgres:5432/$DB_NAME" \
        --namespace="$NAMESPACE" \
        --dry-run=client -o yaml | kubectl apply -f -

    # Create Redis credentials secret
    log_info "Creating Redis credentials secret..."
    kubectl create secret generic redis-credentials \
        --from-literal=password="$REDIS_PASSWORD" \
        --from-literal=url="redis://:$REDIS_PASSWORD@redis:6379/0" \
        --namespace="$NAMESPACE" \
        --dry-run=client -o yaml | kubectl apply -f -

    # Create Neo4j credentials secret
    log_info "Creating Neo4j credentials secret..."
    kubectl create secret generic neo4j-credentials \
        --from-literal=username="$NEO4J_USERNAME" \
        --from-literal=password="$NEO4J_PASSWORD" \
        --namespace="$NAMESPACE" \
        --dry-run=client -o yaml | kubectl apply -f -

    # Create Qdrant credentials secret
    log_info "Creating Qdrant credentials secret..."
    kubectl create secret generic qdrant-credentials \
        --from-literal=api-key="$QDRANT_API_KEY" \
        --namespace="$NAMESPACE" \
        --dry-run=client -o yaml | kubectl apply -f -

    # Create backend secrets
    log_info "Creating backend secrets..."
    kubectl create secret generic backend-secrets \
        --from-literal=secret-key="$BACKEND_SECRET_KEY" \
        --from-literal=jwt-secret="$JWT_SECRET" \
        --from-literal=encryption-key="$ENCRYPTION_KEY" \
        --namespace="$NAMESPACE" \
        --dry-run=client -o yaml | kubectl apply -f -

    # Create AI credentials secret
    log_info "Creating AI credentials secret..."
    kubectl create secret generic ai-credentials \
        --from-literal=openai-key="$OPENAI_API_KEY" \
        --from-literal=anthropic-key="$ANTHROPIC_API_KEY" \
        --namespace="$NAMESPACE" \
        --dry-run=client -o yaml | kubectl apply -f -

    # Create monitoring credentials secret
    log_info "Creating monitoring credentials secret..."
    kubectl create secret generic monitoring-credentials \
        --from-literal=grafana-admin-password="$GRAFANA_ADMIN_PASSWORD" \
        --from-literal=alertmanager-smtp-password="$ALERTMANAGER_SMTP_PASSWORD" \
        --namespace="$NAMESPACE" \
        --dry-run=client -o yaml | kubectl apply -f -

    log_success "Kubernetes secrets created successfully"
}

# Create SSL certificate secret
create_ssl_secret() {
    local cert_path="$SSL_CERT_PATH"
    local key_path="$SSL_KEY_PATH"

    if [ -f "$cert_path" ] && [ -f "$key_path" ]; then
        log_info "Creating SSL certificate secret..."
        kubectl create secret tls ssl-certificates \
            --cert="$cert_path" \
            --key="$key_path" \
            --namespace="$NAMESPACE" \
            --dry-run=client -o yaml | kubectl apply -f -
        log_success "SSL certificate secret created successfully"
    else
        log_warning "SSL certificate files not found. Skipping SSL secret creation."
        log_info "Set SSL_CERT_PATH and SSL_KEY_PATH in your environment file"
    fi
}

# Setup AWS Secrets Manager
setup_aws_secrets_manager() {
    log_info "Setting up AWS Secrets Manager..."

    # Check if AWS credentials are configured
    if ! aws sts get-caller-identity &>/dev/null; then
        log_error "AWS credentials not configured. Please run 'aws configure'"
        return 1
    fi

    # Create secrets in AWS Secrets Manager
    local secrets=(
        "knowledge-graph-analytics/$ENVIRONMENT/database-password:$DB_PASSWORD"
        "knowledge-graph-analytics/$ENVIRONMENT/redis-password:$REDIS_PASSWORD"
        "knowledge-graph-analytics/$ENVIRONMENT/neo4j-password:$NEO4J_PASSWORD"
        "knowledge-graph-analytics/$ENVIRONMENT/qdrant-api-key:$QDRANT_API_KEY"
        "knowledge-graph-analytics/$ENVIRONMENT/openai-api-key:$OPENAI_API_KEY"
        "knowledge-graph-analytics/$ENVIRONMENT/anthropic-api-key:$ANTHROPIC_API_KEY"
    )

    for secret_entry in "${secrets[@]}"; do
        IFS=':' read -r secret_name secret_value <<< "$secret_entry"

        log_info "Creating secret: $secret_name"
        aws secretsmanager create-secret \
            --name "$secret_name" \
            --description "Secret for Knowledge Graph Analytics - $ENVIRONMENT" \
            --secret-string "$secret_value" \
            --region "$AWS_REGION" \
            --no-cli-pager || \
        aws secretsmanager update-secret \
            --secret-id "$secret_name" \
            --secret-string "$secret_value" \
            --region "$AWS_REGION" \
            --no-cli-pager
    done

    log_success "AWS Secrets Manager setup completed"
}

# Verify secrets
verify_secrets() {
    log_info "Verifying created secrets..."

    local secrets=(
        "database-credentials"
        "redis-credentials"
        "neo4j-credentials"
        "qdrant-credentials"
        "backend-secrets"
        "ai-credentials"
        "monitoring-credentials"
    )

    for secret in "${secrets[@]}"; do
        if kubectl get secret "$secret" -n "$NAMESPACE" &>/dev/null; then
            log_success "✓ Secret '$secret' exists"
        else
            log_error "✗ Secret '$secret' missing"
        fi
    done
}

# Show secrets status
show_status() {
    log_info "Current secrets status for namespace: $NAMESPACE"
    echo
    kubectl get secrets -n "$NAMESPACE" | grep -E "(database|redis|neo4j|qdrant|backend|ai|monitoring)"
}

# Rotate secrets
rotate_secrets() {
    log_info "Rotating secrets for environment: $ENVIRONMENT"

    # Generate new random values
    local new_db_password=$(generate_random_string 24)
    local new_redis_password=$(generate_random_string 32)
    local new_neo4j_password=$(generate_random_string 32)
    local new_qdrant_api_key=$(generate_random_string 64)
    local new_backend_secret_key=$(generate_random_string 64)
    local new_jwt_secret=$(generate_random_string 64)

    # Update secrets
    kubectl patch secret database-credentials -n "$NAMESPACE" -p='{"data":{"password":"'$(echo -n "$new_db_password" | base64 -w 0)'"}}'
    kubectl patch secret redis-credentials -n "$NAMESPACE" -p='{"data":{"password":"'$(echo -n "$new_redis_password" | base64 -w 0)'"}}'
    kubectl patch secret neo4j-credentials -n "$NAMESPACE" -p='{"data":{"password":"'$(echo -n "$new_neo4j_password" | base64 -w 0)'"}}'
    kubectl patch secret qdrant-credentials -n "$NAMESPACE" -p='{"data":{"api-key":"'$(echo -n "$new_qdrant_api_key" | base64 -w 0)'"}}'
    kubectl patch secret backend-secrets -n "$NAMESPACE" -p='{"data":{"secret-key":"'$(echo -n "$new_backend_secret_key" | base64 -w 0)'"}}'
    kubectl patch secret backend-secrets -n "$NAMESPACE" -p='{"data":{"jwt-secret":"'$(echo -n "$new_jwt_secret" | base64 -w 0)'"}}'

    log_success "Secrets rotated successfully"
    log_warning "Please restart your application pods to use the new secrets"
}

# Main execution
main() {
    case "${1:-setup}" in
        "generate"|"gen")
            generate_seeds
            ;;
        "setup")
            check_kubectl
            create_namespace
            if [ ! -f "$SEED_FILE" ]; then
                log_warning "Seed file not found. Generating new one..."
                generate_seeds
                log_info "Please edit the seed file and run the script again"
                exit 0
            fi
            create_k8s_secrets "$SEED_FILE"
            create_ssl_secret
            verify_secrets
            ;;
        "aws"|"aws-secrets")
            check_aws
            if [ ! -f "$SEED_FILE" ]; then
                log_error "Seed file not found. Run '$0 generate' first"
                exit 1
            fi
            set -a
            source "$SEED_FILE"
            set +a
            setup_aws_secrets_manager
            ;;
        "status"|"show")
            check_kubectl
            show_status
            ;;
        "rotate")
            check_kubectl
            rotate_secrets
            ;;
        "verify")
            check_kubectl
            verify_secrets
            ;;
        "help"|"-h"|"--help")
            cat << EOF
Secrets Setup Script

Usage: $0 COMMAND [OPTIONS]

Commands:
    generate, gen     Generate a new secrets seed file
    setup            Set up Kubernetes secrets from seed file
    aws, aws-secrets  Set up AWS Secrets Manager secrets
    status, show     Show current secrets status
    rotate           Rotate existing secrets
    verify           Verify that all secrets are properly configured
    help             Show this help message

Environment Variables:
    ENVIRONMENT      Target environment (default: development)
    NAMESPACE        Kubernetes namespace (default: knowledge-graph-analytics)
    AWS_REGION       AWS region for Secrets Manager (default: us-west-2)

Examples:
    $0 generate
    $0 setup
    $0 ENVIRONMENT=production setup
    $0 aws-secrets
    $0 rotate

Important:
    - Always review and edit the generated seed file before running setup
    - Never commit actual secrets to version control
    - Use different values for different environments
    - Regularly rotate your secrets

EOF
            ;;
        *)
            log_error "Unknown command: $1"
            echo "Run '$0 help' for usage information"
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"