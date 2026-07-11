from fastapi import APIRouter

from app.api.v1 import (
    artifacts,
    clients,
    documents,
    execution,
    health,
    observability,
    projects,
    security,
    tasks,
    workspace,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(clients.router)
api_router.include_router(projects.router)
api_router.include_router(artifacts.router)
api_router.include_router(tasks.router)
api_router.include_router(workspace.router)
api_router.include_router(execution.router)
api_router.include_router(documents.router)
api_router.include_router(observability.router)
api_router.include_router(security.router)
