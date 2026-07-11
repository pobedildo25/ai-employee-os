from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.learning.interfaces.learning import LearningStore
from app.learning.models import LearningRule, LearningScope, LearningSource
from app.models.learning import LearningRuleRecord


class PostgresLearningStore(LearningStore):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, rule: LearningRule) -> LearningRule:
        record = await self._session.get(LearningRuleRecord, rule.id)
        if record is None:
            record = LearningRuleRecord(id=rule.id)
            self._session.add(record)
        record.scope = rule.scope.value
        record.category = rule.category
        record.key = rule.key
        record.value = rule.value
        record.confidence = rule.confidence
        record.source = rule.source.value
        record.client_id = rule.client_id
        record.project_id = rule.project_id
        record.metadata_ = rule.metadata
        await self._session.flush()
        rule.updated_at = datetime.now()
        return rule

    async def get(self, rule_id: UUID) -> LearningRule | None:
        record = await self._session.get(LearningRuleRecord, rule_id)
        return _to_rule(record) if record else None

    async def list_rules(
        self,
        *,
        client_id: UUID | None = None,
        project_id: UUID | None = None,
        category: str | None = None,
        limit: int = 100,
    ) -> list[LearningRule]:
        stmt = select(LearningRuleRecord)
        if client_id is not None:
            stmt = stmt.where(LearningRuleRecord.client_id == client_id)
        if project_id is not None:
            stmt = stmt.where(LearningRuleRecord.project_id == project_id)
        if category is not None:
            stmt = stmt.where(LearningRuleRecord.category == category)
        stmt = stmt.order_by(LearningRuleRecord.confidence.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return [_to_rule(record) for record in result.scalars().all()]

    async def find_duplicate(
        self,
        *,
        category: str,
        key: str,
        client_id: UUID | None = None,
        project_id: UUID | None = None,
    ) -> LearningRule | None:
        stmt = select(LearningRuleRecord).where(
            LearningRuleRecord.category == category,
            LearningRuleRecord.key == key,
        )
        if client_id is not None:
            stmt = stmt.where(LearningRuleRecord.client_id == client_id)
        if project_id is not None:
            stmt = stmt.where(LearningRuleRecord.project_id == project_id)
        stmt = stmt.limit(1)
        result = await self._session.execute(stmt)
        record = result.scalar_one_or_none()
        return _to_rule(record) if record else None

    async def search(
        self,
        *,
        query: str | None = None,
        client_id: UUID | None = None,
        project_id: UUID | None = None,
        limit: int = 50,
    ) -> list[LearningRule]:
        stmt = select(LearningRuleRecord)
        if client_id is not None:
            stmt = stmt.where(LearningRuleRecord.client_id == client_id)
        if project_id is not None:
            stmt = stmt.where(LearningRuleRecord.project_id == project_id)
        if query:
            pattern = f"%{query}%"
            stmt = stmt.where(
                LearningRuleRecord.category.ilike(pattern)
                | LearningRuleRecord.key.ilike(pattern)
                | LearningRuleRecord.value.ilike(pattern)
            )
        stmt = stmt.order_by(LearningRuleRecord.confidence.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return [_to_rule(record) for record in result.scalars().all()]


def _to_rule(record: LearningRuleRecord) -> LearningRule:
    return LearningRule(
        id=record.id,
        scope=LearningScope(record.scope),
        category=record.category,
        key=record.key,
        value=record.value,
        confidence=record.confidence,
        source=LearningSource(record.source),
        client_id=record.client_id,
        project_id=record.project_id,
        metadata=record.metadata_ or {},
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
