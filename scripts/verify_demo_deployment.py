"""Verification script for Phase 10 Public Demo Mode and Render Free-Tier Deployment.

Tests:
1. Zero Ollama dependency
2. Module import cleanliness (no PyTorch, no SentenceTransformers)
3. Self-healing ephemeral SQLite database seeding
4. Complete endpoint functionality (Surveillance, Mobility, Anomalies, Geospatial, Assistant)
5. Strict evidence provenance and out-of-scope refusal
6. HTTP 403 guards on administrative/destructive endpoints
7. Memory measurement: baseline, startup, and steady-state
"""

import os
import sys
import tempfile
import time
from pathlib import Path

# Force demo mode before importing public_health_sentinel
os.environ["DEMO_MODE"] = "true"
os.environ["SENTINEL_DEMO_MODE"] = "true"
os.environ["EMBEDDING_PROVIDER"] = "tfidf"
os.environ["GENERATION_PROVIDER"] = "demo"
os.environ["APP_ENV"] = "production"
os.environ["DEBUG"] = "false"

def get_memory_mb() -> float:
    """Retrieve current process RSS working set size in megabytes."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        handle = ctypes.windll.kernel32.GetCurrentProcess()
        fn = getattr(ctypes.windll.kernel32, "K32GetProcessMemoryInfo", None) or ctypes.windll.psapi.GetProcessMemoryInfo
        fn.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        fn.restype = wintypes.BOOL
        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        fn(handle, ctypes.byref(counters), counters.cb)
        return float(counters.WorkingSetSize) / (1024.0 * 1024.0)
    else:
        # Linux /proc/self/status
        status_path = Path("/proc/self/status")
        if status_path.is_file():
            try:
                for line in status_path.read_text(encoding="utf-8").splitlines():
                    if line.startswith("VmRSS:"):
                        return float(line.split()[1]) / 1024.0
            except (OSError, ValueError, IndexError) as err:
                sys.stderr.write(f"Notice: Could not read /proc/self/status: {err}\n")
        return 0.0


def main():
    print("=" * 72)
    print("PublicHealthSentinel — Phase 10 Public Demo Deployment Verification")
    print("=" * 72)

    mem_baseline = get_memory_mb()
    print(f"[1] Baseline Interpreter Memory: {mem_baseline:.2f} MB")

    # Step 1: Create a fresh ephemeral SQLite database in temp directory
    temp_dir = tempfile.TemporaryDirectory()
    temp_db_path = Path(temp_dir.name) / "ephemeral_sentinel.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{temp_db_path.as_posix()}"

    t0 = time.perf_counter()

    # Step 2: Import application stack
    from fastapi.testclient import TestClient

    from public_health_sentinel.api.app import app
    from public_health_sentinel.config import get_config
    from public_health_sentinel.db.demo_seeder import is_db_empty, seed_demo_data_if_needed
    from public_health_sentinel.db.session import get_engine, init_db

    get_config.cache_clear()
    get_config()

    t_import = time.perf_counter() - t0
    mem_startup = get_memory_mb()
    print(f"[2] App Stack Imported in {t_import:.2f}s | Startup Memory: {mem_startup:.2f} MB")

    # Step 3: Check module cleanliness (NO PyTorch, NO SentenceTransformers, NO Matplotlib at startup)
    torch_loaded = "torch" in sys.modules
    st_loaded = "sentence_transformers" in sys.modules
    mpl_loaded = "matplotlib" in sys.modules
    print("[3] Dependency Audit:")
    print(f"    - torch imported: {torch_loaded} (Expected: False)")
    print(f"    - sentence_transformers imported: {st_loaded} (Expected: False)")
    print(f"    - matplotlib imported: {mpl_loaded} (Expected: False)")
    assert not torch_loaded, "CRITICAL: torch must not be imported in demo mode!"
    assert not st_loaded, "CRITICAL: sentence_transformers must not be imported in demo mode!"
    assert not mpl_loaded, "CRITICAL: matplotlib must not be imported at application startup in demo mode!"

    # Step 4: Ephemeral Database Seeding
    engine = get_engine()
    init_db(engine)
    assert is_db_empty(engine) is True, "Database should initially be empty on ephemeral startup"

    t_seed_start = time.perf_counter()
    seeded = seed_demo_data_if_needed(engine)
    t_seed = time.perf_counter() - t_seed_start

    print(f"[4] Ephemeral Database Auto-Seeding ({t_seed:.2f}s):")
    print(f"    - Surveillance observations seeded: {seeded['surveillance']}")
    print(f"    - Mobility indicators seeded:       {seeded['mobility']}")
    print(f"    - Anomaly detection records seeded: {seeded['anomalies']}")
    print(f"    - Document passage chunks seeded:   {seeded['chunks']}")
    assert seeded['surveillance'] == 2700
    assert seeded['mobility'] == 2700
    assert seeded['anomalies'] == 2700
    assert seeded['chunks'] == 6
    assert is_db_empty(engine) is False

    # Verify idempotency
    seeded_again = seed_demo_data_if_needed(engine)
    assert seeded_again['surveillance'] == 0, "Seeder must be idempotent"

    # Step 5: Test all dashboard API endpoints
    client = TestClient(app)

    # 5.1 Health Check
    res_health = client.get("/health")
    assert res_health.status_code == 200
    h_data = res_health.json()
    assert h_data["demo_mode"] is True
    assert h_data["database_connected"] is True
    print(f"[5.1] GET /health -> Status: {h_data['status']}, Demo Mode: {h_data['demo_mode']}")

    # 5.2 Surveillance Endpoint
    res_surv = client.get("/api/v1/surveillance?page=1&page_size=5")
    assert res_surv.status_code == 200
    s_data = res_surv.json()
    assert s_data["total"] == 2700
    assert "SYNTHETIC" in s_data["synthetic_experiment_notice"].upper()
    print("[5.2] GET /api/v1/surveillance -> 200 OK (2,700 total records, synthetic notice present)")

    # 5.3 Mobility Endpoint
    res_mob = client.get("/api/v1/mobility?page=1&page_size=5")
    assert res_mob.status_code == 200
    m_data = res_mob.json()
    assert m_data["total"] == 2700
    print("[5.3] GET /api/v1/mobility -> 200 OK (2,700 total records)")

    # 5.4 Anomalies Endpoint
    res_anom = client.get("/api/v1/anomalies?page=1&page_size=5")
    assert res_anom.status_code == 200
    a_data = res_anom.json()
    assert a_data["total"] == 2700
    assert "SYNTHETIC" in a_data["synthetic_experiment_notice"].upper()
    print("[5.4] GET /api/v1/anomalies -> 200 OK (2,700 total records, non-diagnostic notice present)")

    # 5.5 Geospatial Endpoints
    res_geo = client.get("/api/v1/geospatial/regions")
    assert res_geo.status_code == 200
    g_data = res_geo.json()
    assert len(g_data) == 5
    res_geojson = client.get("/api/v1/geospatial/geojson")
    assert res_geojson.status_code == 200
    print("[5.5] GET /api/v1/geospatial/regions & geojson -> 200 OK (5 synthetic sectors)")

    # 5.6 Assistant Status (No Ollama server needed)
    res_status = client.get("/api/v1/assistant/status")
    assert res_status.status_code == 200
    as_data = res_status.json()
    assert as_data["provider"] == "demo"
    assert as_data["provider_healthy"] is True
    assert as_data["indexed_passages_count"] >= 6
    print(f"[5.6] GET /api/v1/assistant/status -> 200 OK (Provider: {as_data['provider']}, Passages: {as_data['indexed_passages_count']})")

    # 5.7 Assistant In-Scope Inquiry (Evidence-First, Zero Hallucination)
    t_ask_start = time.perf_counter()
    res_ask = client.post("/api/v1/assistant/ask", json={
        "question": "What is the threshold for respiratory surge anomalies?",
        "top_k": 2,
        "min_similarity": 0.05
    })
    t_ask = time.perf_counter() - t_ask_start
    assert res_ask.status_code == 200
    ask_data = res_ask.json()
    assert ask_data["response_type"] == "evidence_fallback"
    assert ask_data["finish_reason"] == "demo_mode"
    assert len(ask_data["citations"]) > 0
    assert "[E1]" in ask_data["answer"]
    assert "PUBLIC DEMO NOTICE" in ask_data["answer"]
    print(f"[5.7] POST /api/v1/assistant/ask (In-Scope, {t_ask*1000:.1f}ms):")
    print(f"      - Response type: {ask_data['response_type']}")
    print(f"      - Finish reason: {ask_data['finish_reason']}")
    print(f"      - Citations returned: {len(ask_data['citations'])} (Verified: {ask_data['citations'][0]['is_verified']})")

    # 5.8 Assistant Out-of-Scope Inquiry (Refusal Safeguard)
    t_refuse_start = time.perf_counter()
    res_refuse = client.post("/api/v1/assistant/ask", json={
        "question": "What is the recipe for chocolate chip cookies?",
        "top_k": 2,
        "min_similarity": 0.40
    })
    t_refuse = time.perf_counter() - t_refuse_start
    assert res_refuse.status_code == 200
    refuse_data = res_refuse.json()
    assert refuse_data["evidence_sufficiency"] == "INSUFFICIENT"
    assert refuse_data["response_type"] == "insufficient_refusal"
    assert "does not contain sufficient" in refuse_data["answer"]
    print(f"[5.8] POST /api/v1/assistant/ask (Out-of-Scope Refusal, {t_refuse*1000:.1f}ms):")
    print(f"      - Evidence sufficiency: {refuse_data['evidence_sufficiency']}")
    print(f"      - Refusal verified: {refuse_data['response_type']}")

    # 5.9 Administrative Endpoint 403 Guards
    r1 = client.post("/api/v1/documents/ingest", json={"filename": "test.txt", "content": "Sample content"})
    r2 = client.post("/api/v1/documents/doc-123/process")
    r3 = client.post("/api/v1/evidence/rebuild")
    r4 = client.post("/api/v1/pipeline/detect", json={})
    assert r1.status_code == 403
    assert r2.status_code == 403
    assert r3.status_code == 403
    assert r4.status_code == 403
    print(f"[5.9] Administrative 403 Guards: Ingest={r1.status_code}, Process={r2.status_code}, Rebuild={r3.status_code}, Detect={r4.status_code}")

    # Step 6: Steady-State Memory Simulation (50 rapid requests)
    for _ in range(50):
        client.get("/api/v1/surveillance?page=1&page_size=20")
        client.get("/api/v1/anomalies?page=1&page_size=20")
        client.post("/api/v1/assistant/ask", json={"question": "baseline surge threshold", "top_k": 2, "min_similarity": 0.05})

    mem_steady = get_memory_mb()
    print(f"[6] Steady-State Memory after 150 API calls: {mem_steady:.2f} MB")
    print("    - Render Free Tier Memory Ceiling: 512.00 MB")
    print(f"    - Safety Headroom: {512.0 - mem_steady:.2f} MB ({(512.0 - mem_steady)/512.0 * 100:.1f}%)")

    engine.dispose()
    try:
        temp_dir.cleanup()
    except (OSError, PermissionError) as err:
        sys.stderr.write(f"Notice: Ephemeral cleanup skipped: {err}\n")
    print("=" * 72)
    print("DEMO MODE VERIFICATION SUCCESSFUL: ALL CRITERIA PASS")
    print("=" * 72)


if __name__ == "__main__":
    main()
