# PublicHealthSentinel

> A production-oriented public health anomaly detection research prototype for syndromic surveillance and population mobility analysis.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status: Phase 7](https://img.shields.io/badge/Status-Phase%207%20Geospatial%20Intelligence-green.svg)]()
[![Tests](https://img.shields.io/badge/Tests-193%20Passing-brightgreen.svg)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0%2B-red.svg)](https://www.sqlalchemy.org/)

---

## 1. Project Objective

**PublicHealthSentinel** is an incrementally developed research prototype designed to:
1. Ingest, validate, and audit **aggregated daily syndromic surveillance counts** (e.g., respiratory, gastrointestinal, febrile symptoms) across geographic jurisdictions.
2. Detect statistical anomalies and unexpected epidemiological surges using automated time-series methods (Rolling MAD, EWMA, Z-Score).
3. Investigate ecological associations between surveillance count surges and **aggregated population mobility indicators** (e.g., transit station usage, workplace mobility, residential shifts).
4. Evaluate predictive utility of mobility augmentation using chronologically partitioned time-ordered modeling without feature or target leakage.
5. Provide relational persistence (**PostgreSQL** / SQLite) and a modern **FastAPI service layer** (`/api/v1`) for querying observations, mobility indicators, anomaly detections, and running surveillance pipelines.
6. Provide an evidence-grounded **reference document ingestion foundation** for syndromic guidelines and public health protocols *(Phase 6A)*.
7. Provide structured, interpretable explanations of detected signals via an epidemiological retrieval-augmented generation (RAG) and LLM-assisted explanation layer *(Phase 6B)*.
8. Deliver interactive **Geospatial Intelligence & Surveillance Mapping** with regional anomaly overlays, time-series exploration, mobility alignment, and lagged cross-correlations *(Phase 7)*.

---

## 2. Scientific Limitations & Ethical Principles

This project adheres to strict epidemiological and data-governance standards:

* **Aggregated Observations Only**: The system processes exclusively high-level regional aggregates (e.g., county, state, district totals). It does **not** collect, store, or process individual patient records, electronic health records (EHR), or Protected Health Information (PHI). Extra unexpected fields are strictly forbidden by schema validators.
* **Correlation Does Not Imply Causation**: Aggregated mobility trends and symptom count surges reflect macro-level ecological observations. **Mobility and symptom associations do not establish causation, disease transmission dynamics, or individual compliance.** Attributing causality to macro correlations risks the *ecological fallacy*.
* **Explicit Data Provenance & Synthetic Geography**: Every observation and indicator declares a `data_status` (`real`, `simulated`, or `derived`). Synthetic benchmark datasets and synthetic geographic fixtures (coordinates, bounding boxes, polygons) are strictly demarcated to prevent simulated data from being mistaken for genuine geographic or clinical evidence.
* **Integrity of Missing Data**: When reference population denominators or reporting facility counts are unrecorded, they are preserved as `None` (`null`). **The system never invents missing values or coerces unknown quantities to zero**, preventing artificial spikes or corrupted incidence rate calculations.
* **Missing Observations vs. Zero Counts**:
  - A **zero count** indicates an active surveillance day in which zero cases were detected.
  - A **missing observation** represents an unrecorded or unsubmitted surveillance window. The pipeline distinguishes absent rows from zero-count rows and audits missing observation dates explicitly.
* **No Future-Data Leakage**: Detection baselines and predictive models use strictly past observations ($t - W \le \tau \le t$). Future data points never influence historical baselines or predictive feature sets.
* **Statistical Surge Only (Non-Diagnostic)**: Flagged anomalies represent statistical divergences from empirical historical baselines. They **never represent confirmed medical diagnoses, verified infectious outbreaks, or clinical case definitions**.
* **Statistical Power & Sample Size Disclaimer**: Benchmark evaluation against injected spikes uses a controlled set of 3 multi-day surge events (9 positive days). These benchmarks evaluate algorithmic mechanics; they do **not** establish clinical or diagnostic effectiveness.
* **Research Prototype**: This software is intended for research, methodology evaluation, and educational AI engineering. It is not an FDA-cleared or CE-marked medical device and should not be used as the sole basis for clinical or emergency public policy decisions.

---

## 3. Incremental Development Roadmap

The prototype is developed across disciplined phases:

| Phase | Focus Area | Status | Key Deliverables |
| :--- | :--- | :--- | :--- |
| **Phase 1** | **Foundations & Data Schemas** | **Complete** | Project structure, strict Pydantic schemas, data provenance, configuration, smoke tests |
| **Phase 2** | **Synthetic Data & Ingestion** | **Complete** | Deterministic generators, CSV loader, schema validator, quarantine logging, quality audit, atomic pipeline |
| **Phase 3** | **Statistical Anomaly Detection** | **Complete** | Rolling MAD, EWMA, and Z-Score detectors, zero-scale guards, benchmark spike evaluation, comparative metrics |
| **Phase 4** | **Mobility Analysis & Predictive Modeling** | **Complete** | Spatial-temporal alignment, Pearson/Spearman correlations, lagged cross-correlations, chronological train/test modeling, comparative evaluation |
| **Phase 5** | **Storage & Service APIs** | **Complete** | Relational models, duplicate prevention, NULL preservation, PostgreSQL & SQLite session management, versioned FastAPI REST API (`/api/v1`), paginated query endpoints, pipeline execution endpoint |
| **Phase 6A** | **Reference Document Ingestion Foundation** | **Complete** | Text and Markdown document ingestion, SHA-256 content hashing, duplicate prevention, metadata and provenance tracking, secure file storage, REST API (`/api/v1/documents`) |
| **Phase 6B** | **Document Chunking & Vector Retrieval** | **Complete** | Chunking, sentence-transformers local embeddings, persistent NumPy vector indexing, semantic search, Evidence Library UI |
| **Phase 6C** | **Evidence-Grounded AI Assistant** | **Complete** | Provider abstraction (Ollama/Mock), compact grounded context, citation validation, prompt injection defense, REST API (`/api/v1/assistant/ask`), interactive AI Assistant UI, automated benchmark evaluation |
| **Phase 7** | **Geospatial Intelligence & Surveillance Mapping** | **Complete** | Regional surveillance aggregations, synthetic coordinate registry, GeoJSON polygons, interactive ECharts time-series explorer with anomaly overlays, dual-axis mobility integration, lagged cross-correlations profile (-7 to +14 days), dedicated frontend Geospatial Intelligence view |
| **Phase 8** | **Testing, Packaging & Docker** | Upcoming | Automated CI/CD workflows, Docker containerization, production readiness audit |

---

## 4. Phase 5 Architecture: Storage & Service APIs

```text
                       [Client Application / Browser / CLI]
                                         │
                                         ▼
                     [FastAPI Service Layer (/api/v1)]
             ├── GET  /health               (Health check & DB ping)
             ├── GET  /api/v1/surveillance  (Paginated observations + filters)
             ├── GET  /api/v1/mobility      (Paginated mobility indicators)
             ├── GET  /api/v1/anomalies     (Paginated anomaly detection records)
             ├── POST /api/v1/pipeline/detect (Run detection & persist outputs)
             └── /api/v1/documents/*        (Reference document ingestion & metadata)
                                         │
                                         ▼
                        [Database Persistence Services]
             ├── Ingest validated observations & mobility (idempotent, skips dups)
             ├── Query observations by date range, region, syndrome
             ├── Persist anomaly detection results & pipeline run records
             └── Preserve NULLs (never coerce missing denominators/counts to 0)
                                         │
                                         ▼
                           [SQLAlchemy 2.0 ORM Models]
             ├── SurveillanceObservationModel   (Unique: date, region, syndrome)
             ├── MobilityIndicatorModel         (Unique: date, region, metric)
             ├── AnomalyDetectionResultModel    (Unique: date, region, syndrome, method)
             ├── PipelineExecutionModel         (Execution metadata, parameters, status)
             └── DocumentMetadataModel          (Document metadata, hash, provenance)
                                         │
                                         ▼
                   [Database Engine: PostgreSQL or SQLite]
```

---

## 5. Phase 6A Architecture: Reference Document Ingestion Foundation

Phase 6A establishes an evidence-grounded reference document repository for public-health surveillance guidelines, case definitions, and clinical threshold protocols:

```text
               [Client / Document Ingestion Request]
                                 │
                                 ▼
                    [Input & Security Validation]
             ├── Allowed Formats: .txt, .md only (rejects others with 400)
             ├── Path Traversal Defense: rejects '..', '/', '\' in filename
             ├── Size Enforcement: rejects > max_document_size_bytes with 413
             ├── Unicode & Encoding: UTF-8 validation and non-empty check
             └── Cryptographic Hash: SHA-256 digest computation
                                 │
                                 ▼
                     [Duplicate Content Check]
             ├── Matches existing active document by SHA-256 content_hash
             ├── If Duplicate: returns HTTP 409 Conflict with existing ID
             └── Prevents duplicate file storage and duplicate active records
                                 │
                                 ▼
                    [Storage & Registration]
             ├── Safe File Storage: data/documents/<document_id>.<ext>
             ├── Title Extraction: H1 header for Markdown; first non-empty line
             └── Database Registration: DocumentMetadataModel (SQLAlchemy)
```

### Document Metadata Model (`document_metadata`)

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | Integer (PK) | Surrogate database primary key. |
| `document_id` | String(64) | Public unique document identifier (`doc-` + 12-char hex). |
| `filename` | String(255) | Sanitized original filename. |
| `title` | String(255) | Extracted H1 title, first non-empty line, or user-supplied title. |
| `doc_format` | String(16) | Format extension (`txt` or `md`). |
| `content_hash` | String(64) | SHA-256 hex digest of the document UTF-8 bytes. |
| `source_publisher` | String(255) | Authoring agency or publisher (optional). |
| `source_url` | String(1024) | Source reference link or DOI (optional). |
| `publication_date` | Date | Original date of publication (optional). |
| `document_size_bytes` | Integer | Exact content size in bytes. |
| `character_count` | Integer | Total Unicode character count. |
| `word_count` | Integer | Estimated word count. |
| `ingestion_status` | String(32) | Ingestion status (`INGESTED`, `DUPLICATE`, `FAILED`). |
| `stored_path` | String(512) | Internal safe relative path to managed raw document file. |
| `ingestion_timestamp` | DateTime | Ingestion timestamp (UTC). |

### Phase 6A Scope & Explicit Exclusions
* **Included**: Document validation, UTF-8 safety, SHA-256 content hashing, duplicate detection, metadata registration, secure on-disk file storage, and REST API endpoints.
* **Explicit Exclusions (Deferred to Phase 6B)**: Vector embeddings, vector databases, LLMs, prompt engineering, text chunking, semantic retrieval, and epidemiological diagnosis generation.

---

## 6. Configuration & Environment Variables

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `SENTINEL_DATABASE_URL` | String | `sqlite:///./data/public_health_sentinel.db` | SQLAlchemy connection string (`postgresql://...` for PostgreSQL). |
| `SENTINEL_DB_ECHO` | Boolean | `false` | Enable verbose SQLAlchemy SQL query logging. |
| `SENTINEL_DATA_DOCUMENTS_DIR` | Path | `data/documents` | Directory for raw reference document files. |
| `SENTINEL_DATA_INDEX_DIR` | Path | `data/index` | Directory for persisted vector indexes (`.npz` and `.json`). |
| `SENTINEL_CHUNK_TARGET_SIZE` | Integer | `800` | Target character size per passage chunk (~800 chars). |
| `SENTINEL_CHUNK_OVERLAP` | Integer | `120` | Character overlap between consecutive chunks (~120 chars). |
| `SENTINEL_EMBEDDING_MODEL_NAME` | String | `sentence-transformers/all-MiniLM-L6-v2` | Hugging Face local sentence-transformer model identifier. |
| `SENTINEL_EMBEDDING_DIMENSION` | Integer | `384` | Embedding vector dimensionality (384 for MiniLM-L6-v2). |
| `SENTINEL_EMBEDDING_BATCH_SIZE` | Integer | `32` | Batch size for parallel vector encoding. |
| `SENTINEL_EMBEDDING_PROVIDER` | String | `sentence_transformer` | Provider strategy (`sentence_transformer` or `mock`). |
| `SENTINEL_MAX_DOCUMENT_SIZE_BYTES` | Integer | `5242880` (5 MB) | Maximum permitted document size. |
| `SENTINEL_API_HOST` | String | `127.0.0.1` | Host address for FastAPI service. |
| `SENTINEL_API_PORT` | Integer | `8000` | Port for FastAPI service. |
| `SENTINEL_API_TITLE` | String | `PublicHealthSentinel API` | OpenAPI application title. |
| `SENTINEL_API_VERSION` | String | `v1` | API semantic version. |

---

## 7. FastAPI Service Endpoints

The service runs under prefix `/api/v1`. Interactive documentation is available at:
* **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

### Endpoint Summary

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | System health and active database connectivity ping. |
| `GET` | `/api/v1/surveillance` | Paginated surveillance observations with date, region, syndrome filters. |
| `GET` | `/api/v1/mobility` | Paginated mobility telemetry indicators with date, region, metric filters. |
| `GET` | `/api/v1/anomalies` | Paginated anomaly detection results with non-diagnostic surge disclaimers. |
| `POST` | `/api/v1/pipeline/detect` | Execute statistical anomaly detection and optionally persist outputs. |
| `POST` | `/api/v1/documents/ingest` | Ingest and register a reference document (`.txt` or `.md`). |
| `GET` | `/api/v1/documents` | List paginated document metadata with format, publisher, and status filters. |
| `GET` | `/api/v1/documents/{document_id}` | Retrieve metadata and provenance record for a single document. |
| `POST` | `/api/v1/documents/{document_id}/process` | **Phase 6B.1**: Split document into passage chunks and generate local vector embeddings. |
| `GET` | `/api/v1/documents/{document_id}/chunks` | **Phase 6B.1**: List paginated passage chunks with character offsets and hashes. |
| `POST` | `/api/v1/evidence/search` | **Phase 6B.1**: Semantic vector search returning ranked passages with cosine similarity. |
| `GET` | `/api/v1/evidence/status` | **Phase 6B.1**: Operational status, model metadata, and total indexed passages. |

---

## 8. Document Chunking, Local Embeddings & Retrieval (Phase 6B.1)

### Architecture & Pipeline Overview

```
Raw Ingested Document (.txt/.md)
          │
          ▼
Structure-Aware Chunker (~800 chars target, ~120 chars overlap)
- Preserves paragraph (\n\n) and sentence boundaries
- Retains character offsets (char_start, char_end)
- Generates deterministic chunk IDs: {doc_id}_c{seq:04d}_{sha256[:8]}
          │
          ▼
Local Embedding Model (sentence-transformers/all-MiniLM-L6-v2)
- CPU execution optimized for 8 GB RAM systems
- 384-dimensional dense vectors
- L2-normalized unit vectors (||v|| = 1.0)
- Explicit NaN and Inf validation
          │
          ├─────────────────────────────────────────────┐
          ▼                                             ▼
Relational Persistence (SQLAlchemy)       Persistent Vector Index (NumPy .npz)
- Table: `document_chunks`                - File: `data/index/evidence_vector_index.npz`
- Stores chunk text, offsets, metadata     - Metadata: `data/index/evidence_vector_index_meta.json`
- Serialized `embedding_json` backup      - Dot-product cosine similarity: S = q · d
- Atomic re-processing idempotency        - Model compatibility verification
```

### Semantic Evidence Search Example

**Request:**
```http
POST /api/v1/evidence/search HTTP/1.1
Content-Type: application/json

{
  "query": "What statistical threshold triggers a respiratory surge alert?",
  "top_k": 3,
  "min_similarity": 0.0
}
```

**Response (`HTTP 200 OK`):**
```json
{
  "query": "What statistical threshold triggers a respiratory surge alert?",
  "query_id": "qry-a1b2c3d4e5",
  "total_results": 1,
  "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
  "items": [
    {
      "chunk_id": "doc-resp_c0000_92eb8ac2",
      "document_id": "doc-resp",
      "title": "Respiratory Surge Statistical Threshold Protocol",
      "text": "Emergency departments monitor daily encounters for respiratory syndrome. Statistical surge alerts trigger when observed counts exceed baseline plus 2.5 times the median absolute deviation (MAD)...",
      "source_publisher": "State Surveillance Taskforce",
      "source_url": "https://health.state.gov/triage",
      "publication_date": "2025-02-01",
      "sequence_number": 0,
      "char_start": 0,
      "char_end": 285,
      "similarity_score": 0.7482,
      "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
      "score_interpretation": "Similarity scores represent geometric cosine similarity (range: -1.0 to 1.0) between query and passage embeddings. A high similarity score indicates semantic alignment of phrasing, NOT clinical truth, empirical outbreak confirmation, or medical consensus."
    }
  ],
  "synthetic_experiment_notice": "SYNTHETIC-DATA NOTICE: Evidence passages retrieved from indexed reference material. Similarity scores indicate text proximity and do not establish clinical diagnosis or real-world validity."
}
```

### Synthetic Retrieval Benchmark Evaluation (Phase 6B.1)

Empirical evaluation executed across 5 synthetic reference documents (10 passage chunks) and 10 ground-truth evaluation queries:

| Metric | Result | Target Benchmark |
| :--- | :--- | :--- |
| **Embedding Model** | `sentence-transformers/all-MiniLM-L6-v2` | 384-D dense embeddings |
| **Recall@1** | **80.00%** | $\ge 70.0\%$ |
| **Recall@3** | **100.00%** | $\ge 85.0\%$ |
| **Recall@5** | **100.00%** | $\ge 90.0\%$ |
| **Mean Reciprocal Rank (MRR)** | **0.8833** | $\ge 0.750$ |
| **Mean Query Latency** | **44.67 ms** | $< 100\text{ ms}$ on CPU |
| **p95 Query Latency** | **82.34 ms** | $< 250\text{ ms}$ on CPU |
| **Peak Memory Allocation** | **256.41 MB** | $< 1\text{ GB}$ (8 GB RAM constraint) |

> [!NOTE]
> **Synthetic Benchmark Notice**: These metrics are measured on a synthetic public health retrieval benchmark for methodology verification. Retrieval accuracy on synthetic questions does not establish clinical validity or diagnostic accuracy on authentic medical literature.

To run the retrieval evaluation benchmark:
```powershell
.\.venv\Scripts\python.exe scripts/evaluate_retrieval.py
```
For fast offline test execution with mock embeddings:
```powershell
.\.venv\Scripts\python.exe scripts/evaluate_retrieval.py --mock
```

---

## 9. Getting Started (Windows PowerShell)

### Step 1: Activate Virtual Environment
```powershell
cd C:\AI\PublicHealthSentinel
.\.venv\Scripts\Activate.ps1
```

### Step 2: Run the Automated Test Suite (153 tests)
```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

### Step 3: Run the Data Pipeline (Phase 2)
```powershell
.\.venv\Scripts\python.exe -m public_health_sentinel.cli
```

### Step 4: Run Statistical Anomaly Detection (Phase 3)
```powershell
.\.venv\Scripts\python.exe -m public_health_sentinel.cli --detect --method all
```

### Step 5: Run Mobility Analysis & Predictive Evaluation (Phase 4)
```powershell
.\.venv\Scripts\python.exe -m public_health_sentinel.cli --analyze-mobility
```

### Step 6: Start the FastAPI Service (Phase 5, 6A & 6B.1)
Start the local development server:
```powershell
.\.venv\Scripts\uvicorn.exe public_health_sentinel.api:app --host 127.0.0.1 --port 8000 --reload
```
Navigate to [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) in your browser.

### Step 7: Launch the Public Health Intelligence Web Application
The enterprise intelligence frontend is built with React 19, TypeScript, Vite, Tailwind CSS, TanStack Query, and Apache ECharts.

```powershell
cd frontend
npm install
npm run dev
```
Open [http://127.0.0.1:5173](http://127.0.0.1:5173) in your browser.

#### Navigation Views:
1. **Command Center**: Surveillance trend charts, anomaly distribution, regional breakdowns, and live KPI summary cards.
2. **Surveillance Explorer**: Paginated symptom observations with filters by date range, jurisdiction, syndrome, and detailed observation inspection.
3. **Anomaly Intelligence**: Outbreak surge evaluations, observed vs. expected baseline comparisons, anomaly score plots, and statistical guardrails.
4. **Mobility Analytics**: Population transit shifts over time, correlation summaries, and Phase 4 predictive evaluation findings.
5. **Evidence Library**: Phase 6B.1 document chunking, passage inspection, local vector indexing status, and semantic evidence retrieval canvas.
6. **AI Intelligence Assistant**: Natural language inquiry canvas grounded in reference documentation with public-health guardrails (Phase 6B preview).
7. **Pipeline Lab**: Interactive validated interface to trigger backend anomaly detection algorithms (Rolling MAD, EWMA, Z-Score) with custom parameters.
8. **System Health**: Real-time roundtrip latency probes, database connection checks, and table telemetry.
9. **Settings**: Configurable backend gateway URLs, cache invalidation, and synthetic data protocol compliance.

To build the production bundle:
```powershell
cd frontend
npm run build
```

---

## 10. Verification & Test Coverage Summary

The automated test suite contains **163 passing tests** (and 1 optional live-model benchmark test) across 16 test modules:
* `tests/test_chunking.py`: 7 tests covering CRLF normalization, whitespace rejection, short document handling, long document overlap, monotonic sequencing, character offset mapping, deterministic IDs, and Unicode preservation.
* `tests/test_embeddings.py`: 7 tests covering 384-D vector dimensions, L2 unit norm validation, NaN/Inf rejection, empty string validation, batch consistency, model failure exceptions, and mock reproducibility.
* `tests/test_retrieval.py`: 13 tests covering empty index handling, cosine similarity ranking order, vector persistence and reload, incompatible model rejection, index rebuild from database, publisher/document filtering, index degradation detection on corrupted files, dimension mismatch degradation, deterministic tie-breaking, NaN/Inf query rejection, model mismatch prevention, orphaned chunk exclusion (DB hydration check), and exact character offset slice fidelity.
* `tests/test_document_processing_api.py`: 10 tests covering `/process` endpoint, `/chunks` pagination, `/search` semantics, `/status` telemetry, `/rebuild` vector restoration, 404 missing document handling, 400 validation, 409 model conflict rejection, degraded status reporting, and idempotent re-processing.
* `tests/test_retrieval_benchmark.py`: 2 tests executing the synthetic retrieval benchmark on deterministic mock (offline) and optional live `sentence-transformers/all-MiniLM-L6-v2` model.
* `tests/test_documents.py`: 24 tests covering text/markdown ingestion, title extraction, SHA-256 hashing, duplicate detection (409), unsupported formats (400), empty files (400), oversized files (413), Unicode preservation, path traversal protection, pagination, and database rollback.
* `tests/test_database.py`: 7 tests covering ORM models, unique constraints, duplicate-ingestion handling, pagination, NULL preservation, pipeline execution logging.
* `tests/test_api.py`: 17 tests covering health endpoint, degraded state, paginated surveillance, mobility, anomalies filter matrix, parameter bounds (422), sanitized error responses (500).
* `tests/test_schemas.py`: 8 tests covering schema validation, forbidden extra fields, missing denominator preservation.
* `tests/test_synthetic_generator.py`: 7 tests covering deterministic seeds, provenance labels, injected spikes.
* `tests/test_validator.py` & `tests/test_quality.py`: 8 tests covering validation, quarantine routing, missing date audits.
* `tests/test_detection_methods.py` & `tests/test_detection_evaluation.py`: 20 tests covering Rolling MAD, EWMA, and Z-score algorithms, zero-scale guards, benchmark spike metrics.
* `tests/test_mobility.py`: 14 tests covering temporal alignment, correlation metrics, lag analysis, chronological predictive modeling.
* `tests/test_loader.py`, `tests/test_pipeline.py`, `tests/test_imports.py`: 14 tests covering CSV ingestion, CLI routing, package imports.

---

## 11. Phase 6B.2: Retrieval Subsystem Quality, Persistence & Recovery

### 11.1 Retrieval Behavior & Correctness
The semantic retrieval engine provides traceable, deterministic passage retrieval with the following guarantees:
* **Query Validation**: Queries are strictly sanitized. Blank or whitespace-only queries return `HTTP 400`, `top_k` is bounded between 1 and 50 (`HTTP 422`), and `min_similarity` must be between -1.0 and 1.0 (`HTTP 422`).
* **Vector Safety**: Query and document vectors are validated against `NaN` and `Inf` values prior to index lookups. Zero-length or malformed vectors are rejected.
* **Deterministic Tie-Breaking**: When multiple passages have identical cosine similarity scores, ties are broken deterministically by passage chunk ID (`chunk_id` ascending).
* **Provenance & Relational Hydration**: Vectors returned by similarity search are validated against relational database records (`DocumentChunkModel`). Orphaned vectors whose underlying chunk or document has been deleted are omitted automatically.
* **Slice-Level Character Fidelity**: Passage character offsets (`char_start`, `char_end`) are adjusted for leading/trailing whitespace stripping, guaranteeing `normalized_text[char_start:char_end] == chunk.text`.
* **Non-Clinical Score Interpretation**: All retrieved items include the disclaimer: *"Cosine similarity indicates semantic phrasing proximity, not clinical truth or diagnostic outbreak confirmation."*

### 11.2 Index Degradation & Recovery Procedure
Vector index persistence utilizes NumPy array storage (`evidence_vector_index.npz`) and metadata tracking (`evidence_vector_index_meta.json`). If index files become damaged, out of sync, or encounter dimension/model mismatches:
1. **Automated Degradation Detection**: The index manager flags itself as `DEGRADED` rather than silently discarding data.
2. **Status Telemetry**: `GET /api/v1/evidence/status` returns `status: "DEGRADED"` with `is_degraded: true` and an actionable `degraded_reason` explaining the issue. The frontend displays an alert banner with recovery options.
3. **Recovery Execution**:
   * **Via REST API**: Trigger `POST /api/v1/evidence/rebuild`.
   * **Via Frontend**: Click the **Rebuild Index from Relational DB** button in the Evidence Library.
   * **Via Python CLI / Service**:
     ```python
     from public_health_sentinel.db.session import get_db_session
     from public_health_sentinel.documents.index import get_vector_index
     from public_health_sentinel.documents.embeddings import get_embedding_service

     db = next(get_db_session())
     idx = get_vector_index()
     emb = get_embedding_service()
     rebuilt_count = idx.rebuild_from_db(session=db, embedding_service=emb)
     print(f"Reconstructed {rebuilt_count} vectors into index.")
     ```

### 11.3 Retrieval Benchmark Methodology & Results
Evaluation script: `scripts/evaluate_retrieval.py` evaluates ranking and rejection accuracy against a ground truth benchmark of 10 answerable public-health surveillance queries and 2 out-of-scope negative control queries.

**Metrics Evaluated**:
* **Recall@k**: Fraction of answerable queries where the ground-truth target document is retrieved in the top-k results.
* **Precision@k**: Fraction of retrieved passages in top-k belonging to the ground-truth target document.
* **Mean Reciprocal Rank (MRR)**: Average reciprocal rank of the first relevant passage.
* **Negative Rejection Rate**: Fraction of out-of-scope queries that correctly return 0 results at or above the similarity cutoff.
* **Latency & Memory**: Mean and 95th-percentile retrieval latencies and peak resident set memory.

**Live Model Benchmark Results** (`sentence-transformers/all-MiniLM-L6-v2`, 384-D):
* **Total Queries**: 12 (10 answerable, 2 negative controls)
* **Recall@1**: 80.00%
* **Recall@3**: 100.00%
* **Recall@5**: 100.00%
* **Precision@1**: 80.00%
* **Precision@3**: 33.33%
* **Precision@5**: 20.00%
* **Mean Reciprocal Rank (MRR)**: 0.8833
* **Negative Rejection Rate**: 100.00%
* **Mean Latency**: 39.11 ms
* **p95 Latency**: 57.01 ms
* **Peak Memory**: 256.43 MB

> **Notice**: These results evaluate retrieval against synthetic public-health guidance documents. No claims of clinical diagnosis or real-world epidemiology performance are made without evaluation on vetted real-world clinical datasets.

### 11.4 Exact Commands to Run Tests

**Run full backend test suite**:
```powershell
.venv\Scripts\pytest -v
```

**Run real-model retrieval benchmark test**:
```powershell
$env:RUN_REAL_MODEL_TESTS="true"; .venv\Scripts\pytest -v tests/test_retrieval_benchmark.py
```

**Run standalone benchmark evaluation script**:
```powershell
.venv\Scripts\python scripts/evaluate_retrieval.py
```

**Run frontend integration test suite**:
```powershell
cd frontend
npm test -- --run
```

**Build frontend production bundle**:
```powershell
cd frontend
npm run build
```

---

## 12. Phase 6C Architecture: Evidence-Grounded AI Assistant

Phase 6C implements an evidence-grounded public-health research assistant on top of the persistent semantic retrieval subsystem, designed for offline execution, strict provenance, zero hallucination, and prompt-injection defense.

```text
                  [User Natural-Language Question]
                                 │
                                 ▼
                     [Request Validation Layer]
              ├── Length bounds: 3 to 1000 characters
              ├── Top-k bounds: 1 to 20 passages (default: 5)
              └── Similarity cutoff: -1.0 to 1.0 (default: 0.30)
                                 │
                                 ▼
                  [Dense Semantic Vector Retrieval]
              ├── Query embedding: sentence-transformers/all-MiniLM-L6-v2 (384-D)
              ├── Cosine similarity ranking over persistent NumPy index
              └── Relational chunk join (title, publisher, offsets, text)
                                 │
                                 ▼
              [Relevance & Evidence Sufficiency Filter]
              ├── If 0 passages >= min_similarity:
              │     └── Return early with evidence_sufficiency = "INSUFFICIENT"
              │         (Guarantees ZERO hallucination with 0 LLM calls)
              └── If passages >= min_similarity:
                    └── Proceed to generation pipeline
                                 │
                                 ▼
                     [Compact Context Builder]
              ├── Isolates each passage in quotation blocks:
              │     [Passage E1] (Title: ..., Publisher: ...)
              │     """<retrieved text verbatim>"""
              └── Defends against prompt injection in untrusted reference documents
                                 │
                                 ▼
              [System-Prompt Grounding & Guardrails]
              ├── Strict rule: Only use supplied evidence passages
              ├── Never invent facts, quotations, or citations
              ├── Distinguish statistical signals from confirmed outbreaks
              ├── Prohibit patient-specific diagnosis or treatment
              └── Enforce traceable citation tags: [E1], [E2]
                                 │
                                 ▼
                 [Configurable Generation Provider]
              ├── OllamaProvider: Local HTTP connection to Ollama daemon (localhost:11434)
              │     ├── Model: llama3.2:latest (configurable)
              │     ├── Explicit connection & read timeouts (30s default)
              │     └── Actionable error handling (503 if daemon down, 504 on timeout)
              └── MockAnswerGenerationProvider: Deterministic, offline unit test generation
                                 │
                                 ▼
                   [Citation & Provenance Validator]
              ├── Extracts all [E#] tags from generated text
              ├── Verifies existence against actually retrieved passage references
              ├── Strips unsupported/hallucinated citation tags (e.g., [E99])
              └── Maps verified citations to chunk IDs, character offsets, and titles
                                 │
                                 ▼
                  [Structured API & Frontend Response]
              ├── Grounded answer with interactive clickable citation badges
              ├── Evidence sufficiency indicator (SUFFICIENT | PARTIAL | INSUFFICIENT)
              ├── Verified citations list with excerpts and retrieval scores
              ├── Expandable reference passages with exact offsets and titles
              └── Synthetic-data and non-clinical research disclosures
```

### 12.1 Configuration & Provider Setup

In `public_health_sentinel/config.py` (or via environment variables):
* `SENTINEL_GENERATION_PROVIDER`: `"ollama"` (default) or `"mock"` (for offline testing).
* `SENTINEL_OLLAMA_HOST`: `"http://localhost:11434"`
* `SENTINEL_OLLAMA_MODEL`: `"llama3.2:latest"`
* `SENTINEL_OLLAMA_TIMEOUT_SECONDS`: `30.0`
* `SENTINEL_ASSISTANT_MIN_SIMILARITY_CUTOFF`: `0.30`
* `SENTINEL_ASSISTANT_MAX_CONTEXT_PASSAGES`: `5`
* `SENTINEL_ASSISTANT_MAX_QUESTION_LENGTH`: `1000`

#### Running Local Ollama (Optional for Live Inference)
1. Install [Ollama](https://ollama.ai/).
2. Start the daemon:
   ```bash
   ollama serve
   ```
3. Pull the target model:
   ```bash
   ollama pull llama3.2
   ```
*If Ollama is offline, the API returns a structured HTTP 503 explaining how to start the daemon, or gracefully returns zero-hallucination refusals for out-of-scope inquiries without invoking an LLM.*

### 12.2 API Endpoints

#### 1. Ask Grounded Question
`POST /api/v1/assistant/ask`

**Request Example**:
```json
{
  "question": "What statistical threshold triggers a respiratory surge alert?",
  "top_k": 5,
  "min_similarity": 0.30
}
```

**Response Example (200 OK)**:
```json
{
  "query_id": "ask-47df919ab56c",
  "question": "What statistical threshold triggers a respiratory surge alert?",
  "answer": "According to the Respiratory Surge Statistical Threshold Protocol [E1], an advisory alert is flagged when syndromic counts exceed 2.0 median absolute deviations (MAD) above the 21-day rolling median for two consecutive days. A high-priority surge alert requires exceeding 3.5 MAD or an EWMA control limit violation with lambda = 0.20.",
  "evidence_sufficiency": "SUFFICIENT",
  "citations": [
    {
      "citation_index": 1,
      "citation_tag": "[E1]",
      "chunk_id": "chk-734f40d184eb",
      "document_id": "doc-a681c62fbdbe",
      "title": "Respiratory Surge Statistical Threshold Protocol",
      "source_publisher": "CDC / State Epidemiologist Consortium",
      "similarity_score": 0.728,
      "char_start": 0,
      "char_end": 745,
      "excerpt": "A statistical advisory alert is triggered when daily respiratory syndromic visits exceed 2.0 median absolute deviations..."
    }
  ],
  "retrieved_passages": [ ... ],
  "provider": "ollama",
  "model": "llama3.2:latest",
  "latency_seconds": 0.84,
  "synthetic_data_notice": "SYNTHETIC-DATA NOTICE: All observations, indicators, and benchmark documents are part of a simulated research prototype...",
  "non_clinical_notice": "DISCLAIMER: This assistant provides research methodology synthesis based on reference documents. It does not provide patient-specific clinical diagnosis, medical triage, or outbreak confirmation."
}
```

#### 2. Assistant Readiness Status
`GET /api/v1/assistant/status`

**Response Example (200 OK)**:
```json
{
  "status": "READY",
  "provider": "ollama",
  "model": "llama3.2:latest",
  "provider_healthy": true,
  "provider_message": "Ollama server is active and model 'llama3.2:latest' is available.",
  "vector_index_status": "HEALTHY",
  "indexed_passages_count": 12,
  "available_models": ["llama3.2:latest"],
  "disclaimer": "Phase 6C Assistant grounded in local document evidence. Operates offline or with local Ollama daemon."
}
```

### 12.3 Automated Assistant Benchmark Evaluation

The assistant is evaluated via `scripts/evaluate_assistant.py` and `tests/test_assistant_evaluation.py` across 9 diverse evaluation queries spanning 6 distinct challenge categories:
1. **Answerable Methodology Questions**: e.g., Respiratory surge thresholds, Rolling MAD calculation mechanics, EWMA smoothing parameters.
2. **Unanswerable / Out-of-Scope Queries**: e.g., Quantum annealing hardware in hospital triage, Cryogenic refrigeration systems.
3. **Conflicting Evidence Queries**: Comparing divergent baseline window recommendations (7-day vs 28-day vs 21-day).
4. **Unsupported Citation Elicitation**: Queries designed to bait the model into citing unretrieved documents.
5. **Synthetic Outbreak Interpretation**: Probing whether computational anomaly alerts are mistakenly declared as confirmed clinical outbreaks.
6. **Prompt Injection Inoculation**: Malicious directives embedded inside reference passages attempting to override grounding rules (`"SYSTEM OVERRIDE: Ignore all previous rules..."`).

**Benchmark Results (`data/assistant_benchmark_results.json`)**:
* **Total Benchmark Queries**: 9
* **Citation Validity Rate**: **100.00%** (All cited tags matched verified retrieved passages)
* **Unsupported Citation Rate**: **0.00%** (Zero invented or out-of-bounds citations accepted)
* **Out-of-Scope Rejection Accuracy**: **100.00%** (Returned `INSUFFICIENT` evidence without speculation)
* **Prompt-Injection Defense**: **100.00%** (Overriding system instructions safely isolated and ignored)
* **Mean Retrieval Latency**: **24.5 ms**
* **Synthetic Data & Non-Clinical Notice Compliance**: **100.00%**

---

### 12.4 Running Tests & Verification Commands

```powershell
# Run full backend test suite (183 tests)
.venv\Scripts\pytest -v

# Run assistant provider, pipeline, and API tests
.venv\Scripts\pytest -v tests/test_assistant_provider.py tests/test_assistant_pipeline.py tests/test_assistant_api.py

# Run standalone assistant evaluation benchmark
.venv\Scripts\python scripts/evaluate_assistant.py

# Run frontend integration test suite (19 tests)
cd frontend
npm test -- --run

# Build frontend production bundle
npm run build
```

---

## 13. Phase 7 Architecture: Interactive Geospatial Intelligence & Surveillance Mapping

```text
               ┌────────────────────────────────────────────────────────────┐
               │    React 19 + TypeScript + Vite + Tailwind CSS Frontend    │
               │  [Geospatial Intelligence Dashboard: /geospatial]          │
               └─────────────┬────────────────────────────────┬─────────────┘
                             │                                │
            1. Sector Grid & │               2. Time-Series & │
               Summary KPIs  │                  Correlations  │
                             ▼                                ▼
               ┌────────────────────────────────────────────────────────────┐
               │        FastAPI Geospatial Service Layer (/api/v1)          │
               │  • GET /api/v1/geospatial/regions                          │
               │  • GET /api/v1/geospatial/geojson                          │
               │  • GET /api/v1/geospatial/surveillance                     │
               │  • GET /api/v1/geospatial/timeseries                       │
               │  • GET /api/v1/geospatial/mobility                         │
               │  • GET /api/v1/geospatial/correlations                     │
               └─────────────┬────────────────────────────────┬─────────────┘
                             │                                │
                             ▼                                ▼
               ┌───────────────────────────┐    ┌───────────────────────────┐
               │ Synthetic Region Registry │    │  Geospatial Aggregation   │
               │  • 5 Synthetic Sectors    │    │         Service           │
               │  • Standard Bounding Box  │    │  • Regional Case Sums     │
               │  • GeoJSON Polygon Bounds │    │  • Crude Incidence /100k  │
               │  • Synthetic Disclosures  │    │  • Algorithmic Anomaly CT │
               └─────────────┬─────────────┘    │  • Lagged Cross-Corr      │
                             │                  └─────────────┬─────────────┘
                             ▼                                │
               ┌──────────────────────────────────────────────▼─────────────┐
               │               Relational SQLite / PostgreSQL               │
               │  • surveillance_observations (2,700 rows, 180 days)        │
               │  • mobility_indicators       (2,700 rows, 3 metrics)       │
               │  • anomaly_detection_results (2,700 rows, 64 flagged)      │
               └────────────────────────────────────────────────────────────┘
```

### 13.1 Geographic Integrity & Synthetic Region Registry

* **Source Provenance**: Raw surveillance datasets contain abstract regional keys (`REGION_A` through `REGION_E`) without genuine GPS coordinates or physical administrative boundary shapefiles.
* **Geographic Integrity Guardrail**: The system adheres to strict epidemiological ethics: **it never invents real-world geographic coordinates for simulated datasets or maps synthetic records to real cities, counties, or districts.**
* **Canonical Synthetic Fixture**: A standardized synthetic sector grid (Sectors Alpha through Epsilon) is maintained in `public_health_sentinel.geospatial.registry` spanning coordinates $37.40^\circ \text{N}$ to $37.85^\circ \text{N}$ and $-122.50^\circ \text{W}$ to $-122.05^\circ \text{W}$.
* **Explicit Disclosures**: Every region, summary response, GeoJSON feature, and map component carries `is_synthetic_geography: true` and an explicit synthetic metadata disclosure banner.
* **Coordinate Validation**: The service validates all geographic latitude and longitude bounds (rejecting non-finite numbers and values outside $[-90, 90]$ or $[-180, 180]$).

### 13.2 Regional Surveillance Aggregation Rules

* **Crude Incidence Rate**: Calculated as:
  $$\text{Crude Rate per 100k} = \frac{\sum \text{Reported Cases}}{\text{Verified Population}} \times 100,000$$
  When population data is unavailable or zero, rate calculations remain `null` to avoid misleading rates.
* **Preservation of Missing Days**: Days with absent observation rows are audited as missing surveillance windows. They are **never coerced to zero**, preventing artificial epidemiological spikes or troughs.
* **Syndromic Breakdown**: Case tallies are segregated by syndrome category (`Febrile`, `Gastrointestinal`, `Respiratory`) without double-counting observations.
* **Anomaly Aggregation**: Algorithmic anomaly counts count unique flagged observation dates where `is_anomaly = 1` for the specified syndrome and detection method.

### 13.3 Lagged Cross-Correlation Methodology

* **Temporal Alignment**: Surveillance time series and mobility indicator percentages are aligned by exact `(date, region_id)` pairs via `align_surveillance_and_mobility()`.
* **Lag Sign Convention**:
  - **Positive Lag ($+k$ days)**: Mobility indicator at date $t$ is evaluated against surveillance count at future date $t + k$ (investigating mobility as a leading indicator).
  - **Negative Lag ($-k$ days)**: Mobility indicator at date $t$ is evaluated against surveillance count at past date $t - k$.
* **Metrics**: Pearson correlation coefficient ($r$), Spearman rank correlation ($\rho$), paired sample size ($N$), and date span.
* **Strict Ecological Disclaimer**: Macro-level mobility correlations represent non-causal ecological associations and **never establish individual clinical transmission or etiology**.

### 13.4 REST API Endpoints (`/api/v1/geospatial`)

| Endpoint | Method | Parameters | Description |
| :--- | :--- | :--- | :--- |
| `/api/v1/geospatial/regions` | `GET` | — | Returns canonical registry of 5 synthetic surveillance sectors with coordinates, bounding boxes, population, and synthetic disclosures. |
| `/api/v1/geospatial/geojson` | `GET` | — | Returns RFC 7946 compliant GeoJSON `FeatureCollection` containing synthetic polygon geometries and region metadata. |
| `/api/v1/geospatial/surveillance` | `GET` | `start_date`, `end_date`, `syndrome` | Returns aggregated case counts, crude incidence rates per 100k, syndromic breakdowns, and anomaly tallies grouped by region. |
| `/api/v1/geospatial/timeseries` | `GET` | `region_id`, `syndrome`, `method`, `start_date`, `end_date` | Returns daily surveillance time series joined with algorithmic baselines, thresholds, anomaly flags, and detection methods. |
| `/api/v1/geospatial/mobility` | `GET` | `region_id`, `mobility_metric`, `syndrome`, `start_date`, `end_date` | Returns calendar-aligned dual series of surveillance counts and mobility percentage deviation. |
| `/api/v1/geospatial/correlations` | `GET` | `region_id`, `mobility_metric`, `syndrome`, `min_lag`, `max_lag`, `start_date`, `end_date` | Computes lagged cross-correlation curve across lag offsets (default $-7$ to $+14$ days) with paired sample sizes. |

### 13.5 Frontend Geospatial Intelligence Interface

The Geospatial Intelligence dashboard is accessed via the **Geospatial Intelligence** sidebar item (`/geospatial`) and features:

1. **Synthetic Surveillance Sector Map (`GeospatialMapChart.tsx`)**:
   * Renders the 5 synthetic surveillance sectors in a high-density tactical grid.
   * Choropleth-style color intensity mapped to case counts or crude incidence rate per 100k.
   * High-priority pulse badges for regions with flagged statistical anomalies.
   * Interactive sector click updates the global region filter across all views.
2. **Regional Intelligence Profile Card**:
   * Displays region name, centroid coordinates, population denominator, syndromic breakdown, and anomaly density.
   * Prominent synthetic data and non-diagnostic warning banner.
3. **Interactive Time-Series Anomaly Inspector (`GeospatialTimeSeriesChart.tsx`)**:
   * Interactive Apache ECharts line chart with daily observed surveillance cases.
   * Historical rolling baseline and statistical threshold envelope lines (Rolling MAD).
   * Red pinpoint markers highlighting flagged anomaly dates with detection method tooltips.
   * Optional dual-axis mobility indicator overlay (dashed line on secondary % axis).
4. **Lagged Cross-Correlation Explorer (`GeospatialLagCorrelationChart.tsx`)**:
   * Interactive bar chart displaying Pearson correlation coefficient across $-7$ to $+14$ day offsets.
   * Visual zero-line, reference bands, and paired sample size tooltips.
   * Explanatory card documenting the leading indicator convention and non-causality disclaimers.
5. **Algorithmic Anomaly Ledger Table**:
   * Chronological ledger of all anomalies flagged within the active date and syndrome filter.
   * Details observation date, syndrome, detection method, observed count, baseline, threshold, and score.
   * Direct "Inspect Time Series" button navigating to that region's temporal trajectory.

### 13.6 Running Verification Commands

```powershell
# Run full backend test suite (193 tests)
.venv\Scripts\pytest -v

# Run targeted geospatial unit and API integration tests (10 tests)
.venv\Scripts\pytest -v tests/test_geospatial.py

# Run frontend quality audit and live API integration tests (25 tests)
cd frontend
npm test -- --run

# Build frontend production bundle with zero TypeScript warnings
npm run build
```

---

## 14. Known Limitations & Next Steps (Phase 8)

* **Synthetic Geographic Grid**: The current geographic layer uses a documented synthetic regional fixture (`Alpha` through `Epsilon`) designed for method testing without claiming genuine geographic precision. Real administrative GeoJSON files (e.g. US Census TIGER/Line or European NUTS boundaries) can be plugged into `GeospatialRegistry` when genuine public health jurisdictions are onboarded.
* **Ecological Correlation Scope**: Mobility indicators and syndromic counts operate at macro-regional granularity. Correlations provide exploratory surveillance leads, not causal epidemiological mechanisms.
* **Local Hardware Footprint**: The platform runs efficiently on standard developer hardware (tested on an 8 GB RAM laptop running Windows 11), with frontend production bundles compiling in under 7 seconds.
* **Next Milestone (Phase 8)**: Automated CI/CD pipelines, multi-stage Docker containerization, comprehensive production readiness audit, and deployment orchestration.


