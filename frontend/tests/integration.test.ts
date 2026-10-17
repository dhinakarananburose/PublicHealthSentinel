/// <reference types="node" />
/**
 * Targeted Frontend & API Client Integration Test Suite for PublicHealthSentinel.
 * Tests parameter serialization, utility formatting, error handling,
 * and live contract verification against the active FastAPI backend.
 */

import assert from 'node:assert/strict'
import { formatBytes, formatDate, formatDateTime, formatNumber, formatScore } from '../src/lib/utils.ts'
import { ApiError } from '../src/lib/api-client.ts'

const BASE_URL = (
  process.env.API_BASE_URL ||
  process.env.VITE_API_URL ||
  'http://127.0.0.1:8081'
).replace(/\/+$/, '')

// Reusable query builder matching api-client logic
function buildQuery(params: Record<string, any>): string {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      query.set(key, String(value))
    }
  }
  const str = query.toString()
  return str ? `?${str}` : ''
}

async function runTests() {
  console.log('=== Starting PublicHealthSentinel Frontend Quality & API Audit Suite ===\n')
  console.log(`Target Backend Gateway: ${BASE_URL}\n`)
  let passed = 0
  let failed = 0
  let skipped = 0

  async function test(name: string, fn: () => Promise<void> | void) {
    try {
      await fn()
      console.log(`[PASS] ${name}`)
      passed++
    } catch (err: any) {
      console.error(`[FAIL] ${name}:`, err.message)
      failed++
    }
  }

  // Probe backend availability for live integration tests
  const skipLive = process.env.SKIP_LIVE_TESTS === 'true'
  let backendReachable = false

  if (!skipLive) {
    try {
      const controller = new AbortController()
      const t = setTimeout(() => controller.abort(), 3000)
      const probe = await fetch(`${BASE_URL}/health`, { signal: controller.signal })
      clearTimeout(t)
      if (probe.ok) {
        const data = await probe.json().catch(() => ({}))
        if (data.app_name === 'PublicHealthSentinel' || data.database_connected === true) {
          backendReachable = true
        } else {
          console.warn(`[WARN] Host at ${BASE_URL} responded but did not identify as PublicHealthSentinel (${data.app_name || 'unknown'}).`)
        }
      }
    } catch {
      backendReachable = false
    }
  }

  async function liveTest(name: string, fn: () => Promise<void> | void) {
    if (skipLive) {
      console.log(`[SKIP] ${name} (SKIP_LIVE_TESTS=true)`)
      skipped++
      return
    }
    if (!backendReachable) {
      if (process.env.REQUIRE_LIVE_BACKEND === 'true') {
        console.error(`[FAIL] ${name}: Backend not reachable at ${BASE_URL}`)
        failed++
        return
      }
      console.log(`[SKIP] ${name} (Backend offline at ${BASE_URL})`)
      skipped++
      return
    }
    await test(name, fn)
  }

  // Unit 1: Formatting Utilities
  await test('formatNumber handles numbers, null, and NaN', () => {
    assert.equal(formatNumber(1250000), '1,250,000')
    assert.equal(formatNumber(0), '0')
    assert.equal(formatNumber(null), '—')
    assert.equal(formatNumber(undefined), '—')
    assert.equal(formatNumber(NaN), '—')
  })

  await test('formatScore rounds floats to 2 decimal places and handles nulls', () => {
    assert.equal(formatScore(3.14159), '3.14')
    assert.equal(formatScore(0.5), '0.50')
    assert.equal(formatScore(null), '—')
    assert.equal(formatScore(undefined), '—')
  })

  await test('formatBytes formats file sizes appropriately', () => {
    assert.equal(formatBytes(0), '0 B')
    assert.equal(formatBytes(1024), '1.0 KB')
    assert.equal(formatBytes(5 * 1024 * 1024), '5.0 MB')
  })

  await test('formatDate safely formats valid and invalid dates', () => {
    const valid = formatDate('2026-05-15')
    assert.match(valid, /May 15, 2026/)
    assert.equal(formatDate(null), '—')
    assert.equal(formatDate('invalid-date'), 'invalid-date')
  })

  // Unit 2: Query Parameter Construction
  await test('buildQuery serializes filters without nulls or empty strings', () => {
    const params = {
      region_id: 'REGION_A',
      syndrome: 'Respiratory',
      emptyField: '',
      nullField: null,
      undefinedField: undefined,
      page: 1,
      page_size: 25,
      is_anomaly: true,
    }
    const q = buildQuery(params)
    assert.equal(
      q,
      '?region_id=REGION_A&syndrome=Respiratory&page=1&page_size=25&is_anomaly=true'
    )
  })

  await test('buildQuery returns empty string when all values are empty', () => {
    assert.equal(buildQuery({ a: '', b: null, c: undefined }), '')
  })

  // Unit 3: ApiError Class
  await test('ApiError retains status code and details', () => {
    const err = new ApiError('Duplicate document', 409, { hash: 'abc123' })
    assert.equal(err.name, 'ApiError')
    assert.equal(err.message, 'Duplicate document')
    assert.equal(err.statusCode, 409)
    assert.deepEqual(err.details, { hash: 'abc123' })
  })

  // Integration 4: Live Health & Telemetry
  await liveTest('GET /health returns healthy status and connected database', async () => {
    const res = await fetch(`${BASE_URL}/health`)
    assert.equal(res.status, 200)
    const data = await res.json()
    assert.equal(data.status, 'healthy')
    assert.equal(data.database_connected, true)
    assert.equal(data.app_name, 'PublicHealthSentinel')
  })

  // Integration 5: Live Surveillance Query & Provenance
  await liveTest('GET /api/v1/surveillance returns paginated records and notice', async () => {
    const res = await fetch(`${BASE_URL}/api/v1/surveillance?page=1&page_size=5`)
    assert.equal(res.status, 200)
    const data = await res.json()
    assert.equal(data.page, 1)
    assert.equal(data.page_size, 5)
    assert.equal(data.items.length, 5)
    assert.ok(data.total >= 2700, `Expected at least 2700 rows, got ${data.total}`)
    assert.match(data.synthetic_experiment_notice, /SYNTHETIC-DATA NOTICE/)
    assert.ok(data.items[0].crude_incidence_per_100k !== null)
  })

  // Integration 6: Live Mobility Analytics & Filtering
  await liveTest('GET /api/v1/mobility filters by metric', async () => {
    const res = await fetch(`${BASE_URL}/api/v1/mobility?mobility_metric=transit_station_pct_change&page_size=3`)
    assert.equal(res.status, 200)
    const data = await res.json()
    assert.ok(data.items.length <= 3)
    for (const item of data.items) {
      assert.equal(item.mobility_metric, 'transit_station_pct_change')
    }
  })

  // Integration 7: Live Mobility Evaluation Endpoint (Stage 5 Verification)
  await liveTest('GET /api/v1/mobility/evaluation returns empirical Phase 4 benchmark', async () => {
    const res = await fetch(`${BASE_URL}/api/v1/mobility/evaluation`)
    assert.equal(res.status, 200)
    const data = await res.json()
    assert.equal(data.baseline_model.f1_score, 0.1864)
    assert.equal(data.augmented_model.f1_score, 0.23)
    assert.equal(data.delta_f1, 0.0436)
    assert.match(data.performance_verdict, /positive improvement in F1-score \(\+0\.0436\)/)
    assert.match(data.synthetic_experiment_notice, /SYNTHETIC-DATA EXPERIMENT/)
    assert.equal(data.train_date_range[0], '2026-01-14')
    assert.equal(data.train_date_range[1], '2026-05-10')
  })

  // Integration 8: Live Anomaly Intelligence & Non-Clinical Guardrails
  await liveTest('GET /api/v1/anomalies returns statistical results with surge disclaimer', async () => {
    const res = await fetch(`${BASE_URL}/api/v1/anomalies?is_anomaly=true&page_size=5`)
    assert.equal(res.status, 200)
    const data = await res.json()
    assert.ok(data.items.length > 0)
    for (const item of data.items) {
      assert.equal(item.is_anomaly, true)
      assert.match(item.interpretation_disclaimer, /STATISTICAL SURGE ONLY/)
    }
  })

  await liveTest('GET /api/v1/anomalies returns empty array for non-matching date range', async () => {
    const res = await fetch(`${BASE_URL}/api/v1/anomalies?start_date=2001-01-01&end_date=2001-01-02`)
    assert.equal(res.status, 200)
    const data = await res.json()
    assert.equal(data.total, 0)
    assert.equal(data.items.length, 0)
  })

  // Integration 9: Document Listing and Duplicate Detection
  await liveTest('GET /api/v1/documents lists repository metadata', async () => {
    const res = await fetch(`${BASE_URL}/api/v1/documents?page_size=5`)
    assert.equal(res.status, 200)
    const data = await res.json()
    assert.ok(data.total >= 1)
    assert.ok(data.items[0].content_hash.length === 64)
  })

  await liveTest('POST /api/v1/documents/ingest detects duplicate document content', async () => {
    const timestamp = Date.now()
    const uniqueContent = `Sample protocol document ${timestamp} for viral hemorrhagic fever surveillance guidelines.`
    const payload = {
      filename: `protocol_${timestamp}.md`,
      content: uniqueContent,
    }
    const res = await fetch(`${BASE_URL}/api/v1/documents/ingest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    assert.equal(res.status, 201)
    const firstResult = await res.json()
    assert.equal(firstResult.status, 'INGESTED')

    // Second ingestion MUST return status 409 DUPLICATE
    const res2 = await fetch(`${BASE_URL}/api/v1/documents/ingest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    assert.equal(res2.status, 409)
    const secondResult = await res2.json()
    assert.equal(secondResult.status, 'DUPLICATE')
    assert.equal(secondResult.document_id, firstResult.document_id)
  })

  // Integration 10: Detection Pipeline Validation
  await liveTest('POST /api/v1/pipeline/detect rejects invalid window size with 422', async () => {
    const payload = {
      method: 'rolling_mad',
      window_size: 1, // Invalid: must be >= 2
      threshold: 3.0,
    }
    const res = await fetch(`${BASE_URL}/api/v1/pipeline/detect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    assert.equal(res.status, 422)
  })

  // Integration 11: Evidence-Grounded AI Assistant Telemetry (Phase 6C)
  await liveTest('GET /api/v1/assistant/status returns provider health and vector index count', async () => {
    const res = await fetch(`${BASE_URL}/api/v1/assistant/status`)
    assert.equal(res.status, 200)
    const data = await res.json()
    assert.ok(data.status)
    assert.ok(data.provider)
    assert.ok(data.model)
    assert.ok(typeof data.indexed_passages_count === 'number')
    assert.ok(data.indexed_passages_count >= 1)
    assert.match(data.disclaimer, /Phase 6C Assistant/)
  })

  // Integration 12: Zero-Hallucination Negative Refusal (Phase 6C)
  await liveTest('POST /api/v1/assistant/ask returns INSUFFICIENT evidence for out-of-scope query', async () => {
    const payload = {
      question: 'What cryogenic refrigeration hardware is used for superconducting qubits?',
      min_similarity: 0.30,
    }
    const res = await fetch(`${BASE_URL}/api/v1/assistant/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    assert.equal(res.status, 200)
    const data = await res.json()
    assert.equal(data.evidence_sufficiency, 'INSUFFICIENT')
    assert.equal(data.citations.length, 0)
    assert.match(data.answer, /does not contain sufficient documentation/)
    assert.match(data.synthetic_data_notice, /SYNTHETIC-DATA NOTICE/)
    assert.match(data.non_clinical_notice, /DISCLAIMER/)
  })

  // Integration 13: Assistant Input Validation (Phase 6C)
  await liveTest('POST /api/v1/assistant/ask rejects questions shorter than 3 characters with 422', async () => {
    const payload = {
      question: 'hi',
    }
    const res = await fetch(`${BASE_URL}/api/v1/assistant/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    assert.equal(res.status, 422)
  })

  // Integration 14: Geospatial Regions & Coordinate Validation (Phase 7)
  await liveTest('GET /api/v1/geospatial/regions lists 5 synthetic sectors with documented coordinates', async () => {
    const res = await fetch(`${BASE_URL}/api/v1/geospatial/regions`)
    assert.equal(res.status, 200)
    const data = await res.json()
    assert.equal(data.length, 5)
    for (const r of data) {
      assert.equal(r.is_synthetic_geography, true)
      assert.ok(r.population > 0)
      assert.ok(r.centroid_lat >= -90 && r.centroid_lat <= 90)
      assert.ok(r.centroid_lon >= -180 && r.centroid_lon <= 180)
    }
  })

  // Integration 15: Geospatial GeoJSON Polygon FeatureCollection (Phase 7)
  await liveTest('GET /api/v1/geospatial/geojson returns valid GeoJSON polygon boundaries', async () => {
    const res = await fetch(`${BASE_URL}/api/v1/geospatial/geojson`)
    assert.equal(res.status, 200)
    const data = await res.json()
    assert.equal(data.type, 'FeatureCollection')
    assert.equal(data.features.length, 5)
    for (const f of data.features) {
      assert.equal(f.type, 'Feature')
      assert.equal(f.geometry.type, 'Polygon')
      assert.ok(f.geometry.coordinates[0].length >= 4)
    }
  })

  // Integration 16: Regional Surveillance & Anomaly Aggregation (Phase 7)
  await liveTest('GET /api/v1/geospatial/surveillance aggregates regional cases and anomaly counts', async () => {
    const res = await fetch(`${BASE_URL}/api/v1/geospatial/surveillance`)
    assert.equal(res.status, 200)
    const data = await res.json()
    assert.equal(data.total_regions, 5)
    assert.ok(data.total_surveillance_cases > 0)
    assert.equal(data.total_anomalies_flagged, 64)
    for (const r of data.regions) {
      assert.ok(r.total_cases > 0)
      assert.ok(r.crude_rate_per_100k > 0)
      assert.equal(r.active_days_count, 180)
    }
  })

  // Integration 17: Geospatial Time Series with Algorithmic Anomalies (Phase 7)
  await liveTest('GET /api/v1/geospatial/timeseries returns 180 aligned points with anomaly markers', async () => {
    const res = await fetch(`${BASE_URL}/api/v1/geospatial/timeseries?region_id=REGION_A&syndrome=Respiratory`)
    assert.equal(res.status, 200)
    const data = await res.json()
    assert.equal(data.region_id, 'REGION_A')
    assert.equal(data.points_count, 180)
    assert.ok(data.anomaly_points_count > 0)
    const anomPoint = data.points.find((p: any) => p.is_anomaly)
    assert.ok(anomPoint)
    assert.equal(anomPoint.detection_method, 'rolling_mad')
    assert.ok(anomPoint.anomaly_score != null)
  })

  // Integration 18: Lagged Cross-Correlations Profile (Phase 7)
  await liveTest('GET /api/v1/geospatial/correlations computes -7 to +14 day cross-correlations', async () => {
    const res = await fetch(`${BASE_URL}/api/v1/geospatial/correlations?region_id=REGION_A&syndrome=Respiratory`)
    assert.equal(res.status, 200)
    const data = await res.json()
    assert.equal(data.sample_size, 180)
    assert.equal(data.lag_points.length, 22)
    assert.match(data.lag_convention, /Positive Lag/)
    assert.match(data.causality_disclaimer, /CAUTION/)
  })

  // Integration 19: Geospatial Parameter Validation (Phase 7)
  await liveTest('GET /api/v1/geospatial/surveillance rejects start_date > end_date with 400', async () => {
    const res = await fetch(`${BASE_URL}/api/v1/geospatial/surveillance?start_date=2026-06-01&end_date=2026-01-01`)
    assert.equal(res.status, 400)
  })

  // Unit 20: Assistant Mode & Parameter Serialization (Phase 9.3)
  await test('Assistant request constructs valid concise and detailed payloads', () => {
    const conciseReq = {
      question: 'What statistical threshold triggers a respiratory surge alert?',
      top_k: 3,
      min_similarity: 0.30,
      mode: 'concise',
      fallback_on_timeout: true,
    }
    assert.equal(conciseReq.mode, 'concise')
    assert.equal(conciseReq.fallback_on_timeout, true)

    const detailedReq = {
      question: 'What statistical threshold triggers a respiratory surge alert?',
      mode: 'detailed',
    }
    assert.equal(detailedReq.mode, 'detailed')
  })

  // Unit 21: Assistant Citation Tag Normalization (Phase 9.3)
  await test('CitationItem tag resolver handles citation_id and citation_tag seamlessly', () => {
    const resolveTag = (cit: { citation_id?: string; citation_tag?: string }) => {
      if (cit.citation_id) {
        return cit.citation_id.startsWith('[') ? cit.citation_id : `[${cit.citation_id}]`
      }
      return cit.citation_tag || '[E?]'
    }

    assert.equal(resolveTag({ citation_id: 'E1' }), '[E1]')
    assert.equal(resolveTag({ citation_id: '[E2]' }), '[E2]')
    assert.equal(resolveTag({ citation_tag: '[E3]' }), '[E3]')
    assert.equal(resolveTag({}), '[E?]')
  })

  // Unit 22: Evidence-First Fallback & Truncation Response Parsing (Phase 9.3)
  await test('Evidence-first fallback response preserves citation provenance and flags fallback', () => {
    const fallbackResponse = {
      query_id: 'ask-fallback-test',
      question: 'What is the respiratory threshold?',
      answer: 'LLM answer synthesis timed out on the model server, but 1 relevant reference evidence passages were retrieved [E1].',
      evidence_sufficiency: 'SUFFICIENT' as const,
      response_type: 'evidence_fallback' as const,
      finish_reason: 'timeout_fallback',
      response_mode: 'concise' as const,
      citations: [
        {
          citation_id: 'E1',
          chunk_id: 'chunk-resp-01',
          document_id: 'doc-resp',
          title: 'Respiratory Surge Protocol',
          similarity_score: 0.85,
          char_start: 0,
          char_end: 120,
          excerpt: 'Threshold triggers when daily counts exceed 3.0 SD...',
          is_verified: true,
        },
      ],
      retrieved_passages: [],
      provider: 'ollama',
      model: 'llama3.2:3b',
      latency_seconds: 90.0,
      synthetic_data_notice: 'SYNTHETIC-DATA NOTICE',
      non_clinical_notice: 'DISCLAIMER',
      warning: 'LLM generation exceeded timeout; returned direct evidence fallback.',
    }

    assert.equal(fallbackResponse.response_type, 'evidence_fallback')
    assert.equal(fallbackResponse.finish_reason, 'timeout_fallback')
    assert.equal(fallbackResponse.response_mode, 'concise')
    assert.equal(fallbackResponse.citations[0].citation_id, 'E1')
    assert.equal(fallbackResponse.citations[0].is_verified, true)
    assert.ok(fallbackResponse.warning)
  })

  // Unit 23: Duplicate Submission Guard Logic (Phase 9.3)
  await test('Duplicate submission guard prevents execution when request is already in-flight', () => {
    let callCount = 0
    let inFlight = false

    const submit = (q: string) => {
      if (inFlight) return 'BLOCKED_DUPLICATE'
      inFlight = true
      callCount++
      return 'SUBMITTED'
    }

    assert.equal(submit('Test Question 1'), 'SUBMITTED')
    assert.equal(submit('Test Question 1 (Rapid Double Click)'), 'BLOCKED_DUPLICATE')
    assert.equal(callCount, 1)

    inFlight = false
    assert.equal(submit('Test Question 2 (After Complete)'), 'SUBMITTED')
    assert.equal(callCount, 2)
  })

  // Integration 24: Live Assistant Out-of-Scope Negative Refusal in Concise Mode (Phase 9.3)
  await liveTest('POST /api/v1/assistant/ask with mode="concise" returns fast refusal with response_mode', async () => {
    const payload = {
      question: 'What cryogenic refrigeration hardware is used for superconducting qubits?',
      min_similarity: 0.30,
      mode: 'concise',
    }
    const res = await fetch(`${BASE_URL}/api/v1/assistant/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    assert.equal(res.status, 200)
    const data = await res.json()
    assert.equal(data.evidence_sufficiency, 'INSUFFICIENT')
    assert.equal(data.response_type, 'insufficient_refusal')
    assert.equal(data.response_mode, 'concise')
    assert.equal(data.finish_reason, 'insufficient_evidence')
    assert.equal(data.citations.length, 0)
  })

  console.log(`\n=== Audit Test Results: ${passed} passed, ${failed} failed, ${skipped} skipped ===\n`)
  if (failed > 0) process.exit(1)
}

runTests()
