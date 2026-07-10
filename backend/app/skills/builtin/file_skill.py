from app.skills.base.skill import BaseSkill
from app.skills.models import Capability, SkillMetadata


class FileSkill(BaseSkill):
    """File processing capabilities."""

    def __init__(self) -> None:
        super().__init__(
            metadata=SkillMetadata(
                id="file_skill",
                name="file_skill",
                description="Работа с файлами",
                capabilities=["file_processing", "file_extraction"],
                input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
                output_schema={"type": "object", "properties": {"content": {"type": "string"}}},
            ),
            capabilities=[
                Capability(
                    name="file_processing",
                    description="Обработка загруженных файлов",
                    category="file",
                ),
                Capability(
                    name="file_extraction",
                    description="Извлечение содержимого из файлов",
                    category="file",
                ),
            ],
        )
