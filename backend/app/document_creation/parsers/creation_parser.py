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

    if status == "incomplete" or missing_information:
        if document_type:
            metadata["document_type"] = document_type
        return None, missing_information, metadata, document_type

    ast_data = data.get("ast")
    if not isinstance(ast_data, dict):
        raise ResponseParseError("Missing ast object in creation response")

    root = _parse_ast_node(ast_data)
    document_ast = build_document_ast(root)
    if document_type:
        metadata["document_type"] = document_type
    return document_ast, missing_information, metadata, document_type


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
