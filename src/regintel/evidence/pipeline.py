"""Append-only evidence persistence, retrieval, and existing workflow adapter."""

import hashlib
import json
import math

from sqlalchemy import select

from regintel.foundation.registry import PROFILE_ID
from regintel.mapping.bm25_retriever import BM25PolicyRetriever
from regintel.mapping.keyword_matcher import tokenize
from regintel.models.evidence import (
    EvidenceChunk,
    EvidenceDocument,
    EvidenceEmbedding,
    EvidenceExtractionRun,
)


def persist_evidence(session, extraction, filename, *, synthetic):
    if synthetic is not True or extraction.get("review_status") != "pending":
        raise ValueError(
            "Only pending, explicitly synthetic demonstration evidence is permitted"
        )
    existing = session.scalar(
        select(EvidenceDocument).where(
            EvidenceDocument.file_sha256 == extraction["file_sha256"]
        )
    )
    document = existing or EvidenceDocument(
        file_sha256=extraction["file_sha256"],
        filename=filename,
        profile_id=PROFILE_ID,
        synthetic=True,
        extraction=extraction,
    )
    if existing is None:
        session.add(document)
        session.flush()
    run_id = hashlib.sha256(
        json.dumps(extraction, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    run = session.get(EvidenceExtractionRun, run_id)
    if run is not None:
        return {
            "document_id": str(document.id),
            "inserted": False,
            "extraction_run_id": run_id,
            "extraction_run_inserted": False,
        }
    session.add(
        EvidenceExtractionRun(id=run_id, document_id=document.id, extraction=extraction)
    )
    for chunk in extraction["chunks"]:
        stored = session.get(EvidenceChunk, chunk["chunk_id"])
        if stored is not None:
            if stored.document_id != document.id or any(
                getattr(stored, field) != chunk[field]
                for field in ("text", "location", "method", "transcription_verified")
            ):
                raise ValueError(
                    "Existing evidence chunk conflict; nothing overwritten"
                )
            continue
        session.add(
            EvidenceChunk(
                id=chunk["chunk_id"],
                document_id=document.id,
                text=chunk["text"],
                location=chunk["location"],
                method=chunk["method"],
                transcription_verified=chunk["transcription_verified"],
            )
        )
    session.flush()
    return {
        "document_id": str(document.id),
        "inserted": existing is None,
        "extraction_run_id": run_id,
        "extraction_run_inserted": True,
    }


def index_evidence(session, *, embed, model):
    inserted = 0
    for chunk in session.scalars(
        select(EvidenceChunk)
        .join(EvidenceDocument)
        .where(EvidenceDocument.profile_id == PROFILE_ID)
    ).all():
        if session.get(EvidenceEmbedding, (chunk.id, model)) is not None:
            continue
        vector = embed(chunk.text)
        if (
            len(vector) != 384
            or any(not math.isfinite(v) for v in vector)
            or not any(vector)
        ):
            raise ValueError("Invalid evidence embedding")
        session.add(EvidenceEmbedding(chunk_id=chunk.id, model=model, embedding=vector))
        inserted += 1
    session.flush()
    return inserted


def retrieve_evidence(
    session, query, *, method="bm25", embed=None, model=None, top_k=5
):
    if (
        method not in ("bm25", "vector", "hybrid")
        or not 1 <= top_k <= 20
        or not query.strip()
    ):
        raise ValueError("Invalid evidence retrieval configuration")
    chunks = session.scalars(
        select(EvidenceChunk)
        .join(EvidenceDocument)
        .where(EvidenceDocument.profile_id == PROFILE_ID)
        .limit(1001)
    ).all()
    if len(chunks) > 1000:
        raise ValueError(
            "Demo evidence corpus limit exceeded; use the scalability pipeline"
        )
    by_id = {c.id: c for c in chunks}
    rankings = []
    if method in ("bm25", "hybrid"):
        sections = [
            {
                "id": c.id,
                "section_number": c.id,
                "section_title": "Synthetic evidence",
                "section_text": c.text,
            }
            for c in chunks
            if tokenize(c.text)
        ]
        rankings.append(
            [
                m.policy_section_id
                for m in BM25PolicyRetriever(sections).search(
                    query, top_k=max(top_k, 20)
                )
            ]
        )
    if method in ("vector", "hybrid"):
        if embed is None or not model:
            raise ValueError("Explicit embedding function and model required")
        vector = embed(query)
        if (
            len(vector) != 384
            or any(not math.isfinite(v) for v in vector)
            or not any(vector)
        ):
            raise ValueError("Invalid query embedding")
        distance = EvidenceEmbedding.embedding.cosine_distance(vector)
        ids = session.scalars(
            select(EvidenceEmbedding.chunk_id)
            .join(EvidenceChunk)
            .join(EvidenceDocument)
            .where(
                EvidenceDocument.profile_id == PROFILE_ID,
                EvidenceEmbedding.model == model,
            )
            .order_by(distance, EvidenceEmbedding.chunk_id)
            .limit(max(top_k, 20))
        ).all()
        rankings.append(ids)
    scores = {}
    for ranked in rankings:
        for rank, identifier in enumerate(ranked, 1):
            scores[identifier] = scores.get(identifier, 0) + 1 / (60 + rank)
    return [
        {
            "chunk_id": identifier,
            "text": by_id[identifier].text,
            "location": by_id[identifier].location,
            "transcription_verified": by_id[identifier].transcription_verified,
            "score": scores[identifier],
            "document_id": str(by_id[identifier].document_id),
        }
        for identifier in sorted(scores, key=lambda i: (-scores[i], i))[:top_k]
    ]


def assess_match(workflow, *, obligation_id, obligation_text, match):
    if match["transcription_verified"] is not True:
        return {
            "classification": "insufficient_evidence",
            "evidence_reference": match["location"],
            "notice": "OCR transcription requires human verification before assessment",
        }
    result = workflow.invoke(
        obligation_id=obligation_id,
        obligation_text=obligation_text,
        policy_section_id=match["chunk_id"],
        policy_text=match["text"],
    )
    return {
        "workflow": result,
        "evidence_reference": {
            "chunk_id": match["chunk_id"],
            "document_id": match["document_id"],
            "location": match["location"],
        },
        "notice": "Existing workflow checks document design; it does not establish operating effectiveness.",
    }
