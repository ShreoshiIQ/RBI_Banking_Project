# Demo walkthrough

A five-to-seven minute demo of the agent through the React web app. Use the
fictional commercial-bank scope in `data/metadata/demo_institution_profile.json`.
Policies and evidence are synthetic demonstration data.

## Before the demo

```powershell
uv run uvicorn regintel.api.app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/app/` and sign in with a compliance-officer
account (create one with `uv run python scripts/create_dev_user.py`). Confirm
`/ready` returns 200. If `/app/` returns 404, the web app is not built; run `npm ci` and
`npm run build` in `frontend/`.

## Script

1. **Overview (1 min).** The problem: RBI and SEBI circulars change faster than
   a compliance team can map them to internal policy. Point to report and review
   counts, the evidence-pack result (0 wrong values accepted without review in
   240 records) and retrieval quality by method (hybrid precision@5 0.733).
   Say that the retrieval labels are AI-written and team-accepted, not
   human-reviewed.
2. **Gap report (2 min).** Open a report. Findings cite the RBI clause and the
   policy passage they were matched against. The Remediation tab shows the risk
   score with its factors, applicability status and a drafted remediation plan.
   The agent runs intake → applicability → prioritise → remediate → route →
   assemble; LLM drafts are validated against the source text, retried, and fall
   back to a template. Show that approve/reject needs a comment and a
   confirmation step, and that History is the audit trail. Do not submit a
   decision on a real report for the demo.
3. **Regulatory monitor (1 min).** The watcher polls the RBI notification feed,
   classifies each notification, hints at applicability and runs clause
   comparison when a tracked direction changes. Applicability is "presumed"
   until an officer decides. RBI's bot protection can block the feed; the
   watcher detects that rather than reporting false removals.
4. **Cross-regulation (1 min).** Obligation families group related RBI and SEBI
   provisions. Contradiction candidates are shown side by side for legal review;
   they are candidates, not findings. Use the compare tool on two provisions.
5. **Evidence (1 min).** Native and OCR extraction from scanned, photographed
   and low-resolution evidence. Values the OCR cannot corroborate are routed to
   human verification instead of being accepted silently.
6. **Production readiness (30 s).** Argon2 + JWT or OIDC sign-in, role checks,
   PostgreSQL row-level tenant isolation, Kubernetes manifests, and CI with 20
   evaluation gates that block a release on quality regressions.

## If asked

- *How do you know it does not hallucinate?* Remediation drafts may cite only
  the policy sections in the finding, and any quantity they state (amounts,
  periods, deadlines) must appear in the source text. Failing drafts are retried
  with the reasons and then replaced with a template. Evidence values without corroboration go
  to a human.
- *What is measured?* See the results table in the README and
  [relevance review](relevance_review.md). Scores are on six queries over 500
  candidates and synthetic evidence; they are indicative, not a benchmark.
- *What is not done?* Human review of relevance labels, real officer
  applicability decisions, an ingestion job UI, and an external security review.

Run the read-only audit check if asked about data integrity:

```powershell
uv run python -m regintel.reporting.audit_consistency
```

The older [dashboard](dashboard.md) at `/dashboard` and the API documentation at
`/docs` remain available for endpoints the web app does not cover, such as
hypothetical change simulation.
