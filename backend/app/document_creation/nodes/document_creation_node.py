import logging
from typing import Any
from uuid import UUID

from app.agent_runtime.state.models import AgentState
from app.brand_style.models import BrandProfile
from app.document_creation.creator import DocumentCreator
from app.document_creation.memory_preparer import prepare_document_creation_memory_items
from app.document_creation.models import DocumentCreationRequest
from app.document_creation.policies.creation_policy import should_create_document
from app.skills.registry import CapabilityRegistry

logger = logging.getLogger(__name__)

DOCUMENT_CREATION_NODE = "document_creation"


class DocumentCreationNode:
    name = DOCUMENT_CREATION_NODE

    def __init__(
        self,
        creator: DocumentCreator,
        registry: CapabilityRegistry,
    ) -> None:
        self._creator = creator
        self._registry = registry

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        _log_node(state, self.name, "started")
        decision = state.get("decision") or {}
        action = decision.get("action")

        if not should_create_document(action):
            update = {
                "current_step": self.name,
                "status": "document_creation_skipped",
                "document_creation_result": None,
                "document_ast": None,
            }
            _log_node({**state, **update}, self.name, "skipped")
            return update

        understanding = state.get("understanding") or {}
        execution_context = state.get("execution_context") or {"user_input": state.get("user_input", "")}
        brand_profile = None
        brand_raw = execution_context.get("brand_profile") or state.get("context", {}).get("brand_profile")
        if brand_raw:
            brand_profile = (
                brand_raw if isinstance(brand_raw, BrandProfile) else BrandProfile.model_validate(brand_raw)
            )

        request = DocumentCreationRequest(
            user_goal=understanding.get("goal") or state.get("user_input", ""),
            context=execution_context,
            brand_profile=brand_profile,
            document_type=state.get("metadata", {}).get("document_type"),
            requirements=list(understanding.get("required_capabilities") or []),
        )

        result = await self._creator.create(
            request,
            available_capabilities=self._registry.list_available_for_prompt(),
            trace_id=state.get("trace_id", "-"),
        )

        client_id = execution_context.get("client_id") or state.get("context", {}).get("client_id")
        project_id = execution_context.get("project_id") or state.get("context", {}).get("project_id")
        memory_items = prepare_document_creation_memory_items(
            result,
            client_id=_to_uuid(client_id),
            project_id=_to_uuid(project_id),
            session_id=state.get("metadata", {}).get("session_id"),
        )

        update = {
            "current_step": self.name,
            "status": "document_created" if result.document_ast else "document_creation_incomplete",
            "document_creation_result": result.model_dump(mode="json"),
            "document_ast": result.document_ast.model_dump(mode="json") if result.document_ast else None,
            "memory_candidates": [item.model_dump(mode="json") for item in memory_items],
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
    return UUID(str(value))
