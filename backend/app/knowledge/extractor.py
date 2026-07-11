import logging
from typing import Any
from uuid import UUID

from app.agents.parsers.response_parser import ResponseParseError
from app.brand_style.models import BrandProfile
from app.document_intelligence.ast.models import DocumentAST
from app.document_intelligence.models import DocumentRepresentation
from app.knowledge.interfaces.extractor import KnowledgeExtractorInterface
from app.knowledge.models import KnowledgeItem
from app.knowledge.parsers.knowledge_parser import parse_knowledge_response
from app.knowledge.policies.migration_policy import filter_items
from app.knowledge.prompt import KNOWLEDGE_EXTRACTION_SYSTEM_PROMPT, build_knowledge_extraction_message
from app.llm.gateway import LLMGateway
from app.llm.models import LLMMessage

logger = logging.getLogger(__name__)


class KnowledgeExtractorError(Exception):
    """Raised when knowledge extraction fails."""


class KnowledgeExtractor(KnowledgeExtractorInterface):
    DEFAULT_MAX_RETRIES = 3

    def __init__(self, llm_gateway: LLMGateway, max_retries: int = DEFAULT_MAX_RETRIES) -> None:
        self._gateway = llm_gateway
        self._max_retries = max_retries

    async def extract(
        self,
        *,
        representation: DocumentRepresentation,
        document_ast: DocumentAST | None = None,
        brand_profile: BrandProfile | None = None,
        context: dict[str, Any] | None = None,
        trace_id: str = "-",
    ) -> list[KnowledgeItem]:
        messages: list[LLMMessage] = [
            LLMMessage(role="system", content=KNOWLEDGE_EXTRACTION_SYSTEM_PROMPT),
            LLMMessage(
                role="user",
                content=build_knowledge_extraction_message(
                    representation=representation.model_dump(mode="json"),
                    document_ast=document_ast.model_dump(mode="json") if document_ast else None,
                    brand_profile=brand_profile.model_dump(mode="json") if brand_profile else None,
                    context=context or {},
                ),
            ),
        ]

        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                response = await self._gateway.complete(messages, temperature=0.2)
                items = parse_knowledge_response(
                    response.content,
                    client_id=None,
                    source_artifact_id=representation.artifact_id,
                )
                filtered = filter_items(items)
                logger.info(
                    "knowledge extracted | trace_id=%s items=%d attempt=%d",
                    trace_id,
                    len(filtered),
                    attempt,
                )
                return filtered
            except ResponseParseError as exc:
                last_error = exc
                logger.warning(
                    "knowledge parse failed | trace_id=%s attempt=%d error=%s",
                    trace_id,
                    attempt,
                    exc,
                )
                messages.append(
                    LLMMessage(
                        role="user",
                        content="Return ONLY valid JSON matching the required knowledge schema.",
                    )
                )

        raise KnowledgeExtractorError(
            f"Failed to extract knowledge after {self._max_retries} attempts: {last_error}"
        )
