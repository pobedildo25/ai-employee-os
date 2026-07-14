from typing import Any

from app.analytics.manager import AnalyticsManager
from app.analytics.models import AnalyticsRequest, AnalyticsType
from app.skills.base.skill import BaseSkill
from app.skills.models import Capability, SkillMetadata


class AnalyticsSkill(BaseSkill):
    """Analytics & reporting over existing system sources (AST for Document/Presentation)."""

    def __init__(
        self,
        manager: AnalyticsManager | None = None,
        llm_gateway: Any | None = None,
    ) -> None:
        if manager is None:
            from app.analytics.analyzer import AnalyticsAnalyzer
            from app.llm.gateway import LLMGateway, create_llm_gateway

            gateway = llm_gateway or create_llm_gateway()
            if not isinstance(gateway, LLMGateway):
                raise TypeError("llm_gateway must be an LLMGateway instance")
            manager = AnalyticsManager(analyzer=AnalyticsAnalyzer(gateway))
        self._manager = manager
        super().__init__(
            metadata=SkillMetadata(
                id="analytics_skill",
                name="analytics_skill",
                description="Аналитика клиентов/проектов/качества и отчёты (AST)",
                capabilities=["analytics"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "analytics_type": {"type": "string"},
                        "type": {"type": "string"},
                        "client_id": {"type": "string"},
                        "project_id": {"type": "string"},
                        "context": {"type": "object"},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "analytics_result": {"type": "object"},
                        "document_ast": {"type": "object"},
                    },
                },
            ),
            capabilities=[
                Capability(
                    name="analytics",
                    description="Аналитика и отчёты по клиентам, проектам, качеству и исполнениям",
                    category="analytics",
                    critical=False,
                ),
            ],
        )

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        context = dict(payload.get("context") or {})
        type_raw = (
            payload.get("analytics_type")
            or payload.get("type")
            or context.get("analytics_type")
            or "CLIENT_PERFORMANCE"
        )
        try:
            analytics_type = AnalyticsType(str(type_raw).upper())
        except ValueError:
            analytics_type = AnalyticsType.CLIENT_PERFORMANCE

        learning_rules = list(
            payload.get("learning_rules")
            or context.get("learning_rules")
            or context.get("learning_context")
            or []
        )
        request = AnalyticsRequest(
            analytics_type=analytics_type,
            client_id=payload.get("client_id") or context.get("client_id"),
            project_id=payload.get("project_id") or context.get("project_id"),
            filters=dict(payload.get("filters") or {}),
            context=context,
            learning_rules=learning_rules,
            goal=payload.get("goal") or payload.get("user_input") or context.get("user_input"),
        )
        result = await self._manager.run(request, trace_id=str(payload.get("trace_id") or "-"))
        return {
            "status": "completed" if result.document_ast else "incomplete",
            "skill": self.name(),
            "analytics_result": result.model_dump(mode="json"),
            "summary": result.summary,
            "metrics": result.metrics,
            "insights": [i.model_dump(mode="json") for i in result.insights],
            "recommendations": result.recommendations,
            "document_ast": result.document_ast,
            "confidence": result.confidence,
            "memory_candidates": result.memory_candidates,
            "analysis_warnings": result.analysis_warnings,
            "metadata": result.metadata,
        }
