#!/bin/bash
# backup_db.sh - Backup harian database PostgreSQL (format .tar.gz + timestamp)

DB_NAME="ecommerce_db"
DB_USER="ecommerce_user"
DB_HOST="localhost"
BACKUP_DIR="/var/backups/ecommerce"

TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
TMP_DIR=$(mktemp -d)
SQL_FILE="$TMP_DIR/$DB_NAME-$TIMESTAMP.sql"
BACKUP_FILE="$BACKUP_DIR/$DB_NAME-backup-$TIMESTAMP.tar.gz"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Memulai backup database $DB_NAME..."

# -w: jangan minta password (pakai ~/.pgpass), aman untuk cron
pg_dump -h "$DB_HOST" -U "$DB_USER" -w -f "$SQL_FILE" "$DB_NAME"
if [[ $? -ne 0 ]]; then
    echo "ERROR: pg_dump gagal."
    rm -rf "$TMP_DIR"
    exit 1
fi

tar -czf "$BACKUP_FILE" -C "$TMP_DIR" .
if [[ $? -eq 0 ]]; then
    echo "Backup berhasil: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"
else
    echo "ERROR: proses kompresi gagal."
    rm -rf "$TMP_DIR"
    exit 1
fi

rm -rf "$TMP_DIR"

exit 0
