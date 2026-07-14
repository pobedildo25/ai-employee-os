"""Human-facing stage labels for Telegram UX.

Maps internal capability names to employee-style descriptions.
Never expose raw capability / skill / node identifiers to the user.
"""

from __future__ import annotations

from typing import Any

# Present continuous for live progress bubbles.
PROGRESS_STAGE_LABELS_RU: dict[str, str] = {
    "research": "Изучаю компанию и рынок…",
    "document_analysis": "Изучаю материалы…",
    "brand_style_analysis": "Сверяю с фирменным стилем…",
    "client_intelligence": "Собираю информацию о клиенте…",
    "strategy_analysis": "Формирую стратегию…",
    "analytics": "Смотрю данные…",
    "document_creation": "Пишу документ…",
    "document_generation": "Пишу документ…",
    "document_revision": "Вношу правки…",
    "presentation_design": "Собираю презентацию…",
    "document_rendering": "Собираю файл…",
    "quality_review": "Проверяю качество…",
    "knowledge_migration": "Обновляю знания…",
}

# Infinite / noun phrases for approval bullet lists (employee proposal).
APPROVAL_STAGE_LABELS_RU: dict[str, str] = {
    "research": "изучу компанию и рынок",
    "document_analysis": "изучу материалы",
    "brand_style_analysis": "сверу с фирменным стилем",
    "client_intelligence": "соберу информацию о клиенте",
    "strategy_analysis": "подготовлю стратегию",
    "analytics": "посмотрю данные",
    "document_creation": "создам документ",
    "document_generation": "создам документ",
    "document_revision": "внесу правки",
    "presentation_design": "соберу презентацию",
    "document_rendering": "подготовлю файл",
    "quality_review": "проверю качество",
    "knowledge_migration": "обновлю знания",
}


def human_progress_title(
    *,
    description: str | None = None,
    capability: str | None = None,
) -> str:
    """Prefer a human description; never leak raw capability ids."""
    text = (description or "").strip()
    if text and text != capability and "_" not in text:
        return text if text.endswith(("…", ".", "!", "?")) else f"{text.rstrip('.')}…"
    if capability:
        return PROGRESS_STAGE_LABELS_RU.get(capability, "Работаю…")
    return "Работаю…"


def human_approval_bullet(step: dict[str, Any]) -> str:
    """One bullet for an employee-style plan proposal."""
    capability = str(step.get("capability") or "").strip()
    description = str(step.get("description") or "").strip()
    if capability and capability in APPROVAL_STAGE_LABELS_RU:
        return APPROVAL_STAGE_LABELS_RU[capability]
    if description and "_" not in description:
        cleaned = description.rstrip(".…").lower()
        return cleaned
    if capability:
        return APPROVAL_STAGE_LABELS_RU.get(capability, "сделаю следующий шаг")
    return "сделаю следующий шаг"


def humanize_direct_plan_label(capability: str) -> str:
    """Label stored on PlanStep.description for progress/approval reuse."""
    return PROGRESS_STAGE_LABELS_RU.get(capability, "Работаю…").rstrip("…")
