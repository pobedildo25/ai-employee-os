from app.learning.models import LearningRule, LearningSignal, RuleExtractionResult

MIN_SAVE_CONFIDENCE = 0.6
CONFIDENCE_BOOST = 0.08
MAX_CONFIDENCE = 0.98

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

LEARNING_MARKERS = (
    "всегда",
    "никогда",
    "предпочитаю",
    "предпочтение",
    "обычно",
    "по умолчанию",
    "меньше текста",
    "короче",
    "без длинных",
    "убирай",
    "не делай",
    "always",
    "never",
    "prefer",
    "preference",
    "less text",
    "shorter",
    "concise",
    "from now on",
)


class LearningPolicy:
    """Infrastructure policy for when and how to persist learning rules."""

    def __init__(
        self,
        *,
        min_confidence: float = MIN_SAVE_CONFIDENCE,
        confidence_boost: float = CONFIDENCE_BOOST,
    ) -> None:
        self.min_confidence = min_confidence
        self.confidence_boost = confidence_boost

    def is_one_off(self, text: str) -> bool:
        lowered = text.lower().strip()
        return any(marker in lowered for marker in ONE_OFF_MARKERS)

    def looks_like_preference(self, text: str) -> bool:
        lowered = text.lower().strip()
        if len(lowered) < 8:
            return False
        return any(marker in lowered for marker in LEARNING_MARKERS)

    def should_save(self, result: RuleExtractionResult, signal: LearningSignal) -> bool:
        if not result.should_learn or result.rule is None:
            return False
        if self.is_one_off(signal.text):
            return False
        return result.confidence >= self.min_confidence

    def merge_confidence(self, existing: LearningRule, incoming_confidence: float) -> float:
        boosted = max(existing.confidence, incoming_confidence) + self.confidence_boost
        return min(MAX_CONFIDENCE, boosted)
