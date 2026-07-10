from collections.abc import AsyncGenerator
from functools import lru_cache

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.database.session import get_db_session
from app.repositories.artifact_repository import ArtifactRepository
from app.repositories.artifact_version_repository import ArtifactVersionRepository
from app.repositories.client_repository import ClientRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.sqlalchemy_artifact_repository import SQLAlchemyArtifactRepository
from app.repositories.sqlalchemy_artifact_version_repository import SQLAlchemyArtifactVersionRepository
from app.repositories.sqlalchemy_client_repository import SQLAlchemyClientRepository
from app.repositories.sqlalchemy_project_repository import SQLAlchemyProjectRepository
from app.repositories.sqlalchemy_task_repository import SQLAlchemyTaskRepository
from app.repositories.task_repository import TaskRepository
from app.services.artifact_service import ArtifactService
from app.services.client_service import ClientService
from app.services.project_service import ProjectService
from app.services.file_processing_service import FileProcessingService
from app.services.task_service import TaskService
from app.file_processing.processor import FileProcessor
from app.storage.minio_storage import MinioStorage
from app.storage.storage_interface import StorageInterface


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db_session():
        yield session


@lru_cache
def get_storage() -> StorageInterface:
    return MinioStorage(get_settings())


def get_client_repository(session: AsyncSession = Depends(get_session)) -> ClientRepository:
    return SQLAlchemyClientRepository(session)


def get_project_repository(session: AsyncSession = Depends(get_session)) -> ProjectRepository:
    return SQLAlchemyProjectRepository(session)


def get_artifact_repository(session: AsyncSession = Depends(get_session)) -> ArtifactRepository:
    return SQLAlchemyArtifactRepository(session)


def get_artifact_version_repository(
    session: AsyncSession = Depends(get_session),
) -> ArtifactVersionRepository:
    return SQLAlchemyArtifactVersionRepository(session)


def get_task_repository(session: AsyncSession = Depends(get_session)) -> TaskRepository:
    return SQLAlchemyTaskRepository(session)


def get_client_service(repository: ClientRepository = Depends(get_client_repository)) -> ClientService:
    return ClientService(repository)


def get_project_service(repository: ProjectRepository = Depends(get_project_repository)) -> ProjectService:
    return ProjectService(repository)


def get_artifact_service(
    repository: ArtifactRepository = Depends(get_artifact_repository),
    version_repository: ArtifactVersionRepository = Depends(get_artifact_version_repository),
    storage: StorageInterface = Depends(get_storage),
) -> ArtifactService:
    return ArtifactService(repository, version_repository, storage)


def get_task_service(repository: TaskRepository = Depends(get_task_repository)) -> TaskService:
    return TaskService(repository)


def get_file_processing_service(
    repository: ArtifactRepository = Depends(get_artifact_repository),
    storage: StorageInterface = Depends(get_storage),
) -> FileProcessingService:
    return FileProcessingService(repository, storage, FileProcessor())
