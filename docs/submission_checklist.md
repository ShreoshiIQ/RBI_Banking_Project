# Submission readiness checklist

Generate an artifact identity snapshot with
`uv run python scripts/build_submission_manifest.py`.
The manifest records hashes of the wheel, audit outputs, build configuration,
and documentation, along with the audited image ID. It excludes environment
files and does not bundle source datasets. Output creation is exclusive; use
`--output another_manifest.json` for a later snapshot. Hashes do not establish
legal applicability, benchmark quality, or a complete security review.

Fresh-schema migration verification passed through `ac89bf0264c5` in a generated
schema inside the dedicated PostgreSQL test database: 14 tables, including
Alembic's version table. The vector extension was enabled as a prerequisite.
The generated schema was removed afterward. This verifies migration execution
on empty tables; it does not establish a fresh-machine or complete container
deployment. Application database schema and records were not changed.

This checklist distinguishes implementation evidence from unfinished validation.
It is not a compliance certification.

| Area | Current evidence | Remaining work |
| --- | --- | --- |
| Authentication and reviews | Argon2, JWT, role checks, atomic review history, isolated regression coverage | Final security review and genuine officer decisions where appropriate |
| Regulatory dataset | Source manifests, hashes, extraction previews, traceability checks, withdrawn-source detection | Reviewed applicability, validated obligation catalog, complete reference annotations |
| Synthetic policies | 20 draft policies and 100 draft scenarios | Human review and independent test splits |
| Change intelligence | Comparison, hypothetical simulation, lexical impact shortlist, authenticated simulation API | Reviewed real-version amendment examples and confirmed affected controls |
| Operations | Request IDs, safe request logging, readiness, retry policy, read-only audit checker | Full operational/security review |
| Evaluation | Hybrid retrieval P@5 0.733 and MRR@10 1.000 on AI-labelled, team-accepted relevance (6 queries × 500 candidates); evidence pack 0 wrong values accepted without review in 240 records, OCR field accuracy 94.4%; 20/20 release gates | Human review of relevance labels; larger query set |
| Web app | React app at `/app` (overview, gap reports with officer review, monitor, cross-regulation, evidence), checked in headless Edge in light, dark and phone width; older `/dashboard` retained | Persisted ingestion jobs, automated browser tests, screen-reader checks |
| Packaging | Non-root API image with a Node build stage, Kubernetes manifests, CI (tests, migration round trip, gates, frontend build, manifest validation, image scan); application database migrated to head `d190f0030001` | Local build of the image with the React stage; non-owner app role for enforced tenant isolation |
| Documentation | Setup, environment template, architecture, demo walkthrough, evaluation status | Final walkthrough rehearsal and submission artifact review |

Do not represent draft scenarios as ground truth, toy test scores as project
metrics, lexical matches as confirmed gaps, or pending reports as approved.
The database audit found one report and zero reviews at verification time;
that snapshot does not replace a human evidence review.

Before submission, retain source versions and citations, confirm no secrets are
included, review generated artifacts, run the isolated regression command below,
and document any excluded checks. Never reset application data for a demo.

```powershell
$env:TEST_DATABASE_URL = ''
uv run pytest tests -q -p no:cacheprovider --ignore=tests/test_obligation_db_integration.py
```

This command excludes the application-database integration test and skips the
opt-in PostgreSQL concurrency check. Run concurrency tests only against a
dedicated test database. It does not include root-level or package-local tests
outside `tests/`, and it does not establish live Gemini or model-download behavior.

Latest full result (October 11, 2026): **496 passed, 10 skipped** with `uv run pytest -q`, **7 passed** Node client checks, and 20/20 gates.

Earlier isolated regression result: **361 passed, 1 skipped**, plus **4 passed**
Node client checks (subsequently expanded to **6 passed**). The skipped check
requires a dedicated PostgreSQL concurrency-test database; the application-data
integration test was excluded explicitly. Two outdated multi-section workflow
fixtures were updated to use the current dictionary result contract. Cache-hit
citation reuse and evidence-rejection routing are now asserted directly.

Read-only PostgreSQL verification of the catalog and mapping query functions
found one persisted source version, 312 obligations, and six latest-policy
sections. One sampled obligation returned three BM25 candidate matches. These
are inventory and query checks, not extraction or mapping quality metrics.
The transaction was explicitly read-only. Separate browser verification used
an isolated synthetic database: viewer/officer login, report selection,
rejection, refreshed audit history, and sign-out passed. Login keyboard focus
and layout checks at five widths also passed; see `dashboard.md` for scope.

The PostgreSQL concurrent-review test was subsequently rerun separately against
the previously provisioned dedicated test database and passed. It confirmed one
winning terminal decision and exactly one audit row; its generated schema was
removed by the test. Application reports were not used or changed.
