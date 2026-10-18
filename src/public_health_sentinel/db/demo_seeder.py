"""Self-healing demo database seeder for PublicHealthSentinel Phase 10.

Automatically populates empty or freshly mounted ephemeral SQLite databases with:
1. 2,700 synthetic syndromic surveillance records
2. 2,700 synthetic mobility indicators
3. 2,700 baseline anomaly detection results
4. Benchmark reference protocol documents and passage chunks

Enables resilient operation on ephemeral cloud platforms (such as Render Free Tier)
without requiring PyTorch or SentenceTransformer downloads during startup.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from public_health_sentinel.config import get_config
from public_health_sentinel.db.models import (
    AnomalyDetectionResultModel,
    DocumentChunkModel,
    DocumentMetadataModel,
    MobilityIndicatorModel,
    SurveillanceObservationModel,
)
from public_health_sentinel.db.service import (
    ingest_mobility_indicators,
    ingest_surveillance_observations,
    persist_anomaly_results,
)
from public_health_sentinel.db.session import get_engine, init_db
from public_health_sentinel.documents.chunker import split_text_into_chunks
from public_health_sentinel.documents.service import ingest_document
from public_health_sentinel.loader import load_mobility_csv, load_surveillance_csv
DEMO_FIXTURE_DOCUMENTS = [
    {
        "filename": "respiratory_surge_protocol.md",
        "title": "Respiratory Surge Statistical Threshold Protocol",
        "publisher": "Synthetic State Surveillance Taskforce",
        "content": (
            "# Respiratory Surge Statistical Threshold Protocol\n\n"
            "## Section 1: Baseline Estimation\n"
            "Emergency departments monitor daily encounters for respiratory syndrome. Baseline encounter counts "
            "are estimated using a 28-day centered window excluding active alert periods. "
            "Statistical surge alerts trigger when observed counts exceed baseline plus 2.5 times the median absolute deviation (MAD).\n\n"
            "## Section 2: Secondary Epidemiological Review\n"
            "Within 4 hours of an alert, the surveillance team verifies chief complaint coding distributions to eliminate "
            "electronic health record batching artifacts before escalating to regional health officers.\n\n"
            "## Section 3: Diagnostic Triage Criteria\n"
            "Patients presenting with acute dyspnea, fever above 38.0 C, and rapid respiratory rate qualify for prioritized syndromic tracking."
        ),
    },
    {
        "filename": "waterborne_outbreak_definition.md",
        "title": "Waterborne Gastrointestinal Outbreak Cluster Definition",
        "publisher": "Synthetic Municipal Water & Health Agency",
        "content": (
            "# Waterborne Gastrointestinal Outbreak Cluster Definition\n\n"
            "## Section 1: Case Definition for Waterborne Diarrheal Illness\n"
            "A suspected case is defined as acute onset of non-bloody watery diarrhea with at least three loose stools in 24 hours. "
            "Spatial clustering within a single municipal water distribution pressure zone warrants environmental sampling.\n\n"
            "## Section 2: Coliform and Turbidity Monitoring\n"
            "Water utilities must cross-reference daily turbidimetric measurements with syndromic diarrhea reports from primary clinics.\n\n"
            "## Section 3: Boil Water Advisory Trigger\n"
            "When clinic diarrhea encounter rates exceed 3.0 standard deviations concurrently with confirmed coliform detections, an immediate boil water advisory is mandatory."
        ),
    },
    {
        "filename": "measles_school_health_protocol.md",
        "title": "Measles and Rash Notification Protocol for School Health",
        "publisher": "Synthetic Department of School Health",
        "content": (
            "# Measles and Rash Notification Protocol for School Health\n\n"
            "## Section 1: Immediate Notification Criteria\n"
            "Any school student presenting with fever (>= 38.3 C) and generalized maculopapular rash, cough, coryza, or conjunctivitis "
            "must be immediately isolated in a designated room with negative air pressure or an N95-equivalent barrier.\n\n"
            "## Section 2: Roster Tracing\n"
            "School nurses must pull immunization rosters within 2 hours of case report to identify unvaccinated contacts.\n\n"
            "## Section 3: Post-Exposure Prophylaxis\n"
            "Unvaccinated susceptible individuals exposed to confirmed measles cases should receive MMR vaccine within 72 hours of initial exposure."
        ),
    },
    {
        "filename": "vhf_barrier_nursing_guidelines.md",
        "title": "Viral Hemorrhagic Fever Triage and Barrier Nursing Guidelines",
        "publisher": "Synthetic Regional Infectious Disease Institute",
        "content": (
            "# Viral Hemorrhagic Fever Triage and Barrier Nursing Guidelines\n\n"
            "## Section 1: Clinical Triage and Travel History\n"
            "Patients with acute febrile illness and travel history to an active filovirus endemic zone within the preceding 21 days "
            "must bypass general waiting rooms directly to an airborne isolation unit.\n\n"
            "## Section 2: Personal Protective Equipment\n"
            "Healthcare workers must don full-body impervious coveralls, double gloves, PAPR respirators, and chemical-resistant boot covers.\n\n"
            "## Section 3: Safe Laboratory Specimen Transport\n"
            "All blood samples must be triple-packaged under Category A biological agent transport standards before transit to reference laboratories."
        ),
    },
    {
        "filename": "mobility_lag_methodology.md",
        "title": "Mobility Index Integration and Lead-Lag Methodology",
        "publisher": "Synthetic Epidemiological Analytics Group",
        "content": (
            "# Mobility Index Integration and Lead-Lag Methodology\n\n"
            "## Section 1: Mobility Indicators in Syndromic Surveillance\n"
            "Aggregated transit and workplace mobility percentage changes are evaluated for lead-lag associations with syndromic curves. "
            "Empirical evidence demonstrates mobility changes precede peak respiratory clinic surge by 3 to 7 days.\n\n"
            "## Section 2: Predictive Comparison\n"
            "Autoregressive baseline models augmented with mobility indicators show modest improvement in F1 score for early wave alerts.\n\n"
            "## Section 3: Cautionary Interpretation\n"
            "Mobility shifts represent indirect population behavior and must not be used as the sole trigger for emergency public health restrictions."
        ),
    },
    {
        "filename": "statistical_anomaly_detection_methods.md",
        "title": "Syndromic Surveillance Statistical Anomaly Detection Methodology Protocol",
        "publisher": "Synthetic Epidemiological Analytics Group",
        "content": (
            "# Syndromic Surveillance Statistical Anomaly Detection Methodology Protocol\n\n"
            "## Section 1: Rolling MAD Dispersion Formula and Outlier Robustness\n"
            "In syndromic surveillance time series, dispersion measures expected variation around a rolling baseline. "
            "The Rolling Median Absolute Deviation (MAD) calculates non-parametric dispersion and handles outliers over past counts X:\n"
            "    raw_mad = median(|X_i - median(X)|)\n"
            "To estimate scale equivalent to standard deviation under normal distribution assumptions, raw MAD is scaled by:\n"
            "    scale = 1.4826 * raw_mad\n"
            "Rolling MAD provides a 50% breakdown point: up to half the historical window can consist of extreme outbreak surges or "
            "outliers without distorting baseline dispersion, unlike standard deviation (0% breakdown point).\n\n"
            "## Section 2: Anomaly Thresholding and Scale Floors\n"
            "The standardized anomaly score is evaluated as score = (observed_count - median(X)) / scale. "
            "A statistical surge alert triggers when score >= threshold (typically 3.0 robust standard deviations). "
            "If raw_mad equals zero (occurring when more than 50% of counts in the lookback window are identical, common in sparse "
            "or low-count syndromes), scale estimation falls back to mean absolute deviation multiplied by 1.2533, or a minimum "
            "scale floor to prevent division by zero.\n\n"
            "## Section 3: Comparative Usage with EWMA and Rolling Z-Score\n"
            "Surveillance pipelines evaluate three complementary statistical anomaly detectors:\n"
            "1. Rolling MAD: Non-parametric detector prioritizing outlier resistance across skewed syndromic counts with 50% breakdown robustness.\n"
            "2. Exponentially Weighted Moving Average (EWMA): Applies geometric smoothing weights lambda in (0, 1] (default: 0.2) to historical "
            "counts, tracking subtle multi-day trends with finite-horizon variance correction.\n"
            "3. Rolling Z-Score: Standard parametric moving average and standard deviation detector (score = (count - mean) / std), "
            "optimal when counts are approximately normal and free of severe outliers.\n\n"
            "## Section 4: Interpretation and Limitations of Statistical Alerts\n"
            "SYNTHETIC RESEARCH NOTICE: Statistical surge alerts indicate departure from simulated historical baseline behavior and do not "
            "establish clinical diagnosis or confirm a real-world outbreak. Algorithmic detections require secondary epidemiological "
            "review within 4 hours to rule out electronic health record coding shifts, holiday reporting lags, or facility batching "
            "artifacts before escalating."
        ),
    },
]

logger = logging.getLogger("public_health_sentinel.db.demo_seeder")


def _find_data_file(filename: str, config) -> Optional[Path]:
    """Resolve seed data file across local, container, and package directory layouts."""
    candidates = [
        config.data_processed_dir / filename,
        Path("data/processed") / filename,
        Path("/app/seed_data/processed") / filename,
        Path(__file__).resolve().parents[3] / "data" / "processed" / filename,
    ]
    for p in candidates:
        if p.exists() and p.is_file():
            return p
    return None


def is_db_empty(session_or_engine=None) -> bool:
    """Check if the primary surveillance observations table contains zero records."""
    if session_or_engine is None:
        session_or_engine = get_engine()

    if hasattr(session_or_engine, "scalar"):
        count = session_or_engine.scalar(select(func.count(SurveillanceObservationModel.id)))
        return count == 0 or count is None
    else:
        SessionLocal = sessionmaker(bind=session_or_engine)
        session = SessionLocal()
        try:
            count = session.scalar(select(func.count(SurveillanceObservationModel.id)))
            return count == 0 or count is None
        finally:
            session.close()


def seed_demo_data_if_needed(engine_or_session_override=None) -> dict[str, int]:
    """Check database tables and populate demonstration records if empty.

    Returns:
        Dictionary of seeded record counts by entity type.
    """
    config = get_config()
    should_close = False

    if engine_or_session_override is not None and hasattr(engine_or_session_override, "scalar"):
        session: Session = engine_or_session_override
    else:
        engine = engine_or_session_override or get_engine()
        init_db(engine)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        should_close = True

    seeded_counts: dict[str, int] = {
        "surveillance": 0,
        "mobility": 0,
        "anomalies": 0,
        "documents": 0,
        "chunks": 0,
    }

    try:
        # 1. Surveillance Observations
        surv_count = session.scalar(select(func.count(SurveillanceObservationModel.id)))
        if surv_count == 0:
            surv_file = _find_data_file("surveillance_observations.csv", config)
            if surv_file:
                logger.info("Populating demo surveillance data from %s...", surv_file)
                df = load_surveillance_csv(surv_file)
                raw_records = df.to_dict(orient="records")
                records = [{k: (None if pd.isna(v) else v) for k, v in row.items()} for row in raw_records]
                inserted, _ = ingest_surveillance_observations(session, records)
                session.commit()
                seeded_counts["surveillance"] = inserted
                logger.info("Seeded %d surveillance observations for demo mode.", inserted)

        # 2. Mobility Indicators
        mob_count = session.scalar(select(func.count(MobilityIndicatorModel.id)))
        if mob_count == 0:
            mob_file = _find_data_file("mobility_indicators.csv", config)
            if mob_file:
                logger.info("Populating demo mobility data from %s...", mob_file)
                df_mob = load_mobility_csv(mob_file)
                raw_records = df_mob.to_dict(orient="records")
                records = [{k: (None if pd.isna(v) else v) for k, v in row.items()} for row in raw_records]
                inserted_mob, _ = ingest_mobility_indicators(session, records)
                session.commit()
                seeded_counts["mobility"] = inserted_mob
                logger.info("Seeded %d mobility indicators for demo mode.", inserted_mob)

        # 3. Anomaly Detection Results
        anom_count = session.scalar(select(func.count(AnomalyDetectionResultModel.id)))
        if anom_count == 0:
            anom_file = _find_data_file("detection_results.csv", config)
            if anom_file:
                logger.info("Populating demo anomaly results from %s...", anom_file)
                df_anom = pd.read_csv(anom_file)
                raw_records = df_anom.to_dict(orient="records")
                records = [{k: (None if pd.isna(v) else v) for k, v in row.items()} for row in raw_records]
                inserted_anom, _ = persist_anomaly_results(session, records)
                session.commit()
                seeded_counts["anomalies"] = inserted_anom
                logger.info("Seeded %d anomaly detection results for demo mode.", inserted_anom)

        # 4. Reference Protocol Documents & Passage Chunks
        for fixture in DEMO_FIXTURE_DOCUMENTS:
            existing_doc = session.scalar(
                select(DocumentMetadataModel).where(DocumentMetadataModel.filename == fixture["filename"])
            )
            if existing_doc is None:
                doc_model, is_dup = ingest_document(
                    session=session,
                    filename=fixture["filename"],
                    content=fixture["content"],
                    title=fixture["title"],
                    source_publisher=fixture["publisher"],
                    publication_date=date(2026, 1, 15),
                )
                session.commit()
                if not is_dup:
                    seeded_counts["documents"] += 1
            else:
                doc_model = existing_doc

            # Verify chunks exist for this document
            chunk_count = session.scalar(
                select(func.count(DocumentChunkModel.id)).where(
                    DocumentChunkModel.document_id == doc_model.document_id
                )
            )
            if chunk_count == 0:
                doc_chunks = split_text_into_chunks(
                    text=fixture["content"],
                    document_id=doc_model.document_id,
                    title=doc_model.title,
                    source_publisher=doc_model.source_publisher,
                    source_url=doc_model.source_url,
                    publication_date=doc_model.publication_date,
                    doc_format=doc_model.doc_format,
                    target_chunk_size=config.chunk_target_size,
                    chunk_overlap=config.chunk_overlap,
                )

                for chunk in doc_chunks:
                    chunk_model = DocumentChunkModel(
                        chunk_id=chunk.chunk_id,
                        document_id=doc_model.document_id,
                        sequence_number=chunk.sequence_number,
                        text=chunk.text,
                        char_start=chunk.char_start,
                        char_end=chunk.char_end,
                        title=chunk.title,
                        source_publisher=chunk.source_publisher,
                        source_url=chunk.source_url,
                        publication_date=chunk.publication_date,
                        content_hash=chunk.content_hash,
                    )
                    session.add(chunk_model)
                    seeded_counts["chunks"] += 1

                session.commit()

        if seeded_counts["documents"] > 0 or seeded_counts["chunks"] > 0:
            logger.info(
                "Seeded %d demo documents and %d passage chunks.",
                seeded_counts["documents"],
                seeded_counts["chunks"],
            )

        # Ensure evidence vector index is synchronized with database chunks
        from public_health_sentinel.documents.index import ensure_evidence_index_initialized
        ensure_evidence_index_initialized(session=session)

    except Exception as exc:
        logger.error("Failed to seed demo data: %s", exc, exc_info=True)
        session.rollback()
    finally:
        if should_close:
            session.close()

    return seeded_counts
