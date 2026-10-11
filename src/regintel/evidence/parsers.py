"""Bounded deterministic parsers; optional OCR receives only image bytes."""

import csv
import hashlib
import io
import json
import zipfile
from pathlib import PurePosixPath
from xml.etree import ElementTree as ET

import pymupdf

MAX_BYTES = 5_000_000
MAX_TEXT = 1_000_000
MAX_UNITS = 10_000


def parse_document(payload, filename, *, ocr=None):
    if not payload or len(payload) > MAX_BYTES:
        raise ValueError("Evidence file must be nonempty and at most 5 MB")
    kind = PurePosixPath(filename.lower()).suffix.lstrip(".")
    sha = hashlib.sha256(payload).hexdigest()
    chunks, warnings = [], []
    characters = 0
    ocr_regions = 0

    def add(text, location, method="native", verified=True):
        nonlocal characters
        if not text.strip():
            return
        chunks.append(
            {
                "text": text,
                "location": location,
                "method": method,
                "transcription_verified": verified,
            }
        )
        characters += len(text)
        if len(chunks) > MAX_UNITS or characters > MAX_TEXT:
            raise ValueError("Evidence extraction limits exceeded")

    def image_text(image, location):
        nonlocal ocr_regions
        if ocr is None:
            warnings.append({"location": location, "reason": "ocr_required"})
            return
        ocr_regions += 1
        if ocr_regions > 10:
            raise ValueError("Live OCR limit is ten regions per document")
        text = ocr(image, "image/png")
        if not isinstance(text, str):
            raise TypeError("OCR must return text")
        if not text.strip():
            warnings.append({"location": location, "reason": "ocr_returned_no_text"})
        add(text, location, "gemini_ocr", False)

    if kind == "pdf":
        if not payload.startswith(b"%PDF-"):
            raise ValueError("Invalid PDF signature")
        with pymupdf.open(stream=payload, filetype="pdf") as doc:
            if doc.needs_pass or len(doc) > 150:
                raise ValueError("Encrypted or over-150-page PDF unsupported")
            for number, page in enumerate(doc, 1):
                blocks = page.get_text("blocks")
                if any(b[4].strip() for b in blocks if b[6] == 0):
                    for b in blocks:
                        if b[6] == 0:
                            add(
                                b[4],
                                {
                                    "kind": "pdf",
                                    "page": number,
                                    "bbox": list(b[:4]),
                                    "coordinate_system": "pdf_points",
                                },
                            )
                    if page.get_images():
                        warnings.append(
                            {
                                "location": {"kind": "pdf", "page": number},
                                "reason": "embedded_images_not_transcribed_on_native_text_page",
                            }
                        )
                else:
                    if page.rect.width * page.rect.height > 20_000_000:
                        raise ValueError("Scanned page pixel limit exceeded")
                    image = page.get_pixmap(matrix=pymupdf.Matrix(1, 1), alpha=False)
                    image_text(
                        image.tobytes("png"),
                        {
                            "kind": "pdf",
                            "page": number,
                            "bbox": list(page.rect),
                            "coordinate_system": "pdf_points",
                            "region_scope": "whole_page",
                        },
                    )
    elif kind in ("png", "jpg", "jpeg"):
        expected = (
            payload.startswith(b"\x89PNG\r\n\x1a\n")
            if kind == "png"
            else payload.startswith(b"\xff\xd8")
        )
        if not expected:
            raise ValueError("Image signature mismatch")
        pix = pymupdf.Pixmap(payload)
        if pix.width * pix.height > 20_000_000:
            raise ValueError("Image pixel limit exceeded")
        image_text(
            pix.tobytes("png"),
            {
                "kind": "image",
                "bbox": [0, 0, pix.width, pix.height],
                "coordinate_system": "pixels",
                "region_scope": "whole_image",
            },
        )
    elif kind == "csv":
        rows = csv.reader(io.StringIO(payload.decode("utf-8-sig")), strict=True)
        previous_line = 0
        for number, row in enumerate(rows, 1):
            if number > MAX_UNITS:
                raise ValueError("CSV row limit exceeded")
            add(
                json.dumps(row, ensure_ascii=False),
                {
                    "kind": "csv",
                    "record": number,
                    "line_start": previous_line + 1,
                    "line_end": rows.line_num,
                    "column_start": 1,
                    "column_end": len(row),
                },
            )
            previous_line = rows.line_num
    elif kind in ("docx", "xlsx"):
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            if (
                len(archive.infolist()) > 2000
                or sum(i.file_size for i in archive.infolist()) > 30_000_000
            ):
                raise ValueError("OOXML expansion limit exceeded")

            def xml(name):
                data = archive.read(name)
                if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
                    raise ValueError("XML entities unsupported")
                return ET.fromstring(data)

            if kind == "docx":
                ns = {
                    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
                }
                body = xml("word/document.xml").find("w:body", ns)
                if body is None:
                    raise ValueError("DOCX body missing")
                paragraph, table = 0, 0
                for node in body:
                    if node.tag.endswith("}p"):
                        paragraph += 1
                        add(
                            "".join(t.text or "" for t in node.findall(".//w:t", ns)),
                            {"kind": "docx", "paragraph": paragraph},
                        )
                    elif node.tag.endswith("}tbl"):
                        table += 1
                        for r, row in enumerate(node.findall("w:tr", ns), 1):
                            for c, cell in enumerate(row.findall("w:tc", ns), 1):
                                add(
                                    "".join(
                                        t.text or "" for t in cell.findall(".//w:t", ns)
                                    ),
                                    {
                                        "kind": "docx",
                                        "table": table,
                                        "row": r,
                                        "column": c,
                                    },
                                )
                warnings.append({"reason": "docx_page_numbers_not_inferred"})
            else:
                ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                shared = []
                if "xl/sharedStrings.xml" in archive.namelist():
                    shared = [
                        "".join(t.text or "" for t in si.findall(".//s:t", ns))
                        for si in xml("xl/sharedStrings.xml").findall("s:si", ns)
                    ]
                relations = {
                    r.attrib["Id"]: r.attrib["Target"]
                    for r in xml("xl/_rels/workbook.xml.rels")
                }
                for sheet in xml("xl/workbook.xml").findall("s:sheets/s:sheet", ns):
                    rid = sheet.attrib[
                        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
                    ]
                    target = relations[rid]
                    path = (
                        target.lstrip("/") if target.startswith("/") else "xl/" + target
                    )
                    if ".." in PurePosixPath(path).parts or not path.startswith("xl/"):
                        raise ValueError("Invalid XLSX relationship")
                    for cell in xml(path).findall(".//s:sheetData/s:row/s:c", ns):
                        location = {
                            "kind": "xlsx",
                            "sheet": sheet.attrib["name"],
                            "cell_range": cell.attrib["r"] + ":" + cell.attrib["r"],
                        }
                        if cell.find("s:f", ns) is not None:
                            warnings.append(
                                {
                                    "location": location,
                                    "reason": "formula_not_evaluated_cached_value_unverified",
                                }
                            )
                            continue
                        value = cell.findtext("s:v", default="", namespaces=ns)
                        if cell.attrib.get("t") == "s":
                            value = shared[int(value)]
                        elif cell.attrib.get("t") == "inlineStr":
                            value = "".join(
                                t.text or "" for t in cell.findall(".//s:t", ns)
                            )
                        add(value, location)
    else:
        raise ValueError("Supported formats: PDF, DOCX, XLSX, CSV, PNG, JPG")
    for index, chunk in enumerate(chunks):
        chunk["chunk_id"] = hashlib.sha256(
            json.dumps([sha, index, chunk], sort_keys=True).encode()
        ).hexdigest()
    return {
        "schema_version": 1,
        "file_sha256": sha,
        "format": kind,
        "chunks": chunks,
        "ocr_model": getattr(ocr, "model", None),
        "warnings": warnings,
        "review_status": "pending",
        "notice": "Source locations identify extracted evidence; OCR transcription and authenticity require review.",
    }
