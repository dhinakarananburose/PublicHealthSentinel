"""Container initialization script for PublicHealthSentinel.

Ensures that if /app/data is mounted as a fresh, empty volume:
1. Subdirectory structure (/app/data/processed, /app/data/synthetic, etc.) is created.
2. Initial seed datasets (synthetic surveillance & mobility CSVs) are copied into /app/data
   without overwriting existing files.
3. If the SQLite database does not exist:
   - Database tables are initialized.
   - Initial synthetic surveillance observations are ingested from the seed CSV.
   - Standard benchmark reference protocols are ingested, chunked, and indexed.
4. If an existing database or data files are detected, NO DATA IS OVERWRITTEN.
"""

from __future__ import annotations

import logging
import os
import shutil
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

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
from public_health_sentinel.documents.processor import DocumentProcessor
from public_health_sentinel.documents.service import ingest_document
from public_health_sentinel.loader import load_mobility_csv, load_surveillance_csv
from scripts.populate_evidence_fixtures import FIXTURE_DOCUMENTS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("init_container")


def ensure_directories(config) -> None:
    """Create all required runtime data directories if missing."""
    dirs = [
        config.data_dir,
        config.data_raw_dir,
        config.data_processed_dir,
        config.data_synthetic_dir,
        config.data_documents_dir,
        config.data_index_dir,
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    logger.info("Runtime data directories verified at %s.", config.data_dir)


def copy_seed_files_if_missing(config, seed_dir: Path) -> None:
    """Copy seed CSV files to data volume if not already present."""
    if not seed_dir.exists():
        logger.info("Seed directory %s does not exist; skipping seed file copy.", seed_dir)
        return

    # Seed processed data
    seed_processed = seed_dir / "processed"
    if seed_processed.exists():
        for src_file in seed_processed.glob("*.csv"):
            dst_file = config.data_processed_dir / src_file.name
            if not dst_file.exists():
                shutil.copy2(src_file, dst_file)
                logger.info("Copied seed processed file: %s -> %s", src_file.name, dst_file)

    # Seed synthetic data
    seed_synthetic = seed_dir / "synthetic"
    if seed_synthetic.exists():
        for src_file in seed_synthetic.glob("*.csv"):
            dst_file = config.data_synthetic_dir / src_file.name
            if not dst_file.exists():
                shutil.copy2(src_file, dst_file)
                logger.info("Copied seed synthetic file: %s -> %s", src_file.name, dst_file)


def initialize_database_if_missing(config) -> None:
    """Initialize database schemas, surveillance data, and benchmark evidence if DB does not exist."""
    db_url = config.database_url
    if db_url.startswith("sqlite"):
        db_path_str = db_url.replace("sqlite:///", "")
        db_path = Path(db_path_str)
        if db_path.exists() and db_path.stat().st_size > 0:
            logger.info("Existing database detected at %s. Preserving existing user data.", db_path)
            return

    logger.info("Initializing new database at %s...", db_url)
    engine = get_engine()
    init_db(engine)

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        # Check if surveillance table already has records
        obs_count = session.scalar(select(func.count(SurveillanceObservationModel.id)))
        if obs_count == 0:
            seed_surv_csv = config.data_processed_dir / "surveillance_observations.csv"
            if seed_surv_csv.exists():
                logger.info("Populating initial surveillance observations from %s...", seed_surv_csv)
                df = load_surveillance_csv(seed_surv_csv)
                raw_records = df.to_dict(orient="records")
                records = [{k: (None if pd.isna(v) else v) for k, v in row.items()} for row in raw_records]
                inserted, _ = ingest_surveillance_observations(session, records)
                session.commit()
                logger.info("Successfully ingested %d synthetic surveillance observations.", inserted)

        # Check if mobility table already has records
        mob_count = session.scalar(select(func.count(MobilityIndicatorModel.id)))
        if mob_count == 0:
            seed_mob_csv = config.data_processed_dir / "mobility_indicators.csv"
            if not seed_mob_csv.exists():
                seed_mob_csv = Path("/app/seed_data/processed/mobility_indicators.csv")
            if seed_mob_csv.exists():
                logger.info("Populating initial mobility indicators from %s...", seed_mob_csv)
                df_mob = load_mobility_csv(seed_mob_csv)
                raw_records = df_mob.to_dict(orient="records")
                records = [{k: (None if pd.isna(v) else v) for k, v in row.items()} for row in raw_records]
                inserted_mob, _ = ingest_mobility_indicators(session, records)
                session.commit()
                logger.info("Successfully ingested %d synthetic mobility indicators.", inserted_mob)

        # Check if anomaly detection results table already has records
        anom_count = session.scalar(select(func.count(AnomalyDetectionResultModel.id)))
        if anom_count == 0:
            seed_anom_csv = config.data_processed_dir / "detection_results.csv"
            if not seed_anom_csv.exists():
                seed_anom_csv = Path("/app/seed_data/processed/detection_results.csv")
            if seed_anom_csv.exists():
                logger.info("Populating initial anomaly detection results from %s...", seed_anom_csv)
                df_anom = pd.read_csv(seed_anom_csv)
                raw_records = df_anom.to_dict(orient="records")
                records = [{k: (None if pd.isna(v) else v) for k, v in row.items()} for row in raw_records]
                inserted_anom, _ = persist_anomaly_results(session, records)
                session.commit()
                logger.info("Successfully ingested %d anomaly detection results.", inserted_anom)

        # Ingest and index standard benchmark fixture documents if document metadata is empty
        doc_count = session.scalar(select(func.count(DocumentMetadataModel.id)))
        if doc_count == 0:
            logger.info("Ingesting and indexing %d benchmark reference documents...", len(FIXTURE_DOCUMENTS))
            processor = DocumentProcessor()
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
                    processor.process_document(session, doc_model.document_id)

            session.commit()
            total_chunks = session.scalar(select(func.count(DocumentChunkModel.id)))
            logger.info("Benchmark evidence indexing complete: %d chunks created.", total_chunks)

    except Exception as exc:
        logger.error("Error during initial data population: %s", exc, exc_info=True)
        session.rollback()
    finally:
        session.close()


def main() -> None:
    """Main container initialization routine."""
    config = get_config()
    ensure_directories(config)
    seed_dir = Path("/app/seed_data")
    copy_seed_files_if_missing(config, seed_dir)
    initialize_database_if_missing(config)
    logger.info("Container data initialization completed successfully.")


if __name__ == "__main__":
    main()
