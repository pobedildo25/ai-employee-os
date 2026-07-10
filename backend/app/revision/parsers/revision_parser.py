import json
from typing import Any

from app.agents.parsers.response_parser import ResponseParseError, extract_json_content
from app.document_intelligence.ast.builder import build_document_ast
from app.document_intelligence.ast.models import ASTNode, ASTNodeType, DocumentAST


def parse_revision_response(raw: str) -> tuple[DocumentAST | None, list[str], str, bool, bool]:
    content = extract_json_content(raw)
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ResponseParseError(f"Invalid JSON: {exc}") from exc

    status = str(data.get("status", "ready")).lower()
    summary = str(data.get("summary", ""))
    changes = [str(item) for item in data.get("changes_applied") or []]
    update_ast = bool(data.get("update_ast", True))
    needs_render = bool(data.get("needs_render", True))

    if status == "failed":
        return None, changes, summary or "Revision failed", False, False

    ast_data = data.get("ast")
    if not update_ast or not isinstance(ast_data, dict):
        return None, changes, summary, update_ast, needs_render

    root = _parse_ast_node(ast_data)
    return build_document_ast(root), changes, summary, update_ast, needs_render


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
