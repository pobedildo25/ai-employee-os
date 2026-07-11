from __future__ import annotations

from typing import Any

TELEGRAM_USER_CLIENT_TYPE = "telegram_user"
TELEGRAM_USER_CLIENT_METADATA = {"type": TELEGRAM_USER_CLIENT_TYPE}


def telegram_user_client_metadata(telegram_user_id: int) -> dict[str, Any]:
    return {
        "type": TELEGRAM_USER_CLIENT_TYPE,
        "telegram_user_id": telegram_user_id,
    }


def client_metadata_value(client: Any) -> dict[str, Any]:
    if client is None:
        return {}
    if isinstance(client, dict):
        metadata = client.get("metadata")
        return dict(metadata) if isinstance(metadata, dict) else {}
    metadata = getattr(client, "metadata_", None)
    if metadata is None:
        metadata = getattr(client, "metadata", None)
    return dict(metadata) if isinstance(metadata, dict) else {}


def is_telegram_user_client(client: Any) -> bool:
    return client_metadata_value(client).get("type") == TELEGRAM_USER_CLIENT_TYPE


def is_business_client(client: Any) -> bool:
    return not is_telegram_user_client(client)
