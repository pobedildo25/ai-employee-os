from typing import Any
from uuid import UUID

from app.client_intelligence.manager import ClientIntelligenceManager
from app.skills.base.skill import BaseSkill
from app.skills.models import Capability, SkillMetadata


class ClientIntelligenceSkill(BaseSkill):
    """Aggregates what the system knows about a client for downstream agents."""

    def __init__(
        self,
        manager: ClientIntelligenceManager | None = None,
        llm_gateway: Any | None = None,
    ) -> None:
        if manager is None:
            from app.client_intelligence.analyzer import ClientIntelligenceAnalyzer
            from app.client_intelligence.builder import ClientIntelligenceBuilder
            from app.llm.gateway import LLMGateway, create_llm_gateway

            gateway = llm_gateway or create_llm_gateway()
            if not isinstance(gateway, LLMGateway):
                raise TypeError("llm_gateway must be an LLMGateway instance")
            analyzer = ClientIntelligenceAnalyzer(gateway)
            manager = ClientIntelligenceManager(
                analyzer=analyzer,
                builder=ClientIntelligenceBuilder(analyzer),
            )
        self._manager = manager
        super().__init__(
            metadata=SkillMetadata(
                id="client_intelligence_skill",
                name="client_intelligence_skill",
                description="Агрегация знаний о клиенте (профиль, предпочтения, риски)",
                capabilities=["client_intelligence"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "client_id": {"type": "string"},
                        "context": {"type": "object"},
                        "use_llm": {"type": "boolean"},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "profile": {"type": "object"},
                        "memory_candidates": {"type": "array"},
                    },
                },
            ),
            capabilities=[
                Capability(
                    name="client_intelligence",
                    description="Профиль клиента: предпочтения, стиль, риски и рекомендации",
                    category="intelligence",
                    critical=False,
                ),
            ],
        )

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        client_id = payload.get("client_id")
        context = dict(payload.get("context") or {})
        if not client_id:
            client_id = context.get("client_id") or (context.get("client_context") or {}).get("id")
        if not client_id:
            return {
                "status": "failed",
                "skill": self.name(),
                "message": "client_id is required",
                "payload_keys": list(payload.keys()),
            }

        result = await self._manager.build_profile(
            client_id,
            execution_context=context,
            use_llm=bool(payload.get("use_llm", True)),
            project_id=payload.get("project_id") or context.get("project_id"),
            user_input=str(payload.get("goal") or payload.get("user_input") or context.get("user_input") or ""),
            trace_id=str(payload.get("trace_id") or "-"),
        )
        return {
            "status": "completed",
            "skill": self.name(),
            "profile": result.profile.model_dump(mode="json"),
            "confidence": result.profile.confidence,
            "memory_candidates": result.memory_candidates,
            "analysis_warnings": result.analysis_warnings,
            "metadata": result.metadata,
        }
