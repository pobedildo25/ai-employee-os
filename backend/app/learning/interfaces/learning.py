from abc import ABC, abstractmethod
from uuid import UUID

from app.learning.models import LearningRule


class LearningStore(ABC):
    @abstractmethod
    async def save(self, rule: LearningRule) -> LearningRule:
        raise NotImplementedError

    @abstractmethod
    async def get(self, rule_id: UUID) -> LearningRule | None:
        raise NotImplementedError

    @abstractmethod
    async def list_rules(
        self,
        *,
        client_id: UUID | None = None,
        project_id: UUID | None = None,
        category: str | None = None,
        limit: int = 100,
    ) -> list[LearningRule]:
        raise NotImplementedError

    @abstractmethod
    async def find_duplicate(
        self,
        *,
        category: str,
        key: str,
        client_id: UUID | None = None,
        project_id: UUID | None = None,
    ) -> LearningRule | None:
        raise NotImplementedError

    @abstractmethod
    async def search(
        self,
        *,
        query: str | None = None,
        client_id: UUID | None = None,
        project_id: UUID | None = None,
        limit: int = 50,
    ) -> list[LearningRule]:
        raise NotImplementedError
