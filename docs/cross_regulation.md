# Cross-regulation intelligence and contradiction candidates

`regintel.crossreg` relates provisions across every locally preserved corpus:
the RBI KYC Directions, four RBI expansion directions (credit and debit cards,
cybersecurity, digital payment security, outsourcing), and three SEBI CSCRF
circulars. Provisions are obligation-bearing source text with page or block
citations. They are not reviewed obligations.

## Obligation families

All provisions are embedded with the local MiniLM model. Two provisions from
*different documents* are linked when each is among the other's three nearest
neighbours and cosine similarity is at least 0.72. Linked provisions form
families. A family spanning RBI and SEBI marks where one control may be tested
once against both regulators. Example: RBI cybersecurity clause 27 and SEBI
CSCRF page 80 both require designating a senior official as CISO.

## Contradiction candidates

Deterministic detectors run on cross-document pairs:

| Detector | Fires when |
| --- | --- |
| `quantitative_divergence` | Both texts state a single, different duration for the same action class (reporting, retention, review, resolution). The explanation names the stricter provision: shorter for deadlines, longer for retention. |
| `polarity_conflict` | One text prohibits and the other requires, and the clauses after the two modal verbs share at least two content words. |
| `retention_erasure_tension` | One text requires retaining records or data and the other requires deleting them. |

Pairs come from mutual top-3 links at similarity 0.62 or above, plus all
cross-document pairs of duration-bearing provisions at 0.55 or above. Sentences
with no action context, or with more than one, are skipped rather than guessed.

`--llm-judge` adds two order-swapped Gemini judgements per candidate. A candidate
becomes `judge_supported` only when both find a contradiction. A failed call
counts as no contradiction. Nothing is ever marked confirmed: every family and
candidate stays `pending` for legal review.

```powershell
uv run python -m regintel.crossreg.analysis --output data/processed/crossreg/new_report.json
```

Current local result (October 11, 2026): 1,015 provisions from 8 documents,
45 families, of which 6 span RBI and SEBI, and one quantitative divergence
candidate: RBI's six-hour cyber-incident report against a SEBI 15-day reporting
timeline. These are probably different report types, which is the kind of
candidate the judge and legal review exist to resolve. Detector precision and
recall have not been measured on reviewed labels.

`POST /api/v1/cross-regulation/compare` runs the deterministic detectors on two
supplied provisions for authenticated users. It makes no model calls.
