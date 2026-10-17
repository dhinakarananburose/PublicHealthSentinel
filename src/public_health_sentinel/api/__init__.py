"""API package for PublicHealthSentinel (Phase 5).

Provides:
- FastAPI application instance and factory (app, create_app)
- API v1 routers (/api/v1/surveillance, /api/v1/mobility, /api/v1/anomalies, /api/v1/pipeline)
- Pydantic request/response data transfer models
"""

from public_health_sentinel.api.app import app, create_app
from public_health_sentinel.api.models import (
    AnomalyResultResponse,
    HealthResponse,
    MobilityIndicatorResponse,
    PaginatedResponse,
    RunDetectionRequest,
    RunDetectionResponse,
    SurveillanceObservationResponse,
)

__all__ = [
    "AnomalyResultResponse",
    "HealthResponse",
    "MobilityIndicatorResponse",
    "PaginatedResponse",
    "RunDetectionRequest",
    "RunDetectionResponse",
    "SurveillanceObservationResponse",
    "app",
    "create_app",
]
