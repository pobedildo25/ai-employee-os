from pathlib import Path

import pytest

from app.file_processing.file_detector import FileDetector
from app.file_processing.models import FileCategory
from app.file_processing.processor import FileProcessor
from tests.fixtures.file_factory import (
    create_docx_file,
    create_pdf_file,
    create_png_file,
    create_pptx_file,
    create_txt_file,
    create_xlsx_file,
    read_file_bytes,
)


@pytest.fixture
def processor() -> FileProcessor:
    return FileProcessor()


@pytest.fixture
def detector() -> FileDetector:
    return FileDetector()


@pytest.fixture
def tmp_txt(tmp_path: Path) -> Path:
    return create_txt_file(tmp_path / "sample.txt")


@pytest.fixture
def tmp_pdf(tmp_path: Path) -> Path:
    return create_pdf_file(tmp_path / "sample.pdf")


@pytest.fixture
def tmp_docx(tmp_path: Path) -> Path:
    return create_docx_file(tmp_path / "sample.docx")


@pytest.fixture
def tmp_pptx(tmp_path: Path) -> Path:
    return create_pptx_file(tmp_path / "sample.pptx")


@pytest.fixture
def tmp_xlsx(tmp_path: Path) -> Path:
    return create_xlsx_file(tmp_path / "sample.xlsx")


@pytest.fixture
def tmp_png(tmp_path: Path) -> Path:
    return create_png_file(tmp_path / "sample.png")
