"""Thin re-exports — copy helpers live in app.conversation.messages."""

from app.conversation.messages import (
    INCOMPLETE_COMPLETION_MESSAGE,
    INCOMPLETE_REASON,
    extract_failure_reason,
    format_approval_message,
    format_completion_message,
    format_delivery_caption,
    format_delivery_summary,
    format_error_message,
    format_progress_header,
    format_progress as format_telegram_progress,
    format_revision_prompt,
    format_runtime_error_message,
    has_real_result_message,
)
from app.conversation.messages import _plural_files

__all__ = [
    "INCOMPLETE_COMPLETION_MESSAGE",
    "INCOMPLETE_REASON",
    "_plural_files",
    "extract_failure_reason",
    "format_approval_message",
    "format_completion_message",
    "format_delivery_caption",
    "format_delivery_summary",
    "format_error_message",
    "format_progress_header",
    "format_revision_prompt",
    "format_runtime_error_message",
    "format_telegram_progress",
    "has_real_result_message",
]
