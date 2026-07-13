from uuid import UUID

from app.llm.gateway import LLMGateway
from app.research.interfaces.researcher import ResearchManagerInterface, ResearchProvider
from app.research.memory_preparer import prepare_research_memory_items
from app.research.models import ResearchRequest, ResearchResult
from app.research.providers.mock_provider import MockProvider
from app.research.providers.search_provider import SearchProvider
from app.research.researcher import Researcher
from app.research.validators.research_validator import ResearchValidator, result_to_document_ast


def _provider_is_mock(provider: ResearchProvider | None) -> bool:
    if provider is None:
        return True
    if isinstance(provider, MockProvider):
        return True
    backend = getattr(provider, "_backend", None)
    return isinstance(backend, MockProvider)


class ResearchManager(ResearchManagerInterface):
    """Runs research and keeps an in-memory result cache for API/context (not Knowledge)."""

    def __init__(
        self,
        *,
        researcher: Researcher | None = None,
        provider: ResearchProvider | None = None,
        llm_gateway: LLMGateway | None = None,
        validator: ResearchValidator | None = None,
    ) -> None:
        backend = provider or SearchProvider(MockProvider())
        self._researcher = researcher or Researcher(backend, llm_gateway=llm_gateway)
        self._validator = validator or ResearchValidator()
        self._results: dict[str, ResearchResult] = {}
        self._latest_by_client: dict[str, str] = {}

    def _is_mock_backend(self) -> bool:
        return _provider_is_mock(getattr(self._researcher, "_provider", None))

    async def run(self, request: ResearchRequest, *, trace_id: str = "-") -> ResearchResult:
        errors = self._validator.validate_request(request)
        if errors:
            return ResearchResult(
                query=request.query,
                research_type=request.research_type,
                analysis_warnings=errors,
                metadata={"status": "invalid_request", "strategy_ready": False},
            )

        result = await self._researcher.research(request, trace_id=trace_id)
        warnings = self._validator.validate_result(result)
        result.analysis_warnings = warnings
        if warnings and (not result.sources or not result.findings):
            result.metadata["status"] = "incomplete"
            result.metadata["strategy_ready"] = False
            self._store(result, client_id=request.client_id)
            return result

        document_ast = result_to_document_ast(result)
        result.document_ast = document_ast.model_dump(mode="json")
        memory_items = prepare_research_memory_items(result, client_id=request.client_id)
        result.memory_candidates = [item.model_dump(mode="json") for item in memory_items]
        result.metadata["document_type"] = "docx"

        # Mock / fixture providers must never look like production-ready research.
        if self._is_mock_backend():
            result.metadata["status"] = "mock_not_production"
            result.metadata["strategy_ready"] = False
            result.metadata["provider"] = "mock"
        else:
            result.metadata["status"] = "ready"
            result.metadata["strategy_ready"] = True

        self._store(result, client_id=request.client_id)
        return result

    def get_result(self, research_id: str) -> ResearchResult | None:
        return self._results.get(str(research_id))

    def get_latest_for_client(self, client_id: UUID | str | None) -> ResearchResult | None:
        if client_id is None:
            return None
        research_id = self._latest_by_client.get(str(client_id))
        if not research_id:
            return None
        return self._results.get(research_id)

    def _store(self, result: ResearchResult, *, client_id: UUID | str | None) -> None:
        self._results[str(result.id)] = result
        if client_id is not None:
            self._latest_by_client[str(client_id)] = str(result.id)
