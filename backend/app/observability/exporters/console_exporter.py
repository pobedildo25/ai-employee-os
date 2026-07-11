import json
import logging
from typing import Any

from app.observability.exporters.json_exporter import JsonExporter
from app.observability.interfaces.observability import ObservabilityProvider

logger = logging.getLogger(__name__)


class ConsoleExporter:
    """Writes observability export to console/log — observation only."""

    def __init__(self, provider: ObservabilityProvider) -> None:
        self._json = JsonExporter(provider)

    def export(self) -> dict[str, Any]:
        payload = self._json.export_dict()
        logger.info("observability export | %s", json.dumps(payload, ensure_ascii=False))
        return payload
