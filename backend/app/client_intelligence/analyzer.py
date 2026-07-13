import json
import logging
from typing import Any

from app.agents.parsers.response_parser import ResponseParseError, extract_json_content
from app.client_intelligence.analyzers.communication_analyzer import CommunicationAnalyzer
from app.client_intelligence.analyzers.history_analyzer import HistoryAnalyzer
from app.client_intelligence.analyzers.preference_analyzer import PreferenceAnalyzer
from app.client_intelligence.analyzers.risk_analyzer import RiskAnalyzer
from app.client_intelligence.models import ClientIntelligenceSources, IntelligenceSignal
from app.client_intelligence.prompt import CLIENT_INTELLIGENCE_SYSTEM_PROMPT, build_analyzer_user_message
from app.llm.exceptions import LLMProviderError
from app.llm.gateway import LLMGateway
from app.llm.models import LLMMessage

logger = logging.getLogger(__name__)


class ClientIntelligenceAnalyzer:
    """Runs specialized analyzers and optional LLM enrichment."""

    def __init__(
        self,
        llm_gateway: LLMGateway | None = None,
        *,
        preference: PreferenceAnalyzer | None = None,
        communication: CommunicationAnalyzer | None = None,
        history: HistoryAnalyzer | None = None,
        risk: RiskAnalyzer | None = None,
    ) -> None:
        self._gateway = llm_gateway
        self._preference = preference or PreferenceAnalyzer()
        self._communication = communication or CommunicationAnalyzer()
        self._history = history or HistoryAnalyzer()
        self._risk = risk or RiskAnalyzer()

    def analyze_heuristics(self, sources: ClientIntelligenceSources) -> list[IntelligenceSignal]:
        signals: list[IntelligenceSignal] = []
        signals.extend(self._preference.analyze(sources))
        signals.extend(self._communication.analyze(sources))
        signals.extend(self._history.analyze(sources))
        signals.extend(self._risk.analyze(sources))
        return signals

    async def enrich_with_llm(
        self,
        sources: ClientIntelligenceSources,
        *,
        trace_id: str = "-",
    ) -> dict[str, Any]:
        if self._gateway is None:
            return {}
        evidence = _evidence_lines(sources)
        if not evidence:
            return {}
        messages = [
            LLMMessage(role="system", content=CLIENT_INTELLIGENCE_SYSTEM_PROMPT),
            LLMMessage(
                role="user",
                content=build_analyzer_user_message(
                    client_id=str(sources.client_id),
                    evidence=evidence,
                    hints={
                        "client": sources.client_context,
                        "workspace": {
                            "active_project_id": sources.workspace.get("active_project_id"),
                            "active_artifact_id": sources.workspace.get("active_artifact_id"),
                        },
                    },
                ),
            ),
        ]
        try:
            response = await self._gateway.complete(messages, temperature=0.2)
            return parse_llm_intelligence(response.content)
        except (LLMProviderError, ResponseParseError, ValueError, json.JSONDecodeError, Exception) as exc:
            logger.warning("client intelligence llm enrich degraded | trace_id=%s error=%s", trace_id, exc)
            return {}


def parse_llm_intelligence(raw: str) -> dict[str, Any]:
    content = extract_json_content(raw)
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ResponseParseError("Client intelligence LLM response must be an object")
    signals: list[IntelligenceSignal] = []
    for item in data.get("signals") or []:
        if not isinstance(item, dict):
            continue
        signals.append(
            IntelligenceSignal(
                category=str(item.get("category") or "preference"),
                key=str(item.get("key") or "signal"),
                value=str(item.get("value") or ""),
                confidence=float(item.get("confidence", 0.7)),
                source="llm_analyzer",
            )
        )
    return {
        "summary": data.get("summary"),
        "industry": data.get("industry"),
        "services": data.get("services") or [],
        "signals": signals,
        "recommendations": [str(r) for r in (data.get("recommendations") or []) if str(r).strip()],
        "risks": [str(r) for r in (data.get("risks") or []) if str(r).strip()],
        "confidence": data.get("confidence"),
    }


def _evidence_lines(sources: ClientIntelligenceSources) -> list[str]:
    lines: list[str] = []
    for item in sources.memory_items:
        if item.get("content"):
            lines.append(f"memory:{item.get('type')}:{item['content']}")
    for item in sources.knowledge_items:
        content = item.get("content") or item.get("title")
        if content:
            lines.append(f"knowledge:{content}")
    for rule in sources.learning_rules:
        lines.append(f"learning:{rule.get('key')}:{rule.get('value') or rule.get('content')}")
    for note in sources.notes:
        lines.append(f"note:{note}")
    return lines
