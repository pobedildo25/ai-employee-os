from app.orchestration.models import (
    ExecutionGraph,
    NodeStatus,
    TelegramProgressLine,
    TelegramProgressMessage,
)

_STATUS_ICONS: dict[NodeStatus, tuple[str, str]] = {
    NodeStatus.COMPLETED: ("✅", "выполнено"),
    NodeStatus.RUNNING: ("⏳", "выполняется"),
    NodeStatus.WAITING: ("⌛", "ожидает"),
    NodeStatus.READY: ("⌛", "ожидает"),
    NodeStatus.PAUSED: ("⏸", "приостановлено"),
    NodeStatus.FAILED: ("❌", "ошибка"),
    NodeStatus.CANCELLED: ("🚫", "отменено"),
}


class ProgressTracker:
    """Compute progress from completed graph nodes."""

    def calculate_progress(self, graph: ExecutionGraph) -> float:
        if not graph.nodes:
            return 100.0
        completed = sum(1 for node in graph.nodes.values() if node.status == NodeStatus.COMPLETED)
        return round((completed / len(graph.nodes)) * 100, 1)

    def build_telegram_progress(
        self,
        execution_id: str,
        graph: ExecutionGraph,
        *,
        progress: float | None = None,
    ) -> TelegramProgressMessage:
        percent = int(progress if progress is not None else self.calculate_progress(graph))
        lines: list[TelegramProgressLine] = []

        for node_id in graph.execution_order:
            node = graph.nodes[node_id]
            icon, label = _STATUS_ICONS.get(node.status, ("⌛", "ожидает"))
            title = node.description or node.capability
            lines.append(
                TelegramProgressLine(
                    title=title,
                    status_icon=icon,
                    status_label=label,
                )
            )

        return TelegramProgressMessage(
            execution_id=execution_id,
            progress_percent=percent,
            lines=lines,
        )

    def format_telegram_text(self, message: TelegramProgressMessage) -> str:
        parts = [f"{line.title}\n{line.status_icon} {line.status_label}" for line in message.lines]
        return "\n\n".join(parts)
