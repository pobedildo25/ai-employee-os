from uuid import UUID

from app.file_processing.models import ExtractedContent
from app.file_processing.processor import FileProcessor
from app.models.enums import ArtifactStatus
from app.repositories.artifact_repository import ArtifactRepository
from app.schemas.artifact import ArtifactRead, ArtifactUpdate
from app.storage.storage_interface import StorageInterface


class FileProcessingService:
    def __init__(
        self,
        artifact_repository: ArtifactRepository,
        storage: StorageInterface,
        processor: FileProcessor | None = None,
    ) -> None:
        self._artifact_repository = artifact_repository
        self._storage = storage
        self._processor = processor or FileProcessor()

    async def process_artifact(self, artifact_id: UUID) -> ArtifactRead:
        artifact = await self._artifact_repository.get_by_id(artifact_id)
        if artifact is None:
            raise ValueError(f"Artifact {artifact_id} not found")
        if not artifact.storage_path:
            raise ValueError(f"Artifact {artifact_id} has no storage path")

        file_data = await self._storage.download(artifact.storage_path)
        filename = artifact.storage_path.split("/")[-1]
        extracted = self._processor.process_bytes(file_data, filename, artifact.mime_type)

        metadata = dict(artifact.metadata_ or {})
        metadata["extracted_text"] = extracted.text
        metadata["extraction_metadata"] = self._build_extraction_metadata(extracted)

        updated = await self._artifact_repository.update(
            artifact_id,
            ArtifactUpdate(
                metadata=metadata,
                status=ArtifactStatus.COMPLETED,
            ),
        )
        if updated is None:
            raise ValueError(f"Failed to update artifact {artifact_id}")

        return ArtifactRead.model_validate(updated)

    def _build_extraction_metadata(self, extracted: ExtractedContent) -> dict[str, object]:
        payload: dict[str, object] = dict(extracted.metadata)
        if extracted.pages is not None:
            payload["pages"] = extracted.pages
        if extracted.tables is not None:
            payload["tables"] = extracted.tables
        if extracted.structure is not None:
            payload["structure"] = extracted.structure
        return payload
