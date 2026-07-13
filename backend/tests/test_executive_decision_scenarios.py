"""≥150 decision-engine scenarios for product behaviour acceptance.

Scenarios encode the product contract (expected DecisionType).
Runtime assertions check routing policies — never keyword-match user text.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.agents.decision.models import DecisionType
from app.agents.decision.policy import (
    is_chat_action,
    is_task_action,
    requires_human_approval,
    should_direct_execute,
    should_invoke_planner,
)
from app.agents.executive.prompt import EXECUTIVE_SYSTEM_PROMPT
from app.agents.intent.policy import is_chat_decision, is_task_decision, needs_planner
from app.planning.direct_plan import build_direct_execution_plan
from app.planning.policies.execution_policy import requires_approval, should_plan


@dataclass(frozen=True)
class DecisionScenario:
    id: str
    user_input: str
    expected_action: DecisionType
    category: str


def _respond(sid: str, text: str, category: str) -> DecisionScenario:
    return DecisionScenario(sid, text, DecisionType.RESPOND, category)


def _clarify(sid: str, text: str, category: str = "clarify") -> DecisionScenario:
    return DecisionScenario(sid, text, DecisionType.ASK_CLARIFICATION, category)


def _execute(sid: str, text: str, category: str = "execute") -> DecisionScenario:
    return DecisionScenario(sid, text, DecisionType.EXECUTE, category)


def _plan(sid: str, text: str, category: str = "plan") -> DecisionScenario:
    return DecisionScenario(sid, text, DecisionType.CREATE_PLAN, category)


SCENARIOS: list[DecisionScenario] = [
    # --- Greetings / chat (1-15) ---
    _respond("R01", "Привет", "chat"),
    _respond("R02", "Здравствуй", "chat"),
    _respond("R03", "Добрый день", "chat"),
    _respond("R04", "Hi", "chat"),
    _respond("R05", "Hello", "chat"),
    _respond("R06", "Как дела?", "chat"),
    _respond("R07", "Как ты?", "chat"),
    _respond("R08", "Кто ты?", "chat"),
    _respond("R09", "Что умеешь?", "chat"),
    _respond("R10", "Расскажи о себе", "chat"),
    _respond("R11", "Спасибо", "chat"),
    _respond("R12", "Благодарю", "chat"),
    _respond("R13", "Пока", "chat"),
    _respond("R14", "До связи", "chat"),
    _respond("R15", "Ок, понял", "chat"),
    # --- Questions / explanations (16-45) ---
    _respond("R16", "Что такое RAG?", "qa"),
    _respond("R17", "Объясни MCP", "qa"),
    _respond("R18", "Объясни SWOT", "qa"),
    _respond("R19", "Расскажи про SWOT", "qa"),
    _respond("R20", "Что такое KPI?", "qa"),
    _respond("R21", "Чем отличается B2B от B2C?", "qa"),
    _respond("R22", "Как работает контекстное окно LLM?", "qa"),
    _respond("R23", "Что такое positioning?", "qa"),
    _respond("R24", "Объясни customer journey", "qa"),
    _respond("R25", "Что значит unit-экономика?", "qa"),
    _respond("R26", "Как считать CAC?", "qa"),
    _respond("R27", "Что такое AIDA?", "qa"),
    _respond("R28", "Объясни разницу между брендингом и маркетингом", "qa"),
    _respond("R29", "Что такое value proposition?", "qa"),
    _respond("R30", "Как устроен OpenRouter?", "qa"),
    _respond("R31", "Что такое embeddings?", "qa"),
    _respond("R32", "Объясни vector search простыми словами", "qa"),
    _respond("R33", "Что такое LangGraph?", "qa"),
    _respond("R34", "Зачем нужен Executive Agent?", "qa"),
    _respond("R35", "Как писать хорошие промпты?", "qa"),
    _respond("R36", "Что такое tone of voice?", "qa"),
    _respond("R37", "Объясни воронку продаж", "qa"),
    _respond("R38", "Что такое ICP?", "qa"),
    _respond("R39", "Чем brief отличается от ТЗ?", "qa"),
    _respond("R40", "Как провести discovery-интервью?", "qa"),
    _respond("R41", "Что такое go-to-market?", "qa"),
    _respond("R42", "Объясни JTBD", "qa"),
    _respond("R43", "Что такое north star metric?", "qa"),
    _respond("R44", "Как приоритизировать гипотезы?", "qa"),
    _respond("R45", "Что такое content-маркетинг?", "qa"),
    # --- News / lookup / forecasts (46-60) ---
    _respond("R46", "Какой курс доллара?", "lookup"),
    _respond("R47", "Какой курс евро сегодня?", "lookup"),
    _respond("R48", "Что нового у OpenAI?", "news"),
    _respond("R49", "Что нового у Anthropic?", "news"),
    _respond("R50", "Какие тренды в digital marketing 2026?", "news"),
    _respond("R51", "Что происходит на рынке AI?", "news"),
    _respond("R52", "Какая погода в Москве?", "lookup"),
    _respond("R53", "Сколько сейчас стоит Bitcoin?", "lookup"),
    _respond("R54", "Какие новости у Google Gemini?", "news"),
    _respond("R55", "Кратко: что случилось с TikTok в США?", "news"),
    _respond("R56", "Прогноз роста e-commerce в РФ", "forecast"),
    _respond("R57", "Как будет меняться performance-реклама?", "forecast"),
    _respond("R58", "Есть ли смысл запускать Telegram Ads сейчас?", "consult"),
    _respond("R59", "Стоит ли агентству внедрять AI-сотрудника?", "consult"),
    _respond("R60", "Какой канал лучше для B2B SaaS?", "consult"),
    # --- Consultations / opinions (61-70) ---
    _respond("R61", "Как улучшить CTR баннера?", "consult"),
    _respond("R62", "Посоветуй структуру лендинга", "consult"),
    _respond("R63", "Как сформулировать оффер для юристов?", "consult"),
    _respond("R64", "Нужен ли нам rebranding?", "consult"),
    _respond("R65", "Как отвечать на возражение «дорого»?", "consult"),
    _respond("R66", "Сравни email и мессенджеры для nurture", "consult"),
    _respond("R67", "Какой формат кейса лучше для сайта?", "consult"),
    _respond("R68", "Как сократить цикл сделки?", "consult"),
    _respond("R69", "Что важнее: бренд или performance?", "consult"),
    _respond("R70", "Как измерить эффект контента?", "consult"),
    # --- Draft-first EXECUTE for underspecified artifacts (was clarify) ---
    _execute("E19", "Сделай коммерческое предложение", "draft"),
    _execute("E20", "Подготовь презентацию", "draft"),
    _execute("E21", "Напиши письмо клиенту", "draft"),
    _execute("E22", "Сделай КП", "draft"),
    _execute("E23", "Подготовь стратегию", "draft"),
    _execute("E24", "Сделай документ", "draft"),
    _execute("E25", "Напиши письмо", "draft"),
    _execute("E26", "Создай презентацию", "draft"),
    _execute("E27", "Сделай отчёт", "draft"),
    _execute("E28", "Подготовь предложение", "draft"),
    # --- Clarifications only when nothing to draft ---
    _clarify("C01", "Сделай лучше"),
    _clarify("C02", "Переделай"),
    _clarify("C03", "Исправь"),
    _clarify("C04", "Измени это"),
    _clarify("C05", "Доработай"),
    # --- Single-skill EXECUTE (detailed) ---
    _execute("E01", "Создай SWOT-анализ для бренда кофеен CoffeeLab"),
    _execute("E02", "Напиши коммерческое предложение для Acme: SEO-аудит, 150к, 2 недели"),
    _execute("E03", "Подготовь стратегию digital для фитнес-клуба FitNow на Q3"),
    _execute("E04", "Создай презентацию о результатах кампании для клиента Nord"),
    _execute("E05", "Сделай КП для ООО Ромашка: контекстная реклама Яндекс, бюджет 300к"),
    _execute("E06", "Напиши письмо клиенту Иванову с апдейтом по проекту и next steps"),
    _execute("E07", "Подготовь brief на съёмку для бренда Atelier"),
    _execute("E08", "Сделай competitor analysis по рынку доставки еды в Казани"),
    _execute("E09", "Создай one-pager про наш AI Employee OS для питча"),
    _execute("E10", "Подготовь media plan на месяц для бренда YouthWear"),
    _execute("E11", "Сделай презентацию услуги performance для нового клиента"),
    _execute("E12", "Напиши стратегию контента для LinkedIn B2B SaaS"),
    _execute("E13", "Создай документ с позиционированием для стартапа Helix"),
    _execute("E14", "Подготовь аналитический отчёт по воронке за июнь для проекта Orion"),
    _execute("E15", "Сделай ревизию текущего КП: сократи текст и усиль оффер", "revision"),
    _execute("E16", "Создай презентацию кейса для тендера RetailMax"),
    _execute("E17", "Напиши коммерческое предложение на SMM для локальной сети кафе"),
    _execute("E18", "Подготовь SWOT после созвона с клиентом BetaCorp"),
    # --- Multi-stage CREATE_PLAN (101-110) ---
    _plan(
        "P01",
        "Исследуй рынок → подготовь стратегию → создай презентацию → сформируй КП для клиента Aurora",
    ),
    _plan(
        "P02",
        "Собери research по конкурентам, на его основе сделай стратегию и презентацию для питча",
    ),
    _plan(
        "P03",
        "Проанализируй брендбук, подготовь стратегию коммуникации и финальную презентацию совету директоров",
    ),
    _plan(
        "P04",
        "Сделай исследование аудитории, затем стратегию, затем серию документов: КП и презентацию",
    ),
    _plan(
        "P05",
        "Нужен полный пакет: research рынка, стратегия go-to-market, презентация инвесторам и КП партнёру",
    ),
    _plan(
        "P06",
        "Сначала проанализируй звонок с клиентом, потом стратегию, потом презентацию результатов",
    ),
    _plan(
        "P07",
        "Исследуй категорию beauty, подготовь позиционирование, стратегию и pitch deck",
    ),
    _plan(
        "P08",
        "Собери аналитику кампаний, сделай выводы, стратегию оптимизации и презентацию для клиента",
    ),
    # --- Extra natural dialogue RESPOND (111-120) ---
    _respond("R71", "Можешь повторить проще?", "chat"),
    _respond("R72", "Приведи пример SWOT на кофейне", "qa"),
    _respond("R73", "В двух предложениях: что такое brand platform?", "qa"),
    _respond("R74", "Это хорошая идея для агентства?", "consult"),
    _respond("R75", "Какие риски у performance-only модели?", "consult"),
    _respond("R76", "Сколько слайдов обычно в питче?", "qa"),
    _respond("R77", "Чем SWOT отличается от PEST?", "qa"),
    _respond("R78", "Нужно ли всегда делать research перед стратегией?", "consult"),
    _respond("R79", "Как NOVA принимает решения?", "qa"),
    _respond("R80", "Ты умеешь делать презентации?", "chat"),
    # --- Forecasts (extra) ---
    _respond("F01", "Как вырастет рынок influencer-маркетинга к 2027?", "forecast"),
    _respond("F02", "Какой прогноз по CPM в Meta на следующий квартал?", "forecast"),
    _respond("F03", "Будет ли спрос на AI-агентов в агентствах расти?", "forecast"),
    _respond("F04", "Что будет с SEO после AI Overviews?", "forecast"),
    _respond("F05", "Прогноз: короткое видео vs long-form в 2026", "forecast"),
    _respond("F06", "Как изменится роль креатива при генеративном AI?", "forecast"),
    _respond("F07", "Ожидания по бюджету performance в retail на Чёрную пятницу", "forecast"),
    _respond("F08", "Тренд: персонализация email — куда движется рынок?", "forecast"),
    # --- News / lookup honesty ---
    _respond("N01", "Что нового у Midjourney?", "news"),
    _respond("N02", "Какие свежие апдейты у ChatGPT?", "news"),
    _respond("N03", "Новости рынка programmatic за неделю", "news"),
    _respond("N04", "Что пишут про релиз Claude?", "news"),
    _respond("N05", "Какой сейчас курс юаня?", "lookup"),
    _respond("N06", "Сколько стоит баррель нефти?", "lookup"),
    # --- Dialogue continuation ---
    _respond("D01", "А можешь чуть подробнее?", "dialogue"),
    _respond("D02", "Ок, а теперь на примере агентства", "dialogue"),
    _respond("D03", "Согласен, идём дальше", "dialogue"),
    _respond("D04", "Подожди, уточни про второй пункт", "dialogue"),
    _respond("D05", "Да, именно это я имел в виду", "dialogue"),
    _respond("D06", "Нет, давай другой угол", "dialogue"),
    _respond("D07", "Сохрани этот вывод на потом", "dialogue"),
    _respond("D08", "Вернёмся к тому, что обсуждали про KPI", "dialogue"),
    # --- Memory / preferences as chat (system learns later) ---
    _respond("M01", "Запомни: клиенту Aurora всегда нужен короткий питч", "memory"),
    _respond("M02", "Предпочитаю таблицы вместо длинного текста", "memory"),
    _respond("M03", "Не используй канцелярит в письмах", "memory"),
    _respond("M04", "У нас brand voice — дружелюбный и прямой", "memory"),
    _respond("M05", "Всегда пиши next steps списком", "memory"),
    _respond("M06", "Клиент не любит слово «синергия»", "memory"),
    # --- Learning signals ---
    _respond("L01", "Всегда делай слайды короче", "learning"),
    _respond("L02", "Никогда не ставь больше 5 bullets на слайд", "learning"),
    _respond("L03", "В следующий раз без воды в summary", "learning"),
    _respond("L04", "Отныне для КП используй структуру проблема-решение-цена", "learning"),
    _respond("L05", "Учти: для этого клиента важнее кейсы, чем теория", "learning"),
    # --- Revision as EXECUTE when artifact context implied ---
    _execute("RV01", "Сделай короче текущий документ", "revision"),
    _execute("RV02", "Добавь таблицу сравнения в презентацию", "revision"),
    _execute("RV03", "Усиль оффер в КП и убери повторы", "revision"),
    _execute("RV04", "Перепиши введение в более деловом тоне", "revision"),
    _execute("RV05", "Исправь структуру слайдов: сначала вывод, потом детали", "revision"),
    # --- Research / strategy EXECUTE ---
    _execute("RS01", "Исследуй конкурентов Delivery Club в Казани", "research"),
    _execute("RS02", "Собери brief по трендам beauty e-com", "research"),
    _execute("RS03", "Сделай SWOT для сервиса подписок CoffeeLab", "strategy"),
    _execute("RS04", "Подготовь go-to-market гипотезы для B2B SaaS Helix", "strategy"),
    _execute("RS05", "Напиши positioning statement для YouthWear", "strategy"),
]


assert len(SCENARIOS) >= 150, f"Need ≥150 scenarios, got {len(SCENARIOS)}"


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s.id for s in SCENARIOS])
def test_decision_routing_contract(scenario: DecisionScenario) -> None:
    """Given the expected action, planner/approval/chat routing must match Stage A."""
    action = scenario.expected_action.value

    if scenario.expected_action == DecisionType.RESPOND:
        assert is_chat_decision(action)
        assert not is_task_decision(action)
        assert should_plan(action) is False
        assert should_invoke_planner(action) is False
        assert should_direct_execute(action) is False
        assert requires_approval(action) is False

    elif scenario.expected_action == DecisionType.ASK_CLARIFICATION:
        assert is_chat_decision(action)
        assert not is_task_decision(action)
        assert should_plan(action) is False
        assert should_direct_execute(action) is False
        assert requires_human_approval(action) is False

    elif scenario.expected_action == DecisionType.EXECUTE:
        assert is_task_action(action)
        assert is_task_decision(action)
        assert needs_planner(action) is False
        assert should_plan(action) is False
        assert should_direct_execute(action) is True
        assert requires_approval(action) is False
        assert requires_human_approval(action) is False

    elif scenario.expected_action == DecisionType.CREATE_PLAN:
        assert is_task_decision(action)
        assert should_plan(action) is True
        assert should_invoke_planner(action) is True
        assert should_direct_execute(action) is False
        # Without a plan object, CREATE_PLAN may still require approval.
        assert requires_approval(action) is True
        assert requires_human_approval(action) is True


def test_scenario_catalog_size_and_coverage() -> None:
    assert len(SCENARIOS) >= 150
    by_action = {action: 0 for action in DecisionType}
    by_category: dict[str, int] = {}
    for scenario in SCENARIOS:
        by_action[scenario.expected_action] += 1
        by_category[scenario.category] = by_category.get(scenario.category, 0) + 1
    assert by_action[DecisionType.RESPOND] >= 70
    assert by_action[DecisionType.ASK_CLARIFICATION] >= 5
    assert by_action[DecisionType.EXECUTE] >= 30
    assert by_action[DecisionType.CREATE_PLAN] >= 5
    for required in (
        "chat",
        "qa",
        "news",
        "forecast",
        "draft",
        "revision",
        "learning",
        "memory",
        "dialogue",
        "research",
        "strategy",
    ):
        assert by_category.get(required, 0) >= 1, f"missing category {required}"


def test_execute_does_not_equal_create_plan_in_policies() -> None:
    assert should_plan(DecisionType.EXECUTE.value) is False
    assert should_plan(DecisionType.CREATE_PLAN.value) is True
    assert should_direct_execute(DecisionType.EXECUTE.value) is True
    assert should_direct_execute(DecisionType.CREATE_PLAN.value) is False
    assert requires_approval(DecisionType.EXECUTE.value) is False
    assert requires_approval(DecisionType.CREATE_PLAN.value) is True
    single = build_direct_execution_plan(
        goal="x", summary="x", required_capabilities=["strategy_analysis"]
    )
    multi = build_direct_execution_plan(
        goal="x",
        summary="x",
        required_capabilities=["research", "strategy_analysis"],
    )
    assert requires_approval(DecisionType.CREATE_PLAN.value, single) is False
    assert requires_approval(DecisionType.CREATE_PLAN.value, multi) is True


def test_policies_ignore_user_text() -> None:
    """Routing helpers accept only DecisionType — never user utterances."""
    toxic_looking = "Сделай план презентацию стратегию research CREATE_PLAN"
    assert should_plan(toxic_looking) is False
    assert should_direct_execute(toxic_looking) is False
    assert is_chat_action(toxic_looking) is False
    assert is_task_action(toxic_looking) is False


def test_normalize_action_handles_enum_instances() -> None:
    from app.agents.decision.policy import normalize_action

    assert normalize_action(DecisionType.RESPOND) == "RESPOND"
    assert normalize_action(DecisionType.EXECUTE) == "EXECUTE"
    assert is_chat_action(DecisionType.RESPOND) is True
    assert should_direct_execute(DecisionType.EXECUTE) is True
    assert should_invoke_planner(DecisionType.CREATE_PLAN) is True
    assert should_invoke_planner(DecisionType.EXECUTE) is False


def test_executive_prompt_prefers_assistant_like_respond() -> None:
    prompt = EXECUTIVE_SYSTEM_PROMPT
    assert "RESPOND" in prompt
    assert "modern AI assistant" in prompt
    assert "CREATE_PLAN — only for objectively multi-stage" in prompt
    assert "Never match keywords" in prompt
    assert "prefer a direct useful reply" in prompt
    assert "draft-first" in prompt or "Prefer draft-first" in prompt
    assert "up-to-the-minute" in prompt or "real-time" in prompt
    assert "Capability Resolver owns" in prompt
    assert "≥2" not in prompt
    assert "linear multi-skill" in prompt.lower() or "Linear multi-skill" in prompt


def test_direct_plan_builder_for_execute_capabilities() -> None:
    plan = build_direct_execution_plan(
        goal="SWOT",
        summary="Single artifact",
        required_capabilities=["strategy_analysis", ""],
    )
    assert len(plan.steps) == 1
    assert plan.steps[0].capability == "strategy_analysis"
    assert plan.required_capabilities == ["strategy_analysis"]
