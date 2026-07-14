from app.learning.models import LearningRule, LearningSignal, RuleExtractionResult

MIN_SAVE_CONFIDENCE = 0.6
REVISION_SAVE_CONFIDENCE = 0.75
CONFIDENCE_BOOST = 0.08
MAX_CONFIDENCE = 0.98

# Hard allowlist — Learning may only persist style/format/preference rules.
# Never strategy, routing, DecisionType, or capability selection.
ALLOWED_LEARNING_CATEGORIES = frozenset(
    {
        "style",
        "writing_style",
        "document_style",
        "presentation_style",
        "format",
        "formatting",
        "language",
        "tone",
        "layout",
        "structure",
        "verbosity",
        "preference",
        "preferences",
        "brand",
        "agency_practice",
        "presentation",
        "visual",
        "copy",
    }
)

_BLOCKED_CATEGORY_MARKERS = (
    "strateg",
    "rout",
    "decision",
    "capability",
    "pipeline",
    "workflow",
    "intent",
    "execut",
    "planner",
    "orchestr",
)

# One-off / ephemeral instruction markers — not durable learning.
ONE_OFF_MARKERS = (
    "только сейчас",
    "на этот раз",
    "в этот раз",
    "just this once",
    "this time only",
    "for now only",
    "once",
)

# Durable preference markers — required for looks_like_preference.
DURABLE_PREFERENCE_MARKERS = (
    "всегда",
    "никогда",
    "предпочитаю",
    "предпочтение",
    "обычно",
    "по умолчанию",
    "always",
    "never",
    "prefer",
    "preference",
    "from now on",
)

# Soft style preferences that may appear with durable markers.
STYLE_PREFERENCE_MARKERS = (
    "меньше текста",
    "короче",
    "без длинных",
    "убирай",
    "не делай",
    "less text",
    "shorter",
    "concise",
)

# One-shot document edit phrasing — alone must NOT become durable learning.
DOCUMENT_EDIT_MARKERS = (
    "короче",
    "длиннее",
    "добавь",
    "убери",
    "исправь",
    "перефразируй",
    "перепиши",
    "shorter",
    "longer",
    "add",
    "remove",
    "fix",
)

LEARNING_MARKERS = DURABLE_PREFERENCE_MARKERS + STYLE_PREFERENCE_MARKERS


class LearningPolicy:
    """Infrastructure policy for when and how to persist learning rules."""

    def __init__(
        self,
        *,
        min_confidence: float = MIN_SAVE_CONFIDENCE,
        confidence_boost: float = CONFIDENCE_BOOST,
        revision_min_confidence: float = REVISION_SAVE_CONFIDENCE,
    ) -> None:
        self.min_confidence = min_confidence
        self.confidence_boost = confidence_boost
        self.revision_min_confidence = revision_min_confidence

    def is_one_off(self, text: str) -> bool:
        lowered = text.lower().strip()
        return any(marker in lowered for marker in ONE_OFF_MARKERS)

    def looks_like_document_edit(self, text: str) -> bool:
        """One-off revision phrasing without durable preference markers."""
        lowered = text.lower().strip()
        if any(marker in lowered for marker in DURABLE_PREFERENCE_MARKERS):
            return False
        return any(marker in lowered for marker in DOCUMENT_EDIT_MARKERS)

    def looks_like_preference(self, text: str) -> bool:
        lowered = text.lower().strip()
        if len(lowered) < 8:
            return False
        if self.looks_like_document_edit(lowered):
            return False
        # Require an explicit durable preference marker (always/prefer/…).
        return any(marker in lowered for marker in DURABLE_PREFERENCE_MARKERS)

    def is_allowed_category(self, category: str | None) -> bool:
        """Fail-closed category gate — Product Goal §5."""
        cat = (category or "").strip().lower()
        if not cat:
            return False
        if any(marker in cat for marker in _BLOCKED_CATEGORY_MARKERS):
            return False
        if cat in ALLOWED_LEARNING_CATEGORIES:
            return True
        # Soft accept common extractor synonyms that stay style/format-bound.
        return any(
            cat.startswith(prefix)
            for prefix in ("style", "writing", "document", "format", "prefer", "brand")
        )

    def should_save(self, result: RuleExtractionResult, signal: LearningSignal) -> bool:
        if not result.should_learn or result.rule is None:
            return False
        if self.is_one_off(signal.text):
            return False
        if self.looks_like_document_edit(signal.text):
            return False
        if not self.is_allowed_category(result.rule.category):
            return False
        threshold = self.min_confidence
        if signal.source.value == "revision_request":
            threshold = self.revision_min_confidence
        return result.confidence >= threshold

    def merge_confidence(self, existing: LearningRule, incoming_confidence: float) -> float:
        boosted = max(existing.confidence, incoming_confidence) + self.confidence_boost
        return min(MAX_CONFIDENCE, boosted)
