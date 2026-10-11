"""Local PDF clause preview; no persistence or regulatory approval."""

import csv
import hashlib
import zipfile
from xml.etree.ElementTree import ParseError

import pymupdf
from fastapi import APIRouter, Depends, HTTPException, UploadFile

from regintel.api.routes.auth import get_current_user
from regintel.evidence.parsers import parse_document
from regintel.ingestion.clause_extractor import extract_clauses
from regintel.ingestion.source_status import inspect_source_status

router = APIRouter(prefix="/ingestion", tags=["Ingestion preview"], dependencies=[Depends(get_current_user)])


@router.post("/evidence-preview")
def preview_evidence(file: UploadFile):
    payload = file.file.read(5_000_001)
    if len(payload) > 5_000_000:
        raise HTTPException(413, "Evidence preview limit is 5 MB")
    try:
        return parse_document(payload, file.filename or "")
    except (ValueError, RuntimeError, KeyError, IndexError, UnicodeError, zipfile.BadZipFile, ParseError, csv.Error):
        raise HTTPException(422, "Evidence could not be parsed; check its supported format and limits") from None


@router.post("/preview")
def preview_pdf(file: UploadFile):
    payload = file.file.read(5_000_001)
    if len(payload) > 5_000_000:
        raise HTTPException(413, "PDF preview limit is 5 MB")
    if not payload.startswith(b"%PDF-"):
        raise HTTPException(422, "A PDF file is required")
    try:
        with pymupdf.open(stream=payload, filetype="pdf") as document:
            if document.needs_pass:
                raise HTTPException(422, "Encrypted PDFs are unsupported")
            if len(document) > 150:
                raise HTTPException(413, "PDF preview limit is 150 pages")
            pages = []
            characters = 0
            for number, page in enumerate(document, 1):
                text = page.get_text()
                characters += len(text)
                if characters > 1_000_000:
                    raise HTTPException(413, "Extracted text exceeds the preview limit")
                pages.append({"page_number": number, "text": text})
    except HTTPException:
        raise
    except (RuntimeError, ValueError):
        raise HTTPException(422, "PDF could not be read") from None
    clauses = extract_clauses(pages)
    return {"sha256": hashlib.sha256(payload).hexdigest(), "pages": len(pages),
            "source_status": inspect_source_status(pages), "clauses_found": len(clauses),
            "clauses": [clause.model_dump() for clause in clauses[:50]], "preview_limit": 50,
            "notice": "Unreviewed upload preview; no database records or source files saved. Source authenticity and applicability are unverified. No OCR is performed."}
