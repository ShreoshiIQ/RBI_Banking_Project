# Phase 4 — measured probes and evaluation boundaries

A subsequent [blind relevance review packet](relevance_review.md) now makes
pending annotations concrete for the frozen 500-candidate run. No human labels
or Recall scores have been created. It explicitly supports queries with no
relevant document in the selected subset.

Implemented October 11, 2026. Benchmark data is in fresh, uniquely named
PostgreSQL databases; the application schema and source/review records were not
modified. This phase supplies measured infrastructure probes and evaluation
tooling. It does not demonstrate D3/F3 reliability or legal compliance.

## Workloads

The read-only snapshot contains 1,150 pending RBI candidates. Two exact repeated
quotes within their source version were excluded from the benchmark view,
leaving **1,148 unique source-derived candidate quotes**. Original database rows
remain unchanged. Distinct quotes are not equivalent to distinct validated
obligations; semantic deduplication and human review remain pending.

| Requested size | Source-derived workload | Separate synthetic stress workload |
| --- | --- | --- |
| 500 | Measured | Measured |
| 2,000 | Unavailable: only 1,148 unique candidate quotes | Measured |
| 5,000 | Unavailable | Measured |
| 10,000 | Unavailable | Measured |

Synthetic rows have `SYN-STRESS-*` IDs, explicit synthetic text and a zero
regulatory-coverage count. They repeat six topic templates with distinct IDs;
this is an infrastructure workload, not semantic or regulatory coverage.
SEBI's 496 review blocks are not counted as segmented obligations and were not
mixed into the bank workload.

## What was measured

`regintel.mapping.scalability` compares BM25, PostgreSQL exact cosine vector
scan and reciprocal-rank fusion. These probes retrieve **obligations from
obligations**, not policy evidence against independently labeled compliance
questions. Six fixed topic queries each run ten times per method at one and
four workers: 60 attempts per method/concurrency/size. Requests use threads and
a four-connection pool against local PostgreSQL. This is a short probe, not a
long-running saturation or production load test.

The prewarmed run opens all four connections before timing retrieval and warms
each method with the six queries. It records connection startup separately.
Latency includes pool acquisition, lexical work, SQL fetch and fusion; excludes
query embedding and executor queue wait. Throughput includes thread-pool setup
and counts successful attempts over wall time. Error rate includes all attempts;
p50/p95 include successful attempts. Raw query IDs/rankings, durations and error
types are retained. No model provider was called.

Ingestion measures cached CPU MiniLM embedding, BM25 construction, database
table creation/load and ANALYZE. It excludes raw PDF parsing, model startup,
database creation, serialization-size measurement and query embedding. Storage
reports PostgreSQL table/index/total bytes, including TOAST in total bytes.
There is no ANN index: vector search is an exact scan. PostgreSQL index bytes
are primary-key indexes, not a vector index. BM25 serialized index size is
measured separately and is not resident RAM consumption. Model/package and
platform metadata are recorded. The cached model weights/config/tokenizer
hashes are in `phase4_reproducibility.json`; the loader's revision field is null
when unavailable rather than guessed.

Initial runs were retained with connection creation inside the first concurrent
vector probe. Their low-size outliers led to one prewarmed repeat, rather than
discarding or silently rewriting measurements. Pool warmup in the genuine
repeat took 15.078 seconds. Both initial and prewarmed result files remain.

## Genuine 500-candidate results

Source: `data/processed/validation/phase4_scalability_warm_results.json`.

| Retrieval method | Workers | p50 ms | p95 ms | Successful requests/s | Error rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| BM25 | 1 | 0.55 | 0.82 | 1,602.85 | 0 / 60 |
| BM25 | 4 | 0.52 | 0.91 | 1,594.48 | 0 / 60 |
| Exact vector | 1 | 3.58 | 4.85 | 270.60 | 0 / 60 |
| Exact vector | 4 | 4.58 | 6.32 | 807.33 | 0 / 60 |
| Hybrid | 1 | 4.84 | 6.42 | 201.29 | 0 / 60 |
| Hybrid | 4 | 8.27 | 10.68 | 455.24 | 0 / 60 |

Measured ingestion throughput: 128.78 rows/s. PostgreSQL storage: 983,040 table
bytes, 65,536 index bytes and 1,155,072 total bytes. BM25 serialized index:
185,364 bytes. These numbers describe this machine and short workload; zero
observed errors do not establish a production reliability rate.

**Recall@5 and Recall@10 are unscored.** There are no reviewed held-out relevance
labels for these probes. Queries, self-retrieval and synthetic IDs are not used
to fabricate labels. With a supplied reviewed labels file, the runner checks the
exact probe query, scenario ID, test split, approved annotation status and
relevant IDs against the selected corpus, then uses the existing recall scorer
at both cutoffs. Annotation status is externally supplied, not authenticated or
created by the benchmark. Predictions and label file SHA-256 are preserved.

## Synthetic infrastructure results — not regulatory coverage

Source: `phase4_synthetic_stress_warm_results.json`. Each retrieval row below
uses four workers and 60 measured attempts. One-worker results and original
startup-inclusive runs remain in the JSON artifacts. No Recall scores are
reported for synthetic topic-template records.

| Synthetic rows | Method | p50 ms | p95 ms | Successful requests/s | Error rate |
| ---: | --- | ---: | ---: | ---: | ---: |
| 500 | BM25 | 0.53 | 1.03 | 1,527.22 | 0 / 60 |
| 500 | Exact vector | 5.02 | 6.37 | 743.10 | 0 / 60 |
| 500 | Hybrid | 8.85 | 11.10 | 439.57 | 0 / 60 |
| 2,000 | BM25 | 18.77 | 25.91 | 212.08 | 0 / 60 |
| 2,000 | Exact vector | 6.51 | 13.97 | 551.27 | 0 / 60 |
| 2,000 | Hybrid | 26.45 | 34.68 | 147.94 | 0 / 60 |
| 5,000 | BM25 | 92.42 | 129.77 | 42.77 | 0 / 60 |
| 5,000 | Exact vector | 10.28 | 13.73 | 354.46 | 0 / 60 |
| 5,000 | Hybrid | 46.47 | 58.08 | 84.80 | 0 / 60 |
| 10,000 | BM25 | 171.35 | 216.11 | 22.87 | 0 / 60 |
| 10,000 | Exact vector | 13.54 | 16.59 | 283.42 | 0 / 60 |
| 10,000 | Hybrid | 193.61 | 231.46 | 20.71 | 0 / 60 |

| Synthetic rows | Ingestion rows/s | PostgreSQL total bytes | PostgreSQL PK index bytes | BM25 serialized bytes |
| ---: | ---: | ---: | ---: | ---: |
| 500 | 228.65 | 1,097,728 | 40,960 | 131,648 |
| 2,000 | 152.14 | 4,227,072 | 98,304 | 522,648 |
| 5,000 | 94.29 | 10,493,952 | 221,184 | 1,299,649 |
| 10,000 | 94.61 | 20,938,752 | 425,984 | 2,607,949 |

Pool warmup was 15.112 seconds. These measurements vary between runs on this
workstation; the repeat was not uniformly faster than the first run. The
prewarmed table is shown for its consistent connection setup, not because it
selects the fastest outcomes. Retain both runs when interpreting variance.

## Multimodal and control evaluation

`phase4_evidence_evaluation_final.json` records actual deterministic synthetic
fixture checks:

- Four native PDF/DOCX/XLSX/CSV fixtures match known synthetic text fragments.
- Three scanned/image fixtures abstain and require OCR when no OCR provider is
  supplied. Abstention is not counted as successful OCR extraction.
- Three native PDF citations were checked directly against the original PDF
  page and rectangle. CSV references were checked against original physical
  source lines as well as chunk/hash identities.
- Six synthetic control cases produce the expected design gap, operating gap,
  evidence gap, insufficient evidence or passing-sample result. SYN-002 is the
  stale record under the explicit fictional 90-day threshold.
- The previously recorded live Gemini PNG transcription exactly matches the
  normalized fixture text in one sample. No new OCR call was made, no human
  transcription verification was created, and other image formats' live OCR
  accuracy remains unmeasured.

This is fixture regression evidence, not independent held-out extraction,
evidence-correctness, citation-accuracy or gap-classification quality on real
bank/regulatory material. Existing extraction/citation/gap scorers remain
available for externally reviewed test exports. Independent labels, larger
format-diverse sets, hallucination checks, OCR word/character error evaluation,
negative evidence cases and end-to-end grounded mapping remain pending.

## Reproduction and database safeguards

Run from the project root, choosing new artifact paths:

```powershell
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
uv run python -m regintel.mapping.scalability export --output new_candidates.json
uv run python scripts/run_phase4_scalability.py --snapshot new_candidates.json --output new_genuine_results.json
uv run python -m regintel.mapping.scalability synthetic --output new_synthetic_stress.json
uv run python scripts/run_phase4_scalability.py --snapshot new_synthetic_stress.json --output new_stress_results.json
uv run python -m regintel.evidence.evaluation --output new_evidence_results.json
```

The launcher creates a new `regintel_benchmark_<32 hexadecimal characters>`
database for every run and retains it. It never drops or recreates an existing
database. The runner refuses application/test database names and any nonempty
benchmark database. Only dedicated benchmark databases receive the vector
extension and `corpus_500`, `corpus_2000`, `corpus_5000`, `corpus_10000` tables.
No Alembic migration is added. The role needs database-creation permission.
This is experiment isolation, not shared tenant authorization or RLS.

Optional `--labels reviewed_labels.json` on the launcher accepts a dictionary
keyed by size (`"500"`, etc.), each containing six existing-scorer cases in query
order. IDs are `probe-0` through `probe-5`; `query` must equal the corresponding
constant in `scalability.py`. Cases need `split: "test"`, externally reviewed
`review_status: "approved"`, and `relevant_section_ids` containing actual
benchmark corpus IDs (the name is retained from the existing scorer). No labels
file was fabricated or supplied for the recorded runs.

Reaching the larger genuine sizes requires additional distinct source-derived,
entity-scoped obligations. Preserve historical sources, review amendment and
applicability status, and freeze each new per-entity workload snapshot before
benchmarking. Do not supplement bank counts with SEBI passages or synthetic
records. Longer sustained runs, repetitions across independent frozen datasets,
queue-inclusive end-to-end latency and ANN comparisons remain future work.

## Validation and pending requirements

Full regression: **419 passed, 4 skipped in 28.89 seconds**. Affected evaluation
and benchmark safety tests passed separately after the final citation changes
(7 passed). Ruff checks passed. The final read-only application inventory
matches Phase 3 counts, regulator counts, review states, evidence counts and
schema revision. Application obligations remain 1,150 pending, with zero human
approvals; synthetic stress rows are absent from that inventory.

Implemented and measured: isolated benchmark databases, BM25/exact-vector/hybrid,
genuine 500-candidate measurements, separately labeled stress workloads at all
four targets, ingestion/storage/concurrency/error measurements, strict recall
scoring inputs, and synthetic multimodal/control/citation evaluation.

Pending: larger genuine datasets, reviewed retrieval labels and Recall scores,
independent multimodal/evidence/citation/gap accuracy, legal applicability,
SEBI segmentation/amendment coverage, shared tenant isolation and demonstrated
D3/F3 reliability. No benchmark or human approval has been invented.
