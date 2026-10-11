# Gap classification evaluation

Run the offline scorer with reviewed test cases and exported predictions:

```powershell
uv run python -m regintel.mapping.gap_benchmark cases.json predictions.json gap_metrics.json
```

Cases are a JSON array containing unique `scenario_id`, `review_status:
"approved"`, `split: "test"`, and `expected_gap_status`. Predictions are a JSON
object mapping those same IDs to predicted statuses. Both use the existing
reporting labels: `supported`, `partial`, `missing`, `potential_conflict`.
Missing or extra predictions, unknown labels, and pending cases are rejected.
Approval is input metadata; this tool does not authenticate reviewers.

Results include accuracy, per-class precision/recall/F1, a confusion matrix
(rows are expected labels; columns are predictions), and scenario IDs for each
class's false positives and false negatives. Each class is treated as positive
against the remaining classes. Macro averages include all four classes,
including absent classes; undefined ratios are zero and supports are included.
These conventions are recorded in the output. Existing outputs are never
overwritten. Preserve inputs alongside outputs for reproducibility.

Keep related synthetic policy variants together when defining train/test
splits. Inspect error scenarios with their source and policy citations before
changing labels. The scorer does not produce predictions, verify split
provenance, or assess legal compliance. Draft scenarios remain unreviewed;
no project classification scores have been produced. Unit tests use toy data.
