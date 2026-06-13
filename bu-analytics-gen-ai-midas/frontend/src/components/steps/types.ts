// Common types shared across step components

export interface ChatMessage {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

// Exclusion Rules types
export type ExclusionColumnType = 'Numeric' | 'Categorical' | 'Date' | 'Boolean';

export interface ExclusionCondition {
  id: string;
  column: string;
  columnType: ExclusionColumnType;
  operator: string;
  value: string | number | string[] | [number, number] | [string, string] | null;
  connector: 'AND' | 'OR';
}

export interface ExclusionGroup {
  id: string;
  conditions: ExclusionCondition[];
}

export interface WaterfallRow {
  step: string;
  label?: string;
  removed: number | string;
  remaining: number;
  eventRate: number | null;
}

export interface ExclusionWarning {
  level: 'amber' | 'red' | 'block';
  message: string;
}

export interface ExclusionPreviewResponse {
  waterfall: WaterfallRow[];
  warnings: ExclusionWarning[];
}

export interface DatasetAnalysis {
  columns: DatasetColumnInfo[];
  suggestedTargetVariable: string | null;
  totalRows: number;
  totalColumns: number;
}

export interface DatasetColumnInfo {
  name: string;
  type: 'Numerical' | 'Categorical';
  pandas_type: string;
  unique_count: number;
  missing_count: number;
  sample_values?: Record<string, number>;
  numerical_stats?: {
    min: number | null;
    max: number | null;
    mean: number | null;
    missing_count: number;
  };
}

export interface DatasetConfig {
  target_variable: string;
  target_variable_type: 'Numerical' | 'Categorical';
  dataset_structure_type: 'classification' | 'regression' | 'time_series' | 'others';
  problem_statement: string;
  data_dictionary: string;
}

// Step component prop types
export interface Step1ObjectivesDataProps {
  selectedDataSources: any[];
  onDataSourceSelect: (dataSource: any) => void;
  onRemoveDataSource: (index: number) => void;
  showDataSourceSelectionModal: boolean;
  setShowDataSourceSelectionModal: (show: boolean) => void;
  datasetAnalysis: DatasetAnalysis | null;
  isAnalyzingDataset: boolean;
  isUploadingDataset: boolean;
  datasetConfig: DatasetConfig | null;
  setDatasetConfig: (config: any) => void;
  activeDatasetId: string | null;
  pendingDatasetId?: string | null;
  setActiveDatasetId: (id: string | null) => void;
  showDatasetOverview: boolean;
  setShowDatasetOverview: (show: boolean) => void;
  chatInputs: {[key: number]: string};
  setChatInputs: (inputs: any) => void;
  dataDictionaryFile: File | null;
  setDataDictionaryFile: (file: File | null) => void;
  onDataDictionaryFileSelect: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onRemoveDataDictionaryFile: () => void;
  onSubmitDataset: () => Promise<void>;
}

export interface Step2DataQCProps {
  selectedDataSources: any[];
  onDataSourceSelect: (dataSource: any) => void;
  onRemoveDataSource: (index: number) => void;
  showDataSourceSelectionModal: boolean;
  setShowDataSourceSelectionModal: (show: boolean) => void;
  activeDatasetId: string | null;
  selectedQCTasks: string[];
  setSelectedQCTasks: (tasks: string[]) => void;
  customQCTask: string;
  setCustomQCTask: (task: string) => void;
  onAutoQC: () => Promise<void>;
  onStandardQC: () => Promise<void>;
  onQCTaskToggle: (task: string, checked: boolean) => void;
  renderStepChat: (step: number) => React.ReactNode;
}

export interface Step3DataInsightsProps {
  selectedInsightSteps: string[];
  setSelectedInsightSteps: (steps: string[]) => void;
  onAutoDataInsights: () => Promise<void>;
  onStandardDataInsights: (stepsOverride?: string[]) => Promise<void>;
  onInsightStepToggle: (step: string, checked: boolean) => void;
  renderStepChat: (step: number) => React.ReactNode;
  activeDatasetId?: string | null;
  datasetAnalysis?: { totalRows: number } | null;
  autoInsightStepStatus: Record<string, 'idle' | 'running' | 'done' | 'absent' | 'error'>;
  insightsMode: 'auto' | 'standard';
  onInsightsModeChange: (mode: 'auto' | 'standard') => void;
}

export interface Step4FeatureEngineeringProps {
  selectedFeatureSteps: string[];
  setSelectedFeatureSteps: (steps: string[]) => void;
  onAutoFeatureEngineering: () => Promise<void>;
  onStandardFeatureEngineering: () => Promise<void>;
  onFeatureStepToggle: (step: string, checked: boolean) => void;
  renderStepChat: (step: number) => React.ReactNode;
}

export interface Step5DataSplittingProps {
  selectedSplitSteps: string[];
  setSelectedSplitSteps: (steps: string[]) => void;
  onAutoDataSplitting: () => Promise<void>;
  onStandardDataSplitting: () => Promise<void>;
  onSplitStepToggle: (step: string, checked: boolean) => void;
  renderStepChat: (step: number) => React.ReactNode;
}

export interface Step6AlgorithmSelectionProps {
  selectedAlgorithmSteps: string[];
  setSelectedAlgorithmSteps: (steps: string[]) => void;
  onAutoAlgorithmSelection: () => Promise<void>;
  onStandardAlgorithmSelection: () => Promise<void>;
  onAlgorithmStepToggle: (step: string, checked: boolean) => void;
  renderStepChat: (step: number) => React.ReactNode;
}

export interface Step7ModelTrainingProps {
  selectedTrainingSteps: string[];
  setSelectedTrainingSteps: (steps: string[]) => void;
  onAutoAlgorithmTraining: () => Promise<void>;
  onStandardAlgorithmTraining: () => Promise<void>;
  onTrainingStepToggle: (step: string, checked: boolean) => void;
  renderStepChat: (step: number) => React.ReactNode;
}

export interface Step8ModelDeploymentProps {
  selectedDeploymentSteps: string[];
  setSelectedDeploymentSteps: (steps: string[]) => void;
  onAutoModelDeployment: () => Promise<void>;
  onStandardModelDeployment: () => Promise<void>;
  onDeploymentStepToggle: (step: string, checked: boolean) => void;
  renderStepChat: (step: number) => React.ReactNode;
}
