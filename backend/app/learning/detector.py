from app.learning.models import LearningSignal, LearningSource
from app.learning.policies.learning_policy import LearningPolicy


class LearningDetector:
    """Detects whether an event carries a durable learning signal."""

    def __init__(self, policy: LearningPolicy | None = None) -> None:
        self._policy = policy or LearningPolicy()

    def detect(
        self,
        text: str | None,
        *,
        source: LearningSource = LearningSource.USER_FEEDBACK,
        client_id=None,
        project_id=None,
        metadata: dict | None = None,
    ) -> LearningSignal | None:
        if not text or not str(text).strip():
            return None
        cleaned = str(text).strip()
        if self._policy.is_one_off(cleaned):
            return None
        if source == LearningSource.EXPLICIT_PREFERENCE:
            return LearningSignal(
                text=cleaned,
                source=source,
                client_id=client_id,
                project_id=project_id,
                metadata=metadata or {},
            )
        if source in {
            LearningSource.USER_FEEDBACK,
            LearningSource.REVISION_REQUEST,
            LearningSource.QUALITY_GATE,
        } and self._policy.looks_like_preference(cleaned):
            return LearningSignal(
                text=cleaned,
                source=source,
                client_id=client_id,
                project_id=project_id,
                metadata=metadata or {},
            )
        return None
