from app.skills.base.skill import BaseSkill
from app.skills.models import Capability, SkillMetadata


class AnalysisSkill(BaseSkill):
    """Analysis-related capabilities."""

    def __init__(self) -> None:
        super().__init__(
            metadata=SkillMetadata(
                id="analysis_skill",
                name="analysis_skill",
                description="Анализ данных и контента",
                capabilities=["data_analysis", "content_analysis"],
                input_schema={"type": "object", "properties": {"source": {"type": "string"}}},
                output_schema={"type": "object", "properties": {"insights": {"type": "array"}}},
            ),
            capabilities=[
                Capability(
                    name="data_analysis",
                    description="Анализ структурированных данных",
                    category="analysis",
                ),
                Capability(
                    name="content_analysis",
                    description="Анализ текстового и медиа контента",
                    category="analysis",
                ),
            ],
        )
