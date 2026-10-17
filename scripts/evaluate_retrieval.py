"""Evaluation script for Phase 6B.1 semantic evidence passage retrieval.

Constructs an explicitly labelled synthetic retrieval benchmark with known
question-passage ground truth pairs, then calculates:
- Recall@1, Recall@3, Recall@5
- Precision@1, Precision@3, Precision@5
- Mean Reciprocal Rank (MRR)
- Indexing throughput and duration
- Mean and p95 query latency
- Active embedding model and memory profile
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
import tracemalloc
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from public_health_sentinel.db.models import Base
from public_health_sentinel.documents.chunker import split_text_into_chunks
from public_health_sentinel.documents.embeddings import (
    DeterministicMockEmbeddingService,
    LocalSentenceTransformerEmbeddingService,
)
from public_health_sentinel.documents.index import VectorIndexManager
from public_health_sentinel.documents.retrieval import SemanticRetrievalService

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("benchmark")

# Synthetic Benchmark Reference Documents
BENCHMARK_DOCUMENTS = [
    {
        "doc_id": "syn-doc-001",
        "title": "Respiratory Surge Statistical Threshold Protocol",
        "publisher": "Synthetic State Surveillance Taskforce",
        "content": (
            "Section 1: Baseline Estimation.\n"
            "Emergency departments monitor daily encounters for respiratory syndrome. Baseline encounter counts "
            "are estimated using a 28-day centered window excluding active alert periods. "
            "Statistical surge alerts trigger when observed counts exceed baseline plus 2.5 times the median absolute deviation (MAD).\n\n"
            "Section 2: Secondary Epidemiological Review.\n"
            "Within 4 hours of an alert, the surveillance team verifies chief complaint coding distributions to eliminate "
            "electronic health record batching artifacts before escalating to regional health officers."
        ),
    },
    {
        "doc_id": "syn-doc-002",
        "title": "Waterborne Gastrointestinal Outbreak Cluster Definition",
        "publisher": "Synthetic Municipal Water & Health Agency",
        "content": (
            "Section 1: Case Definition for Waterborne Diarrheal Illness.\n"
            "A suspected case is defined as acute onset of non-bloody watery diarrhea with at least three loose stools in 24 hours. "
            "Spatial clustering within a single municipal water distribution pressure zone warrants environmental sampling.\n\n"
            "Section 2: Coliform and Turbidity Monitoring.\n"
            "Water utilities must cross-reference daily turbidimetric measurements with syndromic diarrhea reports from primary clinics."
        ),
    },
    {
        "doc_id": "syn-doc-003",
        "title": "Measles and Rash Notification Protocol for School Health",
        "publisher": "Synthetic Department of School Health",
        "content": (
            "Section 1: Immediate Notification Criteria.\n"
            "Any school student presenting with fever (>= 38.3 C) and generalized maculopapular rash, cough, coryza, or conjunctivitis "
            "must be immediately isolated in a designated room with negative air pressure or an N95-equivalent barrier.\n\n"
            "Section 2: Roster Tracing.\n"
            "School nurses must pull immunization rosters within 2 hours of case report to identify unvaccinated contacts."
        ),
    },
    {
        "doc_id": "syn-doc-004",
        "title": "Viral Hemorrhagic Fever Triage and Barrier Nursing Guidelines",
        "publisher": "Synthetic Regional Infectious Disease Institute",
        "content": (
            "Section 1: Clinical Triage and Travel History.\n"
            "Patients with acute febrile illness and travel history to an active filovirus endemic zone within the preceding 21 days "
            "must bypass general waiting rooms directly to an airborne isolation unit.\n\n"
            "Section 2: Personal Protective Equipment.\n"
            "Healthcare workers must don full-body impervious coveralls, double gloves, PAPR respirators, and chemical-resistant boot covers."
        ),
    },
    {
        "doc_id": "syn-doc-005",
        "title": "Mobility Index Integration and Lead-Lag Methodology",
        "publisher": "Synthetic Epidemiological Analytics Group",
        "content": (
            "Section 1: Mobility Indicators in Syndromic Surveillance.\n"
            "Aggregated transit and workplace mobility percentage changes are evaluated for lead-lag associations with syndromic curves. "
            "Empirical evidence demonstrates mobility changes precede peak respiratory clinic surge by 3 to 7 days.\n\n"
            "Section 2: Predictive Comparison.\n"
            "Autoregressive baseline models augmented with mobility indicators show modest improvement in F1 score for early wave alerts."
        ),
    },
]

# Synthetic Benchmark Evaluation Queries and Ground Truth Targets
BENCHMARK_QUERIES = [
    {
        "query": "What statistical threshold triggers a respiratory surge alert?",
        "expected_doc_id": "syn-doc-001",
        "expected_keyword": "median absolute deviation",
    },
    {
        "query": "How many hours after a surge alert must secondary epidemiological review be completed?",
        "expected_doc_id": "syn-doc-001",
        "expected_keyword": "4 hours",
    },
    {
        "query": "What is the clinical case definition for waterborne diarrheal illness?",
        "expected_doc_id": "syn-doc-002",
        "expected_keyword": "watery diarrhea",
    },
    {
        "query": "When should water utilities cross-reference turbidity measurements with clinic reports?",
        "expected_doc_id": "syn-doc-002",
        "expected_keyword": "turbidimetric",
    },
    {
        "query": "What temperature and rash symptoms require immediate school student isolation?",
        "expected_doc_id": "syn-doc-003",
        "expected_keyword": "maculopapular rash",
    },
    {
        "query": "How fast must school nurses pull vaccination rosters for measles contacts?",
        "expected_doc_id": "syn-doc-003",
        "expected_keyword": "2 hours",
    },
    {
        "query": "What travel history and incubation period criteria are used for viral hemorrhagic fever triage?",
        "expected_doc_id": "syn-doc-004",
        "expected_keyword": "21 days",
    },
    {
        "query": "What PPE equipment is required for filovirus barrier nursing?",
        "expected_doc_id": "syn-doc-004",
        "expected_keyword": "impervious coveralls",
    },
    {
        "query": "How many days do mobility indicator changes precede peak respiratory clinic surges?",
        "expected_doc_id": "syn-doc-005",
        "expected_keyword": "3 to 7 days",
    },
    {
        "query": "Does augmenting autoregressive models with mobility indicators improve wave alert F1 score?",
        "expected_doc_id": "syn-doc-005",
        "expected_keyword": "F1 score",
    },
    # Explicit Out-of-Scope / Negative Control Queries (no relevant ground truth passages)
    {
        "query": "What veterinary antibiotic dosage applies to feline viral rhinotracheitis?",
        "expected_doc_id": None,
        "expected_keyword": None,
    },
    {
        "query": "How are agricultural crop pesticide tolerances calculated for citrus orchards?",
        "expected_doc_id": None,
        "expected_keyword": None,
    },
]


def run_benchmark(use_mock: bool = False, output_json: Path | None = None) -> dict[str, Any]:
    """Execute complete retrieval benchmark and compute information retrieval metrics."""
    tracemalloc.start()
    start_total_time = time.perf_counter()

    # 1. Initialize In-Memory DB
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_maker = sessionmaker(bind=engine)
    session = session_maker()

    # 2. Select embedding provider
    if use_mock:
        model_name = "deterministic-mock-minilm"
        emb_svc = DeterministicMockEmbeddingService(model_name=model_name, expected_dim=384)
    else:
        model_name = "sentence-transformers/all-MiniLM-L6-v2"
        emb_svc = LocalSentenceTransformerEmbeddingService(model_name=model_name, expected_dim=384)

    # 3. Setup temporary vector index
    import tempfile
    temp_dir = Path(tempfile.mkdtemp(prefix="sentinel_benchmark_index_"))
    vec_index = VectorIndexManager(index_dir=temp_dir, expected_dim=384, model_name=model_name)

    logger.info("Starting synthetic document chunking and indexing benchmark (%s)...", model_name)
    indexing_start = time.perf_counter()

    from public_health_sentinel.db.models import DocumentChunkModel

    all_chunks: list[tuple[str, str, np.ndarray]] = []
    total_chunk_count = 0

    for doc in BENCHMARK_DOCUMENTS:
        chunks = split_text_into_chunks(
            text=doc["content"],
            document_id=doc["doc_id"],
            title=doc["title"],
            source_publisher=doc["publisher"],
            target_chunk_size=400,
            chunk_overlap=80,
        )
        total_chunk_count += len(chunks)
        texts = [c.text for c in chunks]
        embeddings = emb_svc.embed_batch(texts)

        for chunk, vec in zip(chunks, embeddings):
            cm = DocumentChunkModel(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                sequence_number=chunk.sequence_number,
                text=chunk.text,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                title=chunk.title,
                source_publisher=chunk.source_publisher,
                content_hash=chunk.content_hash,
                embedding_json=json.dumps(vec.tolist()),
                embedding_model=model_name,
            )
            session.add(cm)
            all_chunks.append((chunk.chunk_id, chunk.document_id, vec))

    session.commit()
    vec_index.add_chunks(all_chunks, model_name=model_name)
    indexing_duration = time.perf_counter() - indexing_start

    logger.info(
        "Indexed %d passages from %d synthetic documents in %.2f ms (%.1f passages/sec)",
        total_chunk_count,
        len(BENCHMARK_DOCUMENTS),
        indexing_duration * 1000.0,
        total_chunk_count / indexing_duration,
    )

    # 4. Evaluate queries
    retrieval_svc = SemanticRetrievalService(vector_index=vec_index, embedding_service=emb_svc)

    hits_at_1 = 0
    hits_at_3 = 0
    hits_at_5 = 0
    precision_hits_1 = 0.0
    precision_hits_3 = 0.0
    precision_hits_5 = 0.0
    reciprocal_ranks = []
    latencies = []

    negative_rejections = 0
    detailed_evals = []

    answerable_queries = [q for q in BENCHMARK_QUERIES if q["expected_doc_id"] is not None]
    negative_queries = [q for q in BENCHMARK_QUERIES if q["expected_doc_id"] is None]

    for q_item in BENCHMARK_QUERIES:
        q_text = q_item["query"]
        target_doc = q_item["expected_doc_id"]
        target_kw = q_item["expected_keyword"].lower() if q_item["expected_keyword"] else None

        t0 = time.perf_counter()
        search_res = retrieval_svc.search(session, query=q_text, top_k=5)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(latency_ms)

        top_score = search_res.items[0].similarity_score if search_res.items else 0.0

        if target_doc is not None:
            # Answerable benchmark query
            found_rank = None
            for rank, hit in enumerate(search_res.items, start=1):
                if hit.document_id == target_doc and target_kw and target_kw in hit.text.lower():
                    found_rank = rank
                    break

            if found_rank == 1:
                hits_at_1 += 1
                precision_hits_1 += 1.0
            if found_rank is not None and found_rank <= 3:
                hits_at_3 += 1
                precision_hits_3 += 1.0 / 3.0
            if found_rank is not None and found_rank <= 5:
                hits_at_5 += 1
                precision_hits_5 += 1.0 / 5.0

            rr = (1.0 / found_rank) if found_rank is not None else 0.0
            reciprocal_ranks.append(rr)

            detailed_evals.append({
                "query": q_text,
                "query_type": "answerable",
                "target_doc_id": target_doc,
                "rank": found_rank,
                "reciprocal_rank": round(rr, 4),
                "top_similarity_score": round(top_score, 4),
                "latency_ms": round(latency_ms, 2),
            })
        else:
            # Negative / Out-of-scope control query
            # By IR convention: successfully rejected if top similarity score is low (< 0.40) or no passages returned
            is_rejected = len(search_res.items) == 0 or top_score < 0.40
            if is_rejected:
                negative_rejections += 1

            detailed_evals.append({
                "query": q_text,
                "query_type": "negative_control",
                "target_doc_id": None,
                "top_similarity_score": round(top_score, 4),
                "low_similarity_rejected": is_rejected,
                "latency_ms": round(latency_ms, 2),
            })

    num_answerable = len(answerable_queries)
    recall_at_1 = hits_at_1 / num_answerable if num_answerable > 0 else 0.0
    recall_at_3 = hits_at_3 / num_answerable if num_answerable > 0 else 0.0
    recall_at_5 = hits_at_5 / num_answerable if num_answerable > 0 else 0.0

    precision_at_1 = precision_hits_1 / num_answerable if num_answerable > 0 else 0.0
    precision_at_3 = precision_hits_3 / num_answerable if num_answerable > 0 else 0.0
    precision_at_5 = precision_hits_5 / num_answerable if num_answerable > 0 else 0.0

    mrr = sum(reciprocal_ranks) / num_answerable if num_answerable > 0 else 0.0
    rejection_rate = negative_rejections / len(negative_queries) if negative_queries else 1.0

    mean_latency = float(np.mean(latencies))
    p95_latency = float(np.percentile(latencies, 95))

    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    results = {
        "benchmark_name": "PublicHealthSentinel Phase 6B.2 Synthetic Retrieval Benchmark",
        "benchmark_context": (
            "SYNTHETIC-DATA NOTICE: Evaluated exclusively against simulated public health reference materials. "
            "High benchmark retrieval scores do not imply clinical efficacy or diagnostic accuracy on authentic literature."
        ),
        "unanswerable_query_convention": (
            "Negative control queries (target_doc_id = None) evaluate method selectivity. "
            "Rejection is satisfied when top similarity score is below 0.40 or zero results match."
        ),
        "embedding_model": model_name,
        "embedding_dimension": 384,
        "total_synthetic_documents": len(BENCHMARK_DOCUMENTS),
        "total_indexed_passages": total_chunk_count,
        "indexing_duration_ms": round(indexing_duration * 1000.0, 2),
        "indexing_throughput_passages_per_sec": round(total_chunk_count / indexing_duration, 1),
        "total_queries_evaluated": len(BENCHMARK_QUERIES),
        "answerable_queries_count": num_answerable,
        "negative_control_queries_count": len(negative_queries),
        "metrics": {
            "recall_at_1": round(recall_at_1, 4),
            "recall_at_3": round(recall_at_3, 4),
            "recall_at_5": round(recall_at_5, 4),
            "precision_at_1": round(precision_at_1, 4),
            "precision_at_3": round(precision_at_3, 4),
            "precision_at_5": round(precision_at_5, 4),
            "mean_reciprocal_rank_mrr": round(mrr, 4),
            "negative_query_rejection_rate": round(rejection_rate, 4),
            "mean_query_latency_ms": round(mean_latency, 2),
            "p95_query_latency_ms": round(p95_latency, 2),
        },
        "memory_profile": {
            "current_memory_mb": round(current_mem / (1024 * 1024), 2),
            "peak_memory_mb": round(peak_mem / (1024 * 1024), 2),
        },
        "query_details": detailed_evals,
    }

    print("\n" + "=" * 72)
    print("  PublicHealthSentinel Phase 6B.2 — Semantic Retrieval Evaluation")
    print("=" * 72)
    print(f"Embedding Model:             {model_name} (384-D)")
    print(f"Indexed Documents:           {len(BENCHMARK_DOCUMENTS)}")
    print(f"Indexed Passages:            {total_chunk_count}")
    print(f"Indexing Duration:           {indexing_duration * 1000.0:.2f} ms")
    print(f"Indexing Throughput:         {total_chunk_count / indexing_duration:.1f} passages/sec")
    print("-" * 72)
    print(f"Total Queries Evaluated:     {len(BENCHMARK_QUERIES)} ({num_answerable} answerable, {len(negative_queries)} negative controls)")
    print(f"Recall@1:                    {recall_at_1:.2%}")
    print(f"Recall@3:                    {recall_at_3:.2%}")
    print(f"Recall@5:                    {recall_at_5:.2%}")
    print(f"Precision@1:                 {precision_at_1:.2%}")
    print(f"Precision@3:                 {precision_at_3:.2%}")
    print(f"Precision@5:                 {precision_at_5:.2%}")
    print(f"Mean Reciprocal Rank (MRR):  {mrr:.4f}")
    print(f"Negative Rejection Rate:     {rejection_rate:.2%}")
    print(f"Mean Query Latency:          {mean_latency:.2f} ms")
    print(f"p95 Query Latency:           {p95_latency:.2f} ms")
    print(f"Peak Memory Allocated:       {peak_mem / (1024 * 1024):.2f} MB")
    print("=" * 72)
    print("BENCHMARK CAVEAT: Synthetic benchmark performance measures semantic ranking")
    print("alignment under controlled test conditions. It does not establish diagnostic")
    print("competence or factual accuracy on real-world medical literature.")
    print("=" * 72 + "\n")
    print("BENCHMARK CAVEAT: Synthetic benchmark performance measures semantic ranking")
    print("alignment under controlled test conditions. It does not establish diagnostic")
    print("competence or factual accuracy on real-world medical literature.")
    print("=" * 70 + "\n")

    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        logger.info("Saved benchmark evaluation results to %s", output_json)

    # Cleanup temp dir
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate semantic retrieval on synthetic benchmark.")
    parser.add_argument("--mock", action="store_true", help="Use deterministic mock embeddings for offline runs.")
    parser.add_argument("--output", type=str, default="data/retrieval_benchmark_results.json", help="Output path for JSON report.")
    args = parser.parse_args()

    out_path = Path(args.output) if args.output else None
    run_benchmark(use_mock=args.mock, output_json=out_path)
