# Pending review for recorded retrieval probes

## Local review screen

Open `data/processed/validation/relevance_review_verified.html` in Edge or Chrome.
It is a standalone page: no server or database connection is needed. The screen
starts with all six queries pending and displays all 500 candidates in pages of
25, with search and links to the official PDFs. Rankings are absent from this
screen. Source records remain pending regardless of your relevance decisions.

For each query, inspect the complete subset, select genuinely relevant IDs,
enter your reviewer name and source-backed rationale, and choose whether
relevant documents are present. After actual full-subset review, check the
attestation and click **Mark this query reviewed**. Changing any decision returns
that query to pending. The absence of relevant candidates is a valid choice.

Use **Export draft** before closing the tab; edits are held in memory. Restore
the saved JSON with the file selector. Restoration returns all queries to
pending and requires you to confirm reviews again. Stale-packet or malformed
drafts are rejected. After all six queries are explicitly reviewed, **Export
completed labels** downloads `reviewed_relevance.json` for the scoring command
below. Exports are self-reported annotations, not authenticated approvals.

Validation: 15 Python tests, five JavaScript tests, initial rendering, and eight
browser flow checks in headless Edge passed. The browser checks exercised
paging, search, selection, draft download, completed export, file restoration,
stale-file rejection and approval invalidation after editing. They used a
separate, clearly labeled synthetic fixture; its simulated decisions are not
project approvals. The [browser receipt](../data/processed/validation/review_screen_browser_flow.json)
records the checks and zero actual project approvals. No source records,
database data, original packet or benchmark results were changed. All real
review cases remain pending. To regenerate into a new artifact:

```powershell
uv run python -m regintel.mapping.review_screen --output new_local_review.html
```

To repeat the browser checks locally with installed Microsoft Edge:

```powershell
uv run python scripts/check_review_browser.py --output new_browser_flow_results.json
```

The harness requires `httpx` and `websockets`, creates a fresh synthetic fixture
and browser profile, and preserves its downloaded artifacts for inspection.

Optional [machine suggestions](relevance_suggestions.md) are now available in a
separate preview and JSON artifact. They reuse recorded BM25/MiniLM rankings,
remain unverified, and do not modify this blind packet or approve any labels.
Using them can bias annotations toward the evaluated retrievers, so they should
not be treated as independent ground truth. To regenerate into a new file:

```powershell
uv run python -m regintel.mapping.relevance_review suggest --packet data/processed/validation/phase4_relevance_review_packet.json --output new_unverified_suggestions.json
```

The packet is `data/processed/validation/phase4_relevance_review_packet.json`.
The editable starting form is
`data/processed/validation/phase4_relevance_labels_pending.json`. All six cases
are pending, relevant-ID lists are empty, and no reviewers or approvals were
invented. No database or original benchmark artifact was changed.

The blind packet contains all 500 frozen candidates, original IDs, source
hashes, official URLs, PDF paths and page ranges. Original PDF hashes and page
bounds were checked. Retrieval rankings are omitted to reduce annotation bias.
The deterministic 500-row prefix covers two sources: card issuance/conduct and
cybersecurity/technology risk. It is not a balanced sample of all RBI topics.
The existing six infrastructure queries are not independent held-out compliance
questions. A query can legitimately have no relevant candidate in this subset.

A human reviewer should inspect all candidates for each query and verify
ambiguous evidence against the PDFs. Record relevant IDs, reviewer identity and
a source-backed rationale. Set `full_corpus_reviewed` true only after reviewing
the complete subset. Use `answerability: "relevant_documents_present"` with a
nonempty list, or `answerability: "no_relevant_document_in_subset"` with an empty
list. Leave uncertain cases pending. Set review status to approved only after
actual review. Relevance review is not legal applicability or obligation
approval; reviewer identities are self-reported, not authenticated.

Preserve the pending form and save completed reviews under a new name. Keep
`packet_sha256` unchanged; it binds the complete source packet. To score the
recorded predictions without another model, database or benchmark run:

```powershell
uv run python -m regintel.mapping.relevance_review score --packet data/processed/validation/phase4_relevance_review_packet.json --reviews reviewed_relevance.json --output measured_recall.json
```

All six cases must be reviewed. Scoring rejects stale packets, changed recorded
predictions, unknown/duplicate IDs, missing reviewer/rationale, incomplete
corpus review and inconsistent answerability. Recall@5/@10 is conditional on
queries with nonempty ground truth. Unanswerable queries are reported separately
and do not receive fabricated zero/one Recall. If none are answerable, Recall
remains null. Retain this denominator and the packet/review hashes with scores.

Actual validation: 21 packet and retrieval-scorer tests passed. Simulated test
annotations exist only in unit tests; no approved review files or actual Recall
scores were generated. Independent evaluation, legal applicability and D3/F3
reliability remain pending.

## AI-labelled scores (October 11, 2026)

The human review was not completed. As a disclosed substitute, Claude
(`claude-opus-5-5`) read all 500 candidates for each of the six queries and
labelled relevance (`data/processed/validation/ai_relevance_labels.json`,
`annotation_source: "ai"`). A passage counts as relevant when its main subject is
the query topic; each case's rationale states the criterion. The compound
incident query is read as cyber-incident handling, so general security controls
are excluded. Relevant passages per query: 3, 22, 33, 40, 19, 21. These labels
are independent of the BM25 and MiniLM retrievers being scored, but they are not
human approvals.

| Method | Recall@5 | Recall@10 | Precision@5 | Precision@10 | Capped recall@10 | MRR@10 |
| --- | --- | --- | --- | --- | --- | --- |
| BM25 | 0.205 | 0.293 | 0.533 | 0.500 | 0.578 | 1.000 |
| Vector (MiniLM) | 0.240 | 0.295 | 0.667 | 0.483 | 0.561 | 0.917 |
| Hybrid | 0.248 | 0.298 | 0.733 | 0.500 | 0.578 | 1.000 |

Recall@k is capped at k / |relevant| when a query has more relevant passages
than k, so precision@k and capped recall (hits / min(k, |relevant|)) are
reported alongside. Scores come from the repository scorer, which also verifies
the corpus and ranking hashes (`phase4_scalability_warm_results.json`).
`scripts/eval_gate.py` recomputes hybrid precision@5 (gate ≥ 0.70) and MRR@10
(gate ≥ 0.90). A completed human review should replace these labels; the browser
review screen is unchanged and still produces `reviewed_relevance.json`.
