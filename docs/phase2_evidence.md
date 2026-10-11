# Phase 2 multimodal evidence

This is a single-profile synthetic demonstration implementation. It does not
introduce shared tenant access or establish D3/F3 reliability. Phase 3 is not
started. All evidence and control results require human review.

| Requirement | Implemented and tested | Remaining limits |
| --- | --- | --- |
| Native PDF | PyMuPDF text blocks, page and exact PDF-point bounds | OCR of images embedded on native-text pages is flagged, not performed automatically |
| Scanned PDF, PNG, JPG | Optional Gemini image transcription, actual page/image bounds; provider timeout/retries and ten-region call cap | Whole-page/image citation regions; no inferred word boxes; accuracy and human transcription verification pending |
| DOCX | Deterministic OOXML paragraphs and table cells | Pagination is not inferred; headers, footnotes, tracked changes, drawings, and embedded objects are outside this parser's coverage |
| XLSX | Deterministic sheet/cell text and shared strings | Formulas and cached formula values are flagged and excluded; style-based dates are not converted; charts and embedded images are not transcribed |
| CSV | UTF-8 records, physical line ranges including multiline fields, column ranges | Encoding/dialect inference is not performed |
| PostgreSQL and pgvector | Separate append-only documents, chunks, extraction runs, and 384-dimensional embeddings; idempotent indexing | Demo corpus cap of 1,000 retrieval chunks; no ANN index or scalability claim |
| BM25/vector/hybrid | Existing tokenizer/BM25, exact pgvector cosine search, reciprocal-rank fusion | Candidate relevance does not establish evidence correctness or control effectiveness |
| LangGraph | Existing workflow adapter retains source locations and blocks unverified OCR | Existing workflow evaluates document design; operating tests remain a separate deterministic result |
| Control effectiveness | Synthetic access-review records with cited CSV locations and an explicit fictional age threshold | No population-level assurance or inferred regulatory deadline |
| Dashboard/API | Authenticated `/api/v1/ingestion/evidence-preview` and multimodal upload form | Preview has no persistence or live OCR; CLI performs explicitly selected live operations |

## Safety and provenance

Evidence persistence accepts only explicitly synthetic inputs for
`fictional-commercial-bank-demo`. Native parsing sets transcription fidelity,
not authenticity, completeness, applicability, or human approval. Image OCR
always sets transcription verification false. The workflow adapter returns
`insufficient_evidence` for unverified OCR instead of running the verifier.
There is no automatic OCR approval path.

Limits include 5 MB original files, 150 PDF pages, 20 million image/rendered
pixels, 30 MB OOXML expansion, 2,000 ZIP members, 10,000 extracted units, and
one million extracted characters. XML DTD/entity declarations and unsafe
spreadsheet relationship paths are rejected; macros and formulas are never
executed. Native parsers are not process-sandboxed, and this is not a complete
hostile-document security review.

The original document snapshot is immutable. Later OCR/parsing snapshots
are stored as new hash-bound extraction runs and append new chunks. Existing
chunks with conflicting contents fail rather than being overwritten.
Restrictive foreign keys and disabled automatic downgrades protect evidence.

Migrations `d190f0020001` and `d190f0020002` create four new evidence tables.
They were inspected and tested in a generated schema in the dedicated
PostgreSQL test database before application. Application receipts record
hashed checks proving preservation of every pre-existing row. The existing
312 pending obligations, policies, policy embeddings, users, reports, and
review history were not rewritten.

## Actual demonstration evidence

Seven reproducible synthetic fixtures and their byte hashes are recorded in
`data/metadata/multimodal_synthetic_demo.json`. Files are under
`data/raw/evidence/synthetic_demo/`. Their generator uses exclusive writes and
labels them synthetic; they are not regulatory coverage or evaluation labels.

The database contains seven evidence documents, 12 chunks, and eight extraction
runs. Four native/structured documents produced 11 chunks. A live configured
Gemini `gemini-3.1-flash-lite` call transcribed one synthetic PNG into one
additional, unverified chunk. The scanned PDF and JPG demonstrations still
require live OCR; the PNG still requires human transcription verification.
No OCR accuracy score or human approval was generated.

The existing local MiniLM model generated 11 native evidence embeddings in
offline mode and a second pass inserted none. BM25, exact vector, and hybrid
query smoke checks returned candidates. These are query execution checks,
not Recall or latency benchmarks. A subsequent receipt records indexing of
the OCR chunk; its unverified flag remains unchanged.

The CSV control demonstration uses two explicitly synthetic account records.
With an explicit fictional 90-day threshold and assessment date 2026-10-11,
`SYN-002` fails the age test. The result is `operating_gap`, with the source
file hash, chunk identity, and CSV line/column location. Tests also distinguish
`design_gap`, `evidence_gap`, `insufficient_evidence`, and `test_passed`.
A passing sample does not prove effectiveness across a bank.

Receipts and live OCR preview: `data/processed/validation/phase2_*.json`.

## Reproduction

Actual verification results: **398 Python tests passed, 3 opt-in PostgreSQL
tests skipped** in the isolated full suite (application-data integration
excluded). The separately enabled evidence PostgreSQL test and focused
multimodal tests passed **26 checks**. Following the dashboard/inventory
integration, the affected Python checks passed **39 tests**, and all **7 Node
client tests** passed. New evidence-module Ruff checks passed. One live
synthetic PNG OCR call completed; that is provider smoke evidence, not an
accuracy evaluation. The final inventory is
`data/processed/validation/phase2_inventory_verified.json`.

Run from the project root, choosing a new output filename each time:

```powershell
uv run alembic upgrade d190f0020002
uv run python -m regintel.evidence.cli data/raw/evidence/synthetic_demo/SYN-access-records.csv --output native_evidence_preview.json
uv run python -m regintel.evidence.cli data/raw/evidence/synthetic_demo/SYN-access-records.csv --synthetic --persist --index --output native_evidence_receipt.json
uv run python -m regintel.evidence.cli data/raw/evidence/synthetic_demo/SYN-access-scanned.pdf --live-ocr --ocr-model $env:GEMINI_MODEL --synthetic --persist --output scanned_evidence_receipt.json
```

Live OCR explicitly sends selected image content to Gemini and requires a
configured `GEMINI_API_KEY` or `GOOGLE_API_KEY`. The model must be supplied
explicitly; the CLI loads `.env` only when live OCR is selected. Native parsing
and control tests do not call Gemini. Indexing uses the existing local model,
which may download on first use; this demonstration used its cached files.

Pending reliability work: representative real-format samples, OCR correctness,
human transcription review, unsupported Office content, population completeness,
end-to-end authenticated browser upload checks, and Phase 4 quality/scalability
evaluation. Existing package/image artifacts predating these migrations must
be rebuilt before deployment.
