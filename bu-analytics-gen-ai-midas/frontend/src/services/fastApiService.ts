// FastAPI Backend Integration Service
// Interfaces for FastAPI backend communication

import { apiInterceptor } from './apiInterceptor';
import { SessionExpiredError } from './sessionExpired';
import { buildMidasAuthHeaders } from './authHeaders';
import { handleUnauthorizedResponse, RETRY_AFTER_REFRESH, SilentAuthFailure } from './httpUnauthorized';

export interface FastAPIUploadRequest {
  file?: File;
  /** Use an existing dataset_id from a chunked upload instead of a file upload. */
  existing_dataset_id?: string;
  /** Multiple files for merge upload (e.g., multiple validation files). */
  files?: File[];
  /** If true, multiple validation files will be merged into one. */
  merge_validation?: boolean;
  target_variable: string;
  target_variable_type: 'Numerical' | 'Categorical';
  data_dictionary?: string | File;
  problem_statement?: string;
  unique_id_combinations?: string[];
  segmentation_variable?: string;
  sample_identifier_variable?: string;
  // Split configuration
  has_sampling_variable?: boolean | null;
  sampling_variable?: string | null;
  split_ratio?: number;
  initial_scope?: string; // 'split', 'sampling_variable_split'
  /** JSON string of platform split config (ingestion Step 1). */
  split_configuration?: string;
  /** JSON string of exclusion rules to apply before splitting. */
  exclusion_rules?: string;
  /** JSON array of variable names to remove before processing. */
  variables_to_remove?: string;
  /** Partition role for pre-split uploads (train, test, validation, oot). */
  partition_role?: string;
}

export interface FastAPIDatasetAnalysisRequest {
  file: File;
}

export interface DatasetColumnInfo {
  name: string;
  type: 'Numerical' | 'Categorical';
  pandas_type: string;
  unique_count: number;
  missing_count: number;
  // Optional semantic/logic type from backend (e.g. Date)
  logical_type?: 'Numerical' | 'Categorical' | 'Date' | string;
  is_date?: boolean;
  date_detection_reason?: string | null;
  date_detected_format?: string | null;
  date_detection_confidence?: number | null;
  sample_values?: Record<string, number>;
  numerical_stats?: {
    min: number | null;
    max: number | null;
    mean: number | null;
    missing_count: number;
  };
}

export interface KnowledgeGraphProcessingInfo {
  total_columns?: number;
  processed_columns?: number;
  total_batches?: number;
  completed_batches?: number;
  status?: 'partial' | 'complete' | string;
}

export interface KnowledgeGraphResultPayload {
  success: boolean;
  message: string;
  html_content?: string;
  algorithm_explanation?: string;
  relationship_mapping?: string;
  usage_instructions?: string;
  processing_info?: KnowledgeGraphProcessingInfo;
  error?: string;
  nodes?: Array<{
    id: string;
    group: string;
    size: number;
    color: string;
  }>;
  categories?: Array<{
    name: string;
    color: string;
  }>;
}

export interface FastAPIDatasetAnalysisResponse {
  success: boolean;
  message: string;
  dataset_info: {
    filename: string;
    total_rows: number;
    total_columns: number;
    columns: DatasetColumnInfo[];
    suggested_target_variable: string | null;
  };
}

/** Step 1 Review Stats - /partition-preview response */
export interface PartitionPreviewPartition {
  key: 'train' | 'test' | 'validation';
  row_count: number;
  proportion_pct: number;
  date_range?: string | null;
  event_count?: number;
  event_rate_pct?: number;
  non_event_count?: number;
  target_mean?: number;
  target_median?: number;
  target_std?: number;
  class_counts?: Record<string, number>;
}

export interface PartitionPreviewResponse {
  success: boolean;
  total_rows: number;
  features: number;
  target_kind: 'binary' | 'multiclass' | 'regression' | 'unknown';
  event_label?: string | null;
  overall_event_rate_pct?: number | null;
  partitions: PartitionPreviewPartition[];
  computed_cutoffs?: {
    min_date: string | null;
    max_date: string | null;
    cutoff_1: string | null;
    cutoff_2: string | null;
  };
}

export interface FastAPIChatRequest {
  query: string;
  dataset_id: string;
  agent_context?: string | null;  // "data_insight", "modelling", "data_quality" - helps route ambiguous queries
  
  // Data Quality (QC) specific fields
  qc_mode?: 'auto' | 'manual' | null;  // Auto QC or Manual QC mode
  treatment_sequence?: string[] | null;  // Order of treatments: ["invalid_values", "special_values", "outliers", "missing_values"]
  qc_templates?: Record<string, any> | null;  // Uploaded templates for each treatment type
  qc_ui_selections?: Record<string, any> | null;  // UI selections (e.g., outlier method dropdown)
}

export interface DataStats {
  rows: number;
  columns: number;
  memory_usage_mb: number;
  missing_values: Record<string, number>;
  duplicate_rows: number;
  column_types: Record<string, string>;
  target_variable_info?: Record<string, any>;
}

export interface FastAPIUploadResponse {
  success: boolean;
  message: string;
  dataset_id: string;
  dataset_info: {
    filename: string;
    target_variable: string;
    target_variable_type: string;
    stats: DataStats;
    warnings: string[];
  };
}

export interface FastAPIChatResponse {
  response: string;
  code: string;
  suggestions: string[];
  role?: string;
}

export interface RawDataResponse {
  success: boolean;
  data: Record<string, any>[];
  total_rows: number;
  returned_rows: number;
  columns: string[];
}

export interface ConfigUpdateRequest {
  target_variable?: string;
  target_variable_type?: 'Numerical' | 'Categorical';
  problem_statement?: string;
  data_dictionary?: string;
}

export interface ConfigUpdateResponse {
  success: boolean;
  message: string;
  config: {
    target_variable: string;
    target_variable_type: string;
    problem_statement: string;
    data_dictionary: string;
    filename: string;
    uploaded_at: string;
  };
}

export interface ConfigUpdateResponse {
  success: boolean;
  message: string;
  dataset_id?: string;  // Optional since file hasn't been uploaded yet
  dataset_type: 'classification' | 'regression' | 'time_series' | 'others';
  confidence: number;
  reasoning: string;
  characteristics: Record<string, any>;
  recommendations: string[];
}

export interface ColumnDistributionResponse {
  success: boolean;
  column_name: string;
  column_type: string;
  is_numerical: boolean;
  distribution: Record<string, number>;
  statistics: {
    total_count: number;
    missing_count: number;
    valid_count: number;
    unique_count: number;
  };
}

export interface VariableInfo {
  name: string;
  category: string; // Business/functional category grouping
  type: string; // 'Numerical', 'Categorical', 'DateTime', 'Boolean', 'Text'
  subtype?: string; // 'Continuous', 'Discrete', 'Ordinal', 'Nominal', etc.
  description: string;
  role: string; // 'Target', 'Feature', 'Identifier', 'Drop'
  confidence: number; // 0.0 to 1.0
}

export interface VariableClassificationResponse {
  success: boolean;
  message: string;
  dataset_id: string;
  dataset_info: {
    filename: string;
    total_rows: number;
    total_columns: number;
    current_target?: string;
    current_target_type?: string;
  };
  classification?: {
    dataset_summary: string;
    variables: VariableInfo[];
    recommendations: string[];
    quality_score: number;
  };
  raw_response?: string; // In case JSON parsing fails
  timestamp: string;
}

export interface ColumnInfo {
  column_name: string;
  data_type: string;  // Raw pandas dtype (int64, float64, object, etc.)
  column_type?: 'Numerical' | 'Categorical' | null;  // User-friendly type from improved classification logic
  logical_type?: 'Numerical' | 'Categorical' | 'Date' | null;  // Optional semantic type from backend
  mean?: number | null;
  median?: number | null;
  mode?: number | string | null;
  standard_deviation?: number | null;
  variance?: number | null;
  skewness?: number | null;  // Skewness of the distribution
  min_value?: number | null;
  percentile_0?: number | null;   // p0 (minimum)
  percentile_1?: number | null;   // p1
  percentile_5?: number | null;   // p5
  percentile_25?: number | null;  // p25
  percentile_50?: number | null;  // p50 (median)
  percentile_75?: number | null;  // p75
  percentile_95?: number | null;  // p95
  percentile_99?: number | null;  // p99
  percentile_100?: number | null; // p100 (maximum)
  max_value?: number | null;
  missing_count: number;
  unique_count: number;
  total_count: number;
  // Categorical-specific fields
  top_category?: string | null;  // Most frequent category
  top_category_pct?: number | null;  // Percentage of most frequent category
  lowest_category?: string | null;  // Least frequent category
  lowest_category_pct?: number | null;  // Percentage of least frequent category
  // DateTime-specific fields
  date_min?: string | null;  // Minimum date value
  date_max?: string | null;  // Maximum date value
  most_frequent_date?: string | null;  // Most frequent date/value
}

export interface ColumnInfoResponse {
  success: boolean;
  message: string;
  dataset_id: string;
  columns_info: ColumnInfo[];
  total_columns: number;
  scope?: string;  // 'entire', 'train', 'test', 'validation'
  total_rows?: number;  // Number of rows for the scope
}

// DQS (Data Quality Score) Interfaces
export interface DQSCompletenessDetails {
  base_score: number;
  row_sparseness_penalty: number;
  columns_with_high_missing: number;
  column_fill_rates?: Record<string, number> | null;
  sparse_row_percentage: number;
}

export interface DQSConsistencyDetails {
  type_score: number;
  format_score: number;
  placeholder_score: number;
  range_score: number;
  formatting_issues: number;
  placeholder_count: number;
  invalid_range_count: number;
  placeholder_columns?: string[] | null;
  invalid_range_columns?: string[] | null;
}

export interface DQSStructuralDetails {
  constant_columns: number;
  constant_column_names: string[];
  near_constant_columns: number;
  near_constant_column_names: string[];
  duplicate_columns: number;
  duplicate_column_names: string[];
}

export interface DQSUniquenessDetails {
  duplicate_row_count: number;
  duplicate_row_percentage: number;
  total_rows: number;
}

export interface DQSTargetReadiness {
  target_variable?: string | null;
  target_missing_rate?: number | null;
  target_missing_count?: number | null;
  event_rate?: number | null;
  class_distribution?: Record<string, number> | null;
}

export interface DQSDimension<T> {
  score: number;
  weight: number;
  weighted_contribution: number;
  details: T;
}

export interface DQSResponse {
  success: boolean;
  message: string;
  dataset_id: string;
  composite_score: number;
  score_label: string;
  completeness: DQSDimension<DQSCompletenessDetails>;
  consistency: DQSDimension<DQSConsistencyDetails>;
  structural_integrity: DQSDimension<DQSStructuralDetails>;
  uniqueness: DQSDimension<DQSUniquenessDetails>;
  target_readiness?: DQSTargetReadiness | null;
  calculated_at: string;
  total_rows: number;
  total_columns: number;
}

export interface VariableDefinition {
  definition: string;
  category: string;
  business_context: string;
}

export interface VariableDefinitionsResponse {
  success: boolean;
  definitions: Record<string, VariableDefinition>;
}

export interface LatestColumnsResponse {
  columns: string[];
}

// Feature Transformation Interfaces
export interface FeatureTransformationRequest {
  dataset_id: string;
  plan_json: string; // JSON array of transformation plans
  target_variable?: string;
  woe_bins?: number;
  selected_segments?: string; // comma-separated e.g., "1,2"
  use_split?: boolean; // Indicates if dev/hold split should be used (from Step 1)
}

export interface FeatureTransformationSummaryItem {
  new_variable_name: string;
  var_type: string;
  variable_definition: string;
  transformation_methods: string;
  code_logic: string;
}

export interface FeatureTransformationResponse {
  success: boolean;
  dataset_id: string;
  response_data: FeatureTransformationSummaryItem[];
  error?: string;
}

export interface FeatureTransformationJobStartResponse {
  success: boolean;
  job_id?: string;
  dataset_id?: string;
  error?: string;
}

export interface FeatureTransformationJobStatusResponse {
  success: boolean;
  job_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress?: number; // 0..100
  message?: string;
  results?: FeatureTransformationResponse;
  error?: string;
}

export interface HealthCheckResponse {
  status: string;
  vector_store: {
    initialized: boolean;
    documents_count: number;
  };
}

export interface CodeExecutionResponse {
  success: boolean;
  response: string;
  columns_info: ColumnInfo[] | null;
}

export interface LLMConfigResponse {
  chat: { provider: string; model: string };
  knowledge_graph: { provider: string; model: string };
  embedding: { provider: string; model: string };
}

export interface LLMModelsResponse {
  models: {
    chat: Record<string, { provider: string; model: string; api_base?: string; api_version?: string; reasoning_effort?: string }>;
    knowledge_graph: Record<string, { provider: string; model: string; api_base?: string; api_version?: string; reasoning_effort?: string }>;
    embedding: Record<string, { provider: string; model: string; api_base?: string; api_version?: string; reasoning_effort?: string }>;
  };
  defaults: {
    chat: string;
    knowledge_graph: string;
    embedding: string;
  };
  locked_by_env: {
    chat: { locked: boolean; model_id?: string | null };
    knowledge_graph: { locked: boolean; model_id?: string | null };
    embedding: { locked: boolean; model_id?: string | null };
  };
}

// ==========================================================================
// QC STEP-BY-STEP INTERFACES (Manual QC Mode)
// ==========================================================================

/**
 * Response from QC next step
 */
export interface QCNextStepResponse {
  success: boolean;
  action_performed: string;
  treatment_processed: string;
  next_treatment?: any;
  step_info?: {
    current_step: number;
    total_steps: number;
    current_treatment: string | null;
    next_treatment: string | null;
    has_next: boolean;
    is_complete?: boolean;
  };
  is_complete?: boolean;
  treatment_statuses?: Record<string, string>;
  columns_info?: any[];
  error?: string;  // Error message if request failed
}

export interface QCRegenerateCodeResponse {
  success: boolean;
  treatment_type: string;
  payload: any;
}

export class FastAPIService {
  private baseUrl: string;

  // Track current long-running training jobs so we can cancel + stop polling from the UI
  private autoTrainingJobId: string | null = null;
  private autoTrainingPollHandle: number | null = null;
  private autoTrainingStreamAbort: AbortController | null = null;
  private autoTrainingCancelRequested = false;

  private segmentAutoTrainingJobId: string | null = null;
  private segmentAutoTrainingPollHandle: number | null = null;
  private segmentAutoTrainingCancelRequested = false;

  private manualTrainingJobId: string | null = null;
  private manualTrainingPollHandle: number | null = null;
  private manualTrainingCancelRequested = false;

  private segmentManualTrainingJobId: string | null = null;
  private segmentManualTrainingPollHandle: number | null = null;
  private segmentManualTrainingCancelRequested = false;

  // ---------------------------------------------------------------------------
  // Keepalive - prevents Azure App Service from treating the backend as idle
  // (Azure closes idle connections after ~230 s).  We ping /keepalive every
  // 60 s during any long operation (upload, analyze, training).  Multiple
  // callers can start/stop independently; the interval is ref-counted so it
  // only runs while at least one operation is active.
  // ---------------------------------------------------------------------------
  private _keepaliveTimer: ReturnType<typeof setInterval> | null = null;
  private _keepaliveRefCount = 0;
  private readonly KEEPALIVE_INTERVAL_MS = 60_000; // 60 s - well within the 230 s limit

  /** Call at the start of any long-running operation to begin pinging /keepalive. */
  startKeepalive(): void {
    this._keepaliveRefCount++;
    if (this._keepaliveTimer !== null) return; // already running
    this._keepaliveTimer = setInterval(async () => {
      try {
        const keepaliveUrl = this.baseUrl.replace(/\/api\/v1\/?$/, '') + '/api/v1/keepalive';
        await fetch(keepaliveUrl, { method: 'GET', headers: this.getAuthHeaders() });
      } catch {
        // Silently ignore - the purpose is just to keep the connection alive
      }
    }, this.KEEPALIVE_INTERVAL_MS);
  }

  /** Call at the end of a long-running operation.  Stops the interval when all callers are done. */
  stopKeepalive(): void {
    this._keepaliveRefCount = Math.max(0, this._keepaliveRefCount - 1);
    if (this._keepaliveRefCount === 0 && this._keepaliveTimer !== null) {
      clearInterval(this._keepaliveTimer);
      this._keepaliveTimer = null;
    }
  }

  constructor(baseUrl?: string) {
    const envBaseUrl = import.meta.env.VITE_BASE_URL || '';
    const defaultBaseUrl = import.meta.env.DEV
      ? '/api/v1'
      : envBaseUrl
        ? `${envBaseUrl}/api/v1`
        : '/api/v1';
    this.baseUrl = baseUrl || defaultBaseUrl;
    
    // Debug logging
    if (import.meta.env.DEV) {
      console.log('🏗️ FastAPIService constructor:', {
        providedBaseUrl: baseUrl,
        envBaseUrl: envBaseUrl,
        finalBaseUrl: this.baseUrl,
        allEnvVars: Object.keys(import.meta.env).filter(k => k.startsWith('VITE_'))
      });
    }
  }

  /**
   * Fetch with timeout support using AbortController
   * @param url - The URL to fetch
   * @param options - Fetch options
   * @param timeoutMs - Timeout in milliseconds (default: 120000 = 2 minutes)
   * @returns Promise<Response>
   */
  private async fetchWithTimeout(
    url: string,
    options: RequestInit,
    timeoutMs: number = 120000
  ): Promise<Response> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
      });
      return response;
    } catch (error: any) {
      if (error.name === 'AbortError') {
        throw new Error(
          `Request timed out after ${timeoutMs / 1000} seconds. The server may be processing a large dataset. ` +
          `Please try again with a smaller dataset or fewer segments.`
        );
      }
      // Check for network errors
      if (error.message === 'Failed to fetch' || error.name === 'TypeError') {
        throw new Error(
          'Unable to connect to the server. Please check that the backend is running and try again.'
        );
      }
      throw error;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  /**
   * Compute a sensible per-request timeout for endpoints that ingest a file.
   * Scales linearly with file size so a 2 GiB CSV gets generous headroom while
   * tiny files still surface obvious errors quickly.
   *
   * Formula: max(MIN, MS_PER_MB * file.size). For a 2 GB upload at 5 ms/MB this
   * yields ~170 min; for a 100 MB file ~3 min; minimum floor is 3 min.
   * Aligned with nginx proxy_read_timeout 600s and gunicorn 300s on the server.
   */
  private computeIngestTimeoutMs(fileSizeBytes: number, opts?: { minMs?: number; msPerMB?: number }): number {
    const minMs = opts?.minMs ?? 180_000;
    const msPerMB = opts?.msPerMB ?? 5_000;
    const sizeMB = fileSizeBytes / (1024 * 1024);
    return Math.max(minMs, Math.round(msPerMB * sizeMB));
  }

  async getLLMConfig(): Promise<LLMConfigResponse> {
    const response = await this.fetchWithAutoRefresh(`${this.baseUrl}/llm-config`, {
      method: 'GET',
      headers: {
        ...this.getAuthHeaders(),
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(`LLM config fetch failed: ${response.status} - ${errorData.detail || response.statusText}`);
    }

    return await response.json();
  }

  async getLLMModels(): Promise<LLMModelsResponse> {
    const response = await this.fetchWithAutoRefresh(`${this.baseUrl}/llm-models`, {
      method: 'GET',
      headers: {
        ...this.getAuthHeaders(),
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(`LLM models fetch failed: ${response.status} - ${errorData.detail || response.statusText}`);
    }

    return await response.json();
  }

  async setDatasetScope(request: {
    dataset_id: string;
    scope: 'train' | 'test' | 'validation' | 'entire' | 'dev' | 'hold';
    seed?: number;
    ratio?: number;
    sampling_variable?: string | null;
  }): Promise<{ success: boolean; dataset_id: string; scope: string; shape: [number, number] | null }> {
      // Use absolute path to ensure correct versioned API regardless of base URL configuration
      const resp = await apiInterceptor.post<{ success: boolean; dataset_id: string; scope: string; shape: [number, number] | null }>(
        '/api/v1/dataset/scope',
      request
      );
      return resp.data;
  }

  /**
   * Internal: perform fetch and on 401 try one refresh-and-retry
   */
  private async fetchWithAutoRefresh(input: RequestInfo | URL, init: RequestInit & { skipAuth?: boolean } = {}): Promise<Response> {
    const doFetch = async (reqInit: RequestInit) => fetch(input, reqInit);

    let response = await doFetch(init);
    if (response.status !== 401) {
      return response;
    }
    if (init.skipAuth) {
      return response;
    }

    try {
      await handleUnauthorizedResponse(response, { allowRefresh: true, skipAuth: false });
    } catch (e: unknown) {
      const err = e as { message?: string };
      if (err?.message === RETRY_AFTER_REFRESH) {
        const headers: Record<string, string> = {
          ...(init.headers as Record<string, string>),
          ...(this.getAuthHeaders() as Record<string, string>),
        };
        if (init.body instanceof FormData && headers['Content-Type']?.includes('multipart/form-data')) {
          delete headers['Content-Type'];
        }
        response = await doFetch({ ...init, headers });
        if (response.status === 401) {
          await handleUnauthorizedResponse(response, { allowRefresh: false, skipAuth: false });
        }
        return response;
      }
      throw e;
    }
    throw new Error('Unexpected fallthrough in fetchWithAutoRefresh');
  }

  /**
   * Get authentication headers
   */
  private getAuthHeaders(): HeadersInit {
    return buildMidasAuthHeaders() as HeadersInit;
  }

  /**
   * Generic POST method for making POST requests
   */
  async post(url: string, data: any, options: any = {}): Promise<any> {
    try {
      // Start with auth headers
      const headers: any = this.getAuthHeaders();
      
      // Add any additional headers from options
      if (options.headers) {
        Object.assign(headers, options.headers);
      }
      
      // Remove Content-Type if it's multipart/form-data and data is FormData
      if (data instanceof FormData && headers['Content-Type']?.includes('multipart/form-data')) {
        delete headers['Content-Type'];
      }
      console.log("Base url new from frontend",import.meta.env.VITE_BASE_URL)
      const response = await this.fetchWithAutoRefresh(`${this.baseUrl}${url}`, {
        method: 'POST',
        body: data,
        headers,
        ...options
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`POST request failed: ${response.status} - ${errorData.detail || response.statusText}`);
      }

      return {
        data: await response.json(),
        status: response.status,
        statusText: response.statusText
      };
    } catch (error) {
      if (error instanceof SessionExpiredError || error instanceof SilentAuthFailure) {
        throw error;
      }
      console.error('POST request failed:', error);
      throw error;
    }
  }

  /**
   * Generic GET method for making GET requests
   */
  async get(url: string, options: any = {}): Promise<any> {
    try {
      // Handle query parameters
      let fullUrl = `${this.baseUrl}${url}`;
      if (options.params) {
        const searchParams = new URLSearchParams();
        Object.entries(options.params).forEach(([key, value]) => {
          if (value !== undefined && value !== null) {
            searchParams.append(key, String(value));
          }
        });
        const queryString = searchParams.toString();
        if (queryString) {
          fullUrl += `?${queryString}`;
        }
      }

      console.log('📤 GET request to:', fullUrl);
      
      // Merge auth headers with any provided headers
      const headers = {
        ...this.getAuthHeaders(),
        ...(options.headers || {})
      };
      
      const response = await this.fetchWithAutoRefresh(fullUrl, {
        method: 'GET',
        headers,
        ...options
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`GET request failed: ${response.status} - ${errorData.detail || response.statusText}`);
      }

      return {
        data: await response.json(),
        status: response.status,
        statusText: response.statusText
      };
    } catch (error) {
      if (error instanceof SessionExpiredError || error instanceof SilentAuthFailure) {
        throw error;
      }
      console.error('GET request failed:', error);
      throw error;
    }
  }

  /**
   * Poll GET /insights/jobs/status/{job_id} for CPU-heavy insight jobs.
   */
  async getInsightJobStatus(jobId: string): Promise<{
    data: {
      job_id: string;
      job_type: string;
      status: string;
      progress?: number;
      message?: string;
      result?: unknown;
      error?: string;
    };
    status: number;
    statusText: string;
  }> {
    return this.get(`/insights/jobs/status/${encodeURIComponent(jobId)}`);
  }

  /**
   * Poll until an insight job completes or fails (HTTP 202 from POST/GET /insights/*).
   */
  async pollInsightJobUntilComplete(
    jobId: string,
    options?: { intervalMs?: number; maxAttempts?: number },
  ): Promise<unknown> {
    const intervalMs = options?.intervalMs ?? 2000;
    const maxAttempts = options?.maxAttempts ?? 180;

    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      if (attempt > 0) {
        await new Promise((r) => setTimeout(r, intervalMs));
      }
      const snap = await this.getInsightJobStatus(jobId);
      const st = String(snap.data?.status ?? '');
      if (st === 'completed') {
        return snap.data.result;
      }
      if (st === 'failed') {
        throw new Error(String(snap.data?.error || 'Insight job failed'));
      }
    }
    throw new Error('Insight job timed out while polling status');
  }

  /**
   * POST FormData to an insight route; if the server returns 202, poll until ``result`` is ready.
   */
  async postInsightFormResolve202(url: string, formData: FormData): Promise<unknown> {
    const res = await this.post(url, formData);
    if (res.status === 202 && res.data?.job_id) {
      return await this.pollInsightJobUntilComplete(String(res.data.job_id));
    }
    return res.data;
  }

  /**
   * GET an insight route; if the server returns 202, poll until ``result`` is ready.
   */
  async getInsightResolve202(url: string, options: any = {}): Promise<unknown> {
    const res = await this.get(url, options);
    if (res.status === 202 && res.data?.job_id) {
      return await this.pollInsightJobUntilComplete(String(res.data.job_id));
    }
    return res.data;
  }

  /**
   * Get detailed column info (stats) for all columns in dataset
   */
  async getColumnInfo(datasetId: string): Promise<ColumnInfoResponse> {
    try {
      console.log('Fetching column info for dataset:', datasetId);
      const response = await fetch(`${this.baseUrl}/datasets/${datasetId}/column-info`, {
        headers: this.getAuthHeaders()
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Column info fetch failed: ${response.status} - ${errorData.detail || response.statusText}`);
      }

      const result: ColumnInfoResponse = await response.json();
      console.log('Column info retrieved successfully:', result.total_columns, 'columns');
      return result;
    } catch (error) {
      console.error('Column info fetch failed:', error);
      throw error;
    }
  }

  /**
   * Get detailed column info (stats) filtered by scope (entire, train, test, validation)
   * This is a read-only operation that does NOT modify global state
   */
  async getColumnInfoByScope(datasetId: string, scope: 'entire' | 'train' | 'test' | 'validation'): Promise<ColumnInfoResponse> {
    try {
      console.log('Fetching column info by scope for dataset:', datasetId, 'scope:', scope);
      const response = await fetch(`${this.baseUrl}/datasets/${datasetId}/column-info-by-scope?scope=${scope}`, {
        headers: this.getAuthHeaders()
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Column info by scope fetch failed: ${response.status} - ${errorData.detail || response.statusText}`);
      }

      const result: ColumnInfoResponse = await response.json();
      console.log('Column info by scope retrieved successfully:', result.total_columns, 'columns, scope:', scope, 'rows:', result.total_rows);
      return result;
    } catch (error) {
      console.error('Column info by scope fetch failed:', error);
      throw error;
    }
  }

  /**
   * Get Data Quality Score (DQS) for a dataset
   * Returns composite score and breakdown by 4 dimensions:
   * - Completeness (35%)
   * - Consistency (30%)
   * - Structural Integrity (25%)
   * - Uniqueness (10%)
   */
  async getDataQualityScore(datasetId: string): Promise<DQSResponse> {
    try {
      console.log('Fetching DQS for dataset:', datasetId);
      const response = await fetch(`${this.baseUrl}/datasets/${datasetId}/dqs`, {
        headers: this.getAuthHeaders()
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`DQS fetch failed: ${response.status} - ${errorData.detail || response.statusText}`);
      }

      const result: DQSResponse = await response.json();
      console.log('DQS retrieved successfully:', result.composite_score, `(${result.score_label})`);
      return result;
    } catch (error) {
      console.error('DQS fetch failed:', error);
      throw error;
    }
  }

  /**
   * Get Data Quality Score (DQS) filtered by scope (entire, train, test, validation)
   * This is a read-only operation that does NOT modify global state
   */
  async getDataQualityScoreByScope(datasetId: string, scope: 'entire' | 'train' | 'test' | 'validation'): Promise<DQSResponse> {
    try {
      console.log('Fetching DQS by scope for dataset:', datasetId, 'scope:', scope);
      const response = await fetch(`${this.baseUrl}/datasets/${datasetId}/dqs-by-scope?scope=${scope}`, {
        headers: this.getAuthHeaders()
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`DQS by scope fetch failed: ${response.status} - ${errorData.detail || response.statusText}`);
      }

      const result: DQSResponse = await response.json();
      console.log('DQS by scope retrieved successfully:', result.composite_score, `(${result.score_label})`, 'scope:', scope);
      return result;
    } catch (error) {
      console.error('DQS by scope fetch failed:', error);
      throw error;
    }
  }

  /**
   * P1.4 part 2: One-shot endpoint that returns column-info + DQS for a scope
   * in a single round-trip. Used by the Step 2 Overview sidebar to avoid the
   * 3-5 parallel fan-out that previously stampeded the backend with the same
   * heavy DataFrame load. Falls back to legacy individual endpoints (used by
   * `loadOverviewBundle` below) if the server returns 404 or 405.
   */
  async getOverviewBundle(
    datasetId: string,
    scope: 'entire' | 'train' | 'test' | 'validation'
  ): Promise<{
    success: boolean;
    dataset_id: string;
    scope: string;
    version: number;
    from_cache: { column_info: boolean; dqs: boolean };
    column_info: ColumnInfoResponse;
    dqs: DQSResponse;
  }> {
    const response = await fetch(
      `${this.baseUrl}/datasets/${datasetId}/overview-bundle?scope=${scope}`,
      { headers: this.getAuthHeaders() },
    );
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const err = new Error(
        `Overview bundle fetch failed: ${response.status} - ${errorData.detail || response.statusText}`,
      );
      (err as Error & { status?: number }).status = response.status;
      throw err;
    }
    return await response.json();
  }

  /**
   * P1.4 part 2 (client-side fallback wrapper): try the one-shot bundle, but
   * if it isn't available (older backend, intermittent 404/405), fall back to
   * the two legacy endpoints in parallel - same observable result, slower path.
   *
   * IMPORTANT — 5xx behaviour (4M-row regression fix):
   *   Previously we also fanned out to the two legacy endpoints on any 5xx.
   *   On very large datasets that caused a cascade: the first 504 (Gateway
   *   Timeout / worker overrun) immediately triggered TWO more heavy
   *   parallel calls (column-info-by-scope + dqs-by-scope), each of which
   *   re-loaded the full DataFrame from S3 and finished off the backend
   *   worker. We now NEVER fall back on 5xx; we retry the bundle once with
   *   a short backoff and then surface the error to the caller. Use the
   *   {@link getOverviewBundle} cache hit on the retry (no extra DataFrame
   *   work if the first call seeded the cache).
   */
  async loadOverviewBundle(
    datasetId: string,
    scope: 'entire' | 'train' | 'test' | 'validation'
  ): Promise<{ columnInfo: ColumnInfoResponse; dqs: DQSResponse; fromBundle: boolean }> {
    const tryBundleOnce = async () => this.getOverviewBundle(datasetId, scope);

    try {
      const bundle = await tryBundleOnce();
      return {
        columnInfo: bundle.column_info,
        dqs: bundle.dqs,
        fromBundle: true,
      };
    } catch (err) {
      const status = (err as Error & { status?: number }).status;
      const isMissingEndpoint = status === 404 || status === 405;
      const isServerError = typeof status === 'number' && status >= 500 && status < 600;

      if (isMissingEndpoint) {
        console.warn(
          'overview-bundle endpoint not deployed, falling back to legacy parallel endpoints',
          err,
        );
        const [columnInfo, dqs] = await Promise.all([
          this.getColumnInfoByScope(datasetId, scope),
          this.getDataQualityScoreByScope(datasetId, scope),
        ]);
        return { columnInfo, dqs, fromBundle: false };
      }

      if (isServerError) {
        // One short retry: the bundle endpoint caches its result, so if the
        // first call is what populated the cache the retry is O(1). If the
        // backend is genuinely overloaded we surface the 5xx instead of
        // stampeding it with two more heavy calls.
        console.warn(
          `overview-bundle returned ${status}, retrying once before failing (no legacy fan-out)`,
          err,
        );
        await new Promise((resolve) => setTimeout(resolve, 2000));
        const bundle = await tryBundleOnce();
        return {
          columnInfo: bundle.column_info,
          dqs: bundle.dqs,
          fromBundle: true,
        };
      }

      throw err;
    }
  }

  /**
   * Generate AI-based recommendations for improving data quality based on DQS results
   */
  async generateDqsRecommendations(datasetId: string, dqsData: DQSResponse): Promise<{
    success: boolean;
    recommendations?: Array<{
      title: string;
      description: string;
      type: 'info' | 'warning' | 'success';
      priority: 'high' | 'medium' | 'low';
    }>;
    error?: string;
  }> {
    try {
      console.log('Generating DQS recommendations for dataset:', datasetId);
      const response = await fetch(`${this.baseUrl}/datasets/${datasetId}/dqs-recommendations`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify({ dqs_data: dqsData })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`DQS recommendations failed: ${response.status} - ${errorData.detail || response.statusText}`);
      }

      const result = await response.json();
      console.log('DQS recommendations generated:', result.recommendations?.length || 0);
      return result;
    } catch (error) {
      console.error('DQS recommendations failed:', error);
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Failed to generate recommendations' 
      };
    }
  }

  /**
   * Get variable definitions for columns using AI/LLM
   */
  async getVariableDefinitions(datasetId: string, columns: string[]): Promise<VariableDefinitionsResponse> {
    try {
      console.log('Fetching variable definitions for dataset:', datasetId, 'columns:', columns);
      
      const response = await fetch(`${this.baseUrl}/datasets/${datasetId}/variable-definitions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify({ columns })
      });

      if (!response.ok) {
        // Handle 404 gracefully - endpoint may not exist, return empty definitions
        if (response.status === 404) {
          console.log('Variable definitions endpoint not available, using empty definitions');
          return { success: true, definitions: {} };
        }
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Variable definitions fetch failed: ${response.status} - ${errorData.detail || response.statusText}`);
      }

      const result: VariableDefinitionsResponse = await response.json();
      console.log('Variable definitions retrieved successfully for', columns.length, 'columns');
      return result;
    } catch (error) {
      // Return empty definitions instead of throwing to avoid blocking the flow
      console.log('Variable definitions fetch failed, using empty definitions:', error instanceof Error ? error.message : 'Unknown error');
      return { success: false, definitions: {} };
    }
  }

  /**
   * Validate unique ID columns against an already-uploaded dataset (no file
   * re-upload). The legacy multipart variant has been removed - callers must
   * always go through chunked-upload first and then validate by `dataset_id`.
   *
   * Behaviour:
   *  - 60 s per-attempt timeout (cold S3 stage of a 2 GB sidecar finishes in
   *    well under that; cached scans return in <3 s).
   *  - Up to 3 attempts with 3 s / 6 s exponential backoff for transient
   *    network blips, mirroring `analyzeDataset`.
   *  - The caller's `AbortSignal` (typically a debounced selection-change
   *    signal) short-circuits the in-flight fetch AND any pending backoff.
   */
  async validateUniqueIdsById(
    datasetId: string,
    uniqueIdColumns: string[],
    options?: { signal?: AbortSignal }
  ): Promise<{
    success: boolean;
    is_unique: boolean;
    duplicate_count: number;
    total_rows: number;
    columns: string[];
    message: string;
    error?: string;
    cached?: boolean;
  }> {
    const formData = new FormData();
    formData.append('dataset_id', datasetId);
    formData.append('unique_id_columns', JSON.stringify(uniqueIdColumns));

    const TIMEOUT_MS = 60_000;
    const MAX_RETRIES = 3;
    let lastError: unknown;

    const callerSignal = options?.signal;

    for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
      if (callerSignal?.aborted) {
        throw new DOMException('Aborted', 'AbortError');
      }
      // Combine the caller signal with a per-attempt timeout signal so
      // either a user-driven abort or the timeout can cancel the fetch.
      const ctrl = new AbortController();
      const onCallerAbort = () => ctrl.abort();
      callerSignal?.addEventListener('abort', onCallerAbort, { once: true });
      const timeoutId = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
      try {
        const response = await fetch(
          `${this.baseUrl}/validate-unique-ids-by-id`,
          {
            method: 'POST',
            body: formData,
            headers: this.getAuthHeaders(),
            signal: ctrl.signal,
          }
        );

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(
            `Validation failed: ${response.status} - ${
              (errorData as { detail?: string }).detail || response.statusText
            }`
          );
        }

        return await response.json();
      } catch (err: any) {
        // Caller-driven abort - propagate immediately so the UI doesn't
        // display a stale result for an outdated selection.
        if (callerSignal?.aborted) {
          throw new DOMException('Aborted', 'AbortError');
        }
        lastError = err;
        if (attempt < MAX_RETRIES) {
          const delayMs = attempt * 3000; // 3 s, 6 s
          console.warn(
            `validateUniqueIdsById attempt ${attempt} failed, retrying in ${delayMs}ms`,
            err
          );
          await new Promise<void>((resolve, reject) => {
            const t = setTimeout(resolve, delayMs);
            callerSignal?.addEventListener(
              'abort',
              () => {
                clearTimeout(t);
                reject(new DOMException('Aborted', 'AbortError'));
              },
              { once: true }
            );
          });
        }
      } finally {
        clearTimeout(timeoutId);
        callerSignal?.removeEventListener('abort', onCallerAbort);
      }
    }
    console.error('Unique ID validation failed after retries:', lastError);
    throw lastError;
  }

  /**
   * Upload dataset to FastAPI backend
   */
  async uploadDataset(request: FastAPIUploadRequest): Promise<FastAPIUploadResponse> {
    this.startKeepalive();
    try {
      const formData = new FormData();
      
      // Handle single file or multiple files (for merged validation)
      if (request.merge_validation && request.files && request.files.length > 0) {
        console.log(`Uploading ${request.files.length} validation files to be merged`);
        request.files.forEach((file, index) => {
          formData.append('files', file);
          console.log(`  File ${index + 1}: ${file.name}`);
        });
        formData.append('merge_validation', 'true');
      } else if (request.file) {
        console.log('Uploading dataset to FastAPI backend:', request.file.name);
        formData.append('file', request.file);
      } else if (request.existing_dataset_id) {
        console.log('Using existing dataset ID:', request.existing_dataset_id);
        formData.append('existing_dataset_id', request.existing_dataset_id);
      } else {
        throw new Error('Either file, existing_dataset_id, or files must be provided');
      }
      
      formData.append('target_variable', request.target_variable);
      formData.append('target_variable_type', request.target_variable_type);
      
      if (request.data_dictionary) {
        if (request.data_dictionary instanceof File) {
          // If it's a file, append it as a file
          formData.append('data_dictionary_file', request.data_dictionary);
        } else {
          // If it's a string, append it as text
          formData.append('data_dictionary', request.data_dictionary);
        }
      }
      
      if (request.problem_statement) {
        formData.append('problem_statement', request.problem_statement);
      }

      // Add new optional fields
      if (request.unique_id_combinations && request.unique_id_combinations.length > 0) {
        formData.append('unique_id_combinations', JSON.stringify(request.unique_id_combinations));
      }
      
      if (request.segmentation_variable) {
        formData.append('segmentation_variable', request.segmentation_variable);
      }
      
      if (request.sample_identifier_variable) {
        formData.append('sample_identifier_variable', request.sample_identifier_variable);
      }

      // Add split configuration
      if (request.has_sampling_variable !== undefined && request.has_sampling_variable !== null) {
        formData.append('has_sampling_variable', String(request.has_sampling_variable));
      }
      if (request.sampling_variable) {
        formData.append('sampling_variable', request.sampling_variable);
      }
      if (request.split_ratio !== undefined) {
        formData.append('split_ratio', String(request.split_ratio));
      }
      if (request.initial_scope) {
        formData.append('initial_scope', request.initial_scope);
      }
      if (request.split_configuration) {
        formData.append('split_configuration', request.split_configuration);
      }
      if (request.exclusion_rules) {
        formData.append('exclusion_rules', request.exclusion_rules);
      }
      if (request.variables_to_remove) {
        formData.append('variables_to_remove', request.variables_to_remove);
      }
      if (request.partition_role) {
        formData.append('partition_role', request.partition_role);
      }

      // Compute file-size-aware timeout so the request fails fast on hangs but
      // tolerates large uploads. Uses the largest file's size when multi-file mode.
      const primarySize = request.file?.size
        ?? (request.files && request.files.length > 0 ? Math.max(...request.files.map(f => f.size)) : 0);
      const timeoutMs = this.computeIngestTimeoutMs(primarySize);
      const response = await this.fetchWithTimeout(`${this.baseUrl}/upload`, {
        method: 'POST',
        body: formData,
        headers: this.getAuthHeaders(),
      }, timeoutMs);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Upload failed: ${response.status} - ${errorData.detail || response.statusText}`);
      }

      const result: FastAPIUploadResponse = await response.json();
      console.log('Dataset uploaded successfully:', result.dataset_id);
      return result;
    } catch (error) {
      console.error('Dataset upload failed:', error);
      throw error;
    } finally {
      this.stopKeepalive();
    }
  }

  /**
   * Combine pre-split files (train, test, validation) into a single dataset with split_tag column
   */
  async combinePreSplitFiles(request: {
    files: Array<{ file: File; partitionRole: string }>;
    target_variable: string;
  }): Promise<{ dataset_id: string; total_rows: number; partitions: Record<string, number> }> {
    try {
      console.log(`Combining ${request.files.length} pre-split files`);
      
      const formData = new FormData();
      
      // Append each file
      request.files.forEach((item) => {
        formData.append('files', item.file);
      });
      
      // Send partition roles as JSON string
      const partitionRoles = request.files.map((item) => item.partitionRole);
      formData.append('partition_roles_json', JSON.stringify(partitionRoles));
      
      formData.append('target_variable', request.target_variable);
      
      const response = await fetch(`${this.baseUrl}/combine-presplit`, {
        method: 'POST',
        body: formData,
        headers: this.getAuthHeaders(),
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Combine failed: ${response.status} - ${errorData.detail || response.statusText}`);
      }
      
      const result = await response.json();
      console.log('Pre-split files combined successfully:', result.dataset_id);
      return result;
    } catch (error) {
      console.error('Combine pre-split files failed:', error);
      throw error;
    }
  }

  /**
   * Finalize pre-split dataset - apply exclusion rules and variable removal to combined dataset
   */
  async finalizePreSplitDataset(request: {
    dataset_id: string;
    target_variable: string;
    target_variable_type: 'Numerical' | 'Categorical';
    problem_statement?: string;
    data_dictionary?: string | File;
    unique_id_combinations?: string[];
    segmentation_variable?: string;
    sample_identifier_variable?: string;
    exclusion_rules?: string;
    variables_to_remove?: string;
  }): Promise<{ success: boolean; rows_after_exclusion?: number; columns_after_removal?: number }> {
    try {
      console.log(`Finalizing pre-split dataset: ${request.dataset_id}`);
      
      const formData = new FormData();
      formData.append('dataset_id', request.dataset_id);
      formData.append('target_variable', request.target_variable);
      formData.append('target_variable_type', request.target_variable_type);
      
      if (request.problem_statement) {
        formData.append('problem_statement', request.problem_statement);
      }
      if (request.data_dictionary) {
        if (request.data_dictionary instanceof File) {
          formData.append('data_dictionary_file', request.data_dictionary);
        } else {
          formData.append('data_dictionary', request.data_dictionary);
        }
      }
      if (request.unique_id_combinations && request.unique_id_combinations.length > 0) {
        formData.append('unique_id_combinations', JSON.stringify(request.unique_id_combinations));
      }
      if (request.segmentation_variable) {
        formData.append('segmentation_variable', request.segmentation_variable);
      }
      if (request.sample_identifier_variable) {
        formData.append('sample_identifier_variable', request.sample_identifier_variable);
      }
      if (request.exclusion_rules) {
        formData.append('exclusion_rules', request.exclusion_rules);
      }
      if (request.variables_to_remove) {
        formData.append('variables_to_remove', request.variables_to_remove);
      }
      
      const response = await fetch(`${this.baseUrl}/finalize-presplit`, {
        method: 'POST',
        body: formData,
        headers: this.getAuthHeaders(),
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Finalize failed: ${response.status} - ${errorData.detail || response.statusText}`);
      }
      
      const result = await response.json();
      console.log('Pre-split dataset finalized successfully');
      return result;
    } catch (error) {
      console.error('Finalize pre-split dataset failed:', error);
      throw error;
    }
  }

  /**
   * P2.5: Resumable chunked upload client for files larger than the
   * comfortable single-PUT range (Azure Front Door times out 100 MiB+
   * single PUTs on slow networks). Three RPCs:
   *
   *   1. POST /upload-chunked/init       - reserve an upload_id
   *   2. PATCH /upload-chunked/{id}      - one Content-Range PATCH per chunk
   *      (auto-retries up to MAX_RETRIES per chunk on transient failure)
   *   3. POST /upload-chunked/{id}/finalize -> { dataset_id, storage_key }
   *
   * Chunks are dispatched in parallel via a fixed-size worker pool
   * (`CONCURRENCY` in flight). The backend uses `os.pwrite` so out-of-order
   * arrivals are safe; retries that re-send the same Content-Range are
   * idempotent. Browsers cap simultaneous connections per origin at 6,
   * which is exactly our default - higher concurrency would just queue
   * inside the browser.
   *
   * Speed-up vs the previous serial loop: ~Nx where N is the number of
   * parallel workers (network-bound). On a 2 GB file this drops upload
   * wall-time from ~minutes to ~seconds on a typical office connection.
   */
  async chunkedUpload(
    file: File,
    onProgress?: (sent: number, total: number) => void,
  ): Promise<{ dataset_id: string; storage_key: string; filename: string; total_size: number }> {
    if (!file || file.size === 0) {
      throw new Error('Empty file passed to chunkedUpload');
    }

    const initRes = await fetch(`${this.baseUrl}/upload-chunked/init`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...this.getAuthHeaders() },
      body: JSON.stringify({ filename: file.name, total_size: file.size }),
    });
    if (!initRes.ok) {
      const err = await initRes.json().catch(() => ({}));
      throw new Error(`chunked-upload init failed: ${initRes.status} - ${err.detail || initRes.statusText}`);
    }
    const { upload_id, chunk_size_hint } = await initRes.json();
    const chunkSize: number = chunk_size_hint && chunk_size_hint > 0 ? chunk_size_hint : 8 * 1024 * 1024;

    type ChunkSpec = { start: number; end: number };
    const queue: ChunkSpec[] = [];
    for (let start = 0; start < file.size; start += chunkSize) {
      const end = Math.min(start + chunkSize, file.size) - 1;
      queue.push({ start, end });
    }

    const MAX_RETRIES = 3;
    const CONCURRENCY = Math.min(6, queue.length);
    let totalSent = 0;
    let nextIndex = 0;
    let aborted = false;
    let firstError: unknown = null;

    const uploadOne = async (spec: ChunkSpec): Promise<void> => {
      const blob = file.slice(spec.start, spec.end + 1);
      let attempt = 0;
      while (true) {
        try {
          const res = await fetch(`${this.baseUrl}/upload-chunked/${upload_id}`, {
            method: 'PATCH',
            headers: {
              'Content-Type': 'application/octet-stream',
              'Content-Range': `bytes ${spec.start}-${spec.end}/${file.size}`,
              ...this.getAuthHeaders(),
            },
            body: blob,
          });
          if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            const detail = err.detail || res.statusText;
            // 4xx errors that aren't transient (range/total-size mismatches)
            // should fail fast - retrying won't help.
            if (res.status >= 400 && res.status < 500 && res.status !== 408 && res.status !== 429) {
              throw new Error(`chunk PATCH failed: ${res.status} - ${detail}`);
            }
            throw new Error(`chunk PATCH failed: ${res.status} - ${detail}`);
          }
          return;
        } catch (err) {
          attempt += 1;
          if (attempt >= MAX_RETRIES) throw err;
          console.warn(
            `chunked-upload chunk ${spec.start}-${spec.end} retry ${attempt}/${MAX_RETRIES}`,
            err,
          );
          await new Promise(r => setTimeout(r, attempt * 1500));
        }
      }
    };

    const worker = async (): Promise<void> => {
      while (!aborted) {
        const i = nextIndex++;
        if (i >= queue.length) return;
        const spec = queue[i];
        try {
          await uploadOne(spec);
        } catch (err) {
          aborted = true;
          if (firstError === null) firstError = err;
          return;
        }
        totalSent += (spec.end - spec.start + 1);
        onProgress?.(totalSent, file.size);
      }
    };

    await Promise.all(
      Array.from({ length: CONCURRENCY }, () => worker()),
    );
    if (firstError !== null) {
      // Best-effort cancel so the server frees pre-allocated disk; don't
      // wait, don't surface a cancel error over the original failure.
      try {
        await fetch(`${this.baseUrl}/upload-chunked/${upload_id}`, {
          method: 'DELETE',
          headers: this.getAuthHeaders(),
        });
      } catch {
        // ignore
      }
      throw firstError;
    }

    const finalRes = await fetch(`${this.baseUrl}/upload-chunked/${upload_id}/finalize`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
    });
    if (!finalRes.ok) {
      const err = await finalRes.json().catch(() => ({}));
      throw new Error(`chunked-upload finalize failed: ${finalRes.status} - ${err.detail || finalRes.statusText}`);
    }
    return await finalRes.json();
  }

  /**
   * Analyze dataset and return available columns and their types.
   *
   * P1.1 part 2: when `request.previewBytes` is set (default 5 MiB for files
   * larger than that), we upload only a head-slice of the CSV so multi-GB
   * files don't waste bandwidth just to surface column types in the picker.
   * The backend extrapolates the full row count from the slice's row density
   * and tags `dataset_info.is_estimated = true`.
   *
   * Pass `previewBytes: 0` (or a value >= file.size) to keep the legacy
   * "send full file" behavior - useful for endpoints that need exact counts.
   */
  async analyzeDataset(
    request: FastAPIDatasetAnalysisRequest & { previewBytes?: number }
  ): Promise<FastAPIDatasetAnalysisResponse> {
    this.startKeepalive();
    try {
      console.log('Analyzing dataset:', request.file.name);
      console.log("Base url new from frontend",import.meta.env.VITE_BASE_URL)

      // Decide whether to slice. Default: slice anything bigger than 5 MiB.
      const DEFAULT_PREVIEW_BYTES = 5 * 1024 * 1024;
      const requested = request.previewBytes;
      const previewBytes = requested === undefined ? DEFAULT_PREVIEW_BYTES : requested;
      const useSlice = previewBytes > 0 && request.file.size > previewBytes;
      const payload: Blob = useSlice
        ? request.file.slice(0, previewBytes, request.file.type)
        : request.file;

      const formData = new FormData();
      // Preserve the file name for backend logging/dispatch.
      formData.append('file', payload, request.file.name);
      if (useSlice) {
        formData.append('is_preview', 'true');
        formData.append('original_size', String(request.file.size));
        console.log(
          `analyzeDataset: uploading ${(previewBytes / 1024 / 1024).toFixed(1)} MiB head-slice ` +
            `of ${(request.file.size / 1024 / 1024).toFixed(1)} MiB file`,
        );
      }

      // Retry with exponential backoff - transient network blips on Azure should not fail the user
      const MAX_RETRIES = 3;
      let lastError: unknown;
      // Time out based on the *uploaded* size, not the original file size.
      const timeoutMs = this.computeIngestTimeoutMs(useSlice ? previewBytes : request.file.size);
      for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
        try {
          const response = await this.fetchWithTimeout(`${this.baseUrl}/analyze-dataset`, {
            method: 'POST',
            body: formData,
            headers: this.getAuthHeaders(),
          }, timeoutMs);

          if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(`Analysis failed: ${response.status} - ${errorData.detail || response.statusText}`);
          }

          const result: FastAPIDatasetAnalysisResponse = await response.json();
          console.log('Dataset analysis completed:', result.dataset_info.columns.length, 'columns found');
          return result;
        } catch (err) {
          lastError = err;
          if (attempt < MAX_RETRIES) {
            const delayMs = attempt * 3000; // 3 s, 6 s
            console.warn(`⚠️ analyzeDataset attempt ${attempt} failed, retrying in ${delayMs}ms…`, err);
            await new Promise(r => setTimeout(r, delayMs));
          }
        }
      }
      throw lastError;
    } catch (error) {
      console.error('Dataset analysis failed:', error);
      throw error;
    } finally {
      this.stopKeepalive();
    }
  }

  /**
   * Partition preview for Review Stats (Step 1) - train/test/holdout metrics from CSV + split config.
   */
  async partitionPreview(params: {
    file: File;
    split_configuration: Record<string, unknown>;
    target_variable: string;
    exclusion_rules?: Array<{
      id: string;
      conditions: Array<{
        column: string;
        operator: string;
        value: string | number | string[] | [number, number] | null;
        connector: 'AND' | 'OR';
      }>;
    }>;
    variables_to_remove?: string[];
  }): Promise<PartitionPreviewResponse> {
    const formData = new FormData();
    formData.append('file', params.file);
    formData.append('split_configuration', JSON.stringify(params.split_configuration));
    formData.append('target_variable', params.target_variable.trim());
    if (params.exclusion_rules && params.exclusion_rules.length > 0) {
      formData.append('exclusion_rules', JSON.stringify(params.exclusion_rules));
    }
    if (params.variables_to_remove && params.variables_to_remove.length > 0) {
      formData.append('variables_to_remove', JSON.stringify(params.variables_to_remove));
    }

    const response = await fetch(`${this.baseUrl}/partition-preview`, {
      method: 'POST',
      body: formData,
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        `Partition preview failed: ${response.status} - ${(errorData as { detail?: string }).detail || response.statusText}`
      );
    }

    return (await response.json()) as PartitionPreviewResponse;
  }

  /**
   * Partition preview using cached dataset (no file upload) - optimized for large files.
   */
  async partitionPreviewById(params: {
    dataset_id: string;
    split_configuration: Record<string, unknown>;
    target_variable: string;
    exclusion_rules?: Array<{
      id: string;
      conditions: Array<{
        column: string;
        operator: string;
        value: string | number | string[] | [number, number] | null;
        connector: 'AND' | 'OR';
      }>;
    }>;
    variables_to_remove?: string[];
  }): Promise<PartitionPreviewResponse> {
    const formData = new FormData();
    formData.append('dataset_id', params.dataset_id);
    formData.append('split_configuration', JSON.stringify(params.split_configuration));
    formData.append('target_variable', params.target_variable.trim());
    if (params.exclusion_rules && params.exclusion_rules.length > 0) {
      formData.append('exclusion_rules', JSON.stringify(params.exclusion_rules));
    }
    if (params.variables_to_remove && params.variables_to_remove.length > 0) {
      formData.append('variables_to_remove', JSON.stringify(params.variables_to_remove));
    }

    const response = await fetch(`${this.baseUrl}/partition-preview-by-id`, {
      method: 'POST',
      body: formData,
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        `Partition preview failed: ${response.status} - ${(errorData as { detail?: string }).detail || response.statusText}`
      );
    }

    return (await response.json()) as PartitionPreviewResponse;
  }

  /**
   * Exclusion preview - evaluate exclusion rules and return waterfall statistics.
   */
  async getExclusionPreview(
    file: File,
    exclusionGroups: Array<{
      id: string;
      conditions: Array<{
        column: string;
        operator: string;
        value: string | number | string[] | [number, number] | null;
        connector: 'AND' | 'OR';
      }>;
    }>,
    targetVariable: string
  ): Promise<{
    waterfall: Array<{
      step: string;
      label?: string;
      removed: number | string;
      remaining: number;
      eventRate: number | null;
      eventCount?: number | null;
      nonEventCount?: number | null;
    }>;
    warnings: Array<{
      level: 'amber' | 'red' | 'block';
      message: string;
    }>;
  }> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('exclusion_groups', JSON.stringify(exclusionGroups));
    formData.append('target_variable', targetVariable.trim());

    const response = await fetch(`${this.baseUrl}/exclusion-preview`, {
      method: 'POST',
      body: formData,
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        `Exclusion preview failed: ${response.status} - ${(errorData as { detail?: string }).detail || response.statusText}`
      );
    }

    const result = await response.json();
    return {
      waterfall: result.waterfall || [],
      warnings: result.warnings || [],
    };
  }

  /**
   * Exclusion preview by dataset ID - for pre-split combined datasets.
   * Uses the dataset already stored in backend memory instead of uploading a file.
   */
  async getExclusionPreviewById(
    datasetId: string,
    exclusionGroups: Array<{
      id: string;
      conditions: Array<{
        column: string;
        operator: string;
        value: string | number | string[] | [number, number] | null;
        connector: 'AND' | 'OR';
      }>;
    }>,
    targetVariable: string
  ): Promise<{
    waterfall: Array<{
      step: string;
      label?: string;
      removed: number | string;
      remaining: number;
      eventRate: number | null;
      eventCount?: number | null;
      nonEventCount?: number | null;
    }>;
    warnings: Array<{
      level: 'amber' | 'red' | 'block';
      message: string;
    }>;
  }> {
    const formData = new FormData();
    formData.append('dataset_id', datasetId);
    formData.append('exclusion_groups', JSON.stringify(exclusionGroups));
    formData.append('target_variable', targetVariable.trim());

    const response = await fetch(`${this.baseUrl}/exclusion-preview-by-id`, {
      method: 'POST',
      body: formData,
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        `Exclusion preview by ID failed: ${response.status} - ${(errorData as { detail?: string }).detail || response.statusText}`
      );
    }

    const result = await response.json();
    return {
      waterfall: result.waterfall || [],
      warnings: result.warnings || [],
    };
  }

  // =======================
  // Variable Review Methods
  // =======================

  /**
   * Run variable review preview on an uploaded file (before submission).
   * Similar to getExclusionPreview - works on the raw CSV file.
   * 
   * LLM Touchpoints (when data dictionary is provided):
   * - TP1: After Layer 2 - Classify high-AUC variables as origination/behavioral/lifecycle/post_event
   * - TP2: After Layer 3 - Confirm zero-inflated variables are populated post-event
   * - TP3: After Layer 4 - Reason about differential missingness causal linkage
   */
  async getVariableReviewPreview(
    file: File,
    targetVariable: string,
    sampleIdCol?: string | null,
    weightCol?: string | null,
    dataDictionary?: string | null,
    dataDictionaryFile?: File | null,
    enableLlmReasoning: boolean = true
  ): Promise<VariableReviewResponse> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('target_variable', targetVariable.trim());
    if (sampleIdCol) {
      formData.append('sample_id_col', sampleIdCol.trim());
    }
    if (weightCol) {
      formData.append('weight_col', weightCol.trim());
    }
    if (dataDictionary) {
      formData.append('data_dictionary', dataDictionary);
    }
    if (dataDictionaryFile) {
      formData.append('data_dictionary_file', dataDictionaryFile);
    }
    formData.append('enable_llm_reasoning', enableLlmReasoning ? 'true' : 'false');

    const response = await this.fetchWithAutoRefresh(`${this.baseUrl}/variable-review/preview`, {
      method: 'POST',
      body: formData,
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        `Variable review preview failed: ${response.status} - ${(errorData as { detail?: string }).detail || response.statusText}`
      );
    }

    return await response.json();
  }

  /**
   * Run the 6-layer variable review pipeline to detect identifiers, leakage, and low-value variables.
   * This version works on an already-uploaded dataset (by dataset_id).
   */
  async runVariableReview(request: VariableReviewRequest): Promise<VariableReviewResponse> {
    const response = await this.fetchWithAutoRefresh(`${this.baseUrl}/variable-review/run`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        `Variable review failed: ${response.status} - ${(errorData as { detail?: string }).detail || response.statusText}`
      );
    }

    return await response.json();
  }

  /**
   * Apply variable removal - removes selected variables from the dataset.
   */
  async applyVariableRemoval(request: ApplyVariableRemovalRequest): Promise<ApplyVariableRemovalResponse> {
    const response = await this.fetchWithAutoRefresh(`${this.baseUrl}/variable-review/apply`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        `Apply variable removal failed: ${response.status} - ${(errorData as { detail?: string }).detail || response.statusText}`
      );
    }

    return await response.json();
  }

  /**
   * Chat with FastAPI backend using dataset context
   */
  async chatWithDataset(request: FastAPIChatRequest): Promise<FastAPIChatResponse> {
    try {
      console.log('💬 Sending chat request to FastAPI backend:', request.query.substring(0, 50) + '...');
      
      const response = await this.fetchWithAutoRefresh(`${this.baseUrl}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Chat failed: ${response.status} - ${errorData.detail || response.statusText}`);
      }

      const result: FastAPIChatResponse = await response.json();
      console.log('Chat response received from FastAPI backend');
      return result;
    } catch (error) {
      if (error instanceof SessionExpiredError || error instanceof SilentAuthFailure) {
        throw error;
      }
      console.error('Chat request failed:', error);
      throw error;
    }
  }

  /**
   * Step 6 — LLM narrative comparing shortlisted models (max 2 per algorithm).
   */
  async crossAlgorithmRecommendation(
    datasetId: string,
    body: { problem_type: string; candidates: unknown[]; lr_digest?: unknown[] },
  ): Promise<{ success: boolean; summary: string; error?: string | null }> {
    const response = await this.fetchWithAutoRefresh(
      `${this.baseUrl}/datasets/${datasetId}/cross-algorithm-recommendation`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify(body),
      },
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        `Cross-algorithm recommendation failed: ${response.status} - ${errorData.detail || response.statusText}`,
      );
    }

    return await response.json();
  }

  /**
   * Get dataset statistics
   */
  async getDatasetStats(datasetId: string): Promise<DataStats> {
    try {
      console.log('Fetching dataset stats for:', datasetId);
      
      const response = await fetch(`${this.baseUrl}/datasets/${datasetId}/stats`, {
        headers: this.getAuthHeaders()
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Stats fetch failed: ${response.status} - ${errorData.detail || response.statusText}`);
      }

      const result: DataStats = await response.json();
      console.log('Dataset stats retrieved successfully');
      return result;
    } catch (error) {
      console.error('Dataset stats fetch failed:', error);
      throw error;
    }
  }

  /**
   * Delete dataset
   */
  async deleteDataset(datasetId: string): Promise<void> {
    try {
      console.log('🗑️ Deleting dataset:', datasetId);
      
      const response = await fetch(`${this.baseUrl}/datasets/${datasetId}`, {
        method: 'DELETE',
        headers: this.getAuthHeaders()
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Delete failed: ${response.status} - ${errorData.detail || response.statusText}`);
      }

      console.log('Dataset deleted successfully');
    } catch (error) {
      console.error('Dataset deletion failed:', error);
      throw error;
    }
  }

  /**
   * Health check for FastAPI backend
   */
  async healthCheck(): Promise<boolean> {
    try {
      console.log('🏥 Checking FastAPI backend health...');
      
      // Health endpoint is at root /health, not /api/v1/health
      // Extract base URL without /api/v1 suffix
      let healthUrl: string;
      if (this.baseUrl.includes('/api/v1')) {
        // Remove /api/v1 from the end
        const baseUrlWithoutApi = this.baseUrl.replace(/\/api\/v1\/?$/, '');
        healthUrl = baseUrlWithoutApi ? `${baseUrlWithoutApi}/health` : '/health';
      } else {
        // If baseUrl doesn't have /api/v1, use it as-is and append /health
        healthUrl = this.baseUrl ? `${this.baseUrl}/health` : '/health';
      }
      
      console.log('🏥 Health check URL:', healthUrl, 'Base URL:', this.baseUrl);
      const response = await fetch(healthUrl);
      
      if (!response.ok) {
        console.warn('⚠️ FastAPI backend health check failed:', response.status);
        return false;
      }

      const result: HealthCheckResponse = await response.json();
      console.log('FastAPI backend is healthy:', result);
      return result.status === 'healthy';
    } catch (error) {
      console.error('FastAPI backend health check failed:', error);
      return false;
    }
  }

  /**
   * Reinitialize vector store
   */
  async reinitializeVectorStore(): Promise<{ message: string; documents_count: number }> {
    try {
      console.log('Reinitializing vector store...');
      
      const response = await fetch(`${this.baseUrl}/vector-store/reinitialize`, {
        method: 'POST',
        headers: this.getAuthHeaders()
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Vector store reinitialization failed: ${response.status} - ${errorData.detail || response.statusText}`);
      }

      const result = await response.json();
      console.log('Vector store reinitialized successfully');
      return result;
    } catch (error) {
      console.error('Vector store reinitialization failed:', error);
      throw error;
    }
  }

  /**
   * Get raw data from dataset
   */
  async getRawData(datasetId: string, limit: number = 100): Promise<RawDataResponse> {
    try {
      console.log('Fetching raw data for dataset:', datasetId);
      console.log('API URL:', `${this.baseUrl}/datasets/${datasetId}/raw-data?limit=${limit}`);
      
      const response = await fetch(`${this.baseUrl}/datasets/${datasetId}/raw-data?limit=${limit}`, {
        headers: this.getAuthHeaders()
      });

      console.log('Response status:', response.status);
      console.log('Response ok:', response.ok);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        console.error('Error response data:', errorData);
        throw new Error(`Raw data fetch failed: ${response.status} - ${errorData.detail || response.statusText}`);
      }

      const result: RawDataResponse = await response.json();
      console.log('Raw data retrieved successfully:', result.returned_rows, 'rows');
      return result;
    } catch (error) {
      console.error('Raw data fetch failed:', error);
      throw error;
    }
  }

  /**
   * Export dataset
   */
  async exportDataset(datasetId: string, format: string = 'csv'): Promise<void> {
    try {
      console.log('📤 Exporting dataset:', datasetId, 'format:', format);
      
      const response = await fetch(`${this.baseUrl}/datasets/${datasetId}/export?format=${format}`, {
        headers: this.getAuthHeaders()
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Export failed: ${response.status} - ${errorData.detail || response.statusText}`);
      }

      // Create blob and download
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = response.headers.get('content-disposition')?.split('filename=')[1] || `dataset_${datasetId}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      console.log('Dataset exported successfully');
    } catch (error) {
      console.error('Dataset export failed:', error);
      throw error;
    }
  }

  /**
   * Update dataset configuration
   */
  async updateDatasetConfig(datasetId: string, config: ConfigUpdateRequest, dataDictionaryFile?: File | null): Promise<ConfigUpdateResponse> {
    try {
      console.log('⚙️ Updating dataset configuration:', datasetId);
      
      const formData = new FormData();
      if (config.target_variable) {
        formData.append('target_variable', config.target_variable);
      }
      if (config.target_variable_type) {
        formData.append('target_variable_type', config.target_variable_type);
      }
      if (config.problem_statement) {
        formData.append('problem_statement', config.problem_statement);
      }
      if (dataDictionaryFile) {
        formData.append('data_dictionary_file', dataDictionaryFile);
        console.log('📎 Data dictionary CSV file attached:', dataDictionaryFile.name);
      } else if (config.data_dictionary) {
        formData.append('data_dictionary', config.data_dictionary);
      }

      const response = await fetch(`${this.baseUrl}/datasets/${datasetId}/config`, {
        method: 'PUT',
        body: formData,
        headers: this.getAuthHeaders(),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Config update failed: ${response.status} - ${errorData.detail || response.statusText}`);
      }

      const result: ConfigUpdateResponse = await response.json();
      console.log('Dataset configuration updated successfully');
      return result;
    } catch (error) {
      console.error('Dataset configuration update failed:', error);
      throw error;
    }
  }

  /**
   * Get real distribution data for a specific column
   * @param fullDistribution - If true, returns ALL categories without limiting to top 20 (for stratified split calculation)
   */
  async getColumnDistribution(datasetId: string, columnName: string, bins: number = 10, fullDistribution: boolean = false): Promise<ColumnDistributionResponse> {
    try {
      console.log('Fetching column distribution:', datasetId, columnName, 'fullDistribution:', fullDistribution);

      const response = await fetch(`${this.baseUrl}/datasets/${datasetId}/column-distribution/${encodeURIComponent(columnName)}?bins=${bins}&full_distribution=${fullDistribution}`, {
        headers: this.getAuthHeaders()
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Column distribution fetch failed: ${response.status} - ${errorData.detail || response.statusText}`);
      }

      const result: ColumnDistributionResponse = await response.json();
      console.log('Column distribution retrieved successfully:', Object.keys(result.distribution).length, 'bins/categories');
      return result;
    } catch (error) {
      console.error('Column distribution fetch failed:', error);
      throw error;
    }
  }

  /**
   * Get column distribution filtered by scope (entire, train, test, validation)
   * This is a read-only operation that does NOT modify global state
   */
  async getColumnDistributionByScope(
    datasetId: string, 
    columnName: string, 
    scope: 'entire' | 'train' | 'test' | 'validation',
    bins: number = 10, 
    fullDistribution: boolean = false
  ): Promise<ColumnDistributionResponse> {
    try {
      console.log('Fetching column distribution by scope:', datasetId, columnName, 'scope:', scope);

      const response = await fetch(
        `${this.baseUrl}/datasets/${datasetId}/column-distribution-by-scope/${encodeURIComponent(columnName)}?scope=${scope}&bins=${bins}&full_distribution=${fullDistribution}`, 
        { headers: this.getAuthHeaders() }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Column distribution by scope fetch failed: ${response.status} - ${errorData.detail || response.statusText}`);
      }

      const result: ColumnDistributionResponse = await response.json();
      console.log('Column distribution by scope retrieved successfully:', Object.keys(result.distribution).length, 'bins/categories, scope:', scope);
      return result;
    } catch (error) {
      console.error('Column distribution by scope fetch failed:', error);
      throw error;
    }
  }

  /**
   * Classify variables in a dataset using LLM analysis
   */
  async classifyDatasetVariables(datasetId: string): Promise<VariableClassificationResponse> {
    this.startKeepalive();
    try {
      console.log('🧠 Enqueuing variable classification for dataset:', datasetId);

      // POST returns immediately with queued/cached status - no long connection held open
      const postResp = await fetch(`${this.baseUrl}/datasets/${datasetId}/classify-variables`, {
        method: 'POST',
        headers: this.getAuthHeaders(),
      });

      if (!postResp.ok) {
        const err = await postResp.json().catch(() => ({}));
        throw new Error(`Variable classification failed: ${postResp.status} - ${err.detail || postResp.statusText}`);
      }

      const postData = await postResp.json();

      // If the backend returned a cached/completed result synchronously, use it directly
      if (postData.classification || (postData.success && !postData.queued)) {
        console.log('⚡ Variable classification returned from cache instantly');
        return postData as VariableClassificationResponse;
      }

      // Otherwise poll the status endpoint until done (max ~120 s, 3-second intervals)
      console.log('⏳ Variable classification queued - polling for result…');
      const statusUrl = `${this.baseUrl}/datasets/${datasetId}/classify-variables/status`;
      const maxAttempts = 40;
      for (let attempt = 0; attempt < maxAttempts; attempt++) {
        await new Promise(r => setTimeout(r, 3000));
        const pollResp = await fetch(statusUrl, { headers: this.getAuthHeaders() });
        if (!pollResp.ok) continue;
        const data = await pollResp.json();
        if (data.status === 'completed' || data.classification) {
          console.log('✅ Variable classification completed');
          if (data.classification) {
            console.log(`Classified ${data.classification.variables?.length ?? 0} variables`);
          }
          return data as VariableClassificationResponse;
        }
        if (data.status === 'failed') {
          throw new Error(`Variable classification job failed: ${data.error || 'unknown error'}`);
        }
        console.log(`⏳ Variable classification in progress… (attempt ${attempt + 1}/${maxAttempts})`);
      }
      throw new Error('Variable classification timed out after 120 seconds');
    } catch (error) {
      console.error('Variable classification failed:', error);
      throw error;
    } finally {
      this.stopKeepalive();
    }
  }

  /**
   * Execute Python code on a dataset
   */
  async executeCode(datasetId: string, code: string): Promise<CodeExecutionResponse> {
    this.startKeepalive();
    try {
      console.log('Executing code for dataset:', datasetId);
      
      const formData = new FormData();
      formData.append('dataset_id', datasetId);
      formData.append('code', code);
      
      const response = await fetch(`${this.baseUrl}/execute-code`, {
        method: 'POST',
        body: formData,
        headers: this.getAuthHeaders(),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Code execution failed: ${response.status} - ${errorData.detail || response.statusText}`);
      }

      const result: CodeExecutionResponse = await response.json();
      console.log('Code executed successfully');
      return result;
    } catch (error) {
      console.error('Code execution failed:', error);
      throw error;
    } finally {
      this.stopKeepalive();
    }
  }

  // ==========================================================================
  // QC STEP-BY-STEP METHODS (Manual QC Mode)
  // ==========================================================================

  /**
   * Get the next QC treatment step in Manual QC mode
   * Called after user applies or skips current treatment
   */
  async qcNextStep(
    datasetId: string, 
    action: 'apply' | 'skip', 
    treatmentType: string,
    code?: string
  ): Promise<QCNextStepResponse> {
    this.startKeepalive();
    try {
      console.log(`🔄 QC Next Step: dataset=${datasetId}, action=${action}, treatment=${treatmentType}`);
      
      const response = await this.fetchWithAutoRefresh(`${this.baseUrl}/qc/next-step`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify({
          dataset_id: datasetId,
          action: action,
          treatment_type: treatmentType,
          code: code || null
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`QC next step failed: ${response.status} - ${errorData.detail || response.statusText}`);
      }

      const result: QCNextStepResponse = await response.json();
      console.log('✅ QC next step received:', result);
      return result;
    } catch (error) {
      console.error('❌ QC next step failed:', error);
      throw error;
    } finally {
      this.stopKeepalive();
    }
  }

  /**
   * Apply current QC treatment and get next step
   */
  async applyQCTreatment(
    datasetId: string,
    treatmentType: string,
    code: string
  ): Promise<QCNextStepResponse> {
    return this.qcNextStep(datasetId, 'apply', treatmentType, code);
  }

  /**
   * Skip current QC treatment and get next step
   */
  async skipQCTreatment(
    datasetId: string,
    treatmentType: string
  ): Promise<QCNextStepResponse> {
    return this.qcNextStep(datasetId, 'skip', treatmentType);
  }

  /**
   * Regenerate current manual QC treatment code using dropdown user selections.
   */
  async regenerateQCTreatmentCode(
    datasetId: string,
    treatmentType: string,
    selections: Record<string, string>
  ): Promise<QCRegenerateCodeResponse> {
    this.startKeepalive();
    try {
      const response = await this.fetchWithAutoRefresh(`${this.baseUrl}/qc/regenerate-code`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify({
          dataset_id: datasetId,
          treatment_type: treatmentType,
          selections,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`QC regenerate failed: ${response.status} - ${errorData.detail || response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('❌ QC regenerate failed:', error);
      throw error;
    } finally {
      this.stopKeepalive();
    }
  }

  /**
   * Generate knowledge graph visualization from dataset metadata
   */
  async generateKnowledgeGraph(datasetId: string): Promise<KnowledgeGraphResultPayload> {
    this.startKeepalive();
    try {
      console.log('🕸️ Generating knowledge graph for dataset:', datasetId);

      const response = await fetch(`${this.baseUrl}/generate-knowledge-graph`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify({ dataset_id: datasetId }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Knowledge graph generation failed: ${response.status} - ${errorData.detail || response.statusText}`);
      }

      const result: KnowledgeGraphResultPayload = await response.json();
      console.log('Knowledge graph generated successfully');
      return result;
    } catch (error) {
      console.error('Knowledge graph generation failed:', error);
      throw error;
    } finally {
      this.stopKeepalive();
    }
  }

  async pollKnowledgeGraphProgress(datasetId: string): Promise<{
    available: boolean;
    result?: KnowledgeGraphResultPayload;
    message?: string;
  }> {
    try {
      const response = await fetch(`${this.baseUrl}/knowledge-graph-progress/${datasetId}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
      });

      if (response.status === 404) {
        return { available: false, message: 'No cached knowledge graph yet' };
      }

      if (!response.ok) {
        const detail = await response.text().catch(() => '');
        throw new Error(`Failed to check knowledge graph progress: ${response.status} ${detail}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Failed to poll knowledge graph progress:', error);
      throw error;
    }
  }

    /**
   * Create EventSource for Server-Sent Events stream of knowledge graph updates
   */
    createKnowledgeGraphStream(datasetId: string, token: string): EventSource {
      const url = `${this.baseUrl}/knowledge-graph-stream/${datasetId}?token=${token}`;
      return new EventSource(url);
    }

  /**
   * Upload user knowledge files for a dataset and scope.
   */
  async uploadUserKnowledge(params: {
    dataset_id: string;
    scope: string;
    use_across_midas: boolean;
    use_exl_expertise: boolean;
    files: File[];
  }): Promise<{ indexed_chunks: number; total_chunks: number; warnings: string[] }> {
    const formData = new FormData();
    formData.append('dataset_id', params.dataset_id);
    formData.append('scope', params.scope);
    formData.append('use_across_midas', String(params.use_across_midas));
    formData.append('use_exl_expertise', String(params.use_exl_expertise));
    for (const file of params.files) {
      formData.append('files', file);
    }
    const response = await fetch(`${this.baseUrl}/user-knowledge/upload`, {
      method: 'POST',
      headers: { ...this.getAuthHeaders() },
      body: formData,
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Knowledge upload failed: ${response.status}`);
    }
    return response.json();
  }

  /**
   * Persist user knowledge preferences (EXL expertise toggle) without uploading files.
   */
  async updateUserKnowledgePreferences(params: {
    dataset_id: string;
    scope: string;
    use_across_midas: boolean;
    use_exl_expertise: boolean;
  }): Promise<void> {
    const formData = new FormData();
    formData.append('dataset_id', params.dataset_id);
    formData.append('scope', params.scope);
    formData.append('use_across_midas', String(params.use_across_midas));
    formData.append('use_exl_expertise', String(params.use_exl_expertise));
    const response = await fetch(`${this.baseUrl}/user-knowledge/preferences`, {
      method: 'POST',
      headers: { ...this.getAuthHeaders() },
      body: formData,
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Preferences update failed: ${response.status}`);
    }
  }

  /**
   * Train a global supervised classification model
   */
  async trainGlobalModel(request: GlobalModelTrainingRequest): Promise<GlobalModelTrainingResponse> {
    this.startKeepalive();
    try {
      console.log('FastAPI Service: Starting global model training...');
      console.log('Request URL:', `${this.baseUrl}/train-global-model`);
      console.log('Request payload:', request);
      
      const response = await fetch(`${this.baseUrl}/train-global-model`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify(request),
      });

      console.log('Response status:', response.status);
      console.log('Response ok:', response.ok);

      if (!response.ok) {
        const errorData = await response.json();
        console.error('API Error:', errorData);
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      const result: GlobalModelTrainingResponse = await response.json();
      console.log('API Response:', result);
      return result;
    } catch (error) {
      console.error('Error training global model:', error);
      throw error;
    } finally {
      this.stopKeepalive();
    }
  }

  /**
   * Get the codebook (implementation details) for a specific algorithm with real-time context
   */
  async getModelCodebook(
    algorithm: 'random_forest' | 'gradient_boosting' | 'logistic_regression' | 'xgboost' | 'lightgbm' | 'catboost' | 'cart' | 'chaid',
    context?: {
      dataset_id?: string;
      target_variable?: string;
      selected_variables?: string[];
      k_folds?: number;
      problem_type?: 'classification' | 'regression';
    }
  ): Promise<ModelCodebookResponse> {
    try {
      console.log('FastAPI Service: Fetching model codebook...');
      console.log('Algorithm:', algorithm);
      console.log('Context:', context);
      
      // Build query parameters
      const params = new URLSearchParams();
      if (context?.dataset_id) params.append('dataset_id', context.dataset_id);
      if (context?.target_variable) params.append('target_variable', context.target_variable);
      if (context?.selected_variables && context.selected_variables.length > 0) {
        params.append('selected_variables', JSON.stringify(context.selected_variables));
      }
      if (context?.k_folds) params.append('k_folds', context.k_folds.toString());
      if (context?.problem_type) params.append('problem_type', context.problem_type);
      
      const url = `${this.baseUrl}/model-codebook/${algorithm}${params.toString() ? '?' + params.toString() : ''}`;
      console.log('Request URL:', url);
      
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('Codebook fetch failed:', errorText);
        throw new Error(`HTTP error! status: ${response.status}, body: ${errorText}`);
      }

      const result: ModelCodebookResponse = await response.json();
      console.log('Codebook result:', result);
      return result;

    } catch (error) {
      console.error('Codebook fetch error:', error);
      throw error;
    }
  }

  /**
   * Run supervised segmentation (CART/CHAID) on selected variables
   */
  async runSegmentation(request: SegmentationRequest): Promise<SegmentationResponse> {
    this.startKeepalive();
    try {
      const response = await fetch(`${this.baseUrl}/run-segmentation`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          ...this.getAuthHeaders()
        },
        body: JSON.stringify(request),
      });
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || `HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Error running segmentation:', error);
      throw error;
    } finally {
      this.stopKeepalive();
    }
  }

  /**
   * Run auto segmentation on entire dataset
   */
  async runAutoSegmentation(request: AutoSegmentationRequest): Promise<AutoSegmentationResponse> {
    this.startKeepalive();
    try {
      const response = await fetch(`${this.baseUrl}/run-auto-segmentation`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          ...this.getAuthHeaders()
        },
        body: JSON.stringify(request),
      });
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || `HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Error running auto segmentation:', error);
      throw error;
    } finally {
      this.stopKeepalive();
    }
  }

  // =============================================================================
  // Segmentation Agent API Methods (4-Mode Architecture)
  // =============================================================================

  /**
   * Run unified segmentation supporting all 4 modes
   * Uses extended timeout (3 minutes) for large datasets
   */
  async runUnifiedSegmentation(request: UnifiedSegmentationRequest): Promise<UnifiedSegmentationResponse> {
    // Extended timeout for segmentation (3 minutes) - large datasets need more time
    const SEGMENTATION_TIMEOUT_MS = 180000;
    
    try {
      console.log('🔄 Starting segmentation request:', {
        mode: request.mode,
        dataset_id: request.dataset_id,
        timeout: `${SEGMENTATION_TIMEOUT_MS / 1000}s`
      });
      
      const response = await this.fetchWithTimeout(
        `${this.baseUrl}/segmentation/run`,
        {
          method: 'POST',
          headers: { 
            'Content-Type': 'application/json',
            ...this.getAuthHeaders()
          },
          body: JSON.stringify(request),
        },
        SEGMENTATION_TIMEOUT_MS
      );
      
      if (!response.ok) {
        let errorMessage = `HTTP error! status: ${response.status}`;
        try {
          const err = await response.json();
          // Handle Pydantic validation errors (422) which have detail as array
          if (err.detail) {
            if (Array.isArray(err.detail)) {
              // Pydantic validation errors
              errorMessage = err.detail.map((e: any) => `${e.loc?.join('.')}: ${e.msg}`).join('; ');
            } else if (typeof err.detail === 'string') {
              errorMessage = err.detail;
            } else {
              errorMessage = JSON.stringify(err.detail);
            }
          }
        } catch {
          // If we can't parse JSON, use status text
          errorMessage = `Server error: ${response.status} ${response.statusText}`;
        }
        throw new Error(errorMessage);
      }
      
      const result = await response.json();
      console.log('✅ Segmentation completed:', {
        success: result.success,
        num_segments: result.num_segments,
        mode: result.mode
      });
      return result;
    } catch (error: any) {
      console.error('❌ Error running unified segmentation:', error);
      // Re-throw with more context
      if (error.message?.includes('timed out')) {
        throw error; // Already has good error message
      }
      if (error.message?.includes('Unable to connect')) {
        throw error; // Already has good error message
      }
      throw new Error(`Segmentation failed: ${error.message || 'Unknown error'}`);
    }
  }

  /**
   * Validate manual segmentation rules in real-time (C3 mode)
   */
  async validateSegmentationRules(request: UnifiedSegmentationRequest): Promise<RuleValidationResult> {
    try {
      const response = await fetch(`${this.baseUrl}/segmentation/validate-rules`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          ...this.getAuthHeaders()
        },
        body: JSON.stringify(request),
      });
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || `HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Error validating segmentation rules:', error);
      throw error;
    }
  }

  /**
   * Merge two segments and recompute statistics
   * Uses 60-second timeout for merge operations
   */
  async mergeSegments(
    datasetId: string,
    segmentAId: number,
    segmentBId: number,
    currentSegmentation: any,
    newSegmentName?: string
  ): Promise<MergeSegmentsResponse> {
    const MERGE_TIMEOUT_MS = 60000; // 1 minute timeout
    
    try {
      const request: MergeSegmentsRequest = {
        dataset_id: datasetId,
        segment_a_id: segmentAId,
        segment_b_id: segmentBId,
        current_segmentation: currentSegmentation,
        new_segment_name: newSegmentName
      };

      const response = await this.fetchWithTimeout(
        `${this.baseUrl}/segmentation/merge-segments`,
        {
          method: 'POST',
          headers: { 
            'Content-Type': 'application/json',
            ...this.getAuthHeaders()
          },
          body: JSON.stringify(request),
        },
        MERGE_TIMEOUT_MS
      );
      
      if (!response.ok) {
        let errorMessage = `HTTP error! status: ${response.status}`;
        try {
          const err = await response.json();
          if (err.detail) {
            if (Array.isArray(err.detail)) {
              errorMessage = err.detail.map((e: any) => `${e.loc?.join('.')}: ${e.msg}`).join('; ');
            } else if (typeof err.detail === 'string') {
              errorMessage = err.detail;
            } else {
              errorMessage = JSON.stringify(err.detail);
            }
          }
        } catch {
          errorMessage = `Server error: ${response.status} ${response.statusText}`;
        }
        throw new Error(errorMessage);
      }
      return await response.json();
    } catch (error: any) {
      console.error('Error merging segments:', error);
      if (error.message?.includes('timed out') || error.message?.includes('Unable to connect')) {
        throw error;
      }
      throw new Error(`Merge failed: ${error.message || 'Unknown error'}`);
    }
  }

  /**
   * Edit a segment cutoff with impact preview
   * Uses 60-second timeout for cutoff operations
   */
  async editSegmentCutoff(
    request: CutoffEditRequest
  ): Promise<CutoffEditResponse> {
    const CUTOFF_TIMEOUT_MS = 60000; // 1 minute timeout
    
    try {
      const response = await this.fetchWithTimeout(
        `${this.baseUrl}/segmentation/edit-cutoff`,
        {
          method: 'POST',
          headers: { 
            'Content-Type': 'application/json',
            ...this.getAuthHeaders()
          },
          body: JSON.stringify(request),
        },
        CUTOFF_TIMEOUT_MS
      );
      
      if (!response.ok) {
        let errorMessage = `HTTP error! status: ${response.status}`;
        try {
          const err = await response.json();
          if (err.detail) {
            if (Array.isArray(err.detail)) {
              errorMessage = err.detail.map((e: any) => `${e.loc?.join('.')}: ${e.msg}`).join('; ');
            } else if (typeof err.detail === 'string') {
              errorMessage = err.detail;
            } else {
              errorMessage = JSON.stringify(err.detail);
            }
          }
        } catch {
          errorMessage = `Server error: ${response.status} ${response.statusText}`;
        }
        throw new Error(errorMessage);
      }
      return await response.json();
    } catch (error: any) {
      console.error('Error editing cutoff:', error);
      if (error.message?.includes('timed out') || error.message?.includes('Unable to connect')) {
        throw error;
      }
      throw new Error(`Cutoff edit failed: ${error.message || 'Unknown error'}`);
    }
  }

  /**
   * Save segmentation scheme to dataset (Add to Data)
   */
  async addSegmentationToData(request: AddToDataRequest): Promise<AddToDataResponse> {
    try {
      const response = await fetch(`${this.baseUrl}/segmentation/add-to-data`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          ...this.getAuthHeaders()
        },
        body: JSON.stringify(request),
      });
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || `HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Error adding segmentation to data:', error);
      throw error;
    }
  }

  /**
   * Generate LLM narrative for segmentation results
   */
  async generateSegmentationNarrative(
    narrativeType: 'merge' | 'recommendation' | 'variable',
    contextData: Record<string, any>
  ): Promise<{ success: boolean; narrative_type: string; narrative: string }> {
    this.startKeepalive();
    try {
      const formData = new FormData();
      formData.append('narrative_type', narrativeType);
      formData.append('context_data', JSON.stringify(contextData));

      const response = await fetch(`${this.baseUrl}/segmentation/generate-narrative`, {
        method: 'POST',
        headers: this.getAuthHeaders(),
        body: formData,
      });
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || `HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Error generating narrative:', error);
      throw error;
    }
  }

  /**
   * Get all saved segmentation schemes for a dataset
   */
  async getSegmentationSchemes(datasetId: string): Promise<SchemeRegistryResponse> {
    try {
      const response = await fetch(`${this.baseUrl}/segmentation/schemes/${datasetId}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
      });
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || `HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Error getting segmentation schemes:', error);
      throw error;
    }
  }

  /**
   * Full stored audit metadata for one scheme (registry View details).
   */
  async getSegmentationSchemeDetail(
    datasetId: string,
    schemeId: number
  ): Promise<SegmentationSchemeDetailResponse> {
    try {
      const response = await fetch(
        `${this.baseUrl}/segmentation/schemes/${encodeURIComponent(datasetId)}/${schemeId}`,
        {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
            ...this.getAuthHeaders(),
          },
        }
      );
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || `HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Error getting segmentation scheme detail:', error);
      throw error;
    }
  }

  /**
   * Persisted segmentation audit log (plan Section 15).
   */
  async getSegmentationAuditLog(datasetId: string): Promise<{
    success: boolean;
    dataset_id: string;
    events: Array<Record<string, unknown>>;
    count: number;
  }> {
    try {
      const response = await fetch(
        `${this.baseUrl}/segmentation/audit-log/${encodeURIComponent(datasetId)}`,
        {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
            ...this.getAuthHeaders(),
          },
        }
      );
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || `HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Error getting segmentation audit log:', error);
      throw error;
    } finally {
      this.stopKeepalive();
    }
  }

  /**
   * Segmentation Insight Pins for the Modeler's Notebook (plan Section 12.2).
   */
  async getSegmentationInsightPins(datasetId: string): Promise<{
    success: boolean;
    dataset_id: string;
    pins: Array<Record<string, unknown>>;
    count: number;
  }> {
    this.startKeepalive();
    try {
      const response = await fetch(
        `${this.baseUrl}/segmentation/insight-pins/${encodeURIComponent(datasetId)}`,
        {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
            ...this.getAuthHeaders(),
          },
        }
      );
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || `HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Error getting segmentation insight pins:', error);
      throw error;
    }
  }

  /**
   * Get top 10 variables by IV per segment
   */
  async getTopVariablesBySegment(
    datasetId: string, 
    targetVariable?: string
  ): Promise<{ success: boolean; variables: string[]; overall_iv: Record<string, number>; segment_iv: Record<string, Record<string, number>> }> {
    try {
      const params = new URLSearchParams();
      if (targetVariable) params.append('target_variable', targetVariable);
      
      const response = await fetch(`${this.baseUrl}/segmentation/top-variables/${datasetId}?${params}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
      });
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || `HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Error getting top variables by segment:', error);
      throw error;
    }
  }

  /**
   * Get dataset preview for global model training
   */
  async getDatasetPreview(datasetId: string): Promise<DatasetPreviewResponse> {
    try {
      const response = await fetch(`${this.baseUrl}/dataset-preview/${datasetId}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      const result: DatasetPreviewResponse = await response.json();
      return result;
    } catch (error) {
      console.error('Error getting dataset preview:', error);
      throw error;
    } finally {
      this.stopKeepalive();
    }
  }

  /**
   * Get segmented dataset preview with segment column
   */
  async getSegmentedDatasetPreview(datasetId: string): Promise<DatasetPreviewResponse> {
    try {
      const response = await fetch(`${this.baseUrl}/segmented-dataset-preview/${datasetId}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      const result: DatasetPreviewResponse = await response.json();
      return result;
    } catch (error) {
      console.error('Error getting segmented dataset preview:', error);
      throw error;
    }
  }

  /**
   * Download processed dataset from MessageState as CSV
   */
  async downloadProcessedDataset(datasetId: string): Promise<void> {
    try {
      console.log('Downloading processed dataset:', datasetId);
      
      const response = await fetch(`${this.baseUrl}/datasets/${datasetId}/download-processed`, {
        headers: this.getAuthHeaders()
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Download failed: ${response.status} - ${errorData.detail || response.statusText}`);
      }

      // Create blob and download
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      
      // Extract filename from Content-Disposition header
      const contentDisposition = response.headers.get('content-disposition');
      const filename = contentDisposition 
        ? contentDisposition.split('filename=')[1]?.replace(/"/g, '') 
        : `processed_dataset_${datasetId}.csv`;
      
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      console.log('Processed dataset downloaded successfully');
    } catch (error) {
      console.error('Processed dataset download failed:', error);
      throw error;
    }
  }

  async downloadColumnStats(datasetId: string): Promise<void> {
    try {
      console.log('📊 Downloading column stats table:', datasetId);
      
      const response = await fetch(`${this.baseUrl}/datasets/${datasetId}/download-column-stats`, {
        headers: this.getAuthHeaders()
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Download failed: ${response.status} - ${errorData.detail || response.statusText}`);
      }

      // Create blob and download
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      
      // Extract filename from Content-Disposition header
      const contentDisposition = response.headers.get('content-disposition');
      const filename = contentDisposition 
        ? contentDisposition.split('filename=')[1]?.replace(/"/g, '') 
        : `column_stats_${datasetId}.csv`;
      
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      console.log('✅ Column Stats table downloaded successfully');
    } catch (error) {
      console.error('❌ Column Stats download error:', error);
      throw error;
    }
  }

  async compareColumnStats(datasetId: string, scope: string = 'entire'): Promise<any> {
    try {
      console.log('🔍 Fetching column stats comparison:', datasetId, 'scope:', scope);
      
      const response = await fetch(`${this.baseUrl}/datasets/${datasetId}/compare-column-stats?scope=${scope}`, {
        headers: this.getAuthHeaders()
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Comparison failed: ${response.status} - ${errorData.detail || response.statusText}`);
      }

      const comparisonData = await response.json();
      console.log('✅ Column Stats comparison retrieved:', comparisonData);
      
      return comparisonData;
    } catch (error) {
      console.error('❌ Column Stats comparison error:', error);
      throw error;
    }
  }

  /**
   * Update custom treatments for a dataset
   */
  async updateCustomTreatments(request: { dataset_id: string; custom_treatments: Record<string, string> }): Promise<{ data: any; status: number; statusText: string }> {
    try {
      console.log('📤 Updating custom treatments for dataset:', request.dataset_id);
      
      const response = await fetch(`${this.baseUrl}/update-custom-treatments`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify(request)
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Custom treatments update failed: ${response.status} - ${errorData.detail || response.statusText}`);
      }

      const data = await response.json();
      console.log('✅ Custom treatments updated successfully');
      
      return {
        data,
        status: response.status,
        statusText: response.statusText
      };
    } catch (error) {
      console.error('❌ Custom treatments update failed:', error);
      throw error;
    }
  }

  /**
   * P1.1: Classify dataset type using an already-uploaded dataset_id.
   * Avoids re-uploading the file by referencing the dataset that the backend
   * already has in memory / on Parquet sidecar. Use this whenever you know
   * the dataset_id (i.e. after /upload completed).
   */
  async classifyDatasetTypeById(request: {
    dataset_id: string;
    target_variable: string;
    target_variable_type: string;
  }): Promise<DatasetTypeClassificationResponse> {
    this.startKeepalive();
    try {
      console.log('🔍 Enqueuing dataset-type classification by dataset_id:', request.dataset_id);

      const postResp = await this.fetchWithTimeout(
        `${this.baseUrl}/dataset-type-classification-by-id`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...this.getAuthHeaders(),
          },
          body: JSON.stringify(request),
        },
        // No file upload; a small JSON body. Plenty of headroom.
        60_000,
      );

      if (!postResp.ok) {
        const err = await postResp.json().catch(() => ({}));
        throw new Error(
          `Dataset type classification by-id failed: ${postResp.status} - ${err.detail || postResp.statusText}`,
        );
      }

      const { job_id } = await postResp.json();
      console.log('🤖 Classification job queued (by-id):', job_id);

      return await this._pollClassificationJob(job_id);
    } catch (error) {
      console.error('❌ Dataset type classification (by-id) failed:', error);
      throw error;
    } finally {
      this.stopKeepalive();
    }
  }

  /**
   * Shared poller for the dataset-type-classification job queue.
   * Polls every 3 s up to ~3 min (was 90 s; raised for very large datasets
   * where the LLM step itself can take longer). Returns the completed payload
   * or throws on failure / timeout.
   */
  private async _pollClassificationJob(job_id: string): Promise<DatasetTypeClassificationResponse> {
    const pollUrl = `${this.baseUrl}/dataset-type-classification/status/${job_id}`;
    const maxAttempts = 60; // 60 * 3 s = 180 s
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      await new Promise(r => setTimeout(r, 3000));
      let pollResp: Response;
      try {
        pollResp = await fetch(pollUrl, { headers: this.getAuthHeaders() });
      } catch {
        continue;
      }
      if (!pollResp.ok) continue;
      const data = await pollResp.json();
      if (data.status === 'completed') {
        console.log('✅ Dataset type classification completed:', data.dataset_type);
        return data as DatasetTypeClassificationResponse;
      }
      if (data.status === 'failed') {
        throw new Error(`Classification job failed: ${data.error || 'unknown error'}`);
      }
      console.log(`⏳ Classification in progress… (attempt ${attempt + 1}/${maxAttempts})`);
    }
    throw new Error('Dataset type classification timed out after 180 seconds');
  }

  /**
   * Start async feature transformation job (non-blocking)
   */
  async startFeatureTransformationJob(
    request: FeatureTransformationRequest
  ): Promise<FeatureTransformationJobStartResponse> {
    this.startKeepalive();
    try {
      console.log('🔧 Starting feature transformation job for dataset:', request.dataset_id);

      const formData = new FormData();
      formData.append('dataset_id', request.dataset_id);
      formData.append('plan_json', request.plan_json);

      if (request.target_variable) {
        formData.append('target_variable', request.target_variable);
      }

      if (request.woe_bins) {
        formData.append('woe_bins', request.woe_bins.toString());
      }

      if (request.selected_segments && request.selected_segments.trim() !== '') {
        formData.append('selected_segments', request.selected_segments);
      }

      if (request.use_split !== undefined) {
        formData.append('use_split', request.use_split.toString());
      }

      const response = await fetch(`${this.baseUrl}/feature-transformation/start`, {
        method: 'POST',
        headers: this.getAuthHeaders(),
        body: formData
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Start feature transformation job failed: ${response.status} - ${errorData.detail || errorData.message || response.statusText}`);
      }

      const result: FeatureTransformationJobStartResponse = await response.json();
      return result;
    } catch (error) {
      console.error('❌ Start feature transformation job failed:', error);
      throw error;
    } finally {
      this.stopKeepalive();
    }
  }

  /**
   * Get async feature transformation job status
   */
  async getFeatureTransformationJobStatus(
    jobId: string
  ): Promise<FeatureTransformationJobStatusResponse> {
    try {
      const response = await fetch(`${this.baseUrl}/feature-transformation/status/${jobId}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Feature transformation job status failed: ${response.status} - ${errorData.detail || errorData.message || response.statusText}`);
      }

      const result: FeatureTransformationJobStatusResponse = await response.json();
      return result;
    } catch (error) {
      console.error('❌ Feature transformation job status failed:', error);
      throw error;
    }
  }

  /**
   * Trigger automated model training
   */
  async autoTrainModel(request: AutoTrainRequest): Promise<AutoTrainResponse> {
    this.startKeepalive();
    try {
      console.log('🚀 Starting auto training for dataset:', request.dataset_id);
      
      const response = await fetch(`${this.baseUrl}/auto-train-model`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify(request)
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const errorMessage = errorData.detail || errorData.message || `HTTP error! status: ${response.status}`;
        throw new Error(errorMessage);
      }

      const result: AutoTrainResponse = await response.json();
      console.log('✅ Auto training completed:', result.model_id);
      
      return result;
    } catch (error) {
      console.error('❌ Auto training failed:', error);
      throw error;
    } finally {
      this.stopKeepalive();
    }
  }

  /**
   * Get latest dataframe columns after any transformations
   */
  async getLatestColumns(datasetId: string): Promise<LatestColumnsResponse> {
    try {
      console.log('📊 Fetching latest columns for dataset:', datasetId);
      
      const response = await fetch(`${this.baseUrl}/datasets/${datasetId}/latest-columns`, {
        headers: this.getAuthHeaders()
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Latest columns fetch failed: ${response.status} - ${errorData.detail || response.statusText}`);
      }

      const result: LatestColumnsResponse = await response.json();
      console.log('✅ Latest columns retrieved successfully:', result.columns.length, 'columns');
      
      return result;
    } catch (error) {
      console.error('❌ Latest columns fetch failed:', error);
      throw error;
    }
  }

  /**
   * Export a trained model with artifacts
   */
  async exportModel(request: { model_id: string; include_artifacts?: boolean }): Promise<{
    success: boolean;
    message: string;
    files?: Array<{
      filename: string;
      content: string;
      encoding?: string;
    }>;
  }> {
    try {
      console.log('📤 Exporting model:', request.model_id);

      const response = await fetch(`${this.baseUrl}/export-model/${request.model_id}?include_artifacts=${request.include_artifacts || false}`, {
        headers: this.getAuthHeaders()
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Export failed: ${response.status} - ${errorData.detail || response.statusText}`);
      }

      const result = await response.json();
      console.log('Model exported successfully:', result.files?.length || 0, 'files');
      return result;
    } catch (error) {
      console.error('Model export failed:', error);
      throw error;
    }
  }

  /**
   * Train multiple specified algorithms using selected (or all) variables
   */
  async trainMultipleModels(request: TrainMultipleModelsRequest): Promise<TrainMultipleModelsResponse> {
    try {
      // Step 1: Start the training job
      const startResponse = await fetch(`${this.baseUrl}/train-multiple-models`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify(request)
      });

      if (!startResponse.ok) {
        let bodyText = '';
        try { bodyText = await startResponse.text(); } catch (_) { bodyText = ''; }
        let msg = '';
        try {
          const j = bodyText ? JSON.parse(bodyText) : null;
          msg = (j && (j.detail || j.message)) || bodyText;
        } catch (_) {
          msg = bodyText || startResponse.statusText;
        }
        throw new Error(msg || `HTTP error! status: ${startResponse.status}`);
      }

      const startData = await startResponse.json();
      
      if (!startData.success || !startData.job_id) {
        throw new Error('Failed to start training job');
      }

      const jobId = startData.job_id;
      this.manualTrainingJobId = jobId;
      this.manualTrainingCancelRequested = false;
      console.log('✅ Manual training job started:', jobId);

      // Step 2: Poll for status.
      // Keepalive is started HERE (inside the Promise) so it stays alive for the
      // entire polling window, not just until the outer async function returns.
      return new Promise((resolve, reject) => {
        this.startKeepalive();

        const _done = (fn: () => void) => {
          clearInterval(pollInterval);
          this.manualTrainingPollHandle = null;
          this.manualTrainingJobId = null;
          this.stopKeepalive();
          fn();
        };

        const pollInterval = setInterval(async () => {
          try {
            // If user requested cancel, stop polling and reject with a special error
            if (this.manualTrainingCancelRequested) {
              _done(() => reject(new Error('cancelled')));
              return;
            }

            const statusResponse = await fetch(`${this.baseUrl}/train-multiple-models/status/${jobId}`, {
              method: 'GET',
              headers: {
                'Content-Type': 'application/json',
                ...this.getAuthHeaders(),
              }
            });

            if (!statusResponse.ok) {
              _done(() => reject(new Error(`Failed to get job status: ${statusResponse.status}`)));
              return;
            }

            const statusData = await statusResponse.json();
            const status = statusData.status;

            if (status === 'completed') {
              console.log('✅ Manual training completed');
              _done(() => resolve(statusData.results as TrainMultipleModelsResponse));
            } else if (status === 'failed') {
              _done(() => reject(new Error(statusData.error || 'Training failed')));
            }
            // If pending or running, continue polling
          } catch (error) {
            _done(() => reject(error));
          }
        }, 2000) as unknown as number; // Poll every 2 seconds

        this.manualTrainingPollHandle = pollInterval;
      });
    } catch (error) {
      console.error('❌ Multi-model training failed:', error);
      throw error;
    }
  }

  /**
   * Run §7.2 LR backward elimination on demand (same preprocess/split as manual training).
   */
  async runLrBackwardElimination(request: {
    dataset_id: string;
    target_column: string;
    independent_variables: string[];
    locked_variables?: string[];
    weight_variable?: string;
    vif_threshold?: number;
    p_value_threshold?: number;
    segment_id?: string | number;
    segment_column?: string;
  }): Promise<{ success: boolean; lr_backward_elimination: Record<string, unknown> }> {
    const response = await fetch(`${this.baseUrl}/model-training/lr-backward-elimination`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
      },
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      let bodyText = '';
      try {
        bodyText = await response.text();
      } catch (_) {
        bodyText = '';
      }
      let msg = '';
      try {
        const j = bodyText ? JSON.parse(bodyText) : null;
        msg = (j && (j.detail || j.message)) || bodyText;
      } catch (_) {
        msg = bodyText || response.statusText;
      }
      throw new Error(msg || `HTTP error! status: ${response.status}`);
    }
    return response.json();
  }

  /**
   * Run segment-specific model training
   */
  async runSegmentTraining(request: TrainMultipleModelsRequest): Promise<TrainMultipleModelsResponse> {
    try {
      // Step 1: Start the training job
      const startResponse = await fetch(`${this.baseUrl}/segment-training/run`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify(request)
      });

      if (!startResponse.ok) {
        let bodyText = '';
        try { bodyText = await startResponse.text(); } catch (_) { bodyText = ''; }
        let msg = '';
        try {
          const j = bodyText ? JSON.parse(bodyText) : null;
          msg = (j && (j.detail || j.message)) || bodyText;
        } catch (_) {
          msg = bodyText || startResponse.statusText;
        }
        throw new Error(msg || `HTTP error! status: ${startResponse.status}`);
      }

      const startData = await startResponse.json();
      
      if (!startData.success || !startData.job_id) {
        throw new Error('Failed to start segment training job');
      }

      const jobId = startData.job_id;
      this.segmentManualTrainingJobId = jobId;
      this.segmentManualTrainingCancelRequested = false;
      console.log('✅ Segment manual training job started:', jobId);

      // Step 2: Poll for status.
      // Keepalive is started HERE (inside the Promise) so it stays alive for the
      // entire polling window, not just until the outer async function returns.
      return new Promise((resolve, reject) => {
        this.startKeepalive();

        const _done = (fn: () => void) => {
          clearInterval(pollInterval);
          this.segmentManualTrainingPollHandle = null;
          this.segmentManualTrainingJobId = null;
          this.stopKeepalive();
          fn();
        };

        const pollInterval = setInterval(async () => {
          try {
            if (this.segmentManualTrainingCancelRequested) {
              _done(() => reject(new Error('cancelled')));
              return;
            }

            const statusResponse = await fetch(`${this.baseUrl}/segment-training/status/${jobId}`, {
              method: 'GET',
              headers: {
                'Content-Type': 'application/json',
                ...this.getAuthHeaders(),
              }
            });

            if (!statusResponse.ok) {
              _done(() => reject(new Error(`Failed to get job status: ${statusResponse.status}`)));
              return;
            }

            const statusData = await statusResponse.json();
            const status = statusData.status;

            if (status === 'completed') {
              console.log('✅ Segment manual training completed');
              // If model_id is present, fetch full results from unified-results endpoint (compressed)
              if (statusData.model_id) {
                try {
                  const fullResults = await this.getUnifiedSegmentResults(statusData.model_id);
                  _done(() => resolve(fullResults as TrainMultipleModelsResponse));
                } catch (error) {
                  console.error('❌ Failed to fetch full segment results:', error);
                  _done(() => resolve(statusData.results as TrainMultipleModelsResponse));
                }
              } else {
                _done(() => resolve(statusData.results as TrainMultipleModelsResponse));
              }
            } else if (status === 'failed') {
              _done(() => reject(new Error(statusData.error || 'Segment training failed')));
            }
            // If pending or running, continue polling
          } catch (error) {
            _done(() => reject(error));
          }
        }, 2000) as unknown as number; // Poll every 2 seconds

        this.segmentManualTrainingPollHandle = pollInterval;
      });
    } catch (error) {
      console.error('❌ Segment training failed:', error);
      throw error;
    }
  }

  /**
   * Get unified segment training results for dashboard display
   */
  async getUnifiedSegmentResults(modelId: string): Promise<any> {
    try {
      // Primary route
      let response = await fetch(`${this.baseUrl}/segment-training/${modelId}/unified-results`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        }
      });

      // Fallback 1: nested under /chat
      if (!response.ok && response.status === 404) {
        try {
          response = await fetch(`${this.baseUrl}/chat/segment-training/${modelId}/unified-results`, {
            method: 'GET',
            headers: {
              'Content-Type': 'application/json',
              ...this.getAuthHeaders(),
            }
          });
        } catch (_) { /* noop */ }
      }

      // Fallback 2: explicit localhost
      if (!response.ok && response.status === 404) {
        try {
          const localhostBase = `${this.baseUrl.startsWith('http') ? '' : 'http://localhost:8000'}${this.baseUrl.startsWith('/api') ? '' : ''}`;
          response = await fetch(`${localhostBase || 'http://localhost:8000'}/api/v1/chat/segment-training/${modelId}/unified-results`, {
            method: 'GET',
            headers: {
              'Content-Type': 'application/json',
              ...this.getAuthHeaders(),
            }
          });
        } catch (_) { /* noop */ }
      }

      if (!response.ok) {
        let bodyText = '';
        try { bodyText = await response.text(); } catch (_) { bodyText = ''; }
        let msg = '';
        try {
          const j = bodyText ? JSON.parse(bodyText) : null;
          msg = (j && (j.detail || j.message)) || bodyText;
        } catch (_) {
          msg = bodyText || response.statusText;
        }
        if (!msg || msg.trim() === '') {
          msg = `HTTP ${response.status} ${response.statusText}`;
        }
        throw new Error(msg);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.error('❌ Get unified segment results failed:', error);
      throw error;
    }
  }

  /**
   * Start auto training analysis as background job (async, prevents timeout)
   * Returns job_id immediately
   */
  async startAnalyzeDatasetForAutoTraining(request: {
    dataset_id: string;
    target_column: string;
  }): Promise<{ success: boolean; job_id: string; status: string; message?: string }> {
    try {
      const response = await this.fetchWithAutoRefresh(`${this.baseUrl}/auto-training/analyze/start`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(this.getAuthHeaders() as Record<string, string>),
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const detail = errorData?.detail;
        const msg =
          typeof detail === 'string'
            ? detail
            : detail != null
              ? JSON.stringify(detail)
              : `HTTP error! status: ${response.status}`;
        throw new Error(msg);
      }

      const result = await response.json();
      return result;
    } catch (error) {
      console.error('Error starting auto training analysis:', error);
      throw error;
    }
  }

  /**
   * Get status of auto training analysis job
   */
  async getAutoTrainingAnalyzeStatus(jobId: string): Promise<{
    job_id: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
    progress?: number;
    result?: any;
    error?: string;
  }> {
    try {
      const response = await this.fetchWithAutoRefresh(
        `${this.baseUrl}/auto-training/analyze/status/${encodeURIComponent(jobId)}`,
        {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
            ...(this.getAuthHeaders() as Record<string, string>),
          },
        },
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const detail = errorData?.detail;
        const msg =
          typeof detail === 'string'
            ? detail
            : detail != null
              ? JSON.stringify(detail)
              : `HTTP error! status: ${response.status}`;
        throw new Error(msg);
      }

      const result = await response.json();
      return result;
    } catch (error) {
      console.error('Error getting auto training analysis status:', error);
      throw error;
    }
  }

  /**
   * Analyze dataset for auto training (synchronous, may timeout in Azure)
   * @deprecated Use startAnalyzeDatasetForAutoTraining + getAutoTrainingAnalyzeStatus for production
   */
  async analyzeDatasetForAutoTraining(request: { dataset_id: string; target_column: string }): Promise<any> {
    this.startKeepalive();
    try {
      const response = await fetch(`${this.baseUrl}/auto-training/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify(request)
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.error('❌ Auto training analysis failed:', error);
      throw error;
    } finally {
      this.stopKeepalive();
    }
  }

  /**
   * Auto select variables for training
   */
  async autoSelectVariables(request: { dataset_id: string; target_column: string; variable_analysis: any; problem_type: string }): Promise<any> {
    this.startKeepalive();
    try {
      const response = await fetch(`${this.baseUrl}/auto-training/select-variables`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify(request)
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.error('❌ Auto variable selection failed:', error);
      throw error;
    } finally {
      this.stopKeepalive();
    }
  }

  /**
   * Step 1 lock-variable processing (shared auto/manual)
   */
  async lockTrainingVariables(request: {
    dataset_id: string;
    target_column: string;
    mode: 'auto' | 'manual';
    selected_variables?: string[];
    independent_variables?: string[];
    locked_variables: string[];
    variable_analysis?: any;
  }): Promise<any> {
    this.startKeepalive();
    try {
      const response = await fetch(`${this.baseUrl}/training/lock-variables`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify(request)
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('❌ Variable locking failed:', error);
      throw error;
    } finally {
      this.stopKeepalive();
    }
  }

  /**
   * Auto select algorithms for training
   */
  async autoSelectAlgorithms(request: { dataset_id: string; problem_type: string; dataset_size: number; num_features: number; feature_types?: { numerical: number; categorical: number } }): Promise<any> {
    this.startKeepalive();
    try {
      const response = await fetch(`${this.baseUrl}/auto-training/select-algorithms`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify(request)
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.error('❌ Auto algorithm selection failed:', error);
      throw error;
    } finally {
      this.stopKeepalive();
    }
  }

  /**
   * Read auto-training SSE until a terminal status or transport failure (then caller may fall back to polling).
   * Uses fetch + ReadableStream so Authorization headers work (native EventSource cannot).
   */
  private async _readAutoTrainingSseToTerminal(
    jobId: string,
    signal: AbortSignal
  ): Promise<Record<string, unknown> | null> {
    let response: Response;
    try {
      response = await fetch(`${this.baseUrl}/auto-training/stream/${jobId}`, {
        method: 'GET',
        headers: {
          Accept: 'text/event-stream',
          ...this.getAuthHeaders(),
        },
        signal,
      });
    } catch (err) {
      if (signal.aborted) throw err;
      console.warn('⚠️ Auto-training SSE connect failed, will fall back to polling:', err);
      return null;
    }
    if (response.status === 401) {
      try {
        await handleUnauthorizedResponse(response, { allowRefresh: true, skipAuth: false });
      } catch (e: unknown) {
        if ((e as { message?: string })?.message === RETRY_AFTER_REFRESH) {
          try {
            response = await fetch(`${this.baseUrl}/auto-training/stream/${jobId}`, {
              method: 'GET',
              headers: {
                Accept: 'text/event-stream',
                ...this.getAuthHeaders(),
              },
              signal,
            });
          } catch (retryErr) {
            if (signal.aborted) throw retryErr;
            console.warn('⚠️ Auto-training SSE retry connect failed, will fall back to polling:', retryErr);
            return null;
          }
          if (!response.ok) {
            console.warn(`⚠️ Auto-training SSE HTTP ${response.status} after refresh, falling back to polling`);
            return null;
          }
        } else {
          throw e;
        }
      }
    } else if (!response.ok) {
      console.warn(`⚠️ Auto-training SSE HTTP ${response.status}, falling back to polling`);
      return null;
    }
    const reader = response.body?.getReader();
    if (!reader) return null;

    const decoder = new TextDecoder();
    let buffer = '';
    let lastPayload: Record<string, unknown> | null = null;

    try {
      while (true) {
        let readResult: ReadableStreamReadResult<Uint8Array>;
        try {
          readResult = await reader.read();
        } catch (err) {
          if (signal.aborted) throw err;
          console.warn('⚠️ Auto-training SSE read error, falling back to polling:', err);
          return null;
        }
        const { done, value } = readResult;
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        let sep: number;
        while ((sep = buffer.indexOf('\n\n')) !== -1) {
          const rawEvent = buffer.slice(0, sep);
          buffer = buffer.slice(sep + 2);
          const lines = rawEvent.split('\n');
          const dataParts: string[] = [];
          for (const line of lines) {
            if (line.startsWith(':')) continue;
            if (line.startsWith('data:')) {
              dataParts.push(line.slice(5).trimStart());
            }
          }
          if (dataParts.length === 0) continue;
          const joined = dataParts.join('\n');
          try {
            lastPayload = JSON.parse(joined) as Record<string, unknown>;
          } catch {
            continue;
          }
          const st = lastPayload['status'];
          if (st === 'completed' || st === 'failed') {
            try {
              await reader.cancel();
            } catch {
              /* ignore */
            }
            return lastPayload;
          }
        }
      }
    } finally {
      try {
        reader.releaseLock();
      } catch {
        /* ignore */
      }
    }

    return lastPayload;
  }

  /**
   * Run complete auto training pipeline
   */
  async runCompleteAutoTraining(request: { dataset_id: string; target_column: string; selected_variables?: string[]; locked_variables?: string[]; selection_mode?: string; selected_algorithms?: string[] }): Promise<any> {
    try {
      // Step 1: Start the training job with retry logic (10 attempts, exponential backoff)
      let startResponse;
      let startData;
      const MAX_START_RETRIES = 10;

      for (let attempt = 1; attempt <= MAX_START_RETRIES; attempt++) {
        try {
          startResponse = await this.fetchWithAutoRefresh(`${this.baseUrl}/auto-training/run`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              ...(this.getAuthHeaders() as Record<string, string>),
            },
            body: JSON.stringify(request)
          });

          if (!startResponse.ok) {
            const errorText = await startResponse.text();
            throw new Error(`HTTP error! status: ${startResponse.status}, message: ${errorText}`);
          }

          startData = await startResponse.json();

          if (!startData.success || !startData.job_id) {
            throw new Error('Failed to start training job: ' + (startData.message || 'Unknown error'));
          }

          // Success - exit retry loop
          break;
        } catch (error) {
          // Only retry on *network transport* failures. Retrying HTTP 4xx/5xx can start
          // duplicate training jobs on Azure if the server accepted the first POST but
          // the client never received the response (timeouts / 502 / connection reset).
          const errMsg = error instanceof Error ? error.message : String(error);
          const isNetworkTransport =
            (error instanceof TypeError &&
              (errMsg.includes('fetch') ||
                errMsg.includes('network') ||
                errMsg.includes('Failed to fetch'))) ||
            /Load failed|NetworkError|ECONNRESET|ECONNREFUSED|ETIMEDOUT/i.test(errMsg);

          if (!isNetworkTransport) {
            throw error;
          }

          if (attempt < MAX_START_RETRIES) {
            const delayMs = Math.min(2000 * attempt, 30_000); // 2s, 4s, 6s … capped at 30s
            console.warn(`⚠️ Start-training attempt ${attempt}/${MAX_START_RETRIES} failed (network), retrying in ${delayMs}ms…`, error);
            await new Promise(resolve => setTimeout(resolve, delayMs));
          } else {
            throw new Error('Network error: Unable to connect to server. Please check:\n1. Backend server is running\n2. CORS is configured correctly\n3. Network connection is stable');
          }
        }
      }

      const jobId = startData.job_id;
      this.autoTrainingJobId = jobId;
      this.autoTrainingCancelRequested = false;
      console.log('✅ Training job started:', jobId);

      // Step 2: Prefer SSE (one long-lived connection, fewer HTTP round-trips); fall back to polling.
      return new Promise((resolve, reject) => {
        this.startKeepalive();
        const ac = new AbortController();
        this.autoTrainingStreamAbort = ac;

        const cleanup = () => {
          if (this.autoTrainingPollHandle !== null) {
            clearInterval(this.autoTrainingPollHandle);
            this.autoTrainingPollHandle = null;
          }
          this.autoTrainingStreamAbort = null;
          this.autoTrainingJobId = null;
          this.stopKeepalive();
        };

        const handleTerminal = (statusData: { status?: string; results?: unknown; model_id?: string; error?: string }) => {
          const status = statusData.status;
          if (status === 'completed') {
            console.log('✅ Auto training completed');
            let r = statusData.results;
            if (
              (!r || (typeof r === 'object' && Object.keys(r as object).length === 0)) &&
              statusData.model_id
            ) {
              r = { model_id: statusData.model_id, success: true } as Record<string, unknown>;
            }
            cleanup();
            resolve({ success: true, results: r || {} });
            return true;
          }
          if (status === 'failed') {
            cleanup();
            reject(new Error((statusData.error as string) || 'Training failed'));
            return true;
          }
          return false;
        };

        (async () => {
          try {
            if (this.autoTrainingCancelRequested) {
              cleanup();
              reject(new Error('cancelled'));
              return;
            }

            const ssePayload = await this._readAutoTrainingSseToTerminal(jobId, ac.signal);
            if (
              ssePayload &&
              (ssePayload['status'] === 'completed' || ssePayload['status'] === 'failed') &&
              handleTerminal(ssePayload as { status?: string; results?: unknown; model_id?: string; error?: string })
            ) {
              return;
            }

            console.warn('⚠️ Auto-training SSE did not finish with a terminal event; using status polling');
          } catch (err) {
            if (ac.signal.aborted || this.autoTrainingCancelRequested) {
              cleanup();
              reject(new Error('cancelled'));
              return;
            }
            console.warn('⚠️ Auto-training SSE error; using status polling:', err);
          }

          this.autoTrainingPollHandle = setInterval(async () => {
            try {
              if (this.autoTrainingCancelRequested) {
                cleanup();
                reject(new Error('cancelled'));
                return;
              }

              const statusResponse = await this.fetchWithAutoRefresh(`${this.baseUrl}/auto-training/status/${jobId}`, {
                method: 'GET',
                headers: {
                  'Content-Type': 'application/json',
                  ...(this.getAuthHeaders() as Record<string, string>),
                },
              });

              if (!statusResponse.ok) {
                if (statusResponse.status === 404) {
                  console.warn('⚠️ Job not found in status endpoint, training may still be running in background');
                } else {
                  console.warn(`⚠️ Status check failed with status ${statusResponse.status}, continuing to poll…`);
                }
                return;
              }

              const statusData = await statusResponse.json();
              const status = statusData.status;

              if (status === 'completed') {
                if (
                  handleTerminal(
                    statusData as { status?: string; results?: unknown; model_id?: string; error?: string }
                  )
                ) {
                  return;
                }
              } else if (status === 'failed') {
                if (
                  handleTerminal(
                    statusData as { status?: string; results?: unknown; model_id?: string; error?: string }
                  )
                ) {
                  return;
                }
              }
            } catch (error) {
              console.warn('⚠️ Polling error (will retry):', error);
            }
          }, 2000) as unknown as number;
        })();
      });
    } catch (error) {
      console.error('❌ Complete auto training failed:', error);
      throw error;
    }
  }

  /**
   * Detect segments in dataset
   */
  async detectSegments(request: { dataset_id: string; segment_column?: string }): Promise<any> {
    this.startKeepalive();
    try {
      const response = await fetch(`${this.baseUrl}/detect-segments`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify(request)
      });

      if (!response.ok) {
        // Check if response is HTML (error page)
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('text/html')) {
          const text = await response.text();
          console.error('Server returned HTML error page:', text.substring(0, 500));
          throw new Error(`Server error (${response.status}): Received HTML response instead of JSON`);
        }

        // Try to parse as JSON
        let bodyText = '';
        try {
          bodyText = await response.text();
          const j = bodyText ? JSON.parse(bodyText) : null;
          const msg = (j && (j.detail || j.message)) || bodyText || response.statusText;
          throw new Error(msg);
        } catch (parseError) {
          // If JSON parsing failed, use the text directly
          throw new Error(bodyText || response.statusText || `HTTP error! status: ${response.status}`);
        }
      }

      // Check content type before parsing
      const contentType = response.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
        const text = await response.text();
        console.error('Non-JSON response received:', text.substring(0, 500));
        throw new Error(`Server returned HTML instead of JSON. Content-Type: ${contentType}`);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.error('❌ Segment detection failed:', error);
      throw error;
    } finally {
      this.stopKeepalive();
    }
  }

  /**
   * Run segment-wise auto training (combines auto training with segment-specific models)
   */
  async runSegmentAutoTraining(request: { 
    dataset_id: string; 
    target_column: string; 
    selected_variables?: string[]; 
    locked_variables?: string[];
    selection_mode?: string;
    selected_algorithms?: string[];
  }): Promise<any> {
    try {
      console.log('🚀 Starting segment auto training for dataset:', request.dataset_id);
      
      // Step 1: Start the training job
      const startResponse = await fetch(`${this.baseUrl}/segment-auto-training/run`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify(request)
      });

      if (!startResponse.ok) {
        let bodyText = '';
        try { bodyText = await startResponse.text(); } catch (_) { bodyText = ''; }
        let msg = '';
        try {
          const j = bodyText ? JSON.parse(bodyText) : null;
          msg = (j && (j.detail || j.message)) || bodyText;
        } catch (_) {
          msg = bodyText || startResponse.statusText;
        }
        throw new Error(msg);
      }

      const startData = await startResponse.json();
      
      if (!startData.success || !startData.job_id) {
        throw new Error('Failed to start segment training job');
      }

      const jobId = startData.job_id;
      this.segmentAutoTrainingJobId = jobId;
      this.segmentAutoTrainingCancelRequested = false;
      console.log('✅ Segment training job started:', jobId);

      // Step 2: Poll for status.
      // Keepalive is started HERE (inside the Promise) so it stays alive for the
      // entire polling window, not just until the outer async function returns.
      return new Promise((resolve, reject) => {
        this.startKeepalive();

        const _done = (fn: () => void) => {
          clearInterval(pollInterval);
          this.segmentAutoTrainingPollHandle = null;
          this.segmentAutoTrainingJobId = null;
          this.stopKeepalive();
          fn();
        };

        const pollInterval = setInterval(async () => {
          try {
            if (this.segmentAutoTrainingCancelRequested) {
              _done(() => reject(new Error('cancelled')));
              return;
            }

            const statusResponse = await fetch(`${this.baseUrl}/segment-auto-training/status/${jobId}`, {
              method: 'GET',
              headers: {
                'Content-Type': 'application/json',
                ...this.getAuthHeaders(),
              }
            });

            if (!statusResponse.ok) {
              let bodyText = '';
              try { bodyText = await statusResponse.text(); } catch (_) { bodyText = ''; }
              _done(() => reject(new Error(`Failed to get job status: ${bodyText || statusResponse.statusText}`)));
              return;
            }

            const statusData = await statusResponse.json();
            const status = statusData.status;

            if (status === 'completed') {
              console.log('✅ Segment auto training completed:', statusData.model_id || statusData.results?.model_id);
              if (statusData.model_id) {
                try {
                  const fullResults = await this.getSegmentAutoUnifiedResults(statusData.model_id);
                  _done(() => resolve(fullResults));
                } catch (error) {
                  console.error('❌ Failed to fetch full results:', error);
                  _done(() => resolve(statusData.results || statusData));
                }
              } else {
                _done(() => resolve(statusData.results || statusData));
              }
            } else if (status === 'failed') {
              _done(() => reject(new Error(statusData.error || 'Segment training failed')));
            }
            // If pending or running, continue polling
          } catch (error) {
            _done(() => reject(error));
          }
        }, 2000) as unknown as number; // Poll every 2 seconds

        this.segmentAutoTrainingPollHandle = pollInterval;
      });
    } catch (error) {
      console.error('❌ Segment auto training failed:', error);
      throw error;
    }
  }

  /**
   * Get unified segment auto training results
   */
  async getSegmentAutoUnifiedResults(modelId: string): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/segment-auto-training/${modelId}/unified-results`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        }
      });

      if (!response.ok) {
        let bodyText = '';
        try { bodyText = await response.text(); } catch (_) { bodyText = ''; }
        let msg = '';
        try {
          const j = bodyText ? JSON.parse(bodyText) : null;
          msg = (j && (j.detail || j.message)) || bodyText;
        } catch (_) {
          msg = bodyText || response.statusText;
        }
        throw new Error(msg);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.error('❌ Get segment auto unified results failed:', error);
      throw error;
    }
  }

  /**
   * Get segment-specific auto training results
   */
  async getSegmentAutoTrainingResults(modelId: string, segmentId: string): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/segment-auto-training/${modelId}/segment/${segmentId}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        }
      });

      if (!response.ok) {
        let bodyText = '';
        try { bodyText = await response.text(); } catch (_) { bodyText = ''; }
        let msg = '';
        try {
          const j = bodyText ? JSON.parse(bodyText) : null;
          msg = (j && (j.detail || j.message)) || bodyText;
        } catch (_) {
          msg = bodyText || response.statusText;
        }
        throw new Error(msg);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.error('❌ Get segment auto training results failed:', error);
      throw error;
    }
  }

  /**
   * Get codebook for training mode and type
   */
  async getCodebook(training_mode: string, training_type: string): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/get-codebook/${training_mode}/${training_type}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        }
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('Codebook fetch failed:', errorText);
        throw new Error(`HTTP error! status: ${response.status}, body: ${errorText}`);
      }

      // Check content type
      const contentType = response.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
        const text = await response.text();
        console.error('Non-JSON response received:', text.substring(0, 500));
        throw new Error(`Server returned HTML instead of JSON. Content-Type: ${contentType}`);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.error('❌ Error fetching codebook:', error);
      throw error;
    }
  }

  /**
   * Start VIF and correlation calculation as background job (async, prevents timeout)
   * Returns job_id immediately
   */
  async startCalculateVifCorrelation(request: {
    dataset_id: string;
    target_column: string;
    independent_variables: string[];
  }): Promise<{ success: boolean; job_id: string; status: string; message?: string }> {
    this.startKeepalive();
    try {
      const response = await this.fetchWithAutoRefresh(`${this.baseUrl}/calculate-vif-correlation/start`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(this.getAuthHeaders() as Record<string, string>),
        },
        body: JSON.stringify(request)
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      return result;
    } catch (error) {
      console.error('Error starting VIF correlation calculation:', error);
      throw error;
    } finally {
      this.stopKeepalive();
    }
  }

  /**
   * Get status of VIF correlation calculation job
   */
  async getVifCorrelationStatus(jobId: string): Promise<{
    job_id: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
    progress?: number;
    result?: any;
    error?: string;
  }> {
    try {
      const response = await this.fetchWithAutoRefresh(`${this.baseUrl}/calculate-vif-correlation/status/${jobId}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          ...(this.getAuthHeaders() as Record<string, string>),
        }
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      return result;
    } catch (error) {
      console.error('Error getting VIF correlation status:', error);
      throw error;
    }
  }

  /**
   * Subscribe to training progress updates via WebSocket
   */
  subscribeToTrainingProgress(sessionId: string): WebSocket {
    const wsBaseUrl = this.baseUrl.replace('http', 'ws');
    const wsUrl = `${wsBaseUrl}/training-progress/${sessionId}`;
    
    console.log('🔌 Connecting to training progress WebSocket:', wsUrl);
    return new WebSocket(wsUrl);
  }

  /**
   * Cancel currently running global auto training job (if any)
   * Stops polling on the frontend and marks the job as cancelled on the backend.
   */
  async cancelAutoTrainingJob(): Promise<void> {
    if (!this.autoTrainingJobId) return;
    const jobId = this.autoTrainingJobId;
    this.autoTrainingCancelRequested = true;

    try {
      try {
        this.autoTrainingStreamAbort?.abort();
      } catch {
        /* ignore */
      }
      await this.fetchWithAutoRefresh(`${this.baseUrl}/auto-training/cancel/${jobId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(this.getAuthHeaders() as Record<string, string>),
        }
      });
    } finally {
      if (this.autoTrainingPollHandle !== null) {
        clearInterval(this.autoTrainingPollHandle);
        this.autoTrainingPollHandle = null;
      }
      this.autoTrainingStreamAbort = null;
      this.autoTrainingJobId = null;
    }
  }

  /**
   * Cancel currently running segment auto training job (if any)
   */
  async cancelSegmentAutoTrainingJob(): Promise<void> {
    if (!this.segmentAutoTrainingJobId) return;
    const jobId = this.segmentAutoTrainingJobId;
    this.segmentAutoTrainingCancelRequested = true;

    try {
      await fetch(`${this.baseUrl}/segment-auto-training/cancel/${jobId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        }
      });
    } finally {
      if (this.segmentAutoTrainingPollHandle !== null) {
        clearInterval(this.segmentAutoTrainingPollHandle);
        this.segmentAutoTrainingPollHandle = null;
      }
      this.segmentAutoTrainingJobId = null;
    }
  }

  /**
   * Cancel currently running global manual multi-model training job (if any)
   */
  async cancelTrainMultipleModelsJob(): Promise<void> {
    if (!this.manualTrainingJobId) return;
    const jobId = this.manualTrainingJobId;
    this.manualTrainingCancelRequested = true;

    try {
      await fetch(`${this.baseUrl}/train-multiple-models/cancel/${jobId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        }
      });
    } finally {
      if (this.manualTrainingPollHandle !== null) {
        clearInterval(this.manualTrainingPollHandle);
        this.manualTrainingPollHandle = null;
      }
      this.manualTrainingJobId = null;
    }
  }

  /**
   * Cancel currently running segment manual multi-model training job (if any)
   */
  async cancelSegmentTrainingJob(): Promise<void> {
    if (!this.segmentManualTrainingJobId) return;
    const jobId = this.segmentManualTrainingJobId;
    this.segmentManualTrainingCancelRequested = true;

    try {
      await fetch(`${this.baseUrl}/segment-training/cancel/${jobId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        }
      });
    } finally {
      if (this.segmentManualTrainingPollHandle !== null) {
        clearInterval(this.segmentManualTrainingPollHandle);
        this.segmentManualTrainingPollHandle = null;
      }
      this.segmentManualTrainingJobId = null;
    }
  }

  // Model Documentation Methods
  async generateDataSummary(data: {
    columns: string[];
    data_dictionary: string | null;
    model_objective: string;
  }): Promise<{ success: boolean; summary?: string; error?: string }> {
    try {
      const response = await fetch(`${this.baseUrl}/documentation/generate-data-summary`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify(data),
      });

      const result = await response.json();
      return result;
    } catch (error) {
      console.error('Error generating data summary:', error);
      return { success: false, error: 'Failed to generate data summary' };
    }
  }

  async generateDataQualitySummary(data: {
    metrics: {
      emptyColumns: number;
      constantColumns: number;
      sparseColumns: number;
      formattingIssues: number;
      emptyColumnNames: string[];
      constantColumnNames: string[];
      sparseColumnNames: string[];
      formattingIssueColumnNames: string[];
    };
    recommendations: string[];
    totalRows: number;
    totalColumns: number;
  }): Promise<{ success: boolean; summary?: string; error?: string }> {
    try {
      const response = await fetch(`${this.baseUrl}/documentation/generate-data-quality-summary`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify(data),
      });

      const result = await response.json();
      return result;
    } catch (error) {
      console.error('Error generating data quality summary:', error);
      return { success: false, error: 'Failed to generate data quality summary' };
    }
  }

  async generateTargetDefinition(data: {
    target_variable: string;
    data_dictionary: string | null;
    columns: string[];
    problem_statement: string | null;
  }): Promise<{ success: boolean; definition?: string; error?: string }> {
    try {
      const response = await fetch(`${this.baseUrl}/documentation/generate-target-definition`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify(data),
      });

      const result = await response.json();
      return result;
    } catch (error) {
      console.error('Error generating target definition:', error);
      return { success: false, error: 'Failed to generate target definition' };
    }
  }

  async generateModelObjective(data: {
    project_description?: string | null;
    problem_statement?: string | null;
    data_summary?: string | null;
    target_variable_name?: string | null;
    target_definition?: string | null;
  }): Promise<{ success: boolean; objective?: string; error?: string }> {
    try {
      const response = await fetch(`${this.baseUrl}/documentation/generate-model-objective`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify(data),
      });

      const result = await response.json();
      return result;
    } catch (error) {
      console.error('Error generating model objective:', error);
      return { success: false, error: 'Failed to generate model objective' };
    }
  }

  async generateMonotonicitySummary(data: {
    models: Array<{
      modelName: string;
      monotonicityScore: number;
      ksStatistic: number;
      liftTopDecile: number | null;
      auc: number;
      gini: number;
      psi?: { value: number } | number | null;
    }>;
  }): Promise<{ success: boolean; writeup?: string; error?: string }> {
    try {
      const response = await fetch(`${this.baseUrl}/documentation/generate-monotonicity-summary`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify(data),
      });

      const result = await response.json();
      return result;
    } catch (error) {
      console.error('Error generating monotonicity summary:', error);
      return { success: false, error: 'Failed to generate monotonicity summary' };
    }
  }

  async calculateEventRate(data: {
    dataset_id: string;
    target_variable: string;
  }): Promise<{ success: boolean; event_count?: number; total_count?: number; percentage?: number; error?: string }> {
    try {
      const response = await fetch(`${this.baseUrl}/documentation/calculate-event-rate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify(data),
      });

      const result = await response.json();
      return result;
    } catch (error) {
      console.error('Error calculating event rate:', error);
      return { success: false, error: 'Failed to calculate event rate' };
    }
  }

  async getSamplingPlan(data: {
    dataset_id: string;
    target_variable: string;
  }): Promise<{ 
    success: boolean; 
    has_split?: boolean;
    train?: { total: number; event_count: number; event_rate: number };
    hold?: { total: number; event_count: number; event_rate: number };
    error?: string;
  }> {
    try {
      const response = await fetch(`${this.baseUrl}/documentation/get-sampling-plan`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify(data),
      });

      const result = await response.json();
      return result;
    } catch (error) {
      console.error('Error getting sampling plan:', error);
      return { success: false, error: 'Failed to get sampling plan' };
    }
  }

  async getModelPerformance(data: {
    model_id: string;
    dataset_id: string;
    data_dictionary?: string;
    variable_categories?: Record<string, string>;
    category_colors?: Record<string, string>;
  }): Promise<{
    success: boolean;
    total_features: number;
    used_features: string[];
    top_features: Array<{
      feature_name: string;
      importance: number;
      description: string;
    }>;
    category_distribution: Record<string, number>;
    category_colors: Record<string, string>;
    error?: string;
  }> {
    try {
      const response = await fetch(`${this.baseUrl}/documentation/get-model-performance`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify(data),
      });

      const result = await response.json();
      return result;
    } catch (error: any) {
      console.error('Error getting model performance:', error);
      return {
        success: false,
        total_features: 0,
        used_features: [],
        top_features: [],
        category_distribution: {},
        category_colors: {},
        error: error.message || 'Failed to get model performance',
      };
    }
  }

  async generateSegmentationUnderstanding(data: {
    data_summary: string;
    segments: Array<{
      rule: string;
      total: number;
      eventRate: number;
      segmentDistribution: number;
    }>;
    segment_sizes: number[];
    segment_proportions: number[];
    event_rates: number[];
    iv_report?: {
      table: Array<{
        segment_id: number;
        woe: number;
        iv_contribution: number;
        bad_rate: number;
      }>;
    };
  }): Promise<{ success: boolean; understanding?: string; error?: string }> {
    try {
      const response = await fetch(`${this.baseUrl}/documentation/generate-segmentation-understanding`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify(data),
      });

      const result = await response.json();
      return result;
    } catch (error: any) {
      console.error('Error generating segmentation understanding:', error);
      return {
        success: false,
        error: error.message || 'Failed to generate segmentation understanding',
      };
    }
  }

  async getQualityCheckPlan(datasetId: string): Promise<{ success: boolean; plan?: { table: Array<{ Issue: string; Variable: string; Observation: string; Treatment: string }> }; error?: string }> {
    try {
      const response = await fetch(`${this.baseUrl}/documentation/get-quality-check-plan`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify({ dataset_id: datasetId }),
      });

      const result = await response.json();
      return result;
    } catch (error: any) {
      console.error('Error getting quality check plan:', error);
      return {
        success: false,
        error: error.message || 'Failed to get quality check plan',
      };
    }
  }

  async getColumnStats(datasetId: string): Promise<{ success: boolean; stats?: Array<any>; error?: string }> {
    try {
      const response = await fetch(`${this.baseUrl}/documentation/get-column-stats`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify({ dataset_id: datasetId }),
      });

      const result = await response.json();
      return result;
    } catch (error: any) {
      console.error('Error getting column stats:', error);
      return {
        success: false,
        error: error.message || 'Failed to get column stats',
      };
    }
  }

  async generateQualityChangesWriteup(data: {
    quality_check_plan: { table: Array<{ Issue: string; Variable: string; Observation: string; Treatment: string }> };
    column_stats: Array<any>;
  }): Promise<{ success: boolean; writeup?: string; error?: string }> {
    try {
      const response = await fetch(`${this.baseUrl}/documentation/generate-quality-changes-writeup`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify(data),
      });

      const result = await response.json();
      return result;
    } catch (error: any) {
      console.error('Error generating quality changes write-up:', error);
      return {
        success: false,
        error: error.message || 'Failed to generate quality changes write-up',
      };
    }
  }

  async getDataInsights(datasetId: string): Promise<{ success: boolean; insights?: any; error?: string }> {
    try {
      const response = await fetch(`${this.baseUrl}/documentation/get-data-insights`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify({ dataset_id: datasetId }),
      });

      const result = await response.json();
      return result;
    } catch (error: any) {
      console.error('Error getting data insights:', error);
      return {
        success: false,
        error: error.message || 'Failed to get data insights',
      };
    }
  }

  async generateColumnDistributionInsights(
    datasetId: string,
    columnName: string,
    columnType: string,
    distribution: { [key: string]: number },
    statistics?: {
      total_count: number;
      valid_count: number;
      missing_count: number;
    }
  ): Promise<{ success: boolean; insights?: Array<{ title: string; description: string; type: 'info' | 'warning' | 'success' }>; error?: string }> {
    try {
      const response = await fetch(`${this.baseUrl}/datasets/${datasetId}/column-insights`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify({
          column_name: columnName,
          column_type: columnType,
          distribution: distribution,
          statistics: statistics,
        }),
      });

      const result = await response.json();
      return result;
    } catch (error: any) {
      console.error('Error generating column distribution insights:', error);
      return {
        success: false,
        error: error.message || 'Failed to generate column distribution insights',
      };
    }
  }

  async generateFeatureEngineeringWriteup(data: {
    transformed_variables: Array<{ new_variable_name: string; var_type: string; variable_definition: string; transformation_methods: string }>;
  }): Promise<{ success: boolean; writeup?: string; error?: string }> {
    try {
      const response = await fetch(`${this.baseUrl}/documentation/generate-feature-engineering-writeup`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify(data),
      });

      const result = await response.json();
      return result;
    } catch (error: any) {
      console.error('Error generating feature engineering write-up:', error);
      return {
        success: false,
        error: error.message || 'Failed to generate feature engineering write-up',
      };
    }
  }

  async generateAIExplainabilityWriteup(data: {
    beeswarm_data?: Array<Record<string, any>>;
    waterfall_data?: Array<Record<string, any>>;
    pdp_data?: Array<Record<string, any>>;
  }): Promise<{ success: boolean; writeup?: string; error?: string }> {
    try {
      const response = await fetch(`${this.baseUrl}/documentation/generate-ai-explainability-writeup`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify(data),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Failed to generate AI explainability write-up' }));
        throw new Error(errorData.error || 'Failed to generate AI explainability write-up');
      }

      const result = await response.json();
      return result;
    } catch (error) {
      console.error('Error generating AI explainability write-up:', error);
      return { success: false, error: (error as Error).message };
    }
  }

  async evaluatePrunedModel(data: {
    pruned_model_id: string;
    surviving_features: string[];
    dataset_id: string;
  }): Promise<{ success: boolean; message?: string; error?: string }> {
    try {
      const parts = data.pruned_model_id.split('_pruned_');
      const original_model_id = parts[0];
      const response = await fetch(`${this.baseUrl}/model-evaluation/${original_model_id}/evaluate-pruned`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify(data),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Failed to evaluate pruned model' }));
        throw new Error(errorData.error || 'Failed to evaluate pruned model');
      }

      const result = await response.json();
      return result;
    } catch (error: any) {
      console.error('Error evaluating pruned model:', error);
      return {
        success: false,
        error: error.message || 'Failed to evaluate pruned model',
      };
    }
  }

  async generateDecileProgressionWriteup(data: {
    model_name: string;
    deciles: Array<Record<string, any>>;
    monotonicity_score: number;
    violations: Array<{ fromDecile: number; toDecile: number; drop: number; }>;
  }): Promise<{ success: boolean; writeup?: string; error?: string }> {
    try {
      const response = await fetch(`${this.baseUrl}/documentation/generate-decile-progression-writeup`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify(data),
      });

      const result = await response.json();
      return result;
    } catch (error: any) {
      console.error('Error generating decile progression write-up:', error);
      return {
        success: false,
        error: error.message || 'Failed to generate decile progression write-up',
      };
    }
  }

  async generateSamplingPlanWriteup(data: {
    sampling_plan: {
      hasSplit?: boolean;
      train?: { total: number; eventCount: number; eventRate: number };
      hold?: { total: number; eventCount: number; eventRate: number };
    };
  }): Promise<{ success: boolean; writeup?: string; error?: string }> {
    try {
      const response = await fetch(`${this.baseUrl}/documentation/generate-sampling-plan-writeup`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify(data),
      });

      const result = await response.json();
      return result;
    } catch (error: any) {
      console.error('Error generating sampling plan write-up:', error);
      return {
        success: false,
        error: error.message || 'Failed to generate sampling plan write-up',
      };
    }
  }

  async generateModelValidationWriteup(data: {
    model_validation: {
      hasHoldDataset?: boolean;
      bestModel?: {
        modelName: string;
        metrics: {
          accuracy: number;
          precision: number;
          recall: number;
          f1Score: number;
          aucRoc: number;
          aucPr: number;
          logLoss: number;
        };
      };
    };
    data_summary?: string;
  }): Promise<{ success: boolean; writeup?: string; error?: string }> {
    try {
      const response = await fetch(`${this.baseUrl}/documentation/generate-model-validation-writeup`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify(data),
      });

      const result = await response.json();
      return result;
    } catch (error: any) {
      console.error('Error generating model validation write-up:', error);
      return {
        success: false,
        error: error.message || 'Failed to generate model validation write-up',
      };
    }
  }

  async getTransformedVariables(datasetId: string): Promise<{ success: boolean; transformed_variables?: Array<{ new_variable_name: string; var_type: string; variable_definition: string; transformation_methods: string }>; error?: string }> {
    try {
      // First try to get from sessionStorage (more reliable)
      const stored = sessionStorage.getItem('feature_engineering_transformation_response');
      if (stored) {
        try {
          const parsed = JSON.parse(stored);
          if (parsed?.response_data && Array.isArray(parsed.response_data) && parsed.response_data.length > 0) {
            const transformedVars = parsed.response_data.map((item: any) => ({
              new_variable_name: item.new_variable_name || '',
              var_type: item.var_type || '',
              variable_definition: item.variable_definition || '',
              transformation_methods: item.transformation_methods || ''
            }));
            return {
              success: true,
              transformed_variables: transformedVars
            };
          }
        } catch (e) {
          console.warn('Failed to parse stored transformation response:', e);
        }
      }

      // Fallback to API
      const response = await fetch(`${this.baseUrl}/documentation/get-transformed-variables`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify({ dataset_id: datasetId }),
      });

      const result = await response.json();
      return result;
    } catch (error: any) {
      console.error('Error getting transformed variables:', error);
      return {
        success: false,
        error: error.message || 'Failed to get transformed variables',
      };
    }
  }

  async getVariableAnalysis(datasetId: string): Promise<{ success: boolean; variable_analysis?: any; variable_statistics?: Array<any>; error?: string }> {
    try {
      const response = await fetch(`${this.baseUrl}/documentation/get-variable-analysis`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify({ dataset_id: datasetId }),
      });

      const result = await response.json();
      return result;
    } catch (error: any) {
      console.error('Error getting variable analysis:', error);
      return {
        success: false,
        error: error.message || 'Failed to get variable analysis',
      };
    }
  }

  async downloadDocumentation(documentationData: any): Promise<Blob> {
    try {
      const response = await fetch(`${this.baseUrl}/documentation/download`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
        },
        body: JSON.stringify(documentationData),
      });

      if (!response.ok) {
        throw new Error('Failed to download documentation');
      }

      return await response.blob();
    } catch (error) {
      console.error('Error downloading documentation:', error);
      throw error;
    }
  }

  // =============================================================================
  // Duplicate Removal Methods
  // =============================================================================

  /**
   * Identify duplicate rows in a dataset based on specified columns
   * @param datasetId - The dataset identifier
   * @param columns - List of column names to use as the duplicate key
   * @returns Promise with duplicate count and statistics
   */
  async identifyDuplicates(
    datasetId: string,
    columns: string[]
  ): Promise<{
    success: boolean;
    dataset_id: string;
    duplicate_count: number;
    total_rows: number;
    duplicate_percentage: number;
    columns_used: string[];
    /** 'train' or 'entire' when no split — matches backend identify-duplicates */
    analysis_scope?: string;
  }> {
    try {
      console.log('Identifying duplicates for dataset:', datasetId, 'columns:', columns);
      
      const formData = new FormData();
      columns.forEach(col => formData.append('columns', col));
      
      const response = await fetch(`${this.baseUrl}/datasets/${datasetId}/identify-duplicates`, {
        method: 'POST',
        headers: this.getAuthHeaders(),
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to identify duplicates: ${response.status}`);
      }

      const result = await response.json();
      console.log('Duplicates identified:', result.duplicate_count, 'out of', result.total_rows);
      return result;
    } catch (error) {
      console.error('Error identifying duplicates:', error);
      throw error;
    }
  }

  /**
   * Remove duplicate rows from a dataset based on specified columns
   * @param datasetId - The dataset identifier
   * @param columns - List of column names to use as the duplicate key
   * @returns Promise with removal statistics
   */
  async removeDuplicates(
    datasetId: string,
    columns: string[]
  ): Promise<{
    success: boolean;
    dataset_id: string;
    removed_count: number;
    original_row_count: number;
    new_row_count: number;
    columns_used: string[];
  }> {
    try {
      console.log('Removing duplicates from dataset:', datasetId, 'columns:', columns);
      
      const formData = new FormData();
      columns.forEach(col => formData.append('columns', col));
      
      const response = await fetch(`${this.baseUrl}/datasets/${datasetId}/remove-duplicates`, {
        method: 'POST',
        headers: this.getAuthHeaders(),
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to remove duplicates: ${response.status}`);
      }

      const result = await response.json();
      console.log('Duplicates removed:', result.removed_count, 'New row count:', result.new_row_count);
      return result;
    } catch (error) {
      console.error('Error removing duplicates:', error);
      throw error;
    }
  }

  // =============================================================================
  // EDA Snapshot Methods
  // =============================================================================

  /**
   * Get a comprehensive EDA snapshot for a dataset
   * @param datasetId - The dataset identifier
   * @param scope - Data scope to analyze (entire, train, test, validation)
   * @returns Promise with EDA snapshot containing statistics for all column types
   */
  async getEDASnapshot(
    datasetId: string,
    scope: 'entire' | 'train' | 'test' | 'validation' = 'entire'
  ): Promise<{
    success: boolean;
    dataset_id: string;
    scope: string;
    eda_snapshot: {
      timestamp: string;
      totalRows: number;
      totalColumns: number;
      numericStats: Array<{
        column: string;
        count: number;
        mean: number;
        std: number;
        min: number;
        percentile_25: number;
        percentile_50: number;
        percentile_75: number;
        max: number;
        missing_count: number;
        missing_percentage: number;
      }>;
      categoricalStats: Array<{
        column: string;
        unique_count: number;
        top_category: string | null;
        top_category_count: number;
        top_category_percentage: number;
        missing_count: number;
        missing_percentage: number;
        value_distribution: Record<string, number>;
      }>;
      dateStats: Array<{
        column: string;
        min_date: string | null;
        max_date: string | null;
        date_range_days: number;
        unique_count: number;
        missing_count: number;
        missing_percentage: number;
        most_frequent_date: string | null;
        most_frequent_count: number;
      }>;
      treatmentApplied?: string;
    };
  }> {
    try {
      console.log('Fetching EDA snapshot for dataset:', datasetId, 'scope:', scope);
      
      const response = await fetch(`${this.baseUrl}/datasets/${datasetId}/eda-snapshot?scope=${scope}`, {
        headers: this.getAuthHeaders(),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to get EDA snapshot: ${response.status}`);
      }

      const result = await response.json();
      console.log('EDA snapshot retrieved:', result.eda_snapshot?.totalRows, 'rows,', result.eda_snapshot?.totalColumns, 'columns');
      return result;
    } catch (error) {
      console.error('Error getting EDA snapshot:', error);
      throw error;
    }
  }
}

// Global Model Training Interfaces
export interface GlobalModelTrainingRequest {
  dataset_id: string;
  algorithm: 'random_forest' | 'gradient_boosting' | 'logistic_regression' | 'xgboost' | 'lightgbm' | 'catboost';
  k_folds: number;
  target_variable?: string;
  selected_variables?: string[];  // Optional list of independent variables to use for training
}

export interface CodebookSection {
  title: string;
  type: string;
  content: string;
}

export interface ModelCodebookResponse {
  success: boolean;
  algorithm: string;
  title: string;
  description: string;
  sections: CodebookSection[];
}

export interface GlobalModelTrainingResponse {
  success: boolean;
  message: string;
  algorithm: string;
  algorithm_resolved: string;
  problem_type: 'classification' | 'regression';
  k_folds: number;
  training_time_seconds: number;
  model_id: string;
  performance_metrics: {
    // Classification metrics
    accuracy?: number;
    precision?: number;
    recall?: number;
    f1_score?: number;
    mean_accuracy?: number;
    std_accuracy?: number;
    // Regression metrics
    r2_score?: number;
    adjusted_r2_score?: number;
    mse?: number;
    rmse?: number;
    mae?: number;
    mean_r2?: number;
    std_r2?: number;
    cross_validation_results: Array<{
      fold: number;
      // Classification metrics
      accuracy?: number;
      precision?: number;
      recall?: number;
      f1_score?: number;
      // Regression metrics
      r2_score?: number;
      mse?: number;
      rmse?: number;
      mae?: number;
    }>;
  };
}

export type SegmentationMethod = 'cart' | 'chaid';
export interface SegmentationRequest {
  dataset_id: string;
  variables: string[];
  method: SegmentationMethod;
  target_variable?: string | null;
  max_depth?: number;
  min_samples_leaf?: number;
  min_segment_size_ratio?: number;
  max_segments?: number;
}

export interface SegmentationResponse {
  success: boolean;
  message: string;
  method: string;
  variables_used: string[];
  parameters: Record<string, any>;
  num_segments: number;
  segments: Array<Record<string, any>>;
  viability: Record<string, any>;
  dataset_shape?: number;  // Total rows in dataset used for segmentation
  total_segment_records?: number;  // Sum of all segment sizes
  records_match?: boolean;  // Verification flag
}

export interface AutoSegmentationRequest {
  dataset_id: string;
  method: SegmentationMethod;
  target_variable?: string | null;
  max_depth?: number;
  min_samples_leaf?: number;
  min_segment_size_ratio?: number;
  max_segments?: number;
}

export interface AutoSegmentationResponse {
  success: boolean;
  message: string;
  method: string;
  variables_used: string[];
  parameters: Record<string, any>;
  num_segments: number;
  segments: Array<Record<string, any>>;
  viability: Record<string, any>;
}

// =============================================================================
// Segmentation Agent Types (4-Mode Architecture)
// =============================================================================

export type SegmentationModeType = 'pre_existing' | 'variable_driven' | 'manual_rules' | 'auto';

export interface VariablePriority {
  primary: string;
  secondary?: string | null;
  tertiary?: string | null;
}

export interface RuleCondition {
  variable: string;
  operator: string;
  value: any;
}

export interface ManualSegmentRule {
  segment_name: string;
  conditions: RuleCondition[];
  logic: 'AND' | 'OR';
  /** When true, assigns all rows not matched by earlier segments (plan §6.2). */
  catch_all?: boolean;
}

export interface SegmentDetail {
  segment_id: number;
  segment_name: string;
  rule_definition: string;
  record_count: number;
  pct_of_population: number;
  event_count: number;
  event_rate: number;
  woe: number;
  iv_contribution: number;
}

export interface SegmentFlag {
  segment_name: string;
  flag_type: 'low_observations' | 'low_events' | 'dominant' | 'tiny';
  severity: 'amber' | 'red';
  message: string;
}

export interface MergeRecommendation {
  segment_a: string;
  segment_b: string;
  failed_condition: 'reliability' | 'practical_separation' | 'validation';
  /** True when point separation passes but bootstrap event-rate bands overlap (plan §9.4). */
  is_bootstrap_borderline?: boolean;
  event_rate_a: number;
  event_rate_b: number;
  event_rate_diff: number;
  practical_threshold: number;
  merged_record_count: number;
  merged_event_rate: number;
  iv_before: number;
  iv_after: number;
  iv_change_pct: number;
  explanation: string;
}

export interface BootstrapStabilityResult {
  bootstrap_runs: number;
  rank_order_preservation_rate: number;
  confidence_bands: Record<string, { lower_5pct: number; upper_95pct: number; median: number; std: number }>;
  confidence_bands_overlap: boolean;
}

export interface OutOfSampleValidation {
  partition_used: string;
  rank_order_preserved: boolean;
  max_event_rate_drift: number;
  max_size_drift: number;
  chi_squared_p: number;
  segment_comparison: Array<Record<string, any>>;
}

export interface ValidationSuiteResult {
  chi_squared_p: number;
  chi_squared_significant: boolean;
  total_iv: number;
  iv_category: 'weak' | 'moderate' | 'strong' | 'suspicious';
  cramers_v: number;
  cramers_v_meaningful: boolean;
  recommendation_category: 'strong' | 'exploratory' | 'weak';
  recommendation_explanation: string;
  segment_flags: SegmentFlag[];
  merge_recommendations: MergeRecommendation[];
  stability?: BootstrapStabilityResult | null;
  oos_validation?: OutOfSampleValidation | null;
}

export interface UnifiedSegmentationRequest {
  dataset_id: string;
  mode: SegmentationModeType;
  target_variable?: string | null;
  // C1: Pre-existing Identifier fields
  segment_column?: string | null;
  // C2: Variable-Driven fields
  variable_priority?: VariablePriority | null;
  method?: SegmentationMethod;
  min_segment_size?: number;
  min_segment_size_mode?: 'absolute' | 'percentage';
  min_segment_size_pct?: number;
  max_segments?: number;
  max_depth?: number;
  /** C2 only: initial = skip reliability in merge suggestions (§5.3); post_edit = all three conditions */
  variable_driven_merge_screening?: 'initial' | 'post_edit' | null;
  // C3: Manual Rules fields
  manual_rules?: ManualSegmentRule[] | null;
}

/** Plan Section 3.4 — C2 tertiary promotion when secondary fails significance (API field `type`). */
export interface TertiaryPromotionSuggestion {
  type: string;
  message: string;
  failed_variable?: string | null;
  suggested_variable?: string | null;
  suggested_p_value?: number | null;
  secondary_significant?: boolean | null;
}

/** Plan Section 3.4 — list form (aligns with backend PromotionSuggestion). */
export interface PromotionSuggestion {
  suggestion_type: string;
  message: string;
  failed_variable?: string | null;
  suggested_variable?: string | null;
  suggested_p_value?: number | null;
}

export interface UnifiedSegmentationResponse {
  success: boolean;
  message: string;
  mode: SegmentationModeType;
  method?: string | null;
  variables_used: string[];
  variable_priority?: VariablePriority | null;
  parameters: Record<string, any>;
  num_segments: number;
  segments: SegmentDetail[];
  validation: ValidationSuiteResult;
  variable_relevance?: Record<string, any> | null;
  dataset_shape?: number;
  total_segment_records?: number;
  records_match?: boolean;
  merge_history?: string[];
  cutoff_edits?: string[];
  tertiary_promotion_suggestion?: TertiaryPromotionSuggestion | null;
  promotion_suggestions?: PromotionSuggestion[] | null;
  auto_candidates?: Array<Record<string, any>> | null;
  selected_scheme_rank?: number | null;
  manual_rules?: ManualSegmentRule[] | null;
}

/** Same shape as unified run / merge / cutoff-apply payloads (full `validation` when rebuild succeeds). */
export type SegmentationWorkflowState = Partial<UnifiedSegmentationResponse> &
  Record<string, unknown> & {
    validation?: ValidationSuiteResult | null;
  };

export interface RuleValidationResult {
  coverage_pct: number;
  unassigned_records: number;
  is_mutually_exclusive: boolean;
  overlap_count: number;
  empty_segments: string[];
  segment_counts: Record<string, number>;
}

export interface SchemeRegistryEntry {
  scheme_id: number;
  column_name: string;
  mode: SegmentationModeType;
  variables: string[];
  variable_priority?: VariablePriority | null;
  tree_method?: string | null;
  variable_selection_method?: string | null;
  segment_count: number;
  total_iv: number;
  recommendation_category: string;
  created_at: string;
}

export interface SchemeRegistryResponse {
  success: boolean;
  dataset_id: string;
  schemes: SchemeRegistryEntry[];
  total_schemes: number;
}

export interface SegmentationSchemeDetailResponse {
  success: boolean;
  dataset_id: string;
  scheme_id: number;
  metadata?: Record<string, any> | null;
  message?: string | null;
}

export interface AddToDataRequest {
  dataset_id: string;
  segmentation_result: UnifiedSegmentationResponse;
  scheme_name?: string | null;
  /** Optional; duplicate saves with the same key return the original scheme (server idempotency). */
  idempotency_key?: string | null;
}

export interface AddToDataResponse {
  success: boolean;
  message: string;
  scheme_id: number;
  column_name: string;
  metadata: Record<string, any>;
}

export interface MergeSegmentsRequest {
  dataset_id: string;
  segment_a_id: number;
  segment_b_id: number;
  new_segment_name?: string | null;
  current_segmentation: Record<string, any>;
}

export interface MergeImpact {
  merged_segment_name: string;
  combined_records: number;
  combined_events: number;
  combined_event_rate: number;
  combined_pct_of_population: number;
  iv_before_merge: number;
  iv_after_merge: number;
  iv_change: number;
  iv_change_pct: number;
}

export interface MergeSegmentsResponse {
  success: boolean;
  message: string;
  merged_segment: SegmentDetail;
  merge_impact: MergeImpact;
  updated_segmentation: SegmentationWorkflowState;
  num_segments_after: number;
  can_undo: boolean;
}

export interface CutoffEditRequest {
  dataset_id: string;
  segment_id: number;
  variable: string;
  operator: string;
  old_value: number | string;
  new_value: number | string;
  preview_only: boolean;
  current_segmentation: Record<string, any>;
}

export interface CutoffEditImpact {
  segment_id: number;
  variable: string;
  old_rule: string;
  new_rule: string;
  records_moved_out: number;
  records_moved_in: number;
  new_record_count: number;
  new_event_count: number;
  new_event_rate: number;
  new_pct_of_population: number;
  iv_before: number;
  iv_after: number;
  iv_change: number;
  below_min_size: boolean;
}

export interface CutoffEditResponse {
  success: boolean;
  message: string;
  preview_only: boolean;
  impact: CutoffEditImpact;
  affected_segments: number[];
  updated_segmentation: SegmentationWorkflowState | null;
  can_undo: boolean;
}

export interface DatasetPreviewResponse {
  success: boolean;
  message: string;
  preview_data?: {
    columns: string[];
    rows: Record<string, any>[];
  };
  shape?: {
    rows: number;
    columns: number;
  };
}

// =======================
// Variable Review Types
// =======================

export type ReasonBadge = 'Leakage' | 'Identifier' | 'Low-value' | 'Flagged' | 'Clean';

export interface VariableReviewRow {
  variable: string;
  auc: string;
  auc_value: number | null;
  flags: string;
  reason: ReasonBadge;
  pre_selected: boolean;
  row_class: 'row-preselected' | 'row-flagged' | 'row-clean';
  detail_reasons: string[];
  layer_flags: string[];
  cardinality_ratio?: number;
  null_rate?: number;
  null_rate_diff?: number;
}

export interface VariableReviewSummary {
  total: number;
  pre_selected: number;
  flagged: number;
  clean: number;
}

export interface VariableReviewRequest {
  dataset_id: string;
  target_col: string;
  sample_id_col?: string;
  weight_col?: string;
  auc_threshold?: number;
  near_perfect_auc_threshold?: number;
  correlation_threshold?: number;
  missingness_diff_threshold?: number;
  leaker_correlation_threshold?: number;
}

export interface VariableReviewResponse {
  success: boolean;
  message: string;
  rows: VariableReviewRow[];
  summary: VariableReviewSummary | null;
  pipeline_time_ms: number | null;
}

export interface ApplyVariableRemovalRequest {
  dataset_id: string;
  variables_to_remove: string[];
}

export interface ApplyVariableRemovalResponse {
  success: boolean;
  message: string;
  removed_count: number;
  remaining_columns: number;
}

// Auto Training Interfaces
export interface AutoTrainRequest {
  dataset_id: string;
  target_column: string;
  target_metric: string;
  target_value: number;
  independent_variables: string[];
  max_runtime_secs?: number;
}

export interface AutoTrainResponse {
  model_id: string;
  problem_type: string;
  metrics: Record<string, number>;
  user_defined_metric: {
    metric_name: string;
    target_value: number;
    achieved_value: number;
    difference: number;
  };
  artifact_path: string;
  training_time_seconds: number;
  feature_importance: Array<{feature: string, importance: number}>;
  cross_validation_scores: number[];
  optimization_method: string;
}

// Manual multi-model training interfaces
export interface TrainMultipleModelsRequest {
  dataset_id: string;
  target_column: string;
  independent_variables?: string[];
  locked_variables?: string[];
  algorithms: string[];
  algorithm_params?: Record<string, any>;
  algorithm_param_ranges?: Record<string, Record<string, { min: number; max: number }>>;
  max_iterations?: number;
  optimization_method?: 'bayesian' | 'random';
  target_metric?: string;
  cv_folds?: number;
  optuna_trials?: number;
  early_stopping_rounds?: number;
  lr_backward_elimination?: {
    vif_threshold?: number;
    p_value_threshold?: number;
  };
  /** When set, segment training uses this column (e.g. segmentation_scheme_2). */
  segment_column?: string | null;
}

export interface TrainMultipleModelsResponse {
  success: boolean;
  problem_type: 'classification' | 'regression';
  used_features: string[];
  results?: Array<{
    model_id?: string;
    algorithm: string;
    metrics?: Record<string, number>;
    cv_scores?: number[];
    artifact_path?: string;
    error?: string;
  }>;
  // Segment-specific properties
  segment_results?: Record<string, any>;
  segment_models?: Record<string, string[]>;
  segment_column?: string;
  segments?: string[];
  model_id?: string;
}

// Export a default instance - will use environment variable or empty string
// Note: This instance should ideally be created through APIIntegrationService.initializeFastAPI()
// to ensure proper environment variable handling
export const fastApiService = new FastAPIService();
export default fastApiService;
