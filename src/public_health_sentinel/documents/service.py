"""Service layer for Phase 6A reference document ingestion, validation, and retrieval."""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from public_health_sentinel.config import get_config
from public_health_sentinel.db.models import DocumentMetadataModel

SUPPORTED_FORMATS: frozenset[str] = frozenset({"txt", "md"})


class DocumentValidationError(ValueError):
    """Raised when a document violates format, size, or path safety constraints."""
    pass


class DocumentSizeLimitExceededError(DocumentValidationError):
    """Raised when document content exceeds the configured maximum byte size."""
    pass


def sanitize_and_validate_filename(filename: str) -> tuple[str, str]:
    """Validate filename for path traversal, unsafe characters, and format extension.

    Args:
        filename: Raw user-supplied filename.

    Returns:
        Tuple of (sanitized_basename, doc_format).

    Raises:
        DocumentValidationError: If filename contains path traversal or unsupported format.
    """
    if not filename or not filename.strip():
        raise DocumentValidationError("Filename cannot be empty.")

    cleaned_name = filename.strip()

    # Reject path traversal patterns and directory separators
    if ".." in cleaned_name or "/" in cleaned_name or "\\" in cleaned_name or "\0" in cleaned_name:
        raise DocumentValidationError(
            "Security violation: Filename contains path traversal sequences or directory separators."
        )

    # Disallow control characters
    if any(ord(c) < 32 for c in cleaned_name):
        raise DocumentValidationError("Filename contains invalid control characters.")

    path_obj = Path(cleaned_name)
    ext = path_obj.suffix.lower().lstrip(".")

    if not ext or ext not in SUPPORTED_FORMATS:
        supported_str = ", ".join(sorted(f".{f}" for f in SUPPORTED_FORMATS))
        raise DocumentValidationError(
            f"Unsupported document format '{path_obj.suffix}'. Supported formats are: {supported_str}"
        )

    if not path_obj.stem.strip():
        raise DocumentValidationError("Filename must have a non-empty name before the extension.")

    return path_obj.name, ext


def validate_document_content(
    content: str | bytes,
    max_size_bytes: int,
) -> tuple[str, bytes]:
    """Validate text/binary content for encoding, non-emptiness, and size limits.

    Args:
        content: Raw document string or bytes.
        max_size_bytes: Maximum permitted size in bytes.

    Returns:
        Tuple of (decoded_text, utf8_bytes).

    Raises:
        DocumentSizeLimitExceededError: If content size exceeds configured limit.
        DocumentValidationError: If content is empty or contains malformed UTF-8.
    """
    if isinstance(content, bytes):
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DocumentValidationError(
                f"Document content is not valid UTF-8 text: {exc}"
            ) from exc
        raw_bytes = content
    elif isinstance(content, str):
        text = content
        raw_bytes = content.encode("utf-8")
    else:
        raise DocumentValidationError(f"Expected str or bytes content, received {type(content).__name__}")

    if not text.strip():
        raise DocumentValidationError("Document content cannot be empty or whitespace only.")

    if len(raw_bytes) > max_size_bytes:
        raise DocumentSizeLimitExceededError(
            f"Document size ({len(raw_bytes)} bytes) exceeds the configured limit of {max_size_bytes} bytes."
        )

    return text, raw_bytes


def compute_sha256(data: bytes) -> str:
    """Compute the hexadecimal SHA-256 digest for document content."""
    return hashlib.sha256(data).hexdigest()


def extract_document_title(
    text: str,
    doc_format: str,
    fallback_filename: str,
    explicit_title: Optional[str] = None,
) -> str:
    """Extract or infer a representative document title.

    Args:
        text: Validated document text.
        doc_format: Document extension ('txt' or 'md').
        fallback_filename: Original filename to fall back to.
        explicit_title: User-provided title override if specified.

    Returns:
        Representative title string truncated to 255 characters.
    """
    if explicit_title and explicit_title.strip():
        return explicit_title.strip()[:255]

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return Path(fallback_filename).stem[:255]

    # For Markdown: scan for first H1 header '# Title'
    if doc_format == "md":
        for line in lines:
            if line.startswith("# ") and len(line) > 2:
                title_candidate = line[2:].strip()
                if title_candidate:
                    return title_candidate[:255]

    # For text documents or Markdown without H1, use first non-empty line
    first_line = lines[0]
    # Clean leading markdown markup or bullets if present
    cleaned_line = re.sub(r"^[\#\*\-\s]+", "", first_line).strip()
    if cleaned_line:
        return cleaned_line[:120]

    return Path(fallback_filename).stem[:255]


def ingest_document(
    session: Session,
    filename: str,
    content: str | bytes,
    title: Optional[str] = None,
    source_publisher: Optional[str] = None,
    source_url: Optional[str] = None,
    publication_date: Optional[date] = None,
    storage_dir: Optional[Path] = None,
    max_size_bytes: Optional[int] = None,
) -> tuple[DocumentMetadataModel, bool]:
    """Validate, persist, and register a reference document into storage.

    Args:
        session: Active SQLAlchemy session.
        filename: Original user filename (validated for safety and extension).
        content: Text or bytes payload.
        title: Optional title override.
        source_publisher: Authoring agency or publisher.
        source_url: Reference URL.
        publication_date: Original publication date.
        storage_dir: Target directory for managed raw file storage.
        max_size_bytes: Size ceiling override.

    Returns:
        Tuple of (DocumentMetadataModel, is_duplicate: bool).
        If is_duplicate is True, the existing active model is returned without duplicate file creation.

    Raises:
        DocumentValidationError: If document fails safety, format, or size constraints.
    """
    config = get_config()
    max_bytes = max_size_bytes if max_size_bytes is not None else config.max_document_size_bytes
    target_storage = storage_dir or config.data_documents_dir

    # 1. Validate filename and format
    sanitized_filename, doc_format = sanitize_and_validate_filename(filename)

    # 2. Validate content and size
    text_content, raw_bytes = validate_document_content(content, max_bytes)

    # 3. Compute cryptographic content hash
    content_hash = compute_sha256(raw_bytes)

    # 4. Check for existing active duplicate by content hash
    stmt = select(DocumentMetadataModel).where(
        DocumentMetadataModel.content_hash == content_hash,
        DocumentMetadataModel.ingestion_status == "INGESTED",
    )
    existing = session.execute(stmt).scalar_one_or_none()
    if existing is not None:
        return existing, True

    # 5. Extract metadata metrics
    doc_title = extract_document_title(
        text=text_content,
        doc_format=doc_format,
        fallback_filename=sanitized_filename,
        explicit_title=title,
    )
    doc_id = f"doc-{uuid.uuid4().hex[:12]}"
    char_count = len(text_content)
    word_count = len(text_content.split())
    doc_size = len(raw_bytes)

    # 6. Securely persist raw file to managed directory (keyed by doc_id to eliminate traversal risk)
    target_storage.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{doc_id}.{doc_format}"
    physical_path = target_storage / stored_filename
    physical_path.write_bytes(raw_bytes)

    # Relative stored path for database record
    stored_rel_path = f"data/documents/{stored_filename}"

    # 7. Create database model
    model = DocumentMetadataModel(
        document_id=doc_id,
        filename=sanitized_filename,
        title=doc_title,
        doc_format=doc_format,
        content_hash=content_hash,
        source_publisher=source_publisher.strip() if source_publisher else None,
        source_url=source_url.strip() if source_url else None,
        publication_date=publication_date,
        document_size_bytes=doc_size,
        character_count=char_count,
        word_count=word_count,
        ingestion_status="INGESTED",
        stored_path=stored_rel_path,
        error_message=None,
        ingestion_timestamp=datetime.now(timezone.utc),
    )
    session.add(model)
    session.flush()

    return model, False


def ingest_document_from_file(
    session: Session,
    file_path: Path,
    title: Optional[str] = None,
    source_publisher: Optional[str] = None,
    source_url: Optional[str] = None,
    publication_date: Optional[date] = None,
    storage_dir: Optional[Path] = None,
    max_size_bytes: Optional[int] = None,
) -> tuple[DocumentMetadataModel, bool]:
    """Ingest a reference document directly from a local filesystem path.

    Args:
        session: Active SQLAlchemy session.
        file_path: Path to the target .txt or .md file.
        title: Optional title.
        source_publisher: Authoring organization.
        source_url: Source link.
        publication_date: Document date.
        storage_dir: Optional storage directory override.
        max_size_bytes: Optional byte limit override.

    Returns:
        Tuple of (DocumentMetadataModel, is_duplicate).
    """
    if not file_path.exists():
        raise DocumentValidationError(f"File not found: {file_path}")

    raw_bytes = file_path.read_bytes()
    return ingest_document(
        session=session,
        filename=file_path.name,
        content=raw_bytes,
        title=title,
        source_publisher=source_publisher,
        source_url=source_url,
        publication_date=publication_date,
        storage_dir=storage_dir,
        max_size_bytes=max_size_bytes,
    )


def get_document_by_id(session: Session, document_id: str) -> Optional[DocumentMetadataModel]:
    """Retrieve document metadata by public document identifier."""
    stmt = select(DocumentMetadataModel).where(DocumentMetadataModel.document_id == document_id)
    return session.execute(stmt).scalar_one_or_none()


def list_documents(
    session: Session,
    doc_format: Optional[str] = None,
    source_publisher: Optional[str] = None,
    ingestion_status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[DocumentMetadataModel], int]:
    """Query paginated document metadata records with optional filtering."""
    query = select(DocumentMetadataModel)

    if doc_format is not None:
        query = query.where(DocumentMetadataModel.doc_format == doc_format.lower())
    if source_publisher is not None:
        query = query.where(DocumentMetadataModel.source_publisher == source_publisher)
    if ingestion_status is not None:
        query = query.where(DocumentMetadataModel.ingestion_status == ingestion_status.upper())

    count_stmt = select(func.count()).select_from(query.subquery())
    total_count = session.execute(count_stmt).scalar() or 0

    paged_stmt = (
        query.order_by(DocumentMetadataModel.ingestion_timestamp.desc())
        .limit(limit)
        .offset(offset)
    )
    records = list(session.execute(paged_stmt).scalars().all())
    return records, total_count
