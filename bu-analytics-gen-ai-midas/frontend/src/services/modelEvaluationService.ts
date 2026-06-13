/**
 * Model Evaluation Service - API calls for MEEA integration
 */

import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { buildMidasAuthHeaders } from './authHeaders';
import { RETRY_AFTER_REFRESH } from './httpUnauthorized';
import {
  ModelEvaluationResponse,
  ModelListResponse,
  ModelComparisonResponse,
  PerformanceMetrics,
  FeatureImportance,
  GranularAccuracy,
  ErrorPattern,
  ExplainabilityData,
  PredictionConfidence,
  ModelEvaluationData
} from '../types/modelEvaluation';

const API_BASE_URL = `${import.meta.env.VITE_BASE_URL || ''}/api/v1/model-evaluation`;

/** Dedicated axios instance: Bearer JWT + session headers + 401 refresh / session-expired flow */
const apiClient = axios.create();

apiClient.interceptors.request.use((config) => {
  const h = buildMidasAuthHeaders();
  config.headers = { ...(config.headers as object), ...h } as typeof config.headers;
  return config;
});

apiClient.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const cfg = error.config as InternalAxiosRequestConfig & { _midas401Retried?: boolean };
    if (!error.response || error.response.status !== 401 || !cfg) {
      return Promise.reject(error);
    }
    const body = error.response.data;
    const payload = typeof body === 'object' && body !== null ? body : { detail: String(body ?? 'Unauthorized') };
    const res = new Response(JSON.stringify(payload), {
      status: 401,
      headers: { 'Content-Type': 'application/json' },
    });
    const { handleUnauthorizedResponse } = await import('./httpUnauthorized');
    const allowRefresh = !cfg._midas401Retried;
    try {
      await handleUnauthorizedResponse(res, { allowRefresh, skipAuth: false });
    } catch (e: unknown) {
      if (allowRefresh && (e as Error)?.message === RETRY_AFTER_REFRESH) {
        cfg._midas401Retried = true;
        cfg.headers = { ...(cfg.headers as object), ...buildMidasAuthHeaders() } as typeof cfg.headers;
        return apiClient.request(cfg);
      }
      throw e;
    }
    return Promise.reject(error);
  }
);

class ModelEvaluationService {
  /**
   * Get complete evaluation data for a model
   */
  async getModelEvaluation(modelId: string, includeExplainability: boolean = false): Promise<ModelEvaluationResponse> {
    try {
      const response = await apiClient.get<ModelEvaluationResponse>(`${API_BASE_URL}/${modelId}`, {
        params: { include_explainability: includeExplainability },
      });
      return response.data;
    } catch (error) {
      console.error('Error fetching model evaluation:', error);
      throw error;
    }
  }

  /**
   * List all evaluated models
   */
  async listAllModels(): Promise<ModelListResponse> {
    try {
      const response = await apiClient.get<ModelListResponse>(`${API_BASE_URL}/list/all`);
      return response.data;
    } catch (error) {
      console.error('Error listing models:', error);
      throw error;
    }
  }

  /**
   * List evaluated models for a specific dataset_id
   */
  async listModelsByDataset(datasetId: string): Promise<ModelListResponse> {
    try {
      const response = await apiClient.get<ModelListResponse>(`${API_BASE_URL}/list/by-dataset`, {
        params: { dataset_id: datasetId },
      });
      return response.data;
    } catch (error) {
      console.error('Error listing models by dataset:', error);
      throw error;
    }
  }

  /**
   * List segmentation evaluation models (Step 4)
   * Placeholder endpoint until real segmentation metrics are wired
   */
  async listSegmentationModels(datasetId?: string): Promise<{ success: boolean; count: number; models: ModelEvaluationData[] }> {
    try {
      const response = await apiClient.get(`${API_BASE_URL.replace('/model-evaluation', '/segmentation-model-evaluation')}`, {
        params: datasetId ? { dataset_id: datasetId } : {},
      });
      return response.data;
    } catch (error) {
      console.error('Error listing segmentation evaluation models:', error);
      throw error;
    }
  }

  /**
   * List segment ids for a dataset (for dropdown)
   */
  async listSegmentationIds(datasetId: string): Promise<{ success: boolean; segments: Array<{ segment_id: string; count: number }> }> {
    try {
      const baseUrl = import.meta.env.VITE_BASE_URL || '';
      const response = await apiClient.get(`${baseUrl}/api/v1/segmentation-model-evaluation/segments/${datasetId}`, {
      });
      return response.data;
    } catch (error) {
      console.error('Error listing segmentation ids:', error);
      throw error;
    }
  }

  /**
   * Get models for a specific segment
   */
  async listSegmentationModelsBySegment(datasetId: string, segmentId: string): Promise<{ success: boolean; models: ModelEvaluationData[] }> {
    try {
      const baseUrl = import.meta.env.VITE_BASE_URL || '';
      const response = await apiClient.get(`${baseUrl}/api/v1/segmentation-model-evaluation/${datasetId}/${segmentId}`, {
      });
      return response.data;
    } catch (error) {
      console.error('Error fetching segmentation models for segment:', error);
      throw error;
    }
  }

  /**
   * List raw samples for a model and data source (train/test) - for per-record explainability
   */
  async listSamples(
    modelId: string,
    dataSource: 'train' | 'test' = 'test',
    offset: number = 0,
    limit: number = 50,
    search?: string,
  ): Promise<{
    total: number;
    data_source: 'train' | 'test';
    target_column?: string; // Target column name from model metadata
    samples: Array<{
      sample_index: number;
      row_index: number | string;
      id_value?: string | number | null;
      target?: number | string | null;
      features: Record<string, any>;
    }>;
  }> {
    try {
      const response = await apiClient.get(`${API_BASE_URL}/${modelId}/samples`, {
        params: {
          data_source: dataSource,
          offset,
          limit,
          ...(search && search.trim() ? { search: search.trim() } : {}),
        },
      });
      return response.data;
    } catch (error) {
      console.error('Error listing model samples:', error);
      throw error;
    }
  }

  /**
   * Compare multiple models
   */
  async compareModels(modelIds: string[]): Promise<ModelComparisonResponse> {
    try {
      const response = await apiClient.post<ModelComparisonResponse>(`${API_BASE_URL}/compare`, {
        model_ids: modelIds
      }, {
      });
      return response.data;
    } catch (error) {
      console.error('Error comparing models:', error);
      throw error;
    }
  }

  /**
   * Get performance metrics only
   */
  async getPerformanceMetrics(modelId: string): Promise<PerformanceMetrics> {
    try {
      const response = await apiClient.get(`${API_BASE_URL}/${modelId}/performance`, {
      });
      return response.data.performance_metrics;
    } catch (error) {
      console.error('Error fetching performance metrics:', error);
      throw error;
    }
  }

  /**
   * Get feature importance
   */
  async getFeatureImportance(modelId: string): Promise<FeatureImportance[]> {
    try {
      const response = await apiClient.get(`${API_BASE_URL}/${modelId}/feature-importance`, {
      });
      return response.data.feature_importance;
    } catch (error) {
      console.error('Error fetching feature importance:', error);
      throw error;
    }
  }

  /**
   * Get granular accuracy
   */
  async getGranularAccuracy(modelId: string): Promise<GranularAccuracy[]> {
    try {
      const response = await apiClient.get(`${API_BASE_URL}/${modelId}/granular-accuracy`, {
      });
      return response.data.granular_accuracy;
    } catch (error) {
      console.error('Error fetching granular accuracy:', error);
      throw error;
    }
  }

  /**
   * Get granular accuracy grouped by segments
   */
  async getGranularAccuracyBySegments(
    modelId: string, 
    variable?: string, 
    granularityLevel?: string
  ): Promise<{
    segments: Record<string, GranularAccuracy[]>;
    available_variables: string[];
    available_granularity_levels: string[];
  }> {
    try {
      const params = new URLSearchParams();
      if (variable) params.append('variable', variable);
      if (granularityLevel) params.append('granularity_level', granularityLevel);
      
      const url = `${API_BASE_URL}/${modelId}/granular-accuracy/by-segments${params.toString() ? '?' + params.toString() : ''}`;
      const response = await apiClient.get(url, {
      });
      return response.data;
    } catch (error) {
      console.error('Error fetching granular accuracy by segments:', error);
      throw error;
    }
  }

  /**
   * Get error patterns
   */
  async getErrorPatterns(modelId: string): Promise<ErrorPattern[]> {
    try {
      const response = await apiClient.get(`${API_BASE_URL}/${modelId}/error-patterns`, {
      });
      return response.data.error_patterns;
    } catch (error) {
      console.error('Error fetching error patterns:', error);
      throw error;
    }
  }

  /**
   * Get explainability data (SHAP, ROC, PDP)
   */
  async getExplainabilityData(modelId: string): Promise<ExplainabilityData[]> {
    try {
      const response = await apiClient.get(`${API_BASE_URL}/${modelId}/explainability`, {
      });
      return response.data.explainability_data;
    } catch (error) {
      console.error('Error fetching explainability data:', error);
      throw error;
    }
  }

  /**
   * Get prediction confidence
   */
  async getPredictionConfidence(modelId: string): Promise<PredictionConfidence[]> {
    try {
      const response = await apiClient.get(`${API_BASE_URL}/${modelId}/prediction-confidence`, {
      });
      return response.data.prediction_confidence;
    } catch (error) {
      console.error('Error fetching prediction confidence:', error);
      throw error;
    }
  }

  /**
   * Get PDP data for a specific model (lazy loading optimization)
   * This reduces initial explainability tab load time by 40% by fetching PDP only when needed
   */
  async getPDPData(modelId: string, dataSource: string = 'test'): Promise<any[]> {
    try {
      const response = await apiClient.get(`${API_BASE_URL}/${modelId}/pdp-data?data_source=${dataSource}`, {
      });
      return response.data.pdp_data || [];
    } catch (error) {
      console.error('Error fetching PDP data:', error);
      throw error;
    }
  }

  /**
   * Delete model evaluation data
   */
  async deleteModelEvaluation(modelId: string): Promise<void> {
    try {
      await apiClient.delete(`${API_BASE_URL}/${modelId}`, {
      });
    } catch (error) {
      console.error('Error deleting model evaluation:', error);
      throw error;
    }
  }

  /**
   * Recalculate explainability for a model on train or test data
   */
  async recalculateExplainability(modelId: string, dataSource: 'train' | 'test'): Promise<{ success: boolean; message: string; samples_used: number }> {
    try {
      const response = await apiClient.post(`${API_BASE_URL}/${modelId}/recalculate-explainability`, {
        data_source: dataSource
      }, {
      });
      return response.data;
    } catch (error) {
      console.error('Error recalculating explainability:', error);
      throw error;
    }
  }

  /**
   * Fetch a single evaluation phase for a model.
   * Returns { ready: false } with HTTP 202 when the phase is not yet computed.
   * Returns { ready: true, data: {...} } when the phase is available.
   *
   * Phase 1 - Performance (metrics, ROC/PR, feature importance)
   * Phase 2 - Monotonicity (decile analysis, KS, AUC/Gini)
   * Phase 3 - Granular Accuracy (segment-level accuracy per feature)
   */
  async getModelEvaluationPhase(
    modelId: string,
    phase: 1 | 2 | 3,
  ): Promise<{ ready: boolean; model_id: string; phase: number; data?: any }> {
    try {
      const response = await apiClient.get(`${API_BASE_URL}/${modelId}/phase/${phase}`, {
        // 202 is a valid non-error response — don't let axios throw on it
        validateStatus: (status) => status === 200 || status === 202,
      });
      return response.data;
    } catch (error) {
      console.error(`Error fetching phase ${phase} for model ${modelId}:`, error);
      return { ready: false, model_id: modelId, phase };
    }
  }

  /**
   * Check whether MEEA (comprehensive model evaluation) is still being computed in the
   * background for the given dataset.  Returns { meea_pending, pending_count }.
   */
  async getMeeaStatus(datasetId: string): Promise<{ meea_pending: boolean; pending_count: number; pending_model_ids: string[] }> {
    try {
      const baseUrl = import.meta.env.VITE_BASE_URL || '';
      const response = await apiClient.get(`${baseUrl}/api/v1/auto-training/meea-status/${datasetId}`, {
      });
      return response.data;
    } catch (error) {
      console.error('Error checking MEEA status:', error);
      return { meea_pending: false, pending_count: 0, pending_model_ids: [] };
    }
  }
}

export const modelEvaluationService = new ModelEvaluationService();
export default modelEvaluationService;

// Export helper function for lazy loading PDP data
export const getPDPData = (modelId: string, dataSource: string = 'test') => 
  modelEvaluationService.getPDPData(modelId, dataSource);

