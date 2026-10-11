# Local security review

The Linux image's 105-package inventory was audited separately. The initial
report flagged pip and setuptools; both were upgraded in the local image and
the Dockerfile now requires `pip>=26.2` and `setuptools>=83`. The repeated audit
reported no known vulnerabilities. The local project and CPU-specific PyTorch
version were skipped by the advisory service, so those are not cleared by this
scan. `linux_dependency_audit.json`, the retained before-update report, and
`linux_image_audit_metadata.json` record results and image identity. This scans
Python advisories only, not operating-system packages or the entire image.

An installed-environment dependency audit was run with
`uvx pip-audit --path .venv/Lib/site-packages --progress-spinner off --format json --output dependency_audit.json`.
The local report contains the advisory-query results; no known vulnerabilities
were reported at the time of the scan. This covers the Windows installed
environment, not the Linux image or unreported vulnerabilities. Dependencies
were not modified. Retain skipped-package notices with the report.

The built wheel passed the limited hygiene scan:
`uv run python scripts/check_submission_artifact.py dist/regulatory_compliance_ai-0.1.0-py3-none-any.whl`.
No environment/runtime-file paths or private-key markers were found. Two toy
tests verify detection and redacted reporting. This does not check all API keys,
passwords, tokens, repository history, or dependency vulnerabilities, so a
comprehensive final secret review remains pending.

Scope: repository authentication, review transactions, dashboard, upload preview,
request logging, and local packaging. The code and test review is supplemented
by the Windows dependency audit above; it is not a penetration test or
production certification.

## Verified controls

| Area | Evidence |
| --- | --- |
| Passwords | Argon2 hashing; login uses a dummy hash for unknown usernames; password hashes are excluded from API responses |
| Tokens | HS256 is explicitly selected; sub/iat/exp/type claims are required; invalid and expired tokens are rejected |
| Account status | Current-user lookup reads the database account and rejects inactive users |
| Reviews | Officer-only API dependency; identity comes from the account; pending-only transitions; row lock and atomic audit transaction |
| Competing decisions | Dedicated PostgreSQL test confirmed one terminal decision and one audit record |
| Dashboard | Tokens remain in memory; output uses textContent; current-session 401 signs out; stale responses cannot replace a newer session |
| Browser headers | Same-origin CSP on dashboard, no framing or embedded objects, API no-store, nosniff, no-referrer |
| Upload preview | Authentication, file/text/page bounds, encrypted/malformed rejection, no database persistence, no OCR |
| Request logs | Method, route template, status, duration, request ID; no body/token/query/exception text |
| Packaging | Non-root API image; environment files and datasets excluded from build context; dashboard included in wheel |

Tests verify role rejection, JWT failures, transaction rollback, duplicate review
rejection, safe logging, upload boundaries, and session behavior using isolated
or synthetic inputs. Local container smoke checks and read-only database checks
passed. Browser layout and complete browser interaction testing remain pending.

## Remaining scope and limitations

The application has no login rate limiter, account lockout, token revocation
list, or self-service credential rotation. JWT expiry and account deactivation
are the available session controls. There is no tenant-level report isolation;
authenticated accounts share the local report catalog. Public registration is
absent. The development setup binds published services to loopback and does not
configure TLS termination or an external authentication gateway.

File upload limits are checked after multipart parsing; the framework may spool
temporary files. Reverse-proxy request-size limits, parser process isolation,
and workload rate limits are not configured. PDF text/page limits do not bound
every native-parser resource cost. The preview is intended for trusted local
development documents, not a publicly exposed upload service.

API request logging is controlled, while third-party and Uvicorn logging retain
their settings. Offline workflow exceptions and provider logs need a separate
review before processing sensitive production documents. Benchmark approval
fields and uploaded source provenance are supplied metadata, not authenticated
review evidence. Synthetic datasets and simulation outputs remain labeled.

The image dependency installation resolves version ranges rather than the
Linux lockfile. Linux-image vulnerability scanning, TLS configuration, browser
verification, production deployment review, and secret scanning of final
submission artifacts remain unfinished. Environment exclusion rules and
placeholder templates do not prove arbitrary source files contain no secrets.

Keep the demo local and retain these limitations in the submission. Genuine
report approvals require a compliance officer's evidence review; no application
reports were approved as part of these checks.
