from uuid import uuid4

import pytest

from app.document_creation.parsers.creation_parser import parse_creation_response
from app.revision.agent import RevisionAgent
from app.revision.manager import RevisionManager
from app.revision.models import RevisionRequest, RevisionStatus
from app.schemas.artifact import ArtifactUploadRequest
from tests.llm_fixtures import creation_ast_json, mock_gateway, revision_json


@pytest.mark.asyncio
async def test_revision_lifecycle_creates_artifact_version(settings, artifact_service, client_project_ids) -> None:
    client_id, project_id = client_project_ids
    uploaded = await artifact_service.upload_artifact(
        ArtifactUploadRequest(
            client_id=client_id,
            project_id=project_id,
            name="proposal.docx",
            artifact_type="generated_document",
            metadata={"generated_by": "e2e"},
        ),
        file_data=b"original-proposal",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    gateway, _ = mock_gateway(settings, revision_json(title="Premium Proposal"))
    manager = RevisionManager(RevisionAgent(gateway), artifact_service=artifact_service)
    document_ast, _, _, _ = parse_creation_response(creation_ast_json(title="Original Proposal"))

    request = RevisionRequest(
        source_artifact_id=uploaded.id,
        issues=[],
        suggested_changes=["Add competitor table", "Premium style"],
        user_feedback="Добавь таблицу конкурентов и сделай стиль более премиальным",
        revision_count=0,
    )

    result = await manager.apply_revision(
        request,
        document_ast=document_ast.model_dump(mode="json") if document_ast else None,
        client_id=client_id,
        project_id=project_id,
        output_format="docx",
        trace_id="e2e-revision",
    )

    assert result.status == RevisionStatus.COMPLETED
    assert result.artifact_id == uploaded.id
    assert result.version_id is not None

    history = await artifact_service.get_artifact_history(uploaded.id)
    assert len(history) >= 2
    assert history[0].version_number == 1
    assert history[-1].version_number >= 2
