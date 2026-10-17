"""Script to populate and process benchmark reference documents into PublicHealthSentinel.

Ensures the database and persistent vector index contain verified, traceable
reference protocol passages for Stage A readiness and end-to-end assistant testing.
All records are explicitly labelled with synthetic research notices.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from public_health_sentinel.config import get_config
from public_health_sentinel.db.models import DocumentMetadataModel, DocumentChunkModel
from public_health_sentinel.documents.service import ingest_document
from public_health_sentinel.documents.processor import DocumentProcessor
from public_health_sentinel.documents.index import get_vector_index

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("populate_fixtures")

FIXTURE_DOCUMENTS = [
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


def populate_and_process():
    config = get_config()
    engine = create_engine(config.database_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    processor = DocumentProcessor()
    index_mgr = get_vector_index()

    logger.info("Checking existing database documents for unchunked records...")
    existing_docs = session.scalars(select(DocumentMetadataModel)).all()
    for doc in existing_docs:
        chunk_count = session.scalar(
            select(DocumentChunkModel.id).where(DocumentChunkModel.document_id == doc.document_id)
        )
        if chunk_count is None:
            logger.info("Processing unprocessed existing document %s (%s)...", doc.document_id, doc.title)
            try:
                res = processor.process_document(session, doc.document_id)
                logger.info("Processed %s -> %d chunks created.", doc.document_id, res.chunks_created)
            except Exception as e:
                logger.warning("Failed processing existing doc %s: %s", doc.document_id, e)

    logger.info("Ingesting and processing standard synthetic fixture protocols...")
    ingested_count = 0
    for fixture in FIXTURE_DOCUMENTS:
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
            ingested_count += 1
            logger.info("Ingested new fixture doc: %s (%s)", doc_model.document_id, doc_model.title)
        
        # Always verify document is chunked & indexed
        chunk_exists = session.scalar(
            select(DocumentChunkModel.id).where(DocumentChunkModel.document_id == doc_model.document_id)
        )
        if chunk_exists is None:
            res = processor.process_document(session, doc_model.document_id)
            logger.info("Chunked & indexed %s -> %d chunks.", doc_model.document_id, res.chunks_created)

    from sqlalchemy import func
    total_chunks = session.scalar(select(func.count(DocumentChunkModel.id)))
    total_docs = session.scalar(select(func.count(DocumentMetadataModel.id)))
    logger.info("Done! Total docs: %d, Total chunks in DB: %d, Total vectors in index: %d",
                total_docs, total_chunks, index_mgr.total_vectors)

    session.close()

if __name__ == "__main__":
    populate_and_process()
