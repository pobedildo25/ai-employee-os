from typing import Any

from app.context.models import ContextRequest
from app.context.providers.base import ContextProvider
from app.learning.manager import LearningManager
from app.learning.rules import format_rules_for_context


class LearningContextProvider(ContextProvider):
    """Injects durable learning rules into ExecutionContext as learning_context."""

    name = "learning"

    def __init__(self, manager: LearningManager) -> None:
        self._manager = manager

    async def fetch(self, request: ContextRequest) -> dict[str, Any]:
        # Confidence-filtered rules only — never inject raw get_rules dump.
        rules = await self._manager.get_applicable_rules(
            client_id=request.client_id,
            project_id=request.project_id,
            limit=20,
        )
        if not rules:
            return {}
        formatted = format_rules_for_context(rules)
        return {"learning_context": formatted, "learning_rules": formatted}
