# Evaluation status

The offline evaluation implementation covers extraction precision/recall/F1,
retrieval Recall@K and MRR@K across BM25/vector/hybrid, citation-location
precision and coverage, binary policy-to-obligation relevance, multiclass gap
classification, error inspection, and measured latency/token usage. The unified
runner preserves input SHA-256 digests and lists omitted components. It scores
supplied exports; it does not run the assessment pipeline or generate labels.

## Current evidence

The draft evaluation inventory contains 100 scenarios linked to 20 synthetic
policy drafts. The stored readiness report identifies 25 unique prompts, five
topic families, and two source versions. These are inventory counts, not
quality measurements. Scenarios and policies remain pending review, and
expected compliance labels are absent. Repeated prompts and related policy
variants must be accounted for when constructing independent evaluation splits.

No project extraction, retrieval, citation, mapping, gap-classification,
latency, or token-usage benchmark results are available. Toy tests demonstrate
metric arithmetic and runner integration; they cannot establish project quality.

## Inputs needed for a real benchmark

| Component | Reviewed or measured input required |
| --- | --- |
| Extraction | Complete source-unit annotations, including missed obligations, with explicit candidate alignment and source hashes |
| Retrieval | Approved relevant policy-section IDs and rankings from all three methods on identical test cases and corpora |
| Citations | Reviewed acceptable source-hash/page/clause locations and exported predicted citations |
| Mapping | Reviewed relevant and irrelevant obligation-policy pairs and boolean predictions |
| Gap classification | Approved expected reporting statuses and exported predicted statuses |
| Runtime | Actual durations, outcomes, and observed token counts with a consistent measurement scope |

Reviewers must verify regulatory applicability and source versions before
labeling cases. Synthetic policies must remain clearly identified. Annotation
approval in benchmark files is metadata; it is separate from authenticated
compliance-report approval. Scorers do not validate reviewer identities or
independence from training data.

## Reproduction

Follow [benchmark_runner.md](benchmark_runner.md) for file schemas and the
runner command. Retain source files, reviewed annotations, prediction exports,
input hashes, model versions, retrieval settings, policy corpus versions,
hardware, and split/sampling decisions with each result. Inspect listed false
positives, false negatives, and citation errors against their original evidence.
Do not silently relabel difficult cases or exclude failures from runtime reports.

The evaluation infrastructure is implemented; Day 28 empirical evaluation
remains unfinished until reviewed inputs and actual prediction runs are available.
