"""Database persistence package for PublicHealthSentinel (Phase 5).

Provides:
- SQLAlchemy ORM models (SurveillanceObservationModel, MobilityIndicatorModel, AnomalyDetectionResultModel, PipelineExecutionModel)
- Thread-safe session and engine management (get_engine, get_db_session, init_db)
- Pure persistence services with duplicate-prevention and pagination
"""

from public_health_sentinel.db.models import (
    AnomalyDetectionResultModel,
    Base,
    DocumentMetadataModel,
    MobilityIndicatorModel,
    PipelineExecutionModel,
    SurveillanceObservationModel,
)
from public_health_sentinel.db.service import (
    get_anomaly_results,
    get_mobility_indicators,
    get_surveillance_observations,
    ingest_mobility_indicators,
    ingest_surveillance_observations,
    persist_anomaly_results,
    record_pipeline_execution,
)
from public_health_sentinel.db.session import (
    get_db_session,
    get_engine,
    get_session_factory,
    init_db,
    reset_engine_for_testing,
)

__all__ = [
    "AnomalyDetectionResultModel",
    "Base",
    "DocumentMetadataModel",
    "MobilityIndicatorModel",
    "PipelineExecutionModel",
    "SurveillanceObservationModel",
    "get_anomaly_results",
    "get_db_session",
    "get_engine",
    "get_mobility_indicators",
    "get_session_factory",
    "get_surveillance_observations",
    "ingest_mobility_indicators",
    "ingest_surveillance_observations",
    "init_db",
    "persist_anomaly_results",
    "record_pipeline_execution",
    "reset_engine_for_testing",
]
