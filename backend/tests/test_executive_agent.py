import pytest

from app.agent_runtime.checkpoint.manager import InMemoryCheckpointManager
from app.agent_runtime.runtime import AgentRuntime, build_executive_graph
from app.agents.decision.models import DecisionType
from app.agents.executive.agent import ExecutiveAgent
from app.agents.parsers.response_parser import ResponseParseError, parse_executive_response
from app.core.config import Settings
from app.agent_runtime.state.models import create_initial_state
from tests.llm_fixtures import creation_ast_json as _creation_ast_json
from tests.llm_fixtures import executive_json as _executive_json
from tests.llm_fixtures import mock_gateway as _mock_gateway
from tests.llm_fixtures import review_json as _review_json


@pytest.fixture
def settings() -> Settings:
    return Settings(
        openrouter_api_key="test-key",
        openrouter_base_url="https://openrouter.ai/api/v1",
        default_llm_model="mock-model",
        fallback_llm_model="fallback-model",
    )


@pytest.mark.asyncio
async def test_greeting_returns_respond(settings: Settings) -> None:
    gateway, _ = _mock_gateway(
        settings,
        _executive_json(
            goal="поздороваться",
            summary="Пользователь здоровается",
            action="RESPOND",
            next_action="respond",
            response_message="Привет! Чем могу помочь?",
        ),
    )
    runtime = AgentRuntime(
        graph=build_executive_graph(gateway),
        checkpoint_manager=InMemoryCheckpointManager(),
    )

    result = await runtime.execute("Привет")

    assert result["decision"]["action"] == DecisionType.RESPOND.value
    assert result["understanding"]["goal"] == "поздороваться"
    assert result["result"]["decision"]["action"] == "RESPOND"


@pytest.mark.asyncio
async def test_vague_artifact_request_asks_clarification(settings: Settings) -> None:
    gateway, provider = _mock_gateway(
        settings,
        _executive_json(
            goal="создать коммерческое предложение",
            summary="Не хватает данных клиента и оффера",
            action="ASK_CLARIFICATION",
            required_capabilities=["document_generation"],
            missing_information=["данные клиента", "услуги и цены"],
            next_action="request_information",
            clarification_question="Для какого клиента и какого предложения нужно КП?",
        ),
    )
    runtime = AgentRuntime(
        graph=build_executive_graph(gateway),
        checkpoint_manager=InMemoryCheckpointManager(),
    )

    result = await runtime.execute("Сделай коммерческое предложение")

    assert result["decision"]["action"] == DecisionType.ASK_CLARIFICATION.value
    assert result["decision"]["clarification_question"]
    assert result["understanding"]["missing_information"]
    assert result.get("task_plan") is None
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_clear_proposal_request_executes_without_planner(settings: Settings) -> None:
    gateway, provider = _mock_gateway(
        settings,
        _executive_json(
            goal="создать коммерческое предложение",
            summary="КП для клиента Acme по SEO",
            action="EXECUTE",
            required_capabilities=["document_generation"],
            next_action="execute",
        ),
        _review_json(),
    )
    runtime = AgentRuntime(
        graph=build_executive_graph(gateway),
        checkpoint_manager=InMemoryCheckpointManager(),
    )

    result = await runtime.execute(
        "Сделай коммерческое предложение для Acme: SEO-аудит, срок 2 недели, бюджет 150к"
    )

    assert result["decision"]["action"] == DecisionType.EXECUTE.value
    assert result["task_plan"] is not None
    caps = [step["capability"] for step in result["task_plan"]["steps"]]
    # Resolver expands document_generation → document_rendering for linear EXECUTE.
    assert caps[0] == "document_generation"
    assert "document_rendering" in caps
    # First LLM call is Executive; quality review may follow after the render chain.
    assert len(provider.calls) >= 1
    assert "NOVA" in provider.calls[0].messages[0].content


@pytest.mark.asyncio
async def test_vague_request_asks_clarification(settings: Settings) -> None:
    gateway, _ = _mock_gateway(
        settings,
        _executive_json(
            goal="улучшить результат",
            summary="Запрос слишком расплывчатый, непонятно что улучшать",
            action="ASK_CLARIFICATION",
            next_action="request_information",
            clarification_question="Что именно нужно улучшить? Уточните объект и критерии.",
        ),
    )
    runtime = AgentRuntime(
        graph=build_executive_graph(gateway),
        checkpoint_manager=InMemoryCheckpointManager(),
    )

    result = await runtime.execute("Сделай лучше")

    assert result["decision"]["action"] == DecisionType.ASK_CLARIFICATION.value
    assert result["decision"]["clarification_question"]


def test_parse_executive_response_valid_json() -> None:
    raw = _executive_json(
        goal="test goal",
        summary="test summary",
        action="RESPOND",
        response_message="hello",
    )
    result = parse_executive_response(raw)
    assert result.understanding.goal == "test goal"
    assert result.decision.action == DecisionType.RESPOND


def test_parse_executive_response_json_block() -> None:
    raw = f"```json\n{_executive_json(goal='g', summary='s', action='EXECUTE', next_action='execute')}\n```"
    result = parse_executive_response(raw)
    assert result.decision.action == DecisionType.EXECUTE


def test_parse_executive_response_invalid_json() -> None:
    with pytest.raises(ResponseParseError, match="Invalid JSON"):
        parse_executive_response("not json")


def test_parse_executive_response_invalid_schema() -> None:
    with pytest.raises(ResponseParseError, match="Schema validation failed"):
        parse_executive_response('{"understanding": {}}')


@pytest.mark.asyncio
async def test_executive_agent_retries_on_invalid_json(settings: Settings) -> None:
    valid = _executive_json(
        goal="test",
        summary="test",
        action="RESPOND",
        response_message="ok",
    )
    gateway, provider = _mock_gateway(settings, "invalid json", valid)
    agent = ExecutiveAgent(gateway, max_retries=3)

    state = create_initial_state(
        execution_id="e1",
        trace_id="t1",
        user_input="test",
    )
    result = await agent.analyze(state)

    assert result.decision.action == DecisionType.RESPOND
    assert len(provider.calls) == 2


@pytest.mark.asyncio
async def test_executive_agent_degrades_after_max_parse_retries(settings: Settings) -> None:
    gateway, provider = _mock_gateway(settings, "bad", "bad", "bad")
    agent = ExecutiveAgent(gateway, max_retries=3)

    state = create_initial_state(
        execution_id="e1",
        trace_id="t1",
        user_input="test",
    )

    result = await agent.analyze(state)
    assert result.decision.action == DecisionType.RESPOND
    assert "временно" in (result.decision.response_message or "").lower() or "ошибк" in (
        result.decision.response_message or ""
    ).lower()
    assert len(provider.calls) == 3


@pytest.mark.asyncio
async def test_executive_graph_full_workflow(settings: Settings) -> None:
    gateway, provider = _mock_gateway(
        settings,
        _executive_json(
            goal="анализ документа",
            summary="Нужен анализ",
            action="EXECUTE",
            required_capabilities=["document_analysis"],
            next_action="execute",
        ),
    )
    runtime = AgentRuntime(
        graph=build_executive_graph(gateway),
        checkpoint_manager=InMemoryCheckpointManager(),
    )

    result = await runtime.execute(
        "Проанализируй отчёт",
        trace_id="trace-exec",
    )

    assert result["status"] == "completed"
    assert result["trace_id"] == "trace-exec"
    assert result["result"]["understanding"]["goal"] == "анализ документа"
    assert result["result"]["decision"]["action"] == "EXECUTE"
    assert result["task_plan"]["steps"][0]["capability"] == "document_analysis"
    assert result["execution_graph"] is None
    # document_analysis without extracted_content → fail, not silent COMPLETED.
    assert result["task_execution"]["status"] == "FAILED"
    assert result["progress"] < 100.0
    assert len(provider.calls) == 1