from app.client_intelligence.models import ClientIntelligenceSources, IntelligenceSignal


class PreferenceAnalyzer:
    """Finds style/format/constraint preferences — soft heuristics only."""

    def analyze(self, sources: ClientIntelligenceSources) -> list[IntelligenceSignal]:
        signals: list[IntelligenceSignal] = []
        for item in _iter_texts(sources):
            lower = item.lower()
            if any(token in lower for token in ("коротк", "concise", "short", "minimal", "минимум")):
                signals.append(
                    IntelligenceSignal(
                        category="preference",
                        key="presentation_length" if "презента" in lower or "presentation" in lower else "verbosity",
                        value="short",
                        confidence=0.8,
                        source="preference_analyzer",
                    )
                )
            if any(token in lower for token in ("formal", "официал", "делов")):
                signals.append(
                    IntelligenceSignal(
                        category="preference",
                        key="language",
                        value="formal",
                        confidence=0.75,
                        source="preference_analyzer",
                    )
                )
            if "minimal" in lower or "минималист" in lower:
                signals.append(
                    IntelligenceSignal(
                        category="preference",
                        key="document_style",
                        value="minimal",
                        confidence=0.8,
                        source="preference_analyzer",
                    )
                )
        for rule in sources.learning_rules:
            key = str(rule.get("key") or rule.get("category") or "preference")
            value = str(rule.get("value") or rule.get("content") or "")
            if value:
                signals.append(
                    IntelligenceSignal(
                        category="preference",
                        key=key,
                        value=value,
                        confidence=float(rule.get("confidence") or 0.7),
                        source="learning_rules",
                    )
                )
        return _dedupe(signals)


def _iter_texts(sources: ClientIntelligenceSources) -> list[str]:
    texts: list[str] = []
    texts.extend(sources.notes)
    for item in sources.memory_items:
        if item.get("content"):
            texts.append(str(item["content"]))
    for item in sources.knowledge_items:
        content = item.get("content") or item.get("title") or ""
        if content:
            texts.append(str(content))
    for rule in sources.learning_rules:
        value = rule.get("value") or rule.get("content") or rule.get("text")
        if value:
            texts.append(str(value))
    return texts


def _dedupe(signals: list[IntelligenceSignal]) -> list[IntelligenceSignal]:
    seen: set[tuple[str, str, str]] = set()
    result: list[IntelligenceSignal] = []
    for signal in signals:
        key = (signal.category, signal.key, signal.value)
        if key in seen:
            continue
        seen.add(key)
        result.append(signal)
    return result
