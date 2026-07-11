from uuid import UUID

from app.memory.models import MemoryItem, MemoryType
from app.strategy.models import StrategyResult


def prepare_strategy_memory_items(
    result: StrategyResult,
    *,
    client_id: UUID | str | None = None,
    project_id: UUID | str | None = None,
    session_id: str | None = None,
) -> list[MemoryItem]:
    if result.metadata.get("status") not in {"ready", "incomplete"} and not result.insights:
        return []

    items: list[MemoryItem] = [
        MemoryItem(
            type=MemoryType.DECISION,
            content=(
                f"Strategy prepared: {result.strategy_type.value} — "
                f"{(result.summary or 'no summary')[:180]}"
            ),
            metadata={
                "kind": "strategy_analysis",
                "strategy_type": result.strategy_type.value,
                "insight_count": len(result.insights),
                "recommendation_count": len(result.recommendations),
            },
            importance=0.6,
            source="strategy",
            client_id=UUID(str(client_id)) if client_id else None,
            project_id=UUID(str(project_id)) if project_id else None,
            session_id=session_id,
        )
    ]
    for insight in result.insights[:3]:
        items.append(
            MemoryItem(
                type=MemoryType.FACT,
                content=f"{insight.title}: {insight.description}",
                metadata={
                    "kind": "strategy_insight",
                    "category": insight.category,
                    "confidence": insight.confidence,
                },
                importance=min(0.85, max(0.4, insight.confidence)),
                source="strategy",
                client_id=UUID(str(client_id)) if client_id else None,
                project_id=UUID(str(project_id)) if project_id else None,
                session_id=session_id,
            )
        )
    return items
