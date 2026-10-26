"""Single FastAPI entry point for CareLeap.

Run from the repo root:  make api   (or: python -m uvicorn api.main:app --reload)
"""

from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api import __version__
from api.deps import data_mode
from api.routers import audit, clinics, plan, provenance, report, rural, suggest, whatif
from api.schemas import HealthResponse


def create_app() -> FastAPI:
    mode = data_mode()
    app = FastAPI(
        title="CareLeap: Reachable Care API",
        version=__version__,
        description=(
            "Contracts: docs/contracts.md. Synthetic patients only; logistics only. "
            f"Data mode: {mode}."
        ),
    )

    # The web app runs on another origin (Vite :5173 in dev, Netlify in prod). Allow only
    # the origins we name; override with a comma-separated CARELEAP_WEB_ORIGINS.
    origins = [o.strip() for o in os.environ.get(
        "CARELEAP_WEB_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173").split(",") if o.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"],
                       allow_headers=["Content-Type"])

    @app.middleware("http")
    async def tag_data_mode(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Data-Mode"] = mode
        return response

    @app.get("/health", response_model=HealthResponse, tags=["health"])
    def health() -> HealthResponse:
        return HealthResponse(version=__version__, data_mode=mode)

    app.include_router(audit.router)  # M2
    app.include_router(clinics.router)  # M1 (web Audit screen)
    app.include_router(whatif.router)  # M2
    app.include_router(suggest.router)  # M1 (optimizer -> Suggest panel)
    app.include_router(rural.router)  # M1 (rural lens)
    app.include_router(plan.router)  # M4
    app.include_router(provenance.router)  # M4
    app.include_router(report.router)  # M3 (CHNA PDF report)

    # One-service deploy: serve the built React app from the same origin. Mounted LAST so
    # every API route above wins; the app uses #/ routes, so index.html is all it needs.
    web_dist = os.environ.get("CARELEAP_WEB_DIST")
    if web_dist and os.path.isdir(web_dist):
        app.mount("/", StaticFiles(directory=web_dist, html=True), name="web")

    return app


app = create_app()
