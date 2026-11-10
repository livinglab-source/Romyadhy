#!/usr/bin/env bash
# Dump the livinglab database, gzip it, keep the last 7 days.
# Cron: 15 2 * * * /opt/livinglab/Romyadhy/scripts/backup_db.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/livinglab}"
KEEP_DAYS="${KEEP_DAYS:-7}"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

: "${DB_NAME:?DB_NAME is not set}"
: "${DB_USER:?DB_USER is not set}"
: "${DB_PASSWORD:?DB_PASSWORD is not set}"

mkdir -p "$BACKUP_DIR"
STAMP="$(date +%F)"
OUT="$BACKUP_DIR/${DB_NAME}-${STAMP}.sql.gz"

mysqldump \
  --host="${DB_HOST:-127.0.0.1}" \
  --port="${DB_PORT:-3306}" \
  --user="$DB_USER" \
  --password="$DB_PASSWORD" \
  --single-transaction \
  --quick \
  --no-tablespaces \
  "$DB_NAME" | gzip > "$OUT"

echo "backup written: $OUT"

# Rotate: delete dumps older than KEEP_DAYS
find "$BACKUP_DIR" -name "${DB_NAME}-*.sql.gz" -type f -mtime "+$KEEP_DAYS" -print -delete

# Quick sanity check
if [[ ! -s "$OUT" ]]; then
  echo "error: backup file is empty" >&2
  exit 1
fi