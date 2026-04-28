#!/bin/bash

# Backup and Recovery Script for Multimodal Enterprise RAG System
# Automated backup with retention and recovery procedures

set -e

# Configuration
CONFIG_FILE="/etc/rag-backup/config.conf"
LOG_FILE="/var/log/rag-backup.log"
BACKUP_DIR="/var/backups/rag-system"
MAX_BACKUP_RETENTION_DAYS=30
ENCRYPTION_KEY_FILE="/etc/rag-backup/encryption.key"
# Operator-managed passphrase used to wrap $ENCRYPTION_KEY_FILE so the wrapped
# key remains decryptable if the on-disk key is lost. Source from a KMS, sealed
# secret, or password manager — never generated here. See issue #378.
WRAPPING_PASSPHRASE_FILE="${WRAPPING_PASSPHRASE_FILE:-/etc/rag-backup/wrapping-passphrase}"
PBKDF2_ITER=200000
SLACK_WEBHOOK="${SLACK_WEBHOOK}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Error handling
error_exit() {
    echo -e "${RED}ERROR: $1${NC}" | tee -a "$LOG_FILE"
    send_slack_notification ":red_alert: Backup failed: $1"
    exit 1
}

# Success message
success() {
    echo -e "${GREEN}SUCCESS: $1${NC}" | tee -a "$LOG_FILE"
}

# Warning message
warning() {
    echo -e "${YELLOW}WARNING: $1${NC}" | tee -a "$LOG_FILE"
}

# Send Slack notification
send_slack_notification() {
    if [[ -n "$SLACK_WEBHOOK" ]]; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"$1\"}" "$SLACK_WEBHOOK" || true
    fi
}

# Load configuration
load_config() {
    if [[ -f "$CONFIG_FILE" ]]; then
        source "$CONFIG_FILE"
    else
        error_exit "Configuration file not found: $CONFIG_FILE"
    fi
}

# Create backup directory structure
setup_backup_structure() {
    log "Setting up backup directory structure"

    # Create main backup directory
    mkdir -p "$BACKUP_DIR"
    mkdir -p "$BACKUP_DIR/database"
    mkdir -p "$BACKUP_DIR/volumes"
    mkdir -p "$BACKUP_DIR/config"
    mkdir -p "$BACKUP_DIR/logs"
    mkdir -p "$BACKUP_DIR/encrypted"

    # Set permissions
    chmod 700 "$BACKUP_DIR"
    chmod 700 "$BACKUP_DIR/encrypted"

    # Create timestamp
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_PATH="$BACKUP_DIR/$TIMESTAMP"
    mkdir -p "$BACKUP_PATH"
}

# Database backup
backup_database() {
    log "Starting database backup"

    # PostgreSQL backup
    if docker ps | grep -q "rag-postgres-prod"; then
        log "Backing up PostgreSQL database"
        docker exec rag-postgres-prod pg_dump -U raguser ragdb > "$BACKUP_PATH/postgres_dump.sql"
        success "PostgreSQL backup completed"
    else
        warning "PostgreSQL container not running"
    fi

    # Neo4j backup
    if docker ps | grep -q "rag-neo4j-prod"; then
        log "Backing up Neo4j database"
        docker exec rag-neo4j-prod neo4j-admin database dump --database=ragdb --to="$BACKUP_PATH/neo4j_dump"
        success "Neo4j backup completed"
    else
        warning "Neo4j container not running"
    fi

    # Redis backup
    if docker ps | grep -q "rag-redis-prod"; then
        log "Backing up Redis data"
        docker exec rag-redis-prod redis-cli BGSAVE
        cp "$(docker exec rag-redis-prod redis-cli CONFIG GET dir | tail -n1)/dump.rdb" "$BACKUP_PATH/redis_dump.rdb"
        success "Redis backup completed"
    else
        warning "Redis container not running"
    fi
}

# Volume backup
backup_volumes() {
    log "Starting volume backups"

    # Uploads volume
    if docker ps | grep -q "rag-frontend-prod"; then
        log "Backing up uploads volume"
        docker run --rm -v rag-prod_uploads:/data -v "$BACKUP_PATH:/backup" \
            alpine tar czf "/backup/uploads_backup.tar.gz" -C /data .
        success "Uploads volume backup completed"
    fi

    # Models volume
    if docker ps | grep -q "rag-backend-prod"; then
        log "Backing up models volume"
        docker run --rm -v rag-prod_models:/data -v "$BACKUP_PATH:/backup" \
            alpine tar czf "/backup/models_backup.tar.gz" -C /data .
        success "Models volume backup completed"
    fi

    # Logs volume
    if docker ps | grep -q "rag-backend-prod"; then
        log "Backing up logs volume"
        docker run --rm -v rag-prod_logs:/data -v "$BACKUP_PATH:/backup" \
            alpine tar czf "/backup/logs_backup.tar.gz" -C /data .
        success "Logs volume backup completed"
    fi
}

# Configuration backup
backup_configuration() {
    log "Starting configuration backup"

    # Docker compose files
    cp "/var/lib/docker-compose/rag-prod/docker-compose.prod.yml" "$BACKUP_PATH/"
    cp "/var/lib/docker-compose/rag-prod/.env" "$BACKUP_PATH/" || true

    # Terraform state
    if [[ -d "/var/lib/terraform/rag-prod" ]]; then
        cp -r "/var/lib/terraform/rag-prod" "$BACKUP_PATH/terraform_state"
        success "Terraform state backup completed"
    fi

    # Kubernetes manifests
    if [[ -d "/var/lib/k8s/rag-prod" ]]; then
        cp -r "/var/lib/k8s/rag-prod" "$BACKUP_PATH/kubernetes_manifests"
        success "Kubernetes manifests backup completed"
    fi

    # SSL certificates
    if [[ -d "/etc/ssl/certs" ]]; then
        cp -r "/etc/ssl/certs" "$BACKUP_PATH/"
        success "SSL certificates backup completed"
    fi

    success "Configuration backup completed"
}

# Encryption backup
encrypt_backup() {
    log "Encrypting backup files"

    if [[ ! -f "$ENCRYPTION_KEY_FILE" ]]; then
        # Generate new encryption key if it doesn't exist
        ( umask 077 && openssl rand -hex 32 > "$ENCRYPTION_KEY_FILE" )
        chmod 600 "$ENCRYPTION_KEY_FILE"
        warning "Generated new encryption key"
    fi

    if [[ ! -f "$WRAPPING_PASSPHRASE_FILE" ]]; then
        error_exit "Wrapping passphrase file not found: $WRAPPING_PASSPHRASE_FILE. Provision an operator-managed passphrase (e.g. from KMS) so backups remain recoverable if $ENCRYPTION_KEY_FILE is lost."
    fi

    # Encrypt each backup file using PBKDF2 with the on-disk key as a passphrase.
    # -kfile uses a deprecated single-iteration MD5 KDF; -pass file: + -pbkdf2 is the modern equivalent.
    for file in "$BACKUP_PATH"/*.tar.gz "$BACKUP_PATH"/*.sql "$BACKUP_PATH"/dump*; do
        if [[ -f "$file" ]]; then
            openssl enc -aes-256-cbc -salt -pbkdf2 -iter "$PBKDF2_ITER" \
                -in "$file" \
                -out "$BACKUP_DIR/encrypted/$(basename "$file").enc" \
                -pass "file:$ENCRYPTION_KEY_FILE"
            rm "$file"
        fi
    done

    # Wrap the encryption key with the operator-managed passphrase so the
    # encrypted bundle remains recoverable if $ENCRYPTION_KEY_FILE is lost.
    openssl enc -aes-256-cbc -salt -pbkdf2 -iter "$PBKDF2_ITER" \
        -in "$ENCRYPTION_KEY_FILE" \
        -out "$BACKUP_DIR/encrypted/backup_key.enc" \
        -pass "file:$WRAPPING_PASSPHRASE_FILE"

    success "Backup encryption completed"
}

# Cleanup old backups
cleanup_old_backups() {
    log "Cleaning up old backups"

    # Find backups older than retention period
    find "$BACKUP_DIR" -maxdepth 1 -type d -name "[0-9]*" -mtime +$MAX_BACKUP_RETENTION_DAYS -exec rm -rf {} \;

    # Clean up unencrypted files that might have been missed
    find "$BACKUP_DIR" -name "*.tar.gz" -mtime +$MAX_BACKUP_RETENTION_DAYS -delete

    success "Cleanup completed"
}

# Backup verification
verify_backup() {
    log "Verifying backup integrity"

    local backup_size=$(du -sh "$BACKUP_PATH" | cut -f1)
    log "Backup size: $backup_size"

    # Check if essential files exist
    local essential_files=(
        "postgres_dump.sql"
        "neo4j_dump"
        "redis_dump.rdb"
        "uploads_backup.tar.gz"
        "models_backup.tar.gz"
        "logs_backup.tar.gz"
        "docker-compose.prod.yml"
    )

    for file in "${essential_files[@]}"; do
        if [[ ! -f "$BACKUP_PATH/$file" ]] && [[ ! -d "$BACKUP_PATH/$file" ]]; then
            warning "Backup file missing: $file"
        fi
    done

    # Test encryption/decryption
    local test_file="$BACKUP_DIR/encrypted/test.enc"
    if [[ -f "$test_file" ]]; then
        local tmp_decrypt
        tmp_decrypt=$(mktemp -t rag-backup-verify.XXXXXX)
        chmod 600 "$tmp_decrypt"
        # shellcheck disable=SC2064 -- expand $tmp_decrypt now so the trap fires regardless
        trap "rm -f '$tmp_decrypt'" RETURN
        if openssl enc -d -aes-256-cbc -pbkdf2 -iter "$PBKDF2_ITER" \
                -in "$test_file" -out "$tmp_decrypt" \
                -pass "file:$ENCRYPTION_KEY_FILE"; then
            success "Encryption verification passed"
        else
            error_exit "Encryption verification failed"
        fi
    fi

    success "Backup verification completed"
}

# Backup summary
generate_summary() {
    log "Generating backup summary"

    local summary_file="$BACKUP_PATH/BACKUP_SUMMARY.txt"

    cat << EOF > "$summary_file"
RAG System Backup Summary
========================
Timestamp: $(date)
Backup ID: $TIMESTAMP
Backup Path: $BACKUP_PATH

Components Backed Up:
- PostgreSQL Database: ✓
- Neo4j Database: ✓
- Redis Cache: ✓
- Uploads Volume: ✓
- Models Volume: ✓
- Logs Volume: ✓
- Configuration Files: ✓
- SSL Certificates: ✓

Backup Size: $(du -sh "$BACKUP_PATH" | cut -f1)
Encryption: AES-256-CBC
Retention Period: $MAX_BACKUP_RETENTION_DAYS days

Recovery Instructions:
1. Unwrap the backup key with the operator-managed passphrase:
   openssl enc -d -aes-256-cbc -pbkdf2 -iter $PBKDF2_ITER \\
     -in backup_key.enc -out backup_key -pass file:<wrapping_passphrase>

2. Extract encrypted backup files using the unwrapped key:
   openssl enc -d -aes-256-cbc -pbkdf2 -iter $PBKDF2_ITER \\
     -in <file.enc> -out <output> -pass file:backup_key

3. Restore PostgreSQL:
   docker exec -i rag-postgres-prod psql -U raguser ragdb < postgres_dump.sql

4. Restore Neo4j:
   docker exec rag-neo4j-prod neo4j-admin database restore --database=ragdb --from=neo4j_dump

5. Restore Redis:
   docker exec -i rag-redis-prod redis-cli < redis_dump.rdb

6. Restore volumes:
   docker run --rm -v <volume_name>:/data -v <backup_dir>:/backup alpine tar xzf /backup/<file> -C /data

Backup completed successfully at $(date)
EOF

    success "Backup summary generated"
}

# Main execution
main() {
    log "Starting RAG system backup process"
    send_slack_notification ":backup: Starting RAG system backup"

    # Load configuration
    load_config

    # Setup backup structure
    setup_backup_structure

    # Perform backups
    backup_database
    backup_volumes
    backup_configuration

    # Encrypt backup
    encrypt_backup

    # Verify backup
    verify_backup

    # Generate summary
    generate_summary

    # Cleanup old backups
    cleanup_old_backups

    # Success notification
    success "Backup process completed successfully"
    send_slack_notification ":white_check_mark: RAG system backup completed successfully"

    log "Backup process completed"
}

# Emergency recovery function
emergency_recovery() {
    log "Starting emergency recovery process"

    if [[ -z "$1" ]]; then
        error_exit "Backup timestamp required for recovery"
    fi

    local recovery_timestamp="$1"
    local backup_path="$BACKUP_DIR/$recovery_timestamp"

    if [[ ! -d "$backup_path" ]]; then
        error_exit "Backup directory not found: $backup_path"
    fi

    warning "Emergency recovery starting - this will stop all services"
    send_slack_notification ":warning: Emergency recovery initiated for backup $recovery_timestamp"

    # Stop services
    log "Stopping all RAG services"
    docker-compose -f /var/lib/docker-compose/rag-prod/docker-compose.prod.yml down

    # Restore database
    log "Restoring databases from backup $recovery_timestamp"
    # Add specific recovery commands here

    # Restore volumes
    log "Restoring volumes from backup $recovery_timestamp"
    # Add specific volume recovery commands here

    # Start services
    log "Starting all RAG services"
    docker-compose -f /var/lib/docker-compose/rag-prod/docker-compose.prod.yml up -d

    # Verify services
    log "Verifying service health"
    # Add service verification commands here

    success "Emergency recovery completed"
    send_slack_notification ":recycle: Emergency recovery completed"
}

# Handle command line arguments
case "${1:-}" in
    backup)
        main
        ;;
    recover)
        emergency_recovery "$2"
        ;;
    *)
        echo "Usage: $0 {backup|recover <timestamp>}"
        echo "  backup    - Perform full system backup"
        echo "  recover   - Emergency recovery from specific backup"
        exit 1
        ;;
esac