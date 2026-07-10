from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import DateTime, Float, String, Text, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.memory.interfaces.memory import MemoryStore
from app.memory.models import MemoryItem, MemorySearchQuery, MemoryType

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class MemoryRecord(Base):
    __tablename__ = "memory_items"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)
    importance: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    source: Mapped[str] = mapped_column(String(255), nullable=False, default="system")
    client_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)
    project_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    created_at: Mapped[Any] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[Any | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PostgresLongTermMemory(MemoryStore):
    """PostgreSQL-backed long-term memory for facts, preferences, and decisions."""

    LONG_TERM_TYPES = {
        MemoryType.FACT,
        MemoryType.PREFERENCE,
        MemoryType.DECISION,
    }

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, item: MemoryItem) -> MemoryItem:
        record = _to_record(item)
        self._session.add(record)
        await self._session.flush()
        return _from_record(record)

    async def get(self, memory_id: UUID) -> MemoryItem | None:
        record = await self._session.get(MemoryRecord, memory_id)
        return _from_record(record) if record else None

    async def search(self, query: MemorySearchQuery) -> list[MemoryItem]:
        stmt = select(MemoryRecord)
        types = query.memory_types or list(self.LONG_TERM_TYPES)
        allowed = [t.value for t in types if t in self.LONG_TERM_TYPES]
        if allowed:
            stmt = stmt.where(MemoryRecord.type.in_(allowed))
        if query.client_id:
            stmt = stmt.where(MemoryRecord.client_id == query.client_id)
        if query.project_id:
            stmt = stmt.where(MemoryRecord.project_id == query.project_id)
        if query.query:
            stmt = stmt.where(MemoryRecord.content.ilike(f"%{query.query}%"))
        stmt = stmt.order_by(MemoryRecord.importance.desc(), MemoryRecord.created_at.desc()).limit(query.limit)

        result = await self._session.execute(stmt)
        return [_from_record(record) for record in result.scalars().all()]

    async def delete(self, memory_id: UUID) -> bool:
        record = await self._session.get(MemoryRecord, memory_id)
        if record is None:
            return False
        await self._session.delete(record)
        await self._session.flush()
        return True

    async def update(self, memory_id: UUID, item: MemoryItem) -> MemoryItem | None:
        record = await self._session.get(MemoryRecord, memory_id)
        if record is None:
            return None
        record.type = item.type.value
        record.content = item.content
        record.metadata_ = item.metadata
        record.importance = item.importance
        record.source = item.source
        record.client_id = item.client_id
        record.project_id = item.project_id
        record.session_id = item.session_id
        record.expires_at = item.expires_at
        await self._session.flush()
        return _from_record(record)


class InMemoryLongTermMemory(MemoryStore):
    """In-memory long-term memory for tests."""

    LONG_TERM_TYPES = PostgresLongTermMemory.LONG_TERM_TYPES

    def __init__(self) -> None:
        self._items: dict[UUID, MemoryItem] = {}

    async def save(self, item: MemoryItem) -> MemoryItem:
        self._items[item.id] = item
        return item

    async def get(self, memory_id: UUID) -> MemoryItem | None:
        return self._items.get(memory_id)

    async def search(self, query: MemorySearchQuery) -> list[MemoryItem]:
        types = set(query.memory_types or list(self.LONG_TERM_TYPES))
        results = [
            item
            for item in self._items.values()
            if item.type in types
            and (query.client_id is None or item.client_id == query.client_id)
            and (query.project_id is None or item.project_id == query.project_id)
            and (query.query is None or query.query.lower() in item.content.lower())
        ]
        results.sort(key=lambda item: (-item.importance, item.created_at), reverse=False)
        return results[: query.limit]

    async def delete(self, memory_id: UUID) -> bool:
        return self._items.pop(memory_id, None) is not None

    async def update(self, memory_id: UUID, item: MemoryItem) -> MemoryItem | None:
        if memory_id not in self._items:
            return None
        updated = item.model_copy(update={"id": memory_id})
        self._items[memory_id] = updated
        return updated


def _to_record(item: MemoryItem) -> MemoryRecord:
    return MemoryRecord(
        id=item.id,
        type=item.type.value,
        content=item.content,
        metadata_=item.metadata,
        importance=item.importance,
        source=item.source,
        client_id=item.client_id,
        project_id=item.project_id,
        session_id=item.session_id,
        created_at=item.created_at,
        expires_at=item.expires_at,
    )


def _from_record(record: MemoryRecord) -> MemoryItem:
    return MemoryItem(
        id=record.id,
        type=MemoryType(record.type),
        content=record.content,
        metadata=record.metadata_ or {},
        importance=record.importance,
        source=record.source,
        client_id=record.client_id,
        project_id=record.project_id,
        session_id=record.session_id,
        created_at=record.created_at,
        expires_at=record.expires_at,
    )
