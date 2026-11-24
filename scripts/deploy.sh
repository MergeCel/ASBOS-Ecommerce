#!/bin/bash
# deploy.sh - dijalankan otomatis oleh GitHub Actions lewat SSH
set -euo pipefail

APP_DIR="/var/www/ecommerce"
HEALTH_URL="http://127.0.0.1:8080/"

cd "$APP_DIR"

echo "[$(date)] Menarik kode terbaru dari GitHub..."
git fetch origin main
git reset --hard origin/main

echo "Membangun ulang dan menjalankan container..."
docker compose up -d --build
docker image prune -f

echo "Cek kesehatan aplikasi..."
curl -fsS --retry 10 --retry-delay 2 --retry-connrefused "$HEALTH_URL"
echo
echo "[$(date)] Deploy selesai."
