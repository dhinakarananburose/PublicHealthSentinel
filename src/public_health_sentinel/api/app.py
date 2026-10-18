"""FastAPI Application factory and entry point for PublicHealthSentinel (Phase 5).

Provides:
- GET /health: Application and database connectivity health probe
- Versioned API mounting under /api/v1
- Global error sanitation preventing exposure of stack traces, secrets, or internal paths
- Database schema initialization during application lifespan
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from public_health_sentinel.api.models import HealthResponse
from public_health_sentinel.api.v1.router import api_v1_router
from public_health_sentinel.config import get_config
from public_health_sentinel.db.session import get_engine, init_db

logger = logging.getLogger("public_health_sentinel.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan: initialize database schemas and evidence index on startup."""
    try:
        init_db()
        logger.info("Database schemas initialized successfully.")
        config = get_config()
        if config.demo_mode:
            from public_health_sentinel.db.demo_seeder import seed_demo_data_if_needed
            seed_demo_data_if_needed()

        from public_health_sentinel.documents.index import ensure_evidence_index_initialized
        index_res = ensure_evidence_index_initialized()
        logger.info("Evidence vector index startup verification complete: %s", index_res.get("message"))
    except Exception as exc:
        logger.error("Failed to initialize database or vector index during startup: %s", exc)
    yield


def create_app() -> FastAPI:
    """Construct and configure the PublicHealthSentinel FastAPI service."""
    config = get_config()

    app = FastAPI(
        title=config.api_title,
        version=config.api_version,
        description=(
            "Production-oriented syndromic surveillance anomaly detection and mobility analysis service. "
            "All returned observations, indicators, and detection results are synthetic research benchmarks."
        ),
        lifespan=lifespan,
    )

    # Configure CORS for local development frontend and optional configured origins
    default_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    custom_origins_raw = os.getenv("CORS_ORIGINS", "")
    if custom_origins_raw:
        custom_origins = [o.strip() for o in custom_origins_raw.split(",") if o.strip()]
        allowed_origins = list(dict.fromkeys(default_origins + custom_origins))
    else:
        allowed_origins = default_origins

    origin_regex = os.getenv("CORS_ORIGIN_REGEX")
    if not origin_regex and (config.demo_mode or config.app_env in {"production", "staging"}):
        origin_regex = r"^https://.*\.onrender\.com$"

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_origin_regex=origin_regex,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Global Exception Handlers
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "status_code": exc.status_code,
                "message": exc.detail,
                "path": request.url.path,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Sanitize validation errors: clean field names and messages
        cleaned_errors = []
        for err in exc.errors():
            loc = " -> ".join(str(item) for item in err.get("loc", []))
            cleaned_errors.append({"location": loc, "message": err.get("msg")})
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": True,
                "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
                "message": "Request validation failed. Verify parameter formats and value ranges.",
                "details": cleaned_errors,
                "path": request.url.path,
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Never leak raw stack traces or internal connection details
        logger.error("Unhandled server error at %s: %s", request.url.path, exc, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": True,
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "An internal server error occurred. Please contact the administrator.",
                "path": request.url.path,
            },
        )

    # Health Check Endpoint
    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["System"],
        summary="Application health check",
        description="Verify service availability and database connectivity.",
    )
    def health_check() -> HealthResponse:
        db_connected = False
        try:
            engine = get_engine()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                db_connected = True
        except Exception as exc:
            logger.warning("Database health check probe failed: %s", exc)
            db_connected = False

        status_str = "healthy" if db_connected else "degraded"
        current_config = get_config()
        return HealthResponse(
            status=status_str,
            app_name=current_config.app_name,
            environment=current_config.app_env,
            api_version=current_config.api_version,
            database_connected=db_connected,
            timestamp=datetime.now(timezone.utc),
            demo_mode=current_config.demo_mode,
        )

    # Mount Versioned API
    app.include_router(api_v1_router)

    return app


app = create_app()
