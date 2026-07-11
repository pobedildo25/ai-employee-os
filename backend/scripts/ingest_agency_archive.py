#!/usr/bin/env python3
"""Bootstrap agency knowledge from an on-disk client archive (existing pipeline only)."""

from __future__ import annotations

import argparse
import asyncio
import mimetypes
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.database.session import get_session_factory
from app.knowledge.extractor import KnowledgeExtractor
from app.knowledge.migration import KnowledgeMigrationService
from app.knowledge.manager import KnowledgeManager
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

SUPPORTED_SUFFIXES = {".docx", ".pdf", ".pptx", ".png", ".jpg", ".jpeg", ".webp"}


def _mime_for(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def _artifact_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "source_document"
    if suffix == ".docx":
        return "source_document"
    if suffix == ".pptx":
        return "source_presentation"
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return "brand_asset"
    return "source_document"


async def _ensure_agency_client(session: AsyncSession, *, name: str) -> tuple[UUID, UUID]:
    client_repo = SQLAlchemyClientRepository(session)
    project_repo = SQLAlchemyProjectRepository(session)
    client_service = ClientService(client_repo)
    project_service = ProjectService(project_repo)

    existing = await client_service.list_all()
    agency = next((item for item in existing if item.name == name), None)
    if agency is None:
        agency = await client_service.create(ClientCreate(name=name, description="Agency knowledge archive"))
    projects = await project_service.list_by_client(agency.id)
    project = next((item for item in projects if item.name == "Agency Archive"), None)
    if project is None:
        project = await project_service.create(
            ProjectCreate(
                client_id=agency.id,
                name="Agency Archive",
                description="Imported templates and client materials",
            )
        )
    return agency.id, project.id


async def ingest_archive(
    *,
    archive_root: Path,
    agency_name: str,
    max_files: int,
    trace_id: str,
) -> dict:
    settings = get_settings()
    session_factory = get_session_factory(settings)
    files = [
        path
        for path in archive_root.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    ]
    files = sorted(files)[:max_files]
    if not files:
        return {"status": "skipped", "reason": "no supported files found", "archive_root": str(archive_root)}

    async with session_factory() as session:
        client_id, project_id = await _ensure_agency_client(session, name=agency_name)
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
                    metadata={"source_path": str(path), "imported_by": "ingest_agency_archive"},
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
        await session.commit()
        return {
            "status": "completed",
            "client_id": str(client_id),
            "project_id": str(project_id),
            "files_processed": len(uploaded),
            "knowledge_items": len(result.extracted_items),
            "brand_profiles": len(result.brand_profiles),
            "warnings": result.warnings,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest agency archive into knowledge/brand pipeline")
    parser.add_argument("--archive-root", required=True, help="Root directory with client documents")
    parser.add_argument("--agency-name", default="NOVA Agency")
    parser.add_argument("--max-files", type=int, default=200)
    parser.add_argument("--trace-id", default="agency-ingest")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    archive_root = Path(args.archive_root)
    if not archive_root.exists():
        print(f"Archive path not found: {archive_root}", file=sys.stderr)
        return 1
    summary = asyncio.run(
        ingest_archive(
            archive_root=archive_root,
            agency_name=args.agency_name,
            max_files=args.max_files,
            trace_id=args.trace_id,
        )
    )
    print(summary)
    return 0 if summary.get("status") == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
