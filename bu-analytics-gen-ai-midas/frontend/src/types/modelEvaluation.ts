/**
 * Model Evaluation Types - MEEA Integration
 * Types for comprehensive model evaluation and error analysis
 */

export interface EvaluationModel {
  id: string;
  name: string;
  model_type: string;
  task_type: 'classification' | 'regression';
  training_date: string;
  status: string;
  color: string;
  description?: string;
  created_at: string;
  // Optional metadata used to distinguish global vs segment models in the UI
  dataset_id?: string;
  is_segment_model?: boolean;
  segment_id?: string;
}

export interface PerformanceMetrics {
  id?: string;
  model_id?: string;
  accuracy?: number;
  precision?: number;
  recall?: number;
  f1_score?: number;
  auc_roc?: number;
  auc_pr?: number;
  log_loss?: number;
  confusion_matrix?: number[][];
  class_metrics?: Record<string, ClassMetric>;
  // Regression metrics
  mse?: number;
  rmse?: number;
  mae?: number;
  r2?: number;
  mape?: number;
  max_error?: number;
  created_at?: string;

  // Train/Test split metrics (optional - populated when available from backend)
  train_accuracy?: number;
  test_accuracy?: number;
  train_precision?: number;
  test_precision?: number;
  train_recall?: number;
  test_recall?: number;
  train_f1_score?: number;
  test_f1_score?: number;
  train_auc_roc?: number;
  test_auc_roc?: number;
  train_auc_pr?: number;
  test_auc_pr?: number;
  train_log_loss?: number;
  test_log_loss?: number;

  // Monotonicity/decile diagnostics
  monotonicity_results?: MonotonicityResults;
}

export interface ClassMetric {
  precision: number;
  recall: number;
  f1_score: number;
  support: number;
}

export interface FeatureImportance {
  id?: string;
  model_id?: string;
  feature_name: string;
  shap_importance: number;
  permutation_importance: number;
  gain_importance: number;
  rank: number;
  avg_importance?: number;
  created_at?: string;
}

export interface GranularAccuracy {
  id?: string;
  model_id?: string;
  variable: string;
  segment: string;
  granularity_level: string;
  accuracy: number;
  sample_count: number;
  precision: number;
  recall: number;
  f1_score: number;
  confusion_matrix?: number[][];
  created_at?: string;
  // Segment information fields
  category_value?: string;  // For categorical: the category name
  value_range?: string;  // For continuous: formatted range string (e.g., "0.0 to 1.5")
  min_value?: number;  // For continuous: lower boundary
  max_value?: number;  // For continuous: upper boundary
  grouped_categories?: string[];  // For grouped categorical segments
  is_continuous?: boolean;  // Flag to indicate if this is a continuous variable
}

export interface ErrorPattern {
  id?: string;
  model_id?: string;
  error_type: 'false_positive' | 'false_negative' | 'high_confidence_error';
  count: number;
  percentage: number;
  avg_confidence?: number;
  created_at?: string;
}

export interface PredictionConfidence {
  id?: string;
  model_id?: string;
  bin_start: number;
  bin_end: number;
  count: number;
  accuracy: number;
  avg_confidence: number;
  created_at?: string;
}

export interface ExplainabilityData {
  id?: string;
  model_id?: string;
  data_type: 'roc_curve' | 'pr_curve' | 'shap_summary' | 'shap_waterfall' | 'pdp' | 'lime_sample';
  data_source?: 'train' | 'test';  // NEW: Track which dataset was used
  feature_name?: string;
  values: any;
  metadata?: Record<string, any>;
  created_at?: string;
}

export interface ROCCurveData {
  fpr: number[];
  tpr: number[];
  thresholds: number[];
  auc: number;
}

export interface PRCurveData {
  precision: number[];
  recall: number[];
  thresholds: number[];
  avg_precision: number;
}

export interface SHAPData {
  feature_importance: Array<{
    feature_name: string;
    importance: number;
  }>;
  // OPTIMIZATION: Removed unused 'summary_plot_data' field (was never used in frontend)
  // Frontend uses per-feature entries for beeswarm plots instead
}

export interface PDPData {
  feature_name: string;
  grid_values: number[];
  pd_values: number[];
}

export interface ColumnStats {
  dtype: string;
  variable_type: 'categorical' | 'continuous';
  unique_count: number;
  total_count: number;
  missing_count: number;
  missing_pct: number;
  // Numeric stats (only for continuous)
  min?: number;
  max?: number;
  mean?: number;
  std?: number;
  median?: number;
  q25?: number;
  q75?: number;
  // Categorical stats
  top_categories?: Array<{ value: string; count: number }>;
  num_categories?: number;
}

export interface ModelEvaluationData {
  model: EvaluationModel;
  performance_metrics: PerformanceMetrics;
  feature_importance: FeatureImportance[];
  granular_accuracy: GranularAccuracy[];
  granular_accuracy_train?: GranularAccuracy[];
  error_patterns: ErrorPattern[];
  prediction_confidence: PredictionConfidence[];
  explainability_data: ExplainabilityData[];
  monotonicity_analysis?: Record<string, MonotonicityAnalysis>;
  monotonicity_results?: MonotonicityResults;
  used_features?: string[];
  column_stats?: Record<string, ColumnStats>;
  // Convenience field: maps from model.task_type for easier access
  problem_type?: 'classification' | 'regression' | 'unknown';
}

export interface ModelComparisonData {
  comparison_count: number;
  models: ModelEvaluationData[];
}

export interface MonotonicityAnalysis {
  feature_name: string;
  is_monotonic: boolean;
  direction: 'increasing' | 'decreasing' | 'non-monotonic';
  feature_range: number[];
  predictions: number[];
}

export interface PSIBreakdownRow {
  Bin: number;
  Bin_Range: string;
  Bin_Start: number;
  Bin_End: number;
  Expected_Count: number;
  Expected_Pct: number;
  Actual_Count: number;
  Actual_Pct: number;
  Difference_Pct: number;
  PSI_Contribution: number;
}

export interface CSIRow {
  Variable: string;
  CSI: number;
  Status: 'Stable' | 'Moderate' | 'Significant';
}

export interface MonotonicityResults {
  deciles: Array<Record<string, any>>;
  monotonicity_score: number;
  monotonicity_pass: boolean;
  monotonicity_violations: Array<{
    from_decile: number;
    to_decile: number;
    drop: number;
  }>;
  psi?: number | null;
  psi_breakdown?: PSIBreakdownRow[] | null;
  csi?: CSIRow[] | null;
  ks: number;
  ks_threshold: number;
  ks_tpr: number;
  ks_fpr: number;
  ks_decile: number;
  ks_from_deciles: number;
  auc: number;
  gini: number;
  overall_bad_rate: number;
  lift_top_decile?: number | null;
}

// API Response types
export interface ModelEvaluationResponse {
  success: boolean;
  model_id: string;
  evaluation_data: ModelEvaluationData;
}

export interface ModelListResponse {
  success: boolean;
  count: number;
  models: EvaluationModel[];
}

export interface ModelComparisonResponse {
  success: boolean;
  comparison_count: number;
  models: ModelEvaluationData[];
}

