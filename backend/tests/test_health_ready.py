import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
async def client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_liveness_health(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "ai-employee-os"
    assert "services" not in body


@pytest.mark.asyncio
async def test_readiness_ready(client: AsyncClient) -> None:
    response = await client.get("/ready")
    assert response.status_code in {200, 503}
    body = response.json()
    assert body["status"] in {"ready", "not_ready"}
    assert "services" in body
    assert set(body["services"]) >= {"postgres", "redis", "qdrant", "minio"}


@pytest.mark.asyncio
async def test_v1_health_and_ready(client: AsyncClient) -> None:
    health = await client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    ready = await client.get("/api/v1/ready")
    assert ready.status_code in {200, 503}
    assert "services" in ready.json()
