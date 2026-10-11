# Local compliance dashboard

The signed-out login page was rendered and visually inspected in installed
headless Edge. The desktop capture is readable; the narrow capture is clipped
and does not establish correct mobile layout. Screenshots are saved under
`data/processed/dashboard_qa/`. The check used dummy configuration and a temporary
loopback server, which was stopped afterward. Authenticated browser flows,
keyboard navigation, and complete responsive-workspace verification remain pending.

The PDF preview form calls authenticated `POST /api/v1/ingestion/preview`.
It accepts PDFs up to 5 MB and 150 pages, extracts at most one million text
characters, and displays the first 50 clause candidates with source hash and
page traceability. It reuses the numbered-chapter extractor and withdrawal-marker
check. Unsupported layouts or scanned PDFs can yield no clauses; no OCR occurs.
No database ingestion, approval, or application source-file persistence occurs.
Multipart handling may use framework-managed temporary upload files. Source
authenticity and applicability remain unverified.

The dashboard uses a same-origin content security policy that blocks inline
scripts, embedded objects, and framing. API responses use `Cache-Control:
no-store`, including authentication and error responses. Responses also disable
MIME sniffing and referrer disclosure. These browser controls complement backend
authorization; they do not replace it.

Client session checks run with `node --test tests/dashboard_client.test.cjs`.
They verify bearer-token use, sign-out on a current-session 401, and preservation
of a newer session when an older request returns late. These controlled Node
checks do not replace browser layout or complete interaction tests.

The regulatory catalog panel loads authenticated, read-only database views at
`GET /api/v1/catalog/versions` and `GET /api/v1/catalog/obligations`. It shows
persisted version hashes, clause/obligation counts, candidate quotations,
page ranges, quality flags, and review status with pagination. The obligations
endpoint supports version and review-status filters. File-only expansion
previews are excluded. These counts indicate stored ingestion progress, not
validated applicability; the dashboard does not start ingestion jobs.

Each obligation offers candidate policy retrieval through
`GET /api/v1/catalog/obligations/{obligation_id}/policy-matches`. This reuses
the existing BM25 retriever and latest-ingested-policy loader. Results show
policy codes, section text, matching terms, and scores. File-only drafts are
excluded; scores and missing matches do not establish compliance or gaps.
The local preview rejects corpora exceeding 1,000 loaded sections rather than
silently truncating them. It makes no Gemini calls and stores no mapping decisions.

For a fictional simulation, upload
`data/evaluation/change_demo/dashboard_scenario.json`. The five-to-ten-year
retention change is invented and does not represent an actual RBI amendment.
The uploaded scenario is sent to the simulation endpoint; results are displayed
without persisting an assessment or submitting a review decision.

The evaluation panel reads a unified benchmark runner report locally in the
browser. Metrics, omitted components, error details, and input hashes are
displayed as imported evidence. The file is not uploaded to the API. Basic
report structure is checked, but scores, provenance, and annotation quality
are not independently verified. No project metrics are bundled or invented.

Start the existing FastAPI application and open
`http://127.0.0.1:8000/dashboard`. The page is served from the packaged
`regintel.api.dashboard` assets and uses the same-origin authenticated API.

Implemented interactions include local login, report pagination, report
findings and policy evidence, full report JSON, audit history, refresh, and
sign-out, and JSON-uploaded what-if change simulation. `/auth/me` now includes the account role. Pending reports expose a
decision form only to compliance officers; the backend remains authoritative
for role and state checks. A submission records a real decision, so officers
must review the evidence first. Do not use actual reports for demonstration
approvals. No real review was submitted during implementation.

Bearer tokens remain in JavaScript memory and disappear on reload or sign-out.
Report text is rendered with `textContent`; it is not interpreted as HTML.
The page itself is public, while report and history data require authentication.
Synthetic evidence and pending review status remain explicitly identified.

Serving, authentication, and permission regression tests pass, and JavaScript
syntax was checked. The signed-out page was visually inspected in headless
Edge at desktop size and with a 390 × 844 mobile viewport. The mobile check
measured both viewport and document width at 390 pixels, with no horizontal
overflow. Its screenshot is saved at
`data/processed/dashboard_qa/mobile.png`. Temporary preview processes used
dummy database configuration and were stopped after the check.
Six JavaScript client regression tests pass, including viewer-only report
display, rendering untrusted finding text, officer rationale validation,
decision payloads, session expiry, and duplicate submission protection.
These use a simulated DOM rather than an authenticated browser. The synthetic
API integration test also passes for real login, report rejection, persisted
report status, audit history, and duplicate decision rejection. It uses an
isolated in-memory database and does not change application reports.

An authenticated headless Edge smoke check also passed against a temporary
SQLite fixture database: viewer and officer login, report selection, viewer
review controls hidden, officer rejection, refreshed audit history, review
form removal after a decision, and sign-out clearing displayed report data.
Browser local and session storage remained empty, and the isolated database
contained one consistent synthetic review. The check used actual dashboard
assets and API routes with an overridden database dependency. It submitted
no decisions to the application database. The temporary server and browser
were stopped afterward. This does not establish production PostgreSQL
concurrency behavior or coverage of every dashboard interaction.

Additional headless Edge checks passed at viewport widths 320, 390, 768,
1024, and 1440 pixels: the login page and a visible workspace containing
1,000 characters of unbroken synthetic report text had no horizontal
document overflow. The workspace check injected display content without
calling the database. On the signed-out page, actual Tab key events moved
focus through the API documentation link, username, password, and submit
button, with visible focus outlines on each. Keyboard-only authenticated
workflows, screen-reader behavior, and populated catalog/upload layouts
remain unverified; these checks are not a complete accessibility audit.
The local Docker image was refreshed from the latest wheel and its packaged
dashboard and invalid-PDF handling were smoke-tested using dummy configuration.

Day 29 remains partial: ingestion jobs are not yet integrated
into the dashboard. Those workflows currently use local tools or API docs.

Phase 2 adds an authenticated multimodal evidence preview form for PDF,
DOCX, XLSX, CSV, PNG, and JPG. It displays extracted source locations and
OCR-required warnings without persistence or provider calls. Native/scanned
parsing and the preview API have regression coverage; the new upload control
has a Node duplicate-submission/session test. An end-to-end browser upload
check remains pending. See `phase2_evidence.md` for the explicit local OCR,
append-only evidence, retrieval, and synthetic control-test workflows.
