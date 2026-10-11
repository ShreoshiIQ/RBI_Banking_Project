"""Request metadata only: never log bodies, credentials, queries, or exception text."""

import json
import logging
import re
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("regintel.requests")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False
REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def install_observability(app: FastAPI) -> None:
    @app.middleware("http")
    async def log_request(request: Request, call_next):
        supplied = request.headers.get("X-Request-ID", "")
        request_id = supplied if REQUEST_ID.fullmatch(supplied) else uuid4().hex
        request.state.request_id = request_id
        started = perf_counter()
        error_type = None
        try:
            response = await call_next(request)
        except Exception as exc:
            error_type = type(exc).__name__
            response = JSONResponse(status_code=500, content={
                "detail": "Internal server error", "request_id": request_id,
            })
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/api/v1/"):
            response.headers["Cache-Control"] = "no-store"
        if request.url.path == "/dashboard":
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self'; "
                "connect-src 'self'; object-src 'none'; base-uri 'none'; "
                "frame-ancestors 'none'; form-action 'self'"
            )
        route = request.scope.get("route")
        logger.info(json.dumps({
            "event": "http_request", "request_id": request_id,
            "method": request.method, "route": getattr(route, "path", "unmatched"),
            "status_code": response.status_code,
            "duration_ms": round((perf_counter() - started) * 1000, 2),
            "error_type": error_type,
        }))
        return response
