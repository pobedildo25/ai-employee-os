from typing import Any

from app.document_creation.creator import DocumentCreator
from app.document_creation.memory_preparer import prepare_document_creation_memory_items
from app.document_creation.models import DocumentCreationRequest, DocumentCreationResult
from app.skills.base.skill import BaseSkill
from app.skills.models import Capability, SkillMetadata


class DocumentCreationSkill(BaseSkill):
    """Creates document AST structure from user goal and context."""

    def __init__(
        self,
        creator: DocumentCreator | None = None,
        llm_gateway: Any | None = None,
    ) -> None:
        if creator is None:
            from app.document_creation.generators.ast_generator import DocumentASTGenerator
            from app.llm.gateway import LLMGateway, create_llm_gateway

            gateway = llm_gateway or create_llm_gateway()
            if not isinstance(gateway, LLMGateway):
                raise TypeError("llm_gateway must be an LLMGateway instance")
            creator = DocumentCreator(DocumentASTGenerator(gateway))
        self._creator = creator
        super().__init__(
            metadata=SkillMetadata(
                id="document_creation_skill",
                name="document_creation_skill",
                description="Создание структуры документа из пользовательской задачи",
                capabilities=["document_creation"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "goal": {"type": "string"},
                        "context": {"type": "object"},
                        "brand_profile": {"type": "object"},
                        "document_type": {"type": "string"},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "document_creation_result": {"type": "object"},
                    },
                },
            ),
            capabilities=[
                Capability(
                    name="document_creation",
                    description="Генерация структуры документа (AST) из задачи пользователя",
                    category="document",
                ),
            ],
        )

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        goal = payload.get("goal") or payload.get("user_goal") or payload.get("description")
        if not goal:
            return {
                "status": "failed",
                "skill": self.name(),
                "message": "goal is required for document creation",
                "payload_keys": list(payload.keys()),
            }

        brand_profile = None
        brand_raw = payload.get("brand_profile")
        if brand_raw is not None:
            from app.brand_style.models import BrandProfile

            brand_profile = (
                brand_raw if isinstance(brand_raw, BrandProfile) else BrandProfile.model_validate(brand_raw)
            )

        context = dict(payload.get("context") or {})
        agency_profile = (
            payload.get("agency_profile")
            or payload.get("agency_context")
            or context.get("agency_context")
        )

        request = DocumentCreationRequest(
            user_goal=str(goal),
            context=context,
            brand_profile=brand_profile,
            agency_profile=dict(agency_profile) if isinstance(agency_profile, dict) else None,
            document_type=payload.get("document_type"),
            requirements=list(payload.get("requirements") or []),
        )

        result = await self._creator.create(
            request,
            available_capabilities=list(payload.get("available_capabilities") or []),
            trace_id=str(payload.get("trace_id") or "-"),
        )
        memory_items = prepare_document_creation_memory_items(
            result,
            client_id=payload.get("client_id"),
            project_id=payload.get("project_id"),
            session_id=payload.get("session_id"),
        )

        return {
            "status": "completed" if result.document_ast else "incomplete",
            "skill": self.name(),
            "document_creation_result": result.model_dump(mode="json"),
            "document_ast": result.document_ast.model_dump(mode="json") if result.document_ast else None,
            "missing_information": result.missing_information,
            "memory_candidates": [item.model_dump(mode="json") for item in memory_items],
        }
