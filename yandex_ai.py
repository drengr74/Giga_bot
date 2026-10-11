"""Подключение к Yandex AI Studio (YandexGPT).

Использование в Telegram-боте или другом проекте:

    from yandex_ai import ask_yandex

    text = ask_yandex("Привет!")
    # или с историей диалога:
    text = ask_yandex([
        {"role": "system", "text": "Ты умный помощник."},
        {"role": "user", "text": "Как дела?"},
    ])

Ключи в .env:
    YANDEX_FOLDER_ID=...
    YANDEX_API_KEY=...
    YANDEX_MODEL=yandexgpt-lite   # опционально
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from yandex_ai_studio_sdk import AIStudio

DEFAULT_MODEL = "yandexgpt-lite"
DEFAULT_TEMPERATURE = 0.6


def _load_env(env_file: str | Path | None = None) -> None:
    if env_file is not None:
        load_dotenv(env_file)
    else:
        load_dotenv(Path(__file__).resolve().parent / ".env")
        load_dotenv()  # также подхватить .env из cwd другого проекта


def get_credentials(
    *,
    folder_id: str | None = None,
    api_key: str | None = None,
    env_file: str | Path | None = None,
) -> tuple[str, str]:
    """Возвращает (folder_id, api_key) из аргументов или .env."""
    _load_env(env_file)

    folder = folder_id or os.getenv("YANDEX_FOLDER_ID")
    key = api_key or os.getenv("YANDEX_API_KEY") or os.getenv("YANDEX_AUTH")

    missing = []
    if not folder:
        missing.append("YANDEX_FOLDER_ID")
    if not key:
        missing.append("YANDEX_API_KEY")
    if missing:
        raise ValueError(
            "Не заданы ключи Yandex AI: "
            + ", ".join(missing)
            + ". Передайте аргументы или пропишите их в .env"
        )
    return folder, key


def create_sdk(
    *,
    folder_id: str | None = None,
    api_key: str | None = None,
    env_file: str | Path | None = None,
) -> AIStudio:
    """Создаёт клиент AIStudio для запросов к Yandex AI."""
    folder, key = get_credentials(
        folder_id=folder_id, api_key=api_key, env_file=env_file
    )
    return AIStudio(folder_id=folder, auth=key)


def ask_yandex(
    messages: str | list[dict[str, Any]],
    *,
    model: str | None = None,
    temperature: float | None = None,
    folder_id: str | None = None,
    api_key: str | None = None,
    env_file: str | Path | None = None,
    timeout: int = 180,
) -> str:
    """Отправляет запрос в YandexGPT и возвращает текст ответа.

    ``messages`` — строка (одно user-сообщение) или список словарей
    вида ``{"role": "user"|"assistant"|"system", "text": "..."}``.
    """
    _load_env(env_file)

    model_name = model or os.getenv("YANDEX_MODEL", DEFAULT_MODEL)
    temp = (
        DEFAULT_TEMPERATURE
        if temperature is None
        else temperature
    )
    if temperature is None and os.getenv("YANDEX_TEMPERATURE"):
        temp = float(os.environ["YANDEX_TEMPERATURE"])

    sdk = create_sdk(folder_id=folder_id, api_key=api_key, env_file=env_file)
    gpt = sdk.models.completions(model_name).configure(temperature=temp)
    result = gpt.run(messages, timeout=timeout)
    return result.text


if __name__ == "__main__":
    print(ask_yandex("Ответь одним словом: работает?"))
