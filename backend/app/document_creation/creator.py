from uuid import UUID

from app.document_creation.generators.ast_generator import DocumentASTGenerator
from app.document_creation.interfaces.creator import DocumentCreatorInterface
from app.document_creation.models import DocumentCreationRequest, DocumentCreationResult
from app.document_creation.validators.ast_validator import ASTValidator


class DocumentCreator(DocumentCreatorInterface):
    def __init__(
        self,
        ast_generator: DocumentASTGenerator,
        validator: ASTValidator | None = None,
    ) -> None:
        self._ast_generator = ast_generator
        self._validator = validator or ASTValidator()

    async def create(
        self,
        request: DocumentCreationRequest,
        *,
        available_capabilities: list[dict[str, str]] | None = None,
        trace_id: str = "-",
    ) -> DocumentCreationResult:
        result = await self._ast_generator.generate(
            request,
            available_capabilities=available_capabilities,
            trace_id=trace_id,
        )
        result.missing_information = self._validator.detect_missing_information(result)
        return result
