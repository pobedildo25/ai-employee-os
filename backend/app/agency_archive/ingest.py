"""Ingest on-disk agency/client archive into knowledge pipeline."""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.classification import is_business_client
from app.core.config import get_settings
from app.database.session import get_session_factory
from app.knowledge.extractor import KnowledgeExtractor
from app.knowledge.manager import KnowledgeManager
from app.knowledge.migration import KnowledgeMigrationService
from app.knowledge.stores.postgres_store import PostgresKnowledgeStore
from app.llm.gateway import create_llm_gateway
from app.repositories.sqlalchemy_artifact_repository import SQLAlchemyArtifactRepository
from app.repositories.sqlalchemy_artifact_version_repository import SQLAlchemyArtifactVersionRepository
from app.repositories.sqlalchemy_client_repository import SQLAlchemyClientRepository
from app.repositories.sqlalchemy_project_repository import SQLAlchemyProjectRepository
from app.schemas.artifact import ArtifactUploadRequest
from app.schemas.client import ClientCreate
from app.schemas.project import ProjectCreate
from app.services.artifact_service import ArtifactService
from app.services.client_service import ClientService
from app.services.project_service import ProjectService
from app.storage.minio_storage import MinioStorage

logger = logging.getLogger(__name__)

SUPPORTED_SUFFIXES = {".docx", ".pdf", ".pptx", ".png", ".jpg", ".jpeg", ".webp", ".txt", ".md"}


def _mime_for(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def _artifact_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pptx":
        return "source_presentation"
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return "brand_asset"
    return "source_document"


async def _ensure_business_client(
    session: AsyncSession,
    *,
    name: str,
    description: str,
) -> tuple[UUID, UUID]:
    client_repo = SQLAlchemyClientRepository(session)
    project_repo = SQLAlchemyProjectRepository(session)
    client_service = ClientService(client_repo)
    project_service = ProjectService(project_repo)

    existing = await client_service.list_all()
    client = next(
        (item for item in existing if item.name == name and is_business_client(item)),
        None,
    )
    if client is None:
        client = await client_service.create(
            ClientCreate(
                name=name,
                description=description,
                metadata={"type": "business", "source": "agency_archive"},
            )
        )
    projects = await project_service.list_by_client(client.id)
    project = next((item for item in projects if item.name == "Agency Archive"), None)
    if project is None:
        project = await project_service.create(
            ProjectCreate(
                client_id=client.id,
                name="Agency Archive",
                description="Imported templates and client materials",
            )
        )
    return client.id, project.id


async def _ingest_files_for_client(
    session: AsyncSession,
    *,
    client_id: UUID,
    project_id: UUID,
    files: list[Path],
    agency_name: str,
    archive_root: Path,
    trace_id: str,
) -> dict:
    settings = get_settings()
    artifact_repo = SQLAlchemyArtifactRepository(session)
    version_repo = SQLAlchemyArtifactVersionRepository(session)
    storage = MinioStorage(settings)
    artifact_service = ArtifactService(artifact_repo, version_repo, storage)

    uploaded: list[dict] = []
    file_bytes_by_artifact: dict[str, bytes] = {}
    for path in files:
        data = path.read_bytes()
        uploaded_artifact = await artifact_service.upload_artifact(
            ArtifactUploadRequest(
                client_id=client_id,
                project_id=project_id,
                name=path.name,
                artifact_type=_artifact_type(path),
                metadata={
                    "source_path": str(path),
                    "imported_by": "agency_archive_ingest",
                    "relative_path": str(path.relative_to(archive_root)),
                },
            ),
            file_data=data,
            mime_type=_mime_for(path),
        )
        uploaded.append(
            {
                "id": str(uploaded_artifact.id),
                "artifact_id": str(uploaded_artifact.id),
                "name": uploaded_artifact.name,
                "artifact_type": uploaded_artifact.artifact_type,
                "mime_type": uploaded_artifact.mime_type,
            }
        )
        file_bytes_by_artifact[str(uploaded_artifact.id)] = data

    if not uploaded:
        return {"files_processed": 0, "knowledge_items": 0}

    gateway = create_llm_gateway(settings)
    migration = KnowledgeMigrationService(
        KnowledgeExtractor(gateway),
        KnowledgeManager(PostgresKnowledgeStore(session)),
    )
    result = await migration.migrate(
        client_id=client_id,
        artifacts=uploaded,
        context={"agency_name": agency_name, "archive_root": str(archive_root)},
        file_bytes_by_artifact=file_bytes_by_artifact,
        persist=True,
        trace_id=trace_id,
    )
    return {
        "files_processed": len(uploaded),
        "knowledge_items": len(result.extracted_items),
        "brand_profiles": len(result.brand_profiles),
        "warnings": result.warnings,
    }


def _collect_files(root: Path, *, max_files: int) -> list[Path]:
    files = [
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    ]
    return sorted(files)[:max_files]


async def ingest_archive(
    *,
    archive_root: Path,
    agency_name: str,
    max_files: int,
    trace_id: str,
    per_client: bool = True,
) -> dict:
    settings = get_settings()
    session_factory = get_session_factory(settings)
    if not archive_root.exists():
        return {"status": "skipped", "reason": "archive missing", "archive_root": str(archive_root)}

    async with session_factory() as session:
        if not per_client:
            files = _collect_files(archive_root, max_files=max_files)
            if not files:
                return {
                    "status": "skipped",
                    "reason": "no supported files found",
                    "archive_root": str(archive_root),
                }
            client_id, project_id = await _ensure_business_client(
                session,
                name=agency_name,
                description="Agency knowledge archive",
            )
            stats = await _ingest_files_for_client(
                session,
                client_id=client_id,
                project_id=project_id,
                files=files,
                agency_name=agency_name,
                archive_root=archive_root,
                trace_id=trace_id,
            )
            await session.commit()
            return {"status": "completed", "mode": "flat", "client_id": str(client_id), **stats}

        client_dirs = sorted([path for path in archive_root.iterdir() if path.is_dir()])
        loose_files = [
            path
            for path in archive_root.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
        ]
        summaries: list[dict] = []

        if loose_files:
            client_id, project_id = await _ensure_business_client(
                session,
                name=agency_name,
                description="Agency knowledge archive",
            )
            stats = await _ingest_files_for_client(
                session,
                client_id=client_id,
                project_id=project_id,
                files=sorted(loose_files)[:max_files],
                agency_name=agency_name,
                archive_root=archive_root,
                trace_id=trace_id,
            )
            summaries.append({"client": agency_name, "client_id": str(client_id), **stats})

        for client_dir in client_dirs:
            files = _collect_files(client_dir, max_files=max_files)
            if not files:
                continue
            client_id, project_id = await _ensure_business_client(
                session,
                name=client_dir.name,
                description=f"Imported from archive folder {client_dir.name}",
            )
            stats = await _ingest_files_for_client(
                session,
                client_id=client_id,
                project_id=project_id,
                files=files,
                agency_name=agency_name,
                archive_root=archive_root,
                trace_id=trace_id,
            )
            summaries.append({"client": client_dir.name, "client_id": str(client_id), **stats})

        await session.commit()
        if not summaries:
            return {
                "status": "skipped",
                "reason": "no supported files found",
                "archive_root": str(archive_root),
            }
        return {
            "status": "completed",
            "mode": "per_client",
            "clients": summaries,
            "clients_processed": len(summaries),
            "files_processed": sum(int(item.get("files_processed") or 0) for item in summaries),
        }
