"""Sprint D (P2) focused tests: idempotency, Redis rate limit, tenant ACL, artifacts."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request

from app.adapters.telegram.idempotency import claim_telegram_update
from app.schemas.artifact import ArtifactUploadRequest
from app.security.manager import SecurityManager
from app.security.middleware import SecurityMiddleware
from app.security.models import Role, SecurityPrincipal
from app.security.providers.in_memory_provider import InMemorySecurityProvider
from app.security.rate_limit import RateLimiter, RedisRateLimiter
from app.security.tenant import enforce_client_access, parse_client_id_from_metadata, scoped_client_id
from app.services.artifact_service import ArtifactService, sanitize_storage_name
from tests.conftest import FakeArtifactRepository, FakeArtifactVersionRepository, InMemoryStorage


class FakeRedis:
    def __init__(self) -> None:
        self._kv: dict[str, str] = {}
        self._ttl: dict[str, int] = {}

    async def set(
        self,
        key: str,
        value: str,
        ex: int | None = None,
        nx: bool = False,
    ) -> bool | None:
        if nx and key in self._kv:
            return None
        self._kv[key] = value
        if ex is not None:
            self._ttl[key] = ex
        return True

    async def get(self, key: str) -> str | None:
        return self._kv.get(key)

    async def incr(self, key: str) -> int:
        current = int(self._kv.get(key, "0")) + 1
        self._kv[key] = str(current)
        return current

    async def expire(self, key: str, seconds: int) -> bool:
        if key not in self._kv:
            return False
        self._ttl[key] = seconds
        return True


@pytest.mark.asyncio
async def test_telegram_idempotency_claim() -> None:
    redis = FakeRedis()
    assert await claim_telegram_update(redis, 42) is True
    assert await claim_telegram_update(redis, 42) is False
    assert await claim_telegram_update(None, 99) is True
    assert "telegram:update:42" in redis._kv


@pytest.mark.asyncio
async def test_redis_rate_limiter_fixed_window() -> None:
    redis = FakeRedis()
    limiter = RedisRateLimiter(redis, limit=2, window_seconds=60)
    assert await limiter.allow("ip-1")
    assert await limiter.allow("ip-1")
    assert not await limiter.allow("ip-1")
    assert await limiter.allow("ip-2")


@pytest.mark.asyncio
async def test_redis_rate_limiter_falls_back_on_error() -> None:
    class BrokenRedis:
        async def incr(self, key: str) -> int:
            raise RuntimeError("down")

        async def expire(self, key: str, seconds: int) -> bool:
            raise RuntimeError("down")

    limiter = RedisRateLimiter(BrokenRedis(), limit=1, window_seconds=60)
    assert await limiter.allow("x")
    assert not await limiter.allow("x")


def test_tenant_scope_helpers() -> None:
    client_a = uuid4()
    admin = SecurityPrincipal(actor="a", role=Role.ADMIN, client_id=client_a)
    scoped = SecurityPrincipal(actor="u", role=Role.USER, client_id=client_a)
    unscoped = SecurityPrincipal(actor="u", role=Role.USER, client_id=None)

    assert scoped_client_id(admin) is None
    assert scoped_client_id(unscoped) is None
    assert scoped_client_id(scoped) == client_a

    enforce_client_access(scoped, client_a)
    with pytest.raises(HTTPException) as exc:
        enforce_client_access(scoped, uuid4())
    assert exc.value.status_code == 403

    assert parse_client_id_from_metadata({"client_id": str(client_a)}) == client_a
    assert parse_client_id_from_metadata({"tenant_client_id": str(client_a)}) == client_a
    assert parse_client_id_from_metadata({}) is None


@pytest.mark.asyncio
async def test_validate_api_key_copies_client_scope() -> None:
    manager = SecurityManager(InMemorySecurityProvider(), rate_limiter=RateLimiter(limit=100, window_seconds=60))
    client_id = uuid4()
    created = await manager.create_api_key(
        name="tenant",
        role=Role.USER,
        metadata={"client_id": str(client_id)},
    )
    principal = await manager.validate_api_key(created.api_key)
    assert principal is not None
    assert principal.client_id == client_id


@pytest.mark.asyncio
async def test_tenant_acl_clients_api() -> None:
    manager = SecurityManager(InMemorySecurityProvider(), rate_limiter=RateLimiter(limit=100, window_seconds=60))
    client_a = uuid4()
    client_b = uuid4()
    created = await manager.create_api_key(
        name="scoped",
        role=Role.USER,
        metadata={"client_id": str(client_a)},
    )

    from starlette.requests import Request

    app = FastAPI()

    @app.get("/mine")
    async def mine(request: Request) -> dict:
        principal = request.state.principal
        enforce_client_access(principal, client_a)
        return {"ok": True}

    @app.get("/other")
    async def other(request: Request) -> dict:
        principal = request.state.principal
        enforce_client_access(principal, client_b)
        return {"ok": True}

    app.add_middleware(SecurityMiddleware, security_manager=manager, enabled=True)
    app.state.security_manager = manager

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ok = await client.get("/mine", headers={"X-API-Key": created.api_key})
        assert ok.status_code == 200
        denied = await client.get("/other", headers={"X-API-Key": created.api_key})
        assert denied.status_code == 403


def test_sanitize_storage_name() -> None:
    assert ".." not in sanitize_storage_name("../etc/passwd")
    assert "/" not in sanitize_storage_name("a/b\\c")
    assert "\x00" not in sanitize_storage_name("x\x00y")
    assert sanitize_storage_name("My File.pdf") == "my_file.pdf"
    assert sanitize_storage_name("!!!") == "artifact"


@pytest.mark.asyncio
async def test_artifact_upload_compensation_on_db_failure() -> None:
    storage = InMemoryStorage()
    repo = FakeArtifactRepository()

    async def boom(data):  # noqa: ANN001
        raise RuntimeError("db down")

    repo.create = boom  # type: ignore[method-assign]
    versions = FakeArtifactVersionRepository(repo)
    service = ArtifactService(repo, versions, storage)

    request = ArtifactUploadRequest(
        client_id=uuid4(),
        project_id=uuid4(),
        name="safe-doc",
        artifact_type="document",
    )
    with pytest.raises(RuntimeError, match="db down"):
        await service.upload_artifact(request, b"payload", "text/plain")

    assert storage._objects == {}
