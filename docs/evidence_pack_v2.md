# Multimodal evidence pack v2 and measured results

`regintel.evidence.pack` builds a seeded, fictional privileged-access evidence
pack. `regintel.evidence.pack_eval` measures how the evidence pipeline handles
it against labels fixed when the pack is built.

## The pack

40 access-review records (record, last review date, reviewer, sign-off),
split across six evidence files, plus two supporting files:

| File | Records | Treatment |
| --- | --- | --- |
| `access-reviews.csv` | 10 | native |
| `access-reviews.xlsx` | 10 | native |
| `access-reviews-native.pdf` | 8 | native text |
| `access-reviews-scanned.pdf` | 6 | rasterised, 1.5° skew, 110 dpi, noise σ=30 |
| `access-reviews-photo.png` | 3 | −3° skew, 120 dpi, noise σ=30 |
| `access-reviews-lowres.jpg` | 3 | 2° skew, 80 dpi, blur, noise σ=20, JPEG q=20 (deliberately hard) |
| `access-control-design.docx` | — | control design with the fictional 90-day threshold |
| `access-review-register.xlsx` | 40 | the bank's own register; 2 entries disagree with their evidence |

Planted defects: every evidence file holds at least one review older than
90 days and one unsigned review, plus random extras.

## Decision rule

- Native records are accepted.
- OCR records are always unverified. They are accepted only when date and
  sign-off both match the register (**corroborated**). Otherwise they go to human
  verification with both values side by side.
- The control test (overdue or unsigned) runs only on accepted records.

## Results (October 11, 2026, six seeds, `gemini-3.1-flash-lite`)

240 records: 168 native, 72 through live OCR.
Raw runs and the aggregate are in `data/processed/validation/evidence_pack_v2/`.

| Measure | Result |
| --- | --- |
| Native extraction | 168/168 records, 100% field accuracy |
| OCR record recall | 72/72 |
| OCR field accuracy | 94.4% overall: scanned PDF 100%, photo 100%, low-resolution JPG 77.8% |
| Decisions | 168 native, 61 corroborated, 11 to human verification |
| **Silent errors** (wrong values accepted without a human) | **0** |
| Defect detection on accepted records | precision 1.00, recall 0.92 (7 misses, all on records awaiting humans) |
| Same, if OCR were trusted blindly | precision 0.97, recall 0.99 (3 false defects, 1 missed) |
| Register mismatch detection | recall 1.00 (12/12); precision 0.60, because OCR misreads also disagree with the register and are routed to humans |

All eight OCR errors were dates on the low-resolution JPG: year 2026 read as
2025, and month or day digits confused (6↔8, 9↔8). Each disagreed with the
register, so none was accepted. Without corroboration, these misreads would
have produced three false overdue findings.

## Limits

- Labels are true by construction for a fictional population; this is not a
  measure of real-bank OCR accuracy or control effectiveness.
- Corroboration cannot catch an OCR error that coincides with an identical
  register error. Records absent from the register always go to humans.
- One layout and one record schema; handwriting, stamps, tables with ruled
  lines, and multi-page scans are not covered.

```powershell
uv run python -m regintel.evidence.pack_eval --seed 42 --output new_eval.json            # offline, images unread
uv run python -m regintel.evidence.pack_eval --seed 42 --live-ocr --output new_eval.json # Gemini OCR
uv run python -m regintel.evidence.pack_eval --seed 42 --write-pack new_pack_dir --output new_eval.json
```
