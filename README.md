# Giga_bot

Telegram-бот с двумя режимами работы:

- **🤖 Ассистент (GigaChat)** — личный помощник: задачи, идеи, объяснения, планирование.
- **📺 Сериалы (Yandex AI)** — агент по подбору сериалов на вечер под настроение, жанр и свободное время.

Бот хранит историю диалога отдельно для каждого чата и режима (последние 20 сообщений), конвертирует Markdown из ответов моделей в HTML-разметку Telegram и отправляет логи в [Better Stack Telemetry](https://betterstack.com/telemetry) (бывший Logtail).

## Команды бота

| Команда | Действие |
| --- | --- |
| `/start`, `/help` | Приветствие и выбор режима |
| `/gigachat` | Включить ассистента GigaChat |
| `/series` | Включить подбор сериалов |
| `/mode` | Показать активный режим |
| `/clear` | Очистить историю текущего режима |

## Структура проекта

```
giga_bot.py       # Telegram-бот: режимы, история, обработчики команд
get_token.py      # Получение access token GigaChat
yandex_ai.py      # Запросы к YandexGPT через Yandex AI Studio SDK
requirements.txt  # Python-зависимости
Dockerfile        # Сборка образа
.env.example      # Шаблон переменных окружения
```

## Настройка

Скопируйте шаблон и заполните ключи:

```bash
cp .env.example .env
```

| Переменная | Обязательная | Описание |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | да | Токен бота от [@BotFather](https://t.me/BotFather) |
| `GIGACHAT_CREDENTIALS` | да | Ключ авторизации GigaChat API |
| `GIGACHAT_CA_BUNDLE` | да | Путь к корневому сертификату Минцифры (`russiantrustedca.pem`) |
| `GIGACHAT_MODEL` | нет | Модель GigaChat, по умолчанию `GigaChat-2` |
| `YANDEX_FOLDER_ID` | да | ID каталога в Yandex Cloud |
| `YANDEX_API_KEY` | да | API-ключ сервисного аккаунта Yandex Cloud |
| `YANDEX_MODEL` | нет | Модель YandexGPT, по умолчанию `yandexgpt-lite` |
| `YANDEX_TEMPERATURE` | нет | Температура генерации, по умолчанию `0.6` |
| `BETTERSTACK_SOURCE_TOKEN` | нет | Source token источника в Better Stack |
| `BETTERSTACK_INGESTING_HOST` | нет | Ingesting host источника в Better Stack |

Если переменные Better Stack не заданы, бот работает как обычно и пишет логи только в консоль.

## Локальный запуск

Требуется Python 3.11+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python giga_bot.py
```

## Запуск в Docker

Образ основан на `python:3.11-slim` и запускает бота от непривилегированного пользователя `appuser`. Файл `.env` в образ не попадает — ключи передаются при запуске.

```bash
docker build -t giga-bot .
docker run -d --name giga-bot --restart unless-stopped --env-file .env giga-bot
```

Сертификат GigaChat подключается в контейнер как том, а путь к нему переопределяется переменной:

```bash
docker run -d --name giga-bot --restart unless-stopped \
  --env-file .env \
  -v /path/to/russiantrustedca.pem:/certs/russiantrustedca.pem:ro \
  -e GIGACHAT_CA_BUNDLE=/certs/russiantrustedca.pem \
  giga-bot
```

Образ опубликован в Docker Hub: [`bjjmachine/giga-bot`](https://hub.docker.com/r/bjjmachine/giga-bot).

## Деплой

Новая версия собирается под `linux/amd64` и отправляется в Docker Hub:

```bash
docker buildx build --platform linux/amd64 \
  -t bjjmachine/giga-bot:<версия> -t bjjmachine/giga-bot:latest --push .
```

На сервере раз в час по cron запускается скрипт `/root/update_container.sh`. Он скачивает `bjjmachine/giga-bot:latest` и пересоздаёт контейнер только при появлении новой версии образа, поэтому бот обновляется автоматически в течение часа после публикации.

```bash
tail -n 20 /var/log/update_container.log   # журнал обновлений
docker logs -f giga-bot                     # логи бота
```

## Логи

Логи бота, библиотеки telebot и HTTP-запросов отправляются в Better Stack и доступны в разделе **Live tail**. Каждый ответ бота сопровождается структурированными полями для анализа:

| Поле | Описание |
| --- | --- |
| `mode` | Режим: `gigachat` или `yandex` |
| `chat_id` | ID чата Telegram |
| `duration_ms` | Время получения ответа от модели |
| `request_chars` | Длина запроса пользователя |
| `answer_chars` | Длина ответа модели |

Тексты сообщений пользователей в Better Stack не отправляются.
