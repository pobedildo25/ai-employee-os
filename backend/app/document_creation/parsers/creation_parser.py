import json
from typing import Any

from app.agents.parsers.response_parser import ResponseParseError, extract_json_content
from app.document_intelligence.ast.builder import build_document_ast
from app.document_intelligence.ast.models import ASTNode, ASTNodeType, DocumentAST


def parse_creation_response(raw: str) -> tuple[DocumentAST | None, list[str], dict[str, Any], str | None]:
    content = extract_json_content(raw)
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ResponseParseError(f"Invalid JSON: {exc}") from exc

    missing_information = list(data.get("missing_information") or [])
    metadata = dict(data.get("metadata") or {})
    document_type = data.get("document_type")
    status = data.get("status", "ready")
    if document_type:
        metadata["document_type"] = document_type

    ast_data = data.get("ast")

    # Draft-first: if the model produced a structure, always use it — even when it
    # also listed missing_information. Unknown facts become non-blocking assumptions
    # (rendered as placeholders), never a silent failure. Only treat the document as
    # incomplete when there is genuinely no structure to render.
    if isinstance(ast_data, dict):
        root = _parse_ast_node(ast_data)
        document_ast = build_document_ast(root)
        if missing_information:
            metadata["assumptions"] = missing_information
        return document_ast, [], metadata, document_type

    # No structure produced. If the model did not explicitly signal incompleteness,
    # a missing ast is a malformed response.
    if status != "incomplete" and not missing_information:
        raise ResponseParseError("Missing ast object in creation response")

    return None, missing_information, metadata, document_type


def _parse_ast_node(data: dict[str, Any]) -> ASTNode:
    node_type_raw = data.get("node_type")
    try:
        node_type = ASTNodeType(str(node_type_raw))
    except ValueError as exc:
        raise ResponseParseError(f"Unsupported AST node type: {node_type_raw}") from exc

    children = [_parse_ast_node(child) for child in data.get("children") or [] if isinstance(child, dict)]
    return ASTNode(
        node_type=node_type,
        content=data.get("content"),
        attributes=dict(data.get("attributes") or {}),
        children=children,
    )
