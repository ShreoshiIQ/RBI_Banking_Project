# Clause comparison

The authenticated API exposes `POST /api/v1/changes/simulate`. Submit
`baseline`, `proposal`, and `policy_sections` using the CLI structures below.
All authenticated roles may run this read-only calculation. Invalid edits or
stale baseline hashes return 422; missing authentication returns 401.
Requests are limited to 50 baseline clauses, 50 edits, and 50 policy sections,
with 5,000 characters per evidence passage. Responses and nested results are
marked as simulations. Submitted hashes and evidence are client-supplied and
are not verified against the database. No regulatory or review state is updated.

## What-if simulation

Run the fully synthetic demonstration:

```powershell
uv run python -m regintel.changes.simulate data/evaluation/change_demo/baseline.json data/evaluation/change_demo/proposal.json data/evaluation/change_demo/policy_sections.json --output data/evaluation/change_demo/simulation_report.json
```

The proposal must identify the baseline hash and contains `edits` with
`clause_number`, `operation` (`add`, `modify`, or `remove`), and hypothetical
`clause_text` for additions/modifications. The workflow rejects missing targets,
duplicate edits, empty wording, and stale baselines. It preserves original
evidence and creates separate hypothetical clauses without attaching real PDF
page citations to invented wording. Hypothetical hashes use a `simulation:`
prefix, and nested comparisons and policy shortlists are explicitly labeled
simulation. The demonstration changes a fictional retention period; it is not
an RBI amendment or a compliance finding. No database writes occur, and existing
output files are preserved.

Policy impact shortlists can be generated with
`uv run python -m regintel.changes.impact change_report.json policy_sections.json --output impact_report.json`.
The policy input is a JSON list with unique `id`, `section_number`,
`section_title`, and `section_text` fields. Additional provenance and synthetic
status fields are preserved. The existing BM25 retriever searches old and new
clause text independently, including removed requirements, and skips unchanged
clauses. Results include source-side labels, policy passages, matched terms,
and lexical scores; every review status remains pending. These are review
candidates, not confirmed affected controls or compliance findings. No lexical
match does not establish no impact. Tests use synthetic fixtures only.

The deterministic comparison component accepts two JSON envelopes containing
`document_id`, `content_hash`, and `clauses`. Each clause requires
`clause_number` and `clause_text`; optional page ranges and status are preserved.
The document ID must identify the same instrument in both versions.

```powershell
uv run python -m regintel.changes.compare before.json after.json --output change_report.json
```

The output preserves before/after source passages, records added, removed,
modified, and unchanged clause numbers, and provides word differences.
Whitespace is normalized; quantities, punctuation, case, and negation remain
significant. Exact text under a different clause number produces a pending
renumbering hint, not an automatic amendment mapping. Output files are not
overwritten.

Withdrawn directions and their entity-specific replacements are different
instruments. They must not share a document ID merely to generate a revision
diff. Replacement comparison requires a separate reviewed mapping. Also,
different extracted text under the same PDF hash is an extraction revision,
not a regulatory amendment; the comparator rejects that inconsistency.

Source hashes must be verified against preserved PDF bytes before comparison.
Different extraction methods can introduce apparent changes even across
different PDF versions, so reviewers must inspect source passages.

Only synthetic unit fixtures have exercised this component so far. No real
revision comparison, policy impact result, or regulatory amendment finding is
claimed. Applicability and dataset-label reviews remain pending.
