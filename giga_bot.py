"""Telegram-бот с выбором режима:

- GigaChat — личный ассистент и помощник
- Yandex AI — агент по подбору сериалов на вечер

Модули: get_token.py, yandex_ai.py
Токен Telegram — TELEGRAM_BOT_TOKEN в .env
"""

from __future__ import annotations

import html
import logging
import os
import re
import time
from collections import defaultdict
from pathlib import Path

import telebot
from dotenv import load_dotenv
from gigachat import GigaChat
from logtail import LogtailHandler
from telebot.types import KeyboardButton, Message, ReplyKeyboardMarkup

from get_token import BASE_URL, get_token
from yandex_ai import ask_yandex

load_dotenv(Path(__file__).resolve().parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("giga_bot")

BETTERSTACK_SOURCE_TOKEN = os.getenv("BETTERSTACK_SOURCE_TOKEN")
BETTERSTACK_INGESTING_HOST = os.getenv("BETTERSTACK_INGESTING_HOST")
if BETTERSTACK_SOURCE_TOKEN and BETTERSTACK_INGESTING_HOST:
    host = BETTERSTACK_INGESTING_HOST
    if not host.startswith("http"):
        host = f"https://{host}"
    # Корневой логгер: в Better Stack уходят и логи бота, и логи telebot/httpx
    logging.getLogger().addHandler(
        LogtailHandler(source_token=BETTERSTACK_SOURCE_TOKEN, host=host)
    )
    log.info("Логи отправляются в Better Stack (%s)", host)
else:
    log.warning("BETTERSTACK_SOURCE_TOKEN/BETTERSTACK_INGESTING_HOST не заданы — логи только в консоль")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise SystemExit("Задайте TELEGRAM_BOT_TOKEN в .env")

GIGACHAT_MODEL = os.getenv("GIGACHAT_MODEL", "GigaChat-2")
GIGACHAT_CA_BUNDLE = os.getenv("GIGACHAT_CA_BUNDLE")
MAX_HISTORY = 20
TOKEN_REFRESH_MARGIN = 60

MODE_GIGA = "gigachat"
MODE_YANDEX = "yandex"

BTN_GIGA = "🤖 Ассистент (GigaChat)"
BTN_YANDEX = "📺 Сериалы (Yandex)"

GIGA_SYSTEM = (
    "Ты личный ассистент и умный помощник в Telegram. "
    "Помогай с задачами, идеями, объяснениями, планированием и повседневными вопросами. "
    "Отвечай дружелюбно, кратко и по делу, на языке пользователя. "
    "Если запрос неясен — задай один уточняющий вопрос. "
    "Для выделения используй простой Markdown: **жирный**, *курсив*, `код`. "
    "Не используй HTML-теги."
)

YANDEX_SYSTEM = (
    "Ты специализированный агент по подбору сериалов на вечер. "
    "Твоя единственная задача — рекомендовать сериалы под настроение, жанр, "
    "доступное время и предпочтения пользователя. "
    "Всегда предлагай 3–5 вариантов: название, год (если известен), жанр, "
    "кратко почему подходит на вечер, примерная длительность сезона/серии. "
    "Уточняй: жанр, настроение, платформу/язык, сколько времени есть. "
    "Не уходи в темы вне кино и сериалов — мягко возвращай разговор к подбору. "
    "Для выделения используй простой Markdown: **жирный**, *курсив*. "
    "Не используй HTML-теги."
)

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, parse_mode="HTML")

# chat_id -> режим
_mode: dict[int, str] = {}
# (chat_id, mode) -> история сообщений
_history: dict[tuple[int, str], list[dict]] = defaultdict(list)

_access_token: str | None = None
_token_expires_at: float = 0.0


def _mode_keyboard() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton(BTN_GIGA), KeyboardButton(BTN_YANDEX))
    return kb


def _ensure_token() -> str:
    global _access_token, _token_expires_at

    if _access_token and time.time() < _token_expires_at - TOKEN_REFRESH_MARGIN:
        return _access_token

    token, expires_in, expires_human = get_token()
    _access_token = token
    _token_expires_at = time.time() + expires_in
    log.info("GigaChat token обновлён, живёт ещё %s", expires_human)
    return _access_token


def _extract_giga_text(response) -> str:
    if not response.messages:
        return "Не удалось получить ответ."

    parts: list[str] = []
    for msg in response.messages:
        content = msg.content
        if isinstance(content, str):
            parts.append(content)
            continue
        if isinstance(content, list):
            for part in content:
                text = getattr(part, "text", None)
                if text:
                    parts.append(text)
    return "\n".join(parts).strip() or "Пустой ответ от модели."


def _trim(history: list[dict]) -> None:
    if len(history) > MAX_HISTORY:
        del history[:-MAX_HISTORY]


def ask_gigachat(chat_id: int, user_text: str) -> str:
    key = (chat_id, MODE_GIGA)
    history = _history[key]
    history.append({"role": "user", "content": user_text})
    _trim(history)

    payload = {
        "model": GIGACHAT_MODEL,
        "messages": [
            {"role": "system", "content": GIGA_SYSTEM},
            *history,
        ],
    }

    kwargs: dict = {
        "base_url": BASE_URL,
        "access_token": _ensure_token(),
        "model": GIGACHAT_MODEL,
    }
    if GIGACHAT_CA_BUNDLE:
        kwargs["ca_bundle_file"] = GIGACHAT_CA_BUNDLE

    with GigaChat(**kwargs) as giga:
        response = giga.chat.create(payload)

    answer = _extract_giga_text(response)
    history.append({"role": "assistant", "content": answer})
    return answer


def ask_series_agent(chat_id: int, user_text: str) -> str:
    key = (chat_id, MODE_YANDEX)
    history = _history[key]
    history.append({"role": "user", "text": user_text})
    _trim(history)

    messages = [
        {"role": "system", "text": YANDEX_SYSTEM},
        *history,
    ]
    answer = ask_yandex(messages)
    history.append({"role": "assistant", "text": answer})
    return answer


def _set_mode(chat_id: int, mode: str) -> str:
    _mode[chat_id] = mode
    if mode == MODE_GIGA:
        return (
            "Режим: <b>личный ассистент (GigaChat)</b>\n"
            "Спрашивай что угодно — помогу с задачами, идеями и вопросами."
        )
    return (
        "Режим: <b>подбор сериалов (Yandex AI)</b>\n"
        "Напиши настроение, жанр или сколько у тебя времени — подберу сериалы на вечер."
    )


def _clip(text: str, limit: int = 4000) -> str:
    if len(text) > limit:
        return text[: limit - 10] + "…"
    return text


def _md_to_telegram_html(text: str) -> str:
    """Конвертирует типичный Markdown от LLM в HTML Telegram."""
    text = text.replace("\r\n", "\n")
    placeholders: list[str] = []

    def _hold(html_chunk: str) -> str:
        placeholders.append(html_chunk)
        return f"\x00PH{len(placeholders) - 1}\x00"

    # fenced code blocks
    text = re.sub(
        r"```(?:\w+)?\n?([\s\S]*?)```",
        lambda m: _hold(f"<pre>{html.escape(m.group(1).rstrip())}</pre>"),
        text,
    )
    # inline code
    text = re.sub(
        r"`([^`\n]+)`",
        lambda m: _hold(f"<code>{html.escape(m.group(1))}</code>"),
        text,
    )

    text = html.escape(text)

    # headings -> bold line
    text = re.sub(
        r"(?m)^#{1,6}\s+(.+)$",
        lambda m: f"<b>{m.group(1).strip()}</b>",
        text,
    )
    # bold / italic (after escape, * and _ remain)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text, flags=re.DOTALL)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text, flags=re.DOTALL)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text, flags=re.DOTALL)
    text = re.sub(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)", r"<i>\1</i>", text, flags=re.DOTALL)

    for i, chunk in enumerate(placeholders):
        text = text.replace(f"\x00PH{i}\x00", chunk)
    return text


def _reply(message: Message, text: str) -> None:
    """Отправляет ответ: Markdown→HTML, при ошибке разметки — как plain text."""
    body = _clip(text)
    html_body = _clip(_md_to_telegram_html(body))
    try:
        bot.reply_to(message, html_body, parse_mode="HTML")
    except Exception:
        log.warning("HTML-разметка не принята Telegram, шлём plain text")
        bot.reply_to(message, body, parse_mode=None)


@bot.message_handler(commands=["start", "help"])
def cmd_start(message: Message) -> None:
    bot.send_message(
        message.chat.id,
        "Привет! Выбери режим работы кнопками ниже.\n\n"
        f"{BTN_GIGA} — личный ассистент и помощник\n"
        f"{BTN_YANDEX} — агент по поиску сериалов на вечер\n\n"
        "Команды:\n"
        "/gigachat — включить ассистента\n"
        "/series — включить подбор сериалов\n"
        "/clear — очистить историю текущего режима\n"
        "/mode — показать активный режим\n"
        "/help — справка",
        reply_markup=_mode_keyboard(),
    )


@bot.message_handler(commands=["gigachat", "assistant"])
def cmd_gigachat(message: Message) -> None:
    bot.send_message(
        message.chat.id,
        _set_mode(message.chat.id, MODE_GIGA),
        reply_markup=_mode_keyboard(),
    )


@bot.message_handler(commands=["series", "yandex", "serials"])
def cmd_series(message: Message) -> None:
    bot.send_message(
        message.chat.id,
        _set_mode(message.chat.id, MODE_YANDEX),
        reply_markup=_mode_keyboard(),
    )


@bot.message_handler(commands=["mode"])
def cmd_mode(message: Message) -> None:
    mode = _mode.get(message.chat.id)
    if mode == MODE_GIGA:
        text = "Сейчас: личный ассистент (GigaChat)"
    elif mode == MODE_YANDEX:
        text = "Сейчас: подбор сериалов (Yandex AI)"
    else:
        text = "Режим ещё не выбран. Нажми кнопку ниже."
    bot.send_message(message.chat.id, text, reply_markup=_mode_keyboard())


@bot.message_handler(commands=["clear"])
def cmd_clear(message: Message) -> None:
    chat_id = message.chat.id
    mode = _mode.get(chat_id)
    if not mode:
        bot.reply_to(message, "Сначала выбери режим.")
        return
    _history.pop((chat_id, mode), None)
    label = "ассистента" if mode == MODE_GIGA else "подбора сериалов"
    bot.reply_to(message, f"История режима {label} очищена.")


@bot.message_handler(func=lambda m: m.text == BTN_GIGA)
def on_btn_giga(message: Message) -> None:
    bot.send_message(
        message.chat.id,
        _set_mode(message.chat.id, MODE_GIGA),
        reply_markup=_mode_keyboard(),
    )


@bot.message_handler(func=lambda m: m.text == BTN_YANDEX)
def on_btn_yandex(message: Message) -> None:
    bot.send_message(
        message.chat.id,
        _set_mode(message.chat.id, MODE_YANDEX),
        reply_markup=_mode_keyboard(),
    )


@bot.message_handler(content_types=["text"])
def handle_text(message: Message) -> None:
    text = (message.text or "").strip()
    if not text:
        return

    mode = _mode.get(message.chat.id)
    if not mode:
        bot.send_message(
            message.chat.id,
            "Сначала выбери режим кнопками ниже.",
            reply_markup=_mode_keyboard(),
        )
        return

    bot.send_chat_action(message.chat.id, "typing")
    started = time.monotonic()
    try:
        if mode == MODE_GIGA:
            answer = ask_gigachat(message.chat.id, text)
        else:
            answer = ask_series_agent(message.chat.id, text)
    except Exception:
        log.exception(
            "Ошибка режима %s для chat_id=%s",
            mode,
            message.chat.id,
            extra={
                "mode": mode,
                "chat_id": message.chat.id,
                "duration_ms": round((time.monotonic() - started) * 1000),
            },
        )
        bot.reply_to(
            message,
            "Не удалось получить ответ. Проверь ключи в .env или попробуй позже.",
        )
        return

    duration_ms = round((time.monotonic() - started) * 1000)
    log.info(
        "Ответ в режиме %s за %s мс",
        mode,
        duration_ms,
        extra={
            "mode": mode,
            "chat_id": message.chat.id,
            "duration_ms": duration_ms,
            "request_chars": len(text),
            "answer_chars": len(answer),
        },
    )
    _reply(message, answer)


def main() -> None:
    log.info("Бот запущен: GigaChat=%s + Yandex AI", GIGACHAT_MODEL)
    try:
        _ensure_token()
    except Exception:
        log.warning("GigaChat token пока не получен — попробуем при первом запросе")
    bot.infinity_polling(skip_pending=True, timeout=60)


if __name__ == "__main__":
    main()
