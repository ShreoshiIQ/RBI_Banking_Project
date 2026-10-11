"""Authenticated, read-only views of persisted ingestion and obligations."""

from dataclasses import asdict
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from regintel.api.dependencies import get_db
from regintel.api.routes.auth import get_current_user
from regintel.mapping.bm25_retriever import BM25PolicyRetriever
from regintel.mapping.keyword_matcher import tokenize
from regintel.mapping.run_policy_mapping import load_policy_sections
from regintel.models.clause_candidate import RegulatoryClauseCandidate as Clause
from regintel.models.obligation import RegulatoryObligation as Obligation
from regintel.models.regulation import RegulatoryDocument as Document
from regintel.models.regulation import RegulatoryDocumentVersion as Version

router = APIRouter(prefix="/catalog", tags=["Regulatory catalog"], dependencies=[Depends(get_current_user)])
Db = Annotated[Session, Depends(get_db)]


@router.get("/obligations/{obligation_id}/policy-matches")
def policy_matches(obligation_id: UUID, db: Db, top_k: int = Query(3, ge=1, le=10)):
    obligation = db.get(Obligation, obligation_id)
    if obligation is None:
        raise HTTPException(status_code=404, detail="Obligation not found")
    sections = load_policy_sections(db)
    if len(sections) > 1000:
        raise HTTPException(status_code=409, detail="Policy corpus exceeds the local mapping preview limit")
    searchable = [section for section in sections if tokenize(section["section_title"] + " " + section["section_text"])]
    matches = BM25PolicyRetriever(searchable).search(obligation.evidence_quote, top_k=top_k)
    metadata = {str(section["id"]): section for section in sections}
    return {"obligation_id": obligation.id, "method": "bm25", "sections_considered": len(sections),
            "notice": "Lexical candidates from the latest ingested policy versions; scores are not compliance determinations. Draft files are excluded.",
            "matches": [asdict(match) | {"policy_code": metadata[match.policy_section_id]["policy_code"]} for match in matches]}


@router.get("/versions")
def versions(db: Db, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    clause_count = select(func.count()).select_from(Clause).where(Clause.version_id == Version.id).scalar_subquery()
    obligation_count = select(func.count()).select_from(Obligation).where(Obligation.document_version_id == Version.id).scalar_subquery()
    rows = db.execute(select(Version, Document, clause_count, obligation_count).join(Document, Version.document_id == Document.id)
                      .order_by(Version.retrieved_at.desc(), Version.id).limit(limit).offset(offset)).all()
    return {"total": db.scalar(select(func.count()).select_from(Version)) or 0, "limit": limit, "offset": offset,
            "notice": "Persisted counts are ingestion progress, not validated applicability or extraction quality. File-only previews are excluded.",
            "items": [{"version_id": version.id, "document_id": document.id, "title": document.title,
                       "source_url": document.source_url, "content_hash": version.content_hash,
                       "effective_date": version.effective_date, "retrieved_at": version.retrieved_at,
                       "clauses": clauses, "obligations": obligations}
                      for version, document, clauses, obligations in rows]}


@router.get("/obligations")
def obligations(db: Db, version_id: UUID | None = None,
                review_status: Literal["pending", "approved", "rejected"] | None = None,
                limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    filters = []
    if version_id is not None:
        filters.append(Obligation.document_version_id == version_id)
    if review_status is not None:
        filters.append(Obligation.review_status == review_status)
    rows = db.execute(select(Obligation, Clause, Version).join(Clause, Obligation.source_clause_id == Clause.id)
                      .join(Version, Obligation.document_version_id == Version.id).where(*filters)
                      .order_by(Obligation.clause_number, Obligation.id).limit(limit).offset(offset)).all()
    return {"total": db.scalar(select(func.count()).select_from(Obligation).where(*filters)) or 0,
            "limit": limit, "offset": offset,
            "items": [{"id": obligation.id, "version_id": version.id, "content_hash": version.content_hash,
                       "source_clause_id": clause.id, "clause_number": obligation.clause_number,
                       "start_page": clause.start_page, "end_page": clause.end_page,
                       "clause_status": clause.status, "actor": obligation.actor, "action": obligation.action,
                       "evidence_quote": obligation.evidence_quote, "review_status": obligation.review_status,
                       "quality_status": obligation.quality_status}
                      for obligation, clause, version in rows]}
