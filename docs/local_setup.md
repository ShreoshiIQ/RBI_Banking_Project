# Local setup on Windows

For OneDrive workspaces that reject hardlinks, set `$env:UV_LINK_MODE = 'copy'`
before uv installation or build commands. The local wheel build was verified
with this setting and `uv build --offline --wheel` using cached build dependencies.

Run commands from the project directory. Install Python 3.12 and uv; PostgreSQL
16 with pgvector is required for persistence and vector retrieval. Docker Compose
in this repository starts the database only; it does not deploy the API.

```powershell
uv sync --locked
```

If `.env` does not already exist, copy `.env.example` to `.env`. Preserve an
existing configuration. Replace every placeholder privately before using it.
Use a random JWT secret of at least 32 characters. Keep the database password
and URL credentials consistent; URL-encode reserved characters in the URL.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Required SQLAlchemy PostgreSQL connection URL |
| `DATABASE_CONNECT_TIMEOUT_SECONDS` | PostgreSQL connection timeout, default 5 seconds, permitted range 1–60 |
| `POSTGRES_PASSWORD` | Database container initialization password |
| `JWT_SECRET_KEY` | Required for JWT authentication, minimum 32 characters |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime, default 30, permitted range 1–1440 |
| `GEMINI_API_KEY` | Required for live Gemini verification; offline scoring needs no key |
| `GEMINI_MODEL` | Optional verifier model override |
| `TEST_DATABASE_URL` | Optional dedicated PostgreSQL concurrency-test database |

The template is not usable credentials. Do not publish `.env`, bearer tokens,
database connection strings with real passwords, or model keys.

For a new local database:

```powershell
docker compose up -d postgres
docker compose exec postgres psql -U regintel -d regintel_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
uv run alembic upgrade head
uv run python scripts/create_dev_user.py
uv run uvicorn regintel.api.app:app --host 127.0.0.1 --port 8000
```

Wait for the database health check to succeed before running the extension and
migration commands. The pgvector image provides extension files, but the vector
extension must also be enabled in the database. The current embedding migration
does not enable it automatically.

Migrations change schema and should be reviewed before applying to an existing
database. Never reset the volume to fix authentication problems. PostgreSQL's
initialization password applies when the data volume is first created; editing
the environment file does not rotate a password in an existing database.

Check `http://127.0.0.1:8000/health`, `/ready`, and `/docs`. Readiness verifies
connectivity only. Follow [demo_walkthrough.md](demo_walkthrough.md) for login,
reports, and hypothetical change analysis. Source ingestion and assessments
are separate local pipeline operations; startup does not ingest demo drafts.

Offline evaluation uses [benchmark_runner.md](benchmark_runner.md). Live model
verification can incur API usage and needs a valid key. Embedding workflows may
require model downloads; offline metric calculation does not load embeddings.

This guide reflects the checked-in configuration. Fresh-machine installation,
complete end-to-end deployment verification remain to be performed. An API
[Dockerfile](docker_api.md) is available separately; Compose supplies PostgreSQL.
