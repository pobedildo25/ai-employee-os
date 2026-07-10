import logging

from qdrant_client import QdrantClient

from app.core.config import Settings

logger = logging.getLogger(__name__)

_client: QdrantClient | None = None


def get_qdrant_client(settings: Settings) -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
        )
    return _client


def check_qdrant(settings: Settings) -> tuple[bool, str]:
    try:
        client = get_qdrant_client(settings)
        client.get_collections()
        return True, "ok"
    except Exception as exc:
        logger.warning("Qdrant health check failed: %s", exc)
        return False, str(exc)


def close_qdrant() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
