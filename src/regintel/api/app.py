
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from regintel.api.dependencies import get_db
from regintel.api.observability import install_observability
from regintel.api.routes.auth import router as auth_router
from regintel.api.routes.catalog import router as catalog_router
from regintel.api.routes.changes import router as changes_router
from regintel.api.routes.crossreg import router as crossreg_router
from regintel.api.routes.gap_reports import (
    router as gap_reports_router,
)
from regintel.api.routes.ingestion import router as ingestion_router
from regintel.api.routes.reviews import router as reviews_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Regulatory Compliance AI",
        description=(
            "Regulatory obligation assessment, "
            "evidence reporting, and human review API."
        ),
        version="0.1.0",
    )

    install_observability(app)
    dashboard = Path(__file__).parent / "dashboard"
    app.mount("/dashboard/assets", StaticFiles(directory=dashboard), name="dashboard-assets")

    @app.get("/dashboard", include_in_schema=False)
    def dashboard_page():
        return FileResponse(dashboard / "index.html", headers={"Cache-Control": "no-store"})

    @app.get("/ready", tags=["Health"])
    def readiness(db: Annotated[Session, Depends(get_db)]):
        try:
            db.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return JSONResponse(status_code=503, content={"status": "unavailable"})
        return {"status": "ready"}

    @app.get("/health", tags=["Health"])
    def health():
        return {"status": "ok"}
    
    app.include_router(
    reviews_router,
    prefix="/api/v1",
)
    app.include_router(
        gap_reports_router,
        prefix="/api/v1",
    )

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(changes_router, prefix="/api/v1")
    app.include_router(crossreg_router, prefix="/api/v1")
    app.include_router(catalog_router, prefix="/api/v1")
    app.include_router(ingestion_router, prefix="/api/v1")

    return app


app = create_app()
