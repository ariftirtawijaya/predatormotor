#!/usr/bin/env bash
# Restore: ./scripts/restore.sh backups/db-XXXX.archive.gz backups/uploads-XXXX.tar.gz
set -euo pipefail
DB_FILE=$1
UP_FILE=${2:-}
DB=$(grep '^DB_NAME' backend/.env | cut -d= -f2 | tr -d '"')
read -r -p "Data database '$DB' saat ini akan DITIMPA. Ketik YA untuk lanjut: " ok
[ "$ok" = "YA" ] || exit 1
# Replica set harus PRIMARY sebelum restore (lihat docker-compose: mongo --replSet rs0)
docker compose exec -T mongo mongosh --quiet --eval "quit(db.hello().isWritablePrimary ? 0 : 1)" || { echo "MongoDB belum PRIMARY. Tunggu 'docker compose ps' sehat lalu ulangi."; exit 1; }
docker compose exec -T mongo mongorestore --drop --nsInclude "$DB.*" --archive --gzip < "$DB_FILE"
if [ -n "$UP_FILE" ]; then
  docker compose exec -T backend sh -c 'rm -rf /data/uploads/* && tar xzf - -C /data' < "$UP_FILE"
fi
echo "Restore selesai."
