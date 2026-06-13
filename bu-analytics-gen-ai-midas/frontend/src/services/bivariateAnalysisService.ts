import { fastApiService } from './fastApiService';

// TypeScript interfaces for bivariate analysis
export interface BivariateAnalysisAllResponse {
  success: boolean;
  message: string;
  dataset_id: string;
  target_variable: string;
  total_variables_analyzed: number;
  analysis_results: Record<string, VariableAnalysisResult>;
  dataset_summary: {
    total_rows: number;
    total_columns: number;
    memory_usage_mb: number;
  };
}

export interface BivariateAnalysisSingleResponse {
  success: boolean;
  dataset_id: string;
  target_variable: string;
  variable_name: string;
  analysis_result: VariableAnalysisResult;
}

export interface VariableAnalysisResult {
  variable_name: string;
  variable_type: 'categorical' | 'numerical';
  analysis_result: {
    analysis_type: 'categorical' | 'numerical';
    target_variable: string;
    feature_variable: string;
    insights: string[];
    visualization_data: VisualizationData;
    is_high_cardinality?: boolean;
    cardinality?: number;
    binning_method?: string;
    bins?: number;
  };
  summary: {
    key_insight: string;
    total_categories?: number;
    has_high_cardinality?: boolean;
    binning_method?: string;
    correlation?: number;
  };
  error?: string;
}

export interface VisualizationData {
  chart_type: string;
  data: {
    categories?: string[];
    default_rates?: number[];
    totals?: number[];
    defaults?: number[];
    correlation?: number;
    bin_ranges?: string[];
  };
}

export interface BivariateAnalysisParams {
  dataset_id: string;
  target_variable: string;
  binning_method?: 'quantile' | 'equal_width';
  top_categories?: number;
  bins?: number;
}

class BivariateAnalysisService {
  private baseUrl = '/insights/bivariate';

  /**
   * Perform bivariate analysis for all variables against target variable
   */
  async analyzeAllVariables(params: BivariateAnalysisParams): Promise<BivariateAnalysisAllResponse> {
    try {
      console.log('🔍 Starting bivariate analysis for all variables:', params);
      
      const formData = new FormData();
      formData.append('dataset_id', params.dataset_id);
      formData.append('target_variable', params.target_variable);
      formData.append('binning_method', params.binning_method || 'quantile');
      formData.append('top_categories', (params.top_categories || 10).toString());
      formData.append('bins', (params.bins || 10).toString());

      console.log('📤 Sending request to:', `${this.baseUrl}/all`);
      
      const response = await fastApiService.postInsightFormResolve202(`${this.baseUrl}/all`, formData);

      console.log('✅ Bivariate analysis response received:', response);
      return response as BivariateAnalysisAllResponse;
    } catch (error) {
      console.error('❌ Error analyzing all variables:', error);
      console.error('Error details:', {
        message: error instanceof Error ? error.message : 'Unknown error',
        stack: error instanceof Error ? error.stack : undefined,
        response: error instanceof Error && 'response' in error ? (error as any).response : undefined
      });
      throw new Error('Failed to analyze all variables');
    }
  }

  /**
   * Get analysis results for a specific variable.
   * Optional coarse_bins (numerical) or category_groups (categorical) refine binning / merges.
   */
  async getVariableAnalysis(
    dataset_id: string,
    variable_name: string,
    target_variable: string,
    options?: {
      coarse_bins?: string | null;
      category_groups?: string | null;
    }
  ): Promise<BivariateAnalysisSingleResponse> {
    try {
      console.log('🔍 Getting variable analysis:', { dataset_id, variable_name, target_variable, options });
      
      const url = `${this.baseUrl}/${dataset_id}/variable/${variable_name}`;
      console.log('📤 Sending request to:', url);
      
      const params: Record<string, string> = {
        target_variable,
      };
      if (options?.coarse_bins?.trim()) {
        params.coarse_bins = options.coarse_bins.trim();
      }
      if (options?.category_groups?.trim()) {
        params.category_groups = options.category_groups.trim();
      }

      const response = await fastApiService.get(url, {
        params,
      });

      console.log('✅ Variable analysis response received:', response.data);
      return response.data;
    } catch (error) {
      console.error('❌ Error getting variable analysis:', error);
      console.error('Error details:', {
        message: error instanceof Error ? error.message : 'Unknown error',
        stack: error instanceof Error ? error.stack : undefined,
        response: error instanceof Error && 'response' in error ? (error as any).response : undefined
      });
      throw new Error('Failed to get variable analysis');
    }
  }

  /**
   * Get list of available variables from analysis results
   */
  getAvailableVariables(analysisResults: Record<string, VariableAnalysisResult>): string[] {
    return Object.keys(analysisResults).filter(
      key => !analysisResults[key].error
    );
  }

  /**
   * Get variables by type
   */
  getVariablesByType(
    analysisResults: Record<string, VariableAnalysisResult>,
    type: 'categorical' | 'numerical'
  ): string[] {
    return Object.keys(analysisResults).filter(
      key => analysisResults[key].variable_type === type && !analysisResults[key].error
    );
  }

  /**
   * Get summary statistics for all analyzed variables
   */
  getAnalysisSummary(analysisResults: Record<string, VariableAnalysisResult>) {
    const variables = Object.values(analysisResults);
    const categorical = variables.filter(v => v.variable_type === 'categorical' && !v.error);
    const numerical = variables.filter(v => v.variable_type === 'numerical' && !v.error);
    const errors = variables.filter(v => v.error);

    return {
      total: variables.length,
      categorical: categorical.length,
      numerical: numerical.length,
      errors: errors.length,
      error_variables: errors.map(v => v.variable_name),
    };
  }
}

export const bivariateAnalysisService = new BivariateAnalysisService();
