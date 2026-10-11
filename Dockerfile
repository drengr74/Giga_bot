# Базовый образ: облегчённая версия Python 3.11 на Debian (без лишних пакетов)
FROM python:3.11-slim

# Переменные окружения:
# - PYTHONDONTWRITEBYTECODE — не создавать .pyc файлы (__pycache__) внутри контейнера
# - PYTHONUNBUFFERED — выводить логи сразу, без буферизации (важно для docker logs)
# - PIP_NO_CACHE_DIR — не хранить кэш pip, чтобы образ был меньше
# - PIP_DISABLE_PIP_VERSION_CHECK — не проверять обновления pip при установке
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Рабочая директория: все следующие команды выполняются в /app
WORKDIR /app

# Сначала копируем только список зависимостей.
# Пока requirements.txt не меняется, Docker берёт этот слой и слой установки из кэша,
# и при правке кода зависимости не переустанавливаются
COPY requirements.txt .

# Устанавливаем зависимости проекта
RUN pip install --no-cache-dir -r requirements.txt

# Создаём системного пользователя без root-прав и без домашней директории
RUN useradd --system --no-create-home --shell /usr/sbin/nologin appuser

# Копируем остальной код проекта (исключения задаются в .dockerignore)
# и сразу назначаем владельцем appuser
COPY --chown=appuser:appuser . .

# Переключаемся на непривилегированного пользователя: дальше процесс работает не от root
USER appuser

# Команда запуска контейнера: стартуем Telegram-бота
CMD ["python", "giga_bot.py"]
