# Citation location evaluation

```powershell
uv run python -m regintel.mapping.citation_benchmark cases.json predictions.json citation_metrics.json
```

Cases are a JSON array with unique `scenario_id`, `review_status: "approved"`,
`split: "test"`, and nonempty `acceptable_citations`. Predictions map the same
scenario IDs to citation arrays, which may be empty. Every citation contains
exactly `source_sha256` (lowercase SHA-256), `page` (one-based physical PDF page
index), and `clause_number` (string). Duplicate locations are rejected.

Reviewers must verify that each acceptable location supports the scenario's
claim and enumerate acceptable alternatives before scoring. Exact digest,
page, and clause matches count as correct. Citation location precision is
correct submitted citations divided by all submitted citations; case coverage
is the fraction of scenarios with at least one correct citation. Empty outputs
have zero coverage; undefined precision is zero. Incorrect citations appear
per scenario for inspection. Existing output files are protected from overwrite.

This measures agreement with reviewed citation locations, not quotation
accuracy, semantic entailment, applicability, or legal certification. The
scorer does not open PDFs or verify approval identity. Preserve inputs and
source versions with outputs. Current drafts lack approved citation references;
no project citation scores have been generated. Tests use toy references.
