import json
from typing import Any

from app.observability.interfaces.observability import ObservabilityProvider


class JsonExporter:
    """Exports observability payload as JSON text."""

    def __init__(self, provider: ObservabilityProvider) -> None:
        self._provider = provider

    def export(self, *, indent: int = 2) -> str:
        return json.dumps(self._provider.export_payload(), ensure_ascii=False, indent=indent)

    def export_dict(self) -> dict[str, Any]:
        return self._provider.export_payload()
