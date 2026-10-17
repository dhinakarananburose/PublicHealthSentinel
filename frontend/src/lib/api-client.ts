/**
 * Centralized API client for PublicHealthSentinel backend.
 * Provides typed requests, parameter serialization, timeout handling,
 * and actionable error extraction.
 */

import type {
  AnomalyResult,
  DocumentChunk,
  DocumentIngestRequest,
  DocumentIngestResponse,
  DocumentMetadata,
  EvidenceRebuildResponse,
  EvidenceSearchRequest,
  EvidenceSearchResponse,
  EvidenceSubsystemStatus,
  HealthResponse,
  MobilityEvaluationResponse,
  MobilityIndicator,
  PaginatedResponse,
  ProcessDocumentResponse,
  RunDetectionRequest,
  RunDetectionResponse,
  SurveillanceObservation,
  AssistantAskRequest,
  AssistantAskResponse,
  AssistantStatusResponse,
  SyntheticRegionMetadata,
  GeospatialSurveillanceResponse,
  GeospatialTimeSeriesResponse,
  GeospatialMobilityOverlayResponse,
  GeospatialLaggedCorrelationResponse,
  GeoJSONFeatureCollection,
} from '@/types/api'

export class ApiError extends Error {
  statusCode: number
  details?: any

  constructor(message: string, statusCode: number, details?: any) {
    super(message)
    this.name = 'ApiError'
    this.statusCode = statusCode
    this.details = details
  }
}

// Configurable base URL stored in localStorage for runtime flexibility
const STORAGE_KEY_BASE_URL = 'sentinel_api_base_url'

export function getApiBaseUrl(): string {
  if (typeof window === 'undefined') return ''
  const envUrl = ((import.meta as any).env?.VITE_API_BASE_URL || '').trim().replace(/\/+$/, '')
  const stored = (localStorage.getItem(STORAGE_KEY_BASE_URL) || '').trim().replace(/\/+$/, '')
  let url = stored || envUrl
  if (url && !url.startsWith('http://') && !url.startsWith('https://')) {
    url = `https://${url}`
  }
  return url
}

export function setApiBaseUrl(url: string): void {
  if (typeof window === 'undefined') return
  const clean = url.trim().replace(/\/+$/, '')
  if (!clean) {
    localStorage.removeItem(STORAGE_KEY_BASE_URL)
  } else {
    localStorage.setItem(STORAGE_KEY_BASE_URL, clean)
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
  timeoutMs: number = 15000
): Promise<T> {
  const baseUrl = getApiBaseUrl()
  const url = `${baseUrl}${endpoint}`

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)

  const headers = new Headers(options.headers || {})
  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json')
  }
  if (options.body && typeof options.body === 'string' && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  try {
    const response = await fetch(url, {
      ...options,
      headers,
      signal: controller.signal,
    })

    const contentType = response.headers.get('content-type') || ''
    const isJson = contentType.includes('application/json')

    if (!response.ok) {
      let errorMessage = `HTTP Error ${response.status}: ${response.statusText}`
      let details: any = undefined

      if (isJson) {
        try {
          const body = await response.json()
          errorMessage = body.message || body.detail || errorMessage
          details = body.details || body
        } catch {
          // fallback to text
        }
      } else {
        const text = await response.text()
        if (text) errorMessage = text
      }

      throw new ApiError(errorMessage, response.status, details)
    }

    if (isJson) {
      return (await response.json()) as T
    }
    return (await response.text()) as unknown as T
  } catch (err: any) {
    if (err.name === 'AbortError') {
      const seconds = Math.round(timeoutMs / 1000)
      throw new ApiError(`Request timed out after ${seconds} seconds. Please check backend availability or use Concise mode.`, 408)
    }
    if (err instanceof ApiError) throw err
    throw new ApiError(err.message || 'Network connection failed.', 0)
  } finally {
    clearTimeout(timer)
  }
}

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

export const api = {
  // System Health Probe
  async getHealth(): Promise<HealthResponse> {
    return request<HealthResponse>('/health')
  },

  // Surveillance Observations
  async getSurveillance(params: {
    start_date?: string
    end_date?: string
    region_id?: string
    syndrome?: string
    page?: number
    page_size?: number
  } = {}): Promise<PaginatedResponse<SurveillanceObservation>> {
    return request<PaginatedResponse<SurveillanceObservation>>(
      `/api/v1/surveillance${buildQuery(params)}`
    )
  },

  // Mobility Indicators
  async getMobility(params: {
    start_date?: string
    end_date?: string
    region_id?: string
    mobility_metric?: string
    page?: number
    page_size?: number
  } = {}): Promise<PaginatedResponse<MobilityIndicator>> {
    return request<PaginatedResponse<MobilityIndicator>>(
      `/api/v1/mobility${buildQuery(params)}`
    )
  },

  // Mobility Empirical Evaluation Report (Phase 4)
  async getMobilityEvaluation(): Promise<MobilityEvaluationResponse> {
    return request<MobilityEvaluationResponse>('/api/v1/mobility/evaluation')
  },

  // Anomaly Detection Results
  async getAnomalies(params: {
    start_date?: string
    end_date?: string
    region_id?: string
    syndrome?: string
    method?: string
    is_anomaly?: boolean
    page?: number
    page_size?: number
  } = {}): Promise<PaginatedResponse<AnomalyResult>> {
    return request<PaginatedResponse<AnomalyResult>>(
      `/api/v1/anomalies${buildQuery(params)}`
    )
  },

  // Trigger Anomaly Detection Pipeline
  async runDetectionPipeline(payload: RunDetectionRequest): Promise<RunDetectionResponse> {
    return request<RunDetectionResponse>('/api/v1/pipeline/detect', {
      method: 'POST',
      body: JSON.stringify(payload),
    }, 60000) // 60s timeout for analytical executions
  },

  // Evidence Documents (Phase 6A)
  async ingestDocument(payload: DocumentIngestRequest): Promise<DocumentIngestResponse> {
    return request<DocumentIngestResponse>('/api/v1/documents/ingest', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  async listDocuments(params: {
    doc_format?: string
    source_publisher?: string
    ingestion_status?: string
    page?: number
    page_size?: number
  } = {}): Promise<PaginatedResponse<DocumentMetadata>> {
    return request<PaginatedResponse<DocumentMetadata>>(
      `/api/v1/documents${buildQuery(params)}`
    )
  },

  async getDocument(documentId: string): Promise<DocumentMetadata> {
    return request<DocumentMetadata>(`/api/v1/documents/${encodeURIComponent(documentId)}`)
  },

  // Document Chunking, Local Embeddings & Retrieval (Phase 6B.1)
  async processDocument(documentId: string): Promise<ProcessDocumentResponse> {
    return request<ProcessDocumentResponse>(
      `/api/v1/documents/${encodeURIComponent(documentId)}/process`,
      {
        method: 'POST',
        body: JSON.stringify({}),
      },
      60000
    )
  },

  async getDocumentChunks(
    documentId: string,
    params: { page?: number; page_size?: number } = {}
  ): Promise<PaginatedResponse<DocumentChunk>> {
    return request<PaginatedResponse<DocumentChunk>>(
      `/api/v1/documents/${encodeURIComponent(documentId)}/chunks${buildQuery(params)}`
    )
  },

  async searchEvidence(payload: EvidenceSearchRequest): Promise<EvidenceSearchResponse> {
    return request<EvidenceSearchResponse>('/api/v1/evidence/search', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  async getEvidenceStatus(): Promise<EvidenceSubsystemStatus> {
    return request<EvidenceSubsystemStatus>('/api/v1/evidence/status')
  },

  async rebuildEvidenceIndex(): Promise<EvidenceRebuildResponse> {
    return request<EvidenceRebuildResponse>('/api/v1/evidence/rebuild', {
      method: 'POST',
    })
  },

  // Evidence-Grounded AI Assistant (Phase 6C & Phase 9.3)
  async askAssistant(payload: AssistantAskRequest, timeoutMs: number = 100000): Promise<AssistantAskResponse> {
    return request<AssistantAskResponse>(
      '/api/v1/assistant/ask',
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
      timeoutMs // 100s client timeout allows 90s backend Ollama generation and fallback to return
    )
  },

  async getAssistantStatus(): Promise<AssistantStatusResponse> {
    return request<AssistantStatusResponse>('/api/v1/assistant/status')
  },

  // Geospatial Intelligence (Phase 7)
  async getGeospatialRegions(): Promise<SyntheticRegionMetadata[]> {
    return request<SyntheticRegionMetadata[]>('/api/v1/geospatial/regions')
  },

  async getGeospatialGeoJSON(): Promise<GeoJSONFeatureCollection> {
    return request<GeoJSONFeatureCollection>('/api/v1/geospatial/geojson')
  },

  async getGeospatialSurveillance(params: {
    start_date?: string
    end_date?: string
    syndrome?: string
  } = {}): Promise<GeospatialSurveillanceResponse> {
    return request<GeospatialSurveillanceResponse>(
      `/api/v1/geospatial/surveillance${buildQuery(params)}`
    )
  },

  async getGeospatialTimeSeries(params: {
    region_id?: string
    syndrome?: string
    start_date?: string
    end_date?: string
    detection_method?: string
  } = {}): Promise<GeospatialTimeSeriesResponse> {
    return request<GeospatialTimeSeriesResponse>(
      `/api/v1/geospatial/timeseries${buildQuery(params)}`
    )
  },

  async getGeospatialMobility(params: {
    region_id?: string
    syndrome?: string
    mobility_metric?: string
    start_date?: string
    end_date?: string
  } = {}): Promise<GeospatialMobilityOverlayResponse> {
    return request<GeospatialMobilityOverlayResponse>(
      `/api/v1/geospatial/mobility${buildQuery(params)}`
    )
  },

  async getGeospatialCorrelations(params: {
    region_id?: string
    syndrome?: string
    mobility_metric?: string
    min_lag?: number
    max_lag?: number
  } = {}): Promise<GeospatialLaggedCorrelationResponse> {
    return request<GeospatialLaggedCorrelationResponse>(
      `/api/v1/geospatial/correlations${buildQuery(params)}`
    )
  },
}

