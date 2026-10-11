# Regulatory Compliance AI

A local regulatory assessment workspace for the ET AI Hackathon. It combines
RBI source processing, obligation extraction, policy retrieval, explainable gap
reports, hypothetical change analysis, and authenticated human review.
Assessments are evidence for human review, not legal compliance certifications.

## Local setup

Use Python 3.12, uv, and PostgreSQL 16 with pgvector. Follow
[Windows setup](docs/local_setup.md) for environment configuration, database
initialization, migrations, and account creation. Preserve existing data and
configuration. `.env.example` contains placeholders; never commit real secrets.

From the project root, after setup:

```powershell
uv run uvicorn regintel.api.app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/app/` for the [React web app](docs/frontend.md)
(build it first with `npm ci` and `npm run build` in `frontend/`), or
`http://127.0.0.1:8000/dashboard` for the
[local dashboard](docs/dashboard.md), or `/docs` for interactive API documentation.
The dashboard supports reports, evidence, audit history, officer decisions,
regulatory catalog browsing, BM25 mapping previews, hypothetical simulation,
and imported benchmark results. Ingestion remains a local pipeline operation.

## Authentication and review

Provision local users with `uv run python scripts/create_dev_user.py`.
Passwords are hashed with Argon2 using `UserRecord` and `hash_password`.
Public registration is not exposed. Set a random `JWT_SECRET_KEY` of at least
32 characters; `ACCESS_TOKEN_EXPIRE_MINUTES` defaults to 30.

`POST /api/v1/auth/login` accepts form fields `username` and `password`.
Use its bearer token for protected API calls. `GET /api/v1/auth/me` returns
identity and role without the password hash.

Viewers, admins, and compliance officers can read reports and history. Only
compliance officers can approve or reject pending reports through
`POST /api/v1/gap-reports/{report_id}/review`. Reviewer identity comes from the
account. Report state and audit history commit atomically with row locking.
Do not approve actual reports merely to demonstrate the interface.

## Sources, changes, and evaluation

[Dataset validation](docs/dataset_validation.md) records extraction traceability
and outstanding reviews. [Regulatory expansion](docs/regulatory_expansion.md)
explains source versions, withdrawn material, and file-only previews.
[Synthetic policies](docs/synthetic_dataset.md) remain demonstration evidence.

[Change intelligence](docs/change_intelligence.md) compares clauses and produces
lexical impact candidates. Dashboard simulation uses an authenticated API and
clearly hypothetical inputs; candidate matches do not establish control failures.

[Risk prioritisation and remediation](docs/remediation.md) scores gaps with a
versioned, explainable model and drafts remediation for officer review, with
validated LLM drafts, retries, and template fallback.

[Cross-regulation intelligence](docs/cross_regulation.md) groups related RBI
and SEBI provisions into obligation families and flags contradiction candidates
for legal review.

The [RBI notification watcher](docs/regulatory_watcher.md) polls the official
feed, triages applicability, and runs clause comparison and policy impact
shortlists when a tracked direction changes.

The [multimodal evidence pack](docs/evidence_pack_v2.md) measures extraction,
OCR corroboration, and defect detection on seeded synthetic evidence with
planted defects (six seeds, live OCR: 0 wrong values accepted without review).

[Production controls](docs/production.md) cover applicability enforcement,
PostgreSQL row-level tenant isolation, OIDC single sign-on, Kubernetes manifests,
and CI with evaluation gates.

The [benchmark runner](docs/benchmark_runner.md) scores supplied reviewed labels
and prediction exports across extraction, retrieval, citations, mapping, gap
classification, and runtime. It records input hashes and omitted components.
The [evaluation report](docs/evaluation_report.md) lists missing inputs.
No empirical project benchmark scores are available; draft scenarios are unreviewed.

## Operations and packaging

`/health` checks process liveness. `/ready` runs `SELECT 1` and returns 503 on
a database query failure; it does not validate migrations or dataset quality.
Request logs contain route templates, status, duration, and correlation IDs.
Bodies, tokens, query strings, and exception messages are excluded. Unhandled
request errors return a generic 500 with a request ID. Third-party and Uvicorn
logs retain their own settings. API responses use `Cache-Control: no-store`.

Gemini verifiers share a 30-second per-attempt timeout and at most three total
SDK attempts with exponential backoff and jitter for HTTP 408, 429, 500, 502,
503, and 504. Invalid structured responses are not retried by the application.
Injected clients retain their transport configuration. Retries may consume quota.

Run the read-only history checker with:

```powershell
uv run python -m regintel.reporting.audit_consistency
```

It uses a consistent PostgreSQL snapshot, emits IDs and issue types without
review comments, and exits with code 1 on inconsistency. It does not repair data.

[Docker instructions](docs/docker_api.md) describe the non-root API image.
Compose currently supplies PostgreSQL only. The local image was refreshed with
the latest wheel and its dashboard was smoke-tested. Locked Linux dependencies and
fresh-database end-to-end deployment remain unfinished.

## Verification and submission

Run isolated regressions without application-data integration:

```powershell
$env:TEST_DATABASE_URL = ''
uv run pytest tests -q -p no:cacheprovider --ignore=tests/test_obligation_db_integration.py
node --test tests/dashboard_client.test.cjs
```

Latest results: 361 Python tests passed, one skipped, and four Node tests passed.
The opt-in concurrency check requires a dedicated PostgreSQL test database and
creates/removes only a uniquely named schema. Root-level and package-local tests
outside `tests/` are not included. Browser interaction testing remains pending.

See the [architecture](docs/architecture.md), [demo walkthrough](docs/demo_walkthrough.md),
the [focused security review](docs/security_review.md),
and [submission checklist](docs/submission_checklist.md). Dataset review,
empirical benchmarks, ingestion job UI, full browser verification, and final
security/deployment review remain unfinished.
