from app.document_intelligence.ast.models import ASTNode, ASTNodeType
from app.document_intelligence.models import DocumentElement
from app.file_processing.models import ExtractedContent


def parse_xlsx_content(extracted: ExtractedContent) -> tuple[list[DocumentElement], ASTNode]:
    elements: list[DocumentElement] = []
    sections: list[ASTNode] = []
    tables = extracted.tables or []

    for table_index, table in enumerate(tables):
        sheet_name = str(table.get("sheet", f"Sheet {table_index + 1}"))
        rows = table.get("rows", [])
        table_node = ASTNode(
            node_type=ASTNodeType.TABLE,
            content=sheet_name,
            attributes={"sheet": sheet_name, "row_count": len(rows)},
        )
        section = ASTNode(
            node_type=ASTNodeType.SECTION,
            content=sheet_name,
            children=[
                ASTNode(node_type=ASTNodeType.HEADING, content=sheet_name),
                table_node,
            ],
        )
        sections.append(section)
        elements.append(
            DocumentElement(
                element_type="table",
                content=sheet_name,
                metadata={"sheet": sheet_name, "rows": rows},
                position=len(elements),
            )
        )

    root = ASTNode(node_type=ASTNodeType.DOCUMENT, content="XLSX Document", children=sections)
    return elements, root
