"""Summarize measured evaluation attempts without estimating missing usage."""

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path


def summarize_runtime(attempts: list[dict]) -> dict:
    if not attempts:
        raise ValueError("At least one measured attempt is required")
    grouped = defaultdict(list)
    seen = set()
    for row in attempts:
        for field in ("attempt_id", "scenario_id", "method"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError(f"{field} must be a nonempty string")
        if row["attempt_id"] in seen:
            raise ValueError("Attempt IDs must be unique")
        seen.add(row["attempt_id"])
        duration = row.get("duration_ms")
        if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration < 0:
            raise ValueError("duration_ms must be finite and nonnegative")
        if row.get("outcome") not in {"success", "failure"}:
            raise ValueError("Outcome must be success or failure")
        for field in ("input_tokens", "output_tokens"):
            value = row.get(field)
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise ValueError("Token counts must be nonnegative integers or null")
        grouped[row["method"]].append(row)
    methods = {}
    for method, rows in sorted(grouped.items()):
        durations = sorted(row["duration_ms"] for row in rows)
        usage = {}
        for field in ("input_tokens", "output_tokens"):
            measured = [row[field] for row in rows if row.get(field) is not None]
            usage[field] = {"known_total": sum(measured), "measured_attempts": len(measured),
                            "missing_attempts": len(rows) - len(measured),
                            "complete_total": sum(measured) if len(measured) == len(rows) else None}
        methods[method] = {
            "attempts": len(rows), "unique_scenarios": len({row["scenario_id"] for row in rows}),
            "successes": sum(row["outcome"] == "success" for row in rows),
            "failures": sum(row["outcome"] == "failure" for row in rows),
            "latency_ms": {"mean": sum(durations) / len(rows),
                           "p50": durations[math.ceil(0.50 * len(rows)) - 1],
                           "p95": durations[math.ceil(0.95 * len(rows)) - 1],
                           "maximum": durations[-1]},
            "usage": usage,
        }
    return {"schema_version": 1, "percentile_method": "nearest_rank",
            "latency_scope": "all_recorded_attempts_including_failures", "methods": methods}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("attempts", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = summarize_runtime(json.loads(args.attempts.read_text(encoding="utf-8")))
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)


if __name__ == "__main__":
    main()
