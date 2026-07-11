from app.presentation_design.models import SlideType

SALES_TEMPLATE: list[SlideType] = [
    SlideType.TITLE,
    SlideType.PROBLEM,
    SlideType.SOLUTION,
    SlideType.FEATURES,
    SlideType.BENEFITS,
    SlideType.CASE_STUDY,
    SlideType.OFFER,
    SlideType.CTA,
]

HINTS = {
    "goal": "Move the audience toward a purchase or commitment",
    "audience": "Buyers and commercial stakeholders",
}
