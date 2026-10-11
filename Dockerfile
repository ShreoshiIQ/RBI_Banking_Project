# Build the React web app into the Python package.
FROM node:20.18.0-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN cd frontend && npm ci --no-audit --no-fund
COPY frontend ./frontend
RUN mkdir -p src/regintel/api && cd frontend && npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/cache/huggingface

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY --from=web /web/src/regintel/api/webapp ./src/regintel/api/webapp
# Migrations ship in the image so a pre-deploy job can run them with the owner role.
COPY alembic.ini ./
COPY migrations ./migrations
RUN python -m pip install torch --index-url https://download.pytorch.org/whl/cpu \
    && python -m pip install . \
    && python -m pip install --upgrade "pip>=26.2" "setuptools>=83" \
    && useradd --create-home --uid 10001 regintel

USER regintel
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "regintel.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
