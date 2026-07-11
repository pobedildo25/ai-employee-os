from typing import Any

from app.context.models import ContextRequest
from app.context.providers.base import ContextProvider
from app.research.manager import ResearchManager


class ResearchContextProvider(ContextProvider):
    """Injects recent research results into ExecutionContext — does not replace Knowledge."""

    name = "research"

    def __init__(self, manager: ResearchManager) -> None:
        self._manager = manager

    async def fetch(self, request: ContextRequest) -> dict[str, Any]:
        metadata = request.metadata or {}
        if metadata.get("research_result"):
            return {"research_context": metadata["research_result"]}

        research_id = metadata.get("research_id")
        if research_id:
            stored = self._manager.get_result(str(research_id))
            if stored is not None:
                return {"research_context": stored.model_dump(mode="json")}

        latest = self._manager.get_latest_for_client(request.client_id)
        if latest is None:
            return {}
        return {"research_context": latest.model_dump(mode="json")}
