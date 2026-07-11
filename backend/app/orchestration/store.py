from functools import lru_cache
from threading import Lock

from app.orchestration.models import ExecutionRecord, ExecutionState


class ExecutionStore:
    """Process-local store for orchestration lifecycle and API lookups."""

    def __init__(self) -> None:
        self._records: dict[str, ExecutionRecord] = {}
        self._lock = Lock()

    def save(self, record: ExecutionRecord) -> None:
        with self._lock:
            self._records[record.execution_id] = record

    def get(self, execution_id: str) -> ExecutionRecord | None:
        with self._lock:
            return self._records.get(execution_id)

    def update_state(self, execution_id: str, state: ExecutionState) -> ExecutionRecord | None:
        with self._lock:
            record = self._records.get(execution_id)
            if record is None:
                return None
            record.state = state
            self._records[execution_id] = record
            return record

    def list_ids(self) -> list[str]:
        with self._lock:
            return list(self._records.keys())


@lru_cache
def get_execution_store_singleton() -> ExecutionStore:
    return ExecutionStore()
