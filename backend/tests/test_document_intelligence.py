from pathlib import Path
from uuid import uuid4

import pytest

from app.document_intelligence.analyzer import DocumentAnalyzer
from app.document_intelligence.ast.models import ASTNodeType
from app.document_intelligence.memory_preparer import prepare_document_memory_items
from app.document_intelligence.models import AnalysisStatus
from app.document_intelligence.pipeline import DocumentPipeline
from app.file_processing.processor import FileProcessor
from app.memory.models import MemoryType
from app.skills.builtin.document_analysis_skill import DocumentAnalysisSkill
from app.skills.registry import create_capability_registry
from tests.fixtures.file_factory import create_docx_file, create_pdf_file, read_file_bytes


@pytest.fixture
def analyzer() -> DocumentAnalyzer:
    return DocumentAnalyzer()


@pytest.fixture
def pipeline() -> DocumentPipeline:
    return DocumentPipeline(processor=FileProcessor(), analyzer=DocumentAnalyzer())


def test_document_representation_from_docx(analyzer: DocumentAnalyzer, tmp_docx: Path) -> None:
    artifact_id = uuid4()
    processor = FileProcessor()
    extracted = processor.process_bytes(
        read_file_bytes(tmp_docx),
        "sample.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    representation, document_ast = analyzer.analyze(
        artifact_id=artifact_id,
        title="Sample DOCX",
        extracted=extracted,
    )

    assert representation.artifact_id == artifact_id
    assert representation.document_type == "docx"
    assert representation.analysis_status == AnalysisStatus.COMPLETED
    assert len(representation.elements) >= 2
    assert representation.structure["node_count"] > 0
    assert document_ast.root.node_type == ASTNodeType.DOCUMENT
    assert representation.ast_reference is not None


def test_ast_generation_for_pdf(pipeline: DocumentPipeline, tmp_pdf: Path) -> None:
    artifact_id = uuid4()
    representation, document_ast, extracted, detected = pipeline.process_bytes(
        artifact_id=artifact_id,
        title="Sample PDF",
        data=read_file_bytes(tmp_pdf),
        filename="sample.pdf",
        mime_type="application/pdf",
    )

    assert detected.category.value == "pdf"
    assert representation.document_type == "pdf"
    assert document_ast.node_count >= 1
    assert document_ast.root.node_type == ASTNodeType.DOCUMENT
    assert extracted.pages == 1


def test_pdf_parsing_integration(pipeline: DocumentPipeline, tmp_pdf: Path) -> None:
    artifact_id = uuid4()
    representation, document_ast, _extracted, _detected = pipeline.process_bytes(
        artifact_id=artifact_id,
        title="PDF Integration",
        data=read_file_bytes(tmp_pdf),
        filename="report.pdf",
        mime_type="application/pdf",
    )

    assert representation.structure["section_count"] >= 0
    assert "node_types" in representation.structure
    assert document_ast.root.children is not None


def test_docx_parsing_integration(pipeline: DocumentPipeline, tmp_docx: Path) -> None:
    artifact_id = uuid4()
    representation, document_ast, extracted, _detected = pipeline.process_bytes(
        artifact_id=artifact_id,
        title="DOCX Integration",
        data=read_file_bytes(tmp_docx),
        filename="proposal.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    assert "First paragraph" in (extracted.text or "")
    assert representation.elements[0].content == "First paragraph"
    assert any(node.node_type == ASTNodeType.PARAGRAPH for node in document_ast.root.children[0].children)


@pytest.mark.asyncio
async def test_artifact_metadata_update_after_processing(tmp_path: Path) -> None:
    from datetime import datetime, timezone

    from app.models.artifact import Artifact
    from app.models.enums import ArtifactStatus
    from app.schemas.artifact import ArtifactUpdate
    from app.services.file_processing_service import FileProcessingService
    from tests.conftest import InMemoryStorage
    from tests.fixtures.file_factory import create_txt_file

    artifact_id = uuid4()
    storage = InMemoryStorage()
    txt_path = create_txt_file(tmp_path / "doc.txt", "Important document fact.\nSecond line.")
    content = read_file_bytes(txt_path)
    storage_path = "client/project/doc.txt"
    await storage.upload(storage_path, content, "text/plain")

    class FakeRepo:
        def __init__(self) -> None:
            self.artifact = Artifact(
                id=artifact_id,
                client_id=uuid4(),
                project_id=uuid4(),
                name="doc.txt",
                artifact_type="document",
                description=None,
                status=ArtifactStatus.PROCESSING,
                storage_path=storage_path,
                mime_type="text/plain",
                size=len(content),
                metadata_=None,
                created_by=None,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

        async def get_by_id(self, aid):
            return self.artifact if aid == artifact_id else None

        async def update(self, aid, data: ArtifactUpdate):
            if aid != artifact_id:
                return None
            if data.metadata is not None:
                self.artifact.metadata_ = data.metadata
            if data.status is not None:
                self.artifact.status = data.status
            return self.artifact

    repo = FakeRepo()
    service = FileProcessingService(repo, storage, FileProcessor())
    result = await service.process_artifact(artifact_id)

    assert result.metadata is not None
    assert result.metadata.get("extracted_text") == "Important document fact.\nSecond line."
    assert result.metadata.get("document_type") == "text"
    assert result.metadata.get("analysis_status") == AnalysisStatus.COMPLETED.value
    assert result.metadata.get("document_structure") is not None
    assert result.metadata.get("ast_reference") is not None
    assert "document_representation" in result.metadata
    assert "document_ast" in result.metadata


def test_memory_preparer_creates_candidates(analyzer: DocumentAnalyzer, tmp_docx: Path) -> None:
    artifact_id = uuid4()
    extracted = FileProcessor().process_bytes(
        read_file_bytes(tmp_docx),
        "sample.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    representation, _ = analyzer.analyze(artifact_id=artifact_id, title="Memory Test", extracted=extracted)

    items = prepare_document_memory_items(representation, project_id=uuid4())

    assert len(items) >= 2
    assert items[0].type == MemoryType.FACT
    assert items[0].metadata["kind"] == "document_structure"
    assert any(item.type == MemoryType.KNOWLEDGE for item in items)


@pytest.mark.asyncio
async def test_document_analysis_skill_integration(tmp_docx: Path) -> None:
    extracted = FileProcessor().process_bytes(
        read_file_bytes(tmp_docx),
        "sample.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    skill = DocumentAnalysisSkill()
    result = await skill.execute(
        {
            "artifact_id": str(uuid4()),
            "title": "Skill Test",
            "extracted_content": extracted.model_dump(),
        }
    )

    assert result["status"] == "completed"
    assert result["analysis_status"] == AnalysisStatus.COMPLETED.value
    assert result["representation"]["document_type"] == "docx"
    assert result["memory_candidates"]


def test_skill_registry_includes_document_analysis() -> None:
    registry = create_capability_registry()
    names = {capability.name for capability in registry.list_available()}
    assert "document_analysis" in names
    skill = registry.get_skill_for_capability("document_analysis")
    assert skill is not None
    assert skill.name() == "document_analysis_skill"
