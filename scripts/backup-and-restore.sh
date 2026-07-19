#!/bin/bash
# =============================================================================
# Backup and Restore Script for Knowledge Graph Analytics Dashboard
# =============================================================================
# This script provides automated backup and restore functionality for all
# critical components of the application including databases, file storage,
# and Kubernetes configurations.

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
NAMESPACE="${NAMESPACE:-knowledge-graph-analytics}"
BACKUP_DIR="${BACKUP_DIR:-/tmp/knowledge-graph-backups}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$BACKUP_DIR/backup_${TIMESTAMP}.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

# Check dependencies
check_dependencies() {
    log_info "Checking dependencies..."

    local missing_deps=()

    if ! command -v kubectl &> /dev/null; then
        missing_deps+=("kubectl")
    fi

    if ! command -v aws &> /dev/null; then
        missing_deps+=("aws")
    fi

    if ! command -v helm &> /dev/null; then
        missing_deps+=("helm")
    fi

    if ! command -v velero &> /dev/null; then
        missing_deps+=("velero")
    fi

    if [ ${#missing_deps[@]} -ne 0 ]; then
        log_error "Missing dependencies: ${missing_deps[*]}"
        exit 1
    fi

    log_success "All dependencies are available"
}

# Create backup directory
create_backup_dir() {
    log_info "Creating backup directory: $BACKUP_DIR"
    mkdir -p "$BACKUP_DIR"
    log_success "Backup directory created"
}

# Backup PostgreSQL database
backup_postgresql() {
    log_info "Starting PostgreSQL database backup..."

    local pod_name=$(kubectl get pods -n "$NAMESPACE" -l app=postgres -o jsonpath='{.items[0].metadata.name}')
    if [ -z "$pod_name" ]; then
        log_error "PostgreSQL pod not found"
        return 1
    fi

    local backup_file="$BACKUP_DIR/postgres_backup_${TIMESTAMP}.sql"

    log_info "Executing pg_dump on pod: $pod_name"
    kubectl exec -n "$NAMESPACE" "$pod_name" -- pg_dump -U raguser -d ragdb > "$backup_file"

    if [ $? -eq 0 ]; then
        log_success "PostgreSQL backup completed: $backup_file"

        # Compress backup
        gzip "$backup_file"
        log_success "PostgreSQL backup compressed: ${backup_file}.gz"

        # Upload to S3 if AWS credentials are available
        if aws sts get-caller-identity &>/dev/null; then
            local s3_key="backups/postgres/postgres_backup_${TIMESTAMP}.sql.gz"
            aws s3 cp "${backup_file}.gz" "s3://knowledge-graph-analytics-backups/$s3_key"
            log_success "PostgreSQL backup uploaded to S3: $s3_key"
        fi
    else
        log_error "PostgreSQL backup failed"
        return 1
    fi
}

# Backup Redis data
backup_redis() {
    log_info "Starting Redis data backup..."

    local pod_name=$(kubectl get pods -n "$NAMESPACE" -l app=redis -o jsonpath='{.items[0].metadata.name}')
    if [ -z "$pod_name" ]; then
        log_error "Redis pod not found"
        return 1
    fi

    local backup_file="$BACKUP_DIR/redis_backup_${TIMESTAMP}.rdb"

    log_info "Executing Redis BGSAVE on pod: $pod_name"
    kubectl exec -n "$NAMESPACE" "$pod_name" -- redis-cli BGSAVE

    # Wait for backup to complete
    log_info "Waiting for Redis backup to complete..."
    sleep 10

    # Copy the RDB file
    kubectl cp "$NAMESPACE/$pod_name:/data/dump.rdb" "$backup_file"

    if [ $? -eq 0 ]; then
        log_success "Redis backup completed: $backup_file"

        # Compress backup
        gzip "$backup_file"
        log_success "Redis backup compressed: ${backup_file}.gz"

        # Upload to S3 if AWS credentials are available
        if aws sts get-caller-identity &>/dev/null; then
            local s3_key="backups/redis/redis_backup_${TIMESTAMP}.rdb.gz"
            aws s3 cp "${backup_file}.gz" "s3://knowledge-graph-analytics-backups/$s3_key"
            log_success "Redis backup uploaded to S3: $s3_key"
        fi
    else
        log_error "Redis backup failed"
        return 1
    fi
}

# Backup Neo4j data
backup_neo4j() {
    log_info "Starting Neo4j data backup..."

    local pod_name=$(kubectl get pods -n "$NAMESPACE" -l app=neo4j -o jsonpath='{.items[0].metadata.name}')
    if [ -z "$pod_name" ]; then
        log_error "Neo4j pod not found"
        return 1
    fi

    local backup_file="$BACKUP_DIR/neo4j_backup_${TIMESTAMP}.cypher"

    log_info "Executing Neo4j dump on pod: $pod_name"
    kubectl exec -n "$NAMESPACE" "$pod_name" -- cypher-shell -u neo4j -p "$NEO4J_PASSWORD" "CALL apoc.export.cypher.all('/tmp/neo4j_backup.cypher', {})" || {
        log_warning "Neo4j apoc.export not available, trying alternative method..."

        # Alternative: Use neo4j-admin dump (requires access to Neo4j data directory)
        kubectl exec -n "$NAMESPACE" "$pod_name" -- neo4j-admin dump --database=neo4j --to=/tmp/neo4j_backup.dump
        kubectl cp "$NAMESPACE/$pod_name:/tmp/neo4j_backup.dump" "$BACKUP_DIR/neo4j_backup_${TIMESTAMP}.dump"
        backup_file="$BACKUP_DIR/neo4j_backup_${TIMESTAMP}.dump"
    }

    if [ $? -eq 0 ]; then
        log_success "Neo4j backup completed: $backup_file"

        # Compress backup
        gzip "$backup_file"
        log_success "Neo4j backup compressed: ${backup_file}.gz"

        # Upload to S3 if AWS credentials are available
        if aws sts get-caller-identity &>/dev/null; then
            local s3_key="backups/neo4j/neo4j_backup_${TIMESTAMP}.dump.gz"
            aws s3 cp "${backup_file}.gz" "s3://knowledge-graph-analytics-backups/$s3_key"
            log_success "Neo4j backup uploaded to S3: $s3_key"
        fi
    else
        log_error "Neo4j backup failed"
        return 1
    fi
}

# Backup Qdrant data
backup_qdrant() {
    log_info "Starting Qdrant data backup..."

    local pod_name=$(kubectl get pods -n "$NAMESPACE" -l app=qdrant -o jsonpath='{.items[0].metadata.name}')
    if [ -z "$pod_name" ]; then
        log_error "Qdrant pod not found"
        return 1
    fi

    local backup_file="$BACKUP_DIR/qdrant_backup_${TIMESTAMP}.tar.gz"

    log_info "Creating Qdrant data archive from pod: $pod_name"
    kubectl exec -n "$NAMESPACE" "$pod_name" -- tar -czf /tmp/qdrant_backup.tar.gz -C /qdrant/storage storage

    # Copy the archive
    kubectl cp "$NAMESPACE/$pod_name:/tmp/qdrant_backup.tar.gz" "$backup_file"

    if [ $? -eq 0 ]; then
        log_success "Qdrant backup completed: $backup_file"

        # Upload to S3 if AWS credentials are available
        if aws sts get-caller-identity &>/dev/null; then
            local s3_key="backups/qdrant/qdrant_backup_${TIMESTAMP}.tar.gz"
            aws s3 cp "$backup_file" "s3://knowledge-graph-analytics-backups/$s3_key"
            log_success "Qdrant backup uploaded to S3: $s3_key"
        fi
    else
        log_error "Qdrant backup failed"
        return 1
    fi
}

# Backup Kubernetes configurations
backup_kubernetes_configs() {
    log_info "Starting Kubernetes configuration backup..."

    local config_dir="$BACKUP_DIR/k8s_configs_${TIMESTAMP}"
    mkdir -p "$config_dir"

    # Backup all resources in namespace
    log_info "Backing up all resources in namespace: $NAMESPACE"
    kubectl get all,configmaps,secrets,pvc,ingress,roles,rolebindings -n "$NAMESPACE" -o yaml > "$config_dir/all_resources.yaml"

    # Backup specific application configurations
    log_info "Backing up Helm releases"
    helm list -n "$NAMESPACE" -o yaml > "$config_dir/helm_releases.yaml"

    # Get Helm values for each release
    for release in $(helm list -n "$NAMESPACE" -q); do
        log_info "Backing up Helm values for release: $release"
        helm get values "$release" -n "$NAMESPACE" > "$config_dir/helm_values_${release}.yaml"
    done

    # Backup Custom Resource Definitions
    log_info "Backing up Custom Resource Definitions"
    kubectl get crds -o yaml > "$config_dir/crds.yaml"

    # Backup namespace configuration
    log_info "Backing up namespace configuration"
    kubectl get namespace "$NAMESPACE" -o yaml > "$config_dir/namespace.yaml"

    log_success "Kubernetes configuration backup completed: $config_dir"

    # Create archive and upload to S3
    tar -czf "$BACKUP_DIR/k8s_configs_${TIMESTAMP}.tar.gz" -C "$BACKUP_DIR" "k8s_configs_${TIMESTAMP}"

    if aws sts get-caller-identity &>/dev/null; then
        local s3_key="backups/kubernetes/k8s_configs_${TIMESTAMP}.tar.gz"
        aws s3 cp "$BACKUP_DIR/k8s_configs_${TIMESTAMP}.tar.gz" "s3://knowledge-graph-analytics-backups/$s3_key"
        log_success "Kubernetes configuration backup uploaded to S3: $s3_key"
    fi
}

# Backup application files
backup_application_files() {
    log_info "Starting application files backup..."

    local backup_file="$BACKUP_DIR/application_files_${TIMESTAMP}.tar.gz"

    # Backup uploads directory from persistent volume claims
    local uploads_pvc=$(kubectl get pvc -n "$NAMESPACE" -l app=knowledge-graph-analytics -o jsonpath='{.items[0].metadata.name}')
    if [ -n "$uploads_pvc" ]; then
        log_info "Backing up PVC: $uploads_pvc"

        # Create temporary pod for PVC access
        kubectl run backup-pod --image=busybox --rm -i --restart=Never --namespace="$NAMESPACE" \
            --overrides='{
              "spec": {
                "containers": [{
                  "name": "backup",
                  "image": "busybox",
                  "command": ["sleep", "3600"],
                  "volumeMounts": [{
                    "name": "uploads",
                    "mountPath": "/data"
                  }]
                }],
                "volumes": [{
                  "name": "uploads",
                  "persistentVolumeClaim": {
                    "claimName": "'$uploads_pvc'"
                  }
                }]
              }
            }' &

        local backup_pod="backup-pod"

        # Wait for pod to be ready
        kubectl wait --for=condition=Ready pod/$backup_pod -n "$NAMESPACE" --timeout=300s

        # Copy files from PVC
        kubectl exec -n "$NAMESPACE" "$backup_pod" -- tar -czf /tmp/uploads_backup.tar.gz -C /data .
        kubectl cp "$NAMESPACE/$backup_pod:/tmp/uploads_backup.tar.gz" "$BACKUP_DIR/uploads_backup_${TIMESTAMP}.tar.gz"

        # Delete temporary pod
        kubectl delete pod "$backup_pod" -n "$NAMESPACE" --force --grace-period=0

        log_success "Application files backup completed: $BACKUP_DIR/uploads_backup_${TIMESTAMP}.tar.gz"

        # Upload to S3 if AWS credentials are available
        if aws sts get-caller-identity &>/dev/null; then
            local s3_key="backups/files/uploads_backup_${TIMESTAMP}.tar.gz"
            aws s3 cp "$BACKUP_DIR/uploads_backup_${TIMESTAMP}.tar.gz" "s3://knowledge-graph-analytics-backups/$s3_key"
            log_success "Application files backup uploaded to S3: $s3_key"
        fi
    else
        log_warning "No uploads PVC found for backup"
    fi
}

# Create Velero backup
create_velero_backup() {
    log_info "Creating Velero backup..."

    if command -v velero &> /dev/null; then
        local backup_name="knowledge-graph-backup-${TIMESTAMP}"

        log_info "Running Velero backup: $backup_name"
        velero create backup "$backup_name" \
            --namespace "$NAMESPACE" \
            --include-namespaces "$NAMESPACE" \
            --default-volumes-to-restic=false \
            --wait

        if [ $? -eq 0 ]; then
            log_success "Velero backup completed: $backup_name"
        else
            log_error "Velero backup failed"
            return 1
        fi
    else
        log_warning "Velero not available, skipping Velero backup"
    fi
}

# Restore from backup
restore_backup() {
    local backup_id="$1"

    if [ -z "$backup_id" ]; then
        log_error "Backup ID is required for restore"
        return 1
    fi

    log_info "Starting restore from backup: $backup_id"

    # Download backup files from S3
    local restore_dir="$BACKUP_DIR/restore_${backup_id}"
    mkdir -p "$restore_dir"

    # List available backups
    if aws sts get-caller-identity &>/dev/null; then
        log_info "Available backups in S3:"
        aws s3 ls s3://knowledge-graph-analytics-backups/backups/ --recursive

        # Download backup files
        log_info "Downloading backup files for: $backup_id"
        aws s3 sync "s3://knowledge-graph-analytics-backups/backups/$backup_id" "$restore_dir/"
    else
        log_error "AWS credentials not configured for restore"
        return 1
    fi

    # Restore databases
    log_info "Restoring databases..."

    # Restore PostgreSQL
    if [ -f "$restore_dir/postgres/postgres_backup_${backup_id}.sql.gz" ]; then
        log_info "Restoring PostgreSQL database..."
        gunzip -c "$restore_dir/postgres/postgres_backup_${backup_id}.sql.gz" | kubectl exec -i -n "$NAMESPACE" deployment/postgres -- psql -U raguser -d ragdb
        log_success "PostgreSQL restore completed"
    fi

    # Restore Redis
    if [ -f "$restore_dir/redis/redis_backup_${backup_id}.rdb.gz" ]; then
        log_info "Restoring Redis data..."
        # Note: Redis restore requires service restart
        kubectl cp "$restore_dir/redis/redis_backup_${backup_id}.rdb.gz" temp_redis_backup.rdb.gz
        gunzip temp_redis_backup.rdb.gz
        # Implementation would depend on Redis setup
        log_warning "Redis restore requires manual intervention"
    fi

    log_success "Restore process initiated. Please verify application functionality."
}

# List available backups
list_backups() {
    log_info "Listing available backups..."

    if aws sts get-caller-identity &>/dev/null; then
        echo "=== S3 Backups ==="
        aws s3 ls s3://knowledge-graph-analytics-backups/backups/ --recursive | head -20

        if command -v velero &> /dev/null; then
            echo
            echo "=== Velero Backups ==="
            velero get backups --namespace "$NAMESPACE"
        fi
    else
        log_error "AWS credentials not configured"
    fi
}

# Cleanup old backups
cleanup_old_backups() {
    local retention_days="${1:-30}"

    log_info "Cleaning up backups older than $retention_days days..."

    if aws sts get-caller-identity &>/dev/null; then
        # Clean up S3 backups
        local cutoff_date=$(date -d "$retention_days days ago" +%Y%m%d)

        aws s3 ls s3://knowledge-graph-analytics-backups/backups/ --recursive | \
        while read -r line; do
            local date_str=$(echo "$line" | awk '{print $1}')
            local file_path=$(echo "$line" | awk '{print $4}')

            # Convert date string to comparable format
            local file_date=$(date -d "$date_str" +%Y%m%d 2>/dev/null || echo "00000000")

            if [ "$file_date" -lt "$cutoff_date" ]; then
                log_info "Deleting old backup: $file_path"
                aws s3 rm "s3://knowledge-graph-analytics-backups/$file_path"
            fi
        done

        log_success "Old backup cleanup completed"
    else
        log_error "AWS credentials not configured"
    fi
}

# Main execution
main() {
    case "${1:-backup}" in
        "backup")
            log_info "Starting full backup process..."
            check_dependencies
            create_backup_dir
            backup_postgresql
            backup_redis
            backup_neo4j
            backup_qdrant
            backup_kubernetes_configs
            backup_application_files
            create_velero_backup
            log_success "Full backup process completed"
            ;;
        "restore")
            if [ -z "${2:-}" ]; then
                log_error "Backup ID is required for restore"
                echo "Usage: $0 restore <backup_id>"
                exit 1
            fi
            check_dependencies
            restore_backup "$2"
            ;;
        "list"|"ls")
            check_dependencies
            list_backups
            ;;
        "cleanup")
            local days="${2:-30}"
            check_dependencies
            cleanup_old_backups "$days"
            ;;
        "help"|"-h"|"--help")
            cat << EOF
Backup and Restore Script

Usage: $0 COMMAND [OPTIONS]

Commands:
    backup                   Perform full backup of all components
    restore <backup_id>      Restore from a specific backup
    list, ls                 List available backups
    cleanup [days]           Clean up old backups (default: 30 days)
    help                     Show this help message

Examples:
    $0 backup
    $0 restore 20231201_120000
    $0 list
    $0 cleanup 7

Components backed up:
    - PostgreSQL database
    - Redis cache
    - Neo4j graph database
    - Qdrant vector database
    - Kubernetes configurations
    - Application files
    - Velero cluster backup

Important:
    - Ensure AWS credentials are configured for S3 operations
    - Verify backups are created successfully
    - Test restore procedures regularly
    - Monitor backup processes for failures

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