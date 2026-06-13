import { fastApiService } from './fastApiService';

// TypeScript interfaces for IV analysis
export interface IVAnalysisResponse {
  success: boolean;
  message: string;
  dataset_id: string;
  target_variable: string;
  total_variables_analyzed: number;
  analysis_results: Record<string, IVVariableResult>;
  dataset_summary: {
    total_rows: number;
    total_columns: number;
    memory_usage_mb: number;
  };
}

export interface IVVariableResult {
  variable_name: string;
  variable_type: 'categorical' | 'numerical';
  iv_value: number;
  iv_strength: 'weak' | 'medium' | 'strong' | 'very_strong';
  analysis_result: {
    insights: string[];
    visualization_data: IVVisualizationData;
    bins?: number;
    binning_method?: string;
  };
  summary: {
    key_insight: string;
    iv_strength: string;
    predictive_power: string;
  };
  error?: string;
}

export interface IVVisualizationData {
  chart_type: string;
  data: {
    categories?: string[];
    iv_values?: number[];
    distributions?: {
      category: string;
      count: number;
      event_rate: number;
      iv_contribution: number;
    }[];
  };
}

export interface IVAnalysisParams {
  dataset_id: string;
  target_variable: string;
  binning_method?: 'quantile' | 'equal_width';
  bins?: number;
}

// API calls for IV analysis — /insights/iv-analysis
export const ivAnalysisService = {
  // Analyze all variables for IV
  async analyzeAllVariables(params: IVAnalysisParams): Promise<IVAnalysisResponse> {
    try {
      // Use dedicated IV analysis endpoint
      const formData = new FormData();
      formData.append('dataset_id', params.dataset_id);
      formData.append('target_variable', params.target_variable);
      formData.append('bins', (params.bins || 10).toString());
      
      const response = await fastApiService.postInsightFormResolve202('/insights/iv-analysis', formData);
      
      // Transform the backend response to match our frontend interface
      const backendData = response as Record<string, unknown>;
      
      if (backendData.success && backendData.analysis_results) {
        return {
          success: Boolean(backendData.success),
          message: String(backendData.message ?? ''),
          dataset_id: String(backendData.dataset_id ?? ''),
          target_variable: String(backendData.target_variable ?? ''),
          total_variables_analyzed: Number(backendData.total_variables_analyzed ?? 0),
          analysis_results: backendData.analysis_results as Record<string, IVVariableResult>,
          dataset_summary: backendData.dataset_summary as IVAnalysisResponse['dataset_summary'],
        };
      } else {
        throw new Error('IV analysis returned no results');
      }
    } catch (error) {
      console.error('IV analysis failed:', error);
      throw new Error('Failed to analyze IV');
    }
  },

  // Get analysis for a specific variable
  async getVariableAnalysis(
    datasetId: string,
    variableName: string,
    targetVariable: string
  ): Promise<IVVariableResult> {
    // For now, we'll get all variables and filter
    const allResults = await this.analyzeAllVariables({
      dataset_id: datasetId,
      target_variable: targetVariable
    });
    
    const result = allResults.analysis_results[variableName];
    if (!result) {
      throw new Error(`Variable ${variableName} not found in IV analysis results`);
    }
    
    return result;
  },

  // Helper function to get available variables from analysis results
  getAvailableVariables(analysisResults: Record<string, IVVariableResult>): string[] {
    return Object.keys(analysisResults).filter(key => {
      const result = analysisResults[key];
      return result && !result.error;
    });
  },

  // Helper method to calculate IV from correlation (improved mock calculation)
  calculateIVFromCorrelation(correlation: number): number {
    // This is an improved mock calculation that provides more realistic IV values
    // In reality, IV calculation is more complex and requires binning
    // Using a more realistic transformation that maps correlation to IV ranges
    
    // Map correlation (0-1) to IV ranges that make sense:
    // - Low correlation (0-0.3) -> Low IV (0-0.05)
    // - Medium correlation (0.3-0.6) -> Medium IV (0.05-0.15)  
    // - High correlation (0.6-0.8) -> High IV (0.15-0.3)
    // - Very high correlation (0.8-1.0) -> Very high IV (0.3-0.5+)
    
    if (correlation < 0.3) {
      return correlation * 0.15; // Low correlation to low IV
    } else if (correlation < 0.6) {
      return 0.045 + (correlation - 0.3) * 0.35; // Medium correlation to medium IV
    } else if (correlation < 0.8) {
      return 0.15 + (correlation - 0.6) * 0.75; // High correlation to high IV
    } else {
      return 0.3 + (correlation - 0.8) * 1.0; // Very high correlation to very high IV
    }
  },

  // Helper method to get IV strength
  getIVStrength(ivValue: number): 'weak' | 'medium' | 'strong' | 'very_strong' {
    if (ivValue < 0.02) return 'weak';
    if (ivValue < 0.1) return 'medium';
    if (ivValue < 0.3) return 'strong';
    return 'very_strong';
  },

  // Helper method to get IV recommendation
  getIVRecommendation(ivValue: number): string {
    if (ivValue < 0.02) return 'Variable has weak predictive power, consider removing';
    if (ivValue < 0.1) return 'Variable has medium predictive power, can be useful';
    if (ivValue < 0.3) return 'Variable has strong predictive power, keep in model';
    return 'Variable has very strong predictive power, essential for model';
  },

  // Mock response for when backend is unavailable
  getMockIVResponse(datasetId: string, targetVariable: string): IVAnalysisResponse {
    const mockVariables = ['age', 'income', 'education', 'experience', 'score'];
    const analysisResults: Record<string, IVVariableResult> = {};
    
    mockVariables.forEach(variable => {
      const ivValue = Math.random() * 0.4; // Random IV between 0 and 0.4
      const ivStrength = this.getIVStrength(ivValue);
      
      analysisResults[variable] = {
        variable_name: variable,
        variable_type: 'numerical',
        iv_value: ivValue,
        iv_strength: ivStrength,
        analysis_result: {
          insights: [`Mock IV analysis for ${variable}`],
          visualization_data: {
            chart_type: 'bar',
            data: {},
          },
        },
        summary: {
          key_insight: `IV: ${ivValue.toFixed(3)} (${ivStrength})`,
          iv_strength: ivStrength,
          predictive_power: this.getIVRecommendation(ivValue),
        },
      };
    });
    
    return {
      success: true,
      message: 'Mock IV analysis completed',
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

  /**
   * Get variables by IV strength
   */
  getVariablesByStrength(
    analysisResults: Record<string, IVVariableResult>,
    strength: 'weak' | 'medium' | 'strong' | 'very_strong'
  ): string[] {
    return Object.keys(analysisResults).filter(
      key => analysisResults[key].iv_strength === strength && !analysisResults[key].error
    );
  },

  /**
   * Get summary statistics for all analyzed variables
   */
  getAnalysisSummary(analysisResults: Record<string, IVVariableResult>) {
    const variables = Object.values(analysisResults);
    const weak = variables.filter(v => v.iv_strength === 'weak' && !v.error);
    const medium = variables.filter(v => v.iv_strength === 'medium' && !v.error);
    const strong = variables.filter(v => v.iv_strength === 'strong' && !v.error);
    const veryStrong = variables.filter(v => v.iv_strength === 'very_strong' && !v.error);
    const errors = variables.filter(v => v.error);

    return {
      total: variables.length,
      weak: weak.length,
      medium: medium.length,
      strong: strong.length,
      veryStrong: veryStrong.length,
      errors: errors.length,
      error_variables: errors.map(v => v.variable_name),
    };
  },

  /**
   * Get IV strength interpretation
   */
  getIVStrengthInterpretation(ivValue: number): { strength: string; description: string } {
    if (ivValue < 0.02) {
      return { strength: 'weak', description: 'Not useful for prediction' };
    } else if (ivValue < 0.1) {
      return { strength: 'medium', description: 'Weak predictive power' };
    } else if (ivValue < 0.3) {
      return { strength: 'strong', description: 'Good predictive power' };
    } else {
      return { strength: 'very_strong', description: 'Very strong predictive power (suspect)' };
    }
  }
};
