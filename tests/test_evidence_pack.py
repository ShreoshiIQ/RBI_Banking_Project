import pytest

from regintel.evidence.pack import LAYOUT, build_pack, line
from regintel.evidence.pack_eval import evaluate, extract_records
from regintel.evidence.parsers import parse_document


@pytest.fixture(scope="module")
def pack():
    return build_pack(42)


def test_pack_is_deterministic_and_stratified(pack):
    _, truth = pack
    _, again_truth = build_pack(42)
    assert truth["file_sha256"] == again_truth["file_sha256"]
    assert len(truth["register_mismatches"]) == 2
    for name, ids in truth["layout"].items():
        kinds = {d for i in ids for d in truth["defects"].get(i, [])}
        assert kinds == {"overdue_review", "missing_signoff"} or len(ids) < 3, name


def test_native_formats_extract_with_locations(pack):
    files, truth = pack
    for name in ("access-reviews.csv", "access-reviews.xlsx", "access-reviews-native.pdf"):
        records = extract_records(parse_document(files[name], name))
        assert [r["record_id"] for r in records] == truth["layout"][name]
        assert all(r["transcription_verified"] and r["location"] for r in records)


class TruthfulOCR:
    """Returns the exact rendered lines, as a perfect OCR engine would."""
    model = "fake-perfect"

    def __init__(self, truth):
        self.texts = iter([
            "\n".join(line(r) for r in truth["records"] if r["record_id"] in truth["layout"][name])
            for name in LAYOUT if name.endswith((".pdf", ".png", ".jpg")) and name != "access-reviews-native.pdf"
        ])

    def __call__(self, payload, mime_type):
        return next(self.texts)


class CorruptingOCR(TruthfulOCR):
    """Misreads one date per image, as a weak OCR engine might."""
    model = "fake-corrupting"

    def __call__(self, payload, mime_type):
        text = next(self.texts).splitlines()
        text[0] = text[0].replace("2026-0", "2025-0", 1)
        return "\n".join(text)


def test_without_ocr_images_are_unread_not_guessed(pack):
    files, truth = pack
    result = evaluate(files, truth)
    assert result["silent_errors"] == []
    assert result["per_file"]["access-reviews-photo.png"]["method"] == "ocr_not_run"
    assert result["decisions"]["not_extracted"] == 12


def test_perfect_ocr_is_corroborated_and_mismatches_are_routed(pack):
    files, truth = pack
    result = evaluate(files, truth, ocr=TruthfulOCR(truth))
    assert result["silent_errors"] == []
    assert result["register_mismatch_detection"]["recall"] == 1.0
    routed = {q["record_id"] for q in result["human_queue"]}
    image_ids = {i for n in LAYOUT if "native" not in n and n.endswith((".pdf", ".png", ".jpg")) for i in truth["layout"][n]}
    assert routed == set(truth["register_mismatches"]) & image_ids
    assert result["defect_detection_if_ocr_trusted_blindly"]["recall"] == 1.0


def test_ocr_misreads_are_routed_to_humans_not_accepted(pack):
    files, truth = pack
    result = evaluate(files, truth, ocr=CorruptingOCR(truth))
    errors = [e for name, f in result["per_file"].items() if f["method"] == "ocr" for e in f["field_errors"]]
    assert len(errors) == 3
    assert result["silent_errors"] == []  # every misread disagreed with the register
    assert {e["record_id"] for e in errors} <= {q["record_id"] for q in result["human_queue"]}
    assert result["defect_detection_if_ocr_trusted_blindly"]["false_positives"] >= 1
