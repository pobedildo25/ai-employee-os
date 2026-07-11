from app.security.models import Role
from app.security.permissions import has_permission


class AccessPolicy:
    """Infrastructure access checks — no business decisions."""

    def allow(
        self,
        *,
        role: Role,
        granted: list[str] | None,
        required: str,
    ) -> bool:
        return has_permission(role=role, granted=granted, required=required)
