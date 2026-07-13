from typing import Any
from uuid import UUID

from app.knowledge.manager import KnowledgeManager
from app.knowledge.migration import KnowledgeMigrationService
from app.skills.base.skill import BaseSkill
from app.skills.models import Capability, SkillMetadata


class KnowledgeMigrationSkill(BaseSkill):
    """Migrates client document archives into Knowledge Base."""

    def __init__(
        self,
        migration_service: KnowledgeMigrationService | None = None,
        manager: KnowledgeManager | None = None,
    ) -> None:
        if migration_service is None:
            from app.knowledge.extractor import KnowledgeExtractor
            from app.llm.gateway import create_llm_gateway

            manager = manager or KnowledgeManager()
            migration_service = KnowledgeMigrationService(
                KnowledgeExtractor(create_llm_gateway()),
                manager,
            )
        self._migration_service = migration_service
        super().__init__(
            metadata=SkillMetadata(
                id="knowledge_migration_skill",
                name="knowledge_migration_skill",
                description="Миграция архива документов клиента в базу знаний",
                capabilities=["knowledge_migration"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "client_id": {"type": "string"},
                        "artifacts": {"type": "array"},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "knowledge_migration_result": {"type": "object"},
                    },
                },
            ),
            capabilities=[
                Capability(
                    name="knowledge_migration",
                    description="Извлечение знаний и стиля из архива документов клиента",
                    category="knowledge",
                ),
            ],
        )

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        client_id_raw = payload.get("client_id")
        artifacts = payload.get("artifacts")
        if client_id_raw is None or not isinstance(artifacts, list):
            return {
                "status": "failed",
                "skill": self.name(),
                "message": "client_id and artifacts are required",
                "payload_keys": list(payload.keys()),
            }

        context = dict(payload.get("context") or {})
        if payload.get("confirm_persist") or payload.get("confirm_knowledge"):
            context["confirm_persist"] = True

        result = await self._migration_service.migrate(
            client_id=UUID(str(client_id_raw)),
            artifacts=artifacts,
            context=context,
            file_bytes_by_artifact=payload.get("file_bytes_by_artifact") or {},
            persist=bool(payload.get("persist", False)),
            trace_id=str(payload.get("trace_id") or "-"),
        )

        if any("telegram transport client" in warning.lower() for warning in result.warnings):
            return {
                "status": "skipped",
                "skill": self.name(),
                "message": result.warnings[0],
                "knowledge_migration_result": None,
            }

        return {
            "status": "completed",
            "skill": self.name(),
            "knowledge_migration_result": result.model_dump(mode="json"),
            "memory_candidates": result.memory_candidates,
        }
