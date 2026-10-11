# Reviewed retrieval benchmark

The offline scorer reuses the existing retrieval metrics and compares exported
BM25, vector, and hybrid rankings against the same reviewed test cases.
It makes no database or model calls.

The cases input is a JSON array. Each case requires `scenario_id`,
`review_status: "approved"`, `split: "test"`, and a nonempty array of
`relevant_section_ids` containing stable policy-section IDs. Review approval
is supplied metadata, not an authenticated approval workflow. Reviewers must
check the labels and keep related policy variants out of training splits.

The rankings input is a JSON object with exactly `bm25`, `vector`, and `hybrid`.
Each method maps every scenario ID to an ordered array of section IDs.
Empty rankings count as misses; missing cases and duplicate IDs are rejected.
Use identical policy corpora, queries, and section IDs for all three methods.

```powershell
uv run python -m regintel.mapping.retrieval_benchmark reviewed_cases.json rankings.json benchmark.json --k 5
```

The output contains per-case results and macro-average Recall@K and MRR@K.
MRR@K counts only the first relevant result within the cutoff. Existing output
files are protected from overwrite. Preserve input files alongside each result
to reproduce the calculation. This scorer does not generate rankings, verify
held-out provenance, or measure extraction, citations, gap classification,
latency, or token usage.

Current synthetic scenarios remain pending review and cannot be scored by this
tool. Automated tests use hand-calculated toy rankings; their results are not
project benchmark scores.
