import logging
from typing import Any
from uuid import UUID

from app.agent_runtime.state.models import AgentState
from app.knowledge.migration import KnowledgeMigrationService

logger = logging.getLogger(__name__)

KNOWLEDGE_MIGRATION_NODE = "knowledge_migration"


class KnowledgeMigrationNode:
    """LangGraph-ready node for knowledge migration — not wired into main workflow yet."""

    name = KNOWLEDGE_MIGRATION_NODE

    def __init__(self, migration_service: KnowledgeMigrationService) -> None:
        self._migration_service = migration_service

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        _log_node(state, self.name, "started")
        context = state.get("context") or {}
        execution_context = state.get("execution_context") or {}
        metadata = state.get("metadata") or {}

        client_id = _to_uuid(
            metadata.get("client_id")
            or context.get("client_id")
            or execution_context.get("client_id")
        )
        artifacts = metadata.get("artifacts") or context.get("artifacts") or []

        if client_id is None:
            update = {
                "current_step": self.name,
                "status": "knowledge_migration_skipped",
                "knowledge_migration_result": None,
            }
            _log_node({**state, **update}, self.name, "skipped")
            return update

        result = await self._migration_service.migrate(
            client_id=client_id,
            artifacts=list(artifacts),
            context=execution_context,
            file_bytes_by_artifact=metadata.get("file_bytes_by_artifact") or {},
            persist=bool(metadata.get("persist_knowledge", True)),
            trace_id=state.get("trace_id", "-"),
        )

        update = {
            "current_step": self.name,
            "status": "knowledge_migrated",
            "knowledge_migration_result": result.model_dump(mode="json"),
        }
        _log_node({**state, **update}, self.name, "completed")
        return update


def _log_node(state: AgentState, node_name: str, status: str) -> None:
    logger.info(
        "graph node execution | execution_id=%s trace_id=%s node_name=%s status=%s",
        state.get("execution_id", "-"),
        state.get("trace_id", "-"),
        node_name,
        status,
    )


def _to_uuid(value: object | None) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except ValueError:
        return None
