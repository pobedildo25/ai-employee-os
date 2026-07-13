"""Opt-in live Executive eval against OpenRouter.

Catalog / fixture scenarios in ``test_executive_decision_scenarios.py`` are **not**
live LLM proof. This module is a minimal honest spot-check harness.

How to run
----------
1. Ensure ``OPENROUTER_API_KEY`` (and related Settings) are set for a real provider.
2. Enable the harness::

       set LIVE_EXECUTIVE_EVAL=1
       cd backend
       .\\.venv\\Scripts\\python.exe -m pytest tests/test_executive_live_eval.py -q --tb=short

Skipped by default (no ``LIVE_EXECUTIVE_EVAL=1``) so CI stays deterministic.
"""

from __future__ import annotations

import os

import pytest

from app.agents.decision.models import DecisionType
from app.agents.executive.agent import ExecutiveAgent
from app.agent_runtime.state.models import create_initial_state
from app.core.config import Settings
from app.llm.gateway import create_llm_gateway

pytestmark = pytest.mark.live

_LIVE = os.environ.get("LIVE_EXECUTIVE_EVAL", "").strip() == "1"

# Golden prompts: expected DecisionType is the product contract target.
# Live model output may diverge — failures are signal, not CI blockers.
LIVE_GOLDEN: list[tuple[str, str, DecisionType]] = [
    ("live-respond-fx", "Какой сейчас курс доллара?", DecisionType.RESPOND),
    ("live-execute-kp", "Сделай коммерческое предложение на AI-автоматизацию", DecisionType.EXECUTE),
    ("live-clarify-vague", "Сделай что-нибудь", DecisionType.ASK_CLARIFICATION),
    ("live-plan-multistage", "Подготовь стратегию выхода на новый рынок: исследование, позиционирование, КП и план внедрения", DecisionType.CREATE_PLAN),
    ("live-respond-consult", "Объясни плюсы и минусы короткого КП против длинного", DecisionType.RESPOND),
]


def _skip_unless_live() -> None:
    if not _LIVE:
        pytest.skip("Set LIVE_EXECUTIVE_EVAL=1 to run live OpenRouter Executive eval")


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario_id,prompt,expected", LIVE_GOLDEN)
async def test_live_executive_decision(
    scenario_id: str,
    prompt: str,
    expected: DecisionType,
) -> None:
    _skip_unless_live()
    settings = Settings()
    if not settings.openrouter_api_key:
        pytest.skip("OPENROUTER_API_KEY required for live Executive eval")

    gateway = create_llm_gateway(settings)
    agent = ExecutiveAgent(gateway)
    state = create_initial_state(
        execution_id=f"live-eval-{scenario_id}",
        trace_id=f"live-eval-{scenario_id}",
        user_input=prompt,
    )
    result = await agent.analyze(state)
    assert result.decision.action == expected, (
        f"{scenario_id}: expected {expected.value}, got {result.decision.action.value} "
        f"(goal={result.understanding.goal!r})"
    )
