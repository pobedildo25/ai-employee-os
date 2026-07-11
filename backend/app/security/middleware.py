from collections.abc import Callable
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.security.manager import SecurityManager
from app.security.models import SecurityPrincipal

EXEMPT_PREFIXES = (
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
)


class SecurityMiddleware(BaseHTTPMiddleware):
    """Checks API key, attaches actor, writes audit — no business logic."""

    def __init__(
        self,
        app: Any,
        *,
        security_manager: SecurityManager,
        enabled: bool = False,
        header_name: str = "X-API-Key",
    ) -> None:
        super().__init__(app)
        self._security = security_manager
        self._enabled = enabled
        self._header_name = header_name

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if any(path == prefix or path.startswith(prefix + "/") for prefix in EXEMPT_PREFIXES):
            request.state.principal = SecurityPrincipal(actor="anonymous", permissions=[])
            return await call_next(request)

        manager: SecurityManager = getattr(request.app.state, "security_manager", self._security)
        trace_id = getattr(request.state, "trace_id", None) or request.headers.get("X-Trace-Id") or "-"
        request.state.trace_id = trace_id
        raw_key = request.headers.get(self._header_name)
        identifier = raw_key or request.client.host if request.client else "unknown"

        if not manager.rate_limiter.allow(str(identifier)):
            await manager.record_audit(
                actor="anonymous",
                action="rate_limited",
                resource=path,
                trace_id=trace_id,
                metadata={"method": request.method},
            )
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})

        principal: SecurityPrincipal | None = None
        if raw_key:
            principal = await manager.validate_api_key(raw_key)

        if self._enabled:
            if principal is None:
                await manager.record_audit(
                    actor="anonymous",
                    action="auth_failed",
                    resource=path,
                    trace_id=trace_id,
                    metadata={"method": request.method},
                )
                return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})
        else:
            principal = principal or SecurityPrincipal(actor="anonymous", permissions=[])

        request.state.principal = principal
        await manager.record_audit(
            actor=principal.actor,
            action="api_access",
            resource=path,
            trace_id=trace_id,
            metadata={"method": request.method},
        )
        return await call_next(request)
