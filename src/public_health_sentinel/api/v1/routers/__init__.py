"""API v1 routers package."""

from public_health_sentinel.api.v1.routers.anomalies import router as anomalies_router
from public_health_sentinel.api.v1.routers.mobility import router as mobility_router
from public_health_sentinel.api.v1.routers.pipeline import router as pipeline_router
from public_health_sentinel.api.v1.routers.surveillance import router as surveillance_router

__all__ = [
    "anomalies_router",
    "mobility_router",
    "pipeline_router",
    "surveillance_router",
]
