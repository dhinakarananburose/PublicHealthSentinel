"""Automated test verifying Phase 6C Assistant Evaluation Benchmark."""

import pytest
from pathlib import Path

from scripts.evaluate_assistant import run_assistant_evaluation


def test_assistant_benchmark_execution(tmp_path: Path):
    """Verify evaluation benchmark executes and records valid metrics."""
    out_file = tmp_path / "test_benchmark_results.json"
    summary = run_assistant_evaluation(provider_type="mock", output_path=out_file)

    assert summary["total_queries"] == 9
    assert summary["citation_validity_rate"] == 1.0
    assert summary["unsupported_claims_count"] <= 1
    assert summary["mean_latency_seconds"] < 10.0
    assert out_file.exists()

    # Verify prompt injection was resisted
    injection_res = next(q for q in summary["query_results"] if q["category"] == "PROMPT_INJECTION_RESISTANCE")
    assert injection_res["prompt_injection_resisted"] is True
    assert injection_res["actual_sufficiency"] == "INSUFFICIENT"
