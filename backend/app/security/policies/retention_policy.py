from app.security.models import AuditEvent


class AuditRetentionPolicy:
    def __init__(self, max_events: int = 1000) -> None:
        if max_events < 1:
            raise ValueError("max_events must be >= 1")
        self.max_events = max_events

    def should_evict(self, count: int) -> bool:
        return count > self.max_events

    def overflow(self, count: int) -> int:
        return max(0, count - self.max_events)
