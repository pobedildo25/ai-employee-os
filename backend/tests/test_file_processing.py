from pathlib import Path

import pytest

from tests.fixtures.file_factory import read_file_bytes


def test_txt_extraction(processor, tmp_txt: Path) -> None:
    result = processor.process_bytes(read_file_bytes(tmp_txt), "sample.txt", "text/plain")
    assert result.text is not None
    assert "Hello from TXT file" in result.text
    assert result.metadata["format"] == "txt"
    assert result.metadata["line_count"] == 2


def test_docx_extraction(processor, tmp_docx: Path) -> None:
    result = processor.process_bytes(
        read_file_bytes(tmp_docx),
        "sample.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert result.text is not None
    assert "First paragraph" in result.text
    assert "Second paragraph" in result.text
    assert result.metadata["format"] == "docx"


def test_pptx_extraction(processor, tmp_pptx: Path) -> None:
    result = processor.process_bytes(
        read_file_bytes(tmp_pptx),
        "sample.pptx",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
    assert result.text is not None
    assert "Slide 1 title" in result.text
    assert result.pages == 2
    assert result.metadata["format"] == "pptx"


def test_xlsx_extraction(processor, tmp_xlsx: Path) -> None:
    result = processor.process_bytes(
        read_file_bytes(tmp_xlsx),
        "sample.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    assert result.text is not None
    assert "Item A" in result.text
    assert result.tables is not None
    assert len(result.tables) >= 1
    assert result.metadata["format"] == "xlsx"


def test_pdf_extraction(processor, tmp_pdf: Path) -> None:
    result = processor.process_bytes(read_file_bytes(tmp_pdf), "sample.pdf", "application/pdf")
    assert result.pages == 1
    assert result.metadata["format"] == "pdf"


def test_image_extraction(processor, tmp_png: Path) -> None:
    result = processor.process_bytes(read_file_bytes(tmp_png), "sample.png", "image/png")
    assert result.text is None
    assert result.metadata["format"] == "png"
    assert result.metadata["size_bytes"] > 0
    assert result.metadata.get("width") == 1
    assert result.metadata.get("height") == 1


@pytest.mark.asyncio
async def test_file_processing_service_process_artifact() -> None:
    from datetime import datetime, timezone
    from uuid import uuid4

    from app.file_processing.processor import FileProcessor
    from app.models.artifact import Artifact
    from app.models.enums import ArtifactStatus
    from app.schemas.artifact import ArtifactUpdate
    from app.services.file_processing_service import FileProcessingService
    from tests.conftest import InMemoryStorage
    from tests.fixtures.file_factory import create_txt_file

    artifact_id = uuid4()
    storage = InMemoryStorage()
    content = b"Service integration text"
    storage_path = "client/project/file.txt"
    await storage.upload(storage_path, content, "text/plain")

    class FakeRepo:
        def __init__(self) -> None:
            self.artifact = Artifact(
                id=artifact_id,
                client_id=uuid4(),
                project_id=uuid4(),
                name="file.txt",
                artifact_type="document",
                description=None,
                status=ArtifactStatus.COMPLETED,
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
    assert result.metadata.get("extracted_text") == "Service integration text"
    assert "extraction_metadata" in result.metadata
