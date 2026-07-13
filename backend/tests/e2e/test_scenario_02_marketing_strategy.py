from io import BytesIO

import pytest
from pptx import Presentation

from app.document_renderer.models import OutputFormat, RenderRequest
from app.document_renderer.renderer import DocumentRendererService
from tests.e2e.helpers import marketing_plan_steps
from tests.llm_fixtures import (
    executive_json,
    plan_json,
    presentation_plan_json,
    research_interpretation_json,
    review_json,
    strategy_result_json,
)


@pytest.mark.asyncio
async def test_marketing_strategy_flow_with_presentation(
    e2e_runtime_factory,
    client_project_ids,
) -> None:
    client_id, project_id = client_project_ids
    runtime, gateway, provider, _registry = e2e_runtime_factory(
        executive_json(
            goal="Исследуй рынок AI маркетинга и подготовь стратегию с презентацией",
            summary="Нужны research, strategy и deck",
            action="CREATE_PLAN",
            required_capabilities=["research", "strategy_analysis", "presentation_design", "document_rendering"],
            next_action="create_plan",
        ),
        plan_json(
            goal="Исследуй рынок AI маркетинга и подготовь стратегию с презентацией",
            steps=marketing_plan_steps(),
        ),
        research_interpretation_json(),
        strategy_result_json(summary="AI marketing focus for SMB"),
        presentation_plan_json(title="AI Marketing Strategy"),
        review_json(score=0.91, summary="Strategy deck is structured and on-brand"),
        research_enabled=True,
    )

    result = await runtime.execute(
        "Исследуй рынок AI маркетинга и подготовь стратегию с презентацией",
        context={"client_id": str(client_id), "project_id": str(project_id)},
        metadata={
            "auto_approve": True,
            "client_id": str(client_id),
            "project_id": str(project_id),
            "requires_llm_plan": True,
        },
    )

    assert result["task_execution"]["status"] == "COMPLETED"
    assert result["quality_check"]["passed"] is True

    steps = {step["description"]: step for step in result["task_plan"]["steps"]}
    strategy_step = steps["Strategy analysis"]
    presentation_step = steps["Presentation design"]
    render_step = steps["Render presentation"]

    assert strategy_step["status"] == "COMPLETED"
    assert strategy_step["result"]["strategy_result"]["summary"]

    assert presentation_step["status"] == "COMPLETED"
    assert presentation_step["result"]["presentation_plan"]["slides"]
    assert presentation_step["result"]["document_ast"]

    assert render_step["status"] == "COMPLETED"
    render_result = render_step["result"]["render_result"]
    assert render_result is not None

    ast = presentation_step["result"]["document_ast"]
    rendered = DocumentRendererService().render(
        RenderRequest(
            document_structure=ast,
            output_format=OutputFormat.PPTX,
            metadata={"document_type": "pptx"},
        )
    )
    assert rendered.file_bytes
    presentation = Presentation(BytesIO(rendered.file_bytes))
    assert len(presentation.slides) >= 1
    assert provider.calls
