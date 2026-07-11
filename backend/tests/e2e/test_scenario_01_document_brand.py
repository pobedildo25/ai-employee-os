from uuid import uuid4

import pytest
from docx import Document
from io import BytesIO

from app.brand_style.extractor import BrandStyleExtractor
from app.document_intelligence.pipeline import DocumentPipeline
from app.document_renderer.models import OutputFormat, RenderRequest
from app.document_renderer.renderer import DocumentRendererService
from app.file_processing.processor import FileProcessor
from tests.e2e.helpers import brand_plan_steps
from tests.fixtures.file_factory import (
    create_docx_file,
    create_pdf_file,
    create_png_file,
    create_pptx_file,
    read_file_bytes,
)
from tests.llm_fixtures import creation_ast_json, executive_json, mock_gateway, plan_json, review_json


@pytest.mark.asyncio
async def test_sample_artifacts_and_brand_extraction(tmp_path, settings) -> None:
    docx_path = create_docx_file(tmp_path / "brand.docx", ["Client proposal template"])
    pptx_path = create_pptx_file(tmp_path / "brand.pptx", ["Opening slide"])
    pdf_path = create_pdf_file(tmp_path / "brand.pdf")
    logo_path = create_png_file(tmp_path / "logo.png")

    pipeline = DocumentPipeline(processor=FileProcessor())
    extractor = BrandStyleExtractor()

    for path, mime, title in [
        (docx_path, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "Brand DOCX"),
        (pptx_path, "application/vnd.openxmlformats-officedocument.presentationml.presentation", "Brand PPTX"),
        (pdf_path, "application/pdf", "Brand PDF"),
    ]:
        data = read_file_bytes(path)
        representation, _ast, _extracted, _detected = pipeline.process_bytes(
            artifact_id=uuid4(),
            title=title,
            data=data,
            filename=path.name,
            mime_type=mime,
        )
        profile = extractor.extract(representation, file_bytes=data, filename=path.name, client_id=str(uuid4()))
        assert profile.metadata["source_format"] in {"docx", "pptx", "pdf"}

    assert logo_path.exists()


@pytest.mark.asyncio
async def test_document_creation_with_brand_style_pipeline(
    e2e_runtime_factory,
    client_project_ids,
    tmp_path,
    settings,
) -> None:
    client_id, project_id = client_project_ids
    docx_path = create_docx_file(tmp_path / "source.docx", ["Commercial proposal body"])
    file_bytes = read_file_bytes(docx_path)
    pipeline = DocumentPipeline(processor=FileProcessor())
    artifact_id = uuid4()
    representation, _ast, extracted, _detected = pipeline.process_bytes(
        artifact_id=artifact_id,
        title="Source DOCX",
        data=file_bytes,
        filename="source.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    brand_profile = BrandStyleExtractor().extract(
        representation,
        file_bytes=file_bytes,
        filename="source.docx",
        client_id=str(client_id),
    )

    runtime, gateway, provider, registry = e2e_runtime_factory(
        executive_json(
            goal="Создай новое коммерческое предложение для клиента",
            summary="Нужно КП с фирменным стилем",
            action="EXECUTE",
            required_capabilities=["document_analysis", "brand_style_analysis", "document_creation", "document_rendering"],
            next_action="execute",
        ),
        plan_json(
            goal="Создай новое коммерческое предложение для клиента",
            steps=brand_plan_steps(),
        ),
        creation_ast_json(title="Commercial Proposal", document_type="docx"),
        review_json(score=0.95, summary="Branded proposal meets the goal"),
    )

    result = await runtime.execute(
        "Создай новое коммерческое предложение для клиента",
        context={
            "client_id": str(client_id),
            "project_id": str(project_id),
            "extracted_content": extracted.model_dump(mode="json"),
            "file_bytes": file_bytes,
            "filename": "source.docx",
            "brand_profile": brand_profile.model_dump(mode="json"),
        },
        metadata={"auto_approve": True, "client_id": str(client_id), "project_id": str(project_id)},
    )

    assert result["task_execution"]["status"] == "COMPLETED"
    assert result["execution_graph"] is not None
    assert result["progress"] == 100.0
    assert result["quality_check"]["passed"] is True
    assert result["quality_check"]["score"] >= 0.85

    plan = result["task_plan"]
    completed = [step for step in plan["steps"] if step["status"] == "COMPLETED"]
    assert len(completed) == 4

    brand_step = completed[1]
    assert brand_step["result"]["brand_profile"]["typography"] is not None
    assert "colors" in brand_step["result"]["brand_profile"]

    render_step = completed[3]
    render_result = render_step["result"]["render_result"]
    assert render_result is not None

    document_ast = completed[2]["result"]["document_ast"]
    assert document_ast["root"]["node_type"] == "document"
    rendered = DocumentRendererService().render(
        RenderRequest(
            document_structure=document_ast,
            brand_profile=brand_profile,
            output_format=OutputFormat.DOCX,
        )
    )
    assert rendered.file_bytes
    doc = Document(BytesIO(rendered.file_bytes))
    assert len(doc.paragraphs) >= 1

    assert provider.calls
