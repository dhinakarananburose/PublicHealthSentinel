"""Automated test suite for Phase 6A: Reference Document Ingestion Foundation.

Covers:
1. Successful text document ingestion (.txt).
2. Successful Markdown document ingestion (.md).
3. Metadata and provenance preservation (title, publisher, URL, publication date, word/char counts).
4. Content hash generation (deterministic SHA-256).
5. Duplicate content detection (no duplicate active storage, 409 response code).
6. Unsupported file extension rejection (e.g., .pdf, .docx, .py).
7. Empty or whitespace document rejection (400 Bad Request).
8. Oversized document rejection (413 Request Entity Too Large).
9. Unicode and multi-language content preservation.
10. Missing document retrieval (404 Not Found).
11. Document metadata pagination and filtering (by format, publisher, status).
12. Database transaction failure and rollback handling.
13. Filename and path traversal protection (rejection of '..', '/', '\\').
14. API response schemas and HTTP status codes.
15. Ingest from local filesystem path via service helper.
"""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from public_health_sentinel.api.app import app
from public_health_sentinel.db.models import Base, DocumentMetadataModel
from public_health_sentinel.db.session import get_db_session
from public_health_sentinel.documents.schemas import DocumentIngestRequest
from public_health_sentinel.documents.service import (
    DocumentSizeLimitExceededError,
    DocumentValidationError,
    compute_sha256,
    extract_document_title,
    get_document_by_id,
    ingest_document,
    ingest_document_from_file,
    list_documents,
    sanitize_and_validate_filename,
    validate_document_content,
)


@pytest.fixture
def test_db_session():
    """Create an isolated in-memory SQLite database session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = session_factory()

    yield session

    session.close()
    engine.dispose()


@pytest.fixture
def client(test_db_session: Session):
    """FastAPI TestClient with overridden get_db_session dependency."""
    def _override_db_session():
        try:
            yield test_db_session
            test_db_session.commit()
        except Exception:
            test_db_session.rollback()
            raise

    app.dependency_overrides[get_db_session] = _override_db_session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestDocumentValidationAndHashing:
    """Tests for unit-level document content validation, filename sanitation, and hashing."""

    def test_sanitize_and_validate_valid_filenames(self):
        """Verify valid .txt and .md filenames are accepted."""
        name, fmt = sanitize_and_validate_filename("cdc_guidelines.md")
        assert name == "cdc_guidelines.md"
        assert fmt == "md"

        name_txt, fmt_txt = sanitize_and_validate_filename("case_definitions.txt")
        assert name_txt == "case_definitions.txt"
        assert fmt_txt == "txt"

    def test_reject_unsupported_extensions(self):
        """Verify unsupported extensions (.pdf, .exe, .py) raise DocumentValidationError."""
        with pytest.raises(DocumentValidationError, match="Unsupported document format"):
            sanitize_and_validate_filename("guidelines.pdf")

        with pytest.raises(DocumentValidationError, match="Unsupported document format"):
            sanitize_and_validate_filename("script.py")

        with pytest.raises(DocumentValidationError, match="Unsupported document format"):
            sanitize_and_validate_filename("no_extension")

    def test_path_traversal_attempts_rejected(self):
        """Verify filenames with directory traversal sequences are rejected."""
        with pytest.raises(DocumentValidationError, match="path traversal"):
            sanitize_and_validate_filename("../../etc/passwd.txt")

        with pytest.raises(DocumentValidationError, match="path traversal"):
            sanitize_and_validate_filename("..\\windows\\system32\\calc.md")

        with pytest.raises(DocumentValidationError, match="path traversal"):
            sanitize_and_validate_filename("/root/secret.txt")

    def test_empty_filename_rejected(self):
        """Verify blank filenames are rejected."""
        with pytest.raises(DocumentValidationError, match="Filename cannot be empty"):
            sanitize_and_validate_filename("   ")

    def test_validate_content_empty_rejected(self):
        """Verify empty or whitespace-only content is rejected."""
        with pytest.raises(DocumentValidationError, match="cannot be empty"):
            validate_document_content("", max_size_bytes=1000)

        with pytest.raises(DocumentValidationError, match="cannot be empty"):
            validate_document_content("   \n\t  ", max_size_bytes=1000)

    def test_validate_content_oversized_rejected(self):
        """Verify content exceeding max_size_bytes raises DocumentSizeLimitExceededError."""
        large_content = "A" * 1500
        with pytest.raises(DocumentSizeLimitExceededError, match="exceeds the configured limit"):
            validate_document_content(large_content, max_size_bytes=1000)

    def test_unicode_preservation_and_malformed_bytes(self):
        """Verify Unicode content is preserved and malformed UTF-8 is rejected."""
        unicode_text = "Epidemiología: Señal de alerta 🚨 en Región Médica (α=0.05)"
        decoded, raw_bytes = validate_document_content(unicode_text, max_size_bytes=1000)
        assert decoded == unicode_text
        assert "🚨" in decoded

        # Malformed bytes
        bad_bytes = b"\xff\xfe\x00\x00invalid_utf8"
        with pytest.raises(DocumentValidationError, match="not valid UTF-8"):
            validate_document_content(bad_bytes, max_size_bytes=1000)

    def test_sha256_content_hash_deterministic(self):
        """Verify SHA-256 computation matches standard hashlib output."""
        content = b"Surveillance Case Definition for Acute Respiratory Infection"
        expected = hashlib.sha256(content).hexdigest()
        assert compute_sha256(content) == expected

    def test_extract_document_title(self):
        """Verify title extraction priorities for Markdown and plain text."""
        md_text = "# Syndromic Surveillance Protocol\n\nThis document outlines definitions."
        assert extract_document_title(md_text, "md", "default.md") == "Syndromic Surveillance Protocol"

        txt_text = "Case Reporting Standards 2026\nSecond line details."
        assert extract_document_title(txt_text, "txt", "default.txt") == "Case Reporting Standards 2026"

        # Explicit override
        assert extract_document_title(md_text, "md", "default.md", explicit_title="Custom Title") == "Custom Title"


class TestDocumentServiceIngestion:
    """Tests for document service layer registration, storage, and duplicate detection."""

    def test_ingest_text_document_success(self, test_db_session: Session, tmp_path: Path):
        """Verify successful ingestion of a text document with metadata."""
        content = "Clinical case definitions for syndromic febrile clusters in emergency departments."
        doc, is_dup = ingest_document(
            session=test_db_session,
            filename="febrile_definition.txt",
            content=content,
            title="Febrile Case Definition",
            source_publisher="WHO",
            source_url="https://who.int/surveillance/febrile",
            publication_date=date(2024, 6, 1),
            storage_dir=tmp_path,
        )
        test_db_session.commit()

        assert is_dup is False
        assert doc.document_id.startswith("doc-")
        assert doc.filename == "febrile_definition.txt"
        assert doc.doc_format == "txt"
        assert doc.source_publisher == "WHO"
        assert doc.publication_date == date(2024, 6, 1)
        assert doc.ingestion_status == "INGESTED"
        assert doc.document_size_bytes == len(content.encode("utf-8"))
        assert doc.word_count == len(content.split())
        assert doc.content_hash == hashlib.sha256(content.encode("utf-8")).hexdigest()

        # Check physical file creation
        stored_file = tmp_path / f"{doc.document_id}.txt"
        assert stored_file.exists()
        assert stored_file.read_text(encoding="utf-8") == content

    def test_ingest_markdown_document_success(self, test_db_session: Session, tmp_path: Path):
        """Verify successful ingestion of a Markdown document with H1 title extraction."""
        content = "# Respiratory Surge Protocol\n\nGuidelines for threshold evaluation."
        doc, is_dup = ingest_document(
            session=test_db_session,
            filename="respiratory_protocol.md",
            content=content,
            storage_dir=tmp_path,
        )
        test_db_session.commit()

        assert is_dup is False
        assert doc.title == "Respiratory Surge Protocol"
        assert doc.doc_format == "md"

    def test_duplicate_content_detection(self, test_db_session: Session, tmp_path: Path):
        """Verify identical content is detected by content hash and does not duplicate files."""
        content = "Fixed standard public health advisory notice."
        doc1, is_dup1 = ingest_document(
            session=test_db_session,
            filename="notice_v1.txt",
            content=content,
            storage_dir=tmp_path,
        )
        test_db_session.commit()
        assert is_dup1 is False

        # Attempt to ingest exact same content with different filename
        doc2, is_dup2 = ingest_document(
            session=test_db_session,
            filename="notice_v2.txt",
            content=content,
            storage_dir=tmp_path,
        )
        assert is_dup2 is True
        assert doc2.document_id == doc1.document_id
        assert doc2.content_hash == doc1.content_hash

        # Verify only one physical file exists in storage_dir
        files = list(tmp_path.glob("*.txt"))
        assert len(files) == 1

    def test_ingest_from_file_path(self, test_db_session: Session, tmp_path: Path):
        """Verify ingest_document_from_file helper ingests local files correctly."""
        src_file = tmp_path / "local_protocol.md"
        src_file.write_text("# Local City Protocol\nSurveillance rules.", encoding="utf-8")

        target_dir = tmp_path / "managed_storage"
        doc, is_dup = ingest_document_from_file(
            session=test_db_session,
            file_path=src_file,
            source_publisher="City Health",
            storage_dir=target_dir,
        )
        test_db_session.commit()

        assert is_dup is False
        assert doc.title == "Local City Protocol"
        assert doc.source_publisher == "City Health"


class TestDocumentAPIEndpoints:
    """Tests for Phase 6A FastAPI REST endpoints (/api/v1/documents)."""

    def test_api_ingest_text_document_success(self, client: TestClient):
        """Verify POST /api/v1/documents/ingest returns 201 Created for valid text document."""
        payload = {
            "filename": "clinical_alert.txt",
            "content": "Alert: Unusual cluster of gastrointestinal symptoms detected in ambulatory care.",
            "title": "Clinical Alert 2026-01",
            "source_publisher": "County Public Health",
            "source_url": "https://health.county.gov/alerts/2026-01",
            "publication_date": "2026-02-15",
        }
        response = client.post("/api/v1/documents/ingest", json=payload)
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        assert data["status"] == "INGESTED"
        assert data["filename"] == "clinical_alert.txt"
        assert data["doc_format"] == "txt"
        assert data["title"] == "Clinical Alert 2026-01"
        assert "document_id" in data
        assert "content_hash" in data
        assert "SYNTHETIC-DATA NOTICE" in data["synthetic_experiment_notice"]

    def test_api_ingest_markdown_document_success(self, client: TestClient):
        """Verify POST /api/v1/documents/ingest returns 201 for Markdown with extracted title."""
        payload = {
            "filename": "syndromic_methods.md",
            "content": "# Automated Syndromic Surveillance Methods\nComprehensive overview of MAD and EWMA.",
        }
        response = client.post("/api/v1/documents/ingest", json=payload)
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        assert data["title"] == "Automated Syndromic Surveillance Methods"
        assert data["doc_format"] == "md"

    def test_api_ingest_duplicate_returns_409(self, client: TestClient):
        """Verify submitting identical document content returns HTTP 409 Conflict."""
        payload = {
            "filename": "original_doc.txt",
            "content": "Identical epidemiological case definition text for duplicate testing.",
        }
        r1 = client.post("/api/v1/documents/ingest", json=payload)
        assert r1.status_code == status.HTTP_201_CREATED

        # Second submission of identical content
        r2 = client.post("/api/v1/documents/ingest", json=payload)
        assert r2.status_code == status.HTTP_409_CONFLICT
        data2 = r2.json()
        assert data2["status"] == "DUPLICATE"
        assert data2["document_id"] == r1.json()["document_id"]
        assert "already ingested" in data2["message"]

    def test_api_ingest_unsupported_format_returns_400(self, client: TestClient):
        """Verify unsupported extensions return HTTP 400 Bad Request."""
        payload = {
            "filename": "report.pdf",
            "content": "PDF binary placeholder",
        }
        response = client.post("/api/v1/documents/ingest", json=payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Unsupported document format" in response.json()["message"]

    def test_api_ingest_empty_content_returns_400(self, client: TestClient):
        """Verify empty content returns HTTP 400 Bad Request."""
        payload = {
            "filename": "empty.txt",
            "content": "     \n\t   ",
        }
        response = client.post("/api/v1/documents/ingest", json=payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "cannot be empty" in response.json()["message"]

    def test_api_ingest_oversized_document_returns_413(self, client: TestClient):
        """Verify oversized document returns HTTP 413 Payload Too Large."""
        payload = {
            "filename": "huge.txt",
            "content": "A" * 500,
        }
        from public_health_sentinel.config import get_config
        with patch("public_health_sentinel.documents.service.get_config") as mock_cfg:
            mock_cfg.return_value = get_config().model_copy(update={"max_document_size_bytes": 200})
            response = client.post("/api/v1/documents/ingest", json=payload)
            assert response.status_code == 413
            assert "exceeds" in response.json()["message"]

    def test_api_ingest_path_traversal_returns_400(self, client: TestClient):
        """Verify path traversal sequences in filename are rejected with 400."""
        payload = {
            "filename": "../../secret.txt",
            "content": "Malicious payload attempt",
        }
        response = client.post("/api/v1/documents/ingest", json=payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "path traversal" in response.json()["message"]

    def test_api_get_document_by_id_success(self, client: TestClient):
        """Verify GET /api/v1/documents/{document_id} retrieves registered metadata."""
        ingest_payload = {
            "filename": "guideline.md",
            "content": "# State Reporting Protocol\nMandatory reporting criteria.",
            "source_publisher": "State DOH",
        }
        ingest_resp = client.post("/api/v1/documents/ingest", json=ingest_payload)
        doc_id = ingest_resp.json()["document_id"]

        get_resp = client.get(f"/api/v1/documents/{doc_id}")
        assert get_resp.status_code == status.HTTP_200_OK
        data = get_resp.json()

        assert data["document_id"] == doc_id
        assert data["title"] == "State Reporting Protocol"
        assert data["source_publisher"] == "State DOH"
        assert data["doc_format"] == "md"
        assert data["ingestion_status"] == "INGESTED"
        assert "SYNTHETIC-DATA NOTICE" in data["synthetic_experiment_notice"]

    def test_api_get_document_missing_returns_404(self, client: TestClient):
        """Verify GET /api/v1/documents/{document_id} returns 404 for unknown IDs."""
        response = client.get("/api/v1/documents/doc-nonexistent-123")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["message"]

    def test_api_list_documents_pagination_and_filtering(self, client: TestClient):
        """Verify GET /api/v1/documents pagination and format/publisher filters."""
        # Ingest 3 distinct documents
        for i in range(1, 4):
            client.post(
                "/api/v1/documents/ingest",
                json={
                    "filename": f"protocol_{i}.{'md' if i % 2 == 1 else 'txt'}",
                    "content": f"# Protocol {i}\nSpecific details for window {i}.",
                    "source_publisher": "CDC" if i <= 2 else "WHO",
                },
            )

        # Unfiltered list
        all_resp = client.get("/api/v1/documents")
        assert all_resp.status_code == status.HTTP_200_OK
        all_data = all_resp.json()
        assert all_data["total"] == 3
        assert len(all_data["items"]) == 3

        # Filter by format
        md_resp = client.get("/api/v1/documents?doc_format=md")
        assert md_resp.status_code == status.HTTP_200_OK
        md_data = md_resp.json()
        assert md_data["total"] == 2
        for item in md_data["items"]:
            assert item["doc_format"] == "md"

        # Filter by publisher
        who_resp = client.get("/api/v1/documents?source_publisher=WHO")
        assert who_resp.status_code == status.HTTP_200_OK
        assert who_resp.json()["total"] == 1

        # Pagination: 2 items per page
        page1_resp = client.get("/api/v1/documents?page=1&page_size=2")
        assert page1_resp.status_code == status.HTTP_200_OK
        page1_data = page1_resp.json()
        assert page1_data["total"] == 3
        assert len(page1_data["items"]) == 2
        assert page1_data["total_pages"] == 2

        page2_resp = client.get("/api/v1/documents?page=2&page_size=2")
        assert page2_resp.status_code == status.HTTP_200_OK
        assert len(page2_resp.json()["items"]) == 1

    def test_api_database_transaction_failure_handling(self, client: TestClient):
        """Verify database exception during document ingestion returns 500 without leaking details."""
        with patch("public_health_sentinel.documents.service.Session.add") as mock_add:
            mock_add.side_effect = RuntimeError("Database I/O write error")
            payload = {
                "filename": "failing_doc.txt",
                "content": "Valid content that encounters a simulated database failure.",
            }
            response = client.post("/api/v1/documents/ingest", json=payload)
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            body = response.json()
            assert body["error"] is True
            assert "An internal server error occurred" in body["message"]
            assert "Database I/O" not in str(body)
