from app.skills.base.skill import BaseSkill
from app.skills.models import Capability, SkillMetadata


class DocumentSkill(BaseSkill):
    """Document-related capabilities: read, modify, create."""

    def __init__(self) -> None:
        super().__init__(
            metadata=SkillMetadata(
                id="document_skill",
                name="document_skill",
                description="Работа с документами",
                capabilities=[
                    "document_generation",
                    "document_modification",
                ],
                input_schema={"type": "object", "properties": {"content": {"type": "string"}}},
                output_schema={"type": "object", "properties": {"result": {"type": "string"}}},
            ),
            capabilities=[
                Capability(
                    name="document_generation",
                    description="Создание документов",
                    category="document",
                ),
                Capability(
                    name="document_modification",
                    description="Изменение существующих документов",
                    category="document",
                ),
            ],
        )
