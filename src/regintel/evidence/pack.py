"""Seeded synthetic multimodal evidence pack with planted defects and a construction-time answer key.

Labels are true by construction for this fictional population. They measure
extraction and detection on these fixtures only, not real-bank accuracy.
"""

import hashlib
import io
import json
import random
import zipfile
from datetime import date, timedelta
from xml.sax.saxutils import escape

import numpy as np
import pymupdf

AS_OF = date(2026, 10, 1)
THRESHOLD_DAYS = 90
BANNER = "SYNTHETIC DEMONSTRATION - NOT REAL BANK EVIDENCE"
COLUMNS = ["record_id", "last_reviewed", "reviewer", "signoff"]
# Which records each evidence file holds (1-based, inclusive).
LAYOUT = {
    "access-reviews.csv": (1, 10),
    "access-reviews.xlsx": (11, 20),
    "access-reviews-native.pdf": (21, 28),
    "access-reviews-scanned.pdf": (29, 34),
    "access-reviews-photo.png": (35, 37),
    "access-reviews-lowres.jpg": (38, 40),
}
REVIEWERS = ["A. Rao", "B. Iyer", "C. Das", "D. Menon", "E. Khan", "F. Shah"]


def population(seed: int) -> list[dict]:
    rng = random.Random(seed)
    # Stratified: every evidence file holds at least one overdue and one unsigned record,
    # so detection is measured on each modality, plus random extras across the population.
    overdue, unsigned = set(), set()
    for first, last in LAYOUT.values():
        a, b = rng.sample(range(first, last + 1), 2)
        overdue.add(a)
        unsigned.add(b)
    overdue |= set(rng.sample(range(1, 41), 3))
    unsigned |= set(rng.sample(range(1, 41), 1))
    records = []
    for n in range(1, 41):
        age = rng.randint(THRESHOLD_DAYS + 5, 400) if n in overdue else rng.randint(1, THRESHOLD_DAYS - 5)
        records.append({"record_id": f"SYN-A{n:03d}", "last_reviewed": (AS_OF - timedelta(days=age)).isoformat(),
                        "reviewer": rng.choice(REVIEWERS), "signoff": "UNSIGNED" if n in unsigned else "SIGNED"})
    return records


def defects(record: dict) -> list[str]:
    found = []
    if (AS_OF - date.fromisoformat(record["last_reviewed"])).days > THRESHOLD_DAYS:
        found.append("overdue_review")
    if record["signoff"] != "SIGNED":
        found.append("missing_signoff")
    return found


def _zip(files: dict) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, content in sorted(files.items()):
            archive.writestr(zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0)), content)
    return output.getvalue()


TYPES = '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>{}</Types>'
RELS = '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="{}"/></Relationships>'


def xlsx(rows: list[list[str]], sheet: str) -> bytes:
    def cell(ref, value):
        return f'<c r="{ref}" t="inlineStr"><is><t>{escape(value)}</t></is></c>'
    body = "".join(
        f'<row r="{r}">' + "".join(cell(f"{chr(65 + c)}{r}", v) for c, v in enumerate(row)) + "</row>"
        for r, row in enumerate(rows, 1)
    )
    return _zip({
        "[Content_Types].xml": TYPES.format('<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'),
        "_rels/.rels": RELS.format("xl/workbook.xml"),
        "xl/workbook.xml": f'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="{escape(sheet)}" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        "xl/worksheets/sheet1.xml": f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{body}</sheetData></worksheet>',
    })


def docx(paragraphs: list[str]) -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{escape(p)}</w:t></w:r></w:p>" for p in paragraphs)
    return _zip({
        "word/document.xml": f'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{body}<w:sectPr/></w:body></w:document>',
        "_rels/.rels": RELS.format("word/document.xml"),
        "[Content_Types].xml": TYPES.format('<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'),
    })


def line(record: dict) -> str:
    return f"{record['record_id']} | {record['last_reviewed']} | {record['reviewer']} | {record['signoff']}"


def _text_page(lines: list[str], *, skew_degrees: float = 0.0, fontsize: float = 12) -> pymupdf.Document:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    origin = pymupdf.Point(50, 80)
    morph = (origin, pymupdf.Matrix(skew_degrees)) if skew_degrees else None
    page.insert_text(origin, "\n".join(lines), fontsize=fontsize, lineheight=1.6, morph=morph)
    return doc


def degraded_png(lines: list[str], *, rng: np.random.Generator, skew: float, dpi: int, noise: float,
                 fontsize: float = 9, blur: int = 1) -> bytes:
    """Skewed small text at low resolution, box-blurred, with Gaussian pixel noise."""
    with _text_page(lines, skew_degrees=skew, fontsize=fontsize) as doc:
        pix = doc[0].get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY, alpha=False)
    pixels = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).astype(np.float32)
    if blur:
        padded = np.pad(pixels, blur, mode="edge")
        size = 2 * blur + 1
        pixels = sum(padded[dy:dy + pix.height, dx:dx + pix.width] for dy in range(size) for dx in range(size)) / size**2
    pixels = np.clip(pixels + rng.normal(0, noise, pixels.shape), 0, 255).astype(np.uint8)
    noisy = pymupdf.Pixmap(pymupdf.csGRAY, pix.width, pix.height, pixels.tobytes(), False)
    return noisy.tobytes("png")


def build_pack(seed: int = 42) -> tuple[dict[str, bytes], dict]:
    records = population(seed)
    rng = np.random.default_rng(seed)
    pick = lambda name: records[LAYOUT[name][0] - 1:LAYOUT[name][1]]
    header = [BANNER, "Privileged access review evidence", " | ".join(COLUMNS)]
    files = {}
    csv_rows = [",".join(COLUMNS)] + [",".join(r[c] for c in COLUMNS) for r in pick("access-reviews.csv")]
    files["access-reviews.csv"] = ("\n".join(csv_rows) + "\n").encode()
    files["access-reviews.xlsx"] = xlsx([[BANNER], COLUMNS] + [[r[c] for c in COLUMNS] for r in pick("access-reviews.xlsx")], "SYNTHETIC reviews")
    with _text_page(header + [line(r) for r in pick("access-reviews-native.pdf")]) as doc:
        files["access-reviews-native.pdf"] = doc.tobytes(no_new_id=True)
    scan = degraded_png(header + [line(r) for r in pick("access-reviews-scanned.pdf")], rng=rng, skew=1.5, dpi=110, noise=30)
    with pymupdf.open() as doc:
        page = doc.new_page(width=595, height=842)
        page.insert_image(page.rect, stream=scan)
        files["access-reviews-scanned.pdf"] = doc.tobytes(no_new_id=True)
    files["access-reviews-photo.png"] = degraded_png(header + [line(r) for r in pick("access-reviews-photo.png")], rng=rng, skew=-3.0, dpi=120, noise=30, fontsize=10)
    low = degraded_png(header + [line(r) for r in pick("access-reviews-lowres.jpg")], rng=rng, skew=2.0, dpi=80, noise=20)
    files["access-reviews-lowres.jpg"] = pymupdf.Pixmap(low).tobytes("jpeg", jpg_quality=20)
    files["access-control-design.docx"] = docx([
        BANNER, "Control AC-07: Privileged access review (fictional)",
        f"Each privileged account is reviewed at least every {THRESHOLD_DAYS} days by an independent reviewer.",
        "Each review is signed off; unsigned reviews are not accepted as evidence.",
    ])
    # The register is the bank's own summary. Two entries disagree with their evidence (planted).
    register = [dict(r) for r in records]
    mismatched = sorted(rng.choice(np.arange(len(register)), size=2, replace=False).tolist())
    for index in mismatched:
        shown = date.fromisoformat(register[index]["last_reviewed"]) + timedelta(days=int(rng.integers(120, 200)))
        register[index]["last_reviewed"] = min(shown, AS_OF).isoformat()
    files["access-review-register.xlsx"] = xlsx([[BANNER], COLUMNS] + [[r[c] for c in COLUMNS] for r in register], "SYNTHETIC register")
    truth = {
        "schema_version": 1, "synthetic": True, "seed": seed, "as_of": AS_OF.isoformat(), "threshold_days": THRESHOLD_DAYS,
        "layout": {name: [r["record_id"] for r in pick(name)] for name in LAYOUT},
        "records": records,
        "defects": {r["record_id"]: defects(r) for r in records if defects(r)},
        "register_mismatches": [register[i]["record_id"] for i in mismatched],
        "register_file": "access-review-register.xlsx", "design_file": "access-control-design.docx",
        "file_sha256": {name: hashlib.sha256(data).hexdigest() for name, data in files.items()},
        "notice": "Answer key fixed at construction for a fictional population. Not real-bank evidence or independent ground truth.",
    }
    return files, truth


def truth_json(truth: dict) -> str:
    return json.dumps(truth, indent=2) + "\n"
