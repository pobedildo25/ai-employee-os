from pathlib import Path
from uuid import uuid4

import pytest

from app.brand_style.extractor import BrandStyleExtractor
from app.brand_style.models import BrandProfile
from app.brand_style.profile_manager import BrandProfileManager, BrandProfileNotFoundError, prepare_brand_memory_items
from app.brand_style.rules.style_rules import build_brand_profile
from app.document_intelligence.pipeline import DocumentPipeline
from app.file_processing.processor import FileProcessor
from app.memory.models import MemoryType
from app.skills.builtin.brand_style_analysis_skill import BrandStyleAnalysisSkill
from app.skills.registry import create_capability_registry
from tests.fixtures.file_factory import read_file_bytes


@pytest.fixture
def brand_extractor() -> BrandStyleExtractor:
    return BrandStyleExtractor()


@pytest.fixture
def pipeline() -> DocumentPipeline:
    return DocumentPipeline(processor=FileProcessor())


@pytest.fixture
def profile_manager() -> BrandProfileManager:
    return BrandProfileManager()


def test_brand_profile_creation() -> None:
    client_id = uuid4()
    profile = BrandProfile(
        client_id=client_id,
        name="Client Brand",
        typography={"heading_font": "Arial", "body_font": "Calibri"},
        colors={"primary": "#123456"},
        layout_rules={"header": "top", "footer": True},
    )

    assert profile.client_id == client_id
    assert profile.typography["heading_font"] == "Arial"
    assert profile.colors["primary"] == "#123456"


def test_docx_style_extraction(brand_extractor: BrandStyleExtractor, pipeline: DocumentPipeline, tmp_docx: Path) -> None:
    artifact_id = uuid4()
    file_bytes = read_file_bytes(tmp_docx)
    representation, _document_ast, _extracted, _detected = pipeline.process_bytes(
        artifact_id=artifact_id,
        title="Brand DOCX",
        data=file_bytes,
        filename="brand.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    profile = brand_extractor.extract(
        representation,
        file_bytes=file_bytes,
        filename="brand.docx",
        client_id=str(uuid4()),
    )
    raw = brand_extractor.extract_raw(representation, file_bytes=file_bytes, filename="brand.docx")

    assert profile.metadata["source_format"] == "docx"
    assert "paragraph_count" in raw or profile.document_rules.get("paragraph_count", 0) >= 0
    assert profile.layout_rules.get("footer") is True


def test_pptx_style_extraction(brand_extractor: BrandStyleExtractor, pipeline: DocumentPipeline, tmp_pptx: Path) -> None:
    artifact_id = uuid4()
    file_bytes = read_file_bytes(tmp_pptx)
    representation, _document_ast, _extracted, _detected = pipeline.process_bytes(
        artifact_id=artifact_id,
        title="Brand PPTX",
        data=file_bytes,
        filename="brand.pptx",
        mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )

    profile = brand_extractor.extract(
        representation,
        file_bytes=file_bytes,
        filename="brand.pptx",
        client_id=str(uuid4()),
    )
    raw = brand_extractor.extract_raw(representation, file_bytes=file_bytes, filename="brand.pptx")

    assert profile.metadata["source_format"] == "pptx"
    assert raw["slide_count"] >= 1
    assert "slide_width" in raw
    assert profile.layout_rules.get("slide_dimensions") is not None


def test_pdf_style_extraction(brand_extractor: BrandStyleExtractor, pipeline: DocumentPipeline, tmp_pdf: Path) -> None:
    artifact_id = uuid4()
    file_bytes = read_file_bytes(tmp_pdf)
    representation, _document_ast, _extracted, _detected = pipeline.process_bytes(
        artifact_id=artifact_id,
        title="Brand PDF",
        data=file_bytes,
        filename="brand.pdf",
        mime_type="application/pdf",
    )

    profile = brand_extractor.extract(
        representation,
        file_bytes=file_bytes,
        filename="brand.pdf",
        client_id=str(uuid4()),
    )
    raw = brand_extractor.extract_raw(representation, file_bytes=file_bytes, filename="brand.pdf")

    assert profile.metadata["source_format"] == "pdf"
    assert raw["page_count"] == 1
    assert profile.document_rules.get("page_count") == 1
    assert profile.layout_rules.get("page_sizes")


def test_profile_manager_lifecycle(profile_manager: BrandProfileManager) -> None:
    client_id = uuid4()
    profile = BrandProfile(
        client_id=client_id,
        name="Managed Profile",
        colors={"primary": "#111111"},
        typography={"body_font": "Arial"},
    )

    created = profile_manager.create_profile(profile)
    loaded = profile_manager.get_profile(created.id)
    assert loaded is not None
    assert loaded.name == "Managed Profile"

    updated = profile_manager.update_profile(created.id, {"name": "Updated Profile"})
    assert updated.name == "Updated Profile"

    client_profiles = profile_manager.get_profiles_for_client(client_id)
    assert len(client_profiles) == 1


def test_compare_profiles(profile_manager: BrandProfileManager) -> None:
    left = profile_manager.create_profile(
        BrandProfile(name="Left", colors={"primary": "#111111"}, typography={"body_font": "Arial"})
    )
    right = profile_manager.create_profile(
        BrandProfile(name="Right", colors={"primary": "#222222"}, typography={"body_font": "Arial"})
    )

    comparison = profile_manager.compare_profiles(left.id, right.id)
    assert comparison["colors_match"] is False
    assert comparison["typography_match"] is True
    assert "primary" in comparison["differences"]["colors"]


def test_compare_profiles_not_found(profile_manager: BrandProfileManager) -> None:
    profile = profile_manager.create_profile(BrandProfile(name="Only"))
    with pytest.raises(BrandProfileNotFoundError):
        profile_manager.compare_profiles(profile.id, uuid4())


def test_memory_preparer(profile_manager: BrandProfileManager) -> None:
    client_id = uuid4()
    profile = profile_manager.create_profile(
        BrandProfile(
            client_id=client_id,
            name="Memory Profile",
            colors={"primary": "#123456"},
            typography={"heading_font": "Arial", "body_font": "Calibri"},
        )
    )

    items = prepare_brand_memory_items(profile, client_name="Acme Corp")
    assert len(items) == 2
    assert items[0].type == MemoryType.FACT
    assert "корпоративный стиль" in items[0].content
    assert items[1].type == MemoryType.KNOWLEDGE
    assert items[1].metadata["kind"] == "brand_profile"
    assert items[1].client_id == client_id


@pytest.mark.asyncio
async def test_brand_style_analysis_skill(
    pipeline: DocumentPipeline,
    tmp_docx: Path,
) -> None:
    artifact_id = uuid4()
    client_id = uuid4()
    file_bytes = read_file_bytes(tmp_docx)
    representation, _document_ast, _extracted, _detected = pipeline.process_bytes(
        artifact_id=artifact_id,
        title="Skill DOCX",
        data=file_bytes,
        filename="skill.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    skill = BrandStyleAnalysisSkill()
    result = await skill.execute(
        {
            "document_representation": representation.model_dump(mode="json"),
            "file_bytes": file_bytes,
            "filename": "skill.docx",
            "client_id": str(client_id),
            "client_name": "Test Client",
        }
    )

    assert result["status"] == "completed"
    assert result["brand_profile"]["client_id"] == str(client_id)
    assert result["memory_candidates"]
    assert result["artifact_metadata_patch"]["brand_style_extraction"]["status"] == "completed"


def test_skill_registry_includes_brand_style_analysis() -> None:
    registry = create_capability_registry()
    names = {capability.name for capability in registry.list_available()}
    assert "brand_style_analysis" in names
    skill = registry.get_skill_for_capability("brand_style_analysis")
    assert skill is not None
    assert skill.name() == "brand_style_analysis_skill"


def test_build_brand_profile_from_raw_style() -> None:
    profile = build_brand_profile(
        raw_style={
            "format": "docx",
            "fonts": ["Calibri", "Arial"],
            "font_sizes": [11.0, 14.0],
            "text_colors": ["#123456"],
            "heading_styles": ["Heading 1"],
            "table_count": 1,
            "paragraph_count": 3,
            "page_margins": {"top": 72.0, "bottom": 72.0, "left": 72.0, "right": 72.0},
        },
        client_id=uuid4(),
        name="Built Profile",
        source_artifact_id=uuid4(),
    )

    assert profile.typography["body_font"] == "Calibri"
    assert profile.typography["heading_font"] == "Arial"
    assert profile.colors["primary"] == "#123456"
    assert profile.layout_rules["footer"] is True
    assert profile.document_rules["uses_tables"] is True
