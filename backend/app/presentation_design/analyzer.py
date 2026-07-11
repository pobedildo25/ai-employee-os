from app.presentation_design.layouts import layout_rules
from app.presentation_design.models import PresentationPlan, SlideType


class PresentationAnalyzer:
    """Storytelling / structure checks — no fixed business templates."""

    def analyze(self, plan: PresentationPlan) -> list[str]:
        warnings: list[str] = []
        if not plan.goal.strip():
            warnings.append("Presentation goal is missing")
        if len(plan.slides) < layout_rules.MIN_RECOMMENDED_SLIDES:
            warnings.append("Presentation has too few slides for a clear narrative")
        if len(plan.slides) > layout_rules.MAX_RECOMMENDED_SLIDES:
            warnings.append("Presentation may be too long")

        types = [slide.slide_type for slide in plan.slides]
        if SlideType.CTA not in types and SlideType.OFFER not in types:
            warnings.append("Presentation has no CTA/OFFER slide")

        if not self._has_logical_sequence(types):
            warnings.append("Slide sequence may lack problem→solution progression")

        total_chars = 0
        for slide in plan.slides:
            slide_chars = sum(len(block.text) for block in slide.content_blocks)
            total_chars += slide_chars
            if len(slide.content_blocks) > layout_rules.MAX_BULLETS_PER_SLIDE:
                warnings.append(f"Slide '{slide.title}' has dense content blocks")
            if slide_chars > layout_rules.MAX_CHARS_PER_SLIDE:
                warnings.append(f"Slide '{slide.title}' has high text density")

        if layout_rules.text_density_score(total_chars, len(plan.slides) or 1) > 0.85:
            warnings.append("Overall text density is high")

        return warnings

    @staticmethod
    def _has_logical_sequence(types: list[SlideType]) -> bool:
        if len(types) < 2:
            return True
        if SlideType.PROBLEM in types and SlideType.SOLUTION in types:
            return types.index(SlideType.PROBLEM) < types.index(SlideType.SOLUTION)
        return True
