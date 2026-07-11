from app.presentation_design.models import SlideType

PITCH_TEMPLATE: list[SlideType] = [
    SlideType.TITLE,
    SlideType.PROBLEM,
    SlideType.SOLUTION,
    SlideType.FEATURES,
    SlideType.DATA,
    SlideType.TEAM,
    SlideType.OFFER,
    SlideType.CTA,
]

HINTS = {
    "goal": "Pitch an idea or venture with clear ask",
    "audience": "Investors or partners",
}
