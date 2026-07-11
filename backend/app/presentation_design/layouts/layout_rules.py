"""Soft layout heuristics for presentations — not business templates."""

MAX_RECOMMENDED_SLIDES = 16
MIN_RECOMMENDED_SLIDES = 3
MAX_BULLETS_PER_SLIDE = 6
MAX_CHARS_PER_BLOCK = 280
MAX_CHARS_PER_SLIDE = 900


def text_density_score(total_chars: int, slide_count: int) -> float:
    if slide_count <= 0:
        return 1.0
    avg = total_chars / slide_count
    return min(1.0, avg / MAX_CHARS_PER_SLIDE)
