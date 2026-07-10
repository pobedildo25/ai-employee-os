from typing import Any
from uuid import UUID

from app.brand_style.models import BrandProfile


def build_brand_profile(
    *,
    raw_style: dict[str, Any],
    client_id: UUID | None,
    name: str,
    source_artifact_id: UUID | None = None,
) -> BrandProfile:
    typography = _build_typography(raw_style)
    colors = _build_colors(raw_style)
    layout_rules = _build_layout_rules(raw_style)
    document_rules = _build_document_rules(raw_style)
    visual_elements = _build_visual_elements(raw_style)

    source_artifacts = [source_artifact_id] if source_artifact_id is not None else []

    return BrandProfile(
        client_id=client_id,
        name=name,
        typography=typography,
        colors=colors,
        layout_rules=layout_rules,
        document_rules=document_rules,
        visual_elements=visual_elements,
        metadata={
            "source_format": raw_style.get("format"),
            "extraction_version": "1.0",
        },
        source_artifacts=source_artifacts,
    )


def _build_typography(raw_style: dict[str, Any]) -> dict[str, Any]:
    fonts = raw_style.get("fonts") or []
    font_sizes = raw_style.get("font_sizes") or []
    heading_styles = raw_style.get("heading_styles") or []

    typography: dict[str, Any] = {
        "fonts": fonts,
        "font_sizes": font_sizes,
    }
    if fonts:
        typography["body_font"] = fonts[0]
    if len(fonts) > 1:
        typography["heading_font"] = fonts[1]
    elif fonts:
        typography["heading_font"] = fonts[0]
    if heading_styles:
        typography["heading_styles"] = heading_styles
    return typography


def _build_colors(raw_style: dict[str, Any]) -> dict[str, Any]:
    colors: dict[str, Any] = {}
    text_colors = raw_style.get("text_colors") or []
    theme_colors = raw_style.get("theme_colors") or {}

    if text_colors:
        colors["primary"] = text_colors[0]
        if len(text_colors) > 1:
            colors["secondary"] = text_colors[1]
    if theme_colors:
        colors["theme"] = theme_colors
        if "accent1" in theme_colors and "primary" not in colors:
            colors["primary"] = theme_colors["accent1"]
    return colors


def _build_layout_rules(raw_style: dict[str, Any]) -> dict[str, Any]:
    layout: dict[str, Any] = {"header": "top"}

    page_margins = raw_style.get("page_margins")
    if page_margins:
        layout["page_margins"] = page_margins

    slide_width = raw_style.get("slide_width")
    slide_height = raw_style.get("slide_height")
    if slide_width is not None and slide_height is not None:
        layout["slide_dimensions"] = {"width": slide_width, "height": slide_height}

    page_sizes = raw_style.get("page_sizes")
    if page_sizes:
        layout["page_sizes"] = page_sizes

    element_positions = raw_style.get("element_positions")
    if element_positions:
        layout["element_positions_sample"] = element_positions[:5]

    if raw_style.get("format") == "pptx":
        layout["footer"] = False
    else:
        layout["footer"] = True

    return layout


def _build_document_rules(raw_style: dict[str, Any]) -> dict[str, Any]:
    rules: dict[str, Any] = {
        "format": raw_style.get("format"),
    }
    if raw_style.get("table_count") is not None:
        rules["uses_tables"] = raw_style["table_count"] > 0
    if raw_style.get("slide_count") is not None:
        rules["slide_count"] = raw_style["slide_count"]
    if raw_style.get("page_count") is not None:
        rules["page_count"] = raw_style["page_count"]
    if raw_style.get("paragraph_count") is not None:
        rules["paragraph_count"] = raw_style["paragraph_count"]
    return rules


def _build_visual_elements(raw_style: dict[str, Any]) -> dict[str, Any]:
    elements: dict[str, Any] = {}
    if raw_style.get("image_count") is not None:
        elements["image_count"] = raw_style["image_count"]
    if raw_style.get("table_count") is not None:
        elements["table_count"] = raw_style["table_count"]
    if raw_style.get("slide_backgrounds"):
        elements["slide_backgrounds"] = raw_style["slide_backgrounds"]
    if raw_style.get("block_structure"):
        elements["block_structure"] = raw_style["block_structure"]
    return elements
