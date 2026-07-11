from app.presentation_design.models import SlideType

MARKETING_TEMPLATE: list[SlideType] = [
    SlideType.TITLE,
    SlideType.PROBLEM,
    SlideType.SOLUTION,
    SlideType.PROCESS,
    SlideType.DATA,
    SlideType.TIMELINE,
    SlideType.CTA,
]

HINTS = {
    "goal": "Communicate strategy, channels, and expected outcomes",
    "audience": "Marketing and growth stakeholders",
}
