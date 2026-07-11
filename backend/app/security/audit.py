from app.security.manager import SecurityManager
from app.security.models import AuditEvent


class AuditLogger:
    """Records infrastructure audit events via SecurityManager."""

    def __init__(self, manager: SecurityManager) -> None:
        self._manager = manager

    async def log(
        self,
        *,
        actor: str,
        action: str,
        resource: str,
        trace_id: str = "-",
        metadata: dict | None = None,
    ) -> AuditEvent:
        return await self._manager.record_audit(
            actor=actor,
            action=action,
            resource=resource,
            trace_id=trace_id,
            metadata=metadata,
        )
