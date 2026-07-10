from app.document_intelligence.ast.models import ASTNode, ASTNodeType
from app.document_intelligence.models import DocumentElement
from app.file_processing.models import ExtractedContent


def parse_pptx_content(extracted: ExtractedContent) -> tuple[list[DocumentElement], ASTNode]:
    elements: list[DocumentElement] = []
    slides = (extracted.structure or {}).get("slides", [])
    sections: list[ASTNode] = []

    for slide in slides:
        slide_index = slide.get("index", len(sections) + 1)
        slide_text = str(slide.get("text", "")).strip()
        heading = ASTNode(
            node_type=ASTNodeType.HEADING,
            content=f"Slide {slide_index}",
            attributes={"slide_index": slide_index},
        )
        section = ASTNode(
            node_type=ASTNodeType.SECTION,
            content=f"Slide {slide_index}",
            children=[heading],
        )
        if slide_text:
            paragraph = ASTNode(node_type=ASTNodeType.PARAGRAPH, content=slide_text)
            section.children.append(paragraph)
            elements.append(
                DocumentElement(
                    element_type="paragraph",
                    content=slide_text,
                    metadata={"slide_index": slide_index},
                    position=len(elements),
                )
            )
        sections.append(section)

    root = ASTNode(node_type=ASTNodeType.DOCUMENT, content="PPTX Document", children=sections)
    return elements, root
