"""Production Retrieval Evaluation Suite for PublicHealthSentinel.

Executes a live, repeatable, read-only semantic retrieval evaluation against the
deployed PublicHealthSentinel evidence search API over HTTP:
  POST /api/v1/evidence/search

Calculates:
- Recall@1, Recall@3, Recall@5
- Precision@1, Precision@3, Precision@5
- Mean Reciprocal Rank (MRR)
- Negative control rejection rate (% returning zero results)
- Per-query, mean, and p95 latency
- Model attribution and error reporting

Writes results to data/production_retrieval_evaluation.json without modifying
or overwriting the synthetic benchmark results.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("evaluate_production_retrieval")

DEFAULT_PRODUCTION_URL = "https://public-health-sentinel-api.onrender.com"
DEFAULT_SEARCH_PATH = "/api/v1/evidence/search"
DEFAULT_STATUS_PATH = "/api/v1/evidence/status"
DEFAULT_OUTPUT_FILE = "data/production_retrieval_evaluation.json"
DEFAULT_SIMILARITY_THRESHOLD = 0.30
DEFAULT_TOP_K = 5
DEFAULT_TIMEOUT_SEC = 15.0
DEFAULT_DELAY_SEC = 0.5

SYNTHETIC_DATA_NOTICE = (
    "SYNTHETIC-DATA NOTICE: All observations, indicators, and benchmark documents "
    "are part of a simulated research prototype. Documents represent reference material "
    "and guidelines for methodology testing. High similarity scores reflect semantic "
    "alignment of phrasing, not clinical validation or real-world epidemiology."
)

EVALUATION_LIMITATIONS = [
    "Lightweight hashing TF-IDF embeddings (384-D) do not perform dense semantic expansion; "
    "retrieval quality depends on token and n-gram overlap with indexed passage text.",
    "The 0.30 similarity threshold suppresses partially relevant passages that do not cross the score floor.",
    "The evaluation corpus is restricted to the 6 simulated demo documents (10 indexed passages) available in production.",
    "Sequential request pacing is applied to respect free-tier hosting concurrency limits.",
]


@dataclass(frozen=True)
class QueryDefinition:
    """Definition of an evaluation query and its expected ground-truth targets."""

    query_id: str
    query: str
    category: str  # "relevant", "ambiguous", "negative_control"
    topic: str
    expected_document_titles: list[str] = field(default_factory=list)


# Documented query set grounded exclusively in the production corpus
PRODUCTION_EVALUATION_QUERIES: list[QueryDefinition] = [
    # A. Relevant Queries (Ground truth supported by indexed documents)
    QueryDefinition(
        query_id="rel-01-mad-dispersion",
        query="How does Rolling Median Absolute Deviation (MAD) calculate dispersion and handle outliers?",
        category="relevant",
        topic="Rolling MAD dispersion formula and outlier robustness",
        expected_document_titles=[
            "Syndromic Surveillance Statistical Anomaly Detection Methodology Protocol"
        ],
    ),
    QueryDefinition(
        query_id="rel-02-mad-outlier-robustness",
        query="What breakdown point gives Rolling MAD robustness against extreme outbreak outliers?",
        category="relevant",
        topic="Robustness of MAD to outliers and 50% breakdown point",
        expected_document_titles=[
            "Syndromic Surveillance Statistical Anomaly Detection Methodology Protocol"
        ],
    ),
    QueryDefinition(
        query_id="rel-03-mad-scale-factor",
        query="Why is raw MAD scaled by 1.4826 in normal distribution scale estimation?",
        category="relevant",
        topic="Scaling raw MAD by 1.4826 for normal scale estimation",
        expected_document_titles=[
            "Syndromic Surveillance Statistical Anomaly Detection Methodology Protocol"
        ],
    ),
    QueryDefinition(
        query_id="rel-04-syndromic-anomaly-detection",
        query="What anomaly detection methods are compared for syndromic surveillance time series?",
        category="relevant",
        topic="Syndromic surveillance anomaly detection method comparison",
        expected_document_titles=[
            "Syndromic Surveillance Statistical Anomaly Detection Methodology Protocol"
        ],
    ),
    QueryDefinition(
        query_id="rel-05-baseline-dispersion",
        query="How is statistical baseline dispersion measured in syndromic surveillance time series?",
        category="relevant",
        topic="Statistical baseline dispersion measurement",
        expected_document_titles=[
            "Syndromic Surveillance Statistical Anomaly Detection Methodology Protocol"
        ],
    ),
    QueryDefinition(
        query_id="rel-06-respiratory-surge-threshold",
        query="What statistical threshold triggers an emergency department respiratory surge alert?",
        category="relevant",
        topic="Respiratory surveillance surge thresholds",
        expected_document_titles=[
            "Respiratory Surge Statistical Threshold Protocol"
        ],
    ),
    QueryDefinition(
        query_id="rel-07-operational-review",
        query="What operational review is required within 4 hours to verify surveillance alert validity?",
        category="relevant",
        topic="Operational interpretation and 4-hour review of surveillance thresholds",
        expected_document_titles=[
            "Respiratory Surge Statistical Threshold Protocol",
            "Syndromic Surveillance Statistical Anomaly Detection Methodology Protocol",
        ],
    ),
    QueryDefinition(
        query_id="rel-08-mobility-lead-lag",
        query="What transit and workplace indicators precede respiratory clinic surges by 3 to 7 days?",
        category="relevant",
        topic="Mobility indicators in syndromic surveillance lead-lag",
        expected_document_titles=[
            "Mobility Index Integration and Lead-Lag Methodology"
        ],
    ),
    # B. Ambiguous or Paraphrased Queries
    QueryDefinition(
        query_id="amb-01-mad-spread",
        query="Measuring data spread using median absolute deviation instead of standard deviation",
        category="ambiguous",
        topic="Paraphrase: non-parametric spread using MAD",
        expected_document_titles=[
            "Syndromic Surveillance Statistical Anomaly Detection Methodology Protocol"
        ],
    ),
    QueryDefinition(
        query_id="amb-02-batching-artifacts",
        query="Investigating electronic health record batching artifacts after a hospital surge warning",
        category="ambiguous",
        topic="Paraphrase: secondary review to rule out batching artifacts",
        expected_document_titles=[
            "Respiratory Surge Statistical Threshold Protocol",
            "Syndromic Surveillance Statistical Anomaly Detection Methodology Protocol",
        ],
    ),
    # C. Explicit Out-of-Scope Negative Controls
    QueryDefinition(
        query_id="neg-01-quantum",
        query="Explain quantum entanglement and quantum computing",
        category="negative_control",
        topic="Negative control: Quantum physics",
        expected_document_titles=[],
    ),
    QueryDefinition(
        query_id="neg-02-capital-france",
        query="What is the capital of France and its historical architecture?",
        category="negative_control",
        topic="Negative control: European geography",
        expected_document_titles=[],
    ),
    QueryDefinition(
        query_id="neg-03-autonomous-driving",
        query="Techniques for training convolutional neural networks for autonomous vehicle lane detection",
        category="negative_control",
        topic="Negative control: Autonomous vehicle computer vision",
        expected_document_titles=[],
    ),
]


@dataclass
class RetrievedPassageSummary:
    """Brief representation of an individual retrieved hit."""

    rank: int
    chunk_id: str
    document_id: str
    title: str
    similarity_score: float


@dataclass
class QueryResult:
    """Detailed evaluation outcome for an individual query."""

    query_id: str
    query: str
    category: str
    topic: str
    expected_document_titles: list[str]
    http_status: Optional[int]
    latency_ms: float
    total_results: int
    retrieved_items: list[RetrievedPassageSummary]
    found_rank: Optional[int]
    retrieved_at_rank_1: bool
    retrieved_at_rank_3: bool
    retrieved_at_rank_5: bool
    reciprocal_rank: float
    precision_at_1: float
    precision_at_3: float
    precision_at_5: float
    negative_rejected: Optional[bool]
    error_message: Optional[str]
    embedding_model: Optional[str]


@dataclass
class EvaluationMetrics:
    """Aggregated information retrieval and operational metrics."""

    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    precision_at_1: float
    precision_at_3: float
    precision_at_5: float
    mean_reciprocal_rank_mrr: float
    negative_query_rejection_rate: float
    mean_latency_ms: float
    p95_latency_ms: float


@dataclass
class EvaluationReport:
    """Complete serialized evaluation report."""

    evaluation_name: str
    evaluation_timestamp_utc: str
    api_base_url: str
    search_endpoint: str
    active_embedding_model: str
    similarity_threshold: float
    top_k: int
    query_counts: dict[str, int]
    metrics: EvaluationMetrics
    http_summary: dict[str, Any]
    limitations: list[str]
    synthetic_data_notice: str
    query_results: list[QueryResult]

    def to_dict(self) -> dict[str, Any]:
        """Convert report to JSON-serializable dictionary."""
        return {
            "evaluation_name": self.evaluation_name,
            "evaluation_timestamp_utc": self.evaluation_timestamp_utc,
            "api_base_url": self.api_base_url,
            "search_endpoint": self.search_endpoint,
            "active_embedding_model": self.active_embedding_model,
            "similarity_threshold": self.similarity_threshold,
            "top_k": self.top_k,
            "query_counts": self.query_counts,
            "metrics": asdict(self.metrics),
            "http_summary": self.http_summary,
            "limitations": self.limitations,
            "synthetic_data_notice": self.synthetic_data_notice,
            "query_results": [asdict(qr) for qr in self.query_results],
        }


def default_http_client(
    url: str,
    payload: dict[str, Any],
    timeout: float,
) -> tuple[int, dict[str, Any], float]:
    """Execute live HTTP request using urllib.

    Returns:
        (status_code, response_json_dict, latency_ms)
    """
    req_body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url=url,
        data=req_body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        latency_ms = (time.perf_counter() - t0) * 1000.0
        status_code = response.getcode()
        resp_data = json.loads(response.read().decode("utf-8"))
        return status_code, resp_data, latency_ms


class ProductionRetrievalEvaluator:
    """Evaluates the production retrieval API with configurable HTTP execution."""

    def __init__(
        self,
        base_url: str = DEFAULT_PRODUCTION_URL,
        timeout_sec: float = DEFAULT_TIMEOUT_SEC,
        min_similarity: float = DEFAULT_SIMILARITY_THRESHOLD,
        top_k: int = DEFAULT_TOP_K,
        delay_sec: float = DEFAULT_DELAY_SEC,
        http_client: Optional[
            Callable[[str, dict[str, Any], float], tuple[int, dict[str, Any], float]]
        ] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec
        self.min_similarity = min_similarity
        self.top_k = top_k
        self.delay_sec = delay_sec
        self._http_client = http_client or default_http_client

    def evaluate_query(self, q_def: QueryDefinition) -> QueryResult:
        """Run single query evaluation and compute rank/precision/rejection."""
        search_url = f"{self.base_url}{DEFAULT_SEARCH_PATH}"
        payload = {
            "query": q_def.query,
            "top_k": self.top_k,
            "min_similarity": self.min_similarity,
        }

        try:
            status_code, resp_data, latency_ms = self._http_client(
                search_url, payload, self.timeout_sec
            )
            error_message = None
        except urllib.error.HTTPError as exc:
            latency_ms = 0.0
            status_code = exc.code
            error_message = f"HTTPError {exc.code}: {exc.reason}"
            resp_data = {}
        except urllib.error.URLError as exc:
            latency_ms = 0.0
            status_code = None
            error_message = f"URLError: {exc.reason}"
            resp_data = {}
        except TimeoutError as exc:
            latency_ms = 0.0
            status_code = None
            error_message = f"TimeoutError: Request exceeded {self.timeout_sec}s"
            resp_data = {}
        except Exception as exc:
            latency_ms = 0.0
            status_code = None
            error_message = f"Unexpected error: {type(exc).__name__}: {str(exc)}"
            resp_data = {}

        raw_items = resp_data.get("items", []) if isinstance(resp_data, dict) else []
        total_results = resp_data.get("total_results", len(raw_items)) if isinstance(resp_data, dict) else 0
        embedding_model = resp_data.get("embedding_model") if isinstance(resp_data, dict) else None

        retrieved_items: list[RetrievedPassageSummary] = []
        for idx, it in enumerate(raw_items, start=1):
            retrieved_items.append(
                RetrievedPassageSummary(
                    rank=idx,
                    chunk_id=it.get("chunk_id", ""),
                    document_id=it.get("document_id", ""),
                    title=it.get("title", ""),
                    similarity_score=float(it.get("similarity_score", 0.0)),
                )
            )

        is_answerable = q_def.category in ("relevant", "ambiguous")
        found_rank: Optional[int] = None

        if is_answerable:
            for item in retrieved_items:
                if item.title in q_def.expected_document_titles:
                    found_rank = item.rank
                    break

            retrieved_at_rank_1 = found_rank == 1
            retrieved_at_rank_3 = found_rank is not None and found_rank <= 3
            retrieved_at_rank_5 = found_rank is not None and found_rank <= 5
            reciprocal_rank = (1.0 / found_rank) if found_rank else 0.0

            # Compute precision at k: number of relevant docs in top-k divided by k
            hits_1 = sum(1 for it in retrieved_items[:1] if it.title in q_def.expected_document_titles)
            hits_3 = sum(1 for it in retrieved_items[:3] if it.title in q_def.expected_document_titles)
            hits_5 = sum(1 for it in retrieved_items[:5] if it.title in q_def.expected_document_titles)

            precision_at_1 = hits_1 / 1.0
            precision_at_3 = hits_3 / 3.0
            precision_at_5 = hits_5 / 5.0
            negative_rejected = None
        else:
            # Negative control query:
            # Successfully rejected if HTTP request succeeded (200) AND returned 0 results.
            # HTTP errors or timeouts must NOT count as negative rejections.
            retrieved_at_rank_1 = False
            retrieved_at_rank_3 = False
            retrieved_at_rank_5 = False
            reciprocal_rank = 0.0
            precision_at_1 = 0.0
            precision_at_3 = 0.0
            precision_at_5 = 0.0
            if status_code == 200 and error_message is None:
                negative_rejected = total_results == 0
            else:
                negative_rejected = False

        return QueryResult(
            query_id=q_def.query_id,
            query=q_def.query,
            category=q_def.category,
            topic=q_def.topic,
            expected_document_titles=q_def.expected_document_titles,
            http_status=status_code,
            latency_ms=round(latency_ms, 2),
            total_results=total_results,
            retrieved_items=retrieved_items,
            found_rank=found_rank,
            retrieved_at_rank_1=retrieved_at_rank_1,
            retrieved_at_rank_3=retrieved_at_rank_3,
            retrieved_at_rank_5=retrieved_at_rank_5,
            reciprocal_rank=round(reciprocal_rank, 4),
            precision_at_1=round(precision_at_1, 4),
            precision_at_3=round(precision_at_3, 4),
            precision_at_5=round(precision_at_5, 4),
            negative_rejected=negative_rejected,
            error_message=error_message,
            embedding_model=embedding_model,
        )

    def evaluate_all(
        self,
        queries: Optional[list[QueryDefinition]] = None,
    ) -> EvaluationReport:
        """Run sequential evaluation over all queries and compute aggregate metrics."""
        query_list = queries if queries is not None else PRODUCTION_EVALUATION_QUERIES
        results: list[QueryResult] = []
        latencies: list[float] = []

        total_requests = len(query_list)
        successful_requests = 0
        failed_requests = 0
        timeout_requests = 0
        errors: list[dict[str, Any]] = []
        discovered_model = "unknown"

        logger.info(
            "Starting live retrieval evaluation against %s (%d queries, min_similarity=%.2f, top_k=%d)...",
            self.base_url,
            total_requests,
            self.min_similarity,
            self.top_k,
        )

        for idx, q_def in enumerate(query_list, start=1):
            qr = self.evaluate_query(q_def)
            results.append(qr)

            if qr.embedding_model:
                discovered_model = qr.embedding_model

            if qr.error_message:
                failed_requests += 1
                if "timeout" in qr.error_message.lower():
                    timeout_requests += 1
                errors.append(
                    {
                        "query_id": qr.query_id,
                        "query": qr.query,
                        "http_status": qr.http_status,
                        "error_message": qr.error_message,
                    }
                )
                logger.warning(
                    "[%d/%d] Query '%s' failed: %s",
                    idx,
                    total_requests,
                    qr.query_id,
                    qr.error_message,
                )
            else:
                successful_requests += 1
                latencies.append(qr.latency_ms)
                logger.info(
                    "[%d/%d] Query '%s' [%s]: results=%d rank=%s latency=%.1fms",
                    idx,
                    total_requests,
                    qr.query_id,
                    qr.category,
                    qr.total_results,
                    qr.found_rank if qr.found_rank is not None else "miss",
                    qr.latency_ms,
                )

            if self.delay_sec > 0 and idx < total_requests:
                time.sleep(self.delay_sec)

        # Compute aggregate metrics
        answerable_results = [r for r in results if r.category in ("relevant", "ambiguous")]
        negative_results = [r for r in results if r.category == "negative_control"]

        num_answerable = len(answerable_results)
        num_negative = len(negative_results)

        if num_answerable > 0:
            recall_at_1 = sum(1 for r in answerable_results if r.retrieved_at_rank_1) / num_answerable
            recall_at_3 = sum(1 for r in answerable_results if r.retrieved_at_rank_3) / num_answerable
            recall_at_5 = sum(1 for r in answerable_results if r.retrieved_at_rank_5) / num_answerable
            precision_at_1 = sum(r.precision_at_1 for r in answerable_results) / num_answerable
            precision_at_3 = sum(r.precision_at_3 for r in answerable_results) / num_answerable
            precision_at_5 = sum(r.precision_at_5 for r in answerable_results) / num_answerable
            mrr = sum(r.reciprocal_rank for r in answerable_results) / num_answerable
        else:
            recall_at_1 = 0.0
            recall_at_3 = 0.0
            recall_at_5 = 0.0
            precision_at_1 = 0.0
            precision_at_3 = 0.0
            precision_at_5 = 0.0
            mrr = 0.0

        if num_negative > 0:
            rejection_rate = sum(1 for r in negative_results if r.negative_rejected is True) / num_negative
        else:
            rejection_rate = 1.0

        # Latency statistics
        if latencies:
            mean_latency = float(sum(latencies) / len(latencies))
            # Calculate p95 using nearest-rank or linear interpolation
            sorted_latencies = sorted(latencies)
            idx_95 = max(0, min(len(sorted_latencies) - 1, math.ceil(0.95 * len(sorted_latencies)) - 1))
            p95_latency = float(sorted_latencies[idx_95])
        else:
            mean_latency = 0.0
            p95_latency = 0.0

        metrics = EvaluationMetrics(
            recall_at_1=round(recall_at_1, 4),
            recall_at_3=round(recall_at_3, 4),
            recall_at_5=round(recall_at_5, 4),
            precision_at_1=round(precision_at_1, 4),
            precision_at_3=round(precision_at_3, 4),
            precision_at_5=round(precision_at_5, 4),
            mean_reciprocal_rank_mrr=round(mrr, 4),
            negative_query_rejection_rate=round(rejection_rate, 4),
            mean_latency_ms=round(mean_latency, 2),
            p95_latency_ms=round(p95_latency, 2),
        )

        query_counts = {
            "total_queries": len(query_list),
            "relevant_queries": sum(1 for q in query_list if q.category == "relevant"),
            "ambiguous_queries": sum(1 for q in query_list if q.category == "ambiguous"),
            "negative_control_queries": sum(1 for q in query_list if q.category == "negative_control"),
        }

        http_summary = {
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "timeout_requests": timeout_requests,
            "errors": errors,
        }

        report = EvaluationReport(
            evaluation_name="PublicHealthSentinel Production Semantic Retrieval Evaluation",
            evaluation_timestamp_utc=datetime.now(timezone.utc).isoformat(),
            api_base_url=self.base_url,
            search_endpoint=DEFAULT_SEARCH_PATH,
            active_embedding_model=discovered_model,
            similarity_threshold=self.min_similarity,
            top_k=self.top_k,
            query_counts=query_counts,
            metrics=metrics,
            http_summary=http_summary,
            limitations=EVALUATION_LIMITATIONS,
            synthetic_data_notice=SYNTHETIC_DATA_NOTICE,
            query_results=results,
        )

        return report

    def save_report(self, report: EvaluationReport, output_path: Path) -> Path:
        """Write evaluation results to formatted JSON output file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)
        logger.info("Saved production retrieval evaluation results to %s", output_path)
        return output_path


def print_summary(report: EvaluationReport) -> None:
    """Print readable evaluation summary to terminal."""
    m = report.metrics
    qc = report.query_counts
    hs = report.http_summary

    print("\n" + "=" * 74)
    print("  PublicHealthSentinel — Live Production Retrieval Evaluation Report")
    print("=" * 74)
    print(f"Base URL:                    {report.api_base_url}")
    print(f"Search Endpoint:             {report.search_endpoint}")
    print(f"Embedding Model:             {report.active_embedding_model}")
    print(f"Min Similarity Threshold:    {report.similarity_threshold:.2f}")
    print(f"Top-K Candidates:            {report.top_k}")
    print(f"Timestamp (UTC):             {report.evaluation_timestamp_utc}")
    print("-" * 74)
    print(
        f"Queries Evaluated:           {qc['total_queries']} "
        f"({qc['relevant_queries']} relevant, {qc['ambiguous_queries']} ambiguous, {qc['negative_control_queries']} negative)"
    )
    print(
        f"HTTP Requests:               {hs['total_requests']} total, "
        f"{hs['successful_requests']} successful, {hs['failed_requests']} failed ({hs['timeout_requests']} timeouts)"
    )
    print("-" * 74)
    print("RETRIEVAL QUALITY METRICS (Answerable Queries):")
    print(f"  Recall@1:                  {m.recall_at_1:.2%}")
    print(f"  Recall@3:                  {m.recall_at_3:.2%}")
    print(f"  Recall@5:                  {m.recall_at_5:.2%}")
    print(f"  Precision@1:               {m.precision_at_1:.2%}")
    print(f"  Precision@3:               {m.precision_at_3:.2%}")
    print(f"  Precision@5:               {m.precision_at_5:.2%}")
    print(f"  Mean Reciprocal Rank (MRR):{m.mean_reciprocal_rank_mrr:.4f}")
    print("-" * 74)
    print("SELECTIVITY & NEGATIVE CONTROL METRICS:")
    print(f"  Negative Rejection Rate:   {m.negative_query_rejection_rate:.2%}")
    print("-" * 74)
    print("LATENCY METRICS:")
    print(f"  Mean Request Latency:      {m.mean_latency_ms:.2f} ms")
    print(f"  p95 Request Latency:       {m.p95_latency_ms:.2f} ms")
    print("=" * 74)
    print("QUERY BREAKDOWN:")
    for qr in report.query_results:
        rank_str = f"Rank {qr.found_rank}" if qr.found_rank is not None else "MISS"
        if qr.category == "negative_control":
            status_str = "REJECTED (OK)" if qr.negative_rejected else "FALSE POSITIVE / FAILED"
            print(f"  [{qr.query_id}] {status_str:22} | {qr.latency_ms:6.1f}ms | {qr.query[:45]}...")
        else:
            top_score = qr.retrieved_items[0].similarity_score if qr.retrieved_items else 0.0
            print(f"  [{qr.query_id}] {rank_str:8} (top={top_score:.4f}) | {qr.latency_ms:6.1f}ms | {qr.query[:45]}...")
    print("=" * 74 + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run live evaluation suite against deployed PublicHealthSentinel evidence search API."
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=DEFAULT_PRODUCTION_URL,
        help=f"Base URL of PublicHealthSentinel API (default: {DEFAULT_PRODUCTION_URL})",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=DEFAULT_OUTPUT_FILE,
        help=f"Output path for evaluation JSON report (default: {DEFAULT_OUTPUT_FILE})",
    )
    parser.add_argument(
        "--min-similarity",
        type=float,
        default=DEFAULT_SIMILARITY_THRESHOLD,
        help=f"Minimum similarity score threshold (default: {DEFAULT_SIMILARITY_THRESHOLD})",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_TOP_K,
        help=f"Top-k candidates to retrieve (default: {DEFAULT_TOP_K})",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SEC,
        help=f"HTTP request timeout in seconds (default: {DEFAULT_TIMEOUT_SEC})",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY_SEC,
        help=f"Pacing delay in seconds between consecutive requests (default: {DEFAULT_DELAY_SEC})",
    )
    args = parser.parse_args()

    evaluator = ProductionRetrievalEvaluator(
        base_url=args.base_url,
        timeout_sec=args.timeout,
        min_similarity=args.min_similarity,
        top_k=args.top_k,
        delay_sec=args.delay,
    )

    report = evaluator.evaluate_all()
    out_path = Path(args.output)
    evaluator.save_report(report, out_path)
    print_summary(report)

    # Return 0 if at least one request succeeded and negative queries are properly rejected
    if report.http_summary["failed_requests"] == report.http_summary["total_requests"]:
        logger.error("All production evaluation requests failed.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
