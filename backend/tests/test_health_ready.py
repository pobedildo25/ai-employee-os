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
    assert body["status"] in {"ready", "degraded", "not_ready"}
    assert "services" in body
    assert set(body["services"]) >= {"postgres", "redis", "qdrant", "minio"}
    if body["status"] == "not_ready":
        assert response.status_code == 503
    else:
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_readiness_degraded_when_optional_down(monkeypatch) -> None:
    from app.api import health as health_module

    async def postgres_ok(_settings):
        return True, "ok"

    async def redis_ok(_settings):
        return True, "ok"

    def qdrant_down(_settings):
        return False, "down"

    def minio_down():
        return False, "down"

    monkeypatch.setattr(health_module, "check_postgres", postgres_ok)
    monkeypatch.setattr(health_module, "check_redis", redis_ok)
    monkeypatch.setattr(health_module, "check_qdrant", qdrant_down)
    monkeypatch.setattr(health_module, "check_minio", minio_down)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"


@pytest.mark.asyncio
async def test_v1_health_and_ready(client: AsyncClient) -> None:
    health = await client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    ready = await client.get("/api/v1/ready")
    assert ready.status_code in {200, 503}
    assert "services" in ready.json()
