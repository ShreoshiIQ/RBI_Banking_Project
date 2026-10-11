"""Run supplied offline evaluation components with input provenance."""

import argparse
import hashlib
import json
from pathlib import Path

from regintel.mapping.citation_benchmark import score_citations
from regintel.mapping.extraction_benchmark import score_extraction
from regintel.mapping.gap_benchmark import score_gaps
from regintel.mapping.mapping_benchmark import score_mapping
from regintel.mapping.retrieval_benchmark import score_retrieval
from regintel.mapping.runtime_benchmark import summarize_runtime

SCORERS = {"retrieval": score_retrieval, "extraction": score_extraction,
           "gaps": score_gaps, "citations": score_citations, "mapping": score_mapping}
COMPONENTS = (*SCORERS, "runtime")


def run_benchmark(config_path: Path) -> dict:
    config_bytes = config_path.read_bytes()
    config = json.loads(config_bytes)
    if not isinstance(config, dict) or not config or set(config) - set(COMPONENTS):
        raise ValueError("Supply one or more known evaluation components")
    provenance = {}
    results = {}

    def read_input(component, field, path_value):
        if not isinstance(path_value, str) or not path_value.strip():
            raise ValueError("Input paths must be nonempty strings")
        path = (config_path.parent / path_value).resolve()
        payload = path.read_bytes()
        provenance[f"{component}.{field}"] = {"path": path_value, "sha256": hashlib.sha256(payload).hexdigest()}
        return json.loads(payload)

    for component, specification in config.items():
        expected = {"attempts"} if component == "runtime" else {"cases", "predictions"}
        allowed = expected | ({"k"} if component == "retrieval" else set())
        if not isinstance(specification, dict) or not expected <= set(specification) or set(specification) - allowed:
            raise ValueError(f"Invalid input specification for {component}")
        if component == "runtime":
            results[component] = summarize_runtime(read_input(component, "attempts", specification["attempts"]))
        else:
            cases = read_input(component, "cases", specification["cases"])
            predictions = read_input(component, "predictions", specification["predictions"])
            arguments = {"k": specification.get("k", 5)} if component == "retrieval" else {}
            results[component] = SCORERS[component](cases, predictions, **arguments)
    return {"schema_version": 1, "config_sha256": hashlib.sha256(config_bytes).hexdigest(),
            "inputs": provenance, "results": results,
            "components_not_supplied": [name for name in COMPONENTS if name not in results],
            "notice": "Scores evaluate supplied exports; review identity, split independence, and model provenance are not verified."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = run_benchmark(args.config)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)


if __name__ == "__main__":
    main()
