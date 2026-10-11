# API container

Build the local image:

```powershell
docker build -t regintel-api:local .
```

The image installs the project with CPU-only PyTorch and runs Uvicorn as UID
10001. Build context exclusions prevent local credentials, datasets, virtual
environments, and test artifacts from being copied. The image includes neither
database migrations nor source datasets; run migrations through the existing
local setup before connecting to an application database.

Provide runtime variables using a private container-specific environment file.
On Docker Desktop, a database published on the Windows host is addressed through
`host.docker.internal`, not `127.0.0.1` inside the container. Keep the password
and database name consistent with the existing database. Do not commit this file.

```powershell
docker run --rm --name regintel-api-demo -p 127.0.0.1:8000:8000 --env-file .env.container regintel-api:local
```

Use the same variable requirements described in [local_setup.md](local_setup.md).
Only `/health` can confirm process liveness without querying PostgreSQL;
`/ready` checks database connectivity. This command does not initialize data,
create accounts, or submit reviews. Stop the foreground container with Ctrl+C.
The database's persistent volume remains separate.

The dependency installation currently resolves the version ranges in
`pyproject.toml`; it does not consume `uv.lock`. Retain the built image digest
and resolved dependency inventory for a submitted build. Fully locked Linux
dependencies and end-to-end database deployment verification remain follow-up
work. Building does not download embedding model weights or make Gemini calls.

Local verification: `regintel-api:local` built successfully, and an isolated
container smoke test confirmed UID 10001, HTTP 200 from `/health`, and a response
request ID. The test used dummy configuration and made no database or Gemini
calls. A separate container check against the existing local PostgreSQL database
confirmed `/ready` returns HTTP 200 using `host.docker.internal`. Runtime
credentials were supplied through the process environment, without printing them
or copying them into the image. Full assessment functionality and fresh-database
migration deployment remain unverified.
The read-only audit checker also ran successfully inside the image: one report,
zero review records, and no consistency issues at the time of verification.
