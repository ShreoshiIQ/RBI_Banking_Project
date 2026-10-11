"""Explicit extraction/persistence/indexing; no model calls unless selected."""

import argparse
import json
import os
from pathlib import Path

from regintel.evidence.parsers import MAX_BYTES, parse_document
from regintel.evidence.pipeline import index_evidence, persist_evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--live-ocr", action="store_true")
    parser.add_argument("--ocr-model")
    parser.add_argument("--persist", action="store_true")
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--index", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Choose a new output snapshot")
    if args.index and not args.persist:
        parser.error("--index requires --persist")
    if args.persist and not args.synthetic:
        parser.error("Only explicitly synthetic evidence may be persisted")
    if args.file.stat().st_size > MAX_BYTES:
        raise ValueError("Evidence file exceeds 5 MB")
    ocr = None
    if args.live_ocr:
        from dotenv import load_dotenv

        load_dotenv(Path.cwd() / ".env")
        from regintel.evidence.ocr import GeminiOCR

        ocr = GeminiOCR(
            api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
            model=args.ocr_model,
        )
    try:
        result = parse_document(args.file.read_bytes(), args.file.name, ocr=ocr)
    finally:
        if ocr is not None:
            ocr.client.close()
    if args.persist:
        from regintel.db.session import SessionLocal

        with SessionLocal.begin() as session:
            result["persistence"] = persist_evidence(
                session, result.copy(), args.file.name, synthetic=True
            )
            if args.index:
                from regintel.mapping.embedding_service import MODEL_NAME, embed_text

                result["embeddings_inserted"] = index_evidence(
                    session, embed=embed_text, model=MODEL_NAME
                )
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)


if __name__ == "__main__":
    main()
