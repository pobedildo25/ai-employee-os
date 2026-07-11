from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import (
    get_agent_runtime,
    get_artifact_service,
    get_task_queue_manager,
    get_workspace_service,
)
from app.main import create_app
from app.models.enums import ArtifactStatus
from app.schemas.artifact import ArtifactCreate, ArtifactRead
from app.task_queue.manager import TaskQueueManager
from app.task_queue.repositories.task_queue_repository import InMemoryTaskQueueRepository
from app.workspace.manager import WorkspaceManager
from app.workspace.repositories.workspace_repository import InMemoryWorkspaceRepository
from app.workspace.service import WorkspaceService


class FakeArtifactService:
    def __init__(self) -> None:
        self._items: dict[UUID, ArtifactRead] = {}

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[ArtifactRead]:
        return list(self._items.values())[skip : skip + limit]

    async def list_by_project(
        self, project_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[ArtifactRead]:
        return [item for item in self._items.values() if item.project_id == project_id][
            skip : skip + limit
        ]

    async def get_by_id(self, artifact_id: UUID) -> ArtifactRead | None:
        return self._items.get(artifact_id)

    async def create_artifact(self, data: ArtifactCreate) -> ArtifactRead:
        now = datetime.now(timezone.utc)
        item = ArtifactRead.model_construct(
            id=uuid4(),
            client_id=data.client_id,
            project_id=data.project_id,
            name=data.name,
            artifact_type=data.artifact_type,
            description=data.description,
            status=data.status,
            storage_path=data.storage_path,
            mime_type=data.mime_type,
            size=data.size,
            metadata=data.metadata,
            created_by=data.created_by,
            created_at=now,
            updated_at=now,
        )
        self._items[item.id] = item
        return item

    async def upload_artifact(self, request, file_data: bytes, mime_type: str | None = None):
        return await self.create_artifact(
            ArtifactCreate(
                client_id=request.client_id,
                project_id=request.project_id,
                name=request.name,
                artifact_type=request.artifact_type,
                description=request.description,
                status=ArtifactStatus.UPLOADED,
                mime_type=mime_type,
                size=len(file_data),
                created_by=request.created_by,
                metadata=request.metadata,
            )
        )

    async def get_artifact_history(self, artifact_id: UUID) -> list:
        return []


class FakeAgentRuntime:
    async def execute(
        self,
        user_input: str,
        *,
        trace_id: str | None = None,
        context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "execution_id": "exec-test-1",
            "trace_id": trace_id or "trace-test-1",
            "status": "completed",
            "current_step": "finish",
            "result": {"message": f"Handled: {user_input}"},
            "decision": {"action": "respond"},
            "understanding": {"goal": user_input},
        }


@pytest.fixture
def artifact_service() -> FakeArtifactService:
    return FakeArtifactService()


@pytest.fixture
def workspace_service() -> WorkspaceService:
    return WorkspaceService(WorkspaceManager(InMemoryWorkspaceRepository()))


@pytest.fixture
def queue_manager() -> TaskQueueManager:
    return TaskQueueManager(InMemoryTaskQueueRepository())


@pytest.fixture
async def api_client(
    artifact_service: FakeArtifactService,
    workspace_service: WorkspaceService,
    queue_manager: TaskQueueManager,
):
    app = create_app()
    app.dependency_overrides[get_artifact_service] = lambda: artifact_service
    app.dependency_overrides[get_workspace_service] = lambda: workspace_service
    app.dependency_overrides[get_task_queue_manager] = lambda: queue_manager
    app.dependency_overrides[get_agent_runtime] = lambda: FakeAgentRuntime()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_openapi_and_router(api_client: AsyncClient) -> None:
    docs = await api_client.get("/docs")
    assert docs.status_code == 200

    response = await api_client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/health" in paths
    assert "/api/v1/ready" in paths
    assert "/api/v1/execution/run" in paths
    assert "/api/v1/workspace/open" in paths
    assert "/api/v1/artifacts" in paths
    assert "/api/v1/tasks/background" in paths
    assert "/api/v1/documents/{artifact_id}/process" in paths
    assert "/api/v1/clients" in paths
    assert "/api/v1/clients/{client_id}/intelligence" in paths
    assert "/api/v1/clients/{client_id}/intelligence/analyze" in paths
    assert "/api/v1/analytics/run" in paths
    assert "/api/v1/analytics/client/{client_id}" in paths


@pytest.mark.asyncio
async def test_health_v1(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "ai-employee-os"
    assert body["status"] == "ok"
    assert "services" not in body


@pytest.mark.asyncio
async def test_execution_run(api_client: AsyncClient) -> None:
    response = await api_client.post(
        "/api/v1/execution/run",
        json={"user_input": "Prepare a proposal", "metadata": {"source": "test"}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["execution_id"] == "exec-test-1"
    assert body["status"] == "completed"
    assert body["result"]["message"] == "Handled: Prepare a proposal"


@pytest.mark.asyncio
async def test_workspace_open_and_get(api_client: AsyncClient) -> None:
    client_id = uuid4()
    response = await api_client.post(
        "/api/v1/workspace/open",
        json={"client_id": str(client_id), "open_session": True},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["client_id"] == str(client_id)
    assert body["active_session_id"] is not None

    get_response = await api_client.get(f"/api/v1/workspace/{body['workspace_id']}")
    assert get_response.status_code == 200
    assert get_response.json()["workspace_id"] == body["workspace_id"]


@pytest.mark.asyncio
async def test_artifacts_create_and_get(api_client: AsyncClient) -> None:
    client_id = uuid4()
    project_id = uuid4()
    response = await api_client.post(
        "/api/v1/artifacts",
        data={
            "client_id": str(client_id),
            "project_id": str(project_id),
            "name": "brief.docx",
            "artifact_type": "document",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "brief.docx"

    get_response = await api_client.get(f"/api/v1/artifacts/{body['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == body["id"]


@pytest.mark.asyncio
async def test_background_tasks(
    api_client: AsyncClient,
    queue_manager: TaskQueueManager,
) -> None:
    await queue_manager.enqueue(task_type="demo", payload={"n": 1}, priority=5)
    response = await api_client.get("/api/v1/tasks/background")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["task_type"] == "demo"
    assert body[0]["status"] == "QUEUED"
