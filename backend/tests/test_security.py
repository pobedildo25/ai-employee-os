import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_security_manager
from app.main import create_app
from app.security.manager import SecurityManager
from app.security.middleware import SecurityMiddleware
from app.security.models import APIKeyStatus, Role, SecurityPrincipal
from app.security.permissions import DOCUMENTS_CREATE, EXECUTION_RUN, has_permission
from app.security.providers.api_key_provider import APIKeyProvider
from app.security.providers.in_memory_provider import InMemorySecurityProvider
from app.security.rate_limit import RateLimiter
from app.security.secrets import SecretsManager
from fastapi import FastAPI


@pytest.fixture
def manager() -> SecurityManager:
    return SecurityManager(
        InMemorySecurityProvider(),
        rate_limiter=RateLimiter(limit=5, window_seconds=60),
        secrets=SecretsManager(),
    )


@pytest.mark.asyncio
async def test_api_key_generation_and_hash(manager: SecurityManager) -> None:
    created = await manager.create_api_key(name="test-key", role=Role.ADMIN)
    assert created.api_key.startswith("aeo_")
    assert created.status == APIKeyStatus.ACTIVE

    principal = await manager.validate_api_key(created.api_key)
    assert principal is not None
    assert principal.role == Role.ADMIN
    assert principal.api_key_id == created.id
    assert await manager.validate_api_key("aeo_invalid") is None

    info = await manager.get_key_info(created.id)
    assert info is not None
    assert info.name == "test-key"
    assert "api_key" not in info.model_dump()
    assert "key_hash" not in info.model_dump()


@pytest.mark.asyncio
async def test_revoke(manager: SecurityManager) -> None:
    created = await manager.create_api_key(name="revoke-me")
    revoked = await manager.revoke_api_key(created.id)
    assert revoked is not None
    assert revoked.status == APIKeyStatus.REVOKED
    assert await manager.validate_api_key(created.api_key) is None


def test_permissions() -> None:
    assert has_permission(role=Role.ADMIN, granted=[], required=DOCUMENTS_CREATE)
    assert has_permission(role=Role.USER, granted=[], required=EXECUTION_RUN)
    assert not has_permission(role=Role.SERVICE, granted=[], required="security:keys")

    principal = SecurityPrincipal(actor="u", role=Role.USER, permissions=[DOCUMENTS_CREATE])
    manager = SecurityManager()
    assert manager.check_permission(principal, DOCUMENTS_CREATE)
    assert not manager.check_permission(principal, "security:keys")


@pytest.mark.asyncio
async def test_audit_events(manager: SecurityManager) -> None:
    event = await manager.record_audit(
        actor="api_key:1",
        action="execution.run",
        resource="/api/v1/execution/run",
        trace_id="trace-x",
        metadata={"token": "supersecretvalue"},
    )
    assert event.actor == "api_key:1"
    assert event.action == "execution.run"
    assert event.metadata.get("token") == "***"
    events = await manager.list_audit()
    assert len(events) == 1


@pytest.mark.asyncio
async def test_rate_limiter() -> None:
    limiter = RateLimiter(limit=2, window_seconds=60)
    assert await limiter.allow("user-a")
    assert await limiter.allow("user-a")
    assert not await limiter.allow("user-a")
    assert await limiter.allow("user-b")


def test_secrets_redaction() -> None:
    secrets = SecretsManager()
    text = secrets.redact("Authorization bearer abcdefghijklmnop token=supersecret")
    assert "***" in text


@pytest.mark.asyncio
async def test_security_api(manager: SecurityManager) -> None:
    app = create_app()
    app.state.security_manager = manager
    app.dependency_overrides[get_security_manager] = lambda: manager

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post(
            "/api/v1/security/keys",
            json={"name": "ci-key", "role": "USER"},
        )
        assert created.status_code == 201
        body = created.json()
        assert body["api_key"].startswith("aeo_")
        raw = body["api_key"]
        key_id = body["id"]

        admin_rejected = await client.post(
            "/api/v1/security/keys",
            json={"name": "admin-key", "role": "ADMIN"},
        )
        assert admin_rejected.status_code == 401

        listed = await client.get("/api/v1/security/keys")
        assert listed.status_code == 200
        assert any(item["id"] == key_id for item in listed.json())

        audit = await client.get("/api/v1/security/audit")
        assert audit.status_code == 200
        assert any(item["action"] == "api_access" for item in audit.json())

        revoked = await client.delete(f"/api/v1/security/keys/{key_id}")
        assert revoked.status_code == 200
        assert revoked.json()["status"] == "revoked"
        assert await manager.validate_api_key(raw) is None

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_middleware_rejects_when_enabled(manager: SecurityManager) -> None:
    inner = FastAPI()

    @inner.get("/secure")
    async def secure() -> dict:
        return {"ok": True}

    inner.add_middleware(SecurityMiddleware, security_manager=manager, enabled=True)
    inner.state.security_manager = manager

    transport = ASGITransport(app=inner)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        denied = await client.get("/secure")
        assert denied.status_code == 401

        created = await manager.create_api_key(name="ok", role=Role.SERVICE)
        allowed = await client.get("/secure", headers={"X-API-Key": created.api_key})
        assert allowed.status_code == 200


def test_api_key_provider_hash_stable() -> None:
    raw = "aeo_test_key_value_1234567890"
    assert APIKeyProvider.hash_key(raw) == APIKeyProvider.hash_key(raw)
    assert APIKeyProvider.hash_key(raw) != raw


def test_create_security_store_uses_in_memory_outside_production() -> None:
    from app.core.config import Settings
    from app.main import create_security_store

    store = create_security_store(Settings(app_env="development"))
    assert isinstance(store, InMemorySecurityProvider)


def test_create_security_store_raises_in_production_when_redis_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import Settings
    from app.main import create_security_store

    def _boom(_settings: Settings):
        raise ConnectionError("redis down")

    monkeypatch.setattr("app.database.redis.get_redis_client", _boom)

    with pytest.raises(RuntimeError, match="Redis security store is required"):
        create_security_store(Settings(app_env="production"))


def test_build_rate_limiter_raises_in_production_when_redis_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import Settings
    from app.main import _build_rate_limiter

    def _boom(_settings: Settings):
        raise ConnectionError("redis down")

    monkeypatch.setattr("app.database.redis.get_redis_client", _boom)

    with pytest.raises(RuntimeError, match="Redis rate limiter is required"):
        _build_rate_limiter(Settings(app_env="production"))


def test_stage_zero_contract_files_exist() -> None:
    from pathlib import Path

    docs = Path(__file__).resolve().parents[2] / "docs"
    for name in ("PRODUCTION_CONTRACT.md", "DECISION_CONTRACT.md", "CAPABILITY_MATRIX.md"):
        path = docs / name
        assert path.is_file(), f"missing Stage 0 contract: {name}"
        assert path.stat().st_size > 0
