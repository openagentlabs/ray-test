import { fastApiService } from './fastApiService';

export interface CorrelationData {
  variable_name: string;
  correlation_value: number;
  variable_type: 'numerical' | 'categorical';
}

/** One row from POST /insights/correlation/analyze (all variables vs target). */
export interface CorrelationResultDetail {
  variable_name: string;
  variable_type: string;
  pearson_correlation?: number | null;
  spearman_correlation?: number | null;
  chi_square_statistic?: number | null;
  chi_square_p_value?: number | null;
  cramers_v?: number | null;
  is_significant?: boolean;
  significance_level?: string;
  primary_correlation?: number | null;
  error?: string;
}

export interface CorrelationDatasetSummary {
  shape?: [number, number];
  numeric_columns?: string[];
  categorical_columns?: string[];
  missing_values?: Record<string, unknown>;
}

export interface CorrelationAnalysisResponse {
  dataset_id: string;
  target_variable: string;
  correlation_threshold: number;
  correlations: CorrelationData[];
  total_variables_analyzed: number;
  variables_above_threshold: number;
  analysis_timestamp: string;
  /** Unfiltered backend rows for exports (all features vs target). */
  full_correlation_results: CorrelationResultDetail[];
  dataset_summary?: CorrelationDatasetSummary | null;
}

export interface CorrelationAnalysisParams {
  dataset_id: string;
  target_variable: string;
  correlation_threshold?: number;
  correlation_method?: 'pearson' | 'spearman';
}

class CorrelationAnalysisService {
  private baseUrl = '/insights/correlation';

  /**
   * Perform correlation analysis for all variables against target variable
   */
  async analyzeCorrelations(params: CorrelationAnalysisParams): Promise<CorrelationAnalysisResponse> {
    try {
      console.log('🔍 Starting correlation analysis:', params);
      
      const formData = new FormData();
      formData.append('dataset_id', params.dataset_id);
      formData.append('target_variable', params.target_variable);
      formData.append('correlation_threshold', (params.correlation_threshold || 0.05).toString());
      formData.append('correlation_method', params.correlation_method || 'pearson');

      console.log('📤 Sending correlation request to:', `${this.baseUrl}/analyze`);
      
      const response = await fastApiService.post(`${this.baseUrl}/analyze`, formData);

      console.log('✅ Correlation analysis response received:', response.data);
      
      // Transform backend response to frontend format
      const backendData = response.data;
      
      // Handle backend success field (might be 1 instead of true)
      if (backendData.success === 1) {
        backendData.success = true;
      }
      
      // Extract correlations from correlation_results
      const correlations: CorrelationData[] = [];
      console.log('🔍 Backend correlation_results:', backendData.correlation_results);
      console.log('🔍 Backend correlation_results length:', backendData.correlation_results?.length);
      console.log('🔍 Backend significant_variables:', backendData.significant_variables);
      console.log('🔍 Backend success field:', backendData.success);
      
      const full_correlation_results: CorrelationResultDetail[] = Array.isArray(backendData.correlation_results)
        ? backendData.correlation_results.map((r: Record<string, unknown>) => ({
            variable_name: String(r.variable_name ?? ''),
            variable_type: String(r.variable_type ?? ''),
            pearson_correlation: r.pearson_correlation as number | null | undefined,
            spearman_correlation: r.spearman_correlation as number | null | undefined,
            chi_square_statistic: r.chi_square_statistic as number | null | undefined,
            chi_square_p_value: r.chi_square_p_value as number | null | undefined,
            cramers_v: r.cramers_v as number | null | undefined,
            is_significant: Boolean(r.is_significant),
            significance_level: r.significance_level != null ? String(r.significance_level) : undefined,
            primary_correlation: r.primary_correlation as number | null | undefined,
            error: r.error != null ? String(r.error) : undefined,
          }))
        : [];

      if (backendData.correlation_results) {
        for (const result of backendData.correlation_results) {
          console.log('🔍 Processing result:', result);
          
          // Only use Pearson correlation for numeric variables
          let correlationValue = null;
          if (result.variable_type === 'numeric' && 
              result.pearson_correlation !== null && 
              result.pearson_correlation !== undefined) {
            correlationValue = result.pearson_correlation;
          }
          // Skip categorical variables - only show Pearson correlation for numeric variables in the chart
          
          // Include variables that are significant and have valid correlation values
          if (result.is_significant && correlationValue !== null) {
            console.log('✅ Adding correlation:', {
              variable_name: result.variable_name,
              correlation_value: correlationValue,
              variable_type: result.variable_type
            });
            correlations.push({
              variable_name: result.variable_name,
              correlation_value: correlationValue,
              variable_type: result.variable_type === 'numeric' ? 'numerical' : 'categorical'
            });
          } else {
            console.log('❌ Skipping correlation:', {
              variable_name: result.variable_name,
              is_significant: result.is_significant,
              correlationValue: correlationValue,
              variable_type: result.variable_type
            });
          }
        }
      }
      
      console.log('📊 Extracted correlations before filtering:', correlations);
      console.log('📊 Number of correlations extracted:', correlations.length);
      
      // Filter by threshold and sort
      const filteredCorrelations = this.filterByThreshold(correlations, params.correlation_threshold);
      const sortedCorrelations = this.sortByAbsoluteValue(filteredCorrelations);
      
      console.log('📊 Final correlations after filtering and sorting:', sortedCorrelations);
      console.log('📊 Number of final correlations:', sortedCorrelations.length);
      
      // Create frontend-compatible response
      const ds = backendData.dataset_summary;
      const dataset_summary: CorrelationDatasetSummary | null = ds
        ? {
            shape: ds.shape as [number, number] | undefined,
            numeric_columns: ds.numeric_columns,
            categorical_columns: ds.categorical_columns,
            missing_values: ds.missing_values,
          }
        : null;

      const frontendResponse: CorrelationAnalysisResponse = {
        dataset_id: backendData.dataset_id,
        target_variable: backendData.target_variable,
        correlation_threshold: backendData.correlation_threshold,
        correlations: sortedCorrelations,
        total_variables_analyzed: backendData.total_variables_analyzed,
        variables_above_threshold: sortedCorrelations.length,
        analysis_timestamp: backendData.analysis_timestamp || new Date().toISOString(),
        full_correlation_results,
        dataset_summary,
      };
      
      console.log('🔄 Transformed response for frontend:', frontendResponse);
      return frontendResponse;
    } catch (error) {
      console.error('❌ Error analyzing correlations:', error);
      console.error('Error details:', {
        message: error instanceof Error ? error.message : 'Unknown error',
        stack: error instanceof Error ? error.stack : undefined,
        response: error instanceof Error && 'response' in error ? (error as any).response : undefined
      });
      throw new Error('Failed to analyze correlations');
    }
  }

  /**
   * Get available variables from correlation results
   */
  getAvailableVariables(correlations: CorrelationData[]): string[] {
    return correlations
      .filter(corr => Math.abs(corr.correlation_value) >= 0.05)
      .map(corr => corr.variable_name)
      .sort();
  }

  /**
   * Filter correlations by threshold
   */
  filterByThreshold(correlations: CorrelationData[], threshold: number = 0.05): CorrelationData[] {
    return correlations.filter(corr => Math.abs(corr.correlation_value) >= threshold);
  }

  /**
   * Sort correlations by absolute value (descending)
   */
  sortByAbsoluteValue(correlations: CorrelationData[]): CorrelationData[] {
    return [...correlations].sort((a, b) => 
      Math.abs(b.correlation_value) - Math.abs(a.correlation_value)
    );
  }
}

export const correlationAnalysisService = new CorrelationAnalysisService();
