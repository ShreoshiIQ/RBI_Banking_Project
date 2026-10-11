# Production controls

## Applicability enforcement

`regintel.applicability.engine` decides, for each registered source, whether it
applies to the entity profile. Rules apply in this order:

| Order | Rule | Result |
| --- | --- | --- |
| 1 | Source carries a withdrawal marker | `not_applicable` (historical record) |
| 2 | Source belongs to another entity profile | `not_applicable` |
| 3 | Validated officer decision exists | `applicable` / `not_applicable` (authoritative) |
| 4 | Title names commercial banks, or only excluded entity types | `presumed_applicable` / `presumed_not_applicable` |
| 5 | Instrument covers a feature the profile has, or lacks | `presumed_applicable` / `presumed_not_applicable` |
| 6 | No rule matched | `undetermined` |

Only an officer decision produces `applicable`. The remediation supervisor runs an
`applicability` step after intake: gaps against `not_applicable` and
`presumed_not_applicable` sources leave the register and are listed under
`excluded_not_applicable` with the rule that excluded them. Any other gap that
lacks an officer decision goes to the human queue with "applicability not
confirmed by an officer". `--no-applicability` disables this step. The RBI
watcher uses the same title and feature rules for its triage hints.

Current registry (October 11, 2026): 4 withdrawn RBI directions and 3 SEBI
sources are not applicable to the demo bank; PPI directions are presumed not
applicable because the profile has no PPI issuance; the KYC and four current
commercial-bank directions are presumed applicable. No officer decisions exist yet.

## Tenant isolation

Migration `d190f0030001` adds `tenant_id` to policy, evidence, gap-report, and
review tables (and `users`). Existing rows are assigned to
`fictional-commercial-bank-demo`. Regulatory reference data stays shared.
PostgreSQL row-level security restricts every non-owner role to rows where
`tenant_id` equals the transaction's `app.tenant_id`.

- `regintel.api.tenancy.get_tenant_db` reads the caller's tenant from the users
  table, never from the token, and sets `app.tenant_id` transaction-locally on
  every transaction, so a pooled connection never carries a tenant into another
  request.
- Owners and superusers bypass row-level security. The API must connect as the
  role created by `scripts/provision_app_role.py` (login, no superuser, no
  BYPASSRLS, DML only). Migrations and ingestion keep the owner URL.
- Set `TENANT_ISOLATION_ENABLED=true` only after migrating. It defaults to false,
  so existing local setups behave as before.

Verified in a scratch PostgreSQL 16 database (migrate to head, downgrade, and
upgrade again; then dropped): the app role sees only its tenant; an unscoped
session sees nothing; the scope survives commits and does not leak through the
pool; cross-tenant inserts are rejected and cross-tenant updates change no rows;
the owner still sees all tenants; and `GET /api/v1/gap-reports` returns only the
caller's tenant, with 404 for another tenant's report. The local `regintel_db`
has **not** been migrated.

To adopt locally:

```powershell
uv run alembic upgrade head
$env:APP_DB_PASSWORD = '<random secret>'
uv run python scripts/provision_app_role.py --role regintel_app
# then point the API's DATABASE_URL at regintel_app and set TENANT_ISOLATION_ENABLED=true
```

## Single sign-on (OIDC)

Set `OIDC_ISSUER`, `OIDC_AUDIENCE`, and `OIDC_JWKS_URL` (HTTPS only) to accept
bearer tokens from an identity provider such as Entra ID, Okta, or Keycloak.
Local login keeps working alongside SSO.

- Only asymmetric algorithms are accepted (RS*, ES*, PS256). HS* and `none` are
  rejected, which blocks algorithm-confusion forgeries using the public key.
- Issuer, audience, expiry, issued-at, and subject are required and checked.
- The username claim (`OIDC_USERNAME_CLAIM`, default `preferred_username`) must
  match an existing, active local user. There is no automatic account creation.
  Roles and tenants always come from the local database, not from token claims.

## Deployment

`deploy/k8s` is a Kustomize base plus a production overlay (`kubectl kustomize
deploy/k8s/overlays/production`):

- API Deployment: 3 replicas, zero-downtime rolling updates, startup, readiness
  (`/ready`) and liveness (`/health`) probes, non-root UID 10001, read-only root
  filesystem, all capabilities dropped, and a seccomp profile.
- HorizontalPodAutoscaler (3–10 replicas), PodDisruptionBudget (2 available),
  and a NetworkPolicy limiting egress to DNS, PostgreSQL, and HTTPS.
- Migration Job using the owner URL, run before each rollout.
- RBI watcher CronJob every 30 minutes, single writer, state on a PVC seeded
  with the repository's `data/` tree.
- Namespace with the `restricted` Pod Security Standard and a TLS Ingress.
- Secrets are referenced, never stored: see `deploy/k8s/secret.example.yaml`.

The image now includes `alembic.ini` and `migrations/` so the migration Job can
run, and sets `HF_HOME` to a writable cache volume.

## Continuous integration

`.github/workflows/ci.yml`:

1. Strict lint for every module added in this phase; the older backlog (193
   findings) is reported without blocking, to be ratcheted down.
2. A PostgreSQL 16 + pgvector service; migrations upgrade, downgrade one step,
   and upgrade again.
3. The full test suite with `TEST_DATABASE_URL` set, so the row-level security
   tests run instead of skipping.
4. `scripts/eval_gate.py` against `eval_gates.json`: native extraction recall and
   accuracy, zero silent errors, defect precision, the stored live-OCR summary,
   and exact risk scores on the stored RBI 46(f) report.
5. Manifest rendering and schema validation (kubeconform).
6. Image build and a Trivy scan that fails on fixable critical or high findings.

The workflow has not run on GitHub yet; this folder is not a git repository.
