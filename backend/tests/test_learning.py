from uuid import uuid4

import pytest

from app.agent_runtime.state.models import create_initial_state
from app.context.builder import create_context_builder
from app.context.models import ExecutionContext
from app.context.priority import CONTEXT_PRIORITY, build_prioritized_context
from app.core.config import Settings
from app.learning.detector import LearningDetector
from app.learning.extractor import LearningExtractor, parse_rule_extraction_response
from app.learning.manager import LearningManager
from app.learning.models import LearningRule, LearningScope, LearningSource
from app.learning.policies.learning_policy import LearningPolicy
from app.learning.providers.in_memory_learning_store import InMemoryLearningStore
from app.quality.models import IssueSeverity
from app.revision.agent import RevisionAgent
from app.revision.manager import RevisionManager
from app.revision.nodes.revision_node import RevisionNode
from tests.llm_fixtures import learning_rule_json, mock_gateway, revision_json


@pytest.fixture
def settings() -> Settings:
    return Settings(skills_enabled=True)


@pytest.fixture
def client_id():
    return uuid4()


def test_detector_feedback_signal() -> None:
    detector = LearningDetector()
    signal = detector.detect(
        "Сделай меньше текста в презентациях",
        source=LearningSource.USER_FEEDBACK,
    )
    assert signal is not None
    assert "меньше текста" in signal.text.lower()


def test_detector_rejects_ordinary_question() -> None:
    detector = LearningDetector()
    assert detector.detect("Какой сегодня статус проекта?", source=LearningSource.USER_FEEDBACK) is None


def test_detector_rejects_one_off() -> None:
    detector = LearningDetector()
    assert (
        detector.detect(
            "Только сейчас сделай короче",
            source=LearningSource.USER_FEEDBACK,
        )
        is None
    )


def test_detector_explicit_preference() -> None:
    detector = LearningDetector()
    signal = detector.detect(
        "Always use concise introductions",
        source=LearningSource.EXPLICIT_PREFERENCE,
    )
    assert signal is not None


@pytest.mark.asyncio
async def test_rule_extraction_mock(settings: Settings) -> None:
    gateway, _ = mock_gateway(settings, learning_rule_json())
    extractor = LearningExtractor(gateway)
    signal = LearningDetector().detect(
        "Убирай длинные вступления",
        source=LearningSource.USER_FEEDBACK,
    )
    assert signal is not None
    result = await extractor.extract(signal)
    assert result.should_learn is True
    assert result.rule is not None
    assert result.rule.category == "writing_style"
    assert result.rule.key == "introduction_length"
    assert result.rule.value == "short"
    assert result.confidence == 0.8


def test_parse_rule_extraction_pydantic() -> None:
    result = parse_rule_extraction_response(
        learning_rule_json(category="document_style", key="verbosity", value="short", confidence=0.85)
    )
    assert result.rule is not None
    assert result.rule.category == "document_style"
    assert result.confidence == 0.85


def test_confidence_scoring_policy() -> None:
    policy = LearningPolicy()
    existing = LearningRule(
        category="writing_style",
        key="introduction_length",
        value="short",
        confidence=0.7,
        scope=LearningScope.CLIENT,
    )
    merged = policy.merge_confidence(existing, 0.8)
    assert merged == pytest.approx(0.88)
    assert merged <= 0.98


@pytest.mark.asyncio
async def test_duplicate_merging(settings: Settings, client_id) -> None:
    gateway, _ = mock_gateway(
        settings,
        learning_rule_json(confidence=0.7),
        learning_rule_json(confidence=0.75),
    )
    manager = LearningManager(InMemoryLearningStore(), llm_gateway=gateway)

    first = await manager.learn(
        "Убирай длинные вступления",
        source=LearningSource.USER_FEEDBACK,
        client_id=client_id,
    )
    assert first is not None
    first_confidence = first.confidence

    second = await manager.learn(
        "Убирай длинные вступления всегда",
        source=LearningSource.USER_FEEDBACK,
        client_id=client_id,
    )

    assert second is not None
    assert first.id == second.id
    assert second.confidence > first_confidence
    assert second.metadata.get("merged") is True

    rules = await manager.get_rules(client_id=client_id)
    assert len(rules) == 1


@pytest.mark.asyncio
async def test_storage_and_search(client_id) -> None:
    store = InMemoryLearningStore()
    rule = LearningRule(
        scope=LearningScope.CLIENT,
        category="document_style",
        key="verbosity",
        value="short",
        confidence=0.85,
        source=LearningSource.USER_FEEDBACK,
        client_id=client_id,
    )
    saved = await store.save(rule)
    assert saved.id == rule.id

    found = await store.search(query="verbosity", client_id=client_id)
    assert len(found) == 1
    assert found[0].value == "short"

    dup = await store.find_duplicate(
        category="document_style",
        key="verbosity",
        client_id=client_id,
    )
    assert dup is not None


@pytest.mark.asyncio
async def test_manager_skips_low_confidence(settings: Settings, client_id) -> None:
    gateway, _ = mock_gateway(settings, learning_rule_json(confidence=0.4, should_learn=True))
    manager = LearningManager(InMemoryLearningStore(), llm_gateway=gateway)
    result = await manager.learn(
        "меньше текста пожалуйста",
        source=LearningSource.USER_FEEDBACK,
        client_id=client_id,
    )
    assert result is None


@pytest.mark.asyncio
async def test_context_integration(settings: Settings, client_id) -> None:
    gateway, _ = mock_gateway(settings, learning_rule_json())
    manager = LearningManager(InMemoryLearningStore(), llm_gateway=gateway)
    await manager.learn(
        "Убирай длинные вступления",
        source=LearningSource.EXPLICIT_PREFERENCE,
        client_id=client_id,
        force=True,
    )

    builder = create_context_builder(learning_manager=manager)
    context = await builder.build(user_input="Prepare slides", client_id=client_id)

    assert len(context.learning_context) == 1
    assert context.learning_context[0]["category"] == "writing_style"
    assert "introduction_length" in context.learning_context[0]["rule"]
    assert context.extensions.get("learning_rules")
    prioritized = context.to_prioritized_dict()
    assert "learning_context" in prioritized
    assert list(CONTEXT_PRIORITY).index("learning_context") == list(CONTEXT_PRIORITY).index(
        "client_intelligence_context"
    ) + 1
    assert list(CONTEXT_PRIORITY).index("client_intelligence_context") == list(CONTEXT_PRIORITY).index(
        "research_context"
    ) + 1
    assert list(CONTEXT_PRIORITY).index("research_context") == list(CONTEXT_PRIORITY).index(
        "knowledge_context"
    ) + 1


@pytest.mark.asyncio
async def test_apply_rules(settings: Settings, client_id) -> None:
    gateway, _ = mock_gateway(settings, learning_rule_json())
    manager = LearningManager(InMemoryLearningStore(), llm_gateway=gateway)
    await manager.learn(
        "меньше текста в презентациях",
        source=LearningSource.USER_FEEDBACK,
        client_id=client_id,
    )
    applied = await manager.apply_rules(client_id=client_id)
    assert len(applied) == 1
    assert applied[0]["key"] == "introduction_length"


@pytest.mark.asyncio
async def test_revision_integration_learns_from_feedback(settings: Settings, client_id) -> None:
    gateway, _ = mock_gateway(
        settings,
        revision_json(),
        learning_rule_json(category="presentation", key="slide_text", value="less_text"),
    )
    learning = LearningManager(InMemoryLearningStore(), llm_gateway=gateway)
    node = RevisionNode(RevisionManager(RevisionAgent(gateway)), learning_manager=learning)

    state = create_initial_state(
        execution_id="exec-learn-1",
        trace_id="trace-learn-1",
        user_input="Revise deck",
        metadata={
            "client_id": str(client_id),
            "user_feedback": "Сделай меньше текста в презентациях",
        },
    )
    state["review_result"] = {
        "status": "revise",
        "issues": [
            {
                "category": "content",
                "description": "Too much text",
                "severity": IssueSeverity.MAJOR.value,
            }
        ],
        "recommendations": ["Reduce slide text"],
    }
    state["revision_count"] = 0

    update = await node(state)
    assert update["learning_result"] is not None
    assert update["learning_result"]["category"] == "presentation"
    assert update["learning_result"]["key"] == "slide_text"

    rules = await learning.get_rules(client_id=client_id)
    assert len(rules) == 1


@pytest.mark.asyncio
async def test_revision_skips_learning_without_durable_signal(settings: Settings, client_id) -> None:
    gateway, _ = mock_gateway(settings, revision_json())
    learning = LearningManager(InMemoryLearningStore(), llm_gateway=gateway)
    node = RevisionNode(RevisionManager(RevisionAgent(gateway)), learning_manager=learning)

    state = create_initial_state(
        execution_id="exec-learn-2",
        trace_id="trace-learn-2",
        user_input="Revise",
        metadata={
            "client_id": str(client_id),
            "user_feedback": "Исправь опечатку в заголовке",
        },
    )
    state["review_result"] = {"status": "revise", "issues": [], "recommendations": []}
    state["revision_count"] = 0

    update = await node(state)
    assert update.get("learning_result") is None
    assert await learning.get_rules(client_id=client_id) == []


def test_priority_includes_learning_context() -> None:
    context = build_prioritized_context(
        ExecutionContext(
            user_input="hello",
            knowledge_context=[{"title": "Tone"}],
            research_context={"summary": "Research note"},
            client_intelligence_context={"summary": "Client profile"},
            learning_context=[{"category": "presentation", "rule": "less text on slides"}],
        )
    )
    keys = list(context.keys())
    assert keys.index("knowledge_context") < keys.index("research_context")
    assert keys.index("research_context") < keys.index("client_intelligence_context")
    assert keys.index("client_intelligence_context") < keys.index("learning_context")
