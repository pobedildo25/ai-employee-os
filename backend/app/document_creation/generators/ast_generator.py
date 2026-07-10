import logging

from app.agents.parsers.response_parser import ResponseParseError
from app.document_creation.models import DocumentCreationRequest, DocumentCreationResult
from app.document_creation.parsers.creation_parser import parse_creation_response
from app.document_creation.prompt import (
    DOCUMENT_CREATION_SYSTEM_PROMPT,
    build_creation_user_message,
)
from app.document_creation.validators.ast_validator import ASTValidationError, ASTValidator
from app.llm.gateway import LLMGateway
from app.llm.models import LLMMessage

logger = logging.getLogger(__name__)


class DocumentASTGenerator:
    DEFAULT_MAX_RETRIES = 3

    def __init__(
        self,
        llm_gateway: LLMGateway,
        validator: ASTValidator | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        self._gateway = llm_gateway
        self._validator = validator or ASTValidator()
        self._max_retries = max_retries

    async def generate(
        self,
        request: DocumentCreationRequest,
        *,
        available_capabilities: list[dict[str, str]] | None = None,
        trace_id: str = "-",
    ) -> DocumentCreationResult:
        messages: list[LLMMessage] = [
            LLMMessage(role="system", content=DOCUMENT_CREATION_SYSTEM_PROMPT),
            LLMMessage(
                role="user",
                content=build_creation_user_message(
                    user_goal=request.user_goal,
                    context=request.context,
                    brand_profile=request.brand_profile.model_dump(mode="json")
                    if request.brand_profile
                    else None,
                    document_type=request.document_type,
                    requirements=request.requirements,
                    capabilities=available_capabilities or [],
                ),
            ),
        ]

        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                response = await self._gateway.complete(messages, temperature=0.3)
                document_ast, missing_information, metadata, document_type = parse_creation_response(
                    response.content
                )

                result = DocumentCreationResult(
                    document_ast=document_ast,
                    metadata=metadata,
                    missing_information=missing_information,
                )

                if document_ast is not None:
                    self._validator.validate(document_ast)
                    if document_type and "document_type" not in result.metadata:
                        result.metadata["document_type"] = document_type
                    logger.info(
                        "document ast generated | trace_id=%s nodes=%d attempt=%d",
                        trace_id,
                        document_ast.node_count,
                        attempt,
                    )
                    return result

                logger.info(
                    "document creation incomplete | trace_id=%s missing=%s attempt=%d",
                    trace_id,
                    missing_information,
                    attempt,
                )
                return result
            except (ResponseParseError, ASTValidationError) as exc:
                last_error = exc
                logger.warning(
                    "document ast generation failed | trace_id=%s attempt=%d error=%s",
                    trace_id,
                    attempt,
                    exc,
                )
                messages.append(
                    LLMMessage(
                        role="user",
                        content="Return ONLY valid JSON matching the required document AST schema.",
                    )
                )

        raise DocumentASTGeneratorError(
            f"Failed to generate valid document AST after {self._max_retries} attempts: {last_error}"
        )


class DocumentASTGeneratorError(Exception):
    """Raised when AST generation fails."""
