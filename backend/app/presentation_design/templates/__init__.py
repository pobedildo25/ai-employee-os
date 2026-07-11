from app.presentation_design.models import PresentationType, SlideType
from app.presentation_design.templates import business, marketing, pitch, sales

TEMPLATE_HINTS: dict[PresentationType, dict] = {
    PresentationType.BUSINESS: {
        "slide_types": [item.value for item in business.BUSINESS_TEMPLATE],
        "hints": business.HINTS,
    },
    PresentationType.SALES: {
        "slide_types": [item.value for item in sales.SALES_TEMPLATE],
        "hints": sales.HINTS,
    },
    PresentationType.MARKETING: {
        "slide_types": [item.value for item in marketing.MARKETING_TEMPLATE],
        "hints": marketing.HINTS,
    },
    PresentationType.PITCH: {
        "slide_types": [item.value for item in pitch.PITCH_TEMPLATE],
        "hints": pitch.HINTS,
    },
}


def select_template_hint(presentation_type: PresentationType | str | None) -> dict:
    if presentation_type is None:
        return TEMPLATE_HINTS[PresentationType.BUSINESS]
    if isinstance(presentation_type, str):
        try:
            presentation_type = PresentationType(presentation_type.lower())
        except ValueError:
            return TEMPLATE_HINTS[PresentationType.BUSINESS]
    return TEMPLATE_HINTS.get(presentation_type, TEMPLATE_HINTS[PresentationType.BUSINESS])


def all_slide_types() -> list[str]:
    return [item.value for item in SlideType]
