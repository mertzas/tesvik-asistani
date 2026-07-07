#!/bin/bash

# Database Restore Script
# Usage: ./restore.sh backup_file.sql.gz

set -e

if [ -z "$1" ]; then
    echo "Usage: ./restore.sh <backup_file.sql.gz>"
    exit 1
fi

BACKUP_FILE="$1"
DB_NAME="${DB_NAME:-tesvik_saas}"
DB_USER="${DB_USER:-tesvik_user}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "⚠️  WARNING: This will overwrite the current database!"
read -p "Continue? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "Cancelled"
    exit 0
fi

echo "🔄 Starting database restore..."

# Drop existing database (optional, uncomment to enable)
# psql -U "$DB_USER" -h "$DB_HOST" -c "DROP DATABASE IF EXISTS $DB_NAME;"
# psql -U "$DB_USER" -h "$DB_HOST" -c "CREATE DATABASE $DB_NAME;"

# Restore backup
gunzip -c "$BACKUP_FILE" | psql -U "$DB_USER" -h "$DB_HOST" -p "$DB_PORT" "$DB_NAME"

if [ $? -eq 0 ]; then
    echo "✅ Restore completed successfully"
else
    echo "❌ Restore failed!"
    exit 1
fi

echo "✅ Database restore process completed"
