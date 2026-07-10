import logging
from typing import Any

from app.agent_runtime.state.models import AgentState
from app.brand_style.models import BrandProfile
from app.document_creation.policies.creation_policy import should_render_document
from app.document_renderer.renderer import DocumentRendererService
from app.planning.policies.execution_policy import requires_approval
from app.skills.builtin.document_render_skill import DocumentRenderSkill

logger = logging.getLogger(__name__)

DOCUMENT_RENDER_NODE = "document_render"


class DocumentRenderNode:
    name = DOCUMENT_RENDER_NODE

    def __init__(
        self,
        render_skill: DocumentRenderSkill | None = None,
        renderer_service: DocumentRendererService | None = None,
    ) -> None:
        self._render_skill = render_skill or DocumentRenderSkill(
            renderer_service=renderer_service or DocumentRendererService()
        )

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        _log_node(state, self.name, "started")
        decision = state.get("decision") or {}
        creation_result = state.get("document_creation_result") or {}
        missing_information = creation_result.get("missing_information") or []
        ast_data = state.get("document_ast")
        metadata = state.get("metadata") or {}

        if not should_render_document(
            decision_action=decision.get("action"),
            missing_information=missing_information,
            has_document_ast=ast_data is not None,
        ):
            update = {
                "current_step": self.name,
                "status": "document_render_skipped",
                "render_result": None,
            }
            _log_node({**state, **update}, self.name, "skipped")
            return update

        if requires_approval(decision.get("action")) and not metadata.get("auto_approve"):
            update = {
                "current_step": self.name,
                "status": "waiting_render_approval",
                "render_result": None,
            }
            _log_node({**state, **update}, self.name, "waiting_approval")
            return update

        execution_context = state.get("execution_context") or {}
        brand_profile = None
        brand_raw = execution_context.get("brand_profile") or state.get("context", {}).get("brand_profile")
        if brand_raw:
            brand_profile = (
                brand_raw if isinstance(brand_raw, BrandProfile) else BrandProfile.model_validate(brand_raw)
            )

        document_type = (creation_result.get("metadata") or {}).get("document_type", "docx")
        output_format = document_type if document_type in {"docx", "pptx", "pdf"} else "docx"

        payload: dict[str, Any] = {
            "document_ast": ast_data,
            "brand_profile": brand_profile.model_dump(mode="json") if brand_profile else None,
            "output_format": output_format,
            "metadata": creation_result.get("metadata") or {},
        }

        client_id = execution_context.get("client_id") or state.get("context", {}).get("client_id")
        project_id = execution_context.get("project_id") or state.get("context", {}).get("project_id")
        if client_id and project_id:
            payload.update(
                {
                    "client_id": str(client_id),
                    "project_id": str(project_id),
                    "store_artifact": True,
                    "name": f"generated.{output_format}",
                }
            )

        skill_result = await self._render_skill.execute(payload)
        render_result = skill_result.get("render_result")

        update = {
            "current_step": self.name,
            "status": "rendered" if skill_result.get("status") == "completed" else "render_failed",
            "render_result": render_result,
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
