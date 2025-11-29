#!/bin/bash

# Database Backup Script for PostgreSQL
# This script creates automated backups of the PostgreSQL database

set -euo pipefail

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/backups/postgresql}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-multimodal_rag}"
DB_USER="${DB_USER:-postgres}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_backup_${TIMESTAMP}.sql"
COMPRESSED_FILE="${BACKUP_FILE}.gz"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Error handling
error_exit() {
    log "ERROR: $1"
    exit 1
}

# Check if required environment variables are set
check_requirements() {
    log "Checking requirements..."

    if [[ -z "${DB_PASSWORD:-}" ]]; then
        error_exit "DB_PASSWORD environment variable is required"
    fi

    # Check if pg_dump is available
    if ! command -v pg_dump &> /dev/null; then
        error_exit "pg_dump is not installed or not in PATH"
    fi

    # Create backup directory if it doesn't exist
    mkdir -p "${BACKUP_DIR}" || error_exit "Failed to create backup directory: ${BACKUP_DIR}"

    log "Requirements check completed"
}

# Test database connection
test_connection() {
    log "Testing database connection..."

    if PGPASSWORD="${DB_PASSWORD}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -c "SELECT 1;" &> /dev/null; then
        log "Database connection successful"
    else
        error_exit "Failed to connect to database"
    fi
}

# Create backup
create_backup() {
    log "Starting database backup..."

    # Create backup using pg_dump
    export PGPASSWORD="${DB_PASSWORD}"

    if pg_dump -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" \
        --no-owner --no-privileges \
        --verbose \
        --format=custom \
        --file="${BACKUP_FILE}" 2>&1 | while IFS= read -r line; do
            log "pg_dump: $line"
        done; then

        log "Database backup created successfully: ${BACKUP_FILE}"
    else
        error_exit "Failed to create database backup"
    fi

    # Compress the backup
    log "Compressing backup..."
    gzip "${BACKUP_FILE}" || error_exit "Failed to compress backup"

    log "Backup compressed: ${COMPRESSED_FILE}"

    # Get backup size
    BACKUP_SIZE=$(du -h "${COMPRESSED_FILE}" | cut -f1)
    log "Backup size: ${BACKUP_SIZE}"
}

# Verify backup
verify_backup() {
    log "Verifying backup integrity..."

    if pg_restore --list "${COMPRESSED_FILE}" &> /dev/null; then
        log "Backup verification successful"
    else
        error_exit "Backup verification failed"
    fi
}

# Clean old backups
cleanup_old_backups() {
    log "Cleaning up backups older than ${RETENTION_DAYS} days..."

    # Find and remove old backup files
    DELETED_COUNT=$(find "${BACKUP_DIR}" -name "${DB_NAME}_backup_*.sql.gz" -type f -mtime +${RETENTION_DAYS} -delete -print | wc -l)

    if [[ ${DELETED_COUNT} -gt 0 ]]; then
        log "Deleted ${DELETED_COUNT} old backup files"
    else
        log "No old backup files to delete"
    fi
}

# Create backup metadata
create_metadata() {
    log "Creating backup metadata..."

    METADATA_FILE="${BACKUP_DIR}/${DB_NAME}_backup_${TIMESTAMP}_metadata.json"

    cat > "${METADATA_FILE}" << EOF
{
    "backup_file": "$(basename "${COMPRESSED_FILE}")",
    "database_name": "${DB_NAME}",
    "backup_timestamp": "$(date -Iseconds)",
    "backup_size": "$(du -b "${COMPRESSED_FILE}" | cut -f1)",
    "backup_size_human": "$(du -h "${COMPRESSED_FILE}" | cut -f1)",
    "hostname": "$(hostname)",
    "script_version": "1.0",
    "retention_days": ${RETENTION_DAYS}
}
EOF

    log "Metadata created: ${METADATA_FILE}"
}

# Upload to cloud storage (optional)
upload_to_cloud() {
    if [[ -n "${CLOUD_STORAGE_ENABLED:-}" && "${CLOUD_STORAGE_ENABLED}" == "true" ]]; then
        log "Uploading backup to cloud storage..."

        case "${CLOUD_STORAGE_PROVIDER:-}" in
            "aws")
                upload_to_s3
                ;;
            "gcp")
                upload_to_gcs
                ;;
            "azure")
                upload_to_azure
                ;;
            *)
                log "Unknown cloud storage provider: ${CLOUD_STORAGE_PROVIDER}"
                ;;
        esac
    fi
}

upload_to_s3() {
    if [[ -n "${AWS_S3_BUCKET:-}" && -n "${AWS_ACCESS_KEY_ID:-}" && -n "${AWS_SECRET_ACCESS_KEY:-}" ]]; then
        log "Uploading to S3 bucket: ${AWS_S3_BUCKET}"

        # Upload backup file
        aws s3 cp "${COMPRESSED_FILE}" "s3://${AWS_S3_BUCKET}/database-backups/" || log "WARNING: Failed to upload backup to S3"

        # Upload metadata
        aws s3 cp "${METADATA_FILE}" "s3://${AWS_S3_BUCKET}/database-backups/" || log "WARNING: Failed to upload metadata to S3"

        log "S3 upload completed"
    else
        log "S3 configuration not complete, skipping upload"
    fi
}

upload_to_gcs() {
    if [[ -n "${GCS_BUCKET:-}" && -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" ]]; then
        log "Uploading to Google Cloud Storage bucket: ${GCS_BUCKET}"

        # Upload backup file
        gsutil cp "${COMPRESSED_FILE}" "gs://${GCS_BUCKET}/database-backups/" || log "WARNING: Failed to upload backup to GCS"

        # Upload metadata
        gsutil cp "${METADATA_FILE}" "gs://${GCS_BUCKET}/database-backups/" || log "WARNING: Failed to upload metadata to GCS"

        log "GCS upload completed"
    else
        log "GCS configuration not complete, skipping upload"
    fi
}

upload_to_azure() {
    if [[ -n "${AZURE_STORAGE_ACCOUNT:-}" && -n "${AZURE_STORAGE_KEY:-}" && -n "${AZURE_CONTAINER:-}" ]]; then
        log "Uploading to Azure Blob Storage container: ${AZURE_CONTAINER}"

        # Upload backup file
        az storage blob upload --file "${COMPRESSED_FILE}" --name "database-backups/$(basename "${COMPRESSED_FILE}")" --container-name "${AZURE_CONTAINER}" || log "WARNING: Failed to upload backup to Azure"

        # Upload metadata
        az storage blob upload --file "${METADATA_FILE}" --name "database-backups/$(basename "${METADATA_FILE}")" --container-name "${AZURE_CONTAINER}" || log "WARNING: Failed to upload metadata to Azure"

        log "Azure upload completed"
    else
        log "Azure configuration not complete, skipping upload"
    fi
}

# Send notification (optional)
send_notification() {
    if [[ -n "${NOTIFICATION_ENABLED:-}" && "${NOTIFICATION_ENABLED}" == "true" ]]; then
        log "Sending backup notification..."

        case "${NOTIFICATION_TYPE:-}" in
            "slack")
                send_slack_notification
                ;;
            "email")
                send_email_notification
                ;;
            *)
                log "Unknown notification type: ${NOTIFICATION_TYPE}"
                ;;
        esac
    fi
}

send_slack_notification() {
    if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
        local message="✅ Database backup completed successfully
        • Database: ${DB_NAME}
        • File: $(basename "${COMPRESSED_FILE}")
        • Size: $(du -h "${COMPRESSED_FILE}" | cut -f1)
        • Timestamp: $(date -Iseconds)"

        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"${message}\"}" \
            "${SLACK_WEBHOOK_URL}" || log "WARNING: Failed to send Slack notification"
    fi
}

send_email_notification() {
    if command -v mail &> /dev/null && [[ -n "${NOTIFICATION_EMAIL:-}" ]]; then
        local subject="Database Backup Completed - ${DB_NAME}"
        local body="Database backup completed successfully.

        Database: ${DB_NAME}
        Backup File: $(basename "${COMPRESSED_FILE}")
        Size: $(du -h "${COMPRESSED_FILE}" | cut -f1)
        Timestamp: $(date -Iseconds)
        Hostname: $(hostname)

        This is an automated message from the backup system."

        echo "${body}" | mail -s "${subject}" "${NOTIFICATION_EMAIL}" || log "WARNING: Failed to send email notification"
    fi
}

# Main execution
main() {
    log "Starting database backup process..."

    check_requirements
    test_connection
    create_backup
    verify_backup
    create_metadata
    cleanup_old_backups
    upload_to_cloud
    send_notification

    log "Database backup process completed successfully!"
    log "Backup file: ${COMPRESSED_FILE}"

    # Create a symlink to the latest backup
    LATEST_LINK="${BACKUP_DIR}/${DB_NAME}_latest.sql.gz"
    ln -sf "$(basename "${COMPRESSED_FILE}")" "${LATEST_LINK}"
    log "Latest backup symlink updated: ${LATEST_LINK}"
}

# Handle signals gracefully
trap 'log "Backup process interrupted"; exit 1' INT TERM

# Run main function
main "$@"