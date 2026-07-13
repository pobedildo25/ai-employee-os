"""Redis-backed LangGraph checkpointer (no langgraph-checkpoint-redis dependency)."""

from __future__ import annotations

import pickle
import random
from collections.abc import AsyncIterator, Iterator, Sequence
from typing import Any

import redis
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    get_checkpoint_id,
    get_checkpoint_metadata,
)

from app.agent_runtime.exceptions import CheckpointError

_KEY_PREFIX = "langgraph:ckpt:"


class RedisCheckpointSaver(BaseCheckpointSaver):
    """Persist LangGraph interrupt checkpoints in Redis under ``langgraph:ckpt:{thread_id}:...``.

    Mirrors ``MemorySaver`` semantics using plain Redis keys + pickle (no RediSearch /
    ``langgraph.checkpoint.redis`` package).
    """

    def __init__(
        self,
        client: redis.Redis,
        *,
        ttl_seconds: int = 604800,
        key_prefix: str = _KEY_PREFIX,
    ) -> None:
        super().__init__()
        self._client = client
        self._ttl = max(1, int(ttl_seconds))
        self._prefix = key_prefix
        try:
            self._client.ping()
        except Exception as exc:
            raise CheckpointError(f"Redis checkpointer unavailable: {exc}") from exc

    def _cp_key(self, thread_id: str, checkpoint_ns: str, checkpoint_id: str) -> str:
        return f"{self._prefix}{thread_id}:{checkpoint_ns}:cp:{checkpoint_id}"

    def _index_key(self, thread_id: str, checkpoint_ns: str) -> str:
        return f"{self._prefix}{thread_id}:{checkpoint_ns}:index"

    def _blob_key(self, thread_id: str, checkpoint_ns: str, channel: str, version: Any) -> str:
        return f"{self._prefix}{thread_id}:{checkpoint_ns}:blob:{channel}:{version}"

    def _writes_key(self, thread_id: str, checkpoint_ns: str, checkpoint_id: str) -> str:
        return f"{self._prefix}{thread_id}:{checkpoint_ns}:writes:{checkpoint_id}"

    def _thread_keys_pattern(self, thread_id: str) -> str:
        return f"{self._prefix}{thread_id}:*"

    def _setex(self, key: str, value: bytes) -> None:
        self._client.set(key, value, ex=self._ttl)

    def _dumps(self, obj: Any) -> bytes:
        return pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)

    def _loads(self, raw: bytes) -> Any:
        return pickle.loads(raw)

    def _load_blobs(
        self,
        thread_id: str,
        checkpoint_ns: str,
        versions: ChannelVersions,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for channel, ver in versions.items():
            raw = self._client.get(self._blob_key(thread_id, checkpoint_ns, channel, ver))
            if raw is None:
                continue
            typed = self._loads(raw)
            if typed[0] == "empty":
                continue
            result[channel] = self.serde.loads_typed(typed)
        return result

    def _load_writes(
        self,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
    ) -> list[tuple[str, str, Any]]:
        raw = self._client.get(self._writes_key(thread_id, checkpoint_ns, checkpoint_id))
        if raw is None:
            return []
        writes: dict[tuple[str, int], tuple[str, str, tuple[str, bytes], str]] = self._loads(raw)
        return [(tid, ch, self.serde.loads_typed(blob)) for tid, ch, blob, _ in writes.values()]

    def _checkpoint_tuple(
        self,
        *,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
        packed: tuple[tuple[str, bytes], tuple[str, bytes], str | None],
        config: RunnableConfig | None = None,
    ) -> CheckpointTuple:
        checkpoint_typed, metadata_typed, parent_checkpoint_id = packed
        checkpoint_: Checkpoint = self.serde.loads_typed(checkpoint_typed)
        return CheckpointTuple(
            config=config
            or {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": checkpoint_id,
                }
            },
            checkpoint={
                **checkpoint_,
                "channel_values": self._load_blobs(
                    thread_id, checkpoint_ns, checkpoint_["channel_versions"]
                ),
            },
            metadata=self.serde.loads_typed(metadata_typed),
            pending_writes=self._load_writes(thread_id, checkpoint_ns, checkpoint_id),
            parent_config=(
                {
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": parent_checkpoint_id,
                    }
                }
                if parent_checkpoint_id
                else None
            ),
        )

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        try:
            thread_id: str = config["configurable"]["thread_id"]
            checkpoint_ns: str = config["configurable"].get("checkpoint_ns", "")
            if checkpoint_id := get_checkpoint_id(config):
                raw = self._client.get(self._cp_key(thread_id, checkpoint_ns, checkpoint_id))
                if raw is None:
                    return None
                return self._checkpoint_tuple(
                    thread_id=thread_id,
                    checkpoint_ns=checkpoint_ns,
                    checkpoint_id=checkpoint_id,
                    packed=self._loads(raw),
                    config=config,
                )

            members = self._client.smembers(self._index_key(thread_id, checkpoint_ns))
            if not members:
                return None
            ids = [m.decode() if isinstance(m, bytes) else str(m) for m in members]
            checkpoint_id = max(ids)
            raw = self._client.get(self._cp_key(thread_id, checkpoint_ns, checkpoint_id))
            if raw is None:
                return None
            return self._checkpoint_tuple(
                thread_id=thread_id,
                checkpoint_ns=checkpoint_ns,
                checkpoint_id=checkpoint_id,
                packed=self._loads(raw),
            )
        except CheckpointError:
            raise
        except Exception as exc:
            raise CheckpointError(f"Failed to load LangGraph checkpoint: {exc}") from exc

    def list(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        try:
            if config is None:
                return iter(())
            thread_id: str = config["configurable"]["thread_id"]
            checkpoint_ns: str = config["configurable"].get("checkpoint_ns", "")
            config_checkpoint_id = get_checkpoint_id(config)
            members = self._client.smembers(self._index_key(thread_id, checkpoint_ns))
            ids = sorted(
                (m.decode() if isinstance(m, bytes) else str(m) for m in members),
                reverse=True,
            )
            remaining = limit
            for checkpoint_id in ids:
                if config_checkpoint_id and checkpoint_id != config_checkpoint_id:
                    continue
                if (
                    before
                    and (before_checkpoint_id := get_checkpoint_id(before))
                    and checkpoint_id >= before_checkpoint_id
                ):
                    continue
                raw = self._client.get(self._cp_key(thread_id, checkpoint_ns, checkpoint_id))
                if raw is None:
                    continue
                packed = self._loads(raw)
                metadata = self.serde.loads_typed(packed[1])
                if filter and not all(
                    query_value == metadata.get(query_key)
                    for query_key, query_value in filter.items()
                ):
                    continue
                if remaining is not None:
                    if remaining <= 0:
                        break
                    remaining -= 1
                yield self._checkpoint_tuple(
                    thread_id=thread_id,
                    checkpoint_ns=checkpoint_ns,
                    checkpoint_id=checkpoint_id,
                    packed=packed,
                )
        except CheckpointError:
            raise
        except Exception as exc:
            raise CheckpointError(f"Failed to list LangGraph checkpoints: {exc}") from exc

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        try:
            c = checkpoint.copy()
            thread_id = config["configurable"]["thread_id"]
            checkpoint_ns = config["configurable"]["checkpoint_ns"]
            values: dict[str, Any] = c.pop("channel_values")  # type: ignore[misc]
            for k, v in new_versions.items():
                typed = self.serde.dumps_typed(values[k]) if k in values else ("empty", b"")
                self._setex(self._blob_key(thread_id, checkpoint_ns, k, v), self._dumps(typed))
            packed = (
                self.serde.dumps_typed(c),
                self.serde.dumps_typed(get_checkpoint_metadata(config, metadata)),
                config["configurable"].get("checkpoint_id"),
            )
            checkpoint_id = checkpoint["id"]
            self._setex(self._cp_key(thread_id, checkpoint_ns, checkpoint_id), self._dumps(packed))
            index_key = self._index_key(thread_id, checkpoint_ns)
            self._client.sadd(index_key, checkpoint_id)
            self._client.expire(index_key, self._ttl)
            return {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": checkpoint_id,
                }
            }
        except CheckpointError:
            raise
        except Exception as exc:
            raise CheckpointError(f"Failed to save LangGraph checkpoint: {exc}") from exc

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        try:
            thread_id = config["configurable"]["thread_id"]
            checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
            checkpoint_id = config["configurable"]["checkpoint_id"]
            key = self._writes_key(thread_id, checkpoint_ns, checkpoint_id)
            raw = self._client.get(key)
            stored: dict[tuple[str, int], tuple[str, str, tuple[str, bytes], str]] = (
                self._loads(raw) if raw is not None else {}
            )
            for idx, (channel, value) in enumerate(writes):
                inner_key = (task_id, WRITES_IDX_MAP.get(channel, idx))
                if inner_key[1] >= 0 and inner_key in stored:
                    continue
                stored[inner_key] = (
                    task_id,
                    channel,
                    self.serde.dumps_typed(value),
                    task_path,
                )
            self._setex(key, self._dumps(stored))
        except CheckpointError:
            raise
        except Exception as exc:
            raise CheckpointError(f"Failed to save LangGraph writes: {exc}") from exc

    def delete_thread(self, thread_id: str) -> None:
        try:
            keys = list(self._client.scan_iter(match=self._thread_keys_pattern(thread_id), count=200))
            if keys:
                self._client.delete(*keys)
        except Exception as exc:
            raise CheckpointError(f"Failed to delete LangGraph thread: {exc}") from exc

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        return self.get_tuple(config)

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        for item in self.list(config, filter=filter, before=before, limit=limit):
            yield item

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        return self.put(config, checkpoint, metadata, new_versions)

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        self.put_writes(config, writes, task_id, task_path)

    async def adelete_thread(self, thread_id: str) -> None:
        self.delete_thread(thread_id)

    def get_next_version(self, current: str | None, channel: None) -> str:
        if current is None:
            current_v = 0
        elif isinstance(current, int):
            current_v = current
        else:
            current_v = int(current.split(".")[0])
        next_v = current_v + 1
        next_h = random.random()
        return f"{next_v:032}.{next_h:016}"
