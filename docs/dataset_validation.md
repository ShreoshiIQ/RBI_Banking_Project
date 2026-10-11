# Dataset validation baseline

Phase 4 adds [isolated scalability and evidence evaluations](phase4_evaluation.md).
`phase4_inventory_verified.json` confirms the application inventory remains
unchanged from Phase 3. Synthetic stress rows are excluded from regulatory counts.

For the October 11, 2026 Phase 3 source and database inventory, see
[Phase 3 expansion](phase3_expansion.md) and
`data/processed/validation/phase3_inventory_verified.json`. The KYC-focused
counts below describe the original source review, not the expanded database.

Run from the project root:

```powershell
uv run python -m regintel.ingestion.validate_dataset
uv run pytest tests/test_dataset_validation.py tests/test_obligation_quality.py
```

The command reads existing artifacts and writes separate JSON reports under
`data/processed/validation`. It does not update PostgreSQL, source documents,
review decisions, or extracted candidates. Candidate indices are zero-based
within the source catalog. Each row preserves the original candidate and
records reasons for human review. Passing checks does not approve an obligation.

## Current inventory

- One RBI KYC PDF, 107 pages, matching the recorded SHA-256.
- 82 clause candidates and 312 obligation candidates.
- 231 deferred passages remain outside the obligation catalog.
- One clearly labeled synthetic internal policy.
- Six provisional retrieval labels; these are topic-relevance labels, not
  compliance judgments or a held-out benchmark.

The PDF cover lists updates through August 14, 2025. These are extracted
version-date mentions, not verification that this is the latest applicable
regulation. Publication and amendment dates still require manual confirmation.

## Findings from the current catalog

All 312 candidates have an unresolved actor. Five Section 46 evidence quotes
initially failed a contiguous-text check: they inherit `REs shall` from the
parent and attach it to subclauses (b)–(f). The validation now reconstructs
inherited candidates from the source clause using the existing extractor and
requires an exact match after whitespace normalization. All five match; no
evidence was changed. Six
candidates originate in preliminary or applicability clauses. Other warnings
include 52 candidates with multiple modal keywords, 22 with amendment metadata,
and three with historical or deleted text. Categories overlap.

No normalized duplicate evidence was detected within a document version.
This does not rule out semantic duplicates. The report distinguishes
`contiguous`, `inherited_reconstruction`, and `unmatched` evidence. Reconstruction
shares the extractor's segmentation rules and does not independently validate
its interpretation of hierarchy. Evidence matching checks the local extracted
clause text, not visual accuracy against the PDF. It also does not
prove the database clause UUID or document-version UUID is correctly linked.

## Next dataset work

## Offline human decisions

An unfilled 312-row decisions template is available at
`data/processed/validation/e525b18753fd_review_decisions.json`.
All rows start pending; actor suggestions are not automatically approved.
Review the corresponding validation row and source PDF before entering a
decision. Approved rows require reviewer, rationale, source citation, actor,
and entity-specific applicability. Rejected rows require reviewer, rationale,
and source citation. These are offline dataset annotations, separate from
authenticated compliance-report approvals.

Validate decisions and export a separate reviewed catalog:

```powershell
uv run python -m regintel.ingestion.catalog_review data/processed/validation/e525b18753fd_validation.json --decisions data/processed/validation/e525b18753fd_review_decisions.json --output data/processed/validation/e525b18753fd_reviewed_catalog.json
```

The command rejects stale source/candidate hashes, unknown or duplicate
indices, incomplete decisions, and approval of unmatched evidence. It preserves
original candidates alongside annotations and refuses to overwrite an output
file. Omitted candidates remain pending. Reviewer names are self-reported in
this local workflow; the file does not authenticate reviewers or certify legal
correctness. No database writes occur.

## Actor and applicability review

The validation report now includes `actor_review` for each candidate. The
current catalog has 84 source-backed actor suggestions and 228 without a
suggestion. Original actors remain unchanged. Each suggestion cites the exact
subject/modal phrase and character offsets in the original evidence quote.
Suggestions are pending human review, including inherited Section 46 evidence.

The conservative rule recognizes explicit subjects immediately before
`shall`, `must`, or `may`. Passive wording, multiple competing actors,
preliminary text, and unmatched evidence receive no suggestion. Conditional
scope is flagged. Every candidate's applicability remains subject to human
review; no entity-specific applicability is inferred. These rules are a review
aid and do not establish extraction accuracy.

1. Preserve the inherited-source explanation for Section 46; review hierarchy
   against the PDF before treating reconstructed evidence as legally validated.
2. Resolve regulated actors and applicability through source-backed review;
   keep title, commencement, and definitions separate from operational controls.
3. Review amendment and historical passages against the PDF and source versions.
4. Record human dispositions without overwriting the original candidate evidence.
5. Verify official sources and entity applicability before adding regulatory documents.
6. Expand synthetic policies and evaluation cases only against reviewed requirements.

The proposed 5–8 additional documents, 20–40 synthetic policies, and roughly
100 evaluation scenarios remain future targets. No extraction precision,
recall, or legal validation score is inferred from heuristic checks.
