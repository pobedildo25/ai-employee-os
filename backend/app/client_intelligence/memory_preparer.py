from uuid import UUID

from app.client_intelligence.models import ClientProfile
from app.memory.models import MemoryItem, MemoryType


def prepare_client_intelligence_memory_items(
    profile: ClientProfile,
    *,
    session_id: str | None = None,
) -> list[MemoryItem]:
    """Prepare memory candidates — never auto-remembers."""
    client_uuid = None
    try:
        client_uuid = UUID(str(profile.client_id))
    except ValueError:
        client_uuid = None

    items: list[MemoryItem] = []
    if profile.summary:
        items.append(
            MemoryItem(
                type=MemoryType.FACT,
                content=profile.summary,
                metadata={"kind": "client_intelligence", "field": "summary"},
                importance=0.55,
                source="client_intelligence",
                client_id=client_uuid,
                session_id=session_id,
            )
        )

    for key, value in profile.preferences.items():
        items.append(
            MemoryItem(
                type=MemoryType.PREFERENCE,
                content=f"Client prefers {key}={value}",
                metadata={"kind": "client_intelligence", "preference_key": key},
                importance=0.7,
                source="client_intelligence",
                client_id=client_uuid,
                session_id=session_id,
            )
        )

    tone = profile.communication_style.get("tone")
    verbosity = profile.communication_style.get("verbosity")
    if tone or verbosity:
        items.append(
            MemoryItem(
                type=MemoryType.PREFERENCE,
                content=(
                    "Client communication: "
                    + ", ".join(
                        part
                        for part in (
                            f"tone={tone}" if tone else "",
                            f"verbosity={verbosity}" if verbosity else "",
                        )
                        if part
                    )
                ),
                metadata={"kind": "client_intelligence", "field": "communication_style"},
                importance=0.7,
                source="client_intelligence",
                client_id=client_uuid,
                session_id=session_id,
            )
        )

    for risk in profile.risks[:5]:
        items.append(
            MemoryItem(
                type=MemoryType.FACT,
                content=f"Client risk: {risk}",
                metadata={"kind": "client_intelligence", "field": "risk"},
                importance=0.75,
                source="client_intelligence",
                client_id=client_uuid,
                session_id=session_id,
            )
        )
    return items
