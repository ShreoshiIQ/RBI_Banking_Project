# Synthetic policy drafts and review scenarios

Generate or verify the artifacts with:

```powershell
uv run python scripts/build_synthetic_policies.py
```

Twenty synthetic policy drafts are stored under
`data/raw/policies/synthetic_drafts`, with metadata in
`data/metadata/synthetic_policy_drafts.json`. Each has purpose, procedure, and
oversight sections in the format accepted by the existing policy parser.
Five topics each have detailed, partial, vague, and conflicting variants.
The variants intentionally exercise evidence gaps and contradictory procedures;
they are not twenty independently authored institutional policies.

The nested draft directory keeps these unreviewed documents outside the current
policy ingestor's top-level TXT scan. They have not been persisted to PostgreSQL.
All documents prominently identify synthetic status and unreviewed applicability.
Source anchors identify candidate clauses and pages but represent topic links,
not verified mappings between every procedure and a regulatory requirement.

One hundred provisional review scenarios are in
`data/evaluation/synthetic_draft_scenarios.json`. They cover topic retrieval,
procedures, missing detail, exceptions, and execution evidence. They are design
prompts with pending labels, not manually validated ground truth or a held-out
benchmark. Variants within a topic share content: keep each topic family in one
data split when creating a benchmark to prevent leakage.

Review source applicability, scenario specificity, section relevance, and expected
outcomes before using these for scored evaluation. No compliance judgments or
benchmark scores are supplied. A detailed written procedure alone does not
prove execution. The generator preserves modified files and refuses to
overwrite changed metadata.

## Evaluation readiness

Run `uv run python -m regintel.mapping.dataset_readiness` to regenerate
`data/evaluation/synthetic_draft_readiness.json`.

The 100 policy/scenario pairs contain only 25 distinct prompt texts across
five related topic families and two source versions. The four policy variants
reuse each topic's prompts intentionally. They must not be described as 100
independent questions. All scenario labels and policy reviews remain pending,
and none has compliance ground truth. The readiness check therefore refuses
to describe this dataset as ready for scored compliance evaluation.

The report lists repeated prompts, topic-family groups, and source-version
groups for manual split design. It does not assign a train/test split or compute
scores. Validate question specificity, source applicability, relevant sections,
and expected outcomes before benchmark use. A reviewer is needed to provide
actual ground truth; changing `pending` to `approved` alone is not validation.
