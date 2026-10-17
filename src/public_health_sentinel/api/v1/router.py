"""Assembles API v1 routes under prefix /api/v1."""

from fastapi import APIRouter

from public_health_sentinel.api.v1.routers.anomalies import router as anomalies_router
from public_health_sentinel.api.v1.routers.assistant import router as assistant_router
from public_health_sentinel.api.v1.routers.documents import router as documents_router
from public_health_sentinel.api.v1.routers.evidence import router as evidence_router
from public_health_sentinel.api.v1.routers.geospatial import router as geospatial_router
from public_health_sentinel.api.v1.routers.mobility import router as mobility_router
from public_health_sentinel.api.v1.routers.pipeline import router as pipeline_router
from public_health_sentinel.api.v1.routers.surveillance import router as surveillance_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(surveillance_router)
api_v1_router.include_router(mobility_router)
api_v1_router.include_router(anomalies_router)
api_v1_router.include_router(pipeline_router)
api_v1_router.include_router(documents_router)
api_v1_router.include_router(evidence_router)
api_v1_router.include_router(assistant_router)
api_v1_router.include_router(geospatial_router)

