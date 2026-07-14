"""P2 employee UX — human plan/progress labels, no internal jargon."""

from app.ux.human_labels import human_approval_bullet, human_progress_title
from app.conversation.messages import format_approval_message, format_slash_status
from app.conversation.models import ConversationState, FlowMode


def test_progress_title_never_leaks_capability_id() -> None:
    assert "_" not in human_progress_title(capability="document_rendering")
    assert human_progress_title(capability="quality_review").startswith("Проверяю")


def test_approval_message_is_employee_proposal() -> None:
    text = format_approval_message(
        {
            "steps": [
                {"capability": "research"},
                {"capability": "strategy_analysis"},
                {"capability": "document_creation"},
                {"capability": "quality_review"},
            ]
        }
    )
    assert "Предлагаю такой порядок" in text
    assert "Всё выполнить сразу" in text
    assert "•" in text
    assert "capability" not in text.lower()
    assert "pipeline" not in text.lower()
    assert "research" not in text
    assert "quality_review" not in text


def test_approval_bullet_prefers_human_capability_map() -> None:
    assert human_approval_bullet({"capability": "presentation_design"}) == "соберу презентацию"


def test_status_waiting_approval_has_no_plan_jargon() -> None:
    convo = ConversationState(
        user_id=1,
        chat_id=1,
        flow_mode=FlowMode.WAITING_APPROVAL,
    )
    text = format_slash_status(convo)
    assert "плана" not in text
    assert "подтверждения" in text
