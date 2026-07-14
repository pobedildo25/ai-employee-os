"""Resolve (find or create) the business client a chat task belongs to.

When a user says "сделай КП для Яндекса" or "заведи клиента Acme", the assistant
should attach the work to a real business client in the DB — creating one if it
does not exist yet — so client intelligence, analytics and history work against
that client instead of the anonymous Telegram transport identity.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from app.clients.name_extractor import extract_business_subject
from app.repositories.client_repository import ClientRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.client import ClientCreate
from app.schemas.project import ProjectCreate

logger = logging.getLogger(__name__)

BUSINESS_CLIENT_METADATA = {"type": "business", "source": "chat"}
DEFAULT_PROJECT_SUFFIX = "— общие задачи"
# Weak heuristic extractions may attach to an existing client, but must not invent one.
CREATE_CLIENT_MIN_CONFIDENCE = 0.7


@dataclass(frozen=True)
class ResolvedBusinessClient:
    client_id: UUID
    name: str
    project_id: UUID | None = None
    created: bool = False
    project_created: bool = False


class BusinessClientResolver:
    def __init__(
        self,
        client_repository: ClientRepository,
        *,
        project_repository: ProjectRepository | None = None,
        llm_gateway=None,
        model: str | None = None,
    ) -> None:
        self._clients = client_repository
        self._projects = project_repository
        self._llm = llm_gateway
        self._model = model

    async def resolve(
        self,
        user_input: str,
        *,
        trace_id: str = "-",
    ) -> ResolvedBusinessClient | None:
        subject = await extract_business_subject(
            user_input,
            llm_gateway=self._llm,
            model=self._model,
            trace_id=trace_id,
        )
        if not subject.is_usable or subject.name is None:
            return None

        allow_create = subject.confidence >= CREATE_CLIENT_MIN_CONFIDENCE
        client, created = await self._find_or_create_client(
            subject.name,
            allow_create=allow_create,
        )
        if client is None:
            logger.info(
                "business client skipped (weak extract, not found) | trace_id=%s name=%s confidence=%.2f",
                trace_id,
                subject.name,
                subject.confidence,
            )
            return None
        client_id = getattr(client, "id", None)
        if client_id is None:
            return None

        project_id: UUID | None = None
        project_created = False
        if self._projects is not None:
            project_id, project_created = await self._ensure_project(client)

        if created:
            logger.info(
                "business client auto-created from chat | trace_id=%s client_id=%s name=%s",
                trace_id,
                client_id,
                subject.name,
            )
        return ResolvedBusinessClient(
            client_id=client_id,
            name=getattr(client, "name", subject.name),
            project_id=project_id,
            created=created,
            project_created=project_created,
        )

    async def _find_or_create_client(self, name: str, *, allow_create: bool = True):
        existing = await self._clients.find_by_name(name)
        if existing is not None:
            return existing, False
        if not allow_create:
            return None, False
        client = await self._clients.create(
            ClientCreate(
                name=name,
                description="Автоматически создан из диалога",
                metadata=dict(BUSINESS_CLIENT_METADATA),
            )
        )
        return client, True

    async def _ensure_project(self, client):
        client_id = getattr(client, "id", None)
        if client_id is None:
            return None, False
        existing = await self._projects.list_by_client(client_id, limit=1)
        if existing:
            return getattr(existing[0], "id", None), False
        project = await self._projects.create(
            ProjectCreate(
                client_id=client_id,
                name=f"{getattr(client, 'name', 'Клиент')} {DEFAULT_PROJECT_SUFFIX}",
                description="Проект по умолчанию для задач из диалога",
            )
        )
        return getattr(project, "id", None), True
