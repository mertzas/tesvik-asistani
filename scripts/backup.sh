#!/bin/bash

# Database Backup Script
# Run daily via cron: 0 2 * * * /path/to/backup.sh

set -e

# Configuration
BACKUP_DIR="${BACKUP_DIR:-./backups}"
DB_NAME="${DB_NAME:-tesvik_saas}"
DB_USER="${DB_USER:-tesvik_user}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.sql.gz"

# Create backup directory
mkdir -p "$BACKUP_DIR"

echo "🔄 Starting database backup..."

# Backup PostgreSQL database
pg_dump -U "$DB_USER" -h "$DB_HOST" -p "$DB_PORT" "$DB_NAME" | gzip > "$BACKUP_FILE"

# Check backup success
if [ $? -eq 0 ]; then
    echo "✅ Backup completed: $BACKUP_FILE"
    ls -lh "$BACKUP_FILE"
else
    echo "❌ Backup failed!"
    exit 1
fi

# Upload to S3 (optional)
if [ ! -z "$AWS_S3_BUCKET" ]; then
    echo "📤 Uploading to S3..."
    aws s3 cp "$BACKUP_FILE" "s3://$AWS_S3_BUCKET/backups/" --region "$AWS_S3_REGION"
    echo "✅ S3 upload completed"
fi

# Cleanup old backups
echo "🧹 Cleaning up old backups (older than $RETENTION_DAYS days)..."
find "$BACKUP_DIR" -name "${DB_NAME}_*.sql.gz" -mtime "+$RETENTION_DAYS" -delete

# Verify backup integrity
echo "🔍 Verifying backup integrity..."
gunzip -t "$BACKUP_FILE" && echo "✅ Backup integrity verified"

echo "✅ Backup process completed successfully"
