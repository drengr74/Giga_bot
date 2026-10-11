#!/usr/bin/env bash
# Ежечасное обновление контейнера giga-bot из Docker Hub.
# Контейнер пересоздаётся только при появлении новой версии образа.

set -euo pipefail

IMAGE="bjjmachine/giga-bot:latest"
CONTAINER="giga-bot"
ENV_FILE="/root/.env"
CA_FILE="/root/russiantrustedca.pem"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# Не допускаем одновременного запуска двух копий скрипта
exec 9>/var/lock/update_container.lock
flock -n 9 || { log "Скрипт уже выполняется, выходим"; exit 0; }

# Образ скачивается до остановки контейнера: если Docker Hub недоступен,
# старая версия бота продолжает работать
log "Проверяем обновления $IMAGE"
docker pull --quiet "$IMAGE" >/dev/null

LATEST_ID=$(docker image inspect --format '{{.Id}}' "$IMAGE")
CURRENT_ID=$(docker inspect --format '{{.Image}}' "$CONTAINER" 2>/dev/null || true)
RUNNING=$(docker inspect --format '{{.State.Running}}' "$CONTAINER" 2>/dev/null || echo false)

if [[ "$LATEST_ID" == "$CURRENT_ID" && "$RUNNING" == "true" ]]; then
    log "Обновлений нет, контейнер работает"
    exit 0
fi

log "Новая версия образа или контейнер не запущен — перезапускаем $CONTAINER"

# 1. Останавливаем текущий контейнер
docker stop "$CONTAINER" >/dev/null 2>&1 || true

# 2. Удаляем его
docker rm "$CONTAINER" >/dev/null 2>&1 || true

# 3. Запускаем новый контейнер из свежего образа
docker run -d --name "$CONTAINER" --restart unless-stopped \
    --env-file "$ENV_FILE" \
    -v "$CA_FILE:/certs/russiantrustedca.pem:ro" \
    -e GIGACHAT_CA_BUNDLE=/certs/russiantrustedca.pem \
    "$IMAGE" >/dev/null

# Удаляем старые слои, которые больше ни к чему не привязаны
docker image prune -f >/dev/null

log "Готово: $CONTAINER запущен на ${LATEST_ID:7:12}"
