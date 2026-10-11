# Runtime evaluation

```powershell
uv run python -m regintel.mapping.runtime_benchmark measured_attempts.json runtime_metrics.json
```

Input is a JSON array of measured attempts with unique `attempt_id`,
`scenario_id`, `method`, finite nonnegative `duration_ms`, and `outcome`
(`success` or `failure`). Optional `input_tokens` and `output_tokens` are
nonnegative integers or null. Missing token usage stays unknown; use explicit
zero only for operations known to consume no model tokens.

Record wall-clock duration with a monotonic timer and usage from actual model
responses. Define each record consistently: either one end-to-end operation
including retries or one individual attempt. Do not mix these scopes or count
both. SDK-hidden retries may prevent complete token accounting; record missing
usage instead of estimating it. Include failed operations to avoid reporting
only fast successes. The scorer does not instrument model calls or incur API
charges.

Results group measurements by method and include success/failure counts,
mean, nearest-rank p50/p95, maximum latency, and observed token totals. Complete
token totals are null whenever any count is missing. Latencies include failures.
Preserve run configuration, model version, hardware, inputs, and output for
reproducibility. Existing output files cannot be overwritten. Compare methods
on identical cases and consistent measurement scopes; this summary does not
enforce a shared evaluation set or measure compliance quality.

No project runtime benchmark has been run. Unit tests use toy measurements.
