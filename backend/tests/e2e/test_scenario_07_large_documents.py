from uuid import uuid4

import pytest

from app.brand_style.extractor import BrandStyleExtractor
from app.document_intelligence.pipeline import DocumentPipeline
from app.file_processing.processor import FileProcessor
from tests.fixtures.file_factory import (
    create_docx_with_table,
    create_large_pdf_file,
    create_png_file,
    create_pptx_with_image,
    read_file_bytes,
)


@pytest.mark.asyncio
async def test_large_pdf_pipeline(tmp_path, settings) -> None:
    pdf_path = create_large_pdf_file(tmp_path / "large.pdf", pages=100)
    data = read_file_bytes(pdf_path)
    pipeline = DocumentPipeline(processor=FileProcessor())
    representation, document_ast, extracted, detected = pipeline.process_bytes(
        artifact_id=uuid4(),
        title="Large PDF",
        data=data,
        filename="large.pdf",
        mime_type="application/pdf",
    )
    assert representation is not None
    assert extracted is not None
    assert detected.mime_type == "application/pdf"


@pytest.mark.asyncio
async def test_docx_with_tables_pipeline(tmp_path) -> None:
    docx_path = create_docx_with_table(tmp_path / "tables.docx")
    data = read_file_bytes(docx_path)
    pipeline = DocumentPipeline(processor=FileProcessor())
    representation, _ast, extracted, _detected = pipeline.process_bytes(
        artifact_id=uuid4(),
        title="Tables DOCX",
        data=data,
        filename="tables.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert extracted.text
    profile = BrandStyleExtractor().extract(representation, file_bytes=data, filename="tables.docx")
    assert profile.layout_rules.get("footer") is True


@pytest.mark.asyncio
async def test_pptx_with_image_pipeline(tmp_path) -> None:
    logo = create_png_file(tmp_path / "logo.png")
    pptx_path = create_pptx_with_image(tmp_path / "deck.pptx", logo)
    data = read_file_bytes(pptx_path)
    pipeline = DocumentPipeline(processor=FileProcessor())
    representation, _ast, extracted, _detected = pipeline.process_bytes(
        artifact_id=uuid4(),
        title="Image PPTX",
        data=data,
        filename="deck.pptx",
        mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
    assert extracted is not None
    raw = BrandStyleExtractor().extract_raw(representation, file_bytes=data, filename="deck.pptx")
    assert raw["slide_count"] >= 1
