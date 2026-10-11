# Extraction evaluation

```powershell
uv run python -m regintel.mapping.extraction_benchmark cases.json predictions.json extraction_metrics.json
```

Cases are a JSON array with unique `case_id`, `review_status: "approved"`,
`split: "test"`, `annotation_complete: true`, a lowercase `source_sha256`,
and `expected_obligation_ids`. Predictions map each case ID to an object with
the same source digest and `extracted_obligation_ids`. Empty ID arrays are
allowed for fully annotated source units that contain no obligations.

Reviewers must enumerate all obligations in each evaluated source unit,
including obligations missed by extraction. Reviewing only existing candidates
cannot establish recall. Assign stable reference IDs and explicitly align
extracted candidates to them before scoring; unmatched candidates need distinct
IDs. IDs are matched exactly, without semantic or fuzzy matching. Approval and
annotation completeness are supplied metadata, not authenticated decisions.

The report aggregates true positives, false positives, and false negatives
across units to calculate micro precision, recall, and F1. Undefined ratios
are zero. Per-unit missed and unexpected IDs support error inspection. Do not
evaluate overlapping source units that count the same obligation twice.
Preserve reviewed inputs, candidate alignment, source files, and outputs for
reproducibility. Outputs cannot overwrite existing files.

This tool makes no model or database calls. Current candidate reviews are
pending and are not complete reference annotations; no project extraction
scores have been generated. Toy unit-test results are not benchmark results.
