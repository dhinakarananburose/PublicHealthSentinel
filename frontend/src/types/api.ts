/**
 * TypeScript API contracts for PublicHealthSentinel.
 * Strictly synchronized with FastAPI schemas and SQLAlchemy models.
 */

export interface HealthResponse {
  status: 'healthy' | 'degraded';
  app_name: string;
  environment: string;
  api_version: string;
  database_connected: boolean;
  timestamp: string;
  demo_mode?: boolean;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  synthetic_experiment_notice: string;
}

export interface SurveillanceObservation {
  id: number;
  observation_date: string;
  region_id: string;
  syndrome: string;
  report_count: number;
  reporting_facility_count: number | null;
  population_denominator: number | null;
  crude_incidence_per_100k: number | null;
  data_source: string;
  data_status: string;
  ingestion_timestamp: string;
}

export interface MobilityIndicator {
  id: number;
  observation_date: string;
  region_id: string;
  mobility_metric: string;
  mobility_value: number;
  data_source: string;
  data_status: string;
  ingestion_timestamp: string;
}

export interface AnomalyResult {
  id: number;
  observation_date: string;
  region_id: string;
  syndrome: string;
  detection_method: 'rolling_mad' | 'ewma' | 'zscore' | string;
  observed_count: number | null;
  expected_baseline: number | null;
  anomaly_score: number | null;
  detection_threshold: number | null;
  is_anomaly: boolean | null;
  history_count: number;
  evaluation_status: string;
  data_source: string;
  data_status: string;
  created_at: string;
  interpretation_disclaimer: string;
}

export interface RunDetectionRequest {
  method: 'all' | 'rolling_mad' | 'ewma' | 'zscore';
  window_size?: number;
  threshold?: number;
  min_history?: number;
  ewma_lambda?: number;
  persist_results?: boolean;
}

export interface RunDetectionResponse {
  execution_id: string;
  status: 'SUCCESS' | 'FAILED';
  methods_run: string[];
  total_evaluated_observations: number;
  anomalies_detected_by_method: Record<string, number>;
  database_records_persisted: number;
  metrics_by_method?: Record<string, any>;
  synthetic_experiment_notice: string;
}

export interface DocumentIngestRequest {
  filename: string;
  content: string;
  title?: string;
  source_publisher?: string;
  source_url?: string;
  publication_date?: string;
}

export interface DocumentIngestResponse {
  document_id: string;
  status: 'INGESTED' | 'DUPLICATE' | 'FAILED';
  filename: string;
  doc_format: 'txt' | 'md';
  content_hash: string;
  document_size_bytes: number;
  title: string;
  message: string;
  synthetic_experiment_notice: string;
}

export interface DocumentMetadata {
  id: number;
  document_id: string;
  filename: string;
  title: string;
  doc_format: 'txt' | 'md';
  content_hash: string;
  source_publisher: string | null;
  source_url: string | null;
  publication_date: string | null;
  document_size_bytes: number;
  character_count: number;
  word_count: number;
  ingestion_status: string;
  error_message: string | null;
  ingestion_timestamp: string;
  synthetic_experiment_notice: string;
}

export interface ConfusionMatrix {
  tn: number;
  fp: number;
  fn: number;
  tp: number;
}

export interface ModelPerformanceDetails {
  model_name: string;
  feature_names: string[];
  train_sample_size: number;
  test_sample_size: number;
  test_positive_count: number;
  test_negative_count: number;
  precision: number;
  recall: number;
  f1_score: number;
  specificity: number;
  accuracy: number;
  confusion_matrix: ConfusionMatrix;
  coefficients: Record<string, number>;
  intercept: number;
}

export interface MobilityEvaluationResponse {
  target_definition: string;
  train_date_range: [string, string];
  test_date_range: [string, string];
  train_ratio: number;
  baseline_model: ModelPerformanceDetails;
  augmented_model: ModelPerformanceDetails;
  delta_precision: number;
  delta_recall: number;
  delta_f1: number;
  delta_specificity: number;
  performance_verdict: string;
  synthetic_experiment_notice: string;
}

export interface ProcessDocumentResponse {
  document_id: string;
  status: string;
  chunks_created: number;
  embedding_model: string;
  processing_duration_ms: number;
  message: string;
  synthetic_experiment_notice: string;
}

export interface DocumentChunk {
  id: number;
  chunk_id: string;
  document_id: string;
  sequence_number: number;
  text: string;
  char_start: number;
  char_end: number;
  title: string | null;
  source_publisher: string | null;
  source_url: string | null;
  publication_date: string | null;
  content_hash: string;
  embedding_model: string | null;
  created_at: string;
}

export interface EvidenceSearchRequest {
  query: string;
  top_k?: number;
  document_id?: string;
  source_publisher?: string;
  min_similarity?: number;
}

export interface RetrievedEvidenceItem {
  chunk_id: string;
  document_id: string;
  title: string | null;
  text: string;
  source_publisher: string | null;
  source_url: string | null;
  publication_date: string | null;
  sequence_number: number;
  char_start: number;
  char_end: number;
  similarity_score: number;
  embedding_model: string;
  score_interpretation: string;
}

export interface EvidenceSearchResponse {
  query: string;
  query_id: string;
  total_results: number;
  embedding_model: string;
  items: RetrievedEvidenceItem[];
  synthetic_experiment_notice: string;
}

export interface EvidenceSubsystemStatus {
  status: string;
  total_indexed_chunks: number;
  total_indexed_documents: number;
  dimension: number;
  active_embedding_model: string;
  configured_embedding_model: string;
  index_file_exists: boolean;
  meta_file_exists: boolean;
  is_degraded?: boolean;
  degraded_reason?: string | null;
  last_updated: string | null;
  synthetic_experiment_notice: string;
}

export interface EvidenceRebuildResponse {
  status: string;
  rebuilt_chunks: number;
  active_embedding_model: string;
  message: string;
  synthetic_experiment_notice: string;
}

// Phase 6C: Evidence-Grounded AI Assistant
export interface CitationItem {
  citation_id?: string;
  citation_index?: number;
  citation_tag?: string;
  chunk_id: string;
  document_id: string;
  title: string;
  source_publisher?: string | null;
  similarity_score: number;
  char_start: number;
  char_end: number;
  excerpt: string;
  is_verified?: boolean;
  score_interpretation?: string;
}

export interface RetrievedPassageReference {
  passage_index: number;
  chunk_id: string;
  document_id: string;
  title: string;
  source_publisher?: string | null;
  similarity_score: number;
  char_start: number;
  char_end: number;
  text: string;
}

export interface AssistantAskRequest {
  question: string;
  top_k?: number;
  min_similarity?: number;
  source_publisher?: string;
  mode?: 'concise' | 'detailed';
  fallback_on_timeout?: boolean;
}

export interface AssistantAskResponse {
  query_id: string;
  question: string;
  answer: string;
  evidence_sufficiency: 'SUFFICIENT' | 'PARTIAL' | 'INSUFFICIENT';
  citations: CitationItem[];
  retrieved_passages: RetrievedPassageReference[];
  provider: string;
  model: string;
  latency_seconds: number;
  synthetic_data_notice: string;
  non_clinical_notice: string;
  response_type?: 'synthesized' | 'evidence_fallback' | 'insufficient_refusal';
  finish_reason?: string;
  response_mode?: 'concise' | 'detailed';
  warning?: string | null;
}

export interface AssistantStatusResponse {
  status: 'READY' | 'PROVIDER_UNAVAILABLE' | 'INDEX_DEGRADED' | 'NOT_CONFIGURED';
  provider: string;
  model: string;
  provider_healthy: boolean;
  provider_message: string;
  vector_index_status: string;
  indexed_passages_count: number;
  available_models: string[];
  disclaimer: string;
}

// Phase 7: Geospatial Intelligence & Surveillance Mapping
export interface SyntheticRegionMetadata {
  region_id: string;
  name: string;
  code: string;
  population: number;
  facility_count: number;
  centroid_lat: number;
  centroid_lon: number;
  bounding_box: [number, number, number, number];
  is_synthetic_geography: boolean;
  synthetic_disclaimer: string;
}

export interface RegionalSurveillanceSummary {
  region_id: string;
  region_name: string;
  population: number;
  facility_count: number;
  total_cases: number;
  crude_rate_per_100k: number | null;
  active_days_count: number;
  syndromic_breakdown: Record<string, number>;
  anomaly_count: number;
  recent_anomaly_detected: boolean;
  centroid_lat: number;
  centroid_lon: number;
  data_status: string;
}

export interface GeospatialSurveillanceResponse {
  start_date: string;
  end_date: string;
  syndrome_filter: string | null;
  total_regions: number;
  total_surveillance_cases: number;
  total_anomalies_flagged: number;
  regions: RegionalSurveillanceSummary[];
  synthetic_notice: string;
  non_clinical_notice: string;
}

export interface GeospatialTimeSeriesPoint {
  observation_date: string;
  region_id: string;
  syndrome: string;
  report_count: number;
  is_anomaly: boolean;
  anomaly_score: number | null;
  expected_baseline: number | null;
  detection_threshold: number | null;
  detection_method: string | null;
}

export interface GeospatialTimeSeriesResponse {
  region_id: string;
  region_name: string;
  syndrome: string;
  start_date: string;
  end_date: string;
  points_count: number;
  anomaly_points_count: number;
  points: GeospatialTimeSeriesPoint[];
  synthetic_notice: string;
}

export interface MobilityOverlayPoint {
  observation_date: string;
  report_count: number;
  mobility_value: number | null;
  is_anomaly: boolean;
}

export interface GeospatialMobilityOverlayResponse {
  region_id: string;
  region_name: string;
  syndrome: string;
  mobility_metric: string;
  start_date: string;
  end_date: string;
  aligned_days: number;
  points: MobilityOverlayPoint[];
  synthetic_notice: string;
  causality_disclaimer: string;
}

export interface LaggedCorrelationPoint {
  lag_days: number;
  sample_size_n: number;
  pearson_r: number | null;
  pearson_p_value: number | null;
  spearman_rho: number | null;
  spearman_p_value: number | null;
  convention_description: string;
}

export interface GeospatialLaggedCorrelationResponse {
  region_id: string;
  region_name: string;
  syndrome: string;
  mobility_metric: string;
  sample_size: number;
  best_positive_lag_days: number | null;
  best_positive_lag_pearson_r: number | null;
  lag_points: LaggedCorrelationPoint[];
  lag_convention: string;
  causality_disclaimer: string;
}

export interface GeoJSONGeometry {
  type: 'Polygon';
  coordinates: number[][][];
}

export interface GeoJSONFeature {
  type: 'Feature';
  id: string;
  properties: {
    region_id: string;
    name: string;
    code: string;
    population: number;
    facility_count: number;
    centroid_lat: number;
    centroid_lon: number;
    is_synthetic_geography: boolean;
  };
  geometry: GeoJSONGeometry;
}

export interface GeoJSONFeatureCollection {
  type: 'FeatureCollection';
  features: GeoJSONFeature[];
  synthetic_notice: string;
}

