from typing import Any
from uuid import UUID

from app.learning.detector import LearningDetector
from app.learning.extractor import LearningExtractor
from app.learning.interfaces.learning import LearningStore
from app.learning.models import LearningRule, LearningSignal, LearningSource
from app.learning.policies.learning_policy import LearningPolicy
from app.learning.providers.in_memory_learning_store import InMemoryLearningStore
from app.llm.gateway import LLMGateway


class LearningManager:
    """Persists durable behavior rules — not model fine-tuning."""

    def __init__(
        self,
        store: LearningStore | None = None,
        *,
        extractor: LearningExtractor | None = None,
        detector: LearningDetector | None = None,
        policy: LearningPolicy | None = None,
        llm_gateway: LLMGateway | None = None,
    ) -> None:
        self._store = store or InMemoryLearningStore()
        self._policy = policy or LearningPolicy()
        self._detector = detector or LearningDetector(self._policy)
        if extractor is not None:
            self._extractor = extractor
        elif llm_gateway is not None:
            self._extractor = LearningExtractor(llm_gateway)
        else:
            self._extractor = None

    @property
    def detector(self) -> LearningDetector:
        return self._detector

    async def learn(
        self,
        text: str,
        *,
        source: LearningSource = LearningSource.USER_FEEDBACK,
        client_id: UUID | None = None,
        project_id: UUID | None = None,
        context: dict[str, Any] | None = None,
        trace_id: str = "-",
        force: bool = False,
    ) -> LearningRule | None:
        signal = self._detector.detect(
            text,
            source=source,
            client_id=client_id,
            project_id=project_id,
            metadata=context,
        )
        if signal is None and force and text.strip():
            signal = LearningSignal(
                text=text.strip(),
                source=LearningSource.EXPLICIT_PREFERENCE,
                client_id=client_id,
                project_id=project_id,
                metadata=context or {},
            )
        if signal is None:
            return None
        if self._extractor is None:
            raise ValueError("LearningExtractor requires LLM gateway")

        extraction = await self._extractor.extract(signal, context=context, trace_id=trace_id)
        if not self._policy.should_save(extraction, signal) or extraction.rule is None:
            return None

        candidate = extraction.rule
        existing = await self._store.find_duplicate(
            category=candidate.category,
            key=candidate.key,
            client_id=client_id,
            project_id=project_id,
        )
        if existing is not None:
            existing.value = candidate.value
            existing.confidence = self._policy.merge_confidence(existing, extraction.confidence)
            existing.source = signal.source
            existing.metadata = {
                **existing.metadata,
                "last_signal": signal.text[:300],
                "merged": True,
            }
            return await self._store.save(existing)

        rule = LearningRule(
            scope=candidate.scope,
            category=candidate.category,
            key=candidate.key,
            value=candidate.value,
            confidence=extraction.confidence,
            source=signal.source,
            client_id=client_id,
            project_id=project_id,
            metadata={"signal": signal.text[:300]},
        )
        return await self._store.save(rule)

    async def get_rules(
        self,
        *,
        client_id: UUID | None = None,
        project_id: UUID | None = None,
        category: str | None = None,
        limit: int = 100,
    ) -> list[LearningRule]:
        return await self._store.list_rules(
            client_id=client_id,
            project_id=project_id,
            category=category,
            limit=limit,
        )

    async def search_rules(
        self,
        *,
        query: str | None = None,
        client_id: UUID | None = None,
        project_id: UUID | None = None,
        limit: int = 50,
    ) -> list[LearningRule]:
        return await self._store.search(
            query=query,
            client_id=client_id,
            project_id=project_id,
            limit=limit,
        )

    async def update_confidence(self, rule_id: UUID, confidence: float) -> LearningRule | None:
        rule = await self._store.get(rule_id)
        if rule is None:
            return None
        rule.confidence = max(0.0, min(1.0, confidence))
        return await self._store.save(rule)

    async def get_applicable_rules(
        self,
        *,
        client_id: UUID | None = None,
        project_id: UUID | None = None,
        limit: int = 20,
    ) -> list[LearningRule]:
        """Return rules that pass the confidence filter (read-path isolation)."""
        rules = await self.get_rules(client_id=client_id, project_id=project_id, limit=limit)
        return [rule for rule in rules if rule.confidence >= self._policy.min_confidence]

    async def apply_rules(
        self,
        *,
        client_id: UUID | None = None,
        project_id: UUID | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        rules = await self.get_applicable_rules(
            client_id=client_id, project_id=project_id, limit=limit
        )
        return [
            {
                "id": str(rule.id),
                "category": rule.category,
                "key": rule.key,
                "value": rule.value,
                "rule": f"{rule.key}={rule.value}",
                "confidence": rule.confidence,
                "scope": rule.scope.value,
                "source": rule.source.value,
            }
            for rule in rules
        ]
