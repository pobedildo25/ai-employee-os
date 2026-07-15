"""Offline / no-LLM replies for common useful chat so Telegram stays alive."""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_GREETING_RE = re.compile(
    r"^\s*(привет|здравствуй|здравствуйте|добрый\s+(день|вечер|утро)|hello|hi|hey)"
    r"[\s!?.]*$",
    re.IGNORECASE,
)
_FX_RE = re.compile(
    r"(курс|сколко|сколько).*(доллар|usd|\$)|(доллар|usd).*(курс|сколко|сколько)",
    re.IGNORECASE,
)

GREETING_REPLY = (
    "Привет! Я NOVA — AI-сотрудник агентства.\n"
    "Могу помочь с документами, брифами, исследованиями и задачами по клиентам."
)


async def maybe_local_reply(user_input: str) -> str | None:
    text = (user_input or "").strip()
    if not text:
        return None
    if _GREETING_RE.match(text):
        return GREETING_REPLY
    if _FX_RE.search(text):
        return await _dollar_rate_reply()
    return None


async def _dollar_rate_reply() -> str:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("https://www.cbr-xml-daily.ru/daily_json.js")
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
        usd = (payload.get("Valute") or {}).get("USD") or {}
        value = usd.get("Value")
        previous = usd.get("Previous")
        date = payload.get("Date") or ""
        if value is None:
            raise ValueError("USD rate missing in CBR payload")
        delta = ""
        if previous is not None:
            change = float(value) - float(previous)
            sign = "+" if change >= 0 else ""
            delta = f" (день: {sign}{change:.4f})"
        day = date[:10] if date else "сегодня"
        return (
            f"Курс доллара ЦБ РФ на {day}: {float(value):.4f} ₽{delta}.\n"
            "Источник: cbr-xml-daily.ru (официальный курс ЦБ). "
            "Это не прогноз и не рыночная котировка брокера."
        )
    except Exception as exc:
        logger.warning("local FX lookup failed: %s", exc)
        return (
            "Сейчас не могу быстро взять курс с ЦБ (внешний источник недоступен), "
            "а языковая модель тоже недоступна.\n"
            "Проверьте https://www.cbr.ru/ или напишите снова чуть позже."
        )
