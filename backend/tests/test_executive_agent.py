import pytest

from app.agent_runtime.checkpoint.manager import InMemoryCheckpointManager
from app.agent_runtime.runtime import AgentRuntime, build_executive_graph
from app.agents.decision.models import DecisionType
from app.agents.executive.agent import ExecutiveAgent, ExecutiveAgentError
from app.agents.parsers.response_parser import ResponseParseError, parse_executive_response
from app.core.config import Settings
from app.agent_runtime.state.models import create_initial_state
from tests.llm_fixtures import creation_ast_json as _creation_ast_json
from tests.llm_fixtures import executive_json as _executive_json
from tests.llm_fixtures import mock_gateway as _mock_gateway
from tests.llm_fixtures import plan_json as _plan_json
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
async def test_proposal_request_understands_goal_and_capabilities(settings: Settings) -> None:
    gateway, _ = _mock_gateway(
        settings,
        _executive_json(
            goal="создать коммерческое предложение",
            summary="Пользователь хочет подготовить КП",
            action="CREATE_PLAN",
            required_capabilities=["document_generation", "brand_style", "document_analysis"],
            missing_information=["данные клиента", "услуги и цены"],
            next_action="request_information",
        ),
        _plan_json(goal="создать коммерческое предложение"),
        _creation_ast_json(title="Commercial proposal"),
        _review_json(),
    )
    runtime = AgentRuntime(
        graph=build_executive_graph(gateway),
        checkpoint_manager=InMemoryCheckpointManager(),
    )

    result = await runtime.execute("Сделай коммерческое предложение")

    understanding = result["understanding"]
    assert understanding["goal"] == "создать коммерческое предложение"
    assert "document_generation" in understanding["required_capabilities"]
    assert len(understanding["required_capabilities"]) >= 2
    assert understanding["missing_information"]


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
async def test_executive_agent_raises_after_max_retries(settings: Settings) -> None:
    gateway, _ = _mock_gateway(settings, "bad", "bad", "bad")
    agent = ExecutiveAgent(gateway, max_retries=3)

    state = create_initial_state(
        execution_id="e1",
        trace_id="t1",
        user_input="test",
    )

    with pytest.raises(ExecutiveAgentError, match="Failed to obtain valid"):
        await agent.analyze(state)


@pytest.mark.asyncio
async def test_executive_graph_full_workflow(settings: Settings) -> None:
    gateway, _ = _mock_gateway(
        settings,
        _executive_json(
            goal="анализ данных",
            summary="Нужен анализ",
            action="EXECUTE",
            required_capabilities=["data_analysis"],
            next_action="execute",
        ),
        _plan_json(
            goal="анализ данных",
            steps=[
                {"description": "Analyze report", "capability": "data_analysis", "dependencies": []},
            ],
        ),
        _creation_ast_json(title="Data Analysis Report"),
        _review_json(),
    )
    runtime = AgentRuntime(
        graph=build_executive_graph(gateway),
        checkpoint_manager=InMemoryCheckpointManager(),
    )

    result = await runtime.execute(
        "Проанализируй отчёт",
        trace_id="trace-exec",
        metadata={"auto_approve": True},
    )

    assert result["status"] == "completed"
    assert result["trace_id"] == "trace-exec"
    assert result["current_step"] == "quality_gate"
    assert result["result"]["understanding"]["goal"] == "анализ данных"
    assert result["result"]["decision"]["action"] == "EXECUTE"
    assert result["document_ast"] is not None