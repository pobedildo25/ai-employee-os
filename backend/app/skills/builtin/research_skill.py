from typing import Any

from app.research.manager import ResearchManager
from app.research.models import ResearchRequest, ResearchType
from app.skills.base.skill import BaseSkill
from app.skills.models import Capability, SkillMetadata


class ResearchSkill(BaseSkill):
    """Research & web intelligence aggregation with DocumentAST for reports/strategy handoff."""

    def __init__(
        self,
        manager: ResearchManager | None = None,
        llm_gateway: Any | None = None,
    ) -> None:
        if manager is None:
            from app.core.config import get_settings
            from app.llm.gateway import LLMGateway, create_llm_gateway
            from app.research.providers.mock_provider import MockProvider
            from app.research.providers.openrouter_online_provider import OpenRouterOnlineProvider
            from app.research.providers.search_provider import SearchProvider
            from app.research.researcher import Researcher

            settings = get_settings()
            gateway = llm_gateway or create_llm_gateway(settings)
            if not isinstance(gateway, LLMGateway):
                raise TypeError("llm_gateway must be an LLMGateway instance")
            if (
                settings.research_online_enabled
                and settings.openrouter_api_key
                and settings.openrouter_api_key != "change-me"
            ):
                backend = OpenRouterOnlineProvider(
                    gateway,
                    model=settings.research_online_model,
                )
            else:
                backend = MockProvider()
            manager = ResearchManager(
                researcher=Researcher(SearchProvider(backend), llm_gateway=gateway),
                llm_gateway=gateway,
                provider=SearchProvider(backend),
            )
        self._manager = manager
        super().__init__(
            metadata=SkillMetadata(
                id="research_skill",
                name="research_skill",
                description="Внешнее исследование рынка/конкурентов и research reports (AST)",
                capabilities=["research"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "research_type": {"type": "string"},
                        "type": {"type": "string"},
                        "context": {"type": "object"},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "research_result": {"type": "object"},
                        "document_ast": {"type": "object"},
                    },
                },
            ),
            capabilities=[
                Capability(
                    name="research",
                    description="Исследование рынка, конкурентов и внешних источников",
                    category="research",
                ),
            ],
        )

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        context = dict(payload.get("context") or {})
        query = payload.get("query") or payload.get("goal") or payload.get("user_input") or context.get("query")
        if not query:
            return {
                "status": "failed",
                "skill": self.name(),
                "message": "query is required for research",
                "payload_keys": list(payload.keys()),
            }

        type_raw = payload.get("research_type") or payload.get("type") or context.get("research_type") or "MARKET_RESEARCH"
        try:
            research_type = ResearchType(str(type_raw).upper())
        except ValueError:
            research_type = ResearchType.MARKET_RESEARCH

        request = ResearchRequest(
            query=str(query),
            research_type=research_type,
            client_id=payload.get("client_id") or context.get("client_id"),
            context=context,
            constraints=list(payload.get("constraints") or context.get("constraints") or []),
            learning_rules=list(
                payload.get("learning_rules")
                or context.get("learning_rules")
                or context.get("learning_context")
                or []
            ),
            max_sources=int(payload.get("max_sources") or 8),
        )
        from app.core.config import get_settings

        settings = get_settings()
        result = await self._manager.run(request, trace_id=str(payload.get("trace_id") or "-"))
        status = "completed" if result.document_ast else "incomplete"
        if (
            status == "completed"
            and settings.research_online_enabled
            and settings.app_env == "production"
            and (
                not settings.openrouter_api_key
                or settings.openrouter_api_key == "change-me"
            )
        ):
            # Fail closed: do not claim successful research without a live provider in prod.
            status = "incomplete"
            result.analysis_warnings = list(result.analysis_warnings or []) + [
                "Live research provider is not configured"
            ]
        return {
            "status": status,
            "skill": self.name(),
            "research_result": result.model_dump(mode="json"),
            "research_id": str(result.id),
            "summary": result.summary,
            "sources": [s.model_dump(mode="json") for s in result.sources],
            "findings": [f.model_dump(mode="json") for f in result.findings],
            "insights": [i.model_dump(mode="json") for i in result.insights],
            "recommendations": result.recommendations,
            "confidence": result.confidence,
            "document_ast": result.document_ast,
            "memory_candidates": result.memory_candidates,
            "analysis_warnings": result.analysis_warnings,
            "metadata": result.metadata,
        }
