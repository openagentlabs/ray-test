import { fastApiService } from './fastApiService';

// TypeScript interfaces for VIF analysis
export interface VIFAnalysisResponse {
  success: boolean;
  message: string;
  dataset_id: string;
  target_variable: string;
  total_variables_analyzed: number;
  analysis_results: Record<string, VIFVariableResult>;
  dataset_summary: {
    total_rows: number;
    total_columns: number;
    memory_usage_mb: number;
  };
}

export interface VIFVariableResult {
  variable_name: string;
  variable_type: 'numerical';
  vif_value: number;
  multicollinearity_level: 'low' | 'moderate' | 'high' | 'very_high';
  analysis_result: {
    insights: string[];
    visualization_data: VIFVisualizationData;
    correlated_variables?: string[];
  };
  summary: {
    key_insight: string;
    multicollinearity_level: string;
    recommendation: string;
  };
  error?: string;
}

export interface VIFVisualizationData {
  chart_type: string;
  data: {
    variables?: string[];
    vif_values?: number[];
    correlation_matrix?: Record<string, Record<string, number>>;
  };
}

export interface VIFAnalysisParams {
  dataset_id: string;
  target_variable: string;
  /** Optional server-side cap on numeric columns processed (omit for backend auto-limits). */
  max_columns?: number;
}

// API calls for VIF analysis — canonical /insights/vif-analysis (same calculations as pipeline tables).
export const vifAnalysisService = {
  // Analyze all variables for VIF
  async analyzeAllVariables(params: VIFAnalysisParams): Promise<VIFAnalysisResponse> {
    try {
      const formData = new FormData();
      formData.append('dataset_id', params.dataset_id);
      formData.append('target_variable', params.target_variable);

      if (params.max_columns != null && params.max_columns > 0) {
        formData.append('max_columns', params.max_columns.toString());
      }

      const response = await fastApiService.postInsightFormResolve202('/insights/vif-analysis', formData);
      
      // Transform the backend response to match our frontend interface
      const backendData = response as Record<string, unknown>;
      
      if (backendData.success && backendData.analysis_results) {
        return {
          success: Boolean(backendData.success),
          message: String(backendData.message ?? ''),
          dataset_id: String(backendData.dataset_id ?? ''),
          target_variable: String(backendData.target_variable ?? ''),
          total_variables_analyzed: Number(backendData.total_variables_analyzed ?? 0),
          analysis_results: backendData.analysis_results as Record<string, VIFVariableResult>,
          dataset_summary: backendData.dataset_summary as VIFAnalysisResponse['dataset_summary'],
        };
      } else {
        throw new Error('VIF analysis returned no results');
      }
    } catch (error) {
      console.error('VIF analysis failed:', error);
      throw new Error('Failed to analyze VIF');
    }
  },

  // Get analysis for a specific variable (not implemented in backend yet)
  async getVariableAnalysis(
    datasetId: string,
    variableName: string,
    targetVariable: string
  ): Promise<VIFVariableResult> {
    // For now, we'll get all variables and filter
    const allResults = await this.analyzeAllVariables({
      dataset_id: datasetId,
      target_variable: targetVariable,
    });
    
    const result = allResults.analysis_results[variableName];
    if (!result) {
      throw new Error(`Variable ${variableName} not found in VIF analysis results`);
    }
    
    return result;
  },

  // Helper function to get available variables from analysis results
  getAvailableVariables(analysisResults: Record<string, VIFVariableResult>): string[] {
    return Object.keys(analysisResults).filter(key => {
      const result = analysisResults[key];
      return result && !result.error;
    });
  },

  /**
   * Get variables by multicollinearity level
   */
  getVariablesByMulticollinearityLevel(
    analysisResults: Record<string, VIFVariableResult>,
    level: 'low' | 'moderate' | 'high' | 'very_high'
  ): string[] {
    return Object.keys(analysisResults).filter(
      key => analysisResults[key].multicollinearity_level === level && !analysisResults[key].error
    );
  },

  /**
   * Get summary statistics for all analyzed variables
   */
  getAnalysisSummary(analysisResults: Record<string, VIFVariableResult>) {
    const variables = Object.values(analysisResults);
    const low = variables.filter(v => v.multicollinearity_level === 'low' && !v.error);
    const moderate = variables.filter(v => v.multicollinearity_level === 'moderate' && !v.error);
    const high = variables.filter(v => v.multicollinearity_level === 'high' && !v.error);
    const veryHigh = variables.filter(v => v.multicollinearity_level === 'very_high' && !v.error);
    const errors = variables.filter(v => v.error);

    return {
      total: variables.length,
      low: low.length,
      moderate: moderate.length,
      high: high.length,
      veryHigh: veryHigh.length,
      errors: errors.length,
      error_variables: errors.map(v => v.variable_name),
    };
  },

  // Mock response for when backend is unavailable
  getMockVIFResponse(datasetId: string, targetVariable: string): VIFAnalysisResponse {
    const mockVariables = ['age', 'income', 'education', 'experience', 'score'];
    const analysisResults: Record<string, VIFVariableResult> = {};
    
    mockVariables.forEach(variable => {
      const vifValue = Math.random() * 10; // Random VIF between 0 and 10
      let multicollinearityLevel: 'low' | 'moderate' | 'high' | 'very_high';
      
      if (vifValue < 5) {
        multicollinearityLevel = 'low';
      } else if (vifValue < 10) {
        multicollinearityLevel = 'moderate';
      } else if (vifValue < 20) {
        multicollinearityLevel = 'high';
      } else {
        multicollinearityLevel = 'very_high';
      }
      
      analysisResults[variable] = {
        variable_name: variable,
        variable_type: 'numerical',
        vif_value: vifValue,
        multicollinearity_level: multicollinearityLevel,
        analysis_result: {
          insights: [`Mock VIF analysis for ${variable}`],
          visualization_data: {
            chart_type: 'bar',
            data: {},
          },
        },
        summary: {
          key_insight: `VIF: ${vifValue.toFixed(3)} (${multicollinearityLevel})`,
          multicollinearity_level: multicollinearityLevel,
          recommendation: this.getVIFRecommendation(vifValue),
        },
      };
    });

    return {
      success: true,
      message: 'Mock VIF analysis completed',
      dataset_id: datasetId,
      target_variable: targetVariable,
      total_variables_analyzed: mockVariables.length,
      analysis_results: analysisResults,
      dataset_summary: {
        total_rows: 1000,
        total_columns: 10,
        memory_usage_mb: 5.2,
      },
    };
  },

  // Helper method to get VIF recommendation
  getVIFRecommendation(vifValue: number): string {
    if (vifValue < 5) return 'Variable has low multicollinearity, keep in model';
    if (vifValue < 10) return 'Variable has moderate multicollinearity, consider keeping';
    if (vifValue < 20) return 'Variable has high multicollinearity, consider removing';
    return 'Variable has very high multicollinearity, remove from model';
  },
};
