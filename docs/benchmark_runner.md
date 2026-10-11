# Reproducible offline evaluation

For the subsequently implemented isolated PostgreSQL scalability runner and
actual Phase 4 infrastructure measurements, see
[Phase 4 evaluation](phase4_evaluation.md). The offline scorer described below
still requires supplied reviewed references and predictions; it does not
generate those labels.

Run supplied evaluation exports together:

```powershell
uv run python -m regintel.mapping.run_benchmark benchmark_config.json benchmark_results.json
```

Configuration paths resolve relative to the configuration file. Example:

```json
{
  "retrieval": {"cases": "retrieval_cases.json", "predictions": "rankings.json", "k": 5},
  "extraction": {"cases": "extraction_cases.json", "predictions": "extractions.json"},
  "gaps": {"cases": "gap_cases.json", "predictions": "gap_predictions.json"},
  "mapping": {"cases": "reviewed_pairs.json", "predictions": "pair_predictions.json"},
  "citations": {"cases": "citation_cases.json", "predictions": "citations.json"},
  "runtime": {"attempts": "measured_attempts.json"}
}
```

Supply only components with real inputs. The report lists omitted components
and includes SHA-256 digests of the configuration and every input file. Input
validation remains enforced by each scorer. All components must succeed before
output is created; existing output files cannot be overwritten. Retain inputs
and configuration with the results. Hashes identify files, not label quality.

Input formats and metric conventions are described in
[retrieval](retrieval_benchmark.md), [extraction](extraction_benchmark.md),
[gap classification](gap_benchmark.md), [citations](citation_benchmark.md), and
[runtime](runtime_benchmark.md), and [mapping](mapping_benchmark.md).
Retrieval metrics measure ranking relevance; the mapping scorer separately
evaluates supplied reviewed obligation-policy pairs.

The runner does not generate predictions, access PostgreSQL, make model calls,
authenticate annotations, or enforce independence between training and test
data. Current draft labels remain pending, and no project scores are available.
