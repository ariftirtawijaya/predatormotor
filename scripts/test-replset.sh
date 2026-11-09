#!/usr/bin/env bash
# Uji integrasi transaksi (impor Excel atomik, dll.) terhadap MongoDB replica set SUNGGUHAN di container sementara.
# Data aplikasi / volume mongo_data tidak disentuh. Jalankan dari folder proyek: ./scripts/test-replset.sh
# Opsional: PYTEST_ARGS="-k import" ./scripts/test-replset.sh
set -euo pipefail
NET="predator-test-net-$$"
MONGO="predator-test-mongo-$$"
cleanup() { docker rm -f "$MONGO" >/dev/null 2>&1 || true; docker network rm "$NET" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker network create "$NET" >/dev/null
docker run -d --name "$MONGO" --network "$NET" mongo:7 --replSet rs0 --bind_ip_all >/dev/null
echo "Menunggu replica set siap…"
for _ in $(seq 1 30); do
  docker exec "$MONGO" mongosh --quiet --eval "try { rs.status() } catch (e) { rs.initiate({_id: 'rs0', members: [{_id: 0, host: '$MONGO:27017'}]}) }; quit(db.hello().isWritablePrimary ? 0 : 1)" >/dev/null 2>&1 && break
  sleep 2
done
docker exec "$MONGO" mongosh --quiet --eval "quit(db.hello().isWritablePrimary ? 0 : 1)" || { echo "Replica set gagal siap"; exit 1; }
docker run --rm --network "$NET" -v "$PWD/backend:/src:ro" -e TEST_MONGO_URL="mongodb://$MONGO:27017/?replicaSet=rs0" python:3.11-slim \
  sh -c "cp -r /src /app && rm -f /app/.env && cd /app && pip install -q -r requirements-dev.txt && python -m pytest tests -q -rs -p no:cacheprovider ${PYTEST_ARGS:-}"
echo "Selesai. Pastikan tidak ada tes impor yang 'SKIPPED' karena replica set."
