from app.document_intelligence.ast.models import ASTNode, ASTNodeType
from app.document_intelligence.models import DocumentElement
from app.file_processing.models import ExtractedContent


def parse_pdf_content(extracted: ExtractedContent) -> tuple[list[DocumentElement], ASTNode]:
    elements: list[DocumentElement] = []
    sections: list[ASTNode] = []
    pages = (extracted.structure or {}).get("pages", [])
    text = extracted.text or ""

    if pages:
        page_texts = text.split("\n\n") if text else []
        for index, page_info in enumerate(pages):
            page_text = page_texts[index] if index < len(page_texts) else ""
            section = ASTNode(
                node_type=ASTNodeType.SECTION,
                content=f"Page {page_info.get('index', index + 1)}",
                attributes={"page_index": page_info.get("index", index + 1)},
            )
            if page_text.strip():
                paragraph = ASTNode(node_type=ASTNodeType.PARAGRAPH, content=page_text.strip())
                section.children.append(paragraph)
                elements.append(
                    DocumentElement(
                        element_type="paragraph",
                        content=page_text.strip(),
                        metadata={"page": page_info.get("index", index + 1)},
                        position=len(elements),
                    )
                )
            sections.append(section)
    elif text.strip():
        paragraph = ASTNode(node_type=ASTNodeType.PARAGRAPH, content=text.strip())
        sections.append(ASTNode(node_type=ASTNodeType.SECTION, content="Content", children=[paragraph]))
        elements.append(
            DocumentElement(
                element_type="paragraph",
                content=text.strip(),
                metadata={"page": 1},
                position=0,
            )
        )

    root = ASTNode(node_type=ASTNodeType.DOCUMENT, content="PDF Document", children=sections)
    return elements, root
