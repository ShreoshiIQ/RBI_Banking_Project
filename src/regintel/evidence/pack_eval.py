"""Measure multimodal evidence handling on the synthetic pack against its construction-time answer key.

Pipeline per file: parse (optional live OCR) -> extract records -> reconcile with the
bank's register -> accept native records and OCR records corroborated by the register;
route everything else to human verification -> run the access-review control test on
accepted records only.

Scores describe these synthetic fixtures, not real-bank OCR or detection accuracy.
"""

import argparse
import json
import re
from datetime import UTC, date, datetime
from pathlib import Path

from regintel.evidence.pack import (
    AS_OF,
    COLUMNS,
    THRESHOLD_DAYS,
    build_pack,
    defects,
    truth_json,
)
from regintel.evidence.parsers import parse_document

SEP = r"\s*[|¦Il!]\s*"
ROW = re.compile(r"(SYN\s*-?\s*A\s*\d{3})" + SEP + r"(\d{4}\s*-\s*\d{2}\s*-\s*\d{2})" + SEP + r"([^|\n]+?)" + SEP + r"(UNSIGNED|SIGNED)\b", re.IGNORECASE)
CELL = re.compile(r"([A-Z]+)(\d+)")


def _record(values: dict, location, method, verified) -> dict:
    return {"record_id": re.sub(r"\s|-", "", values["record_id"]).upper().replace("SYNA", "SYN-A"),
            "last_reviewed": re.sub(r"\s", "", values["last_reviewed"]), "reviewer": values["reviewer"].strip(),
            "signoff": values["signoff"].strip().upper(), "location": location, "method": method, "transcription_verified": verified}


def extract_records(parsed: dict) -> list[dict]:
    """Access-review rows from any parsed format, keeping each row's source location."""
    chunks, out = parsed["chunks"], []
    if parsed["format"] == "csv":
        header = json.loads(chunks[0]["text"]) if chunks else []
        for chunk in chunks[1:]:
            row = dict(zip(header, json.loads(chunk["text"])))
            if set(COLUMNS) <= set(row):
                out.append(_record(row, chunk["location"], chunk["method"], chunk["transcription_verified"]))
    elif parsed["format"] == "xlsx":
        rows = {}
        for chunk in chunks:
            col, num = CELL.match(chunk["location"]["cell_range"].split(":")[0]).groups()
            rows.setdefault(int(num), {})[col] = chunk
        header = None
        for num in sorted(rows):
            cells = rows[num]
            values = [cells[c]["text"].strip() for c in sorted(cells)]
            if values == COLUMNS:
                header = sorted(cells)
                continue
            if header and all(c in cells for c in header):
                row = {name: cells[c]["text"] for name, c in zip(COLUMNS, header)}
                location = {"kind": "xlsx", "sheet": cells[header[0]]["location"]["sheet"], "row": num}
                out.append(_record(row, location, "native", True))
    else:
        for chunk in chunks:
            for match in ROW.finditer(chunk["text"]):
                values = dict(zip(COLUMNS, match.groups()))
                out.append(_record(values, chunk["location"], chunk["method"], chunk["transcription_verified"]))
    return out


def design_threshold(parsed: dict) -> int | None:
    match = re.search(r"reviewed at least every (\d+) days", " ".join(c["text"] for c in parsed["chunks"]))
    return int(match.group(1)) if match else None


def _defects_of(record: dict) -> list[str]:
    try:
        date.fromisoformat(record["last_reviewed"])
    except ValueError:
        return ["unreadable_date"]
    return defects(record)


def _pr(predicted: set, actual: set) -> dict:
    tp = len(predicted & actual)
    return {"true_positives": tp, "false_positives": len(predicted - actual), "false_negatives": len(actual - predicted),
            "precision": round(tp / len(predicted), 4) if predicted else None,
            "recall": round(tp / len(actual), 4) if actual else None}


def evaluate(files: dict[str, bytes], truth: dict, *, ocr=None) -> dict:
    truth_by_id = {r["record_id"]: r for r in truth["records"]}
    register = {r["record_id"]: r for r in extract_records(parse_document(files[truth["register_file"]], truth["register_file"]))}
    design = parse_document(files[truth["design_file"]], truth["design_file"])
    per_file, accepted, all_extracted, routed = {}, [], [], []
    for name, expected_ids in truth["layout"].items():
        parsed = parse_document(files[name], name, ocr=ocr)
        records = extract_records(parsed)
        found = {r["record_id"]: r for r in records}
        hits = [found[i] for i in expected_ids if i in found]
        field_errors = [{"record_id": r["record_id"], "field": f, "extracted": r[f], "truth": truth_by_id[r["record_id"]][f]}
                        for r in hits for f in ("last_reviewed", "signoff") if r[f] != truth_by_id[r["record_id"]][f]]
        for record in records:
            if record["record_id"] not in expected_ids:
                continue
            reg = register.get(record["record_id"])
            agrees = reg is not None and all(reg[f] == record[f] for f in ("last_reviewed", "signoff"))
            record["register_agrees"] = agrees
            if record["transcription_verified"]:
                record["decision"] = "accepted_native"
            elif agrees:
                record["decision"] = "accepted_corroborated"
            else:
                record["decision"] = "human_verification"
            (routed if record["decision"] == "human_verification" else accepted).append(record)
            all_extracted.append(record)
        per_file[name] = {
            "format": parsed["format"],
            "method": "ocr" if any(not c["transcription_verified"] for c in parsed["chunks"]) else "ocr_not_run" if not parsed["chunks"] else "native",
            "ocr_required_unrun": any(w["reason"] == "ocr_required" for w in parsed["warnings"]),
            "expected_records": len(expected_ids), "records_found": len(hits),
            "record_recall": round(len(hits) / len(expected_ids), 4),
            "field_accuracy": round(1 - len(field_errors) / (2 * len(hits)), 4) if hits else None,
            "field_errors": field_errors,
            "unexpected_record_ids": sorted(set(found) - set(expected_ids)),
        }
    actual_defects = {(rid, d) for rid, ds in truth["defects"].items() for d in ds}
    accepted_defects = {(r["record_id"], d) for r in accepted for d in _defects_of(r)}
    blind_defects = {(r["record_id"], d) for r in all_extracted for d in _defects_of(r)}
    silent = [{"record_id": r["record_id"], "decision": r["decision"],
               "fields": [f for f in ("last_reviewed", "signoff") if r[f] != truth_by_id[r["record_id"]][f]]}
              for r in accepted if any(r[f] != truth_by_id[r["record_id"]][f] for f in ("last_reviewed", "signoff"))]
    flagged = {r["record_id"] for r in all_extracted if not r["register_agrees"]}
    covered = {r["record_id"] for r in accepted}
    return {
        "schema_version": 1, "generated_at": datetime.now(UTC).isoformat(), "synthetic": True,
        "ocr_model": getattr(ocr, "model", None), "as_of": AS_OF.isoformat(), "threshold_days": THRESHOLD_DAYS,
        "pack_sha256": truth["file_sha256"],
        "design_check": {"threshold_found": design_threshold(design), "threshold_truth": truth["threshold_days"]},
        "per_file": per_file,
        "decisions": {"accepted_native": sum(r["decision"] == "accepted_native" for r in accepted),
                      "accepted_corroborated": sum(r["decision"] == "accepted_corroborated" for r in accepted),
                      "human_verification": len(routed), "not_extracted": len(truth_by_id) - len(all_extracted)},
        "silent_errors": silent,
        "defect_detection_accepted_only": {**_pr(accepted_defects, actual_defects),
                                           "defects_on_records_awaiting_humans": len({d for d in actual_defects if d[0] not in covered})},
        "defect_detection_if_ocr_trusted_blindly": _pr(blind_defects, actual_defects),
        "register_mismatch_detection": _pr(flagged, set(truth["register_mismatches"])),
        "human_queue": [{"record_id": r["record_id"], "location": r["location"], "extracted": {f: r[f] for f in ("last_reviewed", "signoff")},
                         "register": {f: register[r["record_id"]][f] for f in ("last_reviewed", "signoff")} if r["record_id"] in register else None}
                        for r in routed],
        "notice": "Scores on a fictional synthetic pack with construction-time labels. Not real-bank OCR accuracy, control effectiveness, or certification.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--write-pack", type=Path, help="Also write the pack files and answer key to this new directory")
    parser.add_argument("--live-ocr", action="store_true", help="Transcribe image evidence with Gemini (GEMINI_API_KEY, GEMINI_MODEL)")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"Refusing to overwrite {args.output}")
    files, truth = build_pack(args.seed)
    if args.write_pack:
        args.write_pack.mkdir(parents=True, exist_ok=False)
        for name, data in files.items():
            (args.write_pack / name).write_bytes(data)
        (args.write_pack / "answer_key.json").write_text(truth_json(truth), encoding="utf-8")
    ocr = None
    if args.live_ocr:
        import os

        from dotenv import load_dotenv

        from regintel.evidence.ocr import GeminiOCR
        load_dotenv()
        ocr = GeminiOCR(api_key=os.getenv("GEMINI_API_KEY"), model=os.getenv("GEMINI_MODEL"))
    try:
        result = evaluate(files, truth, ocr=ocr)
    finally:
        if ocr is not None:
            ocr.client.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = {k: result[k] for k in ("decisions", "defect_detection_accepted_only", "defect_detection_if_ocr_trusted_blindly", "register_mismatch_detection")}
    summary["silent_errors"] = len(result["silent_errors"])
    summary["per_file"] = {n: {k: v[k] for k in ("method", "record_recall", "field_accuracy")} for n, v in result["per_file"].items()}
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
