from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db_session
from app.repositories.client_repository import ClientRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.artifact_repository import ArtifactRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.sqlalchemy_artifact_repository import SQLAlchemyArtifactRepository
from app.repositories.sqlalchemy_client_repository import SQLAlchemyClientRepository
from app.repositories.sqlalchemy_project_repository import SQLAlchemyProjectRepository
from app.repositories.sqlalchemy_task_repository import SQLAlchemyTaskRepository
from app.services.artifact_service import ArtifactService
from app.services.client_service import ClientService
from app.services.project_service import ProjectService
from app.services.task_service import TaskService


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db_session():
        yield session


def get_client_repository(session: AsyncSession = Depends(get_session)) -> ClientRepository:
    return SQLAlchemyClientRepository(session)


def get_project_repository(session: AsyncSession = Depends(get_session)) -> ProjectRepository:
    return SQLAlchemyProjectRepository(session)


def get_artifact_repository(session: AsyncSession = Depends(get_session)) -> ArtifactRepository:
    return SQLAlchemyArtifactRepository(session)


def get_task_repository(session: AsyncSession = Depends(get_session)) -> TaskRepository:
    return SQLAlchemyTaskRepository(session)


def get_client_service(repository: ClientRepository = Depends(get_client_repository)) -> ClientService:
    return ClientService(repository)


def get_project_service(repository: ProjectRepository = Depends(get_project_repository)) -> ProjectService:
    return ProjectService(repository)


def get_artifact_service(repository: ArtifactRepository = Depends(get_artifact_repository)) -> ArtifactService:
    return ArtifactService(repository)


def get_task_service(repository: TaskRepository = Depends(get_task_repository)) -> TaskService:
    return TaskService(repository)
