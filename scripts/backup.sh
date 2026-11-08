#!/usr/bin/env bash
# Backup database + foto unggahan. Jalankan dari folder proyek: ./scripts/backup.sh
set -euo pipefail
DIR=${BACKUP_DIR:-./backups}
TS=$(date +%Y%m%d-%H%M%S)
DB=$(grep '^DB_NAME' backend/.env | cut -d= -f2 | tr -d '"')
mkdir -p "$DIR"
docker compose exec -T mongo mongodump --db "$DB" --archive --gzip > "$DIR/db-$TS.archive.gz"
docker compose exec -T backend tar czf - -C /data uploads > "$DIR/uploads-$TS.tar.gz"
find "$DIR" -type f -mtime +${KEEP_DAYS:-30} -delete
echo "Backup selesai: $DIR/db-$TS.archive.gz dan $DIR/uploads-$TS.tar.gz"
