# Policy-to-obligation mapping evaluation

Add a `mapping` component to the unified runner configuration:

```json
{"mapping": {"cases": "reviewed_pairs.json", "predictions": "pair_predictions.json"}}
```

Cases are a JSON array with unique `pair_id`, `obligation_id`,
`policy_section_id`, `review_status: "approved"`, `split: "test"`, and boolean
`expected_relevant`. Predictions map the same pair IDs to JSON booleans.
Duplicate obligation-policy pairs, missing predictions, string labels, and
pending reviews are rejected.

Reviewers label whether the policy section is relevant evidence for the
obligation, independently of whether it satisfies the obligation. Include
reviewed positive pairs and representative negative pairs. Define and preserve
the sampling protocol; metrics describe only the supplied pair set and do not
establish recall over an unannotated policy corpus. Keep related variants and
source versions together when assigning evaluation splits.

The scorer reports relevance precision, recall, F1, accuracy, TP/FP/FN/TN,
and misclassified pairs. Undefined ratios are zero. This is distinct from
retrieval Recall@K and from gap classification. Approval is supplied metadata,
not authenticated review. No reviewed project mapping set or project scores
are currently available. Tests use toy labels.
