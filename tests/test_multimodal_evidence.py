import io
import zipfile
from types import SimpleNamespace

import pymupdf
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from regintel.evidence.controls import records_from_csv
from regintel.evidence.controls import test_access_reviews as check_access
from regintel.evidence.parsers import parse_document
from regintel.evidence.pipeline import assess_match, persist_evidence, retrieve_evidence
from regintel.models.evidence import (
    EvidenceChunk,
    EvidenceDocument,
    EvidenceExtractionRun,
)


def archive(files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as z:
        for name, text in files.items():
            z.writestr(name, text)
    return output.getvalue()


def test_native_pdf_preserves_page_and_bounding_box():
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text((72, 72), "Synthetic access review evidence")
        result = parse_document(doc.tobytes(), "native.pdf")
    chunk = result["chunks"][0]
    assert chunk["location"]["page"] == 1 and len(chunk["location"]["bbox"]) == 4
    assert chunk["method"] == "native" and chunk["transcription_verified"]


def test_scanned_pdf_requires_ocr_and_never_auto_verifies_transcription():
    with pymupdf.open() as doc:
        doc.new_page()
        raw = doc.tobytes()
    assert parse_document(raw, "scan.pdf")["warnings"][0]["reason"] == "ocr_required"
    result = parse_document(
        raw, "scan.pdf", ocr=lambda image, mime: "Synthetic image transcription"
    )
    assert not result["chunks"][0]["transcription_verified"]
    assert result["chunks"][0]["location"]["region_scope"] == "whole_page"


@pytest.mark.parametrize("format,extension", [("png", "png"), ("jpeg", "jpg")])
def test_image_coordinates_use_actual_image_dimensions(format, extension):
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 30), False)
    pix.clear_with(255)
    result = parse_document(
        pix.tobytes(format),
        "fixture." + extension,
        ocr=lambda image, mime: "Synthetic text",
    )
    assert result["chunks"][0]["location"]["bbox"] == [0, 0, 40, 30]
    assert not result["chunks"][0]["transcription_verified"]


def test_docx_paragraph_and_table_locations_do_not_invent_pages():
    data = archive(
        {
            "word/document.xml": '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Synthetic policy</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>Review completed</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>'
        }
    )
    result = parse_document(data, "test.docx")
    assert result["chunks"][0]["location"] == {"kind": "docx", "paragraph": 1}
    assert result["chunks"][1]["location"] == {
        "kind": "docx",
        "table": 1,
        "row": 1,
        "column": 1,
    }


def test_xlsx_cells_preserved_and_formula_values_not_trusted():
    data = archive(
        {
            "xl/workbook.xml": '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Synthetic accounts" r:id="rId1"/></sheets></workbook>',
            "xl/_rels/workbook.xml.rels": '<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>',
            "xl/worksheets/sheet1.xml": '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row><c r="B2" t="inlineStr"><is><t>Reviewed</t></is></c><c r="C2"><f>1+1</f><v>2</v></c></row></sheetData></worksheet>',
        }
    )
    result = parse_document(data, "test.xlsx")
    assert result["chunks"][0]["location"] == {
        "kind": "xlsx",
        "sheet": "Synthetic accounts",
        "cell_range": "B2:B2",
    }
    assert (
        len(result["chunks"]) == 1
        and result["warnings"][0]["location"]["cell_range"] == "C2:C2"
    )


def test_csv_multiline_records_retain_physical_line_range():
    result = parse_document(b'id,notes\n1,"two\nlines"\n', "test.csv")
    assert result["chunks"][1]["location"]["line_start"] == 2
    assert result["chunks"][1]["location"]["line_end"] == 3
    assert result == parse_document(b'id,notes\n1,"two\nlines"\n', "test.csv")


@pytest.mark.parametrize(
    "payload,name",
    [
        (b"not a pdf", "test.pdf"),
        (b"not an image", "test.jpg"),
        (b"", "test.csv"),
        (b"unsupported", "test.exe"),
        (b"x" * 5_000_001, "test.csv"),
    ],
    ids=["invalid_pdf", "invalid_image", "empty_csv", "unsupported", "oversized"],
)
def test_invalid_and_oversized_input_rejected(payload, name):
    with pytest.raises(ValueError):
        parse_document(payload, name)


@pytest.mark.parametrize(
    "design,records,expected",
    [
        (False, [], "design_gap"),
        (None, [], "insufficient_evidence"),
        (True, [], "evidence_gap"),
    ],
)
def test_distinct_missing_design_and_evidence_outcomes(design, records, expected):
    assert (
        check_access(
            design_documented=design,
            records=records,
            as_of="2026-10-11",
            maximum_age_days=90,
        )["classification"]
        == expected
    )


@pytest.mark.parametrize(
    "reviewed,expected",
    [
        ("2026-10-01", "test_passed"),
        ("2026-01-01", "operating_gap"),
        ("invalid", "insufficient_evidence"),
        ("2027-01-01", "insufficient_evidence"),
    ],
)
def test_synthetic_control_uses_cited_csv_records(reviewed, expected):
    extraction = parse_document(
        f"record_id,last_reviewed\nSYN-001,{reviewed}\n".encode(), "synthetic.csv"
    )
    records = records_from_csv(extraction, synthetic=True)
    result = check_access(
        design_documented=True, records=records, as_of="2026-10-11", maximum_age_days=90
    )
    assert result["classification"] == expected and result["review_status"] == "pending"


def test_unverified_ocr_cannot_be_used_as_confirmed_operating_evidence():
    record = {
        "record_id": "SYN-001",
        "last_reviewed": "2026-01-01",
        "synthetic": True,
        "transcription_verified": False,
        "evidence_reference": {"page": 1},
    }
    assert (
        check_access(
            design_documented=True,
            records=[record],
            as_of="2026-10-11",
            maximum_age_days=90,
        )["classification"]
        == "insufficient_evidence"
    )
    contradictory = parse_document(
        b"record_id,last_reviewed,synthetic\nSYN-001,2026-01-01,false\n",
        "synthetic.csv",
    )
    with pytest.raises(ValueError):
        records_from_csv(contradictory, synthetic=True)


def test_evidence_persistence_bm25_and_workflow_bridge_are_location_bound():
    engine = create_engine("sqlite+pysqlite://")
    for model in (EvidenceDocument, EvidenceChunk, EvidenceExtractionRun):
        model.__table__.create(engine)
    extraction = parse_document(b"id,access\nSYN-001,access review\n", "synthetic.csv")
    with Session(engine) as db, db.begin():
        assert persist_evidence(db, extraction, "synthetic.csv", synthetic=True)[
            "inserted"
        ]
        assert not persist_evidence(db, extraction, "synthetic.csv", synthetic=True)[
            "inserted"
        ]
        match = retrieve_evidence(db, "access review")[0]
        workflow = SimpleNamespace(
            invoke=lambda **kw: {"final_status": "needs_review", "received": kw}
        )
        result = assess_match(
            workflow,
            obligation_id="synthetic",
            obligation_text="Review access",
            match=match,
        )
        assert result["evidence_reference"]["location"] == match["location"]
        assert db.scalar(select(func.count()).select_from(EvidenceDocument)) == 1
        match["transcription_verified"] = False
        assert (
            assess_match(
                workflow,
                obligation_id="synthetic",
                obligation_text="Review access",
                match=match,
            )["classification"]
            == "insufficient_evidence"
        )
    engine.dispose()


def test_actual_langgraph_adapter_keeps_native_evidence_location():
    from regintel.orchestration.verification_graph import VerificationWorkflow

    workflow = VerificationWorkflow(
        verifier=SimpleNamespace(model_name="preview-no-model"),
        cache=SimpleNamespace(get=lambda key: None),
        use_llm=False,
    )
    match = {
        "chunk_id": "synthetic-chunk",
        "document_id": "synthetic-document",
        "location": {"kind": "docx", "paragraph": 1},
        "text": "The fictional bank retains transaction records for five years.",
        "transcription_verified": True,
    }
    result = assess_match(
        workflow,
        obligation_id="synthetic",
        obligation_text="Retain transaction records for five years",
        match=match,
    )
    assert result["workflow"]["requires_human_review"]
    assert result["workflow"]["final_status"] == "needs_review"
    assert result["evidence_reference"]["location"] == match["location"]


def test_later_ocr_run_preserves_original_document_snapshot():
    engine = create_engine("sqlite+pysqlite://")
    for model in (EvidenceDocument, EvidenceChunk, EvidenceExtractionRun):
        model.__table__.create(engine)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 10, 10), False)
    pix.clear_with(255)
    payload = pix.tobytes("png")
    original = parse_document(payload, "synthetic.png")
    transcribed = parse_document(
        payload, "synthetic.png", ocr=lambda data, mime: "Synthetic transcription"
    )
    with Session(engine) as db, db.begin():
        persist_evidence(db, original, "synthetic.png", synthetic=True)
        result = persist_evidence(db, transcribed, "synthetic.png", synthetic=True)
        assert not result["inserted"] and result["extraction_run_inserted"]
        assert db.scalar(select(EvidenceDocument)).extraction == original
        assert db.scalar(select(func.count()).select_from(EvidenceExtractionRun)) == 2
        assert not db.scalar(select(EvidenceChunk)).transcription_verified
    engine.dispose()


def test_ocr_adapter_uses_image_bytes_and_rejects_extra_fields(monkeypatch):
    from regintel.evidence import ocr

    captured = []

    def generate(**kwargs):
        captured.append(kwargs)
        return SimpleNamespace(text='{"text":"Synthetic image text"}')

    monkeypatch.setattr(
        ocr.genai,
        "Client",
        lambda **kwargs: SimpleNamespace(
            models=SimpleNamespace(generate_content=generate)
        ),
    )
    adapter = ocr.GeminiOCR(api_key="synthetic-not-a-real-key", model="test-model")
    assert adapter(b"test-image", "image/png") == "Synthetic image text"
    assert captured[0]["contents"][1].inline_data.data == b"test-image"
    adapter.client.models.generate_content = lambda **kwargs: SimpleNamespace(
        text='{"text":"x","approved":true}'
    )
    with pytest.raises(ValueError):
        adapter(b"test-image", "image/png")
    adapter.client.models.generate_content = lambda **kwargs: SimpleNamespace(
        text='{"text":"partial"}',
        candidates=[SimpleNamespace(finish_reason="MAX_TOKENS")],
    )
    with pytest.raises(ValueError):
        adapter(b"test-image", "image/png")


def test_multimodal_api_preview_is_authenticated_and_nonpersistent():
    from fastapi.testclient import TestClient

    from regintel.api.app import create_app
    from regintel.api.dependencies import get_db
    from regintel.api.routes.auth import get_current_user

    app = create_app()
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/v1/ingestion/evidence-preview",
                files={"file": ("synthetic.csv", b"a,b\n1,2\n")},
            ).status_code
            == 401
        )
    app.dependency_overrides[get_current_user] = lambda: object()

    def forbidden_database():
        raise AssertionError("Preview cannot use database")

    app.dependency_overrides[get_db] = forbidden_database
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ingestion/evidence-preview",
            files={"file": ("synthetic.csv", b"a,b\n1,2\n")},
        )
        assert (
            response.status_code == 200
            and response.json()["chunks"][1]["location"]["record"] == 2
        )
        assert (
            client.post(
                "/api/v1/ingestion/evidence-preview",
                files={"file": ("invalid.docx", b"bad zip")},
            ).status_code
            == 422
        )
