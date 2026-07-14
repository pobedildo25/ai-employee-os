from typing import Any

from app.agency.profile import AgencyProfile
from app.context.models import ContextRequest
from app.context.providers.base import ContextProvider


class AgencyProfileProvider(ContextProvider):
    """Injects the agency's own identity into every execution context."""

    name = "agency"

    def __init__(self, profile: AgencyProfile) -> None:
        self._profile = profile

    async def fetch(self, request: ContextRequest) -> dict[str, Any]:
        if self._profile is None or not self._profile.is_configured:
            return {}
        return {"agency_context": self._profile.to_context()}
