from app.document_intelligence.ast.models import ASTNode, ASTNodeType
from app.document_intelligence.models import DocumentElement
from app.file_processing.models import ExtractedContent


def parse_docx_content(extracted: ExtractedContent) -> tuple[list[DocumentElement], ASTNode]:
    elements: list[DocumentElement] = []
    paragraphs = (extracted.structure or {}).get("paragraphs", [])
    if not paragraphs and extracted.text:
        paragraphs = [line for line in extracted.text.splitlines() if line.strip()]

    section = ASTNode(node_type=ASTNodeType.SECTION, content="Body")
    for index, paragraph_text in enumerate(paragraphs):
        text = str(paragraph_text).strip()
        if not text:
            continue
        section.children.append(ASTNode(node_type=ASTNodeType.PARAGRAPH, content=text))
        elements.append(
            DocumentElement(
                element_type="paragraph",
                content=text,
                metadata={"paragraph_index": index + 1},
                position=len(elements),
            )
        )

    root = ASTNode(node_type=ASTNodeType.DOCUMENT, content="DOCX Document", children=[section])
    return elements, root
