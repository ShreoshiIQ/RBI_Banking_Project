"""Create seven explicitly synthetic evidence fixtures with exclusive writes."""

import hashlib
import io
import json
import zipfile
from pathlib import Path

import pymupdf


def package(files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, content in sorted(files.items()):
            archive.writestr(
                zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0)), content
            )
    return output.getvalue()


def build():
    banner = "SYNTHETIC DEMONSTRATION - NOT REAL BANK EVIDENCE"
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text((40, 60), banner)
        page.insert_text((40, 90), "Account SYN-001 last reviewed 2026-10-01")
        page.insert_text((40, 110), "Account SYN-002 last reviewed 2026-01-01")
        native = doc.tobytes(no_new_id=True)
        pix = page.get_pixmap(alpha=False)
        png, jpg = pix.tobytes("png"), pix.tobytes("jpeg")
    with pymupdf.open() as scan:
        page = scan.new_page()
        page.insert_image(page.rect, stream=png)
        scanned = scan.tobytes(no_new_id=True)
    document = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>'
        + banner
        + "</w:t></w:r></w:p><w:p><w:r><w:t>Privileged access reviews are documented for this fictional bank.</w:t></w:r></w:p><w:sectPr/></w:body></w:document>"
    )
    types = '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>{}</Types>'
    rels = '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="{}"/></Relationships>'
    docx = package(
        {
            "word/document.xml": document,
            "_rels/.rels": rels.format("word/document.xml"),
            "[Content_Types].xml": types.format(
                '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            ),
        }
    )
    xlsx = package(
        {
            "[Content_Types].xml": types.format(
                '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            ),
            "_rels/.rels": rels.format("xl/workbook.xml"),
            "xl/workbook.xml": '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="SYNTHETIC reviews" sheetId="1" r:id="rId1"/></sheets></workbook>',
            "xl/_rels/workbook.xml.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
            "xl/worksheets/sheet1.xml": '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>'
            + banner
            + '</t></is></c></row><row r="2"><c r="A2" t="inlineStr"><is><t>SYN-001</t></is></c><c r="B2" t="inlineStr"><is><t>2026-10-01</t></is></c></row></sheetData></worksheet>',
        }
    )
    return {
        "SYN-access-native.pdf": native,
        "SYN-access-scanned.pdf": scanned,
        "SYN-access.png": png,
        "SYN-access.jpg": jpg,
        "SYN-access-design.docx": docx,
        "SYN-access-records.xlsx": xlsx,
        "SYN-access-records.csv": b"record_id,last_reviewed,synthetic\nSYN-001,2026-10-01,true\nSYN-002,2026-01-01,true\n",
    }


def main():
    directory = Path("data/raw/evidence/synthetic_demo")
    files = build()
    metadata = Path("data/metadata/multimodal_synthetic_demo.json")
    if metadata.exists() or any((directory / name).exists() for name in files):
        raise FileExistsError("Synthetic fixtures already exist; nothing overwritten")
    directory.mkdir(parents=True, exist_ok=True)
    records = []
    for name, payload in files.items():
        path = directory / name
        with path.open("xb") as stream:
            stream.write(payload)
        records.append(
            {
                "path": path.as_posix(),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "synthetic": True,
            }
        )
    with metadata.open("x", encoding="utf-8") as stream:
        json.dump(
            {
                "schema_version": 1,
                "synthetic": True,
                "profile_id": "fictional-commercial-bank-demo",
                "review_status": "pending",
                "files": records,
                "notice": "Infrastructure/control demonstrations only; not independent evaluation ground truth or regulatory coverage.",
            },
            stream,
            indent=2,
        )


if __name__ == "__main__":
    main()
