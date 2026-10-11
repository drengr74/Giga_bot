"""Получение токена GigaChat.

Использование в другом проекте:
    from get_token import get_token

    access_token, expires_in, expires_human = get_token()
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import NamedTuple

from dotenv import load_dotenv
from gigachat import GigaChat

BASE_URL = "https://api.giga.chat/v1"


class TokenInfo(NamedTuple):
    access_token: str
    expires_in: int  # секунды до истечения
    expires_human: str  # то же в читаемом виде


def _format_seconds(total: int) -> str:
    if total < 0:
        return "истёк"
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days} дн.")
    if hours or days:
        parts.append(f"{hours} ч.")
    if minutes or hours or days:
        parts.append(f"{minutes} мин.")
    parts.append(f"{seconds} сек.")
    return " ".join(parts)


def get_token(
    credentials: str | None = None,
    *,
    base_url: str = BASE_URL,
    ca_bundle_file: str | Path | None = None,
    env_file: str | Path | None = None,
) -> TokenInfo:
    """Запрашивает access token у GigaChat.

    Возвращает ``TokenInfo(access_token, expires_in, expires_human)``.

    Ключ берётся из аргумента ``credentials``, иначе из переменной
    окружения ``GIGACHAT_CREDENTIALS`` (файл ``.env`` подхватывается
    автоматически).

    Для api.giga.chat укажите ``ca_bundle_file`` или ``GIGACHAT_CA_BUNDLE``
    (российский корневой сертификат).
    """
    load_dotenv(env_file)

    key = credentials or os.getenv("GIGACHAT_CREDENTIALS")
    if not key:
        raise ValueError(
            "Не задан ключ авторизации. "
            "Передайте credentials=... или задайте GIGACHAT_CREDENTIALS в .env"
        )

    ca = ca_bundle_file or os.getenv("GIGACHAT_CA_BUNDLE")
    kwargs: dict = {"base_url": base_url, "credentials": key}
    if ca:
        kwargs["ca_bundle_file"] = str(ca)

    with GigaChat(**kwargs) as giga:
        raw = giga.get_token()

    access_token = raw.access_token
    # expires_at приходит в миллисекундах
    expires_in = max(0, int(raw.expires_at / 1000 - time.time()))
    return TokenInfo(access_token, expires_in, _format_seconds(expires_in))


if __name__ == "__main__":
    token, seconds, human = get_token()
    print(f"token: {token}")
    print(f"expires_in: {seconds}")
    print(f"expires_human: {human}")
