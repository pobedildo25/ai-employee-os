import logging
from typing import Any

from app.agents.parsers.response_parser import ResponseParseError
from app.llm.gateway import LLMGateway
from app.llm.models import LLMMessage
from app.revision.interfaces.revision import RevisionInterface
from app.revision.models import RevisionRequest, RevisionResult, RevisionStatus
from app.revision.parsers.revision_parser import parse_revision_response
from app.revision.prompt import REVISION_SYSTEM_PROMPT, build_revision_user_message

logger = logging.getLogger(__name__)


class RevisionAgentError(Exception):
    """Raised when revision planning fails."""


class RevisionAgent(RevisionInterface):
    DEFAULT_MAX_RETRIES = 3

    def __init__(self, llm_gateway: LLMGateway, max_retries: int = DEFAULT_MAX_RETRIES) -> None:
        self._gateway = llm_gateway
        self._max_retries = max_retries

    async def revise(
        self,
        request: RevisionRequest,
        *,
        document_ast: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        trace_id: str = "-",
    ) -> RevisionResult:
        messages: list[LLMMessage] = [
            LLMMessage(role="system", content=REVISION_SYSTEM_PROMPT),
            LLMMessage(
                role="user",
                content=build_revision_user_message(
                    request=request.model_dump(mode="json"),
                    document_ast=document_ast,
                    context=context or {},
                ),
            ),
        ]

        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                response = await self._gateway.complete(messages, temperature=0.3)
                updated_ast, changes, summary, update_ast, needs_render = parse_revision_response(
                    response.content
                )
                if updated_ast is None and update_ast:
                    raise ResponseParseError("Revision response did not include a valid AST")

                result = RevisionResult(
                    artifact_id=request.source_artifact_id,
                    changes_applied=changes,
                    summary=summary or "Revision planned",
                    status=RevisionStatus.COMPLETED,
                    document_ast=updated_ast.model_dump(mode="json") if updated_ast else document_ast,
                    metadata={
                        "update_ast": update_ast,
                        "needs_render": needs_render,
                        "revision_count": request.revision_count,
                    },
                )
                logger.info(
                    "revision planned | trace_id=%s changes=%d attempt=%d",
                    trace_id,
                    len(changes),
                    attempt,
                )
                return result
            except ResponseParseError as exc:
                last_error = exc
                logger.warning(
                    "revision parse failed | trace_id=%s attempt=%d error=%s",
                    trace_id,
                    attempt,
                    exc,
                )
                messages.append(
                    LLMMessage(
                        role="user",
                        content="Return ONLY valid JSON matching the required revision schema.",
                    )
                )

        raise RevisionAgentError(
            f"Failed to obtain valid revision after {self._max_retries} attempts: {last_error}"
        )
