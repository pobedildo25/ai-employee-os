"""Extract the business client a chat task is *for* (e.g. "КП для Яндекса" → "Яндекс").

The agency's AI employee receives free-form tasks. To attach work to the right
business client we need the client/company name mentioned in the request. This
module extracts that subject with an LLM (primary) and a conservative regex
heuristic (fallback / offline). It deliberately errs toward returning nothing
rather than inventing a client, so we never create junk records in the DB.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from app.llm.models import LLMMessage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExtractedSubject:
    name: str | None
    confidence: float = 0.0
    is_agency_self: bool = False

    @property
    def is_usable(self) -> bool:
        return bool(self.name) and not self.is_agency_self and self.confidence >= 0.5


_EXTRACTION_SYSTEM_PROMPT = """You extract the BUSINESS CLIENT a work task is for.

You work inside a marketing agency's assistant. Given one user message, find the
company/brand that the requested deliverable is ABOUT or FOR (the client), e.g.
"сделай КП для Яндекса" → "Яндекс"; "заведи клиента Acme" → "Acme".

Return STRICT JSON only, no prose:
{"business_subject": <string|null>, "is_agency_self": <bool>, "confidence": <0..1>}

Rules:
- business_subject is the client's real brand/company name, normalized to its
  current official form (e.g. "Сбер" not "Сбербанк", "Т-Банк" not "Тинькофф").
- Return null when the task names no external company, is generic (a note, a
  template, a general question, small talk), or is ambiguous.
- is_agency_self=true when the named entity is clearly the assistant's OWN agency
  rather than a client. In that case set business_subject=null.
- confidence reflects how sure you are the subject is a real client to attach work to."""


async def extract_business_subject(
    user_input: str,
    *,
    llm_gateway=None,
    model: str | None = None,
    trace_id: str = "-",
) -> ExtractedSubject:
    text = (user_input or "").strip()
    if not text:
        return ExtractedSubject(name=None)

    if llm_gateway is not None:
        try:
            result = await _extract_with_llm(text, llm_gateway, model, trace_id)
            if result is not None:
                return result
        except Exception as exc:  # never let extraction break the task
            logger.warning(
                "business subject LLM extraction failed | trace_id=%s error=%s",
                trace_id,
                exc,
            )

    return _extract_heuristic(text)


async def _extract_with_llm(
    text: str,
    llm_gateway,
    model: str | None,
    trace_id: str,
) -> ExtractedSubject | None:
    response = await llm_gateway.complete(
        messages=[
            LLMMessage(role="system", content=_EXTRACTION_SYSTEM_PROMPT),
            LLMMessage(role="user", content=text),
        ],
        model=model,
        temperature=0.0,
        max_tokens=200,
        metadata={"purpose": "business_subject_extraction", "trace_id": trace_id},
    )
    payload = _parse_json_object(response.content)
    if payload is None:
        return None
    name = payload.get("business_subject")
    name = name.strip() if isinstance(name, str) else None
    confidence = payload.get("confidence")
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.6 if name else 0.0
    return ExtractedSubject(
        name=name or None,
        confidence=max(0.0, min(1.0, confidence)),
        is_agency_self=bool(payload.get("is_agency_self")),
    )


def _parse_json_object(content: str) -> dict | None:
    if not content:
        return None
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


# --- Heuristic fallback -------------------------------------------------------

# Marker words that introduce a client subject in Russian requests.
_SUBJECT_MARKERS = (
    r"для",
    r"по клиенту",
    r"клиента",
    r"клиент",
    r"заведи клиента",
    r"добавь клиента",
    r"компании",
    r"компания",
    r"бренда",
    r"бренд",
)

_STOPWORDS = {
    "нас",
    "меня",
    "тебя",
    "него",
    "нее",
    "них",
    "агентства",
    "агентство",
}


def _extract_heuristic(text: str) -> ExtractedSubject:
    quoted = re.search(r"[«\"']([^«»\"']{2,60})[»\"']", text)
    if quoted:
        candidate = _clean_candidate(quoted.group(1))
        if candidate:
            return ExtractedSubject(name=candidate, confidence=0.7)

    markers = "|".join(_SUBJECT_MARKERS)
    pattern = re.compile(
        rf"(?:{markers})\s+([A-ZА-ЯЁ][\wА-Яа-яЁё&.\-]*(?:\s+[A-ZА-ЯЁ0-9][\wА-Яа-яЁё&.\-]*){{0,2}})",
    )
    match = pattern.search(text)
    if match:
        candidate = _clean_candidate(match.group(1))
        if candidate and candidate.casefold() not in _STOPWORDS:
            return ExtractedSubject(name=candidate, confidence=0.55)

    return ExtractedSubject(name=None)


def _clean_candidate(raw: str) -> str | None:
    candidate = raw.strip().strip(".,;:!?").strip()
    if len(candidate) < 2:
        return None
    if candidate.casefold() in _STOPWORDS:
        return None
    return candidate
