# Web app (React)

`frontend/` is a React 18 + TypeScript app built with Vite. FastAPI serves the
production build at `/app` (hash routes, for example `/app/#/reports`). The older
`/dashboard` page is unchanged.

| Page | What it shows | API |
| --- | --- | --- |
| Overview | Report and review counts, silent evidence errors, OCR accuracy, retrieval quality by method, latest reports and RBI notifications | `gap-reports`, `insights/summary`, `insights/watch-events` |
| Gap reports | Filterable list; detail with findings and cited policy quotes, a template remediation plan with risk and applicability, review history, and officer approve/reject with a confirmation step | `gap-reports/*`, `gap-reports/{id}/review` |
| Regulatory monitor | Watcher notifications with classification, applicability hint and impact status; applicability of every registered source | `insights/watch-events`, `insights/applicability` |
| Cross-regulation | Family and candidate counts, contradiction candidates with both provisions, expandable obligation families, and a two-provision compare tool | `insights/cross-regulation`, `cross-regulation/compare` |
| Evidence | Evidence-pack results (silent errors, defect detection, register mismatches) and an upload preview with source locations | `insights/summary`, `ingestion/evidence-preview` |

Sign-in uses the existing `/api/v1/auth/login`. The bearer token is kept in
`sessionStorage` and cleared on 401 or sign-out. Only compliance officers see
the approve/reject controls; the API enforces the same rule.

`/api/v1/insights/*` is a new read-only router over result files under the data
root (`DATA_ROOT`, default the working directory). A missing file returns
`{"available": false, "reason": ...}`, so the app degrades instead of failing
when the data volume is absent.

Charts follow the validated three-slot categorical palette (light and dark).
Each chart has a per-bar tooltip, a legend for multiple series, value labels
where bars have room, and a table view. Status pills always pair colour with a
text label.

## Develop and build

```powershell
cd frontend
npm ci
npm run dev        # http://127.0.0.1:5173/app/ , proxies /api to the API on :8000
npm run build      # type-checks, then writes src/regintel/api/webapp (served at /app)
```

The build output is not committed. The Docker image builds it in a Node stage,
and CI type-checks and builds it in its own job.

Checked on October 11, 2026 in headless Edge against the running API (sign-in
stubbed as a demo officer, read-only): all six views render with live data, in
light and dark modes and at 400 px phone width, with no errors and no horizontal
overflow. No review was submitted.
