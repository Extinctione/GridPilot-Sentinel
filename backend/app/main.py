"""
GridPilot Sentinel - Backend Entry Point
Phase 2: Weather, Energy, Battery, Cyber and Cross-Domain intelligence.

This is a simulation / decision-support platform. It does not control
real electricity-grid infrastructure; every figure it serves is either
clearly labelled as simulated/synthetic or derived from such data.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers import battery, correlation, cyber, energy, recommendations, weather

logger = logging.getLogger("gridpilot")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="GridPilot Sentinel API",
    description=(
        "Decision-support and simulation platform for a renewable-rich "
        "electricity grid. This API does not control real grid "
        "infrastructure; all data it serves is either clearly labelled "
        "as simulated/synthetic or derived from such data."
    ),
    version="0.2.0",
)

# Allow the Vite dev server (default port 5173) to call this API during
# local development. Adjust / lock this down before any real deployment.
#
# allow_origin_regex is a safety net: if port 5173 is already taken, Vite
# silently falls forward to 5174/5175/etc, and a fixed allow_origins list
# would then make every request fail CORS with no obvious explanation on
# the frontend (it just looks like the backend is unreachable). Any
# localhost/127.0.0.1 port is still local-dev-only, so this stays safe.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Catch anything a router/service didn't already turn into a clean
    HTTPException.

    Registering this (rather than letting FastAPI's default 500 handler
    fire) matters for two reasons: it prints the real traceback to this
    terminal so the failure is visible, and -- because Starlette only
    attaches CORS headers to responses that pass back through
    ExceptionMiddleware, not to responses built by the outer
    ServerErrorMiddleware -- an uncaught exception here would otherwise
    reach the browser as a bare CORS/network failure, hiding the actual
    500 and making it look like the backend can't be reached at all.
    """
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal error: {type(exc).__name__}: {exc}"},
    )

app.include_router(weather.router)
app.include_router(energy.router)
app.include_router(battery.router)
app.include_router(cyber.router)
app.include_router(correlation.router)
app.include_router(recommendations.router)


@app.get("/api/health")
def health_check():
    """
    Liveness/connectivity check used by the frontend on load.

    Also reports per-module build errors (see app.services.pipeline) so
    a degraded backend is visible and explained here rather than
    surfacing only as scattered page-level failures.
    """
    from app.services import pipeline  # local import avoids a cost at module import time

    try:
        data = pipeline.get_pipeline()
        module_errors = data.get("errors", {})
    except Exception as exc:  # pragma: no cover - pipeline itself should not raise, but never trust that blindly
        logger.exception("Health check could not build the pipeline")
        module_errors = {"pipeline": f"{type(exc).__name__}: {exc}"}

    return {
        "status": "ok" if not module_errors else "degraded",
        "service": "GridPilot Sentinel API",
        "phase": "Phase 2 - Weather, Energy, Battery, Cyber, Cross-Domain",
        "message": (
            "Backend is running and reachable."
            if not module_errors
            else "Backend is running, but one or more modules failed to build -- see module_errors."
        ),
        "module_errors": module_errors,
    }


@app.get("/")
def root():
    return {
        "message": "GridPilot Sentinel API root. See /docs for interactive API docs.",
    }
