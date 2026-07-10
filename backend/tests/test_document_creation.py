from uuid import uuid4

import pytest

from app.brand_style.models import BrandProfile
from app.core.config import Settings
from app.document_creation.creator import DocumentCreator
from app.document_creation.generators.ast_generator import DocumentASTGenerator
from app.document_creation.models import DocumentCreationRequest
from app.document_creation.parsers.creation_parser import parse_creation_response
from app.document_creation.validators.ast_validator import ASTValidationError, ASTValidator
from app.document_intelligence.ast.models import ASTNodeType
from app.document_renderer.models import OutputFormat, RenderRequest
from app.document_renderer.renderer import DocumentRendererService
from app.memory.models import MemoryType
from app.skills.builtin.document_creation_skill import DocumentCreationSkill
from app.skills.registry import create_capability_registry
from tests.llm_fixtures import creation_ast_json, mock_gateway


@pytest.fixture
def settings() -> Settings:
    return Settings(skills_enabled=True)


def test_parse_creation_ast_response() -> None:
    document_ast, missing, metadata, document_type = parse_creation_response(creation_ast_json())
    assert document_ast is not None
    assert missing == []
    assert document_type == "docx"
    assert document_ast.root.node_type == ASTNodeType.DOCUMENT
    assert len(document_ast.root.children) == 2


def test_parse_missing_information_response() -> None:
    document_ast, missing, metadata, _document_type = parse_creation_response(
        creation_ast_json(status="incomplete", missing_information=["нет данных клиента", "нет стоимости"])
    )
    assert document_ast is None
    assert "нет данных клиента" in missing
    assert "нет стоимости" in missing


def test_ast_validator(settings: Settings) -> None:
    document_ast, _, _, _ = parse_creation_response(creation_ast_json())
    assert document_ast is not None
    ASTValidator().validate(document_ast)


def test_ast_validator_rejects_invalid_root() -> None:
    from app.document_intelligence.ast.models import ASTNode, DocumentAST

    invalid_ast = DocumentAST(
        root=ASTNode(node_type=ASTNodeType.PARAGRAPH, content="invalid"),
        node_count=1,
    )
    with pytest.raises(ASTValidationError):
        ASTValidator().validate(invalid_ast)


@pytest.mark.asyncio
async def test_document_ast_generation(settings: Settings) -> None:
    gateway, _ = mock_gateway(settings, creation_ast_json(title="Client Document"))
    creator = DocumentCreator(DocumentASTGenerator(gateway))
    result = await creator.create(
        DocumentCreationRequest(
            user_goal="Подготовь документ для клиента",
            context={"user_input": "Подготовь документ для клиента"},
            document_type="docx",
        ),
        trace_id="trace-create",
    )

    assert result.document_ast is not None
    assert result.missing_information == []
    assert result.metadata["title"] == "Client Document"
    assert result.document_ast.root.children[0].children[0].content == "Overview"


@pytest.mark.asyncio
async def test_missing_information_detection(settings: Settings) -> None:
    gateway, _ = mock_gateway(
        settings,
        creation_ast_json(
            status="incomplete",
            missing_information=["нет данных клиента", "нет описания услуг"],
        ),
    )
    creator = DocumentCreator(DocumentASTGenerator(gateway))
    result = await creator.create(
        DocumentCreationRequest(user_goal="Подготовь документ для клиента"),
    )

    assert result.document_ast is None
    assert "нет данных клиента" in result.missing_information


@pytest.mark.asyncio
async def test_document_creation_skill(settings: Settings) -> None:
    gateway, _ = mock_gateway(settings, creation_ast_json())
    skill = DocumentCreationSkill(creator=DocumentCreator(DocumentASTGenerator(gateway)))
    result = await skill.execute(
        {
            "goal": "Подготовь документ для клиента",
            "context": {"user_input": "Подготовь документ для клиента"},
            "document_type": "docx",
        }
    )

    assert result["status"] == "completed"
    assert result["document_ast"] is not None
    assert result["memory_candidates"]
    assert result["memory_candidates"][0]["type"] == MemoryType.FACT.value


def test_creation_to_renderer_preparation(settings: Settings) -> None:
    document_ast, _, metadata, document_type = parse_creation_response(creation_ast_json(document_type="docx"))
    assert document_ast is not None

    brand_profile = BrandProfile(
        typography={"body_font": "Calibri", "heading_font": "Arial"},
        colors={"primary": "#123456"},
        layout_rules={"header": "top", "footer": True},
    )

    request = RenderRequest(
        document_structure=document_ast,
        brand_profile=brand_profile,
        output_format=OutputFormat.DOCX,
        metadata=metadata,
    )

    render_result = DocumentRendererService().render(request)
    assert render_result.file_bytes is not None
    assert render_result.status.value == "COMPLETED"


def test_skill_registry_includes_document_creation() -> None:
    registry = create_capability_registry()
    names = {capability.name for capability in registry.list_available()}
    assert "document_creation" in names
    skill = registry.get_skill_for_capability("document_creation")
    assert skill is not None
    assert skill.name() == "document_creation_skill"
