"""Automated regression test for the synthetic retrieval benchmark."""

import os
import pytest

from scripts.evaluate_retrieval import run_benchmark


def test_synthetic_retrieval_benchmark_metrics_mock():
    """Verify benchmark execution with deterministic mock embeddings completes and computes metrics."""
    res = run_benchmark(use_mock=True, output_json=None)

    assert res["total_synthetic_documents"] == 5
    assert res["total_indexed_passages"] == 10
    assert res["total_queries_evaluated"] == 12
    assert res["answerable_queries_count"] == 10
    assert res["negative_control_queries_count"] == 2

    metrics = res["metrics"]
    assert "recall_at_1" in metrics
    assert "recall_at_3" in metrics
    assert "recall_at_5" in metrics
    assert "precision_at_1" in metrics
    assert "precision_at_3" in metrics
    assert "precision_at_5" in metrics
    assert "mean_reciprocal_rank_mrr" in metrics
    assert "negative_query_rejection_rate" in metrics
    assert metrics["mean_query_latency_ms"] >= 0.0


@pytest.mark.skipif(
    os.getenv("RUN_REAL_MODEL_TESTS", "false").lower() != "true",
    reason="Skipped to prevent mandatory online model loading during fast unit tests. Set RUN_REAL_MODEL_TESTS=true to run.",
)
def test_synthetic_retrieval_benchmark_real_model():
    """Verify benchmark with real all-MiniLM-L6-v2 embedding model (gated for fast testing)."""
    res = run_benchmark(use_mock=False, output_json=None)
    metrics = res["metrics"]
    assert metrics["recall_at_3"] >= 0.80
    assert metrics["mean_reciprocal_rank_mrr"] >= 0.70
