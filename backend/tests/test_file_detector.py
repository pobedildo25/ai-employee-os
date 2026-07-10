import pytest

from app.file_processing.models import FileCategory
from tests.fixtures.file_factory import read_file_bytes


@pytest.mark.parametrize(
    ("filename", "mime_type", "expected_category"),
    [
        ("report.pdf", "application/pdf", FileCategory.PDF),
        ("doc.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", FileCategory.DOCX),
        ("slides.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation", FileCategory.PPTX),
        ("data.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", FileCategory.XLSX),
        ("notes.txt", "text/plain", FileCategory.TEXT),
        ("photo.png", "image/png", FileCategory.IMAGE),
        ("photo.jpg", "image/jpeg", FileCategory.IMAGE),
    ],
)
def test_file_detector_categories(detector, filename, mime_type, expected_category) -> None:
    detected = detector.detect(filename, mime_type=mime_type)
    assert detected.category == expected_category
    assert detected.mime_type == mime_type
    assert detected.extension.startswith(".")


def test_file_detector_magic_bytes(detector, tmp_pdf, tmp_png) -> None:
    pdf_detected = detector.detect("unknown", data=read_file_bytes(tmp_pdf))
    assert pdf_detected.category == FileCategory.PDF

    png_detected = detector.detect("unknown", data=read_file_bytes(tmp_png))
    assert png_detected.category == FileCategory.IMAGE
