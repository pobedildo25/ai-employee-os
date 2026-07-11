from typing import Any

from app.client_intelligence.manager import ClientIntelligenceManager
from app.context.models import ContextRequest
from app.context.providers.base import ContextProvider


class ClientIntelligenceContextProvider(ContextProvider):
    """Injects aggregated client intelligence after knowledge, before learning."""

    name = "client_intelligence"

    def __init__(self, manager: ClientIntelligenceManager) -> None:
        self._manager = manager

    async def fetch(self, request: ContextRequest) -> dict[str, Any]:
        if request.client_id is None:
            return {}
        result = await self._manager.build_profile(
            request.client_id,
            project_id=request.project_id,
            user_input=request.user_input,
            use_llm=False,
            trace_id=request.trace_id,
        )
        if result.metadata.get("status") == "skipped":
            return {}
        profile = result.profile.model_dump(mode="json")
        return {
            "client_intelligence_context": profile,
            "extensions": {"client_intelligence_confidence": result.profile.confidence},
        }
