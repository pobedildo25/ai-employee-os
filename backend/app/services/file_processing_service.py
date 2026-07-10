from uuid import UUID

from app.document_intelligence.pipeline import DocumentPipeline
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
        document_pipeline: DocumentPipeline | None = None,
    ) -> None:
        self._artifact_repository = artifact_repository
        self._storage = storage
        self._processor = processor or FileProcessor()
        self._document_pipeline = document_pipeline or DocumentPipeline(processor=self._processor)

    async def process_artifact(self, artifact_id: UUID) -> ArtifactRead:
        artifact = await self._artifact_repository.get_by_id(artifact_id)
        if artifact is None:
            raise ValueError(f"Artifact {artifact_id} not found")
        if not artifact.storage_path:
            raise ValueError(f"Artifact {artifact_id} has no storage path")

        file_data = await self._storage.download(artifact.storage_path)
        filename = artifact.storage_path.split("/")[-1]
        representation, document_ast, extracted, _detected = self._document_pipeline.process_bytes(
            artifact_id=artifact_id,
            title=artifact.name,
            data=file_data,
            filename=filename,
            mime_type=artifact.mime_type,
        )

        metadata = dict(artifact.metadata_ or {})
        metadata.update(
            self._document_pipeline.build_artifact_metadata(representation, document_ast, extracted)
        )

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
