#!/bin/bash
# backup_db.sh - Backup harian database PostgreSQL (format .tar.gz + timestamp)
# Database berjalan di container "db", jadi pg_dump dijalankan lewat docker compose.

set -euo pipefail

APP_DIR="${APP_DIR:-/var/www/ecommerce}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/ecommerce}"
DB_NAME="${DB_NAME:-ecommerce_db}"
DB_USER="${DB_USER:-ecommerce_user}"

TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
TMP_DIR=$(mktemp -d)
SQL_FILE="$TMP_DIR/$DB_NAME-$TIMESTAMP.sql"
BACKUP_FILE="$BACKUP_DIR/$DB_NAME-backup-$TIMESTAMP.tar.gz"

trap 'rm -rf "$TMP_DIR"' EXIT
mkdir -p "$BACKUP_DIR"

echo "[$(date)] Memulai backup database $DB_NAME..."

if ! (cd "$APP_DIR" && docker compose exec -T db pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1); then
    echo "ERROR: container 'db' tidak berjalan. Jalankan: cd $APP_DIR && docker compose up -d db"
    exit 1
fi

(cd "$APP_DIR" && docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME") > "$SQL_FILE"

tar -czf "$BACKUP_FILE" -C "$TMP_DIR" .
echo "Backup berhasil: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"
