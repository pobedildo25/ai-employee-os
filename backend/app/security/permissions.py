from app.security.models import Permission, Role

# Infrastructure permission codes — no business rules.
DOCUMENTS_CREATE = "documents:create"
DOCUMENTS_READ = "documents:read"
EXECUTION_RUN = "execution:run"
WORKSPACE_READ = "workspace:read"
SECURITY_KEYS_MANAGE = "security:keys"
SECURITY_AUDIT_READ = "security:audit"
ARTIFACTS_WRITE = "artifacts:write"
ARTIFACTS_READ = "artifacts:read"

ROLE_PERMISSIONS: dict[Role, set[str]] = {
    Role.ADMIN: {
        DOCUMENTS_CREATE,
        DOCUMENTS_READ,
        EXECUTION_RUN,
        WORKSPACE_READ,
        SECURITY_KEYS_MANAGE,
        SECURITY_AUDIT_READ,
        ARTIFACTS_WRITE,
        ARTIFACTS_READ,
    },
    Role.USER: {
        DOCUMENTS_CREATE,
        DOCUMENTS_READ,
        EXECUTION_RUN,
        WORKSPACE_READ,
        ARTIFACTS_WRITE,
        ARTIFACTS_READ,
    },
    Role.SERVICE: {
        DOCUMENTS_READ,
        EXECUTION_RUN,
        WORKSPACE_READ,
        ARTIFACTS_READ,
    },
}


def permissions_for_role(role: Role) -> list[str]:
    return sorted(ROLE_PERMISSIONS.get(role, set()))


def has_permission(
    *,
    role: Role,
    granted: list[str] | None,
    required: str | Permission,
) -> bool:
    code = required.code if isinstance(required, Permission) else required
    effective = set(granted or []) | ROLE_PERMISSIONS.get(role, set())
    return code in effective or f"{code.split(':')[0]}:*" in effective
