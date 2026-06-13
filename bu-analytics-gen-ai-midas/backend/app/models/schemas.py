from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from enum import Enum
from datetime import datetime

class TargetVariableType(str, Enum):
    NUMERICAL = "Numerical"
    CATEGORICAL = "Categorical"

class UploadRequest(BaseModel):
    target_variable: str
    target_variable_type: TargetVariableType
    data_dictionary: Optional[str] = ""
    problem_statement: Optional[str] = ""

class UploadResponse(BaseModel):
    success: bool
    message: str
    dataset_id: Optional[str] = None
    dataset_info: Optional[Dict[str, Any]] = None

class ChatRequest(BaseModel):
    query: str
    dataset_id: str
    agent_context: Optional[str] = None  # "data_insight", "modelling", "data_quality" - helps route ambiguous queries
    
    # Data Quality (QC) specific fields
    qc_mode: Optional[str] = None  # "auto" or "manual"
    treatment_sequence: Optional[List[str]] = None  # Order of treatments
    qc_templates: Optional[Dict[str, Any]] = None  # Uploaded templates for each treatment type
    qc_ui_selections: Optional[Dict[str, Any]] = None  # UI selections (e.g., outlier method dropdown)

class ChatResponse(BaseModel):
    response: Union[str, Dict[str, Any], List[Any]]
    code: str
    suggestions: List[str]
    role: Optional[str] = None
    knowledge_metadata: Optional[Dict[str, Any]] = None  # Contains source_files and use_exl_expertise

class DataStats(BaseModel):
    rows: int
    columns: int
    memory_usage_mb: float
    missing_values: Dict[str, int]
    duplicate_rows: int
    column_types: Dict[str, str]
    target_variable_info: Optional[Dict[str, Any]] = None

class ColumnInfo(BaseModel):
    """Statistical information for a single column"""
    column_name: str
    data_type: str  # Raw pandas dtype (int64, float64, object, etc.)
    column_type: Optional[str] = None  # User-friendly type: 'Numerical', 'Categorical', or 'Date'
    # Optional semantic/logic type and date detection metadata
    logical_type: Optional[str] = None  # e.g. 'Numerical', 'Categorical', 'Date'
    is_date: Optional[bool] = None
    date_detection_reason: Optional[str] = None
    date_detected_format: Optional[str] = None
    date_detection_confidence: Optional[float] = None
    mean: Optional[float] = None
    median: Optional[float] = None
    mode: Optional[Any] = None
    standard_deviation: Optional[float] = None
    variance: Optional[float] = None
    skewness: Optional[float] = None  # Skewness of the distribution
    min_value: Optional[float] = None
    percentile_0: Optional[float] = None  # p0 (minimum)
    percentile_1: Optional[float] = None  # p1
    percentile_5: Optional[float] = None  # p5
    percentile_25: Optional[float] = None  # p25
    percentile_50: Optional[float] = None  # p50 (median)
    percentile_75: Optional[float] = None  # p75
    percentile_95: Optional[float] = None  # p95
    percentile_99: Optional[float] = None  # p99
    percentile_100: Optional[float] = None  # p100 (maximum)
    max_value: Optional[float] = None
    missing_count: int
    unique_count: int
    total_count: int
    # Categorical-specific fields
    top_category: Optional[str] = None  # Most frequent category
    top_category_pct: Optional[float] = None  # Percentage of most frequent category
    lowest_category: Optional[str] = None  # Least frequent category
    lowest_category_pct: Optional[float] = None  # Percentage of least frequent category
    # DateTime-specific fields
    date_min: Optional[str] = None  # Minimum date value (as string)
    date_max: Optional[str] = None  # Maximum date value (as string)
    most_frequent_date: Optional[str] = None  # Most frequent date/value

class ColumnInfoResponse(BaseModel):
    """Response model for column_info API"""
    success: bool
    message: str
    dataset_id: str
    columns_info: List[ColumnInfo]
    total_columns: int
    data_preview: Optional[Dict[str, Any]] = None
    scope: Optional[str] = None  # 'entire', 'train', 'test', 'validation'
    total_rows: Optional[int] = None  # Number of rows for the scope

class ErrorResponse(BaseModel):
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None

class KnowledgeGraphRequest(BaseModel):
    dataset_id: str

class KnowledgeGraphResponse(BaseModel):
    success: bool
    message: str
    html_content: Optional[str] = None
    algorithm_explanation: Optional[str] = None
    relationship_mapping: Optional[str] = None
    usage_instructions: Optional[str] = None
    error: Optional[str] = None
    nodes: Optional[List[Dict[str, Any]]] = None
    categories: Optional[List[Dict[str, str]]] = None
    processing_info: Optional[Dict[str, Any]] = None

class CodeExecutionResponse(BaseModel):
    success: bool
    response: str
    columns_info: Optional[List[ColumnInfo]] = None

# User Authentication Schemas
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    full_name: str = Field(..., min_length=1, max_length=100)
    email: Optional[str] = Field(None, max_length=100)
    password: str = Field(..., min_length=6)
    is_active: bool = Field(True)

class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None

class UserInDB(BaseModel):
    id: int
    username: str
    full_name: str
    email: Optional[str]
    hashed_password: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

class User(BaseModel):
    id: int
    username: str
    full_name: str
    email: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

class UserLogin(BaseModel):
    username: str
    password: str

class TokenData(BaseModel):
    username: Optional[str] = None
    session_id: Optional[str] = None  # JWT claim "sid" when server-side session is used

# Custom Treatment Update Schemas
class CustomTreatmentUpdate(BaseModel):
    dataset_id: str
    custom_treatments: Dict[str, str]  # key: "category-index" or "category", value: custom treatment text

class CustomTreatmentResponse(BaseModel):
    success: bool
    message: str
    updated_plan: Optional[Dict[str, Any]] = None

# Bivariate Analysis Schemas
class BivariateAnalysisAllResponse(BaseModel):
    success: bool
    message: str
    dataset_id: str
    target_variable: str
    total_variables_analyzed: int
    analysis_results: Dict[str, Any]  # Simplified - just store the raw analysis results
    dataset_summary: Dict[str, Any]

class BivariateAnalysisSingleResponse(BaseModel):
    success: bool
    dataset_id: str
    target_variable: str
    variable_name: str
    analysis_result: Dict[str, Any]  # Simplified - just store the raw analysis result

    #------Analyze correlations---------------------
    # ----------------------------------------------    
class CorrelationAnalysisRequest(BaseModel):
    dataset_id: str
    target_variable: str
    correlation_threshold: Optional[float] = 0.05  # Default threshold from knowledge repo
    correlation_types: Optional[List[str]] = ["pearson", "spearman"]  # Default types

class CorrelationResult(BaseModel):
    variable_name: str
    variable_type: str  # "numeric" or "categorical"
    pearson_correlation: Optional[float] = None
    spearman_correlation: Optional[float] = None
    chi_square_statistic: Optional[float] = None
    chi_square_p_value: Optional[float] = None
    cramers_v: Optional[float] = None
    is_significant: bool  # |r| >= threshold
    significance_level: str  # "high", "moderate", "low"

class CorrelationVisualizationData(BaseModel):
    chart_type: str  # "histogram", "scatter", "heatmap", "combo"
    data: Dict[str, Any]  # Chart data structure
    x_axis_label: str
    y_axis_label: str
    title: str
    correlation_value: Optional[float] = None  # Made optional to handle None values
    trend_line_data: Optional[Dict[str, Any]] = None
    bars_data: Optional[Dict[str, Any]] = None  # For combo charts
    line_data: Optional[Dict[str, Any]] = None  # For combo charts

class CorrelationAnalysisResponse(BaseModel):
    success: bool
    message: str
    dataset_id: str
    target_variable: str
    correlation_threshold: float
    total_variables_analyzed: int
    significant_variables: int
    correlation_results: List[CorrelationResult]
    visualization_data: Dict[str, CorrelationVisualizationData]  # Key: variable_name
    dataset_summary: Dict[str, Any]

class SingleVariableCorrelationResponse(BaseModel):
    success: bool
    dataset_id: str
    target_variable: str
    variable_name: str
    correlation_result: CorrelationResult
    visualization_data: CorrelationVisualizationData

class CorrelationHeatmapResponse(BaseModel):
    success: bool
    dataset_id: str
    target_variable: str
    correlation_matrix: Dict[str, Dict[str, float]]
    significant_pairs: List[Dict[str, Any]]  # Pairs with |r| >= threshold
    visualization_data: CorrelationVisualizationData


class CorrelationHeatmapImageResponse(BaseModel):
    success: bool
    image_base64: str
    image_data_uri: str

# Global Model Training Schemas
class ModelAlgorithm(str, Enum):
    RANDOM_FOREST = "random_forest"
    GRADIENT_BOOSTING = "gradient_boosting"
    LOGISTIC_REGRESSION = "logistic_regression"

class ProblemType(str, Enum):
    CLASSIFICATION = "classification"
    REGRESSION = "regression"

class GlobalModelTrainingRequest(BaseModel):
    dataset_id: str
    algorithm: ModelAlgorithm
    k_folds: int = Field(ge=3, le=10, description="Number of folds for cross-validation (3-10)")
    target_variable: Optional[str] = None
    selected_variables: Optional[List[str]] = None  # Independent variables to use for training

class CrossValidationResult(BaseModel):
    fold: int
    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    # Regression metrics
    r2_score: Optional[float] = None
    mse: Optional[float] = None
    rmse: Optional[float] = None
    mae: Optional[float] = None

class ModelPerformanceMetrics(BaseModel):
    # Classification metrics
    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    mean_accuracy: Optional[float] = None
    std_accuracy: Optional[float] = None
    # Regression metrics
    r2_score: Optional[float] = None
    adjusted_r2_score: Optional[float] = None
    mse: Optional[float] = None
    rmse: Optional[float] = None
    mae: Optional[float] = None
    mean_r2: Optional[float] = None
    std_r2: Optional[float] = None
    cross_validation_results: List[CrossValidationResult]

class CodebookSection(BaseModel):
    title: str
    type: str
    content: str

class ModelCodebookResponse(BaseModel):
    success: bool
    algorithm: str
    title: str
    description: str
    sections: List[CodebookSection]

class GlobalModelTrainingResponse(BaseModel):
    success: bool
    message: str
    algorithm: str
    algorithm_resolved: str  # The actual algorithm used (may differ from requested)
    problem_type: ProblemType
    k_folds: int
    performance_metrics: Optional[ModelPerformanceMetrics] = None
    training_time_seconds: Optional[float] = None
    model_id: Optional[str] = None

# Segmentation (CART/CHAID)
class SegmentationMethod(str, Enum):
    CART = "cart"
    CHAID = "chaid"

class SegmentationRequest(BaseModel):
    dataset_id: str
    variables: List[str]
    method: SegmentationMethod = SegmentationMethod.CART
    target_variable: Optional[str] = None
    max_depth: int = Field(default=4, ge=2, le=10)
    min_samples_leaf: int = Field(default=25, ge=5)  # Removed upper limit (le=1000)
    min_segment_size_ratio: Optional[float] = Field(default=None, ge=0.01, le=0.5)
    max_segments: Optional[int] = Field(default=None, ge=2, le=20)

class AutoSegmentationRequest(BaseModel):
    dataset_id: str
    method: SegmentationMethod = SegmentationMethod.CART
    target_variable: Optional[str] = None
    max_depth: int = Field(default=4, ge=2, le=10)
    min_samples_leaf: int = Field(default=25, ge=5)  # Removed upper limit (le=1000)
    min_segment_size_ratio: Optional[float] = Field(default=None, ge=0.01, le=0.5)
    max_segments: Optional[int] = Field(default=None, ge=2, le=20)

# Segment Profiling Schemas
class SegmentProfile(BaseModel):
    segment_id: int
    size: int
    event_rate: float
    feature_distributions: Dict[str, Any]

class StatisticalTestResult(BaseModel):
    test_name: str
    p_value: float
    significant: bool
    threshold: float = 0.05

class StabilityTestResult(BaseModel):
    cross_validation_stability: float
    threshold: float = 0.8
    stable: bool

class SegmentProfilingStep(BaseModel):
    step_name: str
    passed: bool
    details: Dict[str, Any]

class SegmentProfilingResponse(BaseModel):
    success: bool
    message: str
    steps: List[SegmentProfilingStep]
    overall_recommendation: str
    quality_checkpoints: Dict[str, bool]

class SegmentationResponse(BaseModel):
    success: bool
    message: str
    method: str
    variables_used: List[str]
    parameters: Dict[str, Any]
    num_segments: int
    segments: List[Dict[str, Any]]
    viability: Dict[str, Any]
    dataset_shape: Optional[int] = None  # Total rows in dataset used for segmentation
    total_segment_records: Optional[int] = None  # Sum of all segment sizes
    records_match: Optional[bool] = None  # Verification that sum equals dataset shape


# =============================================================================
# Segmentation Agent Schemas (4-Mode Architecture)
# Supports: Pre-existing Identifier (C1), Variable-Driven (C2), 
#           Manual Rules (C3), Auto Segmentation
# =============================================================================

class SegmentationMode(str, Enum):
    """Four segmentation modes as defined in the Segmentation Agent Plan"""
    PRE_EXISTING = "pre_existing"       # C1: Use existing segment column
    VARIABLE_DRIVEN = "variable_driven"  # C2: Platform finds optimal cutoffs
    MANUAL_RULES = "manual_rules"        # C3: SQL-style manual rule builder
    AUTO = "auto"                        # Fully automated segmentation


class VariablePriority(BaseModel):
    """Variable priority ordering for C2 and C3 modes.
    Primary splitter is always used for root split regardless of IV."""
    primary: str
    secondary: Optional[str] = None
    tertiary: Optional[str] = None


class TertiaryPromotionSuggestion(BaseModel):
    """
    Plan Section 3.4 — when the secondary splitter fails the significance gate,
    structured guidance for the modeler (tertiary promotion vs stop at primary).
    JSON field `type` matches auto pipeline / frontend promotion panels.
    """
    type: str  # promote_tertiary | stop_at_primary
    message: str
    failed_variable: Optional[str] = None
    suggested_variable: Optional[str] = None
    suggested_p_value: Optional[float] = None
    secondary_significant: Optional[bool] = None


class PromotionSuggestion(BaseModel):
    """
    Plan Section 3.4 — same semantics as auto pipeline PromotionSuggestion (list form for API).
    """
    suggestion_type: str  # promote_tertiary | stop_at_primary | stop_at_secondary
    message: str
    failed_variable: Optional[str] = None
    suggested_variable: Optional[str] = None
    suggested_p_value: Optional[float] = None


class RuleCondition(BaseModel):
    """Single condition in a segment rule (e.g., variable_A >= 70)"""
    variable: str
    operator: str  # "<=", ">=", "<", ">", "=", "!=", "IN", "NOT IN", "BETWEEN"
    value: Any  # Single value or list for IN/NOT IN, tuple for BETWEEN
    

class ManualSegmentRule(BaseModel):
    """Definition of a single segment in C3 Manual Rules mode"""
    segment_name: str
    conditions: List[RuleCondition] = Field(default_factory=list)
    logic: str = "AND"  # "AND" or "OR" between conditions
    catch_all: bool = False  # True = assign all rows not matched by prior segments (plan §6.2)


class SegmentDetail(BaseModel):
    """Detailed information for a single segment (used in validation results)"""
    segment_id: int
    segment_name: str
    rule_definition: str
    record_count: int
    pct_of_population: float
    event_count: int
    event_rate: float
    event_rate_ci_lower: Optional[float] = None  # Wilson Score 95% CI lower bound
    event_rate_ci_upper: Optional[float] = None  # Wilson Score 95% CI upper bound
    woe: float
    iv_contribution: float


class SegmentFlag(BaseModel):
    """Flag for segment quality issues"""
    segment_name: str
    flag_type: str  # "low_observations", "low_events", "dominant", "tiny"
    severity: str   # "amber", "red"
    message: str


class MergeRecommendation(BaseModel):
    """Recommendation to merge two segments based on three-condition framework"""
    segment_a: str
    segment_b: str
    failed_condition: str  # "reliability", "practical_separation", "validation"
    is_bootstrap_borderline: bool = False  # True = point separation passes but bootstrap CIs overlap (plan §9.4)
    event_rate_a: float
    event_rate_b: float
    event_rate_diff: float
    practical_threshold: float
    merged_record_count: int
    merged_event_rate: float
    iv_before: float
    iv_after: float
    iv_change_pct: float
    explanation: str  # LLM-generated plain language explanation


class BootstrapStabilityResult(BaseModel):
    """Bootstrap stability diagnostics results"""
    bootstrap_runs: int
    rank_order_preservation_rate: float  # e.g., 0.93 means 93% of runs preserved order
    confidence_bands: Dict[str, Dict[str, float]]  # segment_name -> {lower_5pct, upper_95pct}
    confidence_bands_overlap: bool


class OutOfSampleValidation(BaseModel):
    """Out-of-sample validation results per Section 11 of the plan"""
    partition_used: str  # "holdout", "test", or "none"
    rank_order_preserved: bool
    max_event_rate_drift: float
    max_size_drift: float
    event_rate_drift_flagged: bool = False  # True if max_event_rate_drift > 3pp
    size_drift_flagged: bool = False  # True if max_size_drift > 5pp
    chi_squared_p: float
    chi_squared_significant: bool = True  # True if p < 0.05 on OOS data
    segment_comparison: List[Dict[str, Any]]  # Train vs OOS per segment


class ValidationSuiteResult(BaseModel):
    """Complete validation suite results for a segmentation scheme"""
    chi_squared_p: float
    chi_squared_significant: bool
    total_iv: float
    iv_category: str  # "weak" (<0.05), "moderate" (0.05-0.10), "strong" (0.10-0.50), "suspicious" (>0.50)
    cramers_v: float
    cramers_v_meaningful: bool  # True if > 0.10
    recommendation_category: str  # "strong", "exploratory", "weak"
    recommendation_explanation: str  # LLM-generated narrative
    segment_flags: List[SegmentFlag]
    merge_recommendations: List[MergeRecommendation]
    stability: Optional[BootstrapStabilityResult] = None
    oos_validation: Optional[OutOfSampleValidation] = None


class TopVariableBySegment(BaseModel):
    """Top variable IV for a specific segment"""
    variable: str
    overall_iv: float
    segment_iv: float
    iv_category: str  # "strong" (>0.30), "moderate" (0.10-0.30), "weak" (<0.10)


class VariableRelevanceMatrix(BaseModel):
    """Top 10 variables by IV per segment"""
    variables: List[str]
    overall_iv: Dict[str, float]  # variable -> overall IV
    segment_iv: Dict[str, Dict[str, float]]  # segment_name -> {variable -> IV}


class UnifiedSegmentationRequest(BaseModel):
    """Unified request for all 4 segmentation modes"""
    dataset_id: str
    mode: SegmentationMode
    target_variable: Optional[str] = None
    
    # C1: Pre-existing Identifier fields
    segment_column: Optional[str] = None
    
    # C2: Variable-Driven fields
    variable_priority: Optional[VariablePriority] = None
    method: SegmentationMethod = SegmentationMethod.CART
    min_segment_size: int = Field(default=1000, ge=100)
    min_segment_size_mode: str = "absolute"  # "absolute" or "percentage"
    min_segment_size_pct: float = Field(default=5.0, ge=1.0, le=50.0)
    max_segments: int = Field(default=5, ge=2, le=10)
    max_depth: int = Field(default=3, ge=1, le=3)
    
    # C3: Manual Rules fields
    manual_rules: Optional[List[ManualSegmentRule]] = None


class RuleValidationResult(BaseModel):
    """Real-time validation result for C3 manual rules"""
    coverage_pct: float
    unassigned_records: int
    is_mutually_exclusive: bool
    overlap_count: int
    empty_segments: List[str]
    segment_counts: Dict[str, int]  # segment_name -> record count


class SegmentationSchemeMetadata(BaseModel):
    """Complete metadata for a saved segmentation scheme"""
    scheme_id: int
    column_name: str
    mode: SegmentationMode
    variables: List[str]
    manual_rules: Optional[List[ManualSegmentRule]] = None
    variable_priority: Optional[VariablePriority] = None
    variable_selection_method: Optional[str] = None  # For auto mode
    tree_method: Optional[str] = None
    max_depth: Optional[int] = None
    constraints_applied: Dict[str, Any]
    segments: List[SegmentDetail]
    total_iv: float
    chi_squared_p: float
    cramers_v: float
    merge_history: List[str]
    cutoff_edits: List[str]
    validation: ValidationSuiteResult
    # Plan §12.3 — explicit snapshots (also nested under validation where applicable)
    stability: Optional[BootstrapStabilityResult] = None
    holdout_validation: Optional[OutOfSampleValidation] = Field(
        default=None,
        description="OOS / holdout validation snapshot (same as validation.oos_validation when present)",
    )
    recommendation_category: str
    created_at: datetime


class UnifiedSegmentationResponse(BaseModel):
    """Unified response for all segmentation modes"""
    success: bool
    message: str
    mode: SegmentationMode
    method: Optional[str] = None
    variables_used: List[str]
    variable_priority: Optional[VariablePriority] = None
    parameters: Dict[str, Any]
    num_segments: int
    segments: List[SegmentDetail]
    validation: ValidationSuiteResult
    variable_relevance: Optional[VariableRelevanceMatrix] = None
    dataset_shape: Optional[int] = None
    total_segment_records: Optional[int] = None
    records_match: Optional[bool] = None
    merge_history: List[str] = Field(default_factory=list)
    cutoff_edits: List[str] = Field(default_factory=list)
    # C2 variable-driven: Section 3.4 tertiary promotion when secondary fails significance
    tertiary_promotion_suggestion: Optional[TertiaryPromotionSuggestion] = None
    promotion_suggestions: Optional[List[PromotionSuggestion]] = None
    # For Auto mode: scheme comparison
    auto_candidates: Optional[List[Dict[str, Any]]] = None
    selected_scheme_rank: Optional[int] = None
    manual_rules: Optional[List[ManualSegmentRule]] = None


class AddToDataRequest(BaseModel):
    """Request to save a segmentation scheme to the dataset"""
    dataset_id: str
    segmentation_result: UnifiedSegmentationResponse
    scheme_name: Optional[str] = None  # Optional custom name
    # If set, duplicate POSTs with the same key return the original saved scheme (plan §15 idempotent retries)
    idempotency_key: Optional[str] = None


class AddToDataResponse(BaseModel):
    """Response after saving a segmentation scheme"""
    success: bool
    message: str
    scheme_id: int
    column_name: str
    metadata: SegmentationSchemeMetadata


class MergeSegmentsRequest(BaseModel):
    """Request to merge two segments into one"""
    dataset_id: str
    segment_a_id: int  # First segment ID to merge
    segment_b_id: int  # Second segment ID to merge
    new_segment_name: Optional[str] = None  # Optional custom name for merged segment
    current_segmentation: Dict[str, Any]  # Current segmentation result to modify


class MergeImpact(BaseModel):
    """Impact statistics from merging two segments"""
    merged_segment_name: str
    combined_records: int
    combined_events: int
    combined_event_rate: float
    combined_pct_of_population: float
    iv_before_merge: float
    iv_after_merge: float
    iv_change: float
    iv_change_pct: float


class MergeSegmentsResponse(BaseModel):
    """Response after merging segments"""
    success: bool
    message: str
    merged_segment: SegmentDetail  # The new merged segment
    merge_impact: MergeImpact  # Statistics about the merge
    updated_segmentation: Dict[str, Any]  # Full updated segmentation result
    num_segments_after: int
    can_undo: bool = True


class CutoffEditRequest(BaseModel):
    """Request to edit a segment cutoff value"""
    dataset_id: str
    segment_id: int  # ID of segment whose cutoff is being edited
    variable: str  # Variable name (e.g., "age", "income")
    operator: str  # Operator (e.g., ">", "<=", "==")
    old_value: Any  # Numeric threshold or category string for categorical edits
    new_value: Any
    preview_only: bool = True  # If True, only return impact preview without applying
    current_segmentation: Dict[str, Any]  # Current segmentation result


class MoveCategoricalValueRequest(BaseModel):
    """Move one category of a variable from one segment's rule to another (plan §5.4 / C3 parity)."""
    dataset_id: str
    variable: str
    category_value: str
    from_segment_id: int
    to_segment_id: int
    current_segmentation: Dict[str, Any]


class MoveCategoricalValueResponse(BaseModel):
    success: bool
    message: str
    updated_segmentation: Dict[str, Any]
    can_undo: bool = True


class CutoffEditImpact(BaseModel):
    """Impact statistics from editing a cutoff value"""
    segment_id: int
    variable: str
    old_rule: str
    new_rule: str
    records_moved_out: int  # Records that would leave this segment
    records_moved_in: int  # Records that would enter this segment
    new_record_count: int
    new_event_count: int
    new_event_rate: float
    new_pct_of_population: float
    iv_before: float
    iv_after: float
    iv_change: float
    below_min_size: bool  # Warning flag if segment falls below minimum


class CutoffEditResponse(BaseModel):
    """Response after editing a cutoff value"""
    success: bool
    message: str
    preview_only: bool
    impact: CutoffEditImpact  # Impact statistics
    affected_segments: List[int]  # IDs of segments affected by the change
    updated_segmentation: Optional[Dict[str, Any]] = None  # Only if preview_only=False
    can_undo: bool = True


class SchemeRegistryEntry(BaseModel):
    """Entry in the scheme registry panel"""
    scheme_id: int
    column_name: str
    mode: SegmentationMode
    variables: List[str]
    variable_priority: Optional[VariablePriority] = None
    tree_method: Optional[str] = None
    variable_selection_method: Optional[str] = None
    segment_count: int
    total_iv: float
    recommendation_category: str
    created_at: datetime


class SchemeRegistryResponse(BaseModel):
    """Response listing all saved segmentation schemes"""
    success: bool
    dataset_id: str
    schemes: List[SchemeRegistryEntry]
    total_schemes: int


class SegmentationSchemeDetailResponse(BaseModel):
    """Full stored audit metadata for one scheme (registry View details)."""
    success: bool
    dataset_id: str
    scheme_id: int
    metadata: Optional[SegmentationSchemeMetadata] = None
    message: Optional[str] = None


class DatasetPreviewResponse(BaseModel):
    success: bool
    message: str
    preview_data: Optional[Dict[str, Any]] = None
    shape: Optional[Dict[str, int]] = None

# Project Management Schemas
class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Project name (required)")
    description: Optional[str] = Field(None, max_length=500, description="Project description (optional)")

class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Project name")
    description: Optional[str] = Field(None, max_length=500, description="Project description")

class Project(BaseModel):
    id: str = Field(..., description="Project UUID")
    name: str
    description: Optional[str]
    user_id: int = Field(..., description="ID of the user who created the project")
    created_at: datetime
    updated_at: datetime

class ProjectInDB(BaseModel):
    id: str
    name: str
    description: Optional[str]
    user_id: int
    created_at: datetime
    updated_at: datetime

class ProjectResponse(BaseModel):
    success: bool
    message: str
    project: Optional[Project] = None

class ProjectListResponse(BaseModel):
    success: bool
    message: str
    projects: List[Project] = []
    total_count: int




# Dataset Type Classification Schemas (used by dataset-type-classification-by-id API)
class DatasetType(str, Enum):
    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    TIME_SERIES = "time_series"
    OTHERS = "others"

class VariableDefinition(BaseModel):
    definition: str
    category: str
    business_context: str

class VariableDefinitionsRequest(BaseModel):
    columns: List[str]

class VariableDefinitionsResponse(BaseModel):
    success: bool
    definitions: Dict[str, VariableDefinition]


class DatasetTypeClassificationRequest(BaseModel):
    # This will be handled as a file upload in the API endpoint
    pass  # File will be passed as UploadFile parameter


class DatasetTypeClassificationResponse(BaseModel):
    success: bool
    message: str
    dataset_id: Optional[str] = Field(default="", description="Dataset ID if available")
    dataset_type: DatasetType
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score between 0 and 1")
    reasoning: str = Field(description="Explanation of why this dataset type was identified")
    characteristics: Dict[str, Any] = Field(description="Key characteristics that led to this classification")
    recommendations: List[str] = Field(description="Recommendations based on the dataset type")


# =======================
# Feature Engineering API
# =======================

class FeatureTransformationSummaryItem(BaseModel):
    new_variable_name: str
    var_type: str
    variable_definition: str
    transformation_methods: str
    code_logic: str


class FeatureTransformationResponse(BaseModel):
    success: bool
    dataset_id: str
    response_data: List[FeatureTransformationSummaryItem]
    error: Optional[str] = None


# =======================
# Variable Review API
# =======================

class ReasonBadge(str, Enum):
    """Classification badges for variable review results."""
    LEAKAGE = "Leakage"
    IDENTIFIER = "Identifier"
    LOW_VALUE = "Low-value"
    FLAGGED = "Flagged"
    CLEAN = "Clean"


class VariableReviewRow(BaseModel):
    """Single row in variable review results table."""
    variable: str
    auc: str  # Display value: "0.97" or "--"
    auc_value: Optional[float] = None  # Numeric value for sorting
    flags: str  # Display: "L2, L3, L5" or "L1 (x3)" or "--"
    reason: ReasonBadge
    pre_selected: bool
    row_class: str  # "row-preselected", "row-flagged", "row-clean"
    detail_reasons: List[str] = []
    layer_flags: List[str] = []
    cardinality_ratio: Optional[float] = None
    null_rate: Optional[float] = None
    null_rate_diff: Optional[float] = None


class VariableReviewSummary(BaseModel):
    """Summary statistics for variable review."""
    total: int
    pre_selected: int
    flagged: int
    clean: int


class VariableReviewRequest(BaseModel):
    """Request model for variable review API."""
    dataset_id: str
    target_col: str
    sample_id_col: Optional[str] = None
    weight_col: Optional[str] = None
    auc_threshold: float = Field(default=0.70, ge=0.5, le=1.0)
    near_perfect_auc_threshold: float = Field(default=0.95, ge=0.8, le=1.0)
    correlation_threshold: float = Field(default=0.70, ge=0.5, le=1.0)
    missingness_diff_threshold: float = Field(default=0.10, ge=0.01, le=0.5)
    leaker_correlation_threshold: float = Field(default=0.85, ge=0.5, le=1.0)


class VariableReviewResponse(BaseModel):
    """Response model for variable review API."""
    success: bool
    message: str
    rows: List[VariableReviewRow] = []
    summary: Optional[VariableReviewSummary] = None
    pipeline_time_ms: Optional[float] = None


class ApplyVariableRemovalRequest(BaseModel):
    """Request model for applying variable removal."""
    dataset_id: str
    variables_to_remove: List[str]


class ApplyVariableRemovalResponse(BaseModel):
    """Response model for applying variable removal."""
    success: bool
    message: str
    removed_count: int
    remaining_columns: int


# ==================== DATA QUALITY SCORE (DQS) MODELS ====================

class DQSCompletenessDetails(BaseModel):
    """Details for Completeness dimension"""
    base_score: float
    row_sparseness_penalty: float
    columns_with_high_missing: int
    column_fill_rates: Optional[Dict[str, float]] = None
    sparse_row_percentage: float

class DQSConsistencyDetails(BaseModel):
    """Details for Consistency dimension"""
    type_score: float
    format_score: float
    placeholder_score: float
    range_score: float
    formatting_issues: int
    placeholder_count: int
    invalid_range_count: int
    placeholder_columns: Optional[List[str]] = None
    invalid_range_columns: Optional[List[str]] = None

class DQSStructuralDetails(BaseModel):
    """Details for Structural Integrity dimension"""
    constant_columns: int
    constant_column_names: List[str]
    near_constant_columns: int
    near_constant_column_names: List[str]
    duplicate_columns: int
    duplicate_column_names: List[str]

class DQSUniquenessDetails(BaseModel):
    """Details for Uniqueness dimension"""
    duplicate_row_count: int
    duplicate_row_percentage: float
    total_rows: int

class DQSTargetReadiness(BaseModel):
    """Target variable readiness (informational)"""
    target_variable: Optional[str] = None
    target_missing_rate: Optional[float] = None
    target_missing_count: Optional[int] = None
    event_rate: Optional[float] = None
    class_distribution: Optional[Dict[str, int]] = None

class DQSDimension(BaseModel):
    """Single DQS dimension with score and details"""
    score: float
    weight: float
    weighted_contribution: float
    details: Union[DQSCompletenessDetails, DQSConsistencyDetails, DQSStructuralDetails, DQSUniquenessDetails]

class DQSResponse(BaseModel):
    """Full Data Quality Score response"""
    success: bool
    message: str
    dataset_id: str
    composite_score: float
    score_label: str  # Excellent, Good, Fair, Poor
    completeness: DQSDimension
    consistency: DQSDimension
    structural_integrity: DQSDimension
    uniqueness: DQSDimension
    target_readiness: Optional[DQSTargetReadiness] = None
    calculated_at: datetime
    total_rows: int
    total_columns: int


# ---------------------------------------------------------------------------
# RFE (Step 3) + Feature Review & Override (Step 4) schemas
# ---------------------------------------------------------------------------
# Per project rule: Steps 1-4 always operate on the whole training partition.
# The API accepts `segment_id` for forward-compat only and the backend ignores it.


class RfePrecomputedMetric(BaseModel):
    """One metric value forwarded from the Step 2 screener output."""
    iv: Optional[float] = None
    orig_vif: Optional[float] = None
    abs_corr: Optional[float] = None
    missing_pct: Optional[float] = None
    signed_corr: Optional[float] = None


class RfeWorkingSet(BaseModel):
    """Step 2 -> Step 3 handoff: locked variables + screener-selected variables."""
    locked: List[str] = Field(default_factory=list)
    screened: List[str] = Field(default_factory=list)
    precomputed_metrics: Dict[str, RfePrecomputedMetric] = Field(default_factory=dict)


class RfeStartRequest(BaseModel):
    dataset_id: str
    target: str
    working_set: RfeWorkingSet
    weight_col: Optional[str] = None
    # Accepted but deliberately ignored by the backend (whole-train-only rule).
    segment_id: Optional[str] = None


class RfeStartResponse(BaseModel):
    job_id: str
    mode: str  # "local" | "redis"


class RfeFeatureImportance(BaseModel):
    variable: str
    shap_importance: float
    native_importance: float
    shap_rank: int


class RfeIterationRecord(BaseModel):
    iteration: int
    feature_count: int
    features_in: List[str]
    features_dropped: List[str]
    elimination_band_label: str
    cv_auc: float
    test_auc: float
    relative_delta_from_prev: Optional[float] = None
    importances: List[RfeFeatureImportance]
    locked_zero_importance_flags: List[str] = Field(default_factory=list)
    stop_reason: Optional[str] = None
    is_best: bool = False
    timestamp_epoch: float = 0.0


class RfeStatusResponse(BaseModel):
    job_id: str
    status: str
    message: str = ""
    current_iteration: int = 0
    total_features: int = 0
    best_iteration: int = -1
    latest_cv_auc: Optional[float] = None
    iteration_count: int = 0
    heartbeat_at: float = 0.0
    error: Optional[str] = None


class RfeVariableRow(BaseModel):
    variable: str
    locked: bool
    status: str  # "retained" | "dropped"
    drop_iteration: Optional[int] = None
    iv: Optional[float] = None
    orig_vif: Optional[float] = None
    nvar_vif: Optional[float] = None
    abs_corr_target: Optional[float] = None
    shap_importance_best: Optional[float] = None
    rank_trajectory: List[Optional[int]] = Field(default_factory=list)
    suggested_monotone: int = 0
    bivariate_corr: Optional[float] = None


class RfeResultResponse(BaseModel):
    job_id: str
    dataset_id: str
    target: str
    starting_feature_count: int
    final_feature_count: int
    best_iteration: int
    total_iterations: int
    stop_reason: str
    best_cv_auc: float
    best_test_auc: float
    iterations: List[RfeIterationRecord]
    rows: List[RfeVariableRow]
    rolled_back_from_iteration: Optional[int] = None


class RfeOverridePayload(BaseModel):
    include: List[str] = Field(default_factory=list)
    exclude: List[str] = Field(default_factory=list)


class RfeFinalizeRequest(BaseModel):
    job_id: str
    overrides: RfeOverridePayload = Field(default_factory=RfeOverridePayload)
    monotone: Dict[str, int] = Field(default_factory=dict)  # var -> -1, 0, +1


class RfeFinalizeResponse(BaseModel):
    success: bool
    job_id: str
    dataset_id: str
    target: str
    features: List[str]
    locked: List[str]
    monotone: Dict[str, int]
    final_vifs: Dict[str, float]
    finalized_at_epoch: float


class RfeMonotoneResponse(BaseModel):
    """Read-only payload consumed by Step 5 training config."""
    dataset_id: str
    job_id: Optional[str] = None
    features: List[str] = Field(default_factory=list)
    locked: List[str] = Field(default_factory=list)
    monotone: Dict[str, int] = Field(default_factory=dict)
    finalized_at_epoch: Optional[float] = None


class CrossAlgorithmRecommendationRequest(BaseModel):
    """Shortlisted models (max 2 per algorithm) + optional LR sign-validation digest for Step 6 narrative."""

    problem_type: str = "classification"
    candidates: List[Dict[str, Any]] = Field(default_factory=list)
    lr_digest: Optional[List[Dict[str, Any]]] = None


class CrossAlgorithmRecommendationResponse(BaseModel):
    success: bool
    summary: str = ""
    error: Optional[str] = None