from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge.models import KnowledgeItem
from app.knowledge.store import KnowledgeStore
from app.models.knowledge import KnowledgeRecord


class PostgresKnowledgeStore(KnowledgeStore):
    """PostgreSQL-backed knowledge store. Semantic search via Qdrant is deferred."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, item: KnowledgeItem) -> KnowledgeItem:
        record = KnowledgeRecord(
            id=item.id,
            client_id=item.client_id,
            title=item.title,
            category=item.category,
            content=item.content,
            confidence=item.confidence,
            source_artifact_id=item.source_artifact_id,
            metadata_=item.metadata,
        )
        self._session.add(record)
        await self._session.flush()
        return item

    async def get_by_id(self, item_id: UUID) -> KnowledgeItem | None:
        record = await self._session.get(KnowledgeRecord, item_id)
        return _to_item(record) if record else None

    async def list_by_client(self, client_id: UUID, *, limit: int = 50) -> list[KnowledgeItem]:
        stmt = (
            select(KnowledgeRecord)
            .where(KnowledgeRecord.client_id == client_id)
            .order_by(KnowledgeRecord.confidence.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [_to_item(record) for record in result.scalars().all()]

    async def search(
        self,
        *,
        client_id: UUID | None = None,
        query: str | None = None,
        category: str | None = None,
        limit: int = 20,
    ) -> list[KnowledgeItem]:
        stmt = select(KnowledgeRecord)
        if client_id is not None:
            stmt = stmt.where(KnowledgeRecord.client_id == client_id)
        if category is not None:
            stmt = stmt.where(KnowledgeRecord.category == category)
        if query:
            pattern = f"%{query}%"
            stmt = stmt.where(
                KnowledgeRecord.title.ilike(pattern) | KnowledgeRecord.content.ilike(pattern)
            )
        stmt = stmt.order_by(KnowledgeRecord.confidence.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return [_to_item(record) for record in result.scalars().all()]


def _to_item(record: KnowledgeRecord) -> KnowledgeItem:
    return KnowledgeItem(
        id=record.id,
        client_id=record.client_id,
        title=record.title,
        category=record.category,
        content=record.content,
        confidence=record.confidence,
        source_artifact_id=record.source_artifact_id,
        metadata=record.metadata_ or {},
        created_at=record.created_at,
    )
