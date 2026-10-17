"""SQLAlchemy models for PublicHealthSentinel relational persistence.

Defines schemas for:
1. Surveillance observations (aggregated syndromic counts)
2. Mobility indicators (aggregated population mobility shifts)
3. Anomaly detection results (method outputs, baseline scores, flags)
4. Pipeline execution records (audit log of pipeline runs)

Core Design Rules:
- Primary keys on all tables.
- Natural candidate keys guarded with unique constraints to prevent accidental duplicate multiplication.
- Missing counts/denominators remain NULL; never coerced to zero.
- Composite indexes tailored to common surveillance queries (region, syndrome, date range).
- Provenance labels (real, simulated, derived) strictly recorded on every observation.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


class SurveillanceObservationModel(Base):
    """Persisted aggregated syndromic surveillance observation."""

    __tablename__ = "surveillance_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    observation_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    region_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    syndrome: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    report_count: Mapped[int] = mapped_column(Integer, nullable=False)
    reporting_facility_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    population_denominator: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    data_source: Mapped[str] = mapped_column(String(128), nullable=False, default="UNKNOWN")
    data_status: Mapped[str] = mapped_column(String(32), nullable=False, default="simulated")
    ingestion_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint(
            "observation_date",
            "region_id",
            "syndrome",
            name="uq_surveillance_observation",
        ),
        Index("ix_surv_lookup", "region_id", "syndrome", "observation_date"),
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert ORM model to dictionary."""
        return {
            "id": self.id,
            "observation_date": self.observation_date.isoformat(),
            "region_id": self.region_id,
            "syndrome": self.syndrome,
            "report_count": self.report_count,
            "reporting_facility_count": self.reporting_facility_count,
            "population_denominator": self.population_denominator,
            "data_source": self.data_source,
            "data_status": self.data_status,
            "ingestion_timestamp": self.ingestion_timestamp.isoformat(),
        }


class MobilityIndicatorModel(Base):
    """Persisted aggregated population mobility indicator."""

    __tablename__ = "mobility_indicators"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    observation_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    region_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    mobility_metric: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    mobility_value: Mapped[float] = mapped_column(Float, nullable=False)
    data_source: Mapped[str] = mapped_column(String(128), nullable=False, default="UNKNOWN")
    data_status: Mapped[str] = mapped_column(String(32), nullable=False, default="simulated")
    ingestion_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint(
            "observation_date",
            "region_id",
            "mobility_metric",
            name="uq_mobility_indicator",
        ),
        Index("ix_mob_lookup", "region_id", "mobility_metric", "observation_date"),
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert ORM model to dictionary."""
        return {
            "id": self.id,
            "observation_date": self.observation_date.isoformat(),
            "region_id": self.region_id,
            "mobility_metric": self.mobility_metric,
            "mobility_value": self.mobility_value,
            "data_source": self.data_source,
            "data_status": self.data_status,
            "ingestion_timestamp": self.ingestion_timestamp.isoformat(),
        }


class AnomalyDetectionResultModel(Base):
    """Persisted output of statistical anomaly detection algorithms."""

    __tablename__ = "anomaly_detection_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    observation_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    region_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    syndrome: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    detection_method: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    observed_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    expected_baseline: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    anomaly_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    detection_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_anomaly: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, index=True)
    history_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    evaluation_status: Mapped[str] = mapped_column(String(64), nullable=False, default="evaluated")
    data_source: Mapped[str] = mapped_column(String(128), nullable=False, default="UNKNOWN")
    data_status: Mapped[str] = mapped_column(String(32), nullable=False, default="simulated")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint(
            "observation_date",
            "region_id",
            "syndrome",
            "detection_method",
            name="uq_anomaly_result",
        ),
        Index("ix_anom_lookup", "region_id", "syndrome", "detection_method", "observation_date"),
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert ORM model to dictionary."""
        return {
            "id": self.id,
            "observation_date": self.observation_date.isoformat(),
            "region_id": self.region_id,
            "syndrome": self.syndrome,
            "detection_method": self.detection_method,
            "observed_count": self.observed_count,
            "expected_baseline": self.expected_baseline,
            "anomaly_score": self.anomaly_score,
            "detection_threshold": self.detection_threshold,
            "is_anomaly": self.is_anomaly,
            "history_count": self.history_count,
            "evaluation_status": self.evaluation_status,
            "data_source": self.data_source,
            "data_status": self.data_status,
            "created_at": self.created_at.isoformat(),
        }


class PipelineExecutionModel(Base):
    """Audit ledger tracking pipeline execution status and summary metrics."""

    __tablename__ = "pipeline_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    execution_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    pipeline_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    parameters_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    records_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    anomalies_detected: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def to_dict(self) -> dict[str, Any]:
        """Convert ORM model to dictionary."""
        return {
            "id": self.id,
            "execution_id": self.execution_id,
            "pipeline_type": self.pipeline_type,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "parameters_json": self.parameters_json,
            "summary_json": self.summary_json,
            "records_processed": self.records_processed,
            "anomalies_detected": self.anomalies_detected,
            "error_message": self.error_message,
        }


class DocumentMetadataModel(Base):
    """Metadata and provenance record for ingested public health reference documents."""

    __tablename__ = "document_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    doc_format: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_publisher: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    publication_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    document_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    character_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ingestion_status: Mapped[str] = mapped_column(String(32), nullable=False, default="INGESTED", index=True)
    stored_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ingestion_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert ORM model to dictionary."""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "filename": self.filename,
            "title": self.title,
            "doc_format": self.doc_format,
            "content_hash": self.content_hash,
            "source_publisher": self.source_publisher,
            "source_url": self.source_url,
            "publication_date": self.publication_date.isoformat() if self.publication_date else None,
            "document_size_bytes": self.document_size_bytes,
            "character_count": self.character_count,
            "word_count": self.word_count,
            "ingestion_status": self.ingestion_status,
            "stored_path": self.stored_path,
            "error_message": self.error_message,
            "ingestion_timestamp": self.ingestion_timestamp.isoformat(),
        }


class DocumentChunkModel(Base):
    """Extracted text passage chunk with metadata and serialized vector embedding."""

    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chunk_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_publisher: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    publication_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    embedding_model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    __table_args__ = (
        Index("ix_chunk_doc_seq", "document_id", "sequence_number"),
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert ORM model to dictionary."""
        return {
            "id": self.id,
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "sequence_number": self.sequence_number,
            "text": self.text,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "title": self.title,
            "source_publisher": self.source_publisher,
            "source_url": self.source_url,
            "publication_date": self.publication_date.isoformat() if self.publication_date else None,
            "content_hash": self.content_hash,
            "embedding_model": self.embedding_model,
            "created_at": self.created_at.isoformat(),
        }

