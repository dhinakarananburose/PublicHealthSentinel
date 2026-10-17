"""Configuration management for PublicHealthSentinel.

Loads configuration from environment variables with safe defaults.
Contains NO credentials, secrets, or hard-coded production values.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class SentinelConfig(BaseModel):
    """Runtime configuration settings for the sentinel system."""

    model_config = ConfigDict(frozen=True)

    app_name: str = Field(
        default="PublicHealthSentinel",
        description="Application identifier.",
    )
    app_env: Literal["development", "testing", "staging", "production"] = Field(
        default="development",
        description="Deployment environment.",
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging threshold level.",
    )
    debug: bool = Field(
        default=True,
        description="Enable debug mode and verbose tracebacks.",
    )
    data_dir: Path = Field(
        default=Path("data"),
        description="Root directory for local data artifacts.",
    )
    data_raw_dir: Path = Field(
        default=Path("data/raw"),
        description="Directory for raw ingested observations.",
    )
    data_processed_dir: Path = Field(
        default=Path("data/processed"),
        description="Directory for harmonized surveillance data.",
    )
    data_synthetic_dir: Path = Field(
        default=Path("data/synthetic"),
        description="Directory for generated benchmark synthetic datasets.",
    )
    data_documents_dir: Path = Field(
        default=Path("data/documents"),
        description="Directory for raw ingested reference documents.",
    )
    data_index_dir: Path = Field(
        default=Path("data/index"),
        description="Directory for persisted semantic vector indexes.",
    )
    chunk_target_size: int = Field(
        default=800,
        description="Target character size per passage chunk (~800 characters).",
    )
    chunk_overlap: int = Field(
        default=120,
        description="Character overlap between consecutive chunks (~120 characters).",
    )
    embedding_model_name: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="Hugging Face local sentence-transformer model identifier.",
    )
    embedding_dimension: int = Field(
        default=384,
        description="Expected dimensional size of the local embedding vector.",
    )
    embedding_batch_size: int = Field(
        default=32,
        description="Batch size for parallel embedding encoding.",
    )
    embedding_provider: str = Field(
        default="sentence_transformer",
        description="Embedding provider strategy ('sentence_transformer' or 'mock').",
    )
    max_document_size_bytes: int = Field(
        default=5 * 1024 * 1024,
        description="Maximum permitted reference document size in bytes (default: 5MB).",
    )
    database_url: str = Field(
        default="sqlite:///./data/public_health_sentinel.db",
        description="SQLAlchemy database connection URI (SQLite default for testing/local, PostgreSQL for server).",
    )
    db_echo: bool = Field(
        default=False,
        description="Log SQL statements emitted by SQLAlchemy.",
    )
    demo_mode: bool = Field(
        default=False,
        description="Enable lightweight public demonstration mode for free-tier cloud deployment.",
    )
    generation_provider: Literal["ollama", "mock", "demo"] = Field(
        default="ollama",
        description="LLM generation provider strategy ('ollama', 'mock', or 'demo').",
    )
    ollama_host: str = Field(
        default="http://localhost:11434",
        description="HTTP base URL for local Ollama server.",
    )
    ollama_model: str = Field(
        default="llama3.2:latest",
        description="Local Ollama model identifier (e.g. 'llama3.2:latest', 'phi3:mini').",
    )
    ollama_timeout_seconds: float = Field(
        default=90.0,
        description="Request timeout in seconds for LLM generation.",
    )
    ollama_num_predict: Optional[int] = Field(
        default=40,
        description="Maximum output tokens for Ollama generation (num_predict).",
    )
    ollama_keep_alive: str = Field(
        default="60m",
        description="Ollama keep_alive duration string (e.g. '60m', '5m', or '0' to disable).",
    )
    assistant_min_similarity_cutoff: float = Field(
        default=0.30,
        description="Minimum retrieval cosine similarity required for passage inclusion.",
    )
    assistant_max_context_passages: int = Field(
        default=2,
        description="Maximum number of evidence passages provided in prompt context.",
    )
    assistant_concise_num_predict: int = Field(
        default=20,
        description="Token budget for concise response mode (num_predict).",
    )
    assistant_detailed_num_predict: int = Field(
        default=40,
        description="Token budget for detailed response mode (num_predict).",
    )
    assistant_fallback_on_timeout: bool = Field(
        default=True,
        description="When true, fallback to returning retrieved source evidence if LLM generation times out.",
    )
    assistant_max_question_length: int = Field(
        default=1000,
        description="Maximum character length of user inquiry.",
    )
    api_host: str = Field(
        default="127.0.0.1",
        description="Host interface for FastAPI service binding.",
    )
    api_port: int = Field(
        default=8000,
        description="Port for FastAPI service binding.",
    )
    api_title: str = Field(
        default="PublicHealthSentinel API",
        description="Title for OpenAPI and Swagger documentation.",
    )
    api_version: str = Field(
        default="v1",
        description="API semantic version.",
    )


def _str_to_bool(value: str | bool) -> bool:
    """Safely convert truthy/falsy environment strings to boolean."""
    if isinstance(value, bool):
        return value
    return value.strip().lower() in {"true", "1", "t", "yes", "y"}


@lru_cache(maxsize=1)
def get_config() -> SentinelConfig:
    """Retrieve application configuration cached for the process lifetime.

    Environment variables override default settings.
    """
    raw_env = os.getenv("APP_ENV", "development").lower()
    valid_env = raw_env if raw_env in {"development", "testing", "staging", "production"} else "development"

    raw_log = os.getenv("LOG_LEVEL", "INFO").upper()
    valid_log = raw_log if raw_log in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"} else "INFO"

    data_dir = Path(os.getenv("DATA_DIR", "data"))

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        # Check individual postgres parameters if provided
        pg_user = os.getenv("DB_USER")
        pg_pass = os.getenv("DB_PASSWORD")
        pg_host = os.getenv("DB_HOST")
        pg_port = os.getenv("DB_PORT", "5432")
        pg_name = os.getenv("DB_NAME")
        if pg_user and pg_host and pg_name:
            auth = f"{pg_user}:{pg_pass}@" if pg_pass else f"{pg_user}@"
            db_url = f"postgresql+psycopg2://{auth}{pg_host}:{pg_port}/{pg_name}"
        else:
            db_url = "sqlite:///./data/public_health_sentinel.db"

    demo_mode = _str_to_bool(os.getenv("DEMO_MODE") or os.getenv("SENTINEL_DEMO_MODE", "false"))
    default_gen_provider = "demo" if demo_mode else "ollama"
    default_emb_provider = "tfidf" if demo_mode else "sentence_transformer"

    return SentinelConfig(
        app_name=os.getenv("APP_NAME", "PublicHealthSentinel"),
        app_env=valid_env,  # type: ignore[arg-type]
        log_level=valid_log,  # type: ignore[arg-type]
        debug=_str_to_bool(os.getenv("DEBUG", "false" if valid_env in {"production", "staging"} or demo_mode else "true")),
        demo_mode=demo_mode,
        data_dir=data_dir,
        data_raw_dir=Path(os.getenv("DATA_RAW_DIR", str(data_dir / "raw"))),
        data_processed_dir=Path(os.getenv("DATA_PROCESSED_DIR", str(data_dir / "processed"))),
        data_synthetic_dir=Path(os.getenv("DATA_SYNTHETIC_DIR", str(data_dir / "synthetic"))),
        data_documents_dir=Path(os.getenv("DATA_DOCUMENTS_DIR", str(data_dir / "documents"))),
        data_index_dir=Path(os.getenv("DATA_INDEX_DIR", str(data_dir / "index"))),
        chunk_target_size=int(os.getenv("CHUNK_TARGET_SIZE", "800")),
        chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "120")),
        embedding_model_name=os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2"),
        embedding_dimension=int(os.getenv("EMBEDDING_DIMENSION", "384")),
        embedding_batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", "32")),
        embedding_provider=os.getenv("EMBEDDING_PROVIDER", os.getenv("SENTINEL_EMBEDDING_PROVIDER", default_emb_provider)),
        max_document_size_bytes=int(os.getenv("MAX_DOCUMENT_SIZE_BYTES", str(5 * 1024 * 1024))),
        database_url=db_url,
        db_echo=_str_to_bool(os.getenv("DB_ECHO", "false")),
        generation_provider=os.getenv("GENERATION_PROVIDER", os.getenv("SENTINEL_GENERATION_PROVIDER", default_gen_provider)),  # type: ignore[arg-type]
        ollama_host=(os.getenv("OLLAMA_HOST") or os.getenv("SENTINEL_OLLAMA_HOST", "http://localhost:11434")).rstrip("/"),
        ollama_model=os.getenv("OLLAMA_MODEL") or os.getenv("SENTINEL_OLLAMA_MODEL", "llama3.2:latest"),
        ollama_timeout_seconds=float(
            os.getenv("OLLAMA_TIMEOUT_SECONDS") or os.getenv("SENTINEL_OLLAMA_TIMEOUT_SECONDS", "90.0")
        ),
        ollama_num_predict=(
            int(os.getenv("OLLAMA_NUM_PREDICT") or os.getenv("SENTINEL_OLLAMA_NUM_PREDICT"))
            if (os.getenv("OLLAMA_NUM_PREDICT") or os.getenv("SENTINEL_OLLAMA_NUM_PREDICT"))
            else 40
        ),
        ollama_keep_alive=os.getenv("OLLAMA_KEEP_ALIVE") or os.getenv("SENTINEL_OLLAMA_KEEP_ALIVE", "60m"),
        assistant_min_similarity_cutoff=float(os.getenv("ASSISTANT_MIN_SIMILARITY_CUTOFF", "0.30")),
        assistant_max_context_passages=int(
            os.getenv("ASSISTANT_MAX_CONTEXT_PASSAGES") or os.getenv("SENTINEL_ASSISTANT_MAX_CONTEXT_PASSAGES", "2")
        ),
        assistant_max_question_length=int(os.getenv("ASSISTANT_MAX_QUESTION_LENGTH", "1000")),
        api_host=os.getenv("API_HOST", "127.0.0.1"),
        api_port=int(os.getenv("API_PORT", "8000")),
        api_title=os.getenv("API_TITLE", "PublicHealthSentinel API"),
        api_version=os.getenv("API_VERSION", "v1"),
    )
