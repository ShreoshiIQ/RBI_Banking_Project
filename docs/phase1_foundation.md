# Phase 1 regulatory data foundation

This implementation preserves the single-bank demonstration architecture.
It does not establish multi-tenant isolation, legal applicability, operating
effectiveness, or D3/F3 reliability. This document records the Phase 1 snapshot;
subsequent evidence implementation is described in `phase2_evidence.md`.

## Implemented

- Reproducible file inventory with input hashes and optional PostgreSQL
  repeatable-read, read-only inventory. File-only candidates and drafts are
  reported separately from persisted data. Inventory exports omit credentials.
- An offline source/version/applicability registry binds ten verified local
  RBI PDF hashes to one fictional commercial-bank profile. Four snapshots
  with withdrawal markers remain historical. The other six have source-status
  verification pending. All applicability decisions remain pending, and none
  is eligible for the current approved catalog. Absence of a watermark does
  not prove current applicability. The registry is not a runtime filter.
- A conservative candidate review groups exact normalized identities within
  a source version and clause, including type, actor, action, condition, and
  evidence. Repeated evidence alone is not automatically merged. All 312
  original KYC candidates remain intact and pending: zero exact duplicates,
  zero human approvals. Actor, historical-text, and amendment warnings remain.
- All 20 existing synthetic drafts are prevalidated against their byte hashes,
  synthetic labels, pending status, numbered sections, and exact topic-anchor
  candidate/page provenance before transactional ingestion. Topic links do
  not assert validated regulatory mappings.
- An additive `policy_version_provenance` table records synthetic status,
  profile identifier, topic, variant, source anchor, and file hash for each
  version. Database titles explicitly start with `[SYNTHETIC DRAFT]`.
  Existing-version conflicts fail without overwrite; reruns skip matching
  versions after checking provenance and section contents.

## Migration and application data safety

Migration `d190f0010001` follows `ac89bf0264c5`. Its upgrade creates only the
provenance table, with a restrictive foreign key and pending/synthetic checks.
Existing application tables are not altered, reset, or rewritten. Automatic
downgrade is disabled to prevent accidental provenance deletion.

The SQL was inspected before application. An isolated generated schema in
the dedicated PostgreSQL test database verified migration execution, ingestion,
idempotence, and preservation of an existing fixture; only that schema was
removed afterward. The application migration and ingestion ran in one guarded
transaction with lock/statement timeouts and an expected revision check.
Hashed row comparisons verified preservation of every pre-existing application
row. Regulatory, report, review, user, embedding, and cache rows were unchanged.

Actual ingestion added 20 documents, 20 versions, 60 sections, and 20 provenance
rows. A second pass inserted nothing and skipped 20 versions. The database now
contains 21 policies, 21 versions, and 66 sections. Embeddings remain six;
new synthetic sections have not been vector-indexed. All 312 persisted
regulatory obligations remain pending, with no regulatory ingestion changes.

The transaction receipt is
`data/processed/validation/phase1_database_change.json`. It contains counts,
not original record contents. Existing source and dataset files were not
overwritten. New output snapshots use exclusive file creation.

## Reproduction

Run from the project root with a new output filename for each snapshot:

```powershell
uv run python -m regintel.foundation.cli inventory --database --output inventory_snapshot.json
uv run python -m regintel.foundation.cli registry --output registry_snapshot.json
uv run python -m regintel.foundation.cli candidates --output candidate_review_snapshot.json
uv run python -m regintel.foundation.cli policies --output policy_preflight_snapshot.json
```

The first command only reads PostgreSQL. The other three commands read local
inputs. To append validated drafts after the additive migration:

```powershell
uv run alembic upgrade d190f0010001
uv run python -m regintel.foundation.cli policies --database --output policy_ingestion_receipt.json
```

The registry and candidate review are engineering checks. They do not sign
human review decisions. The 838 offline expansion candidates remain separate
from the 312 persisted candidates; their combined 1,150 rows are not claimed
as distinct validated coverage.

## Verification and remaining work

Actual Phase 1 results:

- Isolated regression suite: **373 passed, 2 skipped**. The application-data
  obligation integration test was excluded; both opt-in PostgreSQL tests
  were skipped in that run because no test URL was supplied.
- Foundation file/SQLite tests plus the separately enabled PostgreSQL
  migration/ingestion test: **13 passed** against the dedicated test database.
- Dashboard JavaScript regression checks: **6 passed**.
- Ruff checks on the new modules, migration, and tests: passed.
- Application before/after row-preservation checks: passed; idempotent second
  ingestion inserted zero records.

The final registry snapshot is `data/metadata/phase1_registry_verified.json`.
Inventory snapshots and the candidate review/preflight/transaction receipt
are in `data/processed/validation/phase1_*.json`. Snapshots describe the
database and files when exported, not future state.

Focused SQLite/file tests cover reproducibility, pending-state preservation,
deduplication, path containment, manifest tampering, transaction rollback,
idempotence, and preservation of an unrelated policy. The opt-in PostgreSQL
test in `tests/test_phase1_postgres.py` refuses a database name without
`test` and uses a uniquely generated schema.

Pending: human actor/applicability/atomicity decisions, semantic near-duplicate
review, live source-status verification, runtime applicability enforcement,
vector indexing of the new drafts, multi-tenant isolation, multimodal evidence,
and empirical benchmarks. No live Gemini calls or benchmark claims were made.
Any packaged wheel/image predating Phase 1 must be rebuilt before deployment.
