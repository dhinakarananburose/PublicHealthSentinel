"""Focused unit tests for the production retrieval evaluation suite.

Uses deterministic mocked HTTP clients to verify metrics calculation,
ranking, negative rejection safeguards, timeout/error handling,
and output formatting without calling external APIs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import urllib.error
import pytest

from scripts.evaluate_production_retrieval import (
    EVALUATION_LIMITATIONS,
    PRODUCTION_EVALUATION_QUERIES,
    SYNTHETIC_DATA_NOTICE,
    EvaluationReport,
    ProductionRetrievalEvaluator,
    QueryDefinition,
)


@pytest.fixture
def sample_relevant_query() -> QueryDefinition:
    return QueryDefinition(
        query_id="test-rel-01",
        query="How does Rolling MAD calculate dispersion and handle outliers?",
        category="relevant",
        topic="Rolling MAD formula",
        expected_document_titles=[
            "Syndromic Surveillance Statistical Anomaly Detection Methodology Protocol"
        ],
    )


@pytest.fixture
def sample_negative_query() -> QueryDefinition:
    return QueryDefinition(
        query_id="test-neg-01",
        query="Explain quantum entanglement and quantum computing",
        category="negative_control",
        topic="Negative control",
        expected_document_titles=[],
    )


def test_relevant_document_retrieved_at_rank_1(sample_relevant_query):
    """Verify metrics and ranking when expected document is returned at rank 1."""
    def mock_http(url: str, payload: dict[str, Any], timeout: float):
        resp = {
            "query": payload["query"],
            "total_results": 2,
            "embedding_model": "lightweight-hashing-384",
            "items": [
                {
                    "rank": 1,
                    "chunk_id": "c1",
                    "document_id": "d1",
                    "title": "Syndromic Surveillance Statistical Anomaly Detection Methodology Protocol",
                    "similarity_score": 0.4112,
                },
                {
                    "rank": 2,
                    "chunk_id": "c2",
                    "document_id": "d2",
                    "title": "Respiratory Surge Statistical Threshold Protocol",
                    "similarity_score": 0.2500,
                },
            ],
        }
        return 200, resp, 120.0

    evaluator = ProductionRetrievalEvaluator(http_client=mock_http)
    qr = evaluator.evaluate_query(sample_relevant_query)

    assert qr.http_status == 200
    assert qr.found_rank == 1
    assert qr.retrieved_at_rank_1 is True
    assert qr.retrieved_at_rank_3 is True
    assert qr.retrieved_at_rank_5 is True
    assert qr.reciprocal_rank == 1.0
    assert qr.precision_at_1 == 1.0
    assert qr.precision_at_3 == pytest.approx(1.0 / 3.0, 0.001)
    assert qr.precision_at_5 == pytest.approx(1.0 / 5.0, 0.001)
    assert qr.negative_rejected is None
    assert qr.embedding_model == "lightweight-hashing-384"
    assert qr.error_message is None


def test_relevant_document_retrieved_at_lower_rank(sample_relevant_query):
    """Verify metrics when expected document is returned at a lower rank (rank 3)."""
    def mock_http(url: str, payload: dict[str, Any], timeout: float):
        resp = {
            "query": payload["query"],
            "total_results": 3,
            "embedding_model": "lightweight-hashing-384",
            "items": [
                {
                    "rank": 1,
                    "chunk_id": "c1",
                    "document_id": "d1",
                    "title": "Waterborne Gastrointestinal Outbreak Cluster Definition",
                    "similarity_score": 0.3500,
                },
                {
                    "rank": 2,
                    "chunk_id": "c2",
                    "document_id": "d2",
                    "title": "Respiratory Surge Statistical Threshold Protocol",
                    "similarity_score": 0.3300,
                },
                {
                    "rank": 3,
                    "chunk_id": "c3",
                    "document_id": "d3",
                    "title": "Syndromic Surveillance Statistical Anomaly Detection Methodology Protocol",
                    "similarity_score": 0.3100,
                },
            ],
        }
        return 200, resp, 85.0

    evaluator = ProductionRetrievalEvaluator(http_client=mock_http)
    qr = evaluator.evaluate_query(sample_relevant_query)

    assert qr.found_rank == 3
    assert qr.retrieved_at_rank_1 is False
    assert qr.retrieved_at_rank_3 is True
    assert qr.retrieved_at_rank_5 is True
    assert qr.reciprocal_rank == pytest.approx(1.0 / 3.0, 0.001)
    assert qr.precision_at_1 == 0.0
    assert qr.precision_at_3 == pytest.approx(1.0 / 3.0, 0.001)
    assert qr.precision_at_5 == pytest.approx(1.0 / 5.0, 0.001)


def test_relevant_document_missing_from_top_k(sample_relevant_query):
    """Verify metrics when expected document is completely absent from top-k items."""
    def mock_http(url: str, payload: dict[str, Any], timeout: float):
        resp = {
            "query": payload["query"],
            "total_results": 1,
            "embedding_model": "lightweight-hashing-384",
            "items": [
                {
                    "rank": 1,
                    "chunk_id": "c1",
                    "document_id": "d1",
                    "title": "Waterborne Gastrointestinal Outbreak Cluster Definition",
                    "similarity_score": 0.3150,
                }
            ],
        }
        return 200, resp, 90.0

    evaluator = ProductionRetrievalEvaluator(http_client=mock_http)
    qr = evaluator.evaluate_query(sample_relevant_query)

    assert qr.found_rank is None
    assert qr.retrieved_at_rank_1 is False
    assert qr.retrieved_at_rank_3 is False
    assert qr.retrieved_at_rank_5 is False
    assert qr.reciprocal_rank == 0.0
    assert qr.precision_at_1 == 0.0
    assert qr.precision_at_3 == 0.0
    assert qr.precision_at_5 == 0.0


def test_negative_query_correctly_rejected(sample_negative_query):
    """Verify that a successful 200 response with 0 items is marked as negative_rejected=True."""
    def mock_http(url: str, payload: dict[str, Any], timeout: float):
        resp = {
            "query": payload["query"],
            "total_results": 0,
            "embedding_model": "lightweight-hashing-384",
            "items": [],
        }
        return 200, resp, 65.0

    evaluator = ProductionRetrievalEvaluator(http_client=mock_http)
    qr = evaluator.evaluate_query(sample_negative_query)

    assert qr.http_status == 200
    assert qr.total_results == 0
    assert qr.negative_rejected is True
    assert qr.found_rank is None
    assert qr.error_message is None

    # Test aggregate rejection rate in report
    report = evaluator.evaluate_all(queries=[sample_negative_query])
    assert report.metrics.negative_query_rejection_rate == 1.0


def test_http_failure_not_counted_as_negative_rejection(sample_negative_query):
    """Verify that an HTTP failure (500 or network error) is NOT credited as a rejection."""
    def mock_http(url: str, payload: dict[str, Any], timeout: float):
        raise urllib.error.HTTPError(
            url=url,
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None,
        )

    evaluator = ProductionRetrievalEvaluator(http_client=mock_http)
    qr = evaluator.evaluate_query(sample_negative_query)

    assert qr.http_status == 500
    assert qr.error_message is not None
    assert "HTTPError 500" in qr.error_message
    # Must NOT be counted as negative rejection
    assert qr.negative_rejected is False

    # Aggregate rejection rate must be 0.0
    report = evaluator.evaluate_all(queries=[sample_negative_query])
    assert report.metrics.negative_query_rejection_rate == 0.0
    assert report.http_summary["failed_requests"] == 1


def test_timeout_handling(sample_relevant_query, sample_negative_query):
    """Verify timeout exception handling for both relevant and negative queries."""
    def mock_http(url: str, payload: dict[str, Any], timeout: float):
        raise TimeoutError("Socket read timed out")

    evaluator = ProductionRetrievalEvaluator(http_client=mock_http)
    report = evaluator.evaluate_all(queries=[sample_relevant_query, sample_negative_query])

    assert report.http_summary["total_requests"] == 2
    assert report.http_summary["failed_requests"] == 2
    assert report.http_summary["timeout_requests"] == 2
    assert report.metrics.recall_at_1 == 0.0
    assert report.metrics.negative_query_rejection_rate == 0.0

    neg_res = report.query_results[1]
    assert neg_res.negative_rejected is False
    assert "TimeoutError" in neg_res.error_message


def test_empty_evaluation_dataset_handling():
    """Verify evaluator handles empty query set gracefully without ZeroDivisionError."""
    evaluator = ProductionRetrievalEvaluator()
    report = evaluator.evaluate_all(queries=[])

    assert report.query_counts["total_queries"] == 0
    assert report.metrics.recall_at_1 == 0.0
    assert report.metrics.precision_at_1 == 0.0
    assert report.metrics.mean_reciprocal_rank_mrr == 0.0
    assert report.metrics.negative_query_rejection_rate == 1.0
    assert report.metrics.mean_latency_ms == 0.0
    assert report.metrics.p95_latency_ms == 0.0
    assert len(report.query_results) == 0


def test_json_output_creation(tmp_path, sample_relevant_query, sample_negative_query):
    """Verify JSON output structure, required metadata, and notices."""
    def mock_http(url: str, payload: dict[str, Any], timeout: float):
        is_neg = "quantum" in payload["query"]
        items = [] if is_neg else [
            {
                "rank": 1,
                "chunk_id": "c1",
                "document_id": "d1",
                "title": "Syndromic Surveillance Statistical Anomaly Detection Methodology Protocol",
                "similarity_score": 0.45,
            }
        ]
        return 200, {
            "query": payload["query"],
            "total_results": len(items),
            "embedding_model": "lightweight-hashing-384",
            "items": items,
        }, 50.0

    evaluator = ProductionRetrievalEvaluator(http_client=mock_http)
    report = evaluator.evaluate_all(queries=[sample_relevant_query, sample_negative_query])

    out_file = tmp_path / "test_production_evaluation.json"
    evaluator.save_report(report, out_file)

    assert out_file.exists()
    with open(out_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["evaluation_name"] == "PublicHealthSentinel Production Semantic Retrieval Evaluation"
    assert "evaluation_timestamp_utc" in data
    assert data["active_embedding_model"] == "lightweight-hashing-384"
    assert data["similarity_threshold"] == 0.30
    assert data["top_k"] == 5
    assert data["query_counts"]["total_queries"] == 2
    assert "metrics" in data
    assert data["metrics"]["recall_at_1"] == 1.0
    assert data["metrics"]["negative_query_rejection_rate"] == 1.0
    assert "limitations" in data
    assert len(data["limitations"]) > 0
    assert "synthetic_data_notice" in data
    assert "query_results" in data
    assert len(data["query_results"]) == 2


def test_model_configuration_recorded_correctly():
    """Verify active embedding model from API response is accurately propagated."""
    def mock_http(url: str, payload: dict[str, Any], timeout: float):
        return 200, {
            "query": payload["query"],
            "total_results": 0,
            "embedding_model": "custom-production-hashing-model-v2",
            "items": [],
        }, 40.0

    q = QueryDefinition(
        query_id="q1",
        query="test query",
        category="negative_control",
        topic="test",
        expected_document_titles=[],
    )
    evaluator = ProductionRetrievalEvaluator(http_client=mock_http)
    report = evaluator.evaluate_all(queries=[q])

    assert report.active_embedding_model == "custom-production-hashing-model-v2"
    assert report.query_results[0].embedding_model == "custom-production-hashing-model-v2"
