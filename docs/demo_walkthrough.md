# Local demonstration walkthrough

Use the fictional commercial-bank scope in
`data/metadata/demo_institution_profile.json`. Treat synthetic policies as demo
evidence and pending extraction candidates as unreviewed.

## Start the API

From the project directory, use the existing configured environment and database:

```powershell
uv run uvicorn regintel.api.app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs`. Check `/health` and `/ready`; readiness checks
database connectivity, not data quality or migration completeness. If no local
account exists, run `uv run python scripts/create_dev_user.py` interactively.
Passwords are entered privately. Use a viewer account for read-only navigation.

## Show authenticated reports

Use the Swagger Authorize flow with the local username and password. Read
`GET /api/v1/auth/me`, `GET /api/v1/gap-reports`, then a report's detail and
`GET /api/v1/gap-reports/{report_id}/reviews`. Explain the evidence, assessment
status, and separate pending human-review status. Empty history is valid when
no decision has been recorded.

Do not approve a real pending report merely to demonstrate permissions. Show
the isolated RBAC and concurrent-review test results for transactional behavior.
A genuine decision requires an officer's examination of the report and evidence.
The admin role does not grant approval permission.

## Show change intelligence

Inspect `data/evaluation/change_demo/simulation_report.json` and its baseline,
proposal, and policy-section inputs. These fixtures are fictional. Explain
added, removed, and modified clauses and the affected-policy shortlist.
The authenticated `POST /api/v1/changes/simulate` endpoint provides the same
kind of hypothetical analysis using its documented request schema. Lexical
impact matches are review candidates, not confirmed control failures.

## Show dataset and evaluation evidence

Open [dataset validation](dataset_validation.md),
[regulatory expansion](regulatory_expansion.md), and
[evaluation status](evaluation_report.md). Show source hashes and traceable
citations, and explain why withdrawn sources and pending applicability decisions
cannot be represented as validated current requirements. The 100 synthetic
scenarios are drafts; no empirical project benchmark scores are available.

Run the read-only audit check if desired:

```powershell
uv run python -m regintel.reporting.audit_consistency
```

The local [dashboard](dashboard.md) at `/dashboard` provides report browsing,
evidence, and audit history. API documentation supports the remaining endpoints.
Day 29 dashboard coverage and final deployment verification remain unfinished.
