from app.presentation_design.models import PresentationType, SlideType

# Soft hints for the planner — LLM may rearrange.
BUSINESS_TEMPLATE: list[SlideType] = [
    SlideType.TITLE,
    SlideType.PROBLEM,
    SlideType.SOLUTION,
    SlideType.PROCESS,
    SlideType.BENEFITS,
    SlideType.CTA,
]

HINTS = {
    "goal": "Clarify business objective and recommended next step",
    "audience": "Decision makers and stakeholders",
}
