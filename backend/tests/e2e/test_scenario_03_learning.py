import pytest

from app.context.builder import create_context_builder
from app.learning.manager import LearningManager
from app.learning.models import LearningScope, LearningSource
from app.learning.providers.in_memory_learning_store import InMemoryLearningStore
from app.revision.agent import RevisionAgent
from app.revision.manager import RevisionManager
from app.revision.nodes.revision_node import RevisionNode
from app.agent_runtime.state.models import create_initial_state
from app.quality.models import IssueSeverity
from tests.llm_fixtures import learning_rule_json, mock_gateway, revision_json


@pytest.mark.asyncio
async def test_learning_rule_persists_and_reaches_context_builder(settings, client_project_ids) -> None:
    client_id, _project_id = client_project_ids
    gateway, provider = mock_gateway(
        settings,
        learning_rule_json(category="document_style", key="verbosity", value="short", confidence=0.9),
        learning_rule_json(category="document_style", key="verbosity", value="short", confidence=0.9),
    )
    learning = LearningManager(InMemoryLearningStore(), llm_gateway=gateway)

    rule = await learning.learn(
        "Все документы должны быть короткими",
        source=LearningSource.EXPLICIT_PREFERENCE,
        client_id=client_id,
        force=True,
    )
    assert rule is not None
    assert rule.scope == LearningScope.CLIENT
    assert rule.category == "document_style"
    assert rule.key == "verbosity"
    assert rule.value == "short"

    revision_gateway, _ = mock_gateway(
        settings,
        revision_json(),
        learning_rule_json(category="document_style", key="verbosity", value="short"),
    )
    revision_learning = LearningManager(InMemoryLearningStore(), llm_gateway=revision_gateway)
    node = RevisionNode(RevisionManager(RevisionAgent(revision_gateway)), learning_manager=revision_learning)

    state = create_initial_state(
        execution_id="e2e-learn-1",
        trace_id="trace-learn-1",
        user_input="Revise document",
        metadata={"client_id": str(client_id), "user_feedback": "Сделай документ короче"},
    )
    state["review_result"] = {
        "status": "revise",
        "issues": [{"category": "content", "description": "Too long", "severity": IssueSeverity.MAJOR.value}],
        "recommendations": ["Shorten sections"],
    }
    state["revision_count"] = 0

    update = await node(state)
    assert update.get("learning_result") is not None

    builder = create_context_builder(learning_manager=learning)
    context = await builder.build(
        user_input="Создай следующий документ",
        client_id=client_id,
    )

    assert context.learning_context
    assert any(item.get("category") == "document_style" for item in context.learning_context)
    prioritized = context.to_prioritized_dict()
    assert "learning_context" in prioritized
    assert context.extensions.get("learning_rules")
    assert provider.calls
