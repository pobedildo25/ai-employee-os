from datetime import datetime
from uuid import UUID

from app.learning.interfaces.learning import LearningStore
from app.learning.models import LearningRule


class InMemoryLearningStore(LearningStore):
    def __init__(self) -> None:
        self._rules: dict[UUID, LearningRule] = {}

    async def save(self, rule: LearningRule) -> LearningRule:
        rule.updated_at = datetime.now()
        self._rules[rule.id] = rule
        return rule

    async def get(self, rule_id: UUID) -> LearningRule | None:
        return self._rules.get(rule_id)

    async def list_rules(
        self,
        *,
        client_id: UUID | None = None,
        project_id: UUID | None = None,
        category: str | None = None,
        limit: int = 100,
    ) -> list[LearningRule]:
        results = list(self._rules.values())
        if client_id is not None:
            results = [rule for rule in results if rule.client_id == client_id]
        if project_id is not None:
            results = [rule for rule in results if rule.project_id == project_id]
        if category is not None:
            results = [rule for rule in results if rule.category == category]
        results.sort(key=lambda rule: rule.confidence, reverse=True)
        return results[:limit]

    async def find_duplicate(
        self,
        *,
        category: str,
        key: str,
        client_id: UUID | None = None,
        project_id: UUID | None = None,
    ) -> LearningRule | None:
        for rule in self._rules.values():
            if rule.category != category or rule.key != key:
                continue
            if client_id is not None and rule.client_id != client_id:
                continue
            if project_id is not None and rule.project_id != project_id:
                continue
            return rule
        return None

    async def search(
        self,
        *,
        query: str | None = None,
        client_id: UUID | None = None,
        project_id: UUID | None = None,
        limit: int = 50,
    ) -> list[LearningRule]:
        results = await self.list_rules(client_id=client_id, project_id=project_id, limit=1000)
        if query:
            needle = query.lower()
            results = [
                rule
                for rule in results
                if needle in rule.category.lower()
                or needle in rule.key.lower()
                or needle in rule.value.lower()
            ]
        return results[:limit]
