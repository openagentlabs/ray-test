import { fastApiService } from './fastApiService';

export interface HeatmapImageResponse {
  success: boolean;
  image_base64?: string;
  image_data_uri?: string;
}

/** POST /insights/correlation-matrix — full numeric Pearson/Spearman matrix + metadata. */
export interface CorrelationMatrixExportResponse {
  success?: boolean;
  dataset_id: string;
  target_variable: string;
  correlation_method?: string;
  total_variables?: number;
  variables?: string[];
  correlation_matrix?: Record<string, Record<string, number>>;
  top_correlations?: Array<{
    variable_1: string;
    variable_2: string;
    correlation: number;
    abs_correlation: number;
  }>;
  analysis_timestamp?: string;
  message?: string;
}

class MulticollinearityService {
  private baseUrl = '/insights/correlation';

  /**
   * Fetch Correlation Heatmap (PNG as data URI) for Step 3
   */
  async getHeatmapImage(
    dataset_id: string,
    target_variable?: string,
    dark_mode?: boolean,
    top_n?: number
  ): Promise<string> {
    const url = `${this.baseUrl}/${encodeURIComponent(dataset_id)}/heatmap`;
    const params: Record<string, string | boolean | number> = {};
    if (target_variable) params.target_variable = target_variable;
    if (dark_mode) params.dark_mode = true;
    if (top_n) params.top_n = top_n;
    const res = await fastApiService.getInsightResolve202(url, {
      params: Object.keys(params).length > 0 ? params : undefined,
    });

    const data = (res || {}) as HeatmapImageResponse;
    const uri = data.image_data_uri || (data.image_base64 ? `data:image/png;base64,${data.image_base64}` : null);
    if (!uri) throw new Error('No heatmap image returned');
    return uri;
  }

  /**
   * Pairwise Cramér's V association heatmap for categorical columns (PNG as data URI).
   */
  async getCategoricalHeatmapImage(
    dataset_id: string,
    target_variable?: string,
    dark_mode?: boolean,
    top_n?: number
  ): Promise<string> {
    const url = `${this.baseUrl}/${encodeURIComponent(dataset_id)}/heatmap/categorical`;
    const params: Record<string, string | boolean | number> = {};
    if (target_variable) params.target_variable = target_variable;
    if (dark_mode) params.dark_mode = true;
    if (top_n) params.top_n = top_n;
    const res = await fastApiService.getInsightResolve202(url, {
      params: Object.keys(params).length > 0 ? params : undefined,
    });

    const data = (res || {}) as HeatmapImageResponse;
    const uri = data.image_data_uri || (data.image_base64 ? `data:image/png;base64,${data.image_base64}` : null);
    if (!uri) throw new Error('No categorical heatmap image returned');
    return uri;
  }

  /**
   * Full feature–feature correlation matrix (numeric columns only) for Excel export.
   */
  async getFullCorrelationMatrixData(
    dataset_id: string,
    target_variable: string,
    correlation_method: 'pearson' | 'spearman' = 'pearson'
  ): Promise<CorrelationMatrixExportResponse> {
    const formData = new FormData();
    formData.append('dataset_id', dataset_id);
    formData.append('target_variable', target_variable);
    formData.append('correlation_method', correlation_method);
    const res = await fastApiService.postInsightFormResolve202('/insights/correlation-matrix', formData);
    return (res || {}) as CorrelationMatrixExportResponse;
  }
}

export const multicollinearityService = new MulticollinearityService();


