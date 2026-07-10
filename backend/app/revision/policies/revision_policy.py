MAX_AUTOMATIC_REVISIONS = 1


def can_auto_revise(revision_count: int, max_revisions: int = MAX_AUTOMATIC_REVISIONS) -> bool:
    return revision_count < max_revisions


def should_wait_for_user(revision_count: int, max_revisions: int = MAX_AUTOMATIC_REVISIONS) -> bool:
    return revision_count >= max_revisions


def next_revision_count(current: int) -> int:
    return max(0, current) + 1
