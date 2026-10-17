"""Database session and engine management for PublicHealthSentinel.

Provides:
- Configurable SQLAlchemy engine with connection health validation (pool_pre_ping)
- Thread-safe session factories
- Generator context-manager for transactional database sessions (FastAPI dependency)
- Database schema initialization (Base.metadata.create_all)
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import Optional

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from public_health_sentinel.config import get_config
from public_health_sentinel.db.models import Base

_global_engine: Optional[Engine] = None
_global_session_factory: Optional[sessionmaker[Session]] = None


def get_engine(database_url: Optional[str] = None, echo: Optional[bool] = None) -> Engine:
    """Retrieve or construct the SQLAlchemy Engine.

    Args:
        database_url: Optional connection string override. Defaults to SentinelConfig.database_url.
        echo: Optional boolean to enable SQL query logging. Defaults to SentinelConfig.db_echo.

    Returns:
        SQLAlchemy Engine instance.
    """
    global _global_engine

    config = get_config()
    target_url = database_url or config.database_url
    target_echo = echo if echo is not None else config.db_echo

    # Return cached global engine if parameters match default
    if _global_engine is not None and database_url is None and echo is None:
        return _global_engine

    connect_args = {}
    if target_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        connect_args["timeout"] = 30.0
        # Ensure parent directory exists for file-based SQLite
        if not target_url.startswith("sqlite:///:memory:") and "///" in target_url:
            db_path_str = target_url.split("///")[-1]
            db_path = Path(db_path_str)
            db_path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        target_url,
        echo=target_echo,
        connect_args=connect_args,
        pool_pre_ping=True,
    )

    if target_url.startswith("sqlite") and not target_url.startswith("sqlite:///:memory:"):
        from sqlalchemy import event

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragmas(dbapi_conn, _record):  # type: ignore[no-untyped-def]
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()

    if database_url is None and echo is None:
        _global_engine = engine

    return engine


def get_session_factory(engine: Optional[Engine] = None) -> sessionmaker[Session]:
    """Retrieve or construct the sessionmaker factory."""
    global _global_session_factory

    if _global_session_factory is not None and engine is None:
        return _global_session_factory

    active_engine = engine or get_engine()
    factory = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=active_engine,
        expire_on_commit=False,
    )

    if engine is None:
        _global_session_factory = factory

    return factory


def init_db(engine: Optional[Engine] = None) -> None:
    """Initialize database schemas and create tables if they do not exist."""
    active_engine = engine or get_engine()
    Base.metadata.create_all(bind=active_engine)


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI dependency and context generator yielding a managed database session.

    Commits on clean exit, rolls back on exception, and always closes the session.
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine_for_testing() -> None:
    """Reset cached global engine and session factory (useful for isolated unit tests)."""
    global _global_engine, _global_session_factory
    if _global_engine is not None:
        _global_engine.dispose()
    _global_engine = None
    _global_session_factory = None
