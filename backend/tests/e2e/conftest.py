import pytest

from app.core.config import Settings
from app.learning.manager import LearningManager
from app.learning.providers.in_memory_learning_store import InMemoryLearningStore
from tests.e2e.helpers import build_e2e_runtime, e2e_settings, new_client_project_ids
from tests.llm_fixtures import mock_gateway


@pytest.fixture
def settings() -> Settings:
    return e2e_settings()


@pytest.fixture
def client_project_ids() -> tuple:
    return new_client_project_ids()


@pytest.fixture
def learning_manager(settings: Settings) -> LearningManager:
    gateway, _ = mock_gateway(settings, "{}")
    return LearningManager(InMemoryLearningStore(), llm_gateway=gateway)


@pytest.fixture
def e2e_runtime_factory(settings, artifact_service, learning_manager):
    def _factory(*responses: str, learning: LearningManager | None = None, research_enabled: bool = False):
        run_settings = settings.model_copy(update={"research_enabled": research_enabled})
        gateway, provider = mock_gateway(run_settings, *responses)
        runtime, registry, _ = build_e2e_runtime(
            gateway,
            settings=run_settings,
            artifact_service=artifact_service,
            learning_manager=learning or learning_manager,
        )
        return runtime, gateway, provider, registry

    return _factory
