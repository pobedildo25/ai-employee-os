import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.mark.asyncio
async def test_health_and_ready_endpoints() -> None:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        health = await client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        ready = await client.get("/ready")
        assert ready.status_code in {200, 503}
        body = ready.json()
        assert "postgres" in body.get("services", body)
        assert "redis" in body.get("services", body)

        api_health = await client.get("/api/v1/health")
        assert api_health.status_code == 200
        api_ready = await client.get("/api/v1/ready")
        assert api_ready.status_code in {200, 503}
