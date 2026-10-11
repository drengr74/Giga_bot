#!/usr/bin/env bash
# Ежедневный бэкап базы Dokploy и данных n8n в /root/backups.
# Хранятся последние KEEP_DAYS дней.

set -euo pipefail

BACKUP_DIR="/root/backups"
KEEP_DAYS=14
N8N_VOLUME="n8nmain-n8n-u46wx0_n8n_data"
STAMP=$(date +%F_%H%M)

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

exec 9>/var/lock/backup.lock
flock -n 9 || { log "Бэкап уже выполняется, выходим"; exit 0; }

mkdir -p "$BACKUP_DIR/dokploy" "$BACKUP_DIR/n8n"
chmod 700 "$BACKUP_DIR"

# --- Dokploy: дамп PostgreSQL в сжатом формате pg_dump (-Fc) ---
PG=$(docker ps -q --filter label=com.docker.swarm.service.name=dokploy-postgres | head -n1)
[[ -n "$PG" ]] || { log "ОШИБКА: контейнер dokploy-postgres не запущен"; exit 1; }
DOKPLOY_FILE="$BACKUP_DIR/dokploy/dokploy_$STAMP.dump"
docker exec "$PG" pg_dump -U dokploy -d dokploy -Fc > "$DOKPLOY_FILE.tmp"
mv "$DOKPLOY_FILE.tmp" "$DOKPLOY_FILE"
log "Dokploy: $(du -h "$DOKPLOY_FILE" | cut -f1) -> $DOKPLOY_FILE"

# --- n8n: согласованная копия SQLite через backup API + остальные файлы тома ---
# Простое копирование database.sqlite при работающем n8n (режим WAL) даёт битую копию
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
chown 1000:1000 "$TMP"

docker run --rm -u 1000:1000 \
    -v "$N8N_VOLUME:/data" -v "$TMP:/out" \
    python:3.11-slim python -c '
import sqlite3
src = sqlite3.connect("/data/database.sqlite")
dst = sqlite3.connect("/out/database.sqlite")
src.backup(dst)
ok = dst.execute("pragma integrity_check").fetchone()[0]
dst.close(); src.close()
assert ok == "ok", ok
'

# config содержит ключ шифрования: без него сохранённые credentials не расшифровать
N8N_DATA="/var/lib/docker/volumes/$N8N_VOLUME/_data"
tar -C "$N8N_DATA" --exclude='database.sqlite*' --exclude='crash.journal' -cf "$TMP/files.tar" .

N8N_FILE="$BACKUP_DIR/n8n/n8n_$STAMP.tar.gz"
tar -C "$TMP" -czf "$N8N_FILE.tmp" database.sqlite files.tar
mv "$N8N_FILE.tmp" "$N8N_FILE"
log "n8n: $(du -h "$N8N_FILE" | cut -f1) -> $N8N_FILE"

# --- Удаляем бэкапы старше KEEP_DAYS дней ---
find "$BACKUP_DIR" -type f \( -name '*.dump' -o -name '*.tar.gz' \) -mtime +"$KEEP_DAYS" -print -delete \
    | sed 's/^/Удалён старый бэкап: /' || true

log "Бэкап завершён"
