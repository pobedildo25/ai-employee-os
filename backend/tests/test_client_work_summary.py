from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.clients.work_summary import ClientWorkSummaryService, detect_client_status_query


@dataclass
class StoredClient:
    id: UUID
    name: str
    metadata_: dict[str, Any] | None = None


@dataclass
class StoredProject:
    id: UUID
    client_id: UUID
    name: str
    status: str = "active"


@dataclass
class StoredArtifact:
    id: UUID
    project_id: UUID
    name: str
    artifact_type: str = "docx"
    status: str = "ready"


class FakeClients:
    def __init__(self, clients: list[StoredClient]) -> None:
        self._clients = clients

    async def find_by_name(self, name: str) -> StoredClient | None:
        target = name.strip().casefold()
        for client in self._clients:
            if client.name.casefold() == target:
                return client
        return None


class FakeProjects:
    def __init__(self, projects: list[StoredProject]) -> None:
        self._projects = projects

    async def list_by_client(self, client_id: UUID, skip: int = 0, limit: int = 100) -> list[StoredProject]:
        return [p for p in self._projects if p.client_id == client_id][skip : skip + limit]


class FakeArtifacts:
    def __init__(self, artifacts: list[StoredArtifact]) -> None:
        self._artifacts = artifacts

    async def list_by_project(self, project_id: UUID, skip: int = 0, limit: int = 100) -> list[StoredArtifact]:
        return [a for a in self._artifacts if a.project_id == project_id][skip : skip + limit]


@pytest.mark.parametrize(
    "text,expected_name",
    [
        ("что сделано по клиенту Яндекс", "Яндекс"),
        ("покажи проекты Acme", "Acme"),
        ("какие проекты у клиента Сбер", "Сбер"),
        ("сделай КП для Яндекса", None),  # not a status query
        ("привет", None),
    ],
)
def test_detect_client_status_query(text: str, expected_name: str | None) -> None:
    result = detect_client_status_query(text)
    if expected_name is None:
        assert result is None
    else:
        assert result is not None
        assert result.lower().startswith(expected_name.lower()[:4])


@pytest.mark.asyncio
async def test_summarize_aggregates_projects_and_artifacts() -> None:
    client = StoredClient(id=uuid4(), name="Яндекс")
    project = StoredProject(id=uuid4(), client_id=client.id, name="Яндекс — общие задачи")
    artifact = StoredArtifact(id=uuid4(), project_id=project.id, name="КП.docx")
    service = ClientWorkSummaryService(
        FakeClients([client]),
        project_repository=FakeProjects([project]),
        artifact_repository=FakeArtifacts([artifact]),
    )

    summary = await service.summarize("яндекс")

    assert summary is not None
    assert summary.name == "Яндекс"
    assert len(summary.projects) == 1
    assert len(summary.artifacts) == 1
    reply = service.format_reply(summary)
    assert "Яндекс" in reply
    assert "КП.docx" in reply


@pytest.mark.asyncio
async def test_summarize_unknown_client_returns_none() -> None:
    service = ClientWorkSummaryService(FakeClients([]))

    assert await service.summarize("Неизвестный") is None


@pytest.mark.asyncio
async def test_format_reply_empty_client() -> None:
    client = StoredClient(id=uuid4(), name="Acme")
    service = ClientWorkSummaryService(
        FakeClients([client]),
        project_repository=FakeProjects([]),
        artifact_repository=FakeArtifacts([]),
    )

    summary = await service.summarize("Acme")
    reply = service.format_reply(summary)

    assert "пока нет проектов" in reply
