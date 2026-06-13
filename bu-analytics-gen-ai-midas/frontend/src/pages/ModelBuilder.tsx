import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
// Excel export utility
import * as XLSX from 'xlsx';

import { 

  Brain, 

  Database, 

  CheckCircle, 

  ArrowRight,

  ArrowLeft,

  Target,

  Wrench,

  Split,

  Rocket,

  Lightbulb,

  Users,

  Maximize,

  Download,
  Play,
  X,
  ArrowLeft as BackIcon,
  BarChart3,
  Eye,
  BookOpen,
  Loader,
} from 'lucide-react';



// Import step components

import { validateSplitConfigurationForSubmit } from '../components/PlatformPartitionSection';
import { createDefaultSplitConfiguration } from '../utils/partitionSplitConfig';
import { displayTotalIv } from '../utils/segmentationMetricsDisplay';

import {

  Step1ObjectivesData,

  Step2DataQC,

  Step3DataInsights,

  Step3_5SegmentationAgentAnalysis,

  Step4FeatureEngineering,

  Step5ModelEvaluation,

  Step6AlgorithmSelection,

  Step6_5ModelTrainingAgent,

  Step8AIExplainability,

  Step9ModelDocumentation

} from '../components/steps';

import {
  readMtaNavGateSnapshot,
  MTA_TRAINING_RESULTS_PERSISTED_EVENT,
  type MtaFlowGate,
} from '../components/steps/modelScreenerUtils';

// Import necessary services and utilities

import { useData } from '../contexts/DataContext';

import { useDatabase } from '../contexts/DatabaseContext';

import { useTheme } from '../contexts/ThemeContext';

import { parseCSV, formatFileSize } from '../utils/csvParser';

import DatasetOverviewSidebar from '../components/DatasetOverviewSidebar';
import DataQualityTreatmentTable from '../components/DataQualityTreatmentTable';
import IVAnalysisComponent from '../components/IVAnalysisComponent';
import VIFAnalysisComponent from '../components/VIFAnalysisComponent';
import CorrelationRatioAnalysisComponent from '../components/CorrelationRatioAnalysisComponent';
import { useLlmSelection } from '../contexts/LlmSelectionContext';

import ProjectSelection from '../components/ProjectSelection';

import { apiIntegrationService } from '../services/apiServices';

import { fastApiService, DatasetColumnInfo, FastAPIChatResponse } from '../services/fastApiService';
import {
  runAutoInsightApiPrefetches,
  filterToPrefetchableInsightSteps,
} from '../services/autoInsightsPrefetchService';

import { Project } from '../services/projectService';

import ReactMarkdown from 'react-markdown';
import ModelEvaluationMEEA from './ModelEvaluationMEEA';
import { Sparkles, XCircle } from 'lucide-react';
import modelEvaluationService from '../services/modelEvaluationService';
import KnowledgeDisclaimer from '../components/KnowledgeDisclaimer';

/** Written by Step1ObjectivesData when chunked upload finishes; fingerprint avoids stale ids */
const STAGED_CHUNKED_DATASET_ID_KEY = 'staged_chunked_dataset_id';
const STAGED_CHUNKED_FILE_META_KEY = 'staged_chunked_file_key';

function readStagedChunkedDatasetIdForSubmit(file: File | undefined): string | null {
  if (typeof window === 'undefined' || !file) return null;
  try {
    const id = sessionStorage.getItem(STAGED_CHUNKED_DATASET_ID_KEY);
    const meta = sessionStorage.getItem(STAGED_CHUNKED_FILE_META_KEY);
    if (!id || !meta) return null;
    const fk = `${file.name}|${file.size}|${file.lastModified}`;
    return meta === fk ? id : null;
  } catch {
    return null;
  }
}

const ModelBuilderRefactored: React.FC = () => {

  interface GeminiMessage {

    id: string;

    role: 'user' | 'assistant';

    content: string;

    timestamp: number;

  }



  const { addDataset } = useData();

  const { isDark } = useTheme();

  

  // Project state

  const [selectedProject, setSelectedProject] = useState<Project | null>(null);

  const [showProjectSelection, setShowProjectSelection] = useState(true);

  

  const [currentStep, setCurrentStep] = useState<number>(() => {
    try {
      const saved = sessionStorage.getItem('model_builder_current_step');
      if (saved) {
        const parsed = parseFloat(saved);
        if (!isNaN(parsed)) {
          if (parsed === 6 || parsed === 7) return 5;
          return parsed;
        }
      }
    } catch {}
    return 1;
  });
  useEffect(() => {
    try { sessionStorage.setItem('model_builder_current_step', String(currentStep)); } catch {}
  }, [currentStep]);

  useEffect(() => {
    if (currentStep === 6 || currentStep === 7) setCurrentStep(5);
  }, [currentStep]);

  const [isTraining, setIsTraining] = useState(false);

  const [trainingProgress, setTrainingProgress] = useState(0);

  const [isRecording, setIsRecording] = useState(false);

  const [isPlaying, setIsPlaying] = useState(false);

  const [recordedAudio, setRecordedAudio] = useState<string | null>(null);

  const [transcript, setTranscript] = useState('');

  const [voiceInputType, setVoiceInputType] = useState<'problem' | 'objectives' | 'requirements'>('problem');

  const [showVoiceInterface, setShowVoiceInterface] = useState(false);

  const [inputMethod, setInputMethod] = useState<'voice' | 'text'>('voice');

  

  // Data source selection states

  const [showDataSourceSelectionModal, setShowDataSourceSelectionModal] = useState(false);

  const [selectedDataSources, setSelectedDataSources] = useState<any[]>([]);



  // Dataset analysis states

  const [datasetAnalysis, setDatasetAnalysis] = useState<{

    columns: DatasetColumnInfo[];

    suggestedTargetVariable: string | null;

    totalRows: number;

    totalColumns: number;

  } | null>(null);

  const [isAnalyzingDataset, setIsAnalyzingDataset] = useState(false);

  const [isUploadingDataset, setIsUploadingDataset] = useState(false);
  const [step1SubmitError, setStep1SubmitError] = useState<string | null>(null);

  // Reactive ML classification result - drives the UI immediately when the LLM responds.
  // Using React state (not sessionStorage) so the component re-renders the instant the
  // result arrives, without waiting for any other background call to finish.
  const [mlClassificationResult, setMlClassificationResult] = useState<{
    dataset_type: string;
    confidence: number;
    reasoning: string;
    characteristics: Record<string, string>;
    recommendations: string[];
  } | null>(null);
  const [mlClassificationError, setMlClassificationError] = useState<string | null>(null);

  // P1.2: Tracks the *background* dataset-type-classification job spawned
  // after Submit. This drives the ML-Problem-Type spinner only and does NOT
  // gate the Submit button (kept separate from `isAnalyzingDataset` which
  // covers the pre-Submit /analyze-dataset call).
  const [mlClassificationPending, setMlClassificationPending] = useState(false);

  // Tracks dataset IDs for which classify-variables has already been called,
  // preventing redundant LLM calls on re-renders or repeated navigation.
  const classifiedDatasetIdsRef = useRef<Set<string>>(new Set());
  const [showDatasetIdAlert, setShowDatasetIdAlert] = useState(false);
  const [pendingDatasetId, setPendingDatasetId] = useState<string | null>(null);
  const [stagedUserKnowledgeFiles, setStagedUserKnowledgeFiles] = useState<File[]>([]);
  const [stagedUseAcrossMidas, setStagedUseAcrossMidas] = useState<boolean>(true);
  const [stagedUseExlExpertise, setStagedUseExlExpertise] = useState<boolean>(true);

  // State for "Proceed to Configuration" button - controls when Dataset Configuration is shown
  const [hasProceededToConfig, setHasProceededToConfig] = useState(false);
  const [isProceedingToConfig, setIsProceedingToConfig] = useState(false);

  // Track current dataset columns from preview (dynamic, updates when dataset changes)
  const [currentDatasetColumns, setCurrentDatasetColumns] = useState<string[]>([]);



  // Custom treatment states

  const [customTreatments, setCustomTreatments] = useState<{[key: string]: string}>({});

  const [isUpdatingTreatment, setIsUpdatingTreatment] = useState(false);



  // Chat functionality states for each step

  const [chatMessages, setChatMessages] = useState<{[key: number]: Array<{id: string, type: 'user' | 'assistant', content: string, timestamp: Date, knowledge_metadata?: {source_files?: string[], use_exl_expertise?: boolean}}>}>({});

  const [chatInputs, setChatInputs] = useState<{[key: number]: string}>({});

  const [isTyping, setIsTyping] = useState<{[key: number]: boolean}>({});

  const [isAIAssistantExpanded, setIsAIAssistantExpanded] = useState<boolean>(false);

  const [expandedStepNumber, setExpandedStepNumber] = useState<number | null>(null);



  // Step-specific functionality states

  const [selectedQCTasks, setSelectedQCTasks] = useState<string[]>([]);
  const [lastExecutedQCTasks, setLastExecutedQCTasks] = useState<string[]>([]);
  const [executedIndividualQCTasks, setExecutedIndividualQCTasks] = useState<string[]>([]);

  // Step-by-step Manual QC state
  const [qcStepByStepMode, setQcStepByStepMode] = useState<boolean>(false);
  const [qcCurrentStepIndex, setQcCurrentStepIndex] = useState<number>(0);
  const [qcTreatmentSequence, setQcTreatmentSequence] = useState<string[]>([]);
  const [qcTreatmentStatuses, setQcTreatmentStatuses] = useState<Record<string, 'pending' | 'active' | 'applied' | 'skipped'>>({});
  const [qcTreatmentPlans, setQcTreatmentPlans] = useState<Record<string, any>>({});
  const [qcIsApplyingTreatment, setQcIsApplyingTreatment] = useState<boolean>(false);

  const [selectedInsightSteps, setSelectedInsightSteps] = useState<string[]>([]);
  // Steps to keep rendering in right pane after Generate - persisted so revisiting the page restores panels
  const [displayedInsightSteps, setDisplayedInsightSteps] = useState<string[]>(() => {
    try {
      const saved = sessionStorage.getItem('model_builder_displayed_insight_steps');
      if (saved) return JSON.parse(saved) as string[];
    } catch {}
    return [];
  });

  /** Which flow last populated the Step 3 sidebar: auto (all five) vs standard (checkbox selection). */
  const [insightsGenerationSource, setInsightsGenerationSource] = useState<'auto' | 'standard' | null>(() => {
    try {
      const s = sessionStorage.getItem('model_builder_insights_source');
      if (s === 'auto' || s === 'standard') return s;
    } catch {}
    return null;
  });

  /** Last Standard run’s step list — used to re-run Standard after switching away from Auto. */
  const [lastStandardInsightSteps, setLastStandardInsightSteps] = useState<string[]>(() => {
    try {
      const raw = sessionStorage.getItem('model_builder_last_standard_insight_steps');
      if (raw) return JSON.parse(raw) as string[];
    } catch {}
    return [];
  });

  /** Which Data Insights tab is selected (Auto vs Standard); initialized from last generation source when known. */
  const [insightsUiMode, setInsightsUiMode] = useState<'auto' | 'standard'>(() => {
    try {
      const s = sessionStorage.getItem('model_builder_insights_source');
      if (s === 'standard') return 'standard';
    } catch {}
    return 'auto';
  });

  type AutoInsightStepId =
    | 'bivariate_analysis'
    | 'correlation_analysis'
    | 'iv_analysis'
    | 'variance_inflation_factor'
    | 'correlation_matrix'
    | 'correlation_ratio_analysis';
  type AutoInsightStepStatus = 'idle' | 'running' | 'done' | 'absent' | 'error';

  const [autoInsightStepStatus, setAutoInsightStepStatus] = useState<
    Record<AutoInsightStepId, AutoInsightStepStatus>
  >({
    bivariate_analysis: 'idle',
    correlation_analysis: 'idle',
    iv_analysis: 'idle',
    variance_inflation_factor: 'idle',
    correlation_matrix: 'idle',
    correlation_ratio_analysis: 'idle',
  });

  /** Steps that had REST prefetch in autoInsightsPrefetchService (removed); keep filter for standard flow. */
  const filterToPrefetchableInsightStepsLocal = (steps: string[]): AutoInsightStepId[] => {
    const prefetchable = new Set<string>([
      'iv_analysis',
      'variance_inflation_factor',
      'correlation_ratio_analysis',
      'correlation_matrix',
    ]);
    return steps.filter((s): s is AutoInsightStepId => prefetchable.has(s));
  };

  /** No-op prefetch: insight panels were removed with git clean; unblock UI by marking steps done. */
  const runAutoInsightApiPrefetchesLocal = async (
    _datasetId: string,
    _targetVariable: string,
    onStepStatus: (stepId: AutoInsightStepId, status: AutoInsightStepStatus) => void,
    options?: { onlyStepIds?: AutoInsightStepId[] }
  ): Promise<void> => {
    const all: AutoInsightStepId[] = [
      'bivariate_analysis',
      'correlation_analysis',
      'iv_analysis',
      'variance_inflation_factor',
      'correlation_matrix',
      'correlation_ratio_analysis',
    ];
    const ids = options?.onlyStepIds?.length ? options.onlyStepIds : all;
    await Promise.resolve();
    for (const id of ids) {
      onStepStatus(id, 'done');
    }
  };

  const [problemType, setProblemType] = useState<'classification' | 'regression' | undefined>(undefined);

  // Function to infer problem type from target variable type
  const inferProblemType = (targetVariableType: string | undefined): 'classification' | 'regression' | undefined => {
    if (!targetVariableType) return undefined;
    
    // Categorical targets are typically classification
    if (targetVariableType === 'Categorical') {
      return 'classification';
    }
    
    // Numerical targets are typically regression
    if (targetVariableType === 'Numerical') {
      return 'regression';
    }
    
    return undefined;
  };

  const handleQCRegenerateCode = async (
    treatmentType: 'invalid_values' | 'special_values' | 'outliers' | 'missing_values',
    selections: Record<string, string>
  ) => {
    const datasetId = activeDatasetId || sessionStorage.getItem('dataset_id');
    if (!datasetId) {
      throw new Error('No dataset ID available');
    }
    return fastApiService.regenerateQCTreatmentCode(datasetId, treatmentType, selections);
  };
  const [isTrainingModel, setIsTrainingModel] = useState<boolean>(false);
  const [datasetPreview, setDatasetPreview] = useState<any>(null);

  // Segmentation variable selection (segmentation-only)
  const [selectedSegmentationVariables, setSelectedSegmentationVariables] = useState<string[]>(
    typeof window !== 'undefined'
      ? (() => {
          const saved = sessionStorage.getItem('segmentation_variables');
          return saved ? JSON.parse(saved) : [];
        })()
      : []
  );
  
  const [segmentationMethod, setSegmentationMethod] = useState<'cart' | 'chaid'>(
    (typeof window !== 'undefined' && (sessionStorage.getItem('segmentation_method') as 'cart' | 'chaid')) || 'cart'
  );
  const [segmentationResult, setSegmentationResult] = useState<any>(
    typeof window !== 'undefined'
      ? (() => {
          const saved = sessionStorage.getItem('segmentation_result');
          return saved ? JSON.parse(saved) : null;
        })()
      : null
  );
  const [isRunningSegmentation, setIsRunningSegmentation] = useState<boolean>(false);
  
  // Segmentation mode toggle (custom vs auto)
  const [segmentationMode, setSegmentationMode] = useState<'custom' | 'auto'>(
    (typeof window !== 'undefined' && (sessionStorage.getItem('segmentation_mode') as 'custom' | 'auto')) || 'custom'
  );
  const [isRunningAutoSegmentation, setIsRunningAutoSegmentation] = useState<boolean>(false);
  
  // Segment training mode and detection
  const [segmentTrainingMode, setSegmentTrainingMode] = useState<boolean>(false);
  const [segmentInfo, setSegmentInfo] = useState<any>(null);
  const [isDetectingSegments, setIsDetectingSegments] = useState<boolean>(false);
  
  // Segmentation parameters
  const [minSegmentSize, setMinSegmentSize] = useState<number>(
    (typeof window !== 'undefined' && parseInt(sessionStorage.getItem('min_segment_size') || '1000')) || 25
  );
  const [maxSegments, setMaxSegments] = useState<number>(
    (typeof window !== 'undefined' && parseInt(sessionStorage.getItem('max_segments') || '5')) || 5
  );
  
  // Minimum segment size mode and percentage
  const [minSegmentSizeMode, setMinSegmentSizeMode] = useState<'number' | 'percentage'>('number');
  const [minSegmentSizePercentage, setMinSegmentSizePercentage] = useState<number>(10);

  // (reverted) keep prior selections across dataset changes

  const [selectedFeatureSteps, setSelectedFeatureSteps] = useState<string[]>([]);

  const [selectedSplitSteps, setSelectedSplitSteps] = useState<string[]>([]);

  const [selectedAlgorithmSteps, setSelectedAlgorithmSteps] = useState<string[]>([]);

  const [selectedTrainingSteps, setSelectedTrainingSteps] = useState<string[]>([]);

  const [selectedDeploymentSteps, setSelectedDeploymentSteps] = useState<string[]>([]);

  // EDA state for Data Treatment page
  const [originalEDA, setOriginalEDA] = useState<any>(null);
  const [currentEDA, setCurrentEDA] = useState<any>(null);
  const [showEDAComparison, setShowEDAComparison] = useState(false);
  const [edaRefreshKey, setEdaRefreshKey] = useState(0); // Key to force sidebar to refetch EDA comparison
  // Counter-based trigger: each increment forces the sidebar to switch to the Updated EDA sub-tab.
  // Using a counter (instead of boolean + reset callback) makes the mechanism idempotent and
  // guarantees the effect fires every time the button is clicked, even if the sidebar was already
  // showing the EDA Comparison tab on a different sub-view (e.g. Change Heatmap).
  const [forceEdaComparisonView, setForceEdaComparisonView] = useState(0);
  const triggerEdaComparisonView = useCallback(() => {
    setForceEdaComparisonView((prev) => prev + 1);
  }, []);

  // Duplicate removal state — lifted here so it persists across page navigation
  const [dupWantsToRemove, setDupWantsToRemove] = useState<boolean | null>(null);
  const [dupIsComplete, setDupIsComplete] = useState(false);
  const [dupIsSkipped, setDupIsSkipped] = useState(false);
  const [dupRemovalResult, setDupRemovalResult] = useState<{ removedCount: number; newRowCount: number } | null>(null);
  const [dupSelectedVariables, setDupSelectedVariables] = useState<string[]>([]);
  const [dupIdentificationResult, setDupIdentificationResult] = useState<{
    duplicateCount: number;
    totalRows: number;
    duplicatePercentage: number;
    selectedColumns: string[];
    analysisScope: 'train' | 'entire' | string;
  } | null>(null);

  // QC Templates state — lifted here so templates can be passed to API calls
  const [qcTemplates, setQcTemplates] = useState<Record<string, any> | null>(null);

  // Active dataset id from session storage

  const [activeDatasetId, setActiveDatasetId] = useState<string | null>(

    typeof window !== 'undefined' ? sessionStorage.getItem('dataset_id') : null

  );

  const [mtaFlowGate, setMtaFlowGate] = useState<MtaFlowGate>({
    trainingInProgress: false,
    trainingComplete: false,
    screenerPhaseDone: false,
    variableSelectionConfirmed: false,
  });

  const handleMtaFlowGateChange = useCallback((next: MtaFlowGate) => {
    setMtaFlowGate(next);
  }, []);

  

  // Dataset configuration from session storage

  const [datasetConfig, setDatasetConfig] = useState<{

    target_variable: string;

    target_variable_type: 'Numerical' | 'Categorical';

    dataset_structure_type: 'classification' | 'regression' | 'time_series' | 'others';

    problem_statement: string;

    data_dictionary: string;

    unique_id_combinations: string[];

    segmentation_variable: string;

    weight_variable: string;

    sample_identifier_variable: string;

    split_configuration?: import('../utils/partitionSplitConfig').SplitConfiguration;

    split_ratio?: number;

    initial_scope?: string;

    data_scope?: string;

    has_sampling_variable?: boolean;

    sampling_variable?: string | null;

  } | null>(

    typeof window !== 'undefined' ? 

      (() => {

        const config = sessionStorage.getItem('dataset_config');

        return config ? JSON.parse(config) : null;

      })() : null

  );

  // Avoid brittle cross-context checks: File objects from browser APIs can fail `instanceof` in some runtime edges.
  const isLikelyFile = (value: any): value is File => {
    return !!value && typeof value.name === 'string' && typeof value.size === 'number' && typeof value.type === 'string';
  };
  const getSelectedFileSource = () =>
    [...selectedDataSources].reverse().find((source) => source?.type === 'file' && isLikelyFile(source?.file));

  const getTargetVariableForSubmit = () => {
    const fromChatInputs = (chatInputs['target_var' as unknown as number] as unknown as string) || '';
    const fromDatasetConfig = datasetConfig?.target_variable || '';
    return (fromChatInputs || fromDatasetConfig).trim();
  };

  const getUniqueIdCombinationsForSubmit = () => {
    const fromChatInputs = chatInputs['unique_id_combinations' as unknown as number] as unknown as string[] | undefined;
    const fromDatasetConfig = datasetConfig?.unique_id_combinations || [];
    return (Array.isArray(fromChatInputs) && fromChatInputs.length > 0 ? fromChatInputs : fromDatasetConfig)
      .filter(Boolean);
  };

  const getTargetVariableTypeForSubmit = (): 'Numerical' | 'Categorical' | null => {
    const fromChat = (chatInputs['target_type' as unknown as number] as unknown as string) || '';
    const fromCfg = datasetConfig?.target_variable_type || '';
    const raw = String(fromChat || fromCfg).trim();
    if (raw === 'Numerical' || raw === 'Categorical') return raw;
    return null;
  };

  /** Upload API returned a dataset id (pending alert) or user already acknowledged (active id). */
  const step1DatasetUploadSucceeded = Boolean(activeDatasetId || pendingDatasetId);

  const canSubmitDataset =
    !!getSelectedFileSource() &&
    !!getTargetVariableForSubmit() &&
    !!getTargetVariableTypeForSubmit() &&
    getUniqueIdCombinationsForSubmit().length > 0 &&
    !isAnalyzingDataset &&
    !isUploadingDataset;

  const submitBlockedReason = (() => {
    if (isUploadingDataset) return 'Dataset upload is in progress.';
    if (isAnalyzingDataset) return 'Dataset analysis is in progress.';
    if (!getSelectedFileSource()) return 'Add a CSV file as a data source.';
    if (!getTargetVariableForSubmit()) return 'Select a target variable.';
    if (!getTargetVariableTypeForSubmit()) return 'Select a variable category (target type).';
    if (getUniqueIdCombinationsForSubmit().length === 0) return 'Select at least one Unique ID variable.';
    return null;
  })();

  useEffect(() => {
    if (canSubmitDataset && step1SubmitError) {
      setStep1SubmitError(null);
    }
  }, [canSubmitDataset, step1SubmitError]);

  useEffect(() => {
    const snap = readMtaNavGateSnapshot(activeDatasetId);
    setMtaFlowGate((prev) => ({
      ...prev,
      ...snap,
      trainingInProgress: false,
    }));
  }, [activeDatasetId]);

  useEffect(() => {
    if (typeof window === 'undefined' || !activeDatasetId) return;
    const bump = () => {
      const snap = readMtaNavGateSnapshot(activeDatasetId);
      setMtaFlowGate((prev) => ({ ...prev, ...snap, trainingInProgress: false }));
    };
    window.addEventListener(MTA_TRAINING_RESULTS_PERSISTED_EVENT, bump as EventListener);
    window.addEventListener('midas-mta-screener-phase-complete', bump);
    return () => {
      window.removeEventListener(MTA_TRAINING_RESULTS_PERSISTED_EVENT, bump as EventListener);
      window.removeEventListener('midas-mta-screener-phase-complete', bump);
    };
  }, [activeDatasetId]);

  const modelTrainingStepAllowsLeaving = useMemo(
    () =>
      mtaFlowGate.variableSelectionConfirmed &&
      mtaFlowGate.trainingComplete &&
      mtaFlowGate.screenerPhaseDone &&
      !mtaFlowGate.trainingInProgress,
    [mtaFlowGate],
  );

  // Dataset overview sidebar state

  const [showDatasetOverview, setShowDatasetOverview] = useState(false);

  /** True while Dataset Overview sidebar (step 1) is still loading Overview / Quality / Distributions. */
  const [datasetOverviewStep1PanelsBusy, setDatasetOverviewStep1PanelsBusy] = useState(false);

  const [sidebarWidth, setSidebarWidth] = useState(320);



  // Data Dictionary CSV file state

  const [dataDictionaryFile, setDataDictionaryFile] = useState<File | null>(null);



  // Chat container refs for auto-scroll

  const chatContainerRefs = useRef<{[key: number]: HTMLDivElement | null}>({});


  // CSV Download functionality (auto-headers from first row)
  const convertToCSV = (data: Record<string, any>[]): string => {
    if (data.length === 0) return '';
    
    // Get headers from the first row
    const headers = Object.keys(data[0]);
    
    // Create CSV content
    const csvContent = [
      // Header row
      headers.map(header => `"${header}"`).join(','),
      // Data rows
      ...data.map(row => 
        headers.map(header => {
          const value = row[header];
          // Handle null, undefined, and special characters
          if (value === null || value === undefined) {
            return '""';
          }
          // Convert to string, normalize dashes, and escape quotes
          const stringValue = String(value)
            .replace(/[\u2013\u2014]/g, '-')
            .replace(/\"/g, '""')
            .replace(/"/g, '""');
          return `"${stringValue}"`;
        }).join(',')
      )
    ].join('\n');
    
    return csvContent;
  };

  // Download Standard Data Insights to Excel with one sheet per analysis section
  const downloadInsightsAsXLSX = async (planData: any, stepNumber: number) => {
    try {
      if (!planData || typeof planData !== 'object') {
        alert('No insights available to download');
        return;
      }


      type TableLike = { columns: string[]; rows: any[]; title?: string; variable_type?: string };
      const wb = XLSX.utils.book_new();

      const { insightPayload, tablesMap, dataMeta } = normalizePlanInsightPayload(planData);
      const bivarInsights: string[] = Array.isArray(dataMeta?.bivariate_insight) ? dataMeta.bivariate_insight : (Array.isArray(dataMeta?.llm_bivariate_insight) ? dataMeta.llm_bivariate_insight : []);
      const corrInsights: string[] = Array.isArray(dataMeta?.correlation_insight) ? dataMeta.correlation_insight : (Array.isArray(dataMeta?.llm_correlation_insight) ? dataMeta.llm_correlation_insight : []);
      const vifInsights: string[] = Array.isArray(dataMeta?.vif_insight) ? dataMeta.vif_insight : (Array.isArray(dataMeta?.llm_vif_insight) ? dataMeta.llm_vif_insight : []);
      const corrMatrixInsights: string[] = Array.isArray(dataMeta?.correlation_matrix_insight)
        ? dataMeta.correlation_matrix_insight.map((item: any) =>
            typeof item === 'string'
              ? item
              : typeof item === 'object' && item?.pattern
              ? item.pattern
              : JSON.stringify(item)
          )
        : Array.isArray(dataMeta?.llm_correlation_matrix_insight)
        ? dataMeta.llm_correlation_matrix_insight.map((item: any) =>
            typeof item === 'string'
              ? item
              : typeof item === 'object' && item?.pattern
              ? item.pattern
              : JSON.stringify(item)
          )
        : [];
      const corrRatioInsights: string[] = Array.isArray(dataMeta?.correlation_ratio_insight)
        ? dataMeta.correlation_ratio_insight
        : Array.isArray(dataMeta?.llm_correlation_ratio_insight)
          ? dataMeta.llm_correlation_ratio_insight
          : [];
      const ivContext = getIvContextFromNormalizedPayload(insightPayload, tablesMap, dataMeta);
      const ivInsights: string[] = ivContext.ivInsights;
      const ivSummaryColumns = ivContext.ivSummaryColumns;
      console.log('📥 downloadInsightsAsXLSX iv context', {
        stepNumber,
        ivInsightsCount: ivInsights.length,
        ivSummaryColumns
      });
      //const ivInsights: string[] = Array.isArray(dataMeta?.iv_insight) ? dataMeta.iv_insight : (Array.isArray(dataMeta?.llm_iv_insight) ? dataMeta.llm_iv_insight : []);

      // Group sections for Data Insights export
      const grouped: Record<string, TableLike[]> = {};
      Object.entries(tablesMap).forEach(([sectionName, value]) => {
        if (!Array.isArray(value) || value.length === 0 || !value[0]?.columns || !value[0]?.rows) return;
        
        // Map IV sections by friendly label; keep correlation_* under Correlation Analysis; correlation_matrix_* under Correlation Matrix
        let key = sectionName;
        if (sectionName.startsWith('correlation_matrix')) {
          key = 'Correlation Matrix';
        } else if (sectionName === 'correlation_ratio') {
          key = 'Correlation ratio (η)';
        } else if (sectionName.startsWith('correlation_')) {
          key = 'Correlation Analysis';
        } else if (sectionName.startsWith('iv_analysis_')) {
          key = 'Information Value (IV)';
        }
        
        if (!grouped[key]) grouped[key] = [];
        grouped[key].push(...(value as TableLike[]));
      });

      // Create a sheet per section (use AOA so each block starts at column A; avoids empty columns)
      Object.entries(grouped).forEach(([section, tables]) => {
        const niceTitle = section
          .replace(/_/g, ' ')
          .replace(/\b\w/g, l => l.toUpperCase());

        const ws = XLSX.utils.aoa_to_sheet([]);
        // Merge title across the maximum number of columns in this sheet
        const maxCols = Math.max(1, ...tables.map((t: any) => Array.isArray(t.columns) ? t.columns.length : 1));
        // Title row in uppercase, then an empty spacer row
        const titleUpper = String(niceTitle).toUpperCase();
        XLSX.utils.sheet_add_aoa(ws, [[titleUpper]], { origin: { r: 0, c: 0 } });
        // Basic styling: bold title cell; set column widths for better appearance
        if (!ws['!cols']) {
          ws['!cols'] = Array.from({ length: Math.max(1, maxCols) }, () => ({ wch: 24 }));
        }
        if (ws['A1']) {
          // These styles are supported in most SheetJS builds; if not, they are safely ignored
          // @ts-ignore
          ws['A1'].s = {
            font: { bold: true }
          };
        }
        XLSX.utils.sheet_add_aoa(ws, [[" "]], { origin: -1 });

        // Insights block at the top per analysis with specific headings
        const insightBlock: any[][] = [];
        const isBivarSheet = (section === 'bivariate_analysis' || niceTitle === 'Bivariate Analysis');
        const isCorrSheet = (section === 'Correlation Analysis' || (typeof section === 'string' && section.startsWith('correlation_')) || niceTitle === 'Correlation Analysis');
        const isVifSheet = (section === 'vif_analysis' || niceTitle === 'Vif Analysis' || niceTitle === 'Variation Inflation Factor (VIF) Analysis');
        const isCorrMatrixSheet = (section === 'Correlation Matrix' || (typeof section === 'string' && section.startsWith('correlation_matrix')) || niceTitle === 'Correlation Matrix');
        const isIvSheet =
          niceTitle === 'Information Value (IV)' || niceTitle === 'IV Analysis';
        const isCorrRatioSheet = section === 'Correlation ratio (η)';

        if (isBivarSheet && bivarInsights.length > 0) {
          insightBlock.push(["Bivariate Insights"]);
          bivarInsights.forEach(text => insightBlock.push([String(text)]));
        }
        if (isCorrSheet && corrInsights.length > 0) {
          insightBlock.push(["Correlation Insights"]);
          corrInsights.forEach(text => insightBlock.push([String(text)]));
        }
        if (isCorrMatrixSheet && corrMatrixInsights.length > 0) {
          insightBlock.push(["Correlation Matrix Insights"]);
          corrMatrixInsights.forEach(text => insightBlock.push([String(text)]));
        }
        if (isCorrRatioSheet && corrRatioInsights.length > 0) {
          insightBlock.push(['Correlation ratio (η) Insights']);
          corrRatioInsights.forEach((text) => insightBlock.push([String(text)]));
        }
        if (isVifSheet && vifInsights.length > 0) {
          insightBlock.push(["VIF Insights"]);
          vifInsights.forEach(text => insightBlock.push([String(text)]));
        }
        if (isIvSheet && ivSummaryColumns.length > 0) {
          insightBlock.push(['IV Summary Columns', ivSummaryColumns.join(', ')]);
        }
        if (isIvSheet && ivInsights.length > 0) {
          insightBlock.push(["IV Insights"]);
          ivInsights.forEach(text => insightBlock.push([String(text)]));
        }
        if (insightBlock.length > 0) {
          XLSX.utils.sheet_add_aoa(ws, insightBlock, { origin: -1 });
          XLSX.utils.sheet_add_aoa(ws, [[" "]], { origin: -1 });
        }

        tables.forEach((table: TableLike) => {
          // Skip IV detail tables from export; keep only summary-level tables
          if (isIvSheet && (table as any)?.title && String((table as any).title).toLowerCase().includes('detail')) {
            return;
          }
          const rawHeaders: string[] = Array.isArray(table.columns) ? table.columns : [];
          const perHeaders = rawHeaders.map(h => h === 'Target_Variable_Rate' ? 'Event Rate' : (h === 'Defaults' ? 'Event(Target flag=1)' : h));

          const block: any[][] = [];
          // Header row
          block.push(perHeaders);
          // Data rows in perHeaders order
          const rows = (table.rows || []) as any[];
          rows.forEach(r => {
            block.push(perHeaders.map(h => {
              if (h === 'Event Rate') return r['Event Rate'] !== undefined ? r['Event Rate'] : r['Target_Variable_Rate'];
              if (h === 'Event(Target flag=1)') return r['Event(Target flag=1)'] !== undefined ? r['Event(Target flag=1)'] : r['Defaults'];
              return r[h];
            }));
          });

          // Insights
          const insightsArr: string[] = Array.isArray((table as any).insights) ? (table as any).insights : [];
          if (insightsArr.length > 0) {
            block.push(["Insights:"]);
            insightsArr.forEach(text => block.push([text]));
          }

          // Append block and spacer
          XLSX.utils.sheet_add_aoa(ws, block, { origin: -1 });
          XLSX.utils.sheet_add_aoa(ws, [[" "]], { origin: -1 });
        });

        XLSX.utils.book_append_sheet(wb, ws, niceTitle.slice(0, 31));
      });

      const stepLabel = stepNumber ? `Step${stepNumber}_` : '';
      const ts = new Date().toISOString().replace(/[:.]/g, '-');
      XLSX.writeFile(wb, `${stepLabel}Standard_Data_Insights_${ts}.xlsx`);
    } catch (e) {
      console.error('Error exporting Excel:', e);
      alert('Failed to export Excel');
    }
  };

  // Download Detailed IV Report: three sheets - IV Insights, IV Summary, IV Details
  const downloadDetailedIvReport = async (planData: any, stepNumber: number) => {
    try {
      if (!planData || typeof planData !== 'object') {
        alert('No insights available to download');
        return;
      }

      let XLSX: any;
      try {
        XLSX = await import('xlsx');
      } catch (e) {
        alert('Excel export requires the "xlsx" package. Please run: npm install xlsx');
        return;
      }

      const { insightPayload, tablesMap, dataMeta } = normalizePlanInsightPayload(planData);
      const ivContext = getIvContextFromNormalizedPayload(insightPayload, tablesMap, dataMeta);
      const ivInsights: string[] = ivContext.ivInsights;
      console.log('📥 downloadDetailedIvReport iv context', {
        stepNumber,
        ivInsightsCount: ivInsights.length
      });
      const ivSummary =
        ivContext.ivSummary ||
        (Array.isArray(tablesMap?.iv_analysis_summary) && tablesMap.iv_analysis_summary.length > 0 ? tablesMap.iv_analysis_summary[0] : null);
      const ivDetails: any[] = Array.isArray(tablesMap?.iv_analysis_details) ? tablesMap.iv_analysis_details : [];

      if (!ivInsights.length && !ivSummary && !ivDetails.length) {
        alert('IV data not available in the current insights. Generate IV first.');
        return;
      }

      const wb = XLSX.utils.book_new();

      // Sheet 1: IV Insights
      const wsInsights = XLSX.utils.aoa_to_sheet([]);
      XLSX.utils.sheet_add_aoa(wsInsights, [['IV Insights']], { origin: { r: 0, c: 0 } });
      if (!wsInsights['!cols']) wsInsights['!cols'] = [{ wch: 80 }];
      if (ivInsights.length) {
        const rows = ivInsights.map((txt) => [String(txt)]);
        XLSX.utils.sheet_add_aoa(wsInsights, [[" "]], { origin: -1 });
        XLSX.utils.sheet_add_aoa(wsInsights, rows, { origin: -1 });
      }
      XLSX.utils.book_append_sheet(wb, wsInsights, 'IV Insights');

      // Sheet 2: IV Summary
      const wsSummary = XLSX.utils.aoa_to_sheet([]);
      XLSX.utils.sheet_add_aoa(wsSummary, [['IV Analysis Summary']], { origin: { r: 0, c: 0 } });
      if (ivSummary && Array.isArray(ivSummary.columns) && Array.isArray(ivSummary.rows)) {
        XLSX.utils.sheet_add_aoa(wsSummary, [[" "]], { origin: -1 });
        XLSX.utils.sheet_add_aoa(wsSummary, [ivSummary.columns], { origin: -1 });
        ivSummary.rows.forEach((r: any) => {
          const row = ivSummary.columns.map((c: string) => r?.[c]);
          XLSX.utils.sheet_add_aoa(wsSummary, [row], { origin: -1 });
        });
      } else {
        XLSX.utils.sheet_add_aoa(wsSummary, [["No IV summary available"]], { origin: -1 });
      }
      XLSX.utils.book_append_sheet(wb, wsSummary, 'IV Summary');

      // Sheet 3: IV Details (concatenated blocks)
      const wsDetails = XLSX.utils.aoa_to_sheet([]);
      XLSX.utils.sheet_add_aoa(wsDetails, [['IV Analysis Details']], { origin: { r: 0, c: 0 } });
      if (ivDetails.length) {
        ivDetails.forEach((tbl: any, idx: number) => {
          try {
            const title = String(tbl?.title || `IV Detail ${idx + 1}`);
            const columns: string[] = Array.isArray(tbl?.columns) ? tbl.columns : [];
            const rows: any[] = Array.isArray(tbl?.rows) ? tbl.rows : [];
            if (!columns.length || !rows.length) return;
            XLSX.utils.sheet_add_aoa(wsDetails, [[" "]], { origin: -1 });
            XLSX.utils.sheet_add_aoa(wsDetails, [[title]], { origin: -1 });
            XLSX.utils.sheet_add_aoa(wsDetails, [columns], { origin: -1 });
            rows.forEach((r: any) => {
              const row = columns.map((c: string) => r?.[c]);
              XLSX.utils.sheet_add_aoa(wsDetails, [row], { origin: -1 });
            });
          } catch {}
        });
      } else {
        XLSX.utils.sheet_add_aoa(wsDetails, [["No IV details available"]], { origin: -1 });
      }
      XLSX.utils.book_append_sheet(wb, wsDetails, 'IV Details');

      const stepLabel = stepNumber ? `Step${stepNumber}_` : '';
      const ts = new Date().toISOString().replace(/[:.]/g, '-');
      XLSX.writeFile(wb, `${stepLabel}Detailed_IV_Report_${ts}.xlsx`);
    } catch (e) {
      console.error('Error exporting IV report:', e);
      alert('Failed to export IV report');
    }
  };

  // Project selection handler
  const handleProjectSelect = (project: Project) => {
    setSelectedProject(project);
    setShowProjectSelection(false);
    
    // Store selected project in sessionStorage for persistence
    sessionStorage.setItem('selected_project', JSON.stringify(project));
    
    console.log('🎯 Project selected:', project.name, '(ID:', project.id + ')');
    console.log('  📝 Project Description:', project.description || '(No description)');
    console.log('  💾 Stored in sessionStorage:', JSON.stringify(project));
  };

  // Handle back to project selection
  const handleBackToProjects = () => {
    setSelectedProject(null);
    setShowProjectSelection(true);
    
    // Clear project from sessionStorage
    sessionStorage.removeItem('selected_project');
    
    // Also clear any dataset-related data
    sessionStorage.removeItem('dataset_id');
    sessionStorage.removeItem('dataset_config');
    setActiveDatasetId(null);
    setDatasetConfig(null);
    setShowDatasetOverview(false);
    
    console.log('🔙 Returned to project selection');
  };

  // Load selected project from sessionStorage on component mount
  useEffect(() => {
    const storedProject = sessionStorage.getItem('selected_project');
    if (storedProject) {
      try {
        const project: Project = JSON.parse(storedProject);
        setSelectedProject(project);
        setShowProjectSelection(false);
      } catch (error) {
        console.error('Error parsing stored project:', error);
        sessionStorage.removeItem('selected_project');
      }
    }
  }, []);

  // CSV with explicit headers (preserves order exactly as provided)
  const convertToCSVWithHeaders = (headers: string[], data: Record<string, any>[]): string => {
    const csvContent = [
      headers.map(header => `"${header}"`).join(','),
      ...data.map(row => headers.map(header => {
        const value = row[header];
        if (value === null || value === undefined) return '""';
        const stringValue = String(value)
          .replace(/[\u2013\u2014]/g, '-')
          .replace(/\"/g, '""')
          .replace(/"/g, '""');
        return `"${stringValue}"`;
      }).join(','))
    ].join('\n');
    return csvContent;
  };

  // Convert a Standard Data Insights table {columns, rows} to CSV rows
  const tableToCsvRows = (table: { columns: string[]; rows: any[] }): Record<string, any>[] => {
    const headers = Array.isArray(table.columns) ? table.columns : [];
    const rows = Array.isArray(table.rows) ? table.rows : [];
    return rows.map((row: any) => {
      const out: Record<string, any> = {};
      headers.forEach(h => { out[h] = row?.[h]; });
      return out;
    });
  };

  // Download Standard Data Insights as a single CSV with section title rows
  const downloadInsightsAsCSV = (planData: any, stepNumber: number) => {
    try {
      if (!planData || typeof planData !== 'object') {
        alert('No insights available to download');
        return;
      }

      // We'll build CSV as lines to allow per-section titles
      const csvLines: string[] = [];
      const headerOrder: string[] = [];

      type TableLike = { columns: string[]; rows: any[]; title?: string };

      const tables: { section: string; table: TableLike }[] = [];
      Object.entries(planData).forEach(([sectionName, value]) => {
        if (Array.isArray(value) && value.length > 0 && value[0]?.columns && value[0]?.rows) {
          (value as any[]).forEach((t: any) => {
            tables.push({ section: sectionName, table: t as TableLike });
            // Preferred header order overrides for known table types
            const isBivariateNumerical = sectionName === 'bivariate_analysis' && (t.variable_type === 'numerical');
            const preferredNumerical = ['Variable', 'Bin Range (Decile)', 'Target_Variable_Rate', 'Total', 'Defaults'];
            const cols: string[] = Array.isArray(t.columns) ? t.columns : [];
            const orderedCols = isBivariateNumerical ? preferredNumerical.filter(h => cols.includes(h)).concat(cols.filter(h => !preferredNumerical.includes(h))) : cols;
            orderedCols.forEach((h: string) => { if (!headerOrder.includes(h)) headerOrder.push(h); });
          });
        }
      });

      if (tables.length === 0) {
        alert('No table data available to download');
        return;
      }

      // Build final headers: ordered UI columns (with merged Category/Bin)
      const mergedLabel = 'Category/Bin Range (Decile)';
      const finalHeaders: string[] = [];

      // Preserve UI order; insert merged label where appropriate
      headerOrder.forEach(h => {
        if (h === 'Category' || h === 'Bin Range (Decile)' || h === 'Target_Variable_Rate' || h === 'Defaults') {
          if (!finalHeaders.includes(mergedLabel)) finalHeaders.push(mergedLabel);
          return;
        }
        finalHeaders.push(h);
      });

      // Do NOT add an Insight column; we'll add an extra insight row per table block

      // Group tables by section to emit section title + header + rows
      const grouped: Record<string, TableLike[]> = {};
      tables.forEach(t => {
        grouped[t.section] = grouped[t.section] || [];
        grouped[t.section].push(t.table);
      });

      Object.entries(grouped).forEach(([section, tbls]) => {
        const title = section
          .replace(/_/g, ' ')
          .replace(/\b\w/g, l => l.toUpperCase())
          .replace('Correlation Numeric', 'Correlation Analysis (Numeric)')
          .replace('Correlation Categorical', 'Correlation Analysis (Categorical)');
        // Section title row (single cell)
        csvLines.push(`"${title}"`);
        // For each table/variable: header, data rows, insights, blank line
        tbls.forEach((table) => {
          const isNumericalVar = (table as any)?.variable_type === 'numerical' || (Array.isArray((table as any)?.columns) && (table as any).columns.includes('Bin Range (Decile)'));
          const perHeaders = finalHeaders.map(h => {
            if (h === mergedLabel) return isNumericalVar ? 'Bin Range (Decile)' : 'Category';
            if (h === 'Target_Variable_Rate') return 'Event Rate';
            if (h === 'Defaults') return 'Event(Target flag=1)';
            return h;
          });
          // Header row per variable block
          csvLines.push(perHeaders.map(h => `"${h}"`).join(','));
          const rows = tableToCsvRows(table);
          const insightsArr: string[] = Array.isArray((table as any).insights) ? (table as any).insights : [];
          rows.forEach(r => {
            const out: Record<string, any> = {};
            perHeaders.forEach(h => {
              if (h === 'Category') { out[h] = r['Category'] ?? ''; return; }
              if (h === 'Bin Range (Decile)') { out[h] = r['Bin Range (Decile)'] ?? ''; return; }
              const sourceKey = h === 'Event Rate' ? 'Event Rate' : (h === 'Event(Target flag=1)' ? 'Event(Target flag=1)' : h);
              out[h] = r[sourceKey] ?? '';
            });
            csvLines.push(convertToCSV([out]).split('\n').slice(1).join('\n'));
          });
          if (insightsArr.length > 0) {
            const makeLine = (text: string) => {
              const headersEsc = perHeaders.map(() => '');
              headersEsc[0] = `"${String(text).replace(/\"/g, '""').replace(/"/g, '""')}"`;
              csvLines.push(headersEsc.join(','));
            };
            // Label line
            makeLine('Insights:');
            // One line per insight (no bullet prefix)
            for (let i = 0; i < insightsArr.length; i++) {
              makeLine(`${insightsArr[i]}`);
            }
          }
          // Blank line between variables
          csvLines.push('');
        });
        // Extra blank line between sections
        csvLines.push('');
      });

      const csvContent = csvLines.join('\r\n');

      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      if (link.download !== undefined) {
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        const stepLabel = stepNumber ? `Step${stepNumber}_` : '';
        const ts = new Date().toISOString().replace(/[:.]/g, '-');
        link.setAttribute('download', `${stepLabel}Standard_Data_Insights_${ts}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
      }
    } catch (e) {
      console.error('Error downloading insights CSV:', e);
      alert('Failed to download insights CSV');
    }
  };

  // Download plan as CSV functionality
  const downloadPlanAsCSV = (planData: any, stepNumber: number) => {
    try {
      // Convert plan data to CSV format
      const csvData: Record<string, any>[] = [];
      
      if (planData && typeof planData === 'object') {
        Object.entries(planData).forEach(([category, items]) => {
          // Handle array of objects format (new format)
          if (Array.isArray(items)) {
            items.forEach((item, index) => {
              const name = item.variable || item.field || item.column || '';
              const detection = item.detection || item.strategy || item.approach || item.method || '';
              const treatment = item.treatment || item.solution || item.recommendation || item.action || '';
              
              const row: Record<string, any> = {
                'Issue': index === 0 ? category.replace(/_/g, ' ').replace(/([A-Z])/g, ' $1').trim() : '',
                'Variable': name,
                'Observation': detection,
                'Treatment': treatment
              };
              
              csvData.push(row);
            });
          } else {
            // Handle legacy object format
            const row: Record<string, any> = {
              'Category': category.replace(/_/g, ' ').replace(/([A-Z])/g, ' $1').trim(),
              'Name': 'N/A',
              'Detection': '',
              'Treatment': ''
            };
            
            if (typeof items === 'object' && items !== null) {
              const itemsObj = items as Record<string, any>;
              
              // Extract detection strategy
              const detectionValue = itemsObj.detection || itemsObj.strategy || itemsObj.approach || 
                                   itemsObj.method || itemsObj.identification || itemsObj.analysis || '';
              if (detectionValue) {
                row['Detection'] = String(detectionValue);
              }
              
              // Extract treatment
              const treatmentValue = itemsObj.treatment || itemsObj.solution || itemsObj.recommendation || 
                                   itemsObj.action || itemsObj.handling || itemsObj.mitigation || '';
              if (treatmentValue) {
                row['Treatment'] = String(treatmentValue);
              }
            } else if (typeof items === 'string') {
              row['Treatment'] = String(items);
            }
            
            csvData.push(row);
          }
        });
      }
      
      if (csvData.length === 0) {
        alert('No plan data available to download');
        return;
      }
      
      // Convert to CSV
      const csvContent = convertToCSV(csvData);
      
      // Create blob and download
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      
      if (link.download !== undefined) {
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        
        // Generate filename based on step
        const stepNames = {
          2: 'Data_QC_Plan',
          3: 'Data_Insights_Plan',
          4: 'Feature_Engineering_Plan',
          5: 'Data_Splitting_Plan',
          6: 'Algorithm_Selection_Plan',
          7: 'Model_Training_Plan',
          8: 'Model_Deployment_Plan'
        };
        const stepName = stepNames[stepNumber as keyof typeof stepNames] || 'Analysis_Plan';
        const timestamp = new Date().toISOString().split('T')[0];
        link.setAttribute('download', `${stepName}_${timestamp}.csv`);
        
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        
        console.log(`✅ Plan downloaded as CSV: ${stepName}_${timestamp}.csv`);
      }
    } catch (error) {
      console.error('Failed to download plan CSV:', error);
      alert('Failed to download plan CSV file');
    }
  };

  // Removed Excel export per request; CSV is the only format for now


  // Code execution states

  const [executionResults, setExecutionResults] = useState<{[key: string]: {

    success: boolean;

    response: string;

    columns_info: any[] | null;

    isLoading: boolean;

    error: string | null;

  }}>({});

  const [executingCodeId, setExecutingCodeId] = useState<string | null>(null);

  // Missing flag option state for Manual QC mode
  const [addMissingFlag, setAddMissingFlag] = useState<boolean>(false);

  // Comparison modal state
  const [showComparisonModal, setShowComparisonModal] = useState<boolean>(false);
  const [comparisonData, setComparisonData] = useState<any>(null);
  const [isLoadingComparison, setIsLoadingComparison] = useState<boolean>(false);
  
  // Original column info for comparison with processed data
  const [originalColumnInfo, setOriginalColumnInfo] = useState<any[] | null>(null);
  // Per execution rolling baseline (n-1) for cell-level highlighting
  const [executionBaselines, setExecutionBaselines] = useState<{ [key: string]: any[] }>({});


  // Define all steps for model development

  const steps = [

    { id: 1, title: 'Objectives' },

    { id: 2, title: 'Data Treatment' },

    { id: 3, title: 'Data Insights' },

    { id: 3.5, title: 'Segmentation' },

    { id: 4, title: 'Feature Engineering' },

    { id: 4.5, title: 'Model Training' },

    { id: 5, title: 'Model Evaluation' },

    { id: 8, title: 'AI Explainability' },

    { id: 9, title: 'Model Documentation' },

  ];



  // Icon mapping for each step

  const stepIcons: { [key: number]: any } = {

    1: Database,      // Objectives & Data

    2: CheckCircle,   // Data Treatment

    3: Lightbulb,     // Data Insights

    3.5: Users,       // Segmentation Agent Analysis

    4: Wrench,        // Feature Engineering & Selection

    4.5: Brain,       // Model Training Agent (MTA)

    5: BarChart3,     // Model Evaluation

    8: Eye,           // AI Explainability

    9: BookOpen,      // Model Documentation

  };



  // Initialize Gemini service

  useEffect(() => {

    const initializeGemini = async () => {

      try {

        // Get the Gemini API key from environment

        const geminiApiKey = import.meta.env.VITE_GEMINI_API_KEY;

        

        console.log('🔧 Initializing Gemini in ModelBuilder with key:', geminiApiKey ? `${geminiApiKey.substring(0, 10)}...` : 'NOT SET');

        

        // Initialize the Gemini service only if key exists

        if (geminiApiKey) {

          apiIntegrationService.initializeGemini(geminiApiKey);

        } else {

          console.warn('VITE_GEMINI_API_KEY is not set. Gemini will not be initialized.');

        }

        

        // Test Gemini connection

        const isAvailable = await apiIntegrationService.testGeminiConnection();

        console.log('Gemini API available:', isAvailable);

        

        if (!isAvailable) {

          console.warn('Gemini API not available, will use fallback responses');

        } else {

          // Test a simple message to verify the API works

          await testGeminiIntegration();

        }

      } catch (error) {

        console.error('Error initializing Gemini service:', error);

      }

    };



    const testGeminiIntegration = async () => {

      try {

        console.log('🧪 Testing Gemini integration with simple message...');

        const geminiService = apiIntegrationService.getGeminiService();

        if (!geminiService) {

          console.error('❌ Gemini service not available for testing');

          return;

        }



        const testMessage: GeminiMessage = {

          id: 'test-1',

          role: 'user',

          content: 'Hello, can you respond with a simple greeting?',

          timestamp: Date.now()

        };



        const response = await geminiService.sendMessage([testMessage], 'gemini-2.0-flash');

        const testResponse = response.choices[0]?.message?.content;

        console.log('✅ Gemini test successful, response:', testResponse);

      } catch (error) {

        console.error('❌ Gemini test failed:', error);

      }

    };



    initializeGemini();

  }, []);



  // Auto-scroll when typing indicator appears

  useEffect(() => {

    Object.keys(isTyping).forEach(step => {

      const stepNumber = parseInt(step);

      if (isTyping[stepNumber]) {

        scrollToBottom(stepNumber);

      }

    });

  }, [isTyping]);



  // Auto-show dataset overview if dataset is already active

  useEffect(() => {

    if (activeDatasetId && datasetConfig) {

      setShowDatasetOverview(true);

    }

  }, [activeDatasetId, datasetConfig]);

  // Update problem type when target variable type changes
  useEffect(() => {
    const inferredProblemType = inferProblemType(datasetConfig?.target_variable_type);
    setProblemType(inferredProblemType);
  }, [datasetConfig?.target_variable_type]);

  // Detect segments when target variable is set
  useEffect(() => {
    if (datasetConfig?.target_variable && activeDatasetId) {
      detectSegmentsForDataset();
    }
  }, [datasetConfig?.target_variable, activeDatasetId]);

  // Detect segments when entering training step (4.5)
  useEffect(() => {
    if (currentStep === 4.5 && datasetConfig?.target_variable && activeDatasetId) {
      detectSegmentsForDataset();
    }
  }, [currentStep]);

  // Capture original EDA when dataset is loaded (for comparison after treatments)
  useEffect(() => {
    const captureOriginalEDA = async () => {
      if (activeDatasetId && !originalEDA) {
        try {
          console.log('📊 Capturing original EDA for dataset:', activeDatasetId);
          const edaResponse = await fastApiService.getEDASnapshot(activeDatasetId, 'entire');
          if (edaResponse.success && edaResponse.eda_snapshot) {
            setOriginalEDA({
              timestamp: edaResponse.eda_snapshot.timestamp,
              totalRows: edaResponse.eda_snapshot.totalRows,
              totalColumns: edaResponse.eda_snapshot.totalColumns,
              numericStats: edaResponse.eda_snapshot.numericStats,
              categoricalStats: edaResponse.eda_snapshot.categoricalStats,
              dateStats: edaResponse.eda_snapshot.dateStats,
            });
            console.log('✅ Original EDA captured:', edaResponse.eda_snapshot.totalRows, 'rows');
          }
        } catch (error) {
          console.error('Failed to capture original EDA:', error);
        }
      }
    };
    captureOriginalEDA();
  }, [activeDatasetId, originalEDA]);

  // Function to detect segments in the dataset
  const detectSegmentsForDataset = async () => {
    if (!activeDatasetId) return;

    setIsDetectingSegments(true);
    try {
      console.log('🔍 Detecting segments for dataset:', activeDatasetId);
      const segmentDetectionResult = await fastApiService.detectSegments({
        dataset_id: activeDatasetId
      });

      console.log('📊 Segment detection result:', segmentDetectionResult);

      if (segmentDetectionResult.available) {
        console.log('✅ Segments found:', segmentDetectionResult.segments);
        setSegmentInfo(segmentDetectionResult);
        // Do NOT auto-switch training mode; leave it to user selection
      } else {
        console.log('❌ No segments found:', segmentDetectionResult.message);
        setSegmentInfo(segmentDetectionResult);
        setSegmentTrainingMode(false);
      }
    } catch (error) {
      console.error('❌ Error detecting segments:', error);
      setSegmentInfo(null);
      setSegmentTrainingMode(false);
    } finally {
      setIsDetectingSegments(false);
    }
  };



  // Data source selection handlers - analyze only the first uploaded file for column pickers; Step 1 analyzes each file for row counts.

  const runPrimaryDatasetAnalysis = async (file: File) => {
    try {
      setIsAnalyzingDataset(true);
      const analysisResult = await fastApiService.analyzeDataset({ file });
      if (analysisResult && analysisResult.success) {
        const analysis = {
          columns: analysisResult.dataset_info.columns,
          suggestedTargetVariable: analysisResult.dataset_info.suggested_target_variable,
          totalRows: analysisResult.dataset_info.total_rows,
          totalColumns: analysisResult.dataset_info.total_columns,
        };
        setDatasetAnalysis(analysis);
        sessionStorage.setItem('dataset_analysis', JSON.stringify(analysis));
        // Target and unique ID must be chosen explicitly by the user (suggestion is shown in Dataset Analysis only).
        setDatasetConfig((prev) => {
          const next = {
            target_variable: '',
            target_variable_type: 'Categorical' as const,
            dataset_structure_type: (prev?.dataset_structure_type ?? 'classification') as
              | 'classification'
              | 'regression'
              | 'time_series'
              | 'others',
            problem_statement: prev?.problem_statement ?? '',
            data_dictionary: prev?.data_dictionary ?? '',
            unique_id_combinations: [] as string[],
            segmentation_variable: '',
            weight_variable: '',
            sample_identifier_variable: '',
            split_configuration: createDefaultSplitConfiguration(),
            has_sampling_variable: false,
            sampling_variable: null,
            initial_scope: 'split',
            data_scope: 'split',
          };
          sessionStorage.setItem('dataset_config', JSON.stringify(next));
          return next;
        });
        setChatInputs((prev) => ({
          ...prev,
          ['target_var' as unknown as number]: '',
          ['target_type' as unknown as number]: 'Categorical',
          ['unique_id_combinations' as unknown as number]: [] as any,
        }));
      }
    } catch (error) {
      console.error('Dataset processing failed:', error);
    } finally {
      setIsAnalyzingDataset(false);
    }
  };

  const handleDataSourceSelect = async (dataSource: any) => {
    setShowDataSourceSelectionModal(false);

    setSelectedDataSources((prev) => {
      const prevFileCount = prev.filter((s) => s?.type === 'file' && s?.file instanceof File).length;
      const next = [...prev, dataSource];
      if (dataSource?.type === 'file' && dataSource?.file instanceof File && prevFileCount === 0) {
        void runPrimaryDatasetAnalysis(dataSource.file);
      }
      return next;
    });
  };

  const handleRemoveDataSource = (index: number) => {
    setSelectedDataSources((prev) => {
      const removed = prev[index];
      const next = prev.filter((_, i) => i !== index);
      const remainingFiles = next.filter((s) => s?.type === 'file' && s?.file instanceof File);
      const firstFileIndex = prev.findIndex((s) => s?.type === 'file' && s?.file instanceof File);
      const removedWasFirstFile = removed?.type === 'file' && firstFileIndex === index;

      queueMicrotask(() => {
        if (remainingFiles.length === 0) {
          setDatasetAnalysis(null);
          sessionStorage.removeItem('dataset_analysis');
          return;
        }
        if (removedWasFirstFile && remainingFiles[0]?.file) {
          void runPrimaryDatasetAnalysis(remainingFiles[0].file as File);
        }
      });

      return next;
    });
  };

  const handleUpdateFilePartition = (ingestionId: string, role: 'full' | 'train' | 'test' | 'oot') => {
    setSelectedDataSources((prev) => {
      const byId = prev.findIndex((s) => s.ingestionId === ingestionId);
      if (byId >= 0) {
        return prev.map((s, i) => (i === byId ? { ...s, partitionRole: role } : s));
      }
      const legacy = /^legacy-(\d+)-/.exec(ingestionId);
      if (legacy) {
        const fileIndex = parseInt(legacy[1], 10);
        const fileSlots = prev
          .map((s, idx) => ({ s, idx }))
          .filter((x) => x.s?.type === 'file' && x.s?.file instanceof File);
        const slot = fileSlots[fileIndex];
        if (slot) {
          const newIngestionId =
            slot.s.ingestionId || `ing-${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
          return prev.map((s, i) =>
            i === slot.idx ? { ...s, partitionRole: role, ingestionId: newIngestionId } : s
          );
        }
      }
      return prev;
    });
  };



  // Data Dictionary file selection handler

  const handleDataDictionaryFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {

    const file = e.target.files?.[0];

    if (file) {

      if (file.type === 'text/csv' || file.name.endsWith('.csv')) {

        setDataDictionaryFile(file);

        console.log('✅ Data Dictionary CSV selected:', file.name);

      } else {

        alert('Please select a CSV file for the data dictionary.');

        e.target.value = ''; // Reset the input

      }

    }

  };



  // Remove data dictionary file

  const handleRemoveDataDictionaryFile = () => {

    setDataDictionaryFile(null);

  };



  // Handle "Proceed to Configuration" - for pre-split: combines files; for platform: just proceed
  const handleProceedToConfig = async () => {
    try {
      setIsProceedingToConfig(true);
      
      // Determine workflow type
      const isPreSplitWorkflow = selectedDataSources.some((s) =>
        s?.type === 'file' && ['train', 'test', 'oot'].includes(String(s.partitionRole))
      );
      
      const isPlatformSplitWorkflow = selectedDataSources.some((s) => 
        s?.type === 'file' && s.partitionRole === 'full'
      );
      
      if (isPreSplitWorkflow) {
        // Pre-split workflow: Combine all files into one dataset with split_tag column
        const allFileSources = selectedDataSources.filter(
          (s) => s?.type === 'file' && s?.file instanceof File
        );
        
        if (allFileSources.length > 0) {
          console.log(`📦 Pre-split workflow: Combining ${allFileSources.length} files`);
          
          // Collect all files with their partition roles
          const filesWithRoles = allFileSources.map((s) => ({
            file: s.file as File,
            partitionRole: s.partitionRole as string,
          }));
          
          // Call backend to combine files
          const response = await fastApiService.combinePreSplitFiles({
            files: filesWithRoles,
            target_variable: (chatInputs['target_var' as unknown as number] as unknown as string) || '',
          });
          
          if (response?.dataset_id) {
            console.log(`✅ Pre-split files combined into dataset: ${response.dataset_id}`);
            // Store the combined dataset ID for later use
            sessionStorage.setItem('combined_presplit_dataset_id', response.dataset_id);
            // Store partition info for display
            sessionStorage.setItem('presplit_partitions', JSON.stringify(response.partitions));
            
            // Update datasetAnalysis to reflect the combined dataset's total rows
            // Before this, datasetAnalysis showed only the first file's row count
            if (response.total_rows && setDatasetAnalysis) {
              setDatasetAnalysis((prev) => {
                if (!prev) return prev;
                console.log(`📊 Updating datasetAnalysis totalRows: ${prev.totalRows} → ${response.total_rows}`);
                return {
                  ...prev,
                  totalRows: response.total_rows,
                };
              });
              // Also update sessionStorage
              const storedAnalysis = sessionStorage.getItem('dataset_analysis');
              if (storedAnalysis) {
                try {
                  const parsed = JSON.parse(storedAnalysis);
                  parsed.totalRows = response.total_rows;
                  sessionStorage.setItem('dataset_analysis', JSON.stringify(parsed));
                } catch (e) {
                  console.error('Failed to update dataset_analysis in sessionStorage:', e);
                }
              }
            }
          }
        }
      } else if (isPlatformSplitWorkflow) {
        // Platform split workflow: No combining needed, just proceed
        console.log('📦 Platform split workflow: Proceeding to configuration');
        // Clear any pre-split data
        sessionStorage.removeItem('combined_presplit_dataset_id');
        sessionStorage.removeItem('presplit_partitions');
      }
      
      // Mark as proceeded - shows Dataset Configuration section
      setHasProceededToConfig(true);
      
    } catch (error) {
      console.error('Failed to proceed to configuration:', error);
      alert('Failed to process files. Please try again.');
    } finally {
      setIsProceedingToConfig(false);
    }
  };

  // Submit dataset handler

  const handleSubmitDataset = async () => {

    try {

      setIsUploadingDataset(true);

      const fileSource = getSelectedFileSource();
      const targetVar = getTargetVariableForSubmit();
      const uniqueIds = getUniqueIdCombinationsForSubmit();

      console.info('📤 Dataset submit preflight:', {
        dataSourcesCount: selectedDataSources.length,
        hasFile: !!fileSource,
        fileName: fileSource?.file?.name,
        targetVar,
        uniqueIdsCount: uniqueIds.length,
        isAnalyzingDataset,
        isUploadingDataset,
        activeDatasetId,
        sessionDatasetId: typeof window !== 'undefined' ? sessionStorage.getItem('dataset_id') : null
      });

      if (!fileSource && !activeDatasetId && !pendingDatasetId) {
        console.warn('Upload blocked: no valid file selected', { selectedDataSources });
        setStep1SubmitError('Please add a CSV file as a data source before submitting.');
        alert('Please add at least one uploaded file as a data source.');

        return;

      }

      const file = fileSource?.file as File | undefined;
      const uploadedDatasetId = readStagedChunkedDatasetIdForSubmit(file);
      const submitDatasetId = activeDatasetId || pendingDatasetId || uploadedDatasetId || undefined;

      const targetType = getTargetVariableTypeForSubmit();
      if (!targetType) {
        setStep1SubmitError('Please select a variable category (Numerical or Categorical).');
        alert('Please select a variable category for the target variable.');
        setIsUploadingDataset(false);
        return;
      }

      const problemStmt = (chatInputs['problem_stmt' as unknown as number] as unknown as string) || '';

      if (!targetVar.trim()) {
        console.warn('Upload blocked: target variable is empty');
        setStep1SubmitError('Please choose a target variable.');
        alert('Please enter a target variable.');

        return;

      }

      // Validate unique_id_combinations is not empty
      if (uniqueIds.length === 0) {
        console.warn('Upload blocked: unique_id_combinations missing', { datasetConfig, chatInputsUniqueIds: chatInputs['unique_id_combinations' as unknown as number] });
        setStep1SubmitError('Please select at least one Unique ID variable.');
        alert('Please select at least one Unique ID variable.');

        setIsUploadingDataset(false);

        return;

      }

      // Read split configuration from sessionStorage
      const cfgRaw = sessionStorage.getItem('dataset_config');
      const cfg = cfgRaw ? JSON.parse(cfgRaw) : {};

      const isPlatformSplitWorkflow =
        selectedDataSources.some((s) => s?.type === 'file' && s.partitionRole === 'full') &&
        !selectedDataSources.some((s) =>
          s?.type === 'file' && ['train', 'test', 'oot'].includes(String(s.partitionRole))
        );

      const sc = cfg.split_configuration;
      const hasNewSplit = sc && typeof sc === 'object' && sc.ingestion_mode === 'platform_split';

      if (isPlatformSplitWorkflow && hasNewSplit) {
        const useIdentifier = sc.split_method === 'user_identifier';
        const splitErr = validateSplitConfigurationForSubmit(useIdentifier, sc, targetVar.trim());
        if (splitErr) {
          alert(splitErr);
          setIsUploadingDataset(false);
          return;
        }
      } else if (cfg.has_sampling_variable === true && !cfg.sampling_variable) {
        alert('Please select a sampling variable before submitting.');
        setIsUploadingDataset(false);
        return;
      }

      // Determine if this is a pre-split workflow
      const isPreSplitWorkflow = selectedDataSources.some((s) =>
        s?.type === 'file' && ['train', 'test', 'oot'].includes(String(s.partitionRole))
      );

      // Get all file sources for pre-split workflow
      const allFileSources = selectedDataSources.filter(
        (s) => s?.type === 'file' && s?.file instanceof File
      );

      // Prepare exclusion rules and variables to remove (shared across all files in pre-split mode)
      const exclusionRulesJson = cfg.exclusion_rules && cfg.exclusion_rules.length > 0 
        ? JSON.stringify(cfg.exclusion_rules) 
        : undefined;
      const variablesToRemoveJson = cfg.variables_to_remove && cfg.variables_to_remove.length > 0
        ? JSON.stringify(cfg.variables_to_remove)
        : undefined;

      let res: any;

      // For pre-split workflow, use the combined dataset from handleProceedToConfig
      if (isPreSplitWorkflow && allFileSources.length > 1) {
        // Get the combined dataset ID that was created in handleProceedToConfig
        const combinedDatasetId = sessionStorage.getItem('combined_presplit_dataset_id');
        
        if (!combinedDatasetId) {
          alert('Pre-split files have not been combined. Please click "Proceed to Configuration" first.');
          setIsUploadingDataset(false);
          return;
        }
        
        console.log(`📦 Pre-split workflow: Using combined dataset ${combinedDatasetId}`);
        
        // Apply exclusion rules and variable removal to the combined dataset
        // by calling a finalize endpoint
        const finalizeResponse = await fastApiService.finalizePreSplitDataset({
          dataset_id: combinedDatasetId,
          target_variable: targetVar.trim(),
          target_variable_type: targetType === 'Numerical' ? 'Numerical' : 'Categorical',
          problem_statement: problemStmt.trim() || undefined,
          data_dictionary: dataDictionaryFile || undefined,
          unique_id_combinations: datasetConfig?.unique_id_combinations || [],
          segmentation_variable: datasetConfig?.segmentation_variable || undefined,
          sample_identifier_variable: datasetConfig?.sample_identifier_variable || undefined,
          exclusion_rules: exclusionRulesJson,
          variables_to_remove: variablesToRemoveJson,
        });
        
        res = {
          dataset_id: combinedDatasetId,
          ...finalizeResponse,
        };
        
        console.log(`✅ Pre-split dataset finalized: ${combinedDatasetId}`);
        
      } else {
        // Single file upload (platform_split or single pre-split file)
        const partitionRole = fileSource.partitionRole as string | undefined;

        let splitConfigToSend: string | undefined;
        if (isPlatformSplitWorkflow && hasNewSplit) {
          splitConfigToSend = JSON.stringify(sc);
        } else if (isPreSplitWorkflow && partitionRole) {
          splitConfigToSend = JSON.stringify({
            ingestion_mode: 'pre_split',
            partition_role: partitionRole,
          });
        }

        res = await fastApiService.uploadDataset({

          file: submitDatasetId ? undefined : file,
          existing_dataset_id: submitDatasetId,

          target_variable: targetVar.trim(),

          target_variable_type: targetType === 'Numerical' ? 'Numerical' : 'Categorical',

          problem_statement: problemStmt.trim() || undefined,

          data_dictionary: dataDictionaryFile || undefined,

          unique_id_combinations: datasetConfig?.unique_id_combinations || [],

          segmentation_variable: datasetConfig?.segmentation_variable || undefined,

          sample_identifier_variable: datasetConfig?.sample_identifier_variable || undefined,

          // Split configuration
          has_sampling_variable: cfg.has_sampling_variable !== undefined ? cfg.has_sampling_variable : undefined,
          sampling_variable: cfg.sampling_variable || undefined,
          split_ratio: cfg.split_ratio !== undefined ? cfg.split_ratio : undefined,
          initial_scope: cfg.initial_scope || undefined,
          split_configuration: splitConfigToSend,
          // Exclusion rules from sessionStorage
          exclusion_rules: exclusionRulesJson,
          // Variables to remove from variable review
          variables_to_remove: variablesToRemoveJson,
          // Partition role for pre-split uploads
          partition_role: isPreSplitWorkflow ? partitionRole : undefined,

        });
      }

      if (res?.dataset_id) {
        try {
          // In staged mode (Objectives page), upload knowledge immediately after dataset creation
          // so first invocation across steps can use the indexed context.
          await fastApiService.updateUserKnowledgePreferences({
            dataset_id: res.dataset_id,
            scope: 'objectives',
            use_across_midas: stagedUseAcrossMidas,
            use_exl_expertise: stagedUseExlExpertise,
          });

          if (stagedUserKnowledgeFiles.length > 0) {
            const knowledgeResp = await fastApiService.uploadUserKnowledge({
              dataset_id: res.dataset_id,
              scope: 'objectives',
              use_across_midas: stagedUseAcrossMidas,
              use_exl_expertise: stagedUseExlExpertise,
              files: stagedUserKnowledgeFiles,
            });
            console.log('✅ Staged objectives knowledge indexed:', knowledgeResp);

            if (stagedUseAcrossMidas) {
              const currentGlobal = Number(sessionStorage.getItem('user_knowledge_global_files_count') || 0);
              sessionStorage.setItem(
                'user_knowledge_global_files_count',
                String(currentGlobal + stagedUserKnowledgeFiles.length)
              );
            }

            sessionStorage.setItem('user_knowledge_use_across_midas', String(stagedUseAcrossMidas));
            sessionStorage.setItem('user_knowledge_use_exl_expertise', String(stagedUseExlExpertise));
            setStagedUserKnowledgeFiles([]);
          }
        } catch (knowledgeErr) {
          // Keep dataset upload successful even if knowledge indexing fails.
          console.error('⚠️ Staged objectives knowledge upload failed:', knowledgeErr);
          setStep1SubmitError('Dataset uploaded, but business knowledge indexing failed. You can retry from the panel.');
        }

        sessionStorage.setItem('dataset_id', res.dataset_id);

        try {
          sessionStorage.removeItem(STAGED_CHUNKED_DATASET_ID_KEY);
          sessionStorage.removeItem(STAGED_CHUNKED_FILE_META_KEY);
        } catch {
          /* ignore */
        }

        // DON'T set activeDatasetId yet - wait for user to click OK on alert
        // setActiveDatasetId(res.dataset_id);

        // ✅ Apply split configuration automatically after upload
        // This replaces the separate "Apply" button in DataSplit component
        try {
          const sc = cfg.split_configuration as { ingestion_mode?: string } | undefined;
          const hasStep1Split =
            sc &&
            typeof sc === 'object' &&
            (sc.ingestion_mode === 'platform_split' || sc.ingestion_mode === 'pre_split');

          let scope: 'entire' | 'dev' | 'train' = 'dev';
          let ratio: number | undefined = cfg.split_ratio !== undefined ? cfg.split_ratio : 0.7;

          if (hasStep1Split) {
            scope = 'train';
            ratio = undefined;
          } else if (cfg.has_sampling_variable === true) {
            scope = 'dev';
          } else if (cfg.data_scope === 'entire' || cfg.initial_scope === 'entire') {
            scope = 'entire';
            ratio = 1.0;
          } else {
            scope = 'dev';
          }

          console.log(`📊 Applying split: scope=${scope}, ratio=${ratio}`);

          const scopePayload: Parameters<typeof fastApiService.setDatasetScope>[0] = {
            dataset_id: res.dataset_id,
            scope,
            seed: 42,
            sampling_variable: cfg.sampling_variable || undefined,
          };
          if (ratio !== undefined) {
            scopePayload.ratio = ratio;
          }
          const scopeRes = await fastApiService.setDatasetScope(scopePayload);
          
          console.log(`✅ Split applied: ${scopeRes.scope} (${scopeRes.shape?.[0] || 'unknown'} rows)`);
          
          // Dispatch events for other components to react
          window.dispatchEvent(new CustomEvent('datasetConfigChanged', {
            detail: {
              initial_scope: cfg.initial_scope || 'split',
              split_ratio: ratio,
              sampling_variable: cfg.sampling_variable,
            }
          }));
          window.dispatchEvent(new CustomEvent('datasetScopeChanged', {
            detail: { dataset_id: res.dataset_id, scope: scopeRes.scope }
          }));
        } catch (splitError) {
          console.error('⚠️ Failed to apply split configuration:', splitError);
          // Don't block the upload flow - split can be applied later
        }

        // Store dataset configuration in sessionStorage

        const config: {

          target_variable: string;

          target_variable_type: 'Numerical' | 'Categorical';

          dataset_structure_type: 'classification' | 'regression' | 'time_series' | 'others';

          problem_statement: string;

          data_dictionary: string;

          unique_id_combinations: string[];

          segmentation_variable: string;

          weight_variable: string;

          sample_identifier_variable: string;

        } = {

          target_variable: targetVar.trim(),

          target_variable_type: targetType === 'Numerical' ? 'Numerical' : 'Categorical',

          dataset_structure_type: 'classification',

          problem_statement: problemStmt.trim() || '',

          data_dictionary: dataDictionaryFile ? dataDictionaryFile.name : '',

          unique_id_combinations: uniqueIds,

          segmentation_variable: datasetConfig?.segmentation_variable || '',

          weight_variable: datasetConfig?.weight_variable || '',

          sample_identifier_variable: datasetConfig?.sample_identifier_variable || ''

        };

        // ✅ Merge: keep Step-1 split config (split_ratio/initial_scope/sampling_variable etc.)
    const cfgRaw2 = sessionStorage.getItem('dataset_config');
    const existingCfg = cfgRaw2 ? JSON.parse(cfgRaw2) : {};

    const mergedConfig = {
      ...existingCfg,  // keeps split settings
      ...config        // updates target/ids/segmentation fields
    };

    sessionStorage.setItem('dataset_config', JSON.stringify(mergedConfig));
    setDatasetConfig(mergedConfig);
    setStep1SubmitError(null);

        // NOTE: Scope remains as 'entire' (full data) after Submit
        // The right pane will show entire data by default
        // Agents will set scope to 'train' when needed for modeling

        // Clear the data dictionary file after successful upload

        setDataDictionaryFile(null);

        

        // Show custom alert with dataset ID immediately - don't wait for LLM classification
        setPendingDatasetId(res.dataset_id);
        setShowDatasetIdAlert(true);

        // Kick off ML problem-type classification in the background.
        //
        // P1.1: Use the new by-id endpoint so we DO NOT re-upload the file
        //       a second time. The backend reuses the cached/loaded DataFrame
        //       from the upload that just finished.
        //
        // P1.2: This is a true background task. Do NOT flip
        //       isAnalyzingDataset (that gates the Submit button) — only
        //       drive the ML-Problem-Type spinner via mlClassificationPending.
        //       The user can dismiss the dataset-id alert and proceed to
        //       Step 2 immediately while classification finishes silently.
        setMlClassificationPending(true);
        console.log('🤖 Classifying dataset type in background (by dataset_id, no re-upload)...');
        const _capturedConfig = { ...config };
        fastApiService.classifyDatasetTypeById({
          dataset_id: res.dataset_id,
          target_variable: targetVar.trim(),
          target_variable_type: targetType === 'Numerical' ? 'Numerical' : 'Categorical'
        }).then((classificationResult) => {
          if (classificationResult && classificationResult.success) {
            const suggestedType = classificationResult.dataset_type;
            console.log('🤖 Dataset type classification completed:', suggestedType);

            // ── React state update: triggers immediate re-render ──
            setMlClassificationResult({
              dataset_type: suggestedType,
              confidence: classificationResult.confidence,
              reasoning: classificationResult.reasoning,
              characteristics: classificationResult.characteristics,
              recommendations: classificationResult.recommendations,
            });
            setMlClassificationError(null);

            setChatInputs(prev => ({
              ...prev,
              ['dataset_structure_type' as unknown as number]: suggestedType
            }));
            // Merge with current sessionStorage so we do not drop Step-1 fields
            // (e.g. split_configuration.confirmed / partition_stats). Background
            // classification used to replace the whole object with _capturedConfig only,
            // which cleared confirmation and re-enabled editing when returning to Objectives.
            let persistedDatasetConfig: Record<string, unknown> = {};
            try {
              const rawPersisted = sessionStorage.getItem('dataset_config');
              if (rawPersisted) persistedDatasetConfig = JSON.parse(rawPersisted) as Record<string, unknown>;
            } catch {
              persistedDatasetConfig = {};
            }
            const updatedConfig = {
              ...persistedDatasetConfig,
              ..._capturedConfig,
              dataset_structure_type: suggestedType,
            };
            setDatasetConfig(updatedConfig);
            // Keep sessionStorage for persistence across page refreshes
            sessionStorage.setItem('dataset_config', JSON.stringify(updatedConfig));
            sessionStorage.setItem('dataset_classification', JSON.stringify({
              dataset_type: suggestedType,
              confidence: classificationResult.confidence,
              reasoning: classificationResult.reasoning,
              characteristics: classificationResult.characteristics,
              recommendations: classificationResult.recommendations,
              timestamp: new Date().toISOString()
            }));
          } else {
            console.error('❌ Dataset classification failed');
            setMlClassificationError('AI classification failed. Using default "Others" type.');
            setChatInputs(prev => ({ ...prev, ['dataset_structure_type' as unknown as number]: 'others' }));
            sessionStorage.setItem('dataset_classification_error', JSON.stringify({
              error: true, message: 'AI classification failed. Using default "Others" type.',
              timestamp: new Date().toISOString()
            }));
          }
        }).catch((classificationError) => {
          console.error('❌ Dataset classification error:', classificationError);
          const errMsg = classificationError instanceof Error ? classificationError.message : 'Unknown error';
          setMlClassificationError(`AI classification encountered an error. Using default "Others" type.`);
          setChatInputs(prev => ({ ...prev, ['dataset_structure_type' as unknown as number]: 'others' }));
          sessionStorage.setItem('dataset_classification_error', JSON.stringify({
            error: true,
            message: 'AI classification encountered an error. Using default "Others" type.',
            timestamp: new Date().toISOString(),
            details: errMsg
          }));
        }).finally(() => {
          // P1.2: Only the ML-Problem-Type spinner is cleared here. Submit
          // button is no longer gated by background classification.
          setMlClassificationPending(false);
        });
      }

    } catch (e: any) {

      alert(e?.message || 'Upload failed');

    } finally {

      setIsUploadingDataset(false);

    }

  };

  // Handler for dataset ID alert OK button
  const handleDatasetIdAlertOk = () => {
    if (!pendingDatasetId) {
      setShowDatasetIdAlert(false);
      return;
    }

    const datasetIdToLoad = pendingDatasetId;

    // Close alert and show dataset overview sidebar immediately
    setShowDatasetIdAlert(false);
    setPendingDatasetId(null);
    setActiveDatasetId(datasetIdToLoad);
    setShowDatasetOverview(true);

    // Reset duplicate removal state for the new dataset
    setDupWantsToRemove(null);
    setDupIsComplete(false);
    setDupIsSkipped(false);
    setDupRemovalResult(null);
    setDupSelectedVariables([]);
    setDupIdentificationResult(null);
    
    // Reset EDA comparison state for the new dataset
    setOriginalEDA(null);
    setCurrentEDA(null);
    setShowEDAComparison(false);
    setQcTemplates(null);
    
    console.log('✅ Dataset overview sidebar is now being displayed');
    console.log('🔄 Starting background API calls for variable classification and column info...');

    // Call classify-variables and column-info APIs in the BACKGROUND (non-blocking)
    // These will populate the sidebar as they complete.
    // Guard: only call classify-variables once per dataset to avoid redundant LLM calls.
    (async () => {
      if (classifiedDatasetIdsRef.current.has(datasetIdToLoad)) {
        console.log('⚡ classify-variables already called for this dataset - skipping');
        return;
      }
      classifiedDatasetIdsRef.current.add(datasetIdToLoad);
      try {
        console.log('🧠 Calling classify-variables API in background...');
        const classificationResult = await fastApiService.classifyDatasetVariables(datasetIdToLoad);
        console.log('✅ Variable classification completed:', classificationResult);
      } catch (error) {
        console.error('❌ Variable classification failed:', error);
        // Remove from set so a retry is possible if it genuinely failed
        classifiedDatasetIdsRef.current.delete(datasetIdToLoad);
      }
    })();

    (async () => {
      try {
        console.log('📊 Calling column-info API in background...');
        const columnInfoResult = await fastApiService.getColumnInfo(datasetIdToLoad);
        console.log('✅ Column info retrieved:', columnInfoResult);
        
        // Store the original column info for comparison with processed data
        if (columnInfoResult?.columns_info && !originalColumnInfo) {
          setOriginalColumnInfo(columnInfoResult.columns_info);
          console.log('📊 Stored original column info for comparison:', columnInfoResult.columns_info.length, 'columns');
        }
      } catch (error) {
        console.error('❌ Column info retrieval failed:', error);
      }
    })();
  };



  // Auto-scroll function for chat containers

  const scrollToBottom = (step: number) => {

    const container = chatContainerRefs.current[step];

    if (container) {

      setTimeout(() => {

        container.scrollTop = container.scrollHeight;

      }, 100); // Small delay to ensure content is rendered

    }

  };



  // Function to send hidden prompts to API without displaying them in chat
  const sendHiddenChatMessage = async (step: number, input: string) => {
    if (!input || !input.trim()) return;

    console.log(`🤫 Sending hidden chat message for step ${step}:`, input);

    // Set typing indicator (but don't show user message)
    setIsTyping(prev => ({ ...prev, [step]: true }));

    try {
      // First try backend chat API if dataset_id is available
      // Prefer the currently active dataset, fall back to sessionStorage.
      const datasetId = activeDatasetId || sessionStorage.getItem('dataset_id');
      if (datasetId) {
        try {
          console.log('🔗 Attempting backend chat API with dataset_id:', datasetId);
          const agentContext = getAgentContextFromStep(step);
          console.log(`📌 Agent context for step ${step}:`, agentContext);
          const result = await fastApiService.chatWithDataset({ 
            query: input, 
            dataset_id: datasetId,
            agent_context: agentContext
          });
          
          console.log('📥 Backend API response received:', result);

          // Handle different response types based on role
          let messageContent;
          if (result?.role === "plan_agent" || result?.role === "data_insight") {
            // For planner responses, store the entire result as JSON
            messageContent = JSON.stringify(result);
          } else {
            // For regular responses, use the response field or full result
            const aiResponse = result?.response || result || 'I could not generate a response at this time.';
            
            // Check if result has the structured format (response, code, suggestions)
            if (result?.response || result?.code || result?.suggestions) {
              messageContent = JSON.stringify(result);
            } else {
              messageContent = typeof aiResponse === 'string' ? aiResponse : JSON.stringify(aiResponse);
            }
          }

          const aiMessage = {
            id: (Date.now() + 1).toString(),
            type: 'assistant' as const,
            content: messageContent,
            timestamp: new Date(),
            knowledge_metadata: result?.knowledge_metadata,
          };

          setChatMessages(prev => ({
            ...prev,
            [step]: [...(prev[step] || []), aiMessage]
          }));

          // Scroll to bottom after adding AI response
          scrollToBottom(step);
          return; // Exit early since we got a response from backend
        } catch (fastApiError) {
          console.warn('⚠️ Backend chat API failed, falling back to Gemini:', fastApiError);
        }
      }

      // Fallback response
      const fallbackResponse = generateStepResponse(step, input);
      const aiMessage = {
        id: (Date.now() + 1).toString(),
        type: 'assistant' as const,
        content: fallbackResponse,
        timestamp: new Date(),
      };

      setChatMessages(prev => ({
        ...prev,
        [step]: [...(prev[step] || []), aiMessage]
      }));

      // Scroll to bottom after adding fallback response
      scrollToBottom(step);
    } catch (error) {
      console.error('❌ Error calling API for hidden message:', error);
    } finally {
      setIsTyping(prev => ({ ...prev, [step]: false }));
    }
  };

  // Treatment update functionality
  const handleCustomTreatmentChange = (key: string, value: string) => {
    setCustomTreatments(prev => ({
      ...prev,
      [key]: value
    }));
  };

  // Save custom treatments to backend (matching old file implementation)
  const handleSaveAllTreatments = async () => {
    if (!activeDatasetId) {
      alert('No active dataset found. Please upload a dataset first.');
      return;
    }

    console.log('🚀 Saving custom treatments:', customTreatments);
    console.log('📊 Custom treatments count:', Object.keys(customTreatments).length);
    console.log('🆔 Dataset ID:', activeDatasetId);

    setIsUpdatingTreatment(true);
    try {
      // Use fastApiService to maintain consistent authentication pattern
      const response = await fastApiService.updateCustomTreatments({
        dataset_id: activeDatasetId,
        custom_treatments: customTreatments
      });

      console.log('Custom treatments saved successfully:', response.data);
      alert(response.data.message || 'All custom treatments saved successfully!');
      
      // Keep the custom treatments visible in the UI
      // Don't clear the local state - let user see their saved treatments
      // The treatments are now saved in backend and will persist
      
    } catch (error) {
      console.error('Error saving treatments:', error);
      console.error('Error details:', error instanceof Error ? error.message : String(error));
      console.error('Custom treatments being sent:', customTreatments);
      console.error('Dataset ID:', activeDatasetId);
      alert(`Error saving treatments: ${error instanceof Error ? error.message : String(error)}. Please try again.`);
    } finally {
      setIsUpdatingTreatment(false);
    }
  };

  // Helper function to determine agent context from step number
  const getAgentContextFromStep = (step: number): string | null => {
    // Step 2 = Data Treatment
    if (step === 2){
      return 'data_transformation';
    }
    // Step 3 = Data Insights
    if (step === 3) {
      return 'data_insight';
    }
    if (step === 4) {
      return 'feature_engineering';
    }
    // Step 4.5 training, 5 evaluation = Modelling
    if ([4.5, 5].includes(step)) {
      return 'modelling';
    }
    // Other steps: let backend decide
    return null;
  };

  // Chat functionality handlers
  const handleSendChatMessage = async (
    step: number,
    directInput?: string
  ): Promise<FastAPIChatResponse | null> => {

    const input = directInput || chatInputs[step];

    if (!input || !input.trim()) return null;



    console.log(`🚀 Sending chat message for step ${step}:`, input);



    const userMessage = {

      id: Date.now().toString(),

      type: 'user' as const,

      content: input,

      timestamp: new Date(),

    };



    // Add user message to chat

    setChatMessages(prev => ({

      ...prev,

      [step]: [...(prev[step] || []), userMessage]

    }));



    // Clear input

    setChatInputs(prev => ({ ...prev, [step]: '' }));



    // Set typing indicator

    setIsTyping(prev => ({ ...prev, [step]: true }));



    try {

      // Try backend chat API if dataset_id is available
      // Prefer the currently active dataset, fall back to sessionStorage.
      const datasetId = activeDatasetId || sessionStorage.getItem('dataset_id');

      if (datasetId) {

        try {

          console.log('🔗 Attempting backend chat API with dataset_id:', datasetId);

          const agentContext = getAgentContextFromStep(step);
          console.log(`📌 Agent context for step ${step}:`, agentContext);

          const result = await fastApiService.chatWithDataset({ 

            query: input, 

            dataset_id: datasetId,
            agent_context: agentContext

          });

          

          console.log('📥 Backend API response received:', result);



          // Handle different response types based on role
          
          let messageContent;
          
          if (result?.role === "plan_agent" || result?.role === "data_insight") {
          
            // For planner responses, store the entire result as JSON
          
            messageContent = JSON.stringify(result);
          
          } else {

            // For regular responses, use the response field or full result

            const aiResponse = result?.response || result || 'I could not generate a response at this time.';

            

            // Check if result has the structured format (response, code, suggestions)

            if (result?.response || result?.code || result?.suggestions) {

              messageContent = JSON.stringify(result);

            } else {

              messageContent = typeof aiResponse === 'string' ? aiResponse : JSON.stringify(aiResponse);

            }

          }



          const aiMessage = {

            id: (Date.now() + 1).toString(),

            type: 'assistant' as const,

            content: messageContent,

            timestamp: new Date(),

            knowledge_metadata: result?.knowledge_metadata,

          };



          setChatMessages(prev => ({

            ...prev,

            [step]: [...(prev[step] || []), aiMessage]

          }));



          // Scroll to bottom after adding AI response

          scrollToBottom(step);

          return result;

        } catch (fastApiError) {

          console.warn('⚠️ Backend chat API failed, falling back to Gemini:', fastApiError);

        }

      }



      // Fallback response

      const fallbackResponse = generateStepResponse(step, input);

      const aiMessage = {

        id: (Date.now() + 1).toString(),

        type: 'assistant' as const,

        content: fallbackResponse,

        timestamp: new Date(),

      };



      setChatMessages(prev => ({

        ...prev,

        [step]: [...(prev[step] || []), aiMessage]

      }));



      // Scroll to bottom after adding fallback response

      scrollToBottom(step);
      return null;

    } catch (error) {

      console.error('❌ Error calling API:', error);
      return null;

    } finally {

      setIsTyping(prev => ({ ...prev, [step]: false }));

    }

  };



  const generateStepResponse = (step: number, userInput: string): string => {

    const stepContexts = {

      1: 'Objectives & Data',

      2: 'Data Treatment',

      3: 'Data Insights',

      3.5: 'Segmentation Agent Analysis',

      4: 'Feature Engineering',

      5: 'Model Evaluation',

      6: 'Algorithm Selection',

      7: 'Model Training',

      8: 'AI Explainability',

      9: 'Model Documentation'

    };



    const context = stepContexts[step as keyof typeof stepContexts] || 'Model Building';

    return `I understand you're working on ${context}. Based on your input: "${userInput}", here are some suggestions and insights to help you proceed with your model building process.`;

  };



  // Step-specific handlers
  const handleAutoQC = async () => {

    try {
    console.log('🚀 Running Auto Data Treatment...');

      console.log('🔍 Checking for dataset_id in sessionStorage:', sessionStorage.getItem('dataset_id'));
      
    const content = 'Please run comprehensive automated data quality checks on my dataset. Analyze invalid values, special values, outliers, and missing values.';

    // Auto QC fixed sequence: invalid_values -> special_values -> outliers -> missing_values
    const autoQCSequence = ['invalid_values', 'special_values', 'outliers', 'missing_values'];

    // Add user message to chat
    const userMessage = {
      id: Date.now().toString(),
      type: 'user' as const,
      content: 'Running Auto QC: Invalid Values → Special Values → Outliers → Missing Values',
      timestamp: new Date(),
    };

    setChatMessages(prev => ({
      ...prev,
      [2]: [...(prev[2] || []), userMessage]
    }));

    scrollToBottom(2);
    setIsTyping(prev => ({ ...prev, [2]: true }));

    const datasetId = activeDatasetId || sessionStorage.getItem('dataset_id');
    if (datasetId) {
      try {
        console.log('📤 Auto QC sending templates:', qcTemplates);
        const result = await fastApiService.chatWithDataset({
          query: content,
          dataset_id: datasetId,
          agent_context: 'data_quality',
          qc_mode: 'auto',
          treatment_sequence: autoQCSequence,
          qc_templates: qcTemplates,  // Pass uploaded templates (if any)
          qc_ui_selections: null
        });

        console.log('📥 Auto QC response received:', result);

        const aiMessage = {
          id: (Date.now() + 1).toString(),
          type: 'assistant' as const,
          content: JSON.stringify(result),
          timestamp: new Date(),
        };

        setChatMessages(prev => ({
          ...prev,
          [2]: [...(prev[2] || []), aiMessage]
        }));

        // ═══════════════════════════════════════════════════════════════════════════
        // AUTO-EXECUTE: Extract and execute all treatment codes sequentially
        // ═══════════════════════════════════════════════════════════════════════════
        console.log('📥 Auto QC raw result:', result);
        
        // Parse the response field which contains JSON-stringified treatment data
        let treatmentMessages: any[] = [];
        try {
          if (result?.response) {
            const parsedResponse = JSON.parse(result.response);
            console.log('📥 Parsed Auto QC response:', parsedResponse);
            treatmentMessages = parsedResponse?.treatment_messages || [];
          }
        } catch (parseError) {
          console.warn('⚠️ Failed to parse response JSON, using empty array:', parseError);
        }
        
        console.log(`📥 Auto QC: Received ${treatmentMessages.length} treatment messages from API`);
        
        if (treatmentMessages.length === 0) {
          console.warn('⚠️ No treatment_messages found! Checking result structure...');
          console.log('Result keys:', Object.keys(result || {}));
          console.log('Response string:', result?.response?.substring?.(0, 500));
        }
        
        const codesToExecute: { treatmentType: string; code: string; codeId: string; messageId: string }[] = [];

        // Collect all valid codes from treatment messages
        const baseMessageId = aiMessage.id;
        for (let i = 0; i < treatmentMessages.length; i++) {
          const treatment = treatmentMessages[i];
          console.log(`📋 Treatment ${i + 1}: ${treatment.treatment_type}, skipped=${treatment.skipped}, hasCode=${!!treatment.code}`);
          
          if (treatment.code && 
              treatment.code.trim() !== '' && 
              !treatment.code.includes('# No code') &&
              !treatment.code.includes('# No template') &&
              !treatment.skipped) {
            codesToExecute.push({
              treatmentType: treatment.treatment_type || 'unknown',
              code: treatment.code,
              codeId: generateCodeId(baseMessageId + '_' + i, treatment.code),
              messageId: baseMessageId + '_' + i
            });
            console.log(`  ✅ Will execute: ${treatment.treatment_type}`);
          } else {
            console.log(`  ⏭️ Skipping: ${treatment.treatment_type} (skipped=${treatment.skipped})`);
          }
        }

        console.log(`🔄 Auto QC: Found ${codesToExecute.length} treatments to execute`);

        // Execute each treatment code sequentially with progress messages
        let executedCount = 0;
        const executionSummary: string[] = [];
        
        for (let idx = 0; idx < codesToExecute.length; idx++) {
          const { treatmentType, code, codeId } = codesToExecute[idx];
          const treatmentLabel = treatmentType.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
          
          try {
            console.log(`⚙️ Auto-executing ${treatmentType} treatment (${idx + 1}/${codesToExecute.length})...`);
            
            // Add executing message to chat
            const executingMessage = {
              id: `exec-${codeId}`,
              type: 'assistant' as const,
              content: JSON.stringify({
                isExecutingTreatment: true,
                treatmentType: treatmentType,
                treatmentLabel: treatmentLabel,
                progress: `${idx + 1}/${codesToExecute.length}`,
                status: 'executing'
              }),
              timestamp: new Date(),
            };
            
            setChatMessages(prev => ({
              ...prev,
              [2]: [...(prev[2] || []), executingMessage]
            }));
            scrollToBottom(2);
            
            // Set loading state
            setExecutionResults(prev => ({
              ...prev,
              [codeId]: { isLoading: true, error: null }
            }));
            setExecutingCodeId(codeId);

            const execResult = await fastApiService.executeCode(datasetId, code);
            
            setExecutionResults(prev => ({
              ...prev,
              [codeId]: {
                success: execResult.success,
                response: execResult.response,
                columns_info: execResult.columns_info,
                isLoading: false,
                error: null
              }
            }));

            // Update the executing message to show completion
            if (execResult.success) {
              executedCount++;
              executionSummary.push(`✅ ${treatmentLabel}`);
              console.log(`✅ ${treatmentType} treatment applied successfully`);
              
              // Update message to show success
              setChatMessages(prev => {
                const messages = [...(prev[2] || [])];
                const msgIndex = messages.findIndex(m => m.id === `exec-${codeId}`);
                if (msgIndex !== -1) {
                  messages[msgIndex] = {
                    ...messages[msgIndex],
                    content: JSON.stringify({
                      isExecutingTreatment: true,
                      treatmentType: treatmentType,
                      treatmentLabel: treatmentLabel,
                      progress: `${idx + 1}/${codesToExecute.length}`,
                      status: 'success',
                      response: execResult.response || `${treatmentLabel} applied successfully`
                    })
                  };
                }
                return { ...prev, [2]: messages };
              });
            } else {
              executionSummary.push(`⚠️ ${treatmentLabel} (partial)`);
              console.warn(`⚠️ ${treatmentType} treatment execution returned false`);
            }
          } catch (execError) {
            console.error(`❌ Failed to execute ${treatmentType}:`, execError);
            executionSummary.push(`❌ ${treatmentLabel} (failed)`);
            setExecutionResults(prev => ({
              ...prev,
              [codeId]: {
                isLoading: false,
                error: execError instanceof Error ? execError.message : 'Execution failed'
              }
            }));
            
            // Update message to show error
            setChatMessages(prev => {
              const messages = [...(prev[2] || [])];
              const msgIndex = messages.findIndex(m => m.id === `exec-${codeId}`);
              if (msgIndex !== -1) {
                messages[msgIndex] = {
                  ...messages[msgIndex],
                  content: JSON.stringify({
                    isExecutingTreatment: true,
                    treatmentType: treatmentType,
                    treatmentLabel: treatmentLabel,
                    progress: `${idx + 1}/${codesToExecute.length}`,
                    status: 'error',
                    error: execError instanceof Error ? execError.message : 'Execution failed'
                  })
                };
              }
              return { ...prev, [2]: messages };
            });
          }
        }

        setExecutingCodeId(null);

        // ═══════════════════════════════════════════════════════════════════════════
        // POST-EXECUTION: Fetch updated EDA and show success message
        // ═══════════════════════════════════════════════════════════════════════════
        if (executedCount > 0) {
          console.log(`✅ Auto QC completed: ${executedCount}/${codesToExecute.length} treatments applied`);

          // Fetch updated EDA snapshot
          try {
            const edaResponse = await fastApiService.getEDASnapshot(datasetId, 'entire');
            if (edaResponse.success && edaResponse.eda_snapshot) {
              console.log('📊 Updated EDA fetched:', edaResponse.eda_snapshot);
              
              // Update currentEDA with new statistics (keep originalEDA unchanged)
              setCurrentEDA({
                timestamp: edaResponse.eda_snapshot.timestamp,
                totalRows: edaResponse.eda_snapshot.totalRows,
                totalColumns: edaResponse.eda_snapshot.totalColumns,
                numericStats: edaResponse.eda_snapshot.numericStats,
                categoricalStats: edaResponse.eda_snapshot.categoricalStats,
                dateStats: edaResponse.eda_snapshot.dateStats,
                treatmentApplied: 'Auto QC'
              });

              // Enable EDA comparison view, open sidebar, and trigger refresh
              setShowDatasetOverview(true);
              setShowEDAComparison(true);
              setEdaRefreshKey(prev => prev + 1); // Force sidebar to refetch comparison data
              triggerEdaComparisonView(); // Switch to Updated EDA sub-tab
            }
          } catch (edaError) {
            console.error('Failed to fetch updated EDA:', edaError);
          }

          // Add final success message to chat with summary
          const successMessage = {
            id: (Date.now() + 100).toString(),
            type: 'assistant' as const,
            content: JSON.stringify({
              response: `## ✅ All Treatments Applied Successfully!\n\n**Execution Summary:**\n${executionSummary.join('\n')}\n\n**${executedCount}** out of **${codesToExecute.length}** treatments executed successfully.\n\n📊 The dataset has been updated. Check the **EDA Comparison** panel on the right to see the updated statistics.`,
              isAutoQCComplete: true,
              executedCount: executedCount,
              totalTreatments: codesToExecute.length,
              summary: executionSummary
            }),
            timestamp: new Date(),
          };

          setChatMessages(prev => ({
            ...prev,
            [2]: [...(prev[2] || []), successMessage]
          }));
          scrollToBottom(2);

          // Auto-open the sidebar to show updated EDA
          setShowDatasetOverview(true);
        } else if (codesToExecute.length === 0) {
          // No treatments to execute (all skipped)
          const noTreatmentMessage = {
            id: (Date.now() + 100).toString(),
            type: 'assistant' as const,
            content: JSON.stringify({
              response: `ℹ️ **No treatments were executed.**\n\nAll treatments were either skipped (no template/rules found) or had no applicable code.\n\nTo apply treatments for Invalid Values and Special Values, please upload the corresponding templates.`,
              isAutoQCComplete: true,
              executedCount: 0,
              totalTreatments: 0
            }),
            timestamp: new Date(),
          };

          setChatMessages(prev => ({
            ...prev,
            [2]: [...(prev[2] || []), noTreatmentMessage]
          }));
          scrollToBottom(2);
        }

      } catch (error) {
        console.error('Auto QC API error:', error);
      } finally {
        setIsTyping(prev => ({ ...prev, [2]: false }));
      }
    }

    } catch (e) {
      console.error('Error running Auto Data Treatment:', e);
    }
  };



  const handleStandardQC = async () => {

    try {
    console.log('🚀 Running Standard QC with tasks:', selectedQCTasks);

      console.log('🔍 Checking for dataset_id in sessionStorage:', sessionStorage.getItem('dataset_id'));
      
      // Create display message for the user
    const displayMessage = `Performing Data Treatment on following tasks:\n• ${selectedQCTasks.join('\n• ')}`;

      
      // Create detailed prompt for the API
    const apiContent = `Please run the following data quality checks on my dataset: ${selectedQCTasks.join(', ')}. Provide detailed analysis and recommendations for each check.`;

    

    // Add the display message to chat

    const userMessage = {

      id: Date.now().toString(),

      type: 'user' as const,

      content: displayMessage,

      timestamp: new Date(),

    };



    setChatMessages(prev => ({

      ...prev,

      [2]: [...(prev[2] || []), userMessage]

    }));



      // Scroll to bottom after adding user message
    scrollToBottom(2);

      // Store the executed tasks for individual task buttons
    setLastExecutedQCTasks([...selectedQCTasks]);
    
    // Reset executed individual tasks when new QC plan is generated
    setExecutedIndividualQCTasks([]);
    
    // Initialize step-by-step QC state
    setQcStepByStepMode(true);
    setQcTreatmentSequence([...selectedQCTasks]);
    setQcCurrentStepIndex(0);
    // Initialize statuses: first is active, rest are pending
    const initialStatuses: Record<string, 'pending' | 'active' | 'applied' | 'skipped'> = {};
    selectedQCTasks.forEach((task, idx) => {
      initialStatuses[task] = idx === 0 ? 'active' : 'pending';
    });
    setQcTreatmentStatuses(initialStatuses);
    setQcTreatmentPlans({});
    
    // Set typing indicator
    setIsTyping(prev => ({ ...prev, [2]: true }));

    const datasetId = activeDatasetId || sessionStorage.getItem('dataset_id');
    if (datasetId) {
      try {
        // Manual QC: use user-selected sequence - now returns only FIRST treatment
        console.log('📤 Manual QC sending templates:', qcTemplates);
        const result = await fastApiService.chatWithDataset({
          query: apiContent,
          dataset_id: datasetId,
          agent_context: 'data_quality',
          qc_mode: 'manual',
          treatment_sequence: selectedQCTasks,
          qc_templates: qcTemplates,  // Pass uploaded templates
          qc_ui_selections: null
        });

        console.log('📥 Manual QC response received:', result);

        // Parse the response to extract step_info and treatment_type
        // The backend returns ChatResponse with response field containing JSON
        let parsedResponse: any = null;
        try {
          if (result.response) {
            parsedResponse = JSON.parse(result.response);
          }
        } catch (e) {
          console.log('Response is not JSON, treating as plain response');
        }

        // Update treatment statuses based on backend response
        // step_info is inside the parsed response, not at the top level
        const stepInfo = parsedResponse?.step_info || {};
        const currentTreatment = stepInfo.current_treatment || parsedResponse?.treatment_type;
        const skippedTreatments: string[] = stepInfo.skipped_treatments || [];
        
        console.log('📊 Parsed response:', { stepInfo, currentTreatment, skippedTreatments, parsedResponse });
        
        // Update statuses: mark skipped ones as 'skipped', current one as 'active'
        setQcTreatmentStatuses(prev => {
          const updated = { ...prev };
          // Mark auto-skipped treatments
          skippedTreatments.forEach((t: string) => {
            updated[t] = 'skipped';
          });
          // Mark current treatment as active
          if (currentTreatment && currentTreatment !== 'qc_complete') {
            updated[currentTreatment] = 'active';
          }
          console.log('📊 Updated qcTreatmentStatuses:', updated);
          return updated;
        });

        // Update current step index based on backend response
        if (stepInfo.current_step) {
          setQcCurrentStepIndex(stepInfo.current_step - 1);
        }

        // Store treatment plan for the current treatment
        if (currentTreatment && currentTreatment !== 'qc_complete') {
          setQcTreatmentPlans(prev => ({
            ...prev,
            [currentTreatment]: result
          }));
        }

        // Store the PARSED response (with treatment_type at top level) for proper rendering
        // The backend returns ChatResponse with response field containing JSON,
        // but the rendering logic expects treatment_type at the top level
        const aiMessage = {
          id: (Date.now() + 1).toString(),
          type: 'assistant' as const,
          content: parsedResponse ? JSON.stringify(parsedResponse) : JSON.stringify(result),
          timestamp: new Date(),
        };

        setChatMessages(prev => ({
          ...prev,
          [2]: [...(prev[2] || []), aiMessage]
        }));
      } catch (error) {
        console.error('Manual QC API error:', error);
        // Reset step-by-step mode on error
        setQcStepByStepMode(false);
      } finally {
        setIsTyping(prev => ({ ...prev, [2]: false }));
      }
    }
      
    setSelectedQCTasks([]);

    } catch (e) {
      console.error('Error running Standard QC:', e);
      setQcStepByStepMode(false);
    }
  };

  /**
   * Handle Apply Treatment button click in step-by-step Manual QC
   * Executes the treatment code and requests the next treatment plan
   */
  const handleQCApplyTreatment = async (treatmentType: string, code: string) => {
    const datasetId = activeDatasetId || sessionStorage.getItem('dataset_id');
    if (!datasetId) {
      console.error('No dataset ID available');
      return;
    }

    console.log(`🔧 Applying treatment: ${treatmentType}, code length: ${code?.length || 0}`);
    setQcIsApplyingTreatment(true);

    try {
      // Step 1: Execute code using the SAME endpoint that works for normal/Auto QC
      // This is the same flow as when all tables came at once
      if (code && code.trim() !== '# No code to display') {
        console.log('📤 Step 1: Executing treatment code via /execute-code...');
        const execResult = await fastApiService.executeCode(datasetId, code);
        
        if (!execResult?.success) {
          console.error('❌ Code execution failed:', execResult);
          throw new Error('Treatment code execution failed');
        }
        console.log('✅ Treatment code executed successfully');
      }

      // Step 2: Get next treatment plan (no code execution, just sequence management)
      console.log('📤 Step 2: Getting next treatment plan via /qc/next-step...');
      const result = await fastApiService.qcNextStep(datasetId, 'apply', treatmentType);
      
      console.log('✅ Next step retrieved:', result);
      
      // Check if API call was successful
      if (!result || !result.success) {
        console.error('❌ API returned unsuccessful result:', result);
        throw new Error(result?.error || 'Failed to get next treatment');
      }

      // Update status of current treatment to 'applied'
      setQcTreatmentStatuses(prev => ({
        ...prev,
        [treatmentType]: 'applied'
      }));

      // Refresh EDA/column stats after treatment application
      try {
        // Open sidebar and trigger EDA comparison refresh
        setShowDatasetOverview(true);
        setShowEDAComparison(true);
        setEdaRefreshKey(prev => prev + 1);
        triggerEdaComparisonView();
        
        // Fetch updated EDA snapshot for the Updated EDA tab
        const edaResponse = await fastApiService.getEDASnapshot(datasetId, 'entire');
        if (edaResponse?.success && edaResponse.eda_snapshot) {
          setCurrentEDA({
            totalRows: edaResponse.eda_snapshot.totalRows,
            totalColumns: edaResponse.eda_snapshot.totalColumns,
            numericStats: edaResponse.eda_snapshot.numericStats,
            categoricalStats: edaResponse.eda_snapshot.categoricalStats,
            dateStats: edaResponse.eda_snapshot.dateStats,
            treatmentApplied: treatmentType.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())
          });
        }
        console.log('✅ EDA comparison triggered after treatment application');
      } catch (refreshError) {
        console.warn('Failed to trigger EDA refresh after treatment:', refreshError);
      }

      // If there's a next treatment, add it to the chat and update state
      if (result.next_treatment && !result.is_complete) {
        const nextTreatmentType = result.step_info?.current_treatment || result.next_treatment?.treatment_type;
        const autoSkippedTreatments: string[] = (result.step_info as any)?.auto_skipped_treatments || [];
        
        // Mark any auto-skipped treatments
        if (autoSkippedTreatments.length > 0) {
          setQcTreatmentStatuses(prev => {
            const updated = { ...prev };
            autoSkippedTreatments.forEach((t: string) => {
              updated[t] = 'skipped';
            });
            return updated;
          });
          console.log('📊 Auto-skipped treatments:', autoSkippedTreatments);
        }
        
        if (nextTreatmentType) {
          // Store next treatment plan
          setQcTreatmentPlans(prev => ({
            ...prev,
            [nextTreatmentType]: result.next_treatment
          }));

          // Update status: next treatment is now active
          setQcTreatmentStatuses(prev => ({
            ...prev,
            [nextTreatmentType]: 'active'
          }));

          // Update current step index based on step_info if available
          if (result.step_info?.current_step) {
            setQcCurrentStepIndex(result.step_info.current_step - 1);
          } else {
            setQcCurrentStepIndex(prev => prev + 1);
          }

          // Add next treatment to chat
          const aiMessage = {
            id: (Date.now() + 1).toString(),
            type: 'assistant' as const,
            content: JSON.stringify(result.next_treatment),
            timestamp: new Date(),
          };

          setChatMessages(prev => ({
            ...prev,
            [2]: [...(prev[2] || []), aiMessage]
          }));

          scrollToBottom(2);
        }
      } else if (result.is_complete) {
        // All treatments complete
        setQcStepByStepMode(false);
        
        // Add completion message to chat
        const completionMessage = {
          id: (Date.now() + 1).toString(),
          type: 'assistant' as const,
          content: JSON.stringify(result.next_treatment || {
            response: '✅ All data quality treatments have been processed.',
            qc_complete: true
          }),
          timestamp: new Date(),
        };

        setChatMessages(prev => ({
          ...prev,
          [2]: [...(prev[2] || []), completionMessage]
        }));

        scrollToBottom(2);
      }

    } catch (error: any) {
      console.error('❌ Failed to apply treatment:', error);
      
      // Show error message in chat
      const errorMessage = {
        id: (Date.now() + 1).toString(),
        type: 'assistant' as const,
        content: JSON.stringify({
          response: `❌ **Failed to apply treatment**\n\nError: ${error?.message || 'Unknown error occurred'}`,
          error: true
        }),
        timestamp: new Date(),
      };
      
      setChatMessages(prev => ({
        ...prev,
        [2]: [...(prev[2] || []), errorMessage]
      }));
    } finally {
      setQcIsApplyingTreatment(false);
    }
  };

  /**
   * Handle Skip Treatment button click in step-by-step Manual QC
   * Skips the current treatment and requests the next treatment plan
   */
  const handleQCSkipTreatment = async (treatmentType: string) => {
    const datasetId = activeDatasetId || sessionStorage.getItem('dataset_id');
    if (!datasetId) {
      console.error('No dataset ID available');
      return;
    }

    console.log(`⏭️ Skipping treatment: ${treatmentType}`);
    setQcIsApplyingTreatment(true);

    try {
      // Call the API to skip treatment and get next step
      const result = await fastApiService.skipQCTreatment(datasetId, treatmentType);
      
      console.log('✅ Treatment skipped, next step:', result);

      // Update status of current treatment to 'skipped'
      setQcTreatmentStatuses(prev => ({
        ...prev,
        [treatmentType]: 'skipped'
      }));

      // If there's a next treatment, add it to the chat and update state
      if (result.next_treatment && !result.is_complete) {
        const nextTreatmentType = result.step_info?.current_treatment || result.next_treatment?.treatment_type;
        const autoSkippedTreatments: string[] = (result.step_info as any)?.auto_skipped_treatments || [];
        
        // Mark any auto-skipped treatments
        if (autoSkippedTreatments.length > 0) {
          setQcTreatmentStatuses(prev => {
            const updated = { ...prev };
            autoSkippedTreatments.forEach((t: string) => {
              updated[t] = 'skipped';
            });
            return updated;
          });
          console.log('📊 Auto-skipped treatments:', autoSkippedTreatments);
        }
        
        if (nextTreatmentType) {
          // Store next treatment plan
          setQcTreatmentPlans(prev => ({
            ...prev,
            [nextTreatmentType]: result.next_treatment
          }));

          // Update status: next treatment is now active
          setQcTreatmentStatuses(prev => ({
            ...prev,
            [nextTreatmentType]: 'active'
          }));

          // Update current step index based on step_info if available
          if (result.step_info?.current_step) {
            setQcCurrentStepIndex(result.step_info.current_step - 1);
          } else {
            setQcCurrentStepIndex(prev => prev + 1);
          }

          // Add next treatment to chat
          const aiMessage = {
            id: (Date.now() + 1).toString(),
            type: 'assistant' as const,
            content: JSON.stringify(result.next_treatment),
            timestamp: new Date(),
          };

          setChatMessages(prev => ({
            ...prev,
            [2]: [...(prev[2] || []), aiMessage]
          }));

          scrollToBottom(2);
        }
      } else if (result.is_complete) {
        // All treatments complete
        setQcStepByStepMode(false);
        
        // Add completion message to chat
        const completionMessage = {
          id: (Date.now() + 1).toString(),
          type: 'assistant' as const,
          content: JSON.stringify(result.next_treatment || {
            response: '✅ All data quality treatments have been processed.',
            qc_complete: true
          }),
          timestamp: new Date(),
        };

        setChatMessages(prev => ({
          ...prev,
          [2]: [...(prev[2] || []), completionMessage]
        }));

        scrollToBottom(2);
      }

    } catch (error) {
      console.error('❌ Failed to skip treatment:', error);
    } finally {
      setQcIsApplyingTreatment(false);
    }
  };


  const handleQCTaskToggle = (task: string, checked: boolean) => {

    if (checked) {

      setSelectedQCTasks(prev => [...prev, task]);

    } else {

      setSelectedQCTasks(prev => prev.filter(t => t !== task));

    }

  };

  

  // Map selected QC task IDs to action messages
  const getQCActionMessageFromTaskId = (taskId: string): string => {
    switch (taskId) {
      case 'missing_values':
        return 'Perform missing value imputation';
      case 'outliers':
        return 'Perform outlier treatment';
      case 'duplicates':
        return 'Perform duplicate removal';
      case 'data_types':
        return 'Perform data type validation and correction';
      case 'distribution':
        return 'Perform distribution analysis';
      case 'correlation':
        return 'Perform correlation analysis';
      default:
        // For custom tasks, use them as-is or with "Perform" prefix if needed
        return taskId.startsWith('Perform') ? taskId : `Perform ${taskId}`;
    }
  };

  // Get action-oriented message for QC task categories (for plan-based categories)
  const getQCActionMessage = (category: string): string => {
    const categoryLower = category.toLowerCase();
    
    // Map common QC categories to action messages
    if (categoryLower.includes('missing') || categoryLower.includes('null')) {
      return 'Perform missing value imputation';
    } else if (categoryLower.includes('outlier')) {
      return 'Perform outlier treatment';
    } else if (categoryLower.includes('duplicate')) {
      return 'Perform duplicate removal';
    } else if (categoryLower.includes('data type') || categoryLower.includes('datatype')) {
      return 'Perform data type validation and correction';
    } else if (categoryLower.includes('encoding')) {
      return 'Perform categorical encoding';
    } else if (categoryLower.includes('scaling') || categoryLower.includes('normalization')) {
      return 'Perform data scaling and normalization';
    } else if (categoryLower.includes('correlation')) {
      return 'Perform correlation analysis';
    } else if (categoryLower.includes('distribution')) {
      return 'Perform distribution analysis';
    } else if (categoryLower.includes('feature')) {
      return 'Perform feature analysis';
    } else if (categoryLower.includes('validation')) {
      return 'Perform data validation';
    } else if (categoryLower.includes('quality')) {
      return 'Perform data quality assessment';
    } else if (categoryLower.includes('consistency')) {
      return 'Perform data consistency check';
    } else if (categoryLower.includes('completeness')) {
      return 'Perform data completeness analysis';
    } else if (categoryLower.includes('accuracy')) {
      return 'Perform data accuracy validation';
    } else {
      // Generic fallback for any other category
      return `Perform ${category.toLowerCase()} analysis`;
    }
  };

  const getKnowledgeMetadata = (message: any, parsed?: any) => {
    if (message?.knowledge_metadata) {
      return message.knowledge_metadata;
    }
    if (parsed && typeof parsed === 'object' && parsed.knowledge_metadata) {
      return parsed.knowledge_metadata;
    }
    return undefined;
  };

  // Handle individual QC task execution by selected task ID
  const handleIndividualQCTaskByTaskId = async (taskId: string) => {
    try {
      // Check if task is already executed
      if (executedIndividualQCTasks.includes(taskId)) {
        console.log('🚫 Task already executed:', { taskId });
        return;
      }

      console.log('🎯 Running individual QC task:', { taskId });
      
      // Mark task as executed immediately to prevent double-clicking
      setExecutedIndividualQCTasks(prev => [...prev, taskId]);
      
      // Get the action message that will be displayed to user and sent to backend
      const actionMessage = getQCActionMessageFromTaskId(taskId);

      // Add user message to chat showing which task is being executed
      const userMessage = {
        id: Date.now().toString(),
        type: 'user' as const,
        content: actionMessage,
        timestamp: new Date(),
      };

      setChatMessages(prev => ({
        ...prev,
        [2]: [...(prev[2] || []), userMessage]
      }));

      // Scroll to bottom after adding user message
      scrollToBottom(2);

      // Send the exact same message that appears in chat to the backend
      console.log('📤 Calling sendHiddenChatMessage(2) with exact user message:', actionMessage);
      await sendHiddenChatMessage(2, actionMessage);
    } catch (e) {
      console.error('Error running individual QC task:', e);
      // Remove from executed tasks if there was an error
      setExecutedIndividualQCTasks(prev => prev.filter(id => id !== taskId));
    }
  };

  // Handle individual QC task execution by category (fallback for plan-based categories)
  const handleIndividualQCTaskByCategory = async (category: string, items: any[]) => {
    try {
      console.log('🎯 Running individual QC task category:', { category, itemCount: items.length });
      
      // Get the action message that will be displayed to user and sent to backend
      const actionMessage = getQCActionMessage(category);

      // Add user message to chat showing which task category is being executed
      const userMessage = {
        id: Date.now().toString(),
        type: 'user' as const,
        content: actionMessage,
        timestamp: new Date(),
      };

      setChatMessages(prev => ({
        ...prev,
        [2]: [...(prev[2] || []), userMessage]
      }));

      // Scroll to bottom after adding user message
      scrollToBottom(2);

      // Send the exact same message that appears in chat to the backend
      console.log('📤 Calling sendHiddenChatMessage(2) with exact user message:', actionMessage);
      await sendHiddenChatMessage(2, actionMessage);
    } catch (e) {
      console.error('Error running individual QC task category:', e);
    }
  };



  // Similar handlers for other steps

  const handleInsightStepToggle = (step: string, checked: boolean) => {

    if (checked) {

      setSelectedInsightSteps(prev => [...prev, step]);

    } else {

      setSelectedInsightSteps(prev => prev.filter(s => s !== step));

    }

  };



  const handleStandardDataInsights = async (stepsOverride?: string[]) => {
    // Ignore non-arrays (e.g. React passes a click event if the handler is bound directly to onClick).
    const steps = Array.isArray(stepsOverride) ? stepsOverride : selectedInsightSteps;

    console.log(
      '🚀 Running Standard Data Insights (REST prefetch for selected analysis APIs + chat):',
      steps
    );

    if (steps.length === 0) {
      return;
    }

    const content = `Generate insights for: ${steps.join(', ')}`;
    // Standard flow replaces the sidebar panels (hide auto-insight results)
    setInsightsGenerationSource('standard');
    try {
      sessionStorage.setItem('model_builder_insights_source', 'standard');
    } catch {}
    const next = [...steps];
    setLastStandardInsightSteps(next);
    try {
      sessionStorage.setItem('model_builder_last_standard_insight_steps', JSON.stringify(next));
    } catch {}
    setDisplayedInsightSteps(next);
    try {
      sessionStorage.setItem('model_builder_displayed_insight_steps', JSON.stringify(next));
    } catch {}

    const apiSteps = filterToPrefetchableInsightSteps(steps);
    const datasetId = activeDatasetId;
    const target = datasetConfig?.target_variable?.trim();

    const idleAll: Record<AutoInsightStepId, AutoInsightStepStatus> = {
      bivariate_analysis: 'idle',
      correlation_analysis: 'idle',
      iv_analysis: 'idle',
      variance_inflation_factor: 'idle',
      correlation_matrix: 'idle',
      correlation_ratio_analysis: 'idle',
    };
    const statusForRun: Record<AutoInsightStepId, AutoInsightStepStatus> = { ...idleAll };
    for (const id of apiSteps) {
      statusForRun[id] = 'running';
    }
    setAutoInsightStepStatus(statusForRun);

    setAutoInsightStepStatus(statusForRun);

    // Clear only the selection checkboxes
    setSelectedInsightSteps([]);

    if (datasetId && target && apiSteps.length > 0) {
      runAutoInsightApiPrefetches(
        datasetId,
        target,
        (stepId, status) => {
          setAutoInsightStepStatus((prev) => ({ ...prev, [stepId]: status }));
        },
        { onlyStepIds: apiSteps }
      ).catch((e) => {
        console.error('Standard Data Insights REST prefetch failed:', e);
      });
    } else if (apiSteps.length > 0 && (!datasetId || !target)) {
      setAutoInsightStepStatus((prev) => {
        const merged = { ...prev };
        for (const id of apiSteps) merged[id] = 'error';
        return merged;
      });
    }

    await handleSendChatMessage(3, content);
    // Cache standard insights completion status
    try {
      sessionStorage.setItem('model_builder_standard_insights_cached', 'true');
      // Cache chat messages
      const currentChatMessages = chatMessages[3];
      sessionStorage.setItem('model_builder_standard_chat_messages', JSON.stringify(currentChatMessages));
    } catch {}
  };

  /** Clear sidebar + step 3 chat before switching between Auto and Standard so the new run is the only visible context. */
  const resetStep3InsightPresentationForModeSwitch = () => {
    setDisplayedInsightSteps([]);
    setInsightsGenerationSource(null);
    try {
      sessionStorage.removeItem('model_builder_displayed_insight_steps');
      sessionStorage.removeItem('model_builder_insights_source');
    } catch {}
    setChatMessages((prev) => ({ ...prev, 3: [] }));
    setIsTyping((prev) => ({ ...prev, 3: false }));    // Cache standard insights completion status
    try {
      sessionStorage.setItem('model_builder_standard_insights_cached', 'true');
      // Cache chat messages
      const currentChatMessages = chatMessages[3];
      sessionStorage.setItem('model_builder_standard_chat_messages', JSON.stringify(currentChatMessages));
    } catch {}
  };

  // Load dataset preview
  const loadDatasetPreview = async () => {
    if (!activeDatasetId) return;
    
    try {
      const response = await fastApiService.getDatasetPreview(activeDatasetId);
      if (response.success) {
        setDatasetPreview(response);
      }
    } catch (error) {
      console.error('Failed to load dataset preview:', error);
    }
  };

  // Load dataset preview when dataset changes
  useEffect(() => {
    if (activeDatasetId && currentStep === 3.5) {
      loadDatasetPreview();
    }
  }, [activeDatasetId, currentStep]);

  // Refresh dataset preview when scope changes
  useEffect(() => {
    const handleScopeChange = async (event: Event) => {
      const customEvent = event as CustomEvent;
      if (customEvent.detail?.dataset_id === activeDatasetId) {
        // Reload dataset preview after scope change
        await loadDatasetPreview();
      }
    };

    window.addEventListener('datasetScopeChanged', handleScopeChange);
    return () => {
      window.removeEventListener('datasetScopeChanged', handleScopeChange);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeDatasetId]);

  // Load current dataset columns from preview (dynamic, updates when dataset/segmentation changes)
  useEffect(() => {
    const loadDatasetColumns = async () => {
      if (!activeDatasetId) {
        setCurrentDatasetColumns([]);
        return;
      }
      
      try {
        // Try segmented dataset preview first (most up-to-date, reflects segmentation changes)
        const response = await fastApiService.getSegmentedDatasetPreview(activeDatasetId);
        if (response.success && response.preview_data?.columns) {
          const columns = response.preview_data.columns
            .filter((col: string) => 
              col !== datasetConfig?.target_variable && 
              col.toLowerCase() !== 'segment' &&
              col.toLowerCase() !== 'id' &&
              col.toLowerCase() !== 'member_id'
            );
          setCurrentDatasetColumns(columns);
          return;
        }
      } catch (error) {
        // Fallback to regular preview if segmented preview not available
        try {
          const response = await fastApiService.getDatasetPreview(activeDatasetId);
          if (response.success && response.preview_data?.columns) {
            const columns = response.preview_data.columns
              .filter((col: string) => 
                col !== datasetConfig?.target_variable &&
                col.toLowerCase() !== 'id' &&
                col.toLowerCase() !== 'member_id'
              );
            setCurrentDatasetColumns(columns);
            return;
          }
        } catch (fallbackError) {
          console.error('Failed to load dataset columns from preview:', fallbackError);
        }
      }
      
      // Final fallback to datasetAnalysis (static, from initial analysis)
      if (datasetAnalysis?.columns) {
        const columns = datasetAnalysis.columns
          .map(c => c.name)
          .filter(name => 
            name !== datasetConfig?.target_variable &&
            name.toLowerCase() !== 'segment'
          );
        setCurrentDatasetColumns(columns);
      } else {
        setCurrentDatasetColumns([]);
      }
    };
    
    loadDatasetColumns();
  }, [activeDatasetId, datasetConfig?.target_variable, datasetAnalysis, currentStep, datasetPreview]);

  // Also refresh columns when dataset scope changes (after data treatment)
  useEffect(() => {
    if (!activeDatasetId) return;

    const handleDatasetScopeChanged = async (event: Event) => {
      const customEvent = event as CustomEvent<{ dataset_id: string; scope: string }>;
      if (customEvent.detail?.dataset_id === activeDatasetId) {
        // Refresh columns when dataset scope changes (indicates data treatment completed)
        try {
          const response = await fastApiService.getDatasetPreview(activeDatasetId);
          if (response.success && response.preview_data?.columns) {
            const columns = response.preview_data.columns
              .filter((col: string) => 
                col !== datasetConfig?.target_variable &&
                col.toLowerCase() !== 'id' &&
                col.toLowerCase() !== 'member_id'
              );
            setCurrentDatasetColumns(columns);
          }
        } catch (error) {
          console.error('Failed to refresh columns after dataset scope change:', error);
        }
      }
    };

    window.addEventListener('datasetScopeChanged', handleDatasetScopeChanged);
    return () => {
      window.removeEventListener('datasetScopeChanged', handleDatasetScopeChanged);
    };
  }, [activeDatasetId, datasetConfig?.target_variable]);


  // Feature Engineering handlers

  const handleFeatureStepToggle = (step: string, checked: boolean) => {

    if (checked) {

      setSelectedFeatureSteps(prev => [...prev, step]);

    } else {

      setSelectedFeatureSteps(prev => prev.filter(s => s !== step));

    }

  };



  const handleAutoFeatureEngineering = async () => {

    console.log('🚀 Running Auto Feature Engineering...');

    const content = 'Run comprehensive Auto Feature Engineering on my data';

    await handleSendChatMessage(4, content);

  };



  const handleStandardFeatureEngineering = async () => {

    console.log('🚀 Running Standard Feature Engineering with steps:', selectedFeatureSteps);

    const content = `Standard Feature Engineering request: Perform ${selectedFeatureSteps.join(', ')}`;

    setSelectedFeatureSteps([]);

    await handleSendChatMessage(4, content);

  };



  // Data Splitting handlers

  const handleSplitStepToggle = (step: string, checked: boolean) => {

    if (checked) {

      setSelectedSplitSteps(prev => [...prev, step]);

    } else {

      setSelectedSplitSteps(prev => prev.filter(s => s !== step));

    }

  };



  const handleAutoDataSplitting = async () => {

    console.log('🚀 Running Auto Data Splitting...');

    const content = 'Run comprehensive Auto Data Splitting strategy for my model';

    await handleSendChatMessage(5, content);

  };



  const handleStandardDataSplitting = async () => {

    console.log('🚀 Running Standard Data Splitting with steps:', selectedSplitSteps);

    const content = `Standard Data Splitting request: Perform ${selectedSplitSteps.join(', ')}`;

    setSelectedSplitSteps([]);

    await handleSendChatMessage(5, content);

  };



  // Algorithm Selection handlers

  const handleAlgorithmStepToggle = (step: string, checked: boolean) => {

    if (checked) {

      setSelectedAlgorithmSteps(prev => [...prev, step]);

    } else {

      setSelectedAlgorithmSteps(prev => prev.filter(s => s !== step));

    }

  };



  const handleAutoAlgorithmSelection = async () => {

    console.log('🚀 Running Auto Algorithm Selection...');

    const content = 'Run comprehensive Auto Algorithm Selection for my data and problem';

    await handleSendChatMessage(6, content);

  };



  const handleStandardAlgorithmSelection = async () => {

    console.log('🚀 Running Standard Algorithm Selection with steps:', selectedAlgorithmSteps);

    const content = `Standard Algorithm Selection request: Evaluate ${selectedAlgorithmSteps.join(', ')}`;

    setSelectedAlgorithmSteps([]);

    await handleSendChatMessage(6, content);

  };



  // Model Training handlers

  const handleTrainingStepToggle = (step: string, checked: boolean) => {

    if (checked) {

      setSelectedTrainingSteps(prev => [...prev, step]);

    } else {

      setSelectedTrainingSteps(prev => prev.filter(s => s !== step));

    }

  };



  const handleAutoAlgorithmTraining = async () => {

    console.log('🚀 Running Auto Algorithm Training...');

    const content = 'Run comprehensive Auto Algorithm Training and optimization';

    await handleSendChatMessage(7, content);

  };



  const handleStandardAlgorithmTraining = async () => {

    console.log('🚀 Running Standard Algorithm Training with steps:', selectedTrainingSteps);

    const content = `Standard Algorithm Training request: Perform ${selectedTrainingSteps.join(', ')}`;

    setSelectedTrainingSteps([]);

    await handleSendChatMessage(7, content);

  };



  // Model Deployment handlers

  const handleDeploymentStepToggle = (step: string, checked: boolean) => {

    if (checked) {

      setSelectedDeploymentSteps(prev => [...prev, step]);

    } else {

      setSelectedDeploymentSteps(prev => prev.filter(s => s !== step));

    }

  };



  const handleAutoModelDeployment = async () => {

    console.log('🚀 Running Auto Model Deployment...');

    const content = 'Run comprehensive Auto Model Deployment to production';

    await handleSendChatMessage(8, content);

  };



  const handleStandardModelDeployment = async () => {

    console.log('🚀 Running Standard Model Deployment with steps:', selectedDeploymentSteps);

    const content = `Standard Model Deployment request: Perform ${selectedDeploymentSteps.join(', ')}`;

    setSelectedDeploymentSteps([]);

    await handleSendChatMessage(8, content);

  };



  // Code execution functions
  const executeCode = async (codeId: string, code: string) => {
    const datasetId = sessionStorage.getItem('dataset_id');
    if (!datasetId) {
      console.error('❌ No dataset ID found in session storage');
      return;
    }

    // Capture rolling n-1 baseline before execution for this specific code block.
    let baselineColumns = originalColumnInfo;
    if (!baselineColumns || baselineColumns.length === 0) {
      try {
        const baseline = await fastApiService.getColumnInfo(datasetId);
        if (baseline?.columns_info?.length) {
          baselineColumns = baseline.columns_info;
          setOriginalColumnInfo(baseline.columns_info);
          console.log('📊 Baseline column info loaded for highlighting:', baseline.columns_info.length);
        }
      } catch (baselineErr) {
        console.warn('⚠️ Could not prefetch baseline column info for highlighting:', baselineErr);
      }
    }
    setExecutionBaselines(prev => ({
      ...prev,
      [codeId]: baselineColumns || []
    }));

    // Set loading state for this specific code execution
    setExecutionResults(prev => ({
      ...prev,
      [codeId]: {
        ...prev[codeId],
        isLoading: true,
        error: null
      }
    }));
    setExecutingCodeId(codeId);

    try {
      console.log('🚀 Executing code:', codeId);
      const result = await fastApiService.executeCode(datasetId, code);
      
      console.log('📊 Code execution result:', {
        success: result.success,
        response: result.response,
        has_columns_info: !!result.columns_info,
        columns_info_length: result.columns_info?.length || 0,
        columns_info: result.columns_info
      });
      
      setExecutionResults(prev => ({
        ...prev,
        [codeId]: {
          success: result.success,
          response: result.response,
          columns_info: result.columns_info,
          isLoading: false,
          error: null
        }
      }));

      // Advance rolling baseline to latest n for subsequent executions.
      if (result?.columns_info?.length) {
        setOriginalColumnInfo(result.columns_info);
      }
      
      console.log('✅ Code execution completed. Column Stats table should', 
        result.columns_info && result.columns_info.length > 0 ? 'APPEAR' : 'NOT APPEAR');

      // On the Data Treatment step, every successful treatment (manual Apply Treatment, Auto QC
      // individual blocks, manual code execution) should refresh the EDA Comparison view so
      // train/validation statistics reflect the latest state without requiring duplicate removal
      // or the full Auto-QC flow to run. We also make the EDA Comparison tab available here so
      // users can open it right away via the sidebar tab or the "View Updated EDA" button.
      if (result?.success && currentStep === 2) {
        setShowEDAComparison(true);
        setEdaRefreshKey(prev => prev + 1);

        // Refresh the "entire" EDA snapshot in the background so the Updated EDA sub-tab
        // header stats (total rows / columns) stay in sync with the latest treatment.
        try {
          const edaResponse = await fastApiService.getEDASnapshot(datasetId, 'entire');
          if (edaResponse?.success && edaResponse.eda_snapshot) {
            setCurrentEDA({
              timestamp: edaResponse.eda_snapshot.timestamp,
              totalRows: edaResponse.eda_snapshot.totalRows,
              totalColumns: edaResponse.eda_snapshot.totalColumns,
              numericStats: edaResponse.eda_snapshot.numericStats,
              categoricalStats: edaResponse.eda_snapshot.categoricalStats,
              dateStats: edaResponse.eda_snapshot.dateStats,
              treatmentApplied: 'Treatment Applied',
            });
          }
        } catch (edaErr) {
          console.warn('⚠️ Post-treatment EDA snapshot refresh failed:', edaErr);
        }
      }
    } catch (error) {
      console.error('❌ Code execution failed:', error);
      setExecutionResults(prev => ({
        ...prev,
        [codeId]: {
          ...prev[codeId],
          isLoading: false,
          error: error instanceof Error ? error.message : 'Unknown error occurred'
        }
      }));
    } finally {
      setExecutingCodeId(null);
    }
  };

  const generateCodeId = (messageId: string, codeContent: string) => {
    // Create a stable ID based on message ID and code content hash
    return `code-${messageId}-${codeContent.slice(0, 20).replace(/[^a-zA-Z0-9]/g, '')}`;
  };

  const formatChangePct = (value: any): string => {
    if (typeof value === 'number' && Number.isFinite(value)) {
      return `${value > 0 ? '+' : ''}${value.toFixed(1)}%`;
    }
    return 'N/A';
  };

  const downloadColumnStats = async () => {
    const datasetId = sessionStorage.getItem('dataset_id');
    if (!datasetId) {
      console.error('❌ No dataset ID found in session storage');
      return;
    }

    try {
      console.log('📊 Downloading Column Stats table...');
      await fastApiService.downloadColumnStats(datasetId);
    } catch (error) {
      console.error('❌ Download failed:', error);
      alert('Column Stats download failed: ' + (error instanceof Error ? error.message : 'Unknown error'));
    }
  };

  const handleCompareChanges = async () => {
    const datasetId = sessionStorage.getItem('dataset_id');
    if (!datasetId) {
      console.error('❌ No dataset ID found in session storage');
      return;
    }

    setIsLoadingComparison(true);
    try {
      console.log('🔍 Fetching comparison data...');
      const data = await fastApiService.compareColumnStats(datasetId);
      setComparisonData(data);
      setShowComparisonModal(true);
    } catch (error) {
      console.error('❌ Comparison failed:', error);
      alert('Comparison failed: ' + (error instanceof Error ? error.message : 'Unknown error'));
    } finally {
      setIsLoadingComparison(false);
    }
  };


  // Helper function to format numeric values in tables
  const formatTableCellValue = (value: any, columnName: string): string => {
    const colLower = columnName.toLowerCase();
    
    // Don't show '-' for IV and VIF columns
    if (value === null || value === undefined || value === '') {
      if (colLower.includes('vif') || colLower.includes('iv') || colLower.includes('information value') || colLower.includes('variance inflation')) {
        return '';
      }
      return '-';
    }
    
    // Format numeric values based on column type
    if (typeof value === 'number') {
      if (colLower.includes('vif')) {
        return value.toFixed(2);
      } else if (colLower.includes('iv') || colLower.includes('information value')) {
        return value.toFixed(4);
      } else if (colLower.includes('correlation') || colLower.includes('coefficient') || colLower.includes('cramér')) {
        return value.toFixed(4);
      } else if (colLower.includes('auc') || colLower.includes('precision') || colLower.includes('recall') ||
                 colLower.includes('f1') || colLower.includes('accuracy') || colLower.includes('logloss')) {
        return value.toFixed(3);
      } else if (colLower.includes('mean') || colLower.includes('std')) {
        return value.toFixed(3);
      } else {
        // Default: 2 decimals for other numeric values
        return value.toFixed(2);
      }
    }
    
    return String(value);
  };
  
  const sanitizeJsonForParsing = (value: string): string =>
    value
      .replace(/NaN/g, 'null')
      .replace(/-Infinity/g, 'null')
      .replace(/Infinity/g, 'null');

  const parseJsonIfPossible = (value: any): any => {
    if (typeof value !== 'string') return undefined;
    try {
      return JSON.parse(value);
    } catch {
      try {
        return JSON.parse(sanitizeJsonForParsing(value));
      } catch {
        return undefined;
      }
    }
  };

  const tryParseResponsePayload = (value: any) => {
    if (typeof value !== 'string') return value;
    const parsed = parseJsonIfPossible(value);
    return parsed !== undefined ? parsed : value;
  };

  const normalizePlanInsightPayload = (input: any) => {
    let plan = input;
    if (typeof plan === 'string') {
      const parsed = parseJsonIfPossible(plan);
      if (parsed) plan = parsed;
    }

    let current = plan;
    const seen = new Set<any>();
    while (current && typeof current === 'object' && !seen.has(current)) {
      seen.add(current);
      if (typeof current.response === 'string') {
        const parsed = parseJsonIfPossible(current.response);
        if (parsed) {
          current = parsed;
          continue;
        }
      }

      if (current.response && typeof current.response === 'object' && Object.keys(current).length === 1) {
        current = current.response;
        continue;
      }

      break;
    }

    const insightPayload = current;
    const tablesMap =
      insightPayload?.response && typeof insightPayload.response === 'object'
        ? insightPayload.response
        : insightPayload;
    const dataMeta = insightPayload?.data || {};
    return { insightPayload, tablesMap, dataMeta };
  };

  const getIvContextFromNormalizedPayload = (insightPayload: any, tablesMap: any, dataMeta: any) => {
    const ivInsightsFromMeta: string[] = Array.isArray(dataMeta?.iv_insight)
      ? dataMeta.iv_insight
      : Array.isArray(dataMeta?.llm_iv_insight)
        ? dataMeta.llm_iv_insight
        : [];
    const extraInsights =
      Array.isArray(insightPayload?.data?.iv_insight) ? insightPayload.data.iv_insight : [];
    const ivInsights = ivInsightsFromMeta.length > 0 ? ivInsightsFromMeta : extraInsights;

    const summaryArray =
      (Array.isArray(tablesMap?.iv_analysis_summary) && tablesMap.iv_analysis_summary.length > 0)
        ? tablesMap.iv_analysis_summary
        : (Array.isArray(insightPayload?.response?.iv_analysis_summary)
          ? insightPayload.response.iv_analysis_summary
          : []);
    const ivSummary = summaryArray.length > 0 ? summaryArray[0] : null;
    const ivSummaryColumns = Array.isArray(ivSummary?.columns) ? ivSummary.columns : [];
    const ivSummaryRows = Array.isArray(ivSummary?.rows) ? ivSummary.rows : [];

    console.log('📊 getIvContextFromNormalizedPayload', {
      payloadKeys: insightPayload && typeof insightPayload === 'object' ? Object.keys(insightPayload) : typeof insightPayload,
      ivInsightsCount: ivInsights.length,
      ivSummaryColumns
    });

    return { ivInsights, ivSummaryColumns, ivSummaryRows, ivSummary };
  };

  const handleAutoDataInsights = async () => {
    console.log(
      '🚀 Running Auto Data Insights (REST: bivariate, correlation, matrix, correlation ratio, IV, VIF; chat for narrative only)...'
    );
    const content = 'Generate comprehensive data insights and patterns from my dataset';
    const next = [
      'bivariate_analysis',
      'correlation_analysis',
      'iv_analysis',
      'variance_inflation_factor',
      'correlation_matrix',
      'correlation_ratio_analysis',
    ];
    setInsightsGenerationSource('auto');
    try {
      sessionStorage.setItem('model_builder_insights_source', 'auto');
      sessionStorage.setItem('model_builder_displayed_insight_steps', JSON.stringify(next));
    } catch {}
    setDisplayedInsightSteps(next);

    const datasetId = activeDatasetId;
    const target = datasetConfig?.target_variable?.trim();
    if (!datasetId || !target) {
      setAutoInsightStepStatus({
        bivariate_analysis: 'error',
        correlation_analysis: 'error',
        iv_analysis: 'error',
        variance_inflation_factor: 'error',
        correlation_matrix: 'error',
        correlation_ratio_analysis: 'error',
      });
      return;
    }

    const runningAll: Record<AutoInsightStepId, AutoInsightStepStatus> = {
      bivariate_analysis: 'running',
      correlation_analysis: 'running',
      iv_analysis: 'running',
      variance_inflation_factor: 'running',
      correlation_matrix: 'running',
      correlation_ratio_analysis: 'running',
    };
    setAutoInsightStepStatus(runningAll);

    const chatIvVif = handleSendChatMessage(3, content).catch((e) => {
      console.error('Auto Data Insights chat failed:', e);
    });

    // Run API prefetches and chat independently - each completes on its own
    runAutoInsightApiPrefetches(datasetId, target, (stepId, status) => {
      setAutoInsightStepStatus((prev) => {
        const merged = { ...prev, [stepId]: status };
        try {
          sessionStorage.setItem('model_builder_auto_insights_cached', 'true');
          sessionStorage.setItem('model_builder_auto_insights_status', JSON.stringify(merged));
        } catch {}
        return merged;
      });
    }).catch((e) => {
      console.error('Auto Data Insights API prefetches failed:', e);
    });

    chatIvVif
      .then(() => {
        // Cache chat messages after chat completes
        try {
          sessionStorage.setItem('model_builder_auto_insights_cached', 'true');
          const currentChatMessages = chatMessages[3];
          sessionStorage.setItem('model_builder_auto_chat_messages', JSON.stringify(currentChatMessages));
        } catch {}
      })
      .catch((e) => {
        console.error('Auto Data Insights chat failed:', e);
      });
  };

  /** Switching Auto ↔ Standard clears the other mode’s sidebar/chat state and re-runs the selected mode when applicable. */
  const handleInsightsUiModeChange = (mode: 'auto' | 'standard') => {
    if (mode === insightsUiMode) return;
    setInsightsUiMode(mode);

    if (mode === 'auto' && insightsGenerationSource === 'standard') {
      // Check if auto insights were previously generated
      try {
        const cachedAutoInsights = sessionStorage.getItem('model_builder_auto_insights_cached');
        if (cachedAutoInsights === 'true') {
          // Restore auto insights from cache instead of regenerating
          const cachedChatMessages = sessionStorage.getItem('model_builder_auto_chat_messages');
          const cachedStatus = sessionStorage.getItem('model_builder_auto_insights_status');
          
          setInsightsGenerationSource('auto');
          setDisplayedInsightSteps([
            'bivariate_analysis',
            'correlation_analysis',
            'iv_analysis',
            'variance_inflation_factor',
            'correlation_matrix',
            'correlation_ratio_analysis',
          ]);
          try {
            sessionStorage.setItem('model_builder_insights_source', 'auto');
            sessionStorage.setItem(
              'model_builder_displayed_insight_steps',
              JSON.stringify([
                'bivariate_analysis',
                'correlation_analysis',
                'iv_analysis',
                'variance_inflation_factor',
                'correlation_matrix',
                'correlation_ratio_analysis',
              ])
            );
          } catch {}
          
          // Restore chat messages
          if (cachedChatMessages) {
            try {
              setChatMessages((prev) => ({ ...prev, 3: JSON.parse(cachedChatMessages) }));
            } catch {}
          }
          
          // Restore auto insight step status from cache
          if (cachedStatus) {
            try {
              setAutoInsightStepStatus(JSON.parse(cachedStatus));
            } catch {}
          }
          return;
        }
      } catch {}
      // If no cache, regenerate
      resetStep3InsightPresentationForModeSwitch();
      void handleAutoDataInsights();
      return;
    }

    if (mode === 'standard' && insightsGenerationSource === 'auto') {
      // Check if standard insights were previously generated
      try {
        const cachedStandardInsights = sessionStorage.getItem('model_builder_standard_insights_cached');
        if (cachedStandardInsights === 'true' && lastStandardInsightSteps.length > 0) {
          // Restore standard insights from cache instead of regenerating
          const cachedChatMessages = sessionStorage.getItem('model_builder_standard_chat_messages');
          
          setInsightsGenerationSource('standard');
          setDisplayedInsightSteps(lastStandardInsightSteps);
          try {
            sessionStorage.setItem('model_builder_insights_source', 'standard');
            sessionStorage.setItem('model_builder_displayed_insight_steps', JSON.stringify(lastStandardInsightSteps));
          } catch {}
          
          // Restore chat messages
          if (cachedChatMessages) {
            try {
              setChatMessages((prev) => ({ ...prev, 3: JSON.parse(cachedChatMessages) }));
            } catch {}
          }
          return;
        }
      } catch {}
      // If no cache, regenerate
      resetStep3InsightPresentationForModeSwitch();
      setAutoInsightStepStatus({
        bivariate_analysis: 'idle',
        correlation_analysis: 'idle',
        iv_analysis: 'idle',
        variance_inflation_factor: 'idle',
        correlation_matrix: 'idle',
        correlation_ratio_analysis: 'idle',
      });
      if (lastStandardInsightSteps.length > 0) {
        void handleStandardDataInsights(lastStandardInsightSteps);
      }
    }
  };

  // Helper function to validate modelling response structure
  const validateModellingResponse = (data: any): boolean => {
    if (!data || typeof data !== 'object') return false;
    
    // Check for valid table structures
    const validKeys = [
      'vif_analysis', 'iv_analysis_summary', 'model_comparison', 
      'cv_summary', 'confusion_matrix_summary', 'used_features',
      'used_features_analysis', 'correlation_analysis', 'variable_screener', 'bivariate_analysis',
      'correlation_ratio'
    ];
    
    const hasValidKey = validKeys.some(key => data[key] !== undefined);
    return hasValidKey;
  };

  // Reusable chat component for each step

  const renderStepChat = (step: number) => {

    const messages = chatMessages[step] || [];

    const input = chatInputs[step] || '';

    const typing = isTyping[step] || false;



    return (

      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-6">

        <div className="flex items-center justify-between mb-4">

          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">AI Assistant</h3>

          <button
            type="button"
            onClick={() => {

              setIsAIAssistantExpanded(true);

              setExpandedStepNumber(step);

            }}

            className="flex items-center space-x-2 px-3 py-1 text-xs bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 dark:text-gray-300 rounded-md transition-colors"

            title="Expand Assistant"

          >

            <Maximize className="h-3 w-3" />

            <span>Expand</span>

          </button>

        </div>

        

        {/* Chat Messages */}

        <div 

          ref={(el) => chatContainerRefs.current[step] = el}

          className="h-64 overflow-y-auto mb-4 border border-gray-200 dark:border-gray-700 rounded-lg p-4 bg-gray-50 dark:bg-gray-800/50 scroll-smooth"

        >

          {messages.length === 0 ? (

            <div className="text-center text-gray-500 dark:text-gray-400 py-8">

              <Brain className="h-8 w-8 mx-auto mb-2 text-gray-400 dark:text-gray-500" />

              <p className="text-sm">Ask me anything about this step!</p>

            </div>

          ) : (

            <div className="space-y-3">

              {messages.map((message) => (

                <div

                  key={message.id}

                  className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}

                >

                  <div className={`px-3 py-2 rounded-lg w-3/4 ${

                    message.type === 'user' 

                      ? 'bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff]' 

                      : 'bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700'

                  }`}>

                    <div className="text-sm dark:text-gray-200">

                      {(() => {
                        try {
                          // Try to parse as JSON first (for API responses)
                          const parsed = JSON.parse(message.content);
                          
                          // ============================================================
                          // AUTO QC TREATMENT EXECUTION PROGRESS HANDLER
                          // Shows progress during auto-execution of each treatment
                          // ============================================================
                          if (parsed.isExecutingTreatment) {
                            const statusColors = {
                              executing: 'bg-blue-50 dark:bg-blue-900/30 border-blue-200 dark:border-blue-700',
                              success: 'bg-green-50 dark:bg-green-900/30 border-green-200 dark:border-green-700',
                              error: 'bg-red-50 dark:bg-red-900/30 border-red-200 dark:border-red-700'
                            };
                            const statusIcons = {
                              executing: (
                                <svg className="w-5 h-5 text-blue-500 animate-spin" fill="none" viewBox="0 0 24 24">
                                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                </svg>
                              ),
                              success: (
                                <svg className="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                </svg>
                              ),
                              error: (
                                <svg className="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                              )
                            };
                            const status = parsed.status as 'executing' | 'success' | 'error';
                            
                            return (
                              <div className={`rounded-lg border p-3 ${statusColors[status]}`}>
                                <div className="flex items-center space-x-3">
                                  <div className="flex-shrink-0">
                                    {statusIcons[status]}
                                  </div>
                                  <div className="flex-1 min-w-0">
                                    <div className="flex items-center justify-between">
                                      <p className={`text-sm font-medium ${status === 'executing' ? 'text-blue-800 dark:text-blue-300' : status === 'success' ? 'text-green-800 dark:text-green-300' : 'text-red-800 dark:text-red-300'}`}>
                                        {status === 'executing' ? `Executing ${parsed.treatmentLabel}...` : 
                                         status === 'success' ? `${parsed.treatmentLabel} Applied` :
                                         `${parsed.treatmentLabel} Failed`}
                                      </p>
                                      <span className="text-xs text-gray-500 dark:text-gray-400">
                                        {parsed.progress}
                                      </span>
                                    </div>
                                    {parsed.response && status === 'success' && (
                                      <p className="mt-1 text-xs text-green-600 dark:text-green-400 truncate">
                                        {parsed.response}
                                      </p>
                                    )}
                                    {parsed.error && status === 'error' && (
                                      <p className="mt-1 text-xs text-red-600 dark:text-red-400 truncate">
                                        {parsed.error}
                                      </p>
                                    )}
                                  </div>
                                </div>
                              </div>
                            );
                          }

                          // ============================================================
                          // AUTO QC COMPLETION MESSAGE HANDLER
                          // Shows success message when all treatments are auto-executed
                          // ============================================================
                          if (parsed.isAutoQCComplete) {
                            const isSuccess = parsed.executedCount > 0;
                            return (
                              <div className="space-y-3">
                                <div className={`${isSuccess ? 'bg-green-50 dark:bg-green-900/30 border-green-200 dark:border-green-700' : 'bg-yellow-50 dark:bg-yellow-900/30 border-yellow-200 dark:border-yellow-700'} border rounded-lg p-4`}>
                                  <div className="flex items-start space-x-3">
                                    <div className="flex-shrink-0">
                                      {isSuccess ? (
                                        <svg className="w-6 h-6 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                        </svg>
                                      ) : (
                                        <svg className="w-6 h-6 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                        </svg>
                                      )}
                                    </div>
                                    <div className="flex-1">
                                      <h3 className={`text-sm font-semibold ${isSuccess ? 'text-green-800 dark:text-green-300' : 'text-yellow-800 dark:text-yellow-300'}`}>
                                        {isSuccess ? 'All Treatments Applied Successfully!' : 'No Treatments Executed'}
                                      </h3>
                                      {isSuccess ? (
                                        <>
                                          <p className="mt-1 text-sm text-green-700 dark:text-green-400">
                                            <strong>{parsed.executedCount}</strong> out of <strong>{parsed.totalTreatments}</strong> treatment{parsed.totalTreatments > 1 ? 's' : ''} executed successfully.
                                          </p>
                                          {parsed.summary && Array.isArray(parsed.summary) && (
                                            <div className="mt-2 text-xs text-green-600 dark:text-green-400 space-y-0.5">
                                              {parsed.summary.map((item: string, idx: number) => (
                                                <div key={idx}>{item}</div>
                                              ))}
                                            </div>
                                          )}
                                        </>
                                      ) : (
                                        <p className="mt-1 text-sm text-yellow-700 dark:text-yellow-400">
                                          All treatments were skipped. Please upload templates for Invalid Values and Special Values to apply those treatments.
                                        </p>
                                      )}
                                      {isSuccess && (
                                        <div className="mt-3 flex items-center space-x-2">
                                          <button
                                            onClick={() => {
                                              setShowDatasetOverview(true);
                                              setShowEDAComparison(true);
                                              triggerEdaComparisonView(); // Open Updated EDA sub-tab
                                            }}
                                            className="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-md bg-green-100 dark:bg-green-800 text-green-800 dark:text-green-200 hover:bg-green-200 dark:hover:bg-green-700 transition-colors"
                                          >
                                            <svg className="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                                            </svg>
                                            View Updated EDA
                                          </button>
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              </div>
                            );
                          }

                          // ============================================================
                          // DATA QUALITY TREATMENT TABLE HANDLER
                          // Renders structured tables for Invalid Values, Special Values,
                          // Outliers, and Missing Values treatments
                          // ============================================================
                          if (parsed.treatment_type && ['invalid_values', 'special_values', 'outliers', 'missing_values'].includes(parsed.treatment_type)) {
                            console.log('📊 Detected treatment_type response:', parsed.treatment_type);
                            return (
                              <div className="space-y-4">
                                {/* Response text - only show when NOT skipped (skipped treatments show yellow warning in DataQualityTreatmentTable) */}
                                {parsed.response && !parsed.skipped && (
                                  <div className="text-sm text-gray-700 dark:text-gray-300 bg-blue-50 dark:bg-blue-900/20 p-3 rounded-lg border border-blue-200 dark:border-blue-700">
                                    <ReactMarkdown>{parsed.response}</ReactMarkdown>
                                  </div>
                                )}
                                
                                {/* Treatment Table */}
                                <DataQualityTreatmentTable
                                  treatmentType={parsed.treatment_type}
                                  qcMode={parsed.qc_mode || 'manual'}
                                  tableData={parsed.table_data}
                                  skipped={parsed.skipped}
                                  skipReason={parsed.response}
                                  code={parsed.code}
                                  specialMessages={parsed.special_messages}
                                  onApplyTreatment={(latestCode) => {
                                    // Execute the generated code when Apply is clicked
                                    const sourceCode = latestCode || parsed.code;
                                    if (sourceCode && sourceCode.trim() !== '# No code to display') {
                                      // For missing_values in manual mode, append missing_flag code if user selected it
                                      let codeToExecute = sourceCode;
                                      if (parsed.treatment_type === 'missing_values' && addMissingFlag) {
                                        codeToExecute = sourceCode + "\n\n# Add missing_flag column (1 if any value in row is missing, 0 otherwise)\ndf['missing_flag'] = df.isna().any(axis=1).astype(int)";
                                      }
                                      
                                      // Use step-by-step handler if in Manual QC step-by-step mode
                                      if (qcStepByStepMode && (parsed.qc_mode || 'manual') === 'manual') {
                                        handleQCApplyTreatment(parsed.treatment_type, codeToExecute);
                                      } else {
                                        executeCode(generateCodeId(message.id, sourceCode), codeToExecute);
                                      }
                                    }
                                  }}
                                  onSkipTreatment={() => {
                                    // Use step-by-step handler if in Manual QC step-by-step mode
                                    if (qcStepByStepMode && (parsed.qc_mode || 'manual') === 'manual') {
                                      handleQCSkipTreatment(parsed.treatment_type);
                                    } else {
                                      console.log(`Skipped ${parsed.treatment_type} treatment`);
                                    }
                                  }}
                                  onRegenerateCode={({ treatmentType, selections }) =>
                                    handleQCRegenerateCode(treatmentType, selections)
                                  }
                                  isApplying={executingCodeId === generateCodeId(message.id, parsed.code) || qcIsApplyingTreatment}
                                  showMissingFlagOption={parsed.show_missing_flag_option}
                                  addMissingFlag={addMissingFlag}
                                  onMissingFlagChange={setAddMissingFlag}
                                  treatmentStatus={qcTreatmentStatuses[parsed.treatment_type]}
                                  stepInfo={qcStepByStepMode && qcTreatmentStatuses[parsed.treatment_type] === 'active' ? {
                                    currentStep: qcCurrentStepIndex + 1,
                                    totalSteps: qcTreatmentSequence.length
                                  } : undefined}
                                  onViewUpdatedEDA={() => {
                                    setShowDatasetOverview(true);
                                    setShowEDAComparison(true);
                                    triggerEdaComparisonView();
                                  }}
                                />
                                
                                {/* Suggestions */}
                                {parsed.suggestion && Array.isArray(parsed.suggestion) && parsed.suggestion.length > 0 && (
                                  <div className="mt-3">
                                    <div className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">💡 Suggestions:</div>
                                    <ul className="list-disc list-inside text-xs text-gray-500 dark:text-gray-400 space-y-0.5">
                                      {parsed.suggestion.map((s: string, i: number) => (
                                        <li key={i}>{s}</li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                              </div>
                            );
                          }

                          // ============================================================
                          // DATA QUALITY COMBINED RESPONSE HANDLER
                          // Handles the new response format with multiple treatment_messages
                          // The response field contains a JSON string that needs to be parsed
                          // ============================================================
                          
                          // Try to detect data_quality response - could be direct or nested in response field
                          let dataQualityData: any = null;
                          if (parsed.role === 'data_quality' && parsed.treatment_messages) {
                            dataQualityData = parsed;
                          } else if (parsed.response && typeof parsed.response === 'string') {
                            try {
                              const nestedParsed = JSON.parse(parsed.response);
                              if (nestedParsed.role === 'data_quality' && nestedParsed.treatment_messages) {
                                dataQualityData = nestedParsed;
                              }
                            } catch (e) {
                              // Not a nested JSON, continue
                            }
                          }
                          
                          if (dataQualityData && dataQualityData.treatment_messages && Array.isArray(dataQualityData.treatment_messages)) {
                            console.log('📊 Detected data_quality response with treatment_messages:', dataQualityData.treatment_messages.length);
                            return (
                              <div className="space-y-6">
                                {/* Render each treatment message as a separate table */}
                                {dataQualityData.treatment_messages.map((treatmentMsg: any, idx: number) => (
                                  <div key={idx} className="border-b border-gray-200 dark:border-gray-700 pb-4 last:border-b-0">
                                    {/* Response text for this treatment - only show if NOT skipped (skipped shows yellow warning instead) */}
                                    {treatmentMsg.response && !treatmentMsg.skipped && (
                                      <div className="text-sm text-gray-700 dark:text-gray-300 bg-blue-50 dark:bg-blue-900/20 p-3 rounded-lg border border-blue-200 dark:border-blue-700 mb-3">
                                        <ReactMarkdown>{treatmentMsg.response}</ReactMarkdown>
                                      </div>
                                    )}
                                    
                                    {/* Treatment Table */}
                                    <DataQualityTreatmentTable
                                      treatmentType={treatmentMsg.treatment_type}
                                      qcMode={treatmentMsg.qc_mode || dataQualityData.qc_mode || 'manual'}
                                      tableData={treatmentMsg.table_data}
                                      skipped={treatmentMsg.skipped}
                                      skipReason={treatmentMsg.response}
                                      code={treatmentMsg.code}
                                      specialMessages={treatmentMsg.special_messages}
                                      onApplyTreatment={(latestCode) => {
                                        const sourceCode = latestCode || treatmentMsg.code;
                                        if (sourceCode && sourceCode.trim() !== '# No code to display') {
                                          // For missing_values in manual mode, append missing_flag code if user selected it
                                          let codeToExecute = sourceCode;
                                          if (treatmentMsg.treatment_type === 'missing_values' && addMissingFlag) {
                                            codeToExecute = sourceCode + "\n\n# Add missing_flag column (1 if any value in row is missing, 0 otherwise)\ndf['missing_flag'] = df.isna().any(axis=1).astype(int)";
                                          }
                                          
                                          // Use step-by-step handler if in Manual QC step-by-step mode
                                          const effectiveQcMode = treatmentMsg.qc_mode || dataQualityData.qc_mode || 'manual';
                                          if (qcStepByStepMode && effectiveQcMode === 'manual') {
                                            handleQCApplyTreatment(treatmentMsg.treatment_type, codeToExecute);
                                          } else {
                                            executeCode(generateCodeId(message.id + '_' + idx, sourceCode), codeToExecute);
                                          }
                                        }
                                      }}
                                      onSkipTreatment={() => {
                                        // Use step-by-step handler if in Manual QC step-by-step mode
                                        const effectiveQcMode = treatmentMsg.qc_mode || dataQualityData.qc_mode || 'manual';
                                        if (qcStepByStepMode && effectiveQcMode === 'manual') {
                                          handleQCSkipTreatment(treatmentMsg.treatment_type);
                                        } else {
                                          console.log(`Skipped ${treatmentMsg.treatment_type} treatment`);
                                        }
                                      }}
                                      onRegenerateCode={({ treatmentType, selections }) =>
                                        handleQCRegenerateCode(treatmentType, selections)
                                      }
                                      isApplying={executingCodeId === generateCodeId(message.id + '_' + idx, treatmentMsg.code) || qcIsApplyingTreatment}
                                      showMissingFlagOption={treatmentMsg.show_missing_flag_option}
                                      addMissingFlag={addMissingFlag}
                                      onMissingFlagChange={setAddMissingFlag}
                                      treatmentStatus={qcTreatmentStatuses[treatmentMsg.treatment_type]}
                                      stepInfo={qcStepByStepMode && qcTreatmentStatuses[treatmentMsg.treatment_type] === 'active' ? {
                                        currentStep: qcCurrentStepIndex + 1,
                                        totalSteps: qcTreatmentSequence.length
                                      } : undefined}
                                      onViewUpdatedEDA={() => {
                                        setShowDatasetOverview(true);
                                        setShowEDAComparison(true);
                                        triggerEdaComparisonView();
                                      }}
                                    />
                                  </div>
                                ))}
                                
                                {/* Summary section if available */}
                                {dataQualityData.summary && (
                                  <div className="mt-4 p-4 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-700">
                                    <h4 className="font-semibold text-green-800 dark:text-green-300 mb-2">Data Quality Treatment Summary</h4>
                                    {dataQualityData.summary.response && (
                                      <div className="text-sm text-gray-700 dark:text-gray-300">
                                        <ReactMarkdown>{dataQualityData.summary.response}</ReactMarkdown>
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>
                            );
                          }
                          
                          // Check if this is a planner response with role
                          console.log('🔍 Checking message for planner role:', parsed);
                          if (
                            parsed.role === "plan_agent" ||
                            parsed.role === "data_insight" ||
                            message.content.includes('"role":"plan_agent"') ||
                            message.content.includes('\"role\":\"plan_agent\"') ||
                            message.content.includes('"role": "plan_agent"') ||
                            message.content.includes('"role":"data_insight"') ||
                            message.content.includes('\"role\":\"data_insight\"') ||
                            message.content.includes('"role": "data_insight"')
                          ) {
                            console.log('✅ Detected planner response');
                            // Parse the actual response content which might be nested JSON
                            let planData: any = parsed;
                            try {
                              if (parsed.response) {
                                planData = tryParseResponsePayload(parsed.response);
                              } else if (parsed.plan) {
                                planData = tryParseResponsePayload(parsed.plan);
                              } else {
                                const { role, code, suggestions, ...restData } = parsed;
                                planData = Object.keys(restData).length > 0 ? restData : parsed;
                              }
                            } catch {
                              planData = parsed;
                            }

                            const normalizedPlanData = tryParseResponsePayload(planData);
                            planData = normalizedPlanData;
                            console.log('📊 Plan/Insight data extracted:', {
                              role: parsed.role,
                              type: typeof planData,
                              keys: planData && typeof planData === 'object' ? Object.keys(planData) : [],
                              sample: planData
                            });

                            // Render Data Insights tables when available
                            if (parsed.role === 'data_insight' && planData && typeof planData === 'object') {
                              const { insightPayload, tablesMap, dataMeta } = normalizePlanInsightPayload(planData);
                              const ivContext = getIvContextFromNormalizedPayload(insightPayload, tablesMap, dataMeta);
                              console.log('📍 Data insight IV context:', {
                                step,
                                ivInsightsCount: ivContext.ivInsights.length,
                                ivSummaryColumns: ivContext.ivSummaryColumns
                              });

                              // Optional top 3 insights (LLM-ranked) can come from either parsed.data or nested dataMeta
                              const topInsights = (parsed?.data && (parsed.data as any).top_insights) || dataMeta?.top_insights || null;
                              const llmBivar: string[] = Array.isArray(dataMeta?.bivariate_insight)
                                ? dataMeta.bivariate_insight
                                : (Array.isArray(dataMeta?.llm_bivariate_insight) ? dataMeta.llm_bivariate_insight : []);
                              const llmCorr: string[] = Array.isArray(dataMeta?.correlation_insight)
                                ? dataMeta.correlation_insight
                                : (Array.isArray(dataMeta?.llm_correlation_insight) ? dataMeta.llm_correlation_insight : []);
                              const llmVif: string[] = Array.isArray(dataMeta?.vif_insight)
                                ? dataMeta.vif_insight
                                : (Array.isArray(dataMeta?.llm_vif_insight) ? dataMeta.llm_vif_insight : []);
                              const llmIv = ivContext.ivInsights;
                              const llmCorrMatrix: string[] = Array.isArray(dataMeta?.correlation_matrix_insight)
                                ? dataMeta.correlation_matrix_insight.map((item: any) =>
                                    typeof item === 'string' ? item :
                                      typeof item === 'object' && item.pattern ? item.pattern : JSON.stringify(item)
                                  )
                                : (Array.isArray(dataMeta?.llm_correlation_matrix_insight)
                                  ? dataMeta.llm_correlation_matrix_insight.map((item: any) =>
                                      typeof item === 'string' ? item :
                                        typeof item === 'object' && item.pattern ? item.pattern : JSON.stringify(item)
                                    )
                                  : []);
                              const llmCorrRatio: string[] = Array.isArray(dataMeta?.correlation_ratio_insight)
                                ? dataMeta.correlation_ratio_insight
                                : Array.isArray(dataMeta?.llm_correlation_ratio_insight)
                                  ? dataMeta.llm_correlation_ratio_insight
                                  : [];
                              const ivSummaryTable = Array.isArray(tablesMap?.iv_analysis_summary)
                                ? tablesMap.iv_analysis_summary[0]
                                : null;
                              const corrHighTable = Array.isArray(tablesMap?.correlation_matrix_high)
                                ? tablesMap.correlation_matrix_high[0]
                                : null;
                              const corrSummaryTable = Array.isArray(tablesMap?.correlation_matrix_summary)
                                ? tablesMap.correlation_matrix_summary[0]
                                : null;

                              // Show insights and tables
                              if (
                                llmBivar.length > 0 ||
                                llmCorr.length > 0 ||
                                llmVif.length > 0 ||
                                llmIv.length > 0 ||
                                llmCorrMatrix.length > 0 ||
                                llmCorrRatio.length > 0 ||
                                topInsights ||
                                tablesMap
                              ) {
                                return (
                                  <div className="space-y-6">
                                    <div className="flex items-center justify-between">
                                      <div className="text-sm font-medium text-blue-700 dark:text-blue-400">📊 Data Insights</div>
                                      <div className="flex items-center gap-2">
                                        <button
                                          onClick={() => downloadInsightsAsXLSX(insightPayload, step)}
                                          className="flex items-center space-x-1 px-2 py-1 text-xs bg-green-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded hover:bg-green-700 dark:hover:bg-[#333380] transition-colors"
                                          title="Download Full Insight Report"
                                        >
                                          <Download className="h-3 w-3" />
                                          <span>Download Full Insight Report</span>
                                        </button>
                                          {(llmIv.length > 0 || ivSummaryTable) && (
                                            <button
                                              onClick={() => downloadDetailedIvReport(insightPayload, step)}
                                              className="flex items-center space-x-1 px-2 py-1 text-xs bg-purple-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded hover:bg-purple-700 dark:hover:bg-[#333380] transition-colors"
                                              title="Download Detailed IV Report"
                                        >
                                          <Download className="h-3 w-3" />
                                          <span>Download Detailed IV Report</span>
                                        </button>
                                      )}
                                      </div>
                                    </div>
                                    
                                    
                                    {/* Top 3 variables intentionally hidden as requested */}
                                    {llmBivar.length > 0 && (
                                      <div className="space-y-2">
                                        <div className="text-xs font-semibold text-gray-800 dark:text-gray-200">Bivariate Insights</div>
                                        <ul className="list-disc list-inside text-xs text-gray-700 dark:text-gray-300">
                                          {llmBivar.map((ins, i) => (<li key={i}>{ins}</li>))}
                                        </ul>
                                      </div>
                                    )}
                                    {llmCorr.length > 0 && (
                                      <div className="space-y-2">
                                        <div className="text-xs font-semibold text-gray-800 dark:text-gray-200">Correlation Insights</div>
                                        <ul className="list-disc list-inside text-xs text-gray-700 dark:text-gray-300">
                                          {llmCorr.map((ins, i) => (<li key={i}>{ins}</li>))}
                                        </ul>
                                      </div>
                                    )}
                                    {llmVif.length > 0 && (
                                      <div className="space-y-2">
                                        <div className="text-xs font-semibold text-gray-800 dark:text-gray-200">VIF Insights</div>
                                        <ul className="list-disc list-inside text-xs text-gray-700 dark:text-gray-300">
                                          {llmVif.map((ins, i) => (<li key={i}>{ins}</li>))}
                                        </ul>
                                      </div>
                                    )}
                                    {llmIv.length > 0 && (
                                      <div className="space-y-2">
                                        <div className="text-xs font-semibold text-gray-800 dark:text-gray-200">IV Insights</div>
                                        <ul className="list-disc list-inside text-xs text-gray-700 dark:text-gray-300">
                                          {llmIv.map((ins, i) => (<li key={i}>{ins}</li>))}
                                        </ul>
                                      </div>
                                    )}
                                    {llmCorrMatrix.length > 0 && (
                                      <div className="space-y-2">
                                        <div className="text-xs font-semibold text-gray-800 dark:text-gray-200">Correlation Matrix Insights</div>
                                        <ul className="list-disc list-inside text-xs text-gray-700 dark:text-gray-300">
                                          {llmCorrMatrix.map((ins, i) => (<li key={i}>{ins}</li>))}
                                        </ul>
                                      </div>
                                    )}
                                    {llmCorrRatio.length > 0 && (
                                      <div className="space-y-2">
                                        <div className="text-xs font-semibold text-gray-800 dark:text-gray-200">
                                          Correlation ratio (η) Insights
                                        </div>
                                        <ul className="list-disc list-inside text-xs text-gray-700 dark:text-gray-300">
                                          {llmCorrRatio.map((ins, i) => (
                                            <li key={i}>{ins}</li>
                                          ))}
                                        </ul>
                                      </div>
                                    )}
                                    {/* {ivSummaryTable && (
                                      <div className="space-y-2">
                                        <div className="text-xs font-semibold text-gray-800 dark:text-gray-200">IV Analysis Summary</div>
                                        <div className="overflow-x-auto border border-gray-200 rounded-b-lg">
                                          {ivSummaryTable.rows && ivSummaryTable.rows.length > 0 ? (
                                            <table className="min-w-full text-xs">
                                              <thead className="bg-gray-50">
                                                <tr>
                                                  {ivSummaryTable.columns?.map((col: string, idx: number) => (
                                                    <th key={idx} className="px-3 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">{col}</th>
                                                  ))}
                                                </tr>
                                              </thead>
                                              <tbody>
                                                {ivSummaryTable.rows.map((row: any, rowIdx: number) => (
                                                  <tr key={rowIdx} className={rowIdx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                                                    {ivSummaryTable.columns?.map((col: string, colIdx: number) => (
                                                      <td key={colIdx} className="px-3 py-2 border-b border-gray-200 text-gray-700">
                                                        {formatTableCellValue(row[col], col)}
                                                      </td>
                                                    ))}
                                                  </tr>
                                                ))}
                                              </tbody>
                                            </table>
                                          ) : (
                                            <div className="px-4 py-3 text-xs text-gray-500">No IV summary rows available.</div>
                                          )}
                                        </div>
                                      </div>
                                    )} */}
                                    {/* {corrHighTable && (
                                      <div className="space-y-2">
                                        <div className="text-xs font-semibold text-gray-800 dark:text-gray-200">High Correlations</div>
                                        <div className="overflow-x-auto border border-gray-200 rounded-b-lg">
                                          {corrHighTable.rows && corrHighTable.rows.length > 0 ? (
                                            <table className="min-w-full text-xs">
                                              <thead className="bg-gray-50">
                                                <tr>
                                                  {corrHighTable.columns?.map((col: string, idx: number) => (
                                                    <th key={idx} className="px-3 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">{col}</th>
                                                  ))}
                                                </tr>
                                              </thead>
                                              <tbody>
                                                {corrHighTable.rows.map((row: any, rowIdx: number) => (
                                                  <tr key={rowIdx} className={rowIdx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                                                    {corrHighTable.columns?.map((col: string, colIdx: number) => (
                                                      <td key={colIdx} className="px-3 py-2 border-b border-gray-200 text-gray-700">
                                                        {formatTableCellValue(row[col], col)}
                                                      </td>
                                                    ))}
                                                  </tr>
                                                ))}
                                              </tbody>
                                            </table>
                                          ) : (
                                            <div className="px-4 py-3 text-xs text-gray-500">No high correlation rows available.</div>
                                          )}
                                        </div>
                                      </div>
                                    )} */}
                                    {/* {corrSummaryTable && (
                                      <div className="space-y-2">
                                        <div className="text-xs font-semibold text-gray-800 dark:text-gray-200">Correlation Matrix Summary</div>
                                        <div className="overflow-x-auto border border-gray-200 rounded-b-lg">
                                          {corrSummaryTable.rows && corrSummaryTable.rows.length > 0 ? (
                                            <table className="min-w-full text-xs">
                                              <thead className="bg-gray-50">
                                                <tr>
                                                  {corrSummaryTable.columns?.map((col: string, idx: number) => (
                                                    <th key={idx} className="px-3 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">{col}</th>
                                                  ))}
                                                </tr>
                                              </thead>
                                              <tbody>
                                                {corrSummaryTable.rows.map((row: any, rowIdx: number) => (
                                                  <tr key={rowIdx} className={rowIdx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                                                    {corrSummaryTable.columns?.map((col: string, colIdx: number) => (
                                                      <td key={colIdx} className="px-3 py-2 border-b border-gray-200 text-gray-700">
                                                        {formatTableCellValue(row[col], col)}
                                                      </td>
                                                    ))}
                                                  </tr>
                                                ))}
                                              </tbody>
                                            </table>
                                          ) : (
                                            <div className="px-4 py-3 text-xs text-gray-500">No correlation summary rows available.</div>
                                          )}
                                        </div>
                                      </div>
                                    )} */}
                                    {/* IV Insights duplicate removed */}
                                    {/* IV Analysis tables hidden per requirements (show insights only) */}
                                  </div>
                                );
                              }
                            }

                            // Default: render Analysis Plan (plan_agent)
                            return (
                              <div className="space-y-3">
                                <div className="flex items-center justify-between mb-2">
                                  <div className="text-sm font-medium text-blue-700 dark:text-blue-400">📋 Analysis Plan</div>
                                  <button
                                    onClick={() => downloadPlanAsCSV(planData, step)}
                                    className="flex items-center space-x-1 px-2 py-1 text-xs bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded hover:bg-blue-700 dark:hover:bg-[#333380] transition-colors"
                                    title="Download plan as CSV"
                                  >
                                    <Download className="h-3 w-3" />
                                    <span>Download CSV</span>
                                  </button>
                                </div>
                                <div className="flex justify-end mb-4">
                                  <button
                                    onClick={handleSaveAllTreatments}
                                    disabled={isUpdatingTreatment || Object.keys(customTreatments).length === 0}
                                    className="px-4 py-2 bg-green-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-green-700 dark:hover:bg-[#333380] disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center space-x-2"
                                  >
                                    {isUpdatingTreatment ? (
                                      <>
                                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                                        <span>Saving All Updates...</span>
                                      </>
                                    ) : (
                                      <>
                                        <span>Save All Updates</span>
                                      </>
                                    )}
                                  </button>
                                </div>
                                <div className="overflow-x-auto">
                                  <table className="min-w-full text-xs border border-gray-200 dark:border-gray-700 rounded">
                                    <thead className="bg-gray-50 dark:bg-gray-700">
                                      <tr>
                                        <th className="px-2 py-1 text-left border border-gray-200 dark:border-gray-700 font-medium text-gray-700 dark:text-gray-300">Issue</th>
                                        <th className="px-2 py-1 text-left border border-gray-200 dark:border-gray-700 font-medium text-gray-700 dark:text-gray-300">Variable</th>
                                        <th className="px-2 py-1 text-left border border-gray-200 dark:border-gray-700 font-medium text-gray-700 dark:text-gray-300">Observation</th>
                                        <th className="px-2 py-1 text-left border border-gray-200 dark:border-gray-700 font-medium text-gray-700 dark:text-gray-300">Treatment</th>
                                        <th className="px-2 py-1 text-left border border-gray-200 dark:border-gray-700 font-medium text-gray-700 dark:text-gray-300">Custom Treatment</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {planData && typeof planData === 'object' ? Object.entries(planData)
                                        .map(([category, items]) => {
                                          if (Array.isArray(items)) {
                                            const validItems = items.filter(item => {
                                              const detection = item.detection || item.strategy || item.approach || item.method || '';
                                              const treatment = item.treatment || item.solution || item.recommendation || item.action || '';
                                              return detection && treatment && detection.trim() !== '' && treatment.trim() !== '';
                                            });
                                            if (validItems.length === 0) return null;
                                            return validItems.map((item, index) => {
                                              const name = item.variable || item.field || item.column || '';
                                              const detection = item.detection || item.strategy || item.approach || item.method || '';
                                              const treatment = item.treatment || item.solution || item.recommendation || item.action || '';
                                              return (
                                                <tr key={`${category}-${index}`} className={index % 2 === 0 ? 'bg-white dark:bg-gray-800' : 'bg-gray-50 dark:bg-gray-800/50'}>
                                                  {index === 0 ? (
                                                    <td rowSpan={validItems.length} className="px-2 py-1 border border-gray-200 dark:border-gray-700 font-medium text-gray-700 dark:text-gray-300 align-top">
                                                      {category.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                                                    </td>
                                                  ) : null}
                                                  <td className="px-2 py-1 border border-gray-200 dark:border-gray-700">
                                                    <span className="text-gray-800 dark:text-gray-200 font-medium">{name || 'N/A'}</span>
                                                  </td>
                                                  <td className="px-2 py-1 border border-gray-200 dark:border-gray-700"><span className="text-gray-600 dark:text-gray-400">{detection || 'Not specified'}</span></td>
                                                  <td className="px-2 py-1 border border-gray-200 dark:border-gray-700"><span className="text-gray-600 dark:text-gray-400">{treatment || 'Not specified'}</span></td>
                                                  <td className="px-2 py-1 border border-gray-200 dark:border-gray-700">
                                                    <textarea
                                                      value={customTreatments[`${category}-${index}`] || item.custom_treatment || ''}
                                                      onChange={(e) => handleCustomTreatmentChange(`${category}-${index}`, e.target.value)}
                                                      className="w-full px-2 py-1 text-xs border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none"
                                                      rows={2}
                                                      placeholder={`Original: ${treatment || 'Not specified'}\nEnter custom treatment...`}
                                                    />
                                                  </td>
                                                </tr>
                                              );
                                            });
                                          } else {
                                            const detection = (items as any)?.detection || (items as any)?.strategy || (items as any)?.approach || '';
                                            const treatment = (items as any)?.treatment || (items as any)?.solution || (items as any)?.recommendation || '';
                                            if (!detection || !treatment || detection.trim() === '' || treatment.trim() === '') {
                                              return null;
                                            }
                                            return (
                                              <tr key={category} className="bg-white dark:bg-gray-800">
                                                <td className="px-2 py-1 border border-gray-200 dark:border-gray-700 font-medium text-gray-700 dark:text-gray-300">{category.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</td>
                                                <td className="px-2 py-1 border border-gray-200 dark:border-gray-700"><span className="text-gray-800 dark:text-gray-200 font-medium">N/A</span></td>
                                                <td className="px-2 py-1 border border-gray-200 dark:border-gray-700"><span className="text-gray-600 dark:text-gray-400">{detection || 'Not specified'}</span></td>
                                                <td className="px-2 py-1 border border-gray-200 dark:border-gray-700"><span className="text-gray-600 dark:text-gray-400">{treatment || 'Not specified'}</span></td>
                                                <td className="px-2 py-1 border border-gray-200 dark:border-gray-700">
                                                  <textarea
                                                    value={customTreatments[category] || (items as any)?.custom_treatment || ''}
                                                    onChange={(e) => handleCustomTreatmentChange(category, e.target.value)}
                                                    className="w-full px-2 py-1 text-xs border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none"
                                                    rows={2}
                                                    placeholder={`Original: ${treatment || 'Not specified'}\nEnter custom treatment...`}
                                                  />
                                                </td>
                                              </tr>
                                            );
                                          }
                                        })
                                        .filter(item => item !== null)
                                        .flat() : (
                                        <tr>
                                          <td colSpan={5} className="px-2 py-1 border border-gray-200 dark:border-gray-700 text-center text-gray-500 dark:text-gray-400">No plan data available</td>
                                        </tr>
                                      )}
                                    </tbody>
                                  </table>
                                </div>
                                {/* Knowledge Disclaimer for Analysis Plan - between table and QC task buttons */}
                                {step === 2 && (() => {
                                  const knowledgeMetadata = getKnowledgeMetadata(message, parsed);
                                  if (!knowledgeMetadata) return null;
                                  return (
                                    <KnowledgeDisclaimer
                                      sourceFiles={knowledgeMetadata.source_files || []}
                                      useExlExpertise={knowledgeMetadata.use_exl_expertise !== false}
                                    />
                                  );
                                })()}

                                {/* Individual QC Task Execution Buttons */}
                                {step === 2 && lastExecutedQCTasks.length > 0 && (
                                  <div className="mt-6 border-t dark:border-gray-700 pt-4">
                                    <div className="text-sm font-medium text-purple-700 dark:text-purple-400 mb-3">🎯 Execute Individual QC Tasks</div>
                                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                                      {lastExecutedQCTasks.map((taskId) => {
                                        const actionMessage = getQCActionMessageFromTaskId(taskId);
                                        
                                        // Get task display name
                                        let taskDisplayName = '';
                                        let taskDescription = '';
                                        
                                        switch (taskId) {
                                          case 'missing_values':
                                            taskDisplayName = 'Missing Values';
                                            taskDescription = 'Identify and handle missing data points';
                                            break;
                                          case 'outliers':
                                            taskDisplayName = 'Outliers';
                                            taskDescription = 'Detect and treat outlier values';
                                            break;
                                          case 'duplicates':
                                            taskDisplayName = 'Duplicates';
                                            taskDescription = 'Find and remove duplicate records';
                                            break;
                                          case 'data_types':
                                            taskDisplayName = 'Data Types';
                                            taskDescription = 'Validate and correct data types';
                                            break;
                                          case 'distribution':
                                            taskDisplayName = 'Distribution';
                                            taskDescription = 'Analyze data distributions';
                                            break;
                                          case 'correlation':
                                            taskDisplayName = 'Correlation';
                                            taskDescription = 'Analyze variable correlations';
                                            break;
                                          default:
                                            taskDisplayName = taskId;
                                            taskDescription = `Custom QC task: ${taskId}`;
                                            break;
                                        }
                                        
                                        const isExecuted = executedIndividualQCTasks.includes(taskId);
                                        
                                        return (
                                          <button
                                            key={taskId}
                                            onClick={() => handleIndividualQCTaskByTaskId(taskId)}
                                            disabled={isExecuted}
                                            className={`p-3 border rounded-lg transition-colors text-left ${
                                              isExecuted 
                                                ? 'bg-gray-100 dark:bg-gray-800 border-gray-300 dark:border-gray-600 cursor-not-allowed opacity-60' 
                                                : 'bg-purple-50 dark:bg-gray-800 border-purple-200 dark:border-purple-700 hover:bg-purple-100 dark:hover:bg-gray-700'
                                            }`}
                                          >
                                            <div className={`text-sm font-medium mb-1 ${
                                              isExecuted ? 'text-gray-500 dark:text-gray-400' : 'text-purple-700 dark:text-purple-400'
                                            }`}>
                                              {taskDisplayName} {isExecuted && '✓'}
                                            </div>
                                            <div className={`text-xs overflow-hidden ${
                                              isExecuted ? 'text-gray-400 dark:text-gray-500' : 'text-purple-600 dark:text-purple-300'
                                            }`} style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
                                              {isExecuted ? 'Task completed' : taskDescription}
                                            </div>
                                          </button>
                                        );
                                      })}
                                    </div>

                                  </div>
                                )}

                                {/* Code Section for plan_agent responses that include code */}
                                {parsed.code && 
                                 parsed.code !== "# No code to display" && 
                                 parsed.code !== "No Code to display" &&
                                 parsed.code.trim() !== "# Plan generated successfully" &&
                                 parsed.code.trim() !== "Plan generated successfully" &&
                                 parsed.code.trim().length > 0 && (
                                  <div className="mt-6 border-t pt-4">
                                    <div className="text-sm font-medium text-green-700 mb-2">📝 Generated Code</div>
                                    <div className="bg-gray-900 text-green-400 p-2 rounded text-xs font-mono overflow-x-auto">
                                      <pre>{parsed.code}</pre>
                                    </div>
                                  </div>
                                )}
                              </div>
                            );
                          }

                          // ============================================================
                          // MODELLING AGENT RESPONSE HANDLER
                          // ============================================================
                          if (parsed.role === 'modelling') {
                            try {
                              // Parse response if it's a JSON string
                              let modellingData = parsed.response;
                              if (typeof modellingData === 'string') {
                                try {
                                  modellingData = JSON.parse(modellingData);
                                } catch {
                                  // If parsing fails, it's a plain text response
                                }
                              }
                              
                              // Validate response structure if it's an object
                              if (typeof modellingData === 'object' && modellingData !== null) {
                                if (!validateModellingResponse(modellingData)) {
                                  console.warn('Invalid modelling response structure:', modellingData);
                                  // Fallback to markdown rendering
                                  return (
                                    <div className="text-sm text-gray-700 dark:text-gray-300 bg-yellow-50 dark:bg-yellow-900/20 p-3 rounded-lg border border-yellow-200 dark:border-yellow-700">
                                      <ReactMarkdown>{typeof parsed.response === 'string' ? parsed.response : JSON.stringify(parsed.response, null, 2)}</ReactMarkdown>
                                    </div>
                                  );
                                }
                              }
                            
                            return (
                              <div className="space-y-4">
                                <div className="flex items-center justify-between mb-2">
                                  <div className="text-sm font-medium text-blue-700">🤖 Model Training Assistant</div>
                                </div>

                                {/* Render plain text response OR special table for "variables used in model training" */}
                                {typeof modellingData === 'string' && (() => {
                                  const content = modellingData;
                                  const lower = content.toLowerCase();

                                  // Detect the specific explanation format:
                                  // "The variables used in model training are:\nloan_status\nlast_pymnt_d\n..."
                                  if (lower.includes('variables used in model training')) {
                                    const lines = content.split('\n');
                                    const features: string[] = [];

                                    const startIdx = lines.findIndex((l) =>
                                      l.toLowerCase().includes('variables used in model training')
                                    );

                                    if (startIdx !== -1) {
                                      for (let i = startIdx + 1; i < lines.length; i++) {
                                        let raw = lines[i].trim();
                                        if (!raw) continue;

                                        // Stop when we hit the explanation sentence
                                        if (/^these features/i.test(raw)) break;

                                        // Strip bullets like "- " or "• "
                                        raw = raw.replace(/^[-•]\s*/, '');

                                        features.push(raw);
                                      }
                                    }

                                    if (features.length > 0) {
                                      return (
                                        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 text-sm">
                                          <div className="flex items-center justify-between mb-3">
                                            <div className="font-semibold text-gray-900 dark:text-white">📊 Model Training Insights</div>
                                          </div>

                                          <div className="text-xs text-gray-600 dark:text-gray-400 mb-1">
                                            Variables Used for Model Training
                                          </div>
                                          <div className="text-[11px] text-gray-500 dark:text-gray-400 mb-3">
                                            Note: This list is extracted from the assistant&apos;s explanation text and may not
                                            include every engineered or derived feature used in the pipeline.
                                          </div>

                                          <div className="overflow-x-auto border border-gray-200 dark:border-gray-700 rounded-lg">
                                            <table className="min-w-full text-xs">
                                              <thead className="bg-gray-50 dark:bg-slate-900">
                                                <tr>
                                                  <th className="px-3 py-2 text-left border-b border-gray-300 dark:border-gray-700 text-gray-700 dark:text-gray-200">S.No</th>
                                                  <th className="px-3 py-2 text-left border-b border-gray-300 dark:border-gray-700 text-gray-700 dark:text-gray-200">Feature Name</th>
                                                </tr>
                                              </thead>
                                              <tbody>
                                                {features.map((feat, idx) => (
                                                  <tr
                                                    key={`${idx}-${feat}`}
                                                    className={idx % 2 === 0 ? 'bg-white dark:bg-slate-950' : 'bg-gray-50 dark:bg-slate-900/60'}
                                                  >
                                                    <td className="px-3 py-2 border-b border-gray-200 dark:border-gray-800 text-gray-700 dark:text-gray-200">{idx + 1}</td>
                                                    <td className="px-3 py-2 border-b border-gray-200 dark:border-gray-800 text-gray-700 dark:text-gray-200">{feat}</td>
                                                  </tr>
                                                ))}
                                              </tbody>
                                            </table>
                                          </div>
                                        </div>
                                      );
                                    }
                                  }

                                  // Default markdown rendering for other modelling responses
                                  return (
                                    <div className="text-sm text-gray-700 dark:text-gray-300 bg-blue-50 dark:bg-blue-900/20 p-3 rounded-lg border border-blue-200 dark:border-blue-700">
                                      <ReactMarkdown>{content}</ReactMarkdown>
                                    </div>
                                  );
                                })()}

                                {/* VIF charts and values from /insights/vif-analysis only (not chat tables). */}
                                {autoInsightStepStatus.variance_inflation_factor === 'running' ? (
                                  <div className="bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-700 rounded-lg p-4 text-center">
                                    <Loader className="h-6 w-6 text-purple-600 animate-spin mx-auto mb-2" />
                                    <p className="text-purple-700 dark:text-purple-400 text-sm">Analyzing VIF...</p>
                                  </div>
                                ) : activeDatasetId && (datasetConfig?.target_variable || '').trim() ? (
                                  <VIFAnalysisComponent
                                    datasetId={activeDatasetId}
                                    targetVariable={(datasetConfig?.target_variable || '').trim()}
                                    currentStep={3}
                                  />
                                ) : null}

                                {/* Render Correlation Analysis */}
                                {modellingData?.correlation_analysis && (
                                  <div className="space-y-3">
                                    {modellingData.correlation_analysis.numeric && (
                                      <div>
                                        <div className="text-xs font-semibold text-gray-800 dark:text-gray-200 mb-2 bg-green-50 px-3 py-2 rounded-t-lg border border-green-200">
                                          Numeric Correlation Analysis
                                        </div>
                                        <div className="overflow-x-auto border border-gray-200 rounded-b-lg">
                                          {modellingData.correlation_analysis.numeric.rows && modellingData.correlation_analysis.numeric.rows.length > 0 ? (
                                            <table className="min-w-full text-xs">
                                              <thead className="bg-gray-50">
                                                <tr>
                                                  {modellingData.correlation_analysis.numeric.columns?.map((col: string, idx: number) => (
                                                    <th key={idx} className="px-3 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">{col}</th>
                                                  ))}
                                                </tr>
                                              </thead>
                                              <tbody>
                                                {modellingData.correlation_analysis.numeric.rows.map((row: any, rowIdx: number) => (
                                                  <tr key={rowIdx} className={rowIdx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                                                    {modellingData.correlation_analysis.numeric.columns?.map((col: string, colIdx: number) => (
                                                      <td key={colIdx} className="px-3 py-2 border-b border-gray-200 text-gray-700">
                                                        {formatTableCellValue(row[col], col)}
                                                      </td>
                                                    ))}
                                                  </tr>
                                                ))}
                                              </tbody>
                                            </table>
                                          ) : (
                                            <div className="px-4 py-8 text-center text-sm text-gray-500 bg-gray-50">
                                              No results match the specified filter criteria.
                                            </div>
                                          )}
                                        </div>
                                      </div>
                                    )}
                                    {modellingData.correlation_analysis.categorical && (
                                      <div>
                                        <div className="text-xs font-semibold text-gray-800 dark:text-gray-200 mb-2 bg-green-50 dark:bg-slate-900/70 px-3 py-2 rounded-t-lg border border-green-200 dark:border-slate-700">
                                          Categorical Correlation Analysis
                                        </div>
                                        <div className="overflow-x-auto border border-gray-200 dark:border-gray-700 rounded-b-lg">
                                          {modellingData.correlation_analysis.categorical.rows && modellingData.correlation_analysis.categorical.rows.length > 0 ? (
                                            <table className="min-w-full text-xs">
                                              <thead className="bg-gray-50 dark:bg-slate-900">
                                                <tr>
                                                  {modellingData.correlation_analysis.categorical.columns?.map((col: string, idx: number) => (
                                                    <th key={idx} className="px-3 py-2 text-left border-b border-gray-300 dark:border-gray-700 font-semibold text-gray-700 dark:text-gray-200">{col}</th>
                                                  ))}
                                                </tr>
                                              </thead>
                                              <tbody>
                                                {modellingData.correlation_analysis.categorical.rows.map((row: any, rowIdx: number) => (
                                                  <tr key={rowIdx} className={rowIdx % 2 === 0 ? 'bg-white dark:bg-slate-950' : 'bg-gray-50 dark:bg-slate-900/60'}>
                                                    {modellingData.correlation_analysis.categorical.columns?.map((col: string, colIdx: number) => (
                                                      <td key={colIdx} className="px-3 py-2 border-b border-gray-200 dark:border-gray-800 text-gray-700 dark:text-gray-200">
                                                        {formatTableCellValue(row[col], col)}
                                                      </td>
                                                    ))}
                                                  </tr>
                                                ))}
                                              </tbody>
                                            </table>
                                          ) : (
                                            <div className="px-4 py-8 text-center text-sm text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-slate-900/60">
                                              No results match the specified filter criteria.
                                            </div>
                                          )}
                                        </div>
                                      </div>
                                    )}
                                  </div>
                                )}

                                {/* Render Variable Screener (Correlation + VIF from Variable Screener) */}
                                {modellingData?.variable_screener &&
                                  Array.isArray(modellingData.variable_screener) &&
                                  modellingData.variable_screener.length > 0 && (
                                  <div className="space-y-2">
                                    {modellingData.variable_screener.map((table: any, idx: number) => (
                                      <div key={idx}>
                                        <div className="text-xs font-semibold text-gray-800 dark:text-gray-200 mb-2 bg-teal-50 px-3 py-2 rounded-t-lg border border-teal-200">
                                          {table.title || 'Variable Screener - Correlation, VIF & IV'}
                                        </div>
                                        <div className="overflow-x-auto border border-gray-200 rounded-b-lg">
                                          <table className="min-w-full text-xs">
                                            <thead className="bg-gray-50">
                                              <tr>
                                                {table.columns?.map((col: string, colIdx: number) => (
                                                  <th
                                                    key={colIdx}
                                                    className="px-3 py-2 text-left border-b border-gray-300 font-semibold text-gray-700"
                                                  >
                                                    {col}
                                                  </th>
                                                ))}
                                              </tr>
                                            </thead>
                                            <tbody>
                                              {table.rows?.map((row: any, rowIdx: number) => (
                                                <tr
                                                  key={rowIdx}
                                                  className={rowIdx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}
                                                >
                                                  {table.columns?.map((col: string, colIdx: number) => (
                                                    <td
                                                      key={colIdx}
                                                      className="px-3 py-2 border-b border-gray-200 text-gray-700"
                                                    >
                                                      {row[col] ?? '-'}
                                                    </td>
                                                  ))}
                                                </tr>
                                              ))}
                                            </tbody>
                                          </table>
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                )}

                                {/* IV charts and values from /insights/iv-analysis only (not chat tables). */}
                                {autoInsightStepStatus.iv_analysis === 'running' ? (
                                  <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-700 rounded-lg p-4 text-center">
                                    <Loader className="h-6 w-6 text-yellow-600 animate-spin mx-auto mb-2" />
                                    <p className="text-yellow-700 dark:text-yellow-400 text-sm">Analyzing IV...</p>
                                  </div>
                                ) : activeDatasetId && (datasetConfig?.target_variable || '').trim() ? (
                                  <IVAnalysisComponent
                                    datasetId={activeDatasetId}
                                    targetVariable={(datasetConfig?.target_variable || '').trim()}
                                    currentStep={3}
                                  />
                                ) : null}

                                {/* Correlation ratio η heatmap from /insights/correlation-ratio-analysis (not chat). */}
                                {autoInsightStepStatus.correlation_ratio_analysis === 'running' ? (
                                  <div className="bg-teal-50 dark:bg-teal-900/20 border border-teal-200 dark:border-teal-800 rounded-lg p-4 text-center">
                                    <Loader className="h-6 w-6 text-teal-600 animate-spin mx-auto mb-2" />
                                    <p className="text-teal-800 dark:text-teal-200 text-sm">Computing correlation ratio (η)…</p>
                                  </div>
                                ) : activeDatasetId && (datasetConfig?.target_variable || '').trim() ? (
                                  <CorrelationRatioAnalysisComponent
                                    datasetId={activeDatasetId}
                                    targetVariable={(datasetConfig?.target_variable || '').trim()}
                                    currentStep={3}
                                  />
                                ) : null}

                                {/* Render Model Comparison */}
                                {modellingData?.model_comparison && Array.isArray(modellingData.model_comparison) && modellingData.model_comparison.length > 0 && (
                                  <div className="space-y-2">
                                    {modellingData.model_comparison.map((table: any, idx: number) => (
                                      <div key={idx}>
                                        <div className="text-xs font-semibold text-gray-800 dark:text-gray-200 mb-2 bg-blue-50 px-3 py-2 rounded-t-lg border border-blue-200">
                                          {table.title || 'Model Comparison'}
                                        </div>
                                        <div className="overflow-x-auto border border-gray-200 rounded-b-lg">
                                          {table.rows && table.rows.length > 0 ? (
                                            <table className="min-w-full text-xs">
                                              <thead className="bg-gray-50">
                                                <tr>
                                                  {table.columns?.map((col: string, colIdx: number) => (
                                                    <th key={colIdx} className="px-3 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">{col}</th>
                                                  ))}
                                                </tr>
                                              </thead>
                                              <tbody>
                                                {table.rows.map((row: any, rowIdx: number) => (
                                                  <tr key={rowIdx} className={rowIdx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                                                    {table.columns?.map((col: string, colIdx: number) => (
                                                      <td key={colIdx} className="px-3 py-2 border-b border-gray-200 text-gray-700">
                                                        {formatTableCellValue(row[col], col)}
                                                      </td>
                                                    ))}
                                                  </tr>
                                                ))}
                                              </tbody>
                                            </table>
                                          ) : (
                                            <div className="px-4 py-8 text-center text-sm text-gray-500 bg-gray-50">
                                              No model comparison data available.
                                            </div>
                                          )}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                )}

                                {/* Render Feature Statistics */}
                                {modellingData?.feature_statistics && Array.isArray(modellingData.feature_statistics) && modellingData.feature_statistics.length > 0 && (
                                  <div className="space-y-2 mb-4">
                                    {modellingData.feature_statistics.map((table: any, idx: number) => (
                                      <div key={idx}>
                                        <div className="text-xs font-semibold text-gray-800 dark:text-gray-200 mb-2 bg-emerald-50 px-3 py-2 rounded-t-lg border border-emerald-200">
                                          {table.title || 'Feature Statistics'}
                                        </div>
                                        <div className="overflow-x-auto border border-gray-200 rounded-b-lg">
                                          {table.rows && table.rows.length > 0 ? (
                                            <table className="min-w-full text-xs">
                                              <thead className="bg-gray-50">
                                                <tr>
                                                  {table.columns?.map((col: string, colIdx: number) => (
                                                    <th key={colIdx} className="px-3 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">{col}</th>
                                                  ))}
                                                </tr>
                                              </thead>
                                              <tbody>
                                                {table.rows.map((row: any, rowIdx: number) => (
                                                  <tr key={rowIdx} className={rowIdx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                                                    {table.columns?.map((col: string, colIdx: number) => (
                                                      <td key={colIdx} className="px-3 py-2 border-b border-gray-200 text-gray-700">
                                                        {formatTableCellValue(row[col], col)}
                                                      </td>
                                                    ))}
                                                  </tr>
                                                ))}
                                              </tbody>
                                            </table>
                                          ) : (
                                            <div className="px-4 py-8 text-center text-sm text-gray-500 bg-gray-50">
                                              No feature statistics available.
                                            </div>
                                          )}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                )}

                                {/* Render Iterations Summary */}
                                {modellingData?.iterations_summary && Array.isArray(modellingData.iterations_summary) && modellingData.iterations_summary.length > 0 && (
                                  <div className="space-y-2 mb-4">
                                    {modellingData.iterations_summary.map((table: any, idx: number) => (
                                      <div key={idx}>
                                        <div className="text-xs font-semibold text-gray-800 dark:text-gray-200 mb-2 bg-purple-50 px-3 py-2 rounded-t-lg border border-purple-200">
                                          {table.title || 'Iterations Summary'}
                                        </div>
                                        <div className="overflow-x-auto border border-gray-200 rounded-b-lg">
                                          {table.rows && table.rows.length > 0 ? (
                                            <table className="min-w-full text-xs">
                                              <thead className="bg-gray-50">
                                                <tr>
                                                  {table.columns?.map((col: string, colIdx: number) => (
                                                    <th key={colIdx} className="px-3 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">{col}</th>
                                                  ))}
                                                </tr>
                                              </thead>
                                              <tbody>
                                                {table.rows.map((row: any, rowIdx: number) => (
                                                  <tr key={rowIdx} className={rowIdx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                                                    {table.columns?.map((col: string, colIdx: number) => (
                                                      <td key={colIdx} className="px-3 py-2 border-b border-gray-200 text-gray-700">
                                                        {formatTableCellValue(row[col], col)}
                                                      </td>
                                                    ))}
                                                  </tr>
                                                ))}
                                              </tbody>
                                            </table>
                                          ) : (
                                            <div className="px-4 py-8 text-center text-sm text-gray-500 bg-gray-50">
                                              No iterations data available.
                                            </div>
                                          )}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                )}

                                {/* Render Pruned Models Summary */}
                                {modellingData?.pruned_models_summary && Array.isArray(modellingData.pruned_models_summary) && modellingData.pruned_models_summary.length > 0 && (
                                  <div className="space-y-2 mb-4">
                                    {modellingData.pruned_models_summary.map((table: any, idx: number) => (
                                      <div key={idx}>
                                        <div className="text-xs font-semibold text-gray-800 dark:text-gray-200 mb-2 bg-rose-50 px-3 py-2 rounded-t-lg border border-rose-200">
                                          {table.title || 'Pruned Models Summary'}
                                        </div>
                                        <div className="overflow-x-auto border border-gray-200 rounded-b-lg">
                                          {table.rows && table.rows.length > 0 ? (
                                            <table className="min-w-full text-xs">
                                              <thead className="bg-gray-50">
                                                <tr>
                                                  {table.columns?.map((col: string, colIdx: number) => (
                                                    <th key={colIdx} className="px-3 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">{col}</th>
                                                  ))}
                                                </tr>
                                              </thead>
                                              <tbody>
                                                {table.rows.map((row: any, rowIdx: number) => (
                                                  <tr key={rowIdx} className={rowIdx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                                                    {table.columns?.map((col: string, colIdx: number) => (
                                                      <td key={colIdx} className="px-3 py-2 border-b border-gray-200 text-gray-700">
                                                        {formatTableCellValue(row[col], col)}
                                                      </td>
                                                    ))}
                                                  </tr>
                                                ))}
                                              </tbody>
                                            </table>
                                          ) : (
                                            <div className="px-4 py-8 text-center text-sm text-gray-500 bg-gray-50">
                                              No pruned models available.
                                            </div>
                                          )}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                )}

                                {/* Render CV Summary */}
                                {modellingData?.cv_summary && Array.isArray(modellingData.cv_summary) && modellingData.cv_summary.length > 0 && (
                                  <div className="space-y-2">
                                    {modellingData.cv_summary.map((table: any, idx: number) => (
                                      <div key={idx}>
                                        <div className="text-xs font-semibold text-gray-800 dark:text-gray-200 mb-2 bg-indigo-50 px-3 py-2 rounded-t-lg border border-indigo-200">
                                          {table.title || 'Cross-Validation Summary'}
                                        </div>
                                        <div className="overflow-x-auto border border-gray-200 rounded-b-lg">
                                          {table.rows && table.rows.length > 0 ? (
                                            <table className="min-w-full text-xs">
                                              <thead className="bg-gray-50">
                                                <tr>
                                                  {table.columns?.map((col: string, colIdx: number) => (
                                                    <th key={colIdx} className="px-3 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">{col}</th>
                                                  ))}
                                                </tr>
                                              </thead>
                                              <tbody>
                                                {table.rows.map((row: any, rowIdx: number) => (
                                                  <tr key={rowIdx} className={rowIdx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                                                    {table.columns?.map((col: string, colIdx: number) => (
                                                      <td key={colIdx} className="px-3 py-2 border-b border-gray-200 text-gray-700">
                                                        {formatTableCellValue(row[col], col)}
                                                      </td>
                                                    ))}
                                                  </tr>
                                                ))}
                                              </tbody>
                                            </table>
                                          ) : (
                                            <div className="px-4 py-8 text-center text-sm text-gray-500 bg-gray-50">
                                              No cross-validation data available.
                                            </div>
                                          )}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                )}

                                {/* Render Confusion Matrix Summary */}
                                {modellingData?.confusion_matrix_summary && Array.isArray(modellingData.confusion_matrix_summary) && modellingData.confusion_matrix_summary.length > 0 && (
                                  <div className="space-y-2">
                                    {modellingData.confusion_matrix_summary.map((table: any, idx: number) => (
                                      <div key={idx}>
                                        <div className="text-xs font-semibold text-gray-800 dark:text-gray-200 mb-2 bg-red-50 px-3 py-2 rounded-t-lg border border-red-200">
                                          {table.title || 'Confusion Matrix Summary'}
                                        </div>
                                        <div className="overflow-x-auto border border-gray-200 rounded-b-lg">
                                          {table.rows && table.rows.length > 0 ? (
                                            <table className="min-w-full text-xs">
                                              <thead className="bg-gray-50">
                                                <tr>
                                                  {table.columns?.map((col: string, colIdx: number) => (
                                                    <th key={colIdx} className="px-3 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">{col}</th>
                                                  ))}
                                                </tr>
                                              </thead>
                                              <tbody>
                                                {table.rows.map((row: any, rowIdx: number) => (
                                                  <tr key={rowIdx} className={rowIdx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                                                    {table.columns?.map((col: string, colIdx: number) => (
                                                      <td key={colIdx} className="px-3 py-2 border-b border-gray-200 text-gray-700">
                                                        {formatTableCellValue(row[col], col)}
                                                      </td>
                                                    ))}
                                                  </tr>
                                                ))}
                                              </tbody>
                                            </table>
                                          ) : (
                                            <div className="px-4 py-8 text-center text-sm text-gray-500 bg-gray-50">
                                              No confusion matrix data available.
                                            </div>
                                          )}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                )}

                                {/* Render Used Features */}
                                {modellingData?.used_features && modellingData.used_features.columns && (
                                  <div>
                                    <div className="text-xs font-semibold text-gray-800 dark:text-gray-200 mb-2 bg-teal-50 px-3 py-2 rounded-t-lg border border-teal-200">
                                      {modellingData.used_features.title || 'Used Features'}
                                    </div>
                                    <div className="overflow-x-auto border border-gray-200 rounded-b-lg">
                                      {modellingData.used_features.rows && modellingData.used_features.rows.length > 0 ? (
                                        <table className="min-w-full text-xs">
                                          <thead className="bg-gray-50">
                                            <tr>
                                              {modellingData.used_features.columns.map((col: string, idx: number) => (
                                                <th key={idx} className="px-3 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">{col}</th>
                                              ))}
                                            </tr>
                                          </thead>
                                          <tbody>
                                            {modellingData.used_features.rows.map((row: any, rowIdx: number) => (
                                              <tr key={rowIdx} className={rowIdx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                                                {modellingData.used_features.columns.map((col: string, colIdx: number) => (
                                                  <td key={colIdx} className="px-3 py-2 border-b border-gray-200 text-gray-700">
                                                    {formatTableCellValue(row[col], col)}
                                                  </td>
                                                ))}
                                              </tr>
                                            ))}
                                          </tbody>
                                        </table>
                                      ) : (
                                        <div className="px-4 py-8 text-center text-sm text-gray-500 bg-gray-50">
                                          No features found.
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                )}

                                {/* Render Used Features Analysis (VIF/IV/Correlation of used features) */}
                                {modellingData?.used_features_analysis && Array.isArray(modellingData.used_features_analysis) && modellingData.used_features_analysis.length > 0 && (
                                  <div className="space-y-2">
                                    {modellingData.used_features_analysis.map((table: any, idx: number) => (
                                      <div key={idx}>
                                        <div className="text-xs font-semibold text-gray-800 dark:text-gray-200 mb-2 bg-blue-50 px-3 py-2 rounded-t-lg border border-blue-200">
                                          {table.title || 'Used Features Analysis'}
                                        </div>
                                        <div className="overflow-x-auto border border-gray-200 rounded-b-lg">
                                          {table.rows && table.rows.length > 0 ? (
                                            <table className="min-w-full text-xs">
                                              <thead className="bg-gray-50">
                                                <tr>
                                                  {table.columns?.map((col: string, colIdx: number) => (
                                                    <th key={colIdx} className="px-3 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">{col}</th>
                                                  ))}
                                                </tr>
                                              </thead>
                                              <tbody>
                                                {table.rows.map((row: any, rowIdx: number) => (
                                                  <tr key={rowIdx} className={rowIdx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                                                    {table.columns?.map((col: string, colIdx: number) => (
                                                      <td key={colIdx} className="px-3 py-2 border-b border-gray-200 text-gray-700">
                                                        {formatTableCellValue(row[col], col)}
                                                      </td>
                                                    ))}
                                                  </tr>
                                                ))}
                                              </tbody>
                                            </table>
                                          ) : (
                                            <div className="px-4 py-8 text-center text-sm text-gray-500 bg-gray-50">
                                              No results match the specified filter criteria.
                                            </div>
                                          )}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                )}

                                {/* Render Bivariate Analysis */}
                                {modellingData?.bivariate_analysis && Array.isArray(modellingData.bivariate_analysis) && modellingData.bivariate_analysis.length > 0 && (
                                  <div className="space-y-3">
                                    <div className="text-xs font-semibold text-gray-800 dark:text-gray-200 bg-orange-50 px-3 py-2 rounded-lg border border-orange-200">
                                      Bivariate Analysis
                                    </div>
                                    {modellingData.bivariate_analysis.map((table: any, idx: number) => (
                                      <div key={idx}>
                                        <div className="text-xs font-medium text-gray-700 mb-1 px-2">{table.title}</div>
                                        <div className="overflow-x-auto border border-gray-200 rounded-lg">
                                          <table className="min-w-full text-xs">
                                            <thead className="bg-gray-50">
                                              <tr>
                                                {table.columns?.map((col: string, colIdx: number) => (
                                                  <th key={colIdx} className="px-3 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">{col}</th>
                                                ))}
                                              </tr>
                                            </thead>
                                            <tbody>
                                              {table.rows?.map((row: any, rowIdx: number) => (
                                                <tr key={rowIdx} className={rowIdx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                                                  {table.columns?.map((col: string, colIdx: number) => (
                                                    <td key={colIdx} className="px-3 py-2 border-b border-gray-200 text-gray-700">{row[col] || '-'}</td>
                                                  ))}
                                                </tr>
                                              ))}
                                            </tbody>
                                          </table>
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                )}

                                {/* Render Suggestions */}
                                {parsed.suggestion && Array.isArray(parsed.suggestion) && parsed.suggestion.length > 0 && (
                                  <div className="mt-4">
                                    <div className="text-sm font-medium text-purple-700 mb-2">💡 Suggestions</div>
                                    <ul className="text-sm text-gray-700 space-y-1 bg-purple-50 p-3 rounded-lg border border-purple-200">
                                      {parsed.suggestion.map((suggestion: string, index: number) => (
                                        <li key={index} className="flex items-start space-x-2">
                                          <span className="text-purple-500 mt-0.5 font-bold">•</span>
                                          <span>{suggestion}</span>
                                        </li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                              </div>
                            );
                            } catch (error) {
                              console.error('Error rendering modelling response:', error);
                              return (
                                <div className="text-sm text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-900/20 p-3 rounded-lg border border-red-200 dark:border-red-700">
                                  Error rendering response. Please try again.
                                  {process.env.NODE_ENV === 'development' && (
                                    <div className="mt-2 text-xs text-red-600">
                                      {String(error)}
                                    </div>
                                  )}
                                </div>
                              );
                            }
                          }
                          // ============================================================
                          // END MODELLING AGENT RESPONSE HANDLER
                          // ============================================================

                          // ============================================================
                          // MANUAL QC COMPLETION MESSAGE HANDLER
                          // Shows summary card with treatment statuses + View Updated EDA
                          // ============================================================
                          if (parsed.isManualQCComplete) {
                            return (
                              <div className="space-y-3">
                                <div className="bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-700 rounded-lg p-4">
                                  <div className="flex items-start space-x-3">
                                    <div className="flex-shrink-0">
                                      <svg className="w-6 h-6 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                      </svg>
                                    </div>
                                    <div className="flex-1">
                                      <h3 className="text-sm font-semibold text-green-800 dark:text-green-300">
                                        Data Quality Treatment Complete!
                                      </h3>
                                      <div className="mt-3 flex items-center space-x-2">
                                        <button
                                          onClick={() => {
                                            setShowDatasetOverview(true);
                                            setShowEDAComparison(true);
                                            triggerEdaComparisonView();
                                          }}
                                          className="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-md bg-green-100 dark:bg-green-800 text-green-800 dark:text-green-200 hover:bg-green-200 dark:hover:bg-green-700 transition-colors"
                                        >
                                          <svg className="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                                          </svg>
                                          View Updated EDA
                                        </button>
                                      </div>
                                    </div>
                                  </div>
                                </div>
                              </div>
                            );
                          }

                          // Check if this is a regular API response with response, code, suggestions
                          if (parsed.response || parsed.code || parsed.suggestions) {
                            return (
                              <div className="space-y-4">
                                {/* Explanation Section */}
                                {parsed.response && (
                                  <div>
                                    <div className="text-sm font-medium text-blue-700 dark:text-blue-400 mb-2">💡 Explanation</div>
                                    <div className="text-sm text-gray-700 dark:text-gray-300">
                                      {typeof parsed.response === 'string' ? (
                                        <ReactMarkdown>{parsed.response}</ReactMarkdown>
                                      ) : (
                                        <div className="bg-gray-100 dark:bg-gray-800 p-4 rounded-lg overflow-x-auto text-xs font-mono">
                                          <pre>{JSON.stringify(parsed.response, null, 2)}</pre>
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                )}
                                
                                {/* Code Section */}
                                {parsed.code && 
                                 parsed.code !== "# No code to display" && 
                                 parsed.code !== "No Code to display" &&
                                 parsed.code.trim() !== "# Plan generated successfully" &&
                                 parsed.code.trim() !== "Plan generated successfully" &&
                                 parsed.code.trim().length > 0 && (
                                  <div>
                                    <div className="text-sm font-medium text-green-700 dark:text-green-400 mb-2">📝 Code</div>
                                    <div className="bg-gray-900 text-green-400 p-2 rounded text-xs font-mono overflow-x-auto">
                                      <pre>{parsed.code}</pre>
                                    </div>

                                    {/* Knowledge Disclaimer for Explanation section - after Execute button */}
                                    {step === 2 && message.knowledge_metadata && (
                                      <KnowledgeDisclaimer
                                        sourceFiles={message.knowledge_metadata.source_files || []}
                                        useExlExpertise={message.knowledge_metadata.use_exl_expertise !== false}
                                      />
                                    )}

                                    {/* Execution Results */}
                                    {executionResults[generateCodeId(message.id, parsed.code)] && (
                                      <div className="mt-3">
                                        <div className="text-sm font-medium text-blue-700 mb-2">🚀 Execution Results</div>
                                        {executionResults[generateCodeId(message.id, parsed.code)]?.isLoading ? (
                                          <div className="text-sm text-gray-600">Executing code...</div>
                                        ) : executionResults[generateCodeId(message.id, parsed.code)]?.error ? (
                                          <div className="text-sm text-red-600 bg-red-50 p-2 rounded">
                                            Error: {executionResults[generateCodeId(message.id, parsed.code)]?.error}
                                          </div>
                                        ) : (
                                          <div className="space-y-3">
                                            {/* Response output hidden */}
                                            {(() => {
                                              const codeId = generateCodeId(message.id, parsed.code);
                                              const result = executionResults[codeId];
                                              const hasColumnsInfo = result?.columns_info && result.columns_info.length > 0;
                                              
                                              // Debug logging
                                              console.log('📊 Column Stats check for code:', codeId, {
                                                has_result: !!result,
                                                has_columns_info: !!result?.columns_info,
                                                columns_info_length: result?.columns_info?.length,
                                                columns_info: result?.columns_info
                                              });
                                              
                                              // Always show buttons after successful execution, even if columns_info is empty
                                              return (
                                              <div>
                                                <div className="flex justify-between items-center mb-2">
                                                  <div className="text-sm font-medium text-gray-700 dark:text-gray-300">📊 Column Stats {!hasColumnsInfo && '(No data)'}</div>
                                                  <div className="flex items-center gap-2">
                                                    <button
                                                      onClick={downloadColumnStats}
                                                      disabled={!hasColumnsInfo}
                                                      className="px-3 py-1 bg-green-600 text-white text-xs rounded hover:bg-green-700 transition-colors flex items-center space-x-1 disabled:opacity-50 disabled:cursor-not-allowed"
                                                      title="Download Column Stats table as CSV"
                                                    >
                                                      <Download className="w-3 h-3" />
                                                      <span>Download Stats Table</span>
                                                    </button>
                                                    <button
                                                      onClick={handleCompareChanges}
                                                      disabled={isLoadingComparison}
                                                      className="px-3 py-1 bg-purple-600 text-white text-xs rounded hover:bg-purple-700 transition-colors flex items-center space-x-1 disabled:opacity-50"
                                                      title="Compare original vs processed statistics"
                                                    >
                                                      {isLoadingComparison ? (
                                                        <>
                                                          <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                                                          <span>Loading...</span>
                                                        </>
                                                      ) : (
                                                        <>
                                                          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                                                          </svg>
                                                          <span>Compare Changes</span>
                                                        </>
                                                      )}
                                                    </button>
                                                  </div>
                                                </div>
                                                {hasColumnsInfo && (
                                                <div className="overflow-x-auto">
                                                  <table className="min-w-full text-xs border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white">
                                                    <thead>
                                                      <tr className="bg-gray-100 dark:bg-gray-800">
                                                        <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">Column</th>
                                                        <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">Type</th>
                                                        <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">Missing</th>
                                                        <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">Unique</th>
                                                        <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">Mean</th>
                                                        <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">Median</th>
                                                        <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">Mode</th>
                                                        <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">Std</th>
                                                        <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">Var</th>
                                                        <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">Min</th>
                                                        <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">p5%</th>
                                                        <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">p25%</th>
                                                        <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">p50%</th>
                                                        <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">p75%</th>
                                                        <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">p95%</th>
                                                        <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">p99%</th>
                                                        <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">Max</th>
                                                      </tr>
                                                    </thead>
                                                    <tbody>
                                                      {executionResults[generateCodeId(message.id, parsed.code)]?.columns_info?.map((col: any, idx: number) => {
                                                        // Use improved column_type from backend API (with smart classification logic)
                                                        const columnType = col.column_type || (['int64', 'float64', 'int32', 'float32'].includes(col.data_type) ? 'Numerical' : 'Categorical');
                                                        
                                                        // Find the original column info for comparison
                                                        const colName = col.column_name || col.name;
                                                        const baselineColumns = executionBaselines[generateCodeId(message.id, parsed.code)] || originalColumnInfo;
                                                        const originalCol = baselineColumns?.find(
                                                          (oc: any) => (oc.column_name || oc.name) === colName
                                                        );
                                                        
                                                        // Helper to format value, using original if current is null
                                                        const formatValue = (currentVal: any, originalVal: any, isNumeric: boolean = true) => {
                                                          const val = (currentVal !== null && currentVal !== undefined) ? currentVal : originalVal;
                                                          if (val === null || val === undefined) return '';
                                                          if (typeof val === 'number' && isNumeric) return val.toFixed(2);
                                                          return String(val);
                                                        };
                                                        
                                                        // Helper to check if value changed and get appropriate cell class
                                                        const getCellClass = (currentValue: any, originalValue: any, isNumeric: boolean = true) => {
                                                          let isDifferent = false;
                                                          if (originalCol) {
                                                            if (
                                                              (currentValue === null || currentValue === undefined) &&
                                                              (originalValue === null || originalValue === undefined)
                                                            ) {
                                                              isDifferent = false;
                                                            } else if (
                                                              currentValue === null || currentValue === undefined ||
                                                              originalValue === null || originalValue === undefined
                                                            ) {
                                                              isDifferent = true;
                                                            } else if (typeof currentValue === 'number' && typeof originalValue === 'number' && isNumeric) {
                                                              isDifferent = Math.abs(currentValue - originalValue) > 1e-9;
                                                            } else {
                                                              isDifferent = String(currentValue) !== String(originalValue);
                                                            }
                                                          }
                                                          return `px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white ${isDifferent ? 'bg-yellow-100 text-amber-800 font-medium dark:bg-yellow-900/30 dark:text-white' : ''}`;
                                                        };
                                                        
                                                        return (
                                                        <tr key={idx} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                                                          <td className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white font-medium">{col.column_name}</td>
                                                          <td className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white" title={`pandas dtype: ${col.data_type}`}>
                                                            {columnType}
                                                          </td>
                                                          <td className={getCellClass(col.missing_count, originalCol?.missing_count, false)}>{formatValue(col.missing_count, originalCol?.missing_count, false)}</td>
                                                          <td className={getCellClass(col.unique_count, originalCol?.unique_count, false)}>{formatValue(col.unique_count, originalCol?.unique_count, false)}</td>
                                                          <td className={getCellClass(col.mean, originalCol?.mean)}>{formatValue(col.mean, originalCol?.mean)}</td>
                                                          <td className={getCellClass(col.median, originalCol?.median)}>{formatValue(col.median, originalCol?.median)}</td>
                                                          <td className={`${getCellClass(col.mode, originalCol?.mode, false)} max-w-[150px] truncate`} title={formatValue(col.mode, originalCol?.mode, false)}>
                                                            {formatValue(col.mode, originalCol?.mode, false)}
                                                          </td>
                                                          <td className={getCellClass(col.standard_deviation, originalCol?.standard_deviation)}>{formatValue(col.standard_deviation, originalCol?.standard_deviation)}</td>
                                                          <td className={getCellClass(col.variance, originalCol?.variance)}>{formatValue(col.variance, originalCol?.variance)}</td>
                                                          <td className={getCellClass(col.min_value, originalCol?.min_value)}>{formatValue(col.min_value, originalCol?.min_value)}</td>
                                                          <td className={getCellClass(col.percentile_5, originalCol?.percentile_5)}>{formatValue(col.percentile_5, originalCol?.percentile_5)}</td>
                                                          <td className={getCellClass(col.percentile_25, originalCol?.percentile_25)}>{formatValue(col.percentile_25, originalCol?.percentile_25)}</td>
                                                          <td className={getCellClass(col.percentile_50, originalCol?.percentile_50)}>{formatValue(col.percentile_50, originalCol?.percentile_50)}</td>
                                                          <td className={getCellClass(col.percentile_75, originalCol?.percentile_75)}>{formatValue(col.percentile_75, originalCol?.percentile_75)}</td>
                                                          <td className={getCellClass(col.percentile_95, originalCol?.percentile_95)}>{formatValue(col.percentile_95, originalCol?.percentile_95)}</td>
                                                          <td className={getCellClass(col.percentile_99, originalCol?.percentile_99)}>{formatValue(col.percentile_99, originalCol?.percentile_99)}</td>
                                                          <td className={getCellClass(col.max_value, originalCol?.max_value)}>{formatValue(col.max_value, originalCol?.max_value)}</td>
                                                        </tr>
                                                        );
                                                      })}
                                                    </tbody>
                                                  </table>
                                                </div>
                                                )}
                                              </div>
                                              );
                                            })()}
                                          </div>
                                        )}
                                      </div>
                                    )}
                                  </div>
                                )}
                                
                                {/* Suggestions Section */}
                                {parsed.suggestions && parsed.suggestions.length > 0 && (
                                  <div>
                                    <div className="text-sm font-medium text-purple-700 dark:text-purple-400 mb-2">🔍 Suggestions</div>
                                    <ul className="text-sm text-gray-700 dark:text-gray-300 space-y-1">
                                      {parsed.suggestions.map((suggestion: string, index: number) => (
                                        <li key={index} className="flex items-start space-x-2">
                                          <span className="text-purple-500 mt-0.5">•</span>
                                          <span>{suggestion}</span>
                                        </li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                              </div>
                            );
                          }
                          
                          // Fallback for other JSON structures
                          return <ReactMarkdown>{message.content}</ReactMarkdown>;
                        } catch {
                          // Not JSON, render as regular markdown
                          return <ReactMarkdown>{message.content}</ReactMarkdown>;
                        }
                      })()}
                    </div>

                    {/* Knowledge Disclaimer for assistant messages on Data Insights and Feature Engineering steps */}
                    {message.type === 'assistant' && (step === 3 || step === 4) && message.knowledge_metadata && (
                      <KnowledgeDisclaimer
                        sourceFiles={message.knowledge_metadata.source_files || []}
                        useExlExpertise={message.knowledge_metadata.use_exl_expertise !== false}
                      />
                    )}

                    <div className="text-xs opacity-70 mt-1">

                      {message.timestamp.toLocaleTimeString()}

                    </div>

                  </div>

                </div>

              ))}

              

              {typing && (

                <div className="flex justify-start">

                  <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-2">

                    <div className="flex items-center space-x-2">

                      <Brain className="h-3 w-3 text-blue-600" />

                      <div className="flex space-x-1">

                        <div className="w-1 h-1 bg-gray-400 rounded-full animate-bounce"></div>

                        <div className="w-1 h-1 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.1s'}}></div>

                        <div className="w-1 h-1 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>

                      </div>

                    </div>

                  </div>

                </div>

              )}

            </div>

          )}

        </div>

        

        {/* Chat Input */}

        <div className="flex items-center space-x-2">

          <input

            type="text"

            value={input}

            onChange={(e) => setChatInputs(prev => ({ ...prev, [step]: e.target.value }))}

            onKeyDown={(e) => {

              if (e.key === 'Enter' && !typing) {

                e.preventDefault();

                handleSendChatMessage(step);

              }

            }}

            placeholder="Ask about this step..."

            className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"

            disabled={typing}

          />

          <button

            onClick={() => handleSendChatMessage(step)}

            disabled={!input.trim() || typing}

            className="p-2 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"

          >

            <ArrowRight className="h-4 w-4" />

          </button>

        </div>

      </div>

    );

  };



  const renderStepContent = () => {

    switch (currentStep) {

      case 1:

        return (

          <Step1ObjectivesData

            selectedDataSources={selectedDataSources}

            onDataSourceSelect={handleDataSourceSelect}

            onRemoveDataSource={handleRemoveDataSource}

            onUpdateFilePartition={handleUpdateFilePartition}

            showDataSourceSelectionModal={showDataSourceSelectionModal}

            setShowDataSourceSelectionModal={setShowDataSourceSelectionModal}

            datasetAnalysis={datasetAnalysis}

            setDatasetAnalysis={setDatasetAnalysis}

            isAnalyzingDataset={isAnalyzingDataset}

            isUploadingDataset={isUploadingDataset}

            mlClassificationPending={mlClassificationPending}

            datasetConfig={datasetConfig}

            setDatasetConfig={setDatasetConfig}

            activeDatasetId={activeDatasetId}

            pendingDatasetId={pendingDatasetId}

            setActiveDatasetId={setActiveDatasetId}

            showDatasetOverview={showDatasetOverview}

            setShowDatasetOverview={setShowDatasetOverview}

            chatInputs={chatInputs}

            setChatInputs={setChatInputs}

            dataDictionaryFile={dataDictionaryFile}

            setDataDictionaryFile={setDataDictionaryFile}

            onDataDictionaryFileSelect={handleDataDictionaryFileSelect}

            onRemoveDataDictionaryFile={handleRemoveDataDictionaryFile}

            onSubmitDataset={handleSubmitDataset}
            stagedUserKnowledgeFiles={stagedUserKnowledgeFiles}
            setStagedUserKnowledgeFiles={setStagedUserKnowledgeFiles}
            stagedUseAcrossMidas={stagedUseAcrossMidas}
            setStagedUseAcrossMidas={setStagedUseAcrossMidas}
            stagedUseExlExpertise={stagedUseExlExpertise}
            setStagedUseExlExpertise={setStagedUseExlExpertise}
            canSubmitDataset={canSubmitDataset}
            submitValidationError={step1SubmitError}
            submitBlockedReason={submitBlockedReason || undefined}

            hasProceededToConfig={hasProceededToConfig}
            setHasProceededToConfig={setHasProceededToConfig}
            onProceedToConfig={handleProceedToConfig}
            isProceedingToConfig={isProceedingToConfig}

            mlClassificationResult={mlClassificationResult}

            mlClassificationError={mlClassificationError}

          />

        );



      case 2:

        return (

          <Step2DataQC

            selectedDataSources={selectedDataSources}

            onDataSourceSelect={handleDataSourceSelect}

            onRemoveDataSource={handleRemoveDataSource}

            showDataSourceSelectionModal={showDataSourceSelectionModal}

            setShowDataSourceSelectionModal={setShowDataSourceSelectionModal}

            activeDatasetId={activeDatasetId}

            datasetAnalysis={datasetAnalysis}

            selectedQCTasks={selectedQCTasks}

            setSelectedQCTasks={setSelectedQCTasks}

            onAutoQC={handleAutoQC}

            onStandardQC={handleStandardQC}

            onQCTaskToggle={handleQCTaskToggle}

            renderStepChat={renderStepChat}

            wantsToRemoveDuplicates={dupWantsToRemove}

            onWantsToRemoveDuplicatesChange={setDupWantsToRemove}

            isDuplicateRemovalComplete={dupIsComplete}

            onDuplicateRemovalComplete={async (result) => {
              setDupIsComplete(true);
              setDupRemovalResult(result);
              setShowEDAComparison(true);
              setShowDatasetOverview(true);
              
              // Fetch updated EDA after duplicate removal
              const datasetId = activeDatasetId || sessionStorage.getItem('dataset_id');
              if (datasetId) {
                try {
                  console.log('📊 Fetching updated EDA after duplicate removal for dataset:', datasetId);
                  const edaResponse = await fastApiService.getEDASnapshot(datasetId, 'entire');
                  console.log('📊 EDA Response received:', edaResponse);
                  
                  if (edaResponse.success && edaResponse.eda_snapshot) {
                    const updatedEDA = {
                      timestamp: edaResponse.eda_snapshot.timestamp,
                      totalRows: edaResponse.eda_snapshot.totalRows,
                      totalColumns: edaResponse.eda_snapshot.totalColumns,
                      numericStats: edaResponse.eda_snapshot.numericStats,
                      categoricalStats: edaResponse.eda_snapshot.categoricalStats,
                      dateStats: edaResponse.eda_snapshot.dateStats,
                      treatmentApplied: 'Duplicate Removal'
                    };
                    console.log('📊 Setting currentEDA with:', updatedEDA.totalRows, 'rows,', 
                                updatedEDA.numericStats?.length, 'numeric cols,',
                                updatedEDA.categoricalStats?.length, 'categorical cols');
                    setCurrentEDA(updatedEDA);
                    setEdaRefreshKey(prev => prev + 1);
                    triggerEdaComparisonView(); // Switch to Updated EDA sub-tab
                    console.log('✅ Updated EDA set after duplicate removal');
                  } else {
                    console.warn('⚠️ EDA response missing success or eda_snapshot:', edaResponse);
                  }
                } catch (error) {
                  console.error('Failed to fetch updated EDA after duplicate removal:', error);
                }
              } else {
                console.warn('⚠️ No datasetId available for EDA fetch');
              }
            }}

            isSkipped={dupIsSkipped}

            onSkip={() => setDupIsSkipped(true)}

            removalResult={dupRemovalResult}

            dupSelectedVariables={dupSelectedVariables}
            onDupSelectedVariablesChange={setDupSelectedVariables}
            dupIdentificationResult={dupIdentificationResult}
            onDupIdentificationResultChange={(v) => setDupIdentificationResult(v)}

            onOpenSidebar={() => setShowDatasetOverview(true)}

            onQcTemplatesChange={setQcTemplates}

          />

        );



      case 3:

        return (

          <Step3DataInsights

            selectedInsightSteps={selectedInsightSteps}

            setSelectedInsightSteps={setSelectedInsightSteps}

            onAutoDataInsights={handleAutoDataInsights}

            onStandardDataInsights={handleStandardDataInsights}

            onInsightStepToggle={handleInsightStepToggle}

            renderStepChat={renderStepChat}

            activeDatasetId={activeDatasetId}

            datasetAnalysis={datasetAnalysis}

            targetVariable={datasetConfig?.target_variable ?? null}

            autoInsightStepStatus={autoInsightStepStatus}

            insightsMode={insightsUiMode}

            onInsightsModeChange={handleInsightsUiModeChange}

          />

        );



      case 3.5:

        return (

          <Step3_5SegmentationAgentAnalysis

            datasetPreview={datasetPreview}
            problemType={datasetConfig?.dataset_structure_type || undefined}

            activeDatasetId={activeDatasetId ?? undefined}
            targetVariable={datasetConfig?.target_variable || undefined}

            segmentationMode={segmentationMode}
            setSegmentationMode={(mode) => { setSegmentationMode(mode); try { sessionStorage.setItem('segmentation_mode', mode); } catch {} }}

            availableColumns={currentDatasetColumns.length > 0 
              ? currentDatasetColumns 
              : (datasetAnalysis?.columns || [])
              .map(c => c.name)
              .filter(name => name !== datasetConfig?.target_variable)}

            columnMetadata={datasetAnalysis?.columns}

            selectedSegmentationVariables={selectedSegmentationVariables}

            setSelectedSegmentationVariables={(cols) => {
              setSelectedSegmentationVariables(cols);
              try { sessionStorage.setItem('segmentation_variables', JSON.stringify(cols)); } catch {}
            }}

            segmentationMethod={segmentationMethod}
            setSegmentationMethod={(m) => { setSegmentationMethod(m); try { sessionStorage.setItem('segmentation_method', m); } catch {} }}
            minSegmentSize={minSegmentSize}
            setMinSegmentSize={(size) => { setMinSegmentSize(size); try { sessionStorage.setItem('min_segment_size', size.toString()); } catch {} }}
            maxSegments={maxSegments}
            setMaxSegments={(count) => { setMaxSegments(count); try { sessionStorage.setItem('max_segments', count.toString()); } catch {} }}
            
            minSegmentSizeMode={minSegmentSizeMode}
            setMinSegmentSizeMode={setMinSegmentSizeMode}
            minSegmentSizePercentage={minSegmentSizePercentage}
            setMinSegmentSizePercentage={setMinSegmentSizePercentage}
            onRunSegmentation={async () => {
              if (!activeDatasetId) { alert('No dataset selected.'); return; }
              if (!datasetConfig?.target_variable) { alert('Target variable not set.'); return; }
              if (!selectedSegmentationVariables.length) { alert('Select at least one variable.'); return; }
              
              // Set loading state and give React time to render
              setIsRunningSegmentation(true);
              await new Promise(resolve => setTimeout(resolve, 50)); // Force UI update
              
              try {
                const res = await fastApiService.runSegmentation({
                  dataset_id: activeDatasetId,
                  variables: selectedSegmentationVariables,
                  method: segmentationMethod,
                  target_variable: datasetConfig?.target_variable || undefined,
                  // Use appropriate parameter based on mode
                  ...(minSegmentSizeMode === 'number' 
                    ? { min_samples_leaf: minSegmentSize }
                    : { min_segment_size_ratio: minSegmentSizePercentage / 100 }
                  ),
                  max_depth: 6, // Allow deeper tree initially
                  max_segments: maxSegments
                });
                // Debug: Log warning message
                if (res.warning) {
                  console.log('⚠️ Segmentation Warning:', res.warning);
                } else {
                  console.log('✅ No warning message in response');
                }
                setSegmentationResult(res);
                // Store segmentation result in sessionStorage for documentation
                try {
                  sessionStorage.setItem('segmentation_result', JSON.stringify(res));
                  console.log('✅ Segmentation result stored in sessionStorage');
                } catch (e) {
                  console.error('Failed to store segmentation result in sessionStorage:', e);
                }
                const msg = `Segmentation (${res.method.toUpperCase()}) created ${res.num_segments} segments.\nViability: min 2 segments=${res.viability?.minimum_two_segments ? 'yes' : 'no'}, size OK=${res.viability?.each_segment_meets_size ? 'yes' : 'no'}, interpretable=${res.viability?.rules_interpretable ? 'yes' : 'no'}.`;
                const aiMessage = { id: `ai-seg-${Date.now()}`, type: 'assistant' as const, content: msg, timestamp: new Date() };
                setChatMessages(prev => ({ ...prev, [3.5]: [...(prev[3.5] || []), aiMessage] }));
                setTimeout(() => { scrollToBottom(3.5); }, 100);
              } catch (e) {
                const msg = `Segmentation failed: ${e instanceof Error ? e.message : 'Unknown error'}`;
                const aiMessage = { id: `ai-seg-err-${Date.now()}`, type: 'assistant' as const, content: msg, timestamp: new Date() };
                setChatMessages(prev => ({ ...prev, [3.5]: [...(prev[3.5] || []), aiMessage] }));
              } finally {
                setIsRunningSegmentation(false);
              }
            }}

            isRunningSegmentation={isRunningSegmentation}

            onRunAutoSegmentation={async () => {
              if (!activeDatasetId) { alert('No dataset selected.'); return; }
              if (!datasetConfig?.target_variable) { alert('Target variable not set.'); return; }
              setIsRunningAutoSegmentation(true);
              try {
                // Call auto segmentation API - runs on entire dataset automatically
                const res = await fastApiService.runAutoSegmentation({
                  dataset_id: activeDatasetId,
                  method: segmentationMethod,
                  target_variable: datasetConfig?.target_variable || undefined,
                  // Use appropriate parameter based on mode
                  ...(minSegmentSizeMode === 'number' 
                    ? { min_samples_leaf: minSegmentSize }
                    : { min_segment_size_ratio: minSegmentSizePercentage / 100 }
                  ),
                  max_depth: 6, // Allow deeper tree initially
                  max_segments: maxSegments
                });
                // Debug: Log warning message
                if (res.warning) {
                  console.log('⚠️ Auto Segmentation Warning:', res.warning);
                } else {
                  console.log('✅ No warning message in auto segmentation response');
                }
                setSegmentationResult(res);
                // Store segmentation result in sessionStorage for documentation
                try {
                  sessionStorage.setItem('segmentation_result', JSON.stringify(res));
                  console.log('✅ Auto segmentation result stored in sessionStorage');
                } catch (e) {
                  console.error('Failed to store auto segmentation result in sessionStorage:', e);
                }
                const msg = `Auto Segmentation (${res.method.toUpperCase()}) completed successfully!\nSegments created: ${res.num_segments}\nViability: min 2 segments=${res.viability?.minimum_two_segments ? 'yes' : 'no'}, size OK=${res.viability?.each_segment_meets_size ? 'yes' : 'no'}, interpretable=${res.viability?.rules_interpretable ? 'yes' : 'no'}.\n\nNote: This segmentation was performed on the entire dataset automatically.`;
                const aiMessage = { id: `ai-auto-seg-${Date.now()}`, type: 'assistant' as const, content: msg, timestamp: new Date() };
                setChatMessages(prev => ({ ...prev, [3.5]: [...(prev[3.5] || []), aiMessage] }));
                setTimeout(() => { scrollToBottom(3.5); }, 100);
              } catch (e) {
                const msg = `Auto segmentation failed: ${e instanceof Error ? e.message : 'Unknown error'}`;
                const aiMessage = { id: `ai-auto-seg-err-${Date.now()}`, type: 'assistant' as const, content: msg, timestamp: new Date() };
                setChatMessages(prev => ({ ...prev, [3.5]: [...(prev[3.5] || []), aiMessage] }));
              } finally {
                setIsRunningAutoSegmentation(false);
              }
            }}
            isRunningAutoSegmentation={isRunningAutoSegmentation}

            segmentationResult={segmentationResult}

            onSegmentationResult={(result) => {
              if (result) {
                setSegmentationResult(result);
                try {
                  sessionStorage.setItem('segmentation_result', JSON.stringify(result));
                  console.log('✅ Unified segmentation result stored in sessionStorage');
                } catch (e) {
                  console.error('Failed to store segmentation result in sessionStorage:', e);
                }
                // Add chat message for the result
                const msg = result.validation 
                  ? `Segmentation completed: ${result.num_segments} segments created.\nRecommendation: ${result.validation.recommendation_category?.toUpperCase() || 'N/A'}\nTotal IV: ${displayTotalIv(result.validation.total_iv, result.segments)}`
                  : `Segmentation completed: ${result.num_segments} segments created.`;
                const aiMessage = { id: `ai-seg-${Date.now()}`, type: 'assistant' as const, content: msg, timestamp: new Date() };
                setChatMessages(prev => ({ ...prev, [3.5]: [...(prev[3.5] || []), aiMessage] }));
                setTimeout(() => { scrollToBottom(3.5); }, 100);
              }
            }}

            renderStepChat={renderStepChat}

          />

        );



      case 4:

        return (

          <Step4FeatureEngineering

            selectedFeatureSteps={selectedFeatureSteps}

            setSelectedFeatureSteps={setSelectedFeatureSteps}

            renderStepChat={renderStepChat}

            datasetId={sessionStorage.getItem('dataset_id') ?? undefined}
            
            targetVariable={datasetConfig?.target_variable}

            activeDatasetId={activeDatasetId}

            maxSegments={maxSegments}

            segmentationResult={segmentationResult}
          />

        );



      case 5:

        return (

          <Step5ModelEvaluation

            selectedSplitSteps={selectedSplitSteps}

            setSelectedSplitSteps={setSelectedSplitSteps}

            onAutoDataSplitting={handleAutoDataSplitting}

            onStandardDataSplitting={handleStandardDataSplitting}

            onSplitStepToggle={handleSplitStepToggle}

            renderStepChat={renderStepChat}

            activeDatasetId={activeDatasetId}

            datasetAnalysis={datasetAnalysis}

          />

        );



      case 4.5:

        return (

          <Step6_5ModelTrainingAgent

            renderStepChat={renderStepChat}
            activeDatasetId={activeDatasetId}
            segmentTrainingMode={segmentTrainingMode}
            segmentInfo={segmentInfo}
            onSegmentInfoUpdate={setSegmentInfo}
            targetVariable={datasetConfig?.target_variable}
            datasetAnalysis={datasetAnalysis}
            onMtaFlowGateChange={handleMtaFlowGateChange}

          />

        );



      case 8:

        return (

          <Step8AIExplainability

            selectedDeploymentSteps={selectedDeploymentSteps}

            setSelectedDeploymentSteps={setSelectedDeploymentSteps}

            onAutoModelDeployment={handleAutoModelDeployment}

            onStandardModelDeployment={handleStandardModelDeployment}

            onDeploymentStepToggle={handleDeploymentStepToggle}

            renderStepChat={renderStepChat}

            activeDatasetId={activeDatasetId}

            datasetAnalysis={datasetAnalysis}

          />

        );



      case 9:

        return (

          <Step9ModelDocumentation

            renderStepChat={renderStepChat}

          />

        );



      default:

        return null;

    }

  };



  // Show project selection if no project is selected
  if (showProjectSelection || !selectedProject) {
    return <ProjectSelection onProjectSelect={handleProjectSelect} />;
  }

  const handleClearDisplayedInsights = () => {
    setDisplayedInsightSteps([]);
    setInsightsGenerationSource(null);
    try {
      sessionStorage.removeItem('model_builder_displayed_insight_steps');
      sessionStorage.removeItem('model_builder_insights_source');
    } catch {}
  };

  return (

    <div className="relative h-full">

      <div 

        className="h-full overflow-y-auto p-6 space-y-8 transition-all duration-300"

        style={{ 

          paddingRight: (showDatasetOverview && currentStep < 4 ) ? `${sidebarWidth + 12}px` : '24px'

        }}

      >

        {/* Header */}

        <div>

          <div className="flex items-center justify-between">

            <div>

              <div className="flex items-center space-x-3">

                <button

                  onClick={handleBackToProjects}

                  className="flex items-center space-x-2 px-3 py-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"

                  title="Back to Projects"

                >

                  <BackIcon className="h-4 w-4" />

                  <span className="text-sm">Projects</span>

                </button>

                <div className="h-4 w-px bg-gray-300 dark:bg-gray-600"></div>

                <div>

                  <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Model Lab</h1>

                  <p className="text-gray-600 dark:text-gray-400 mt-1">

                    Project: <span className="font-medium text-gray-900 dark:text-gray-200">{selectedProject.name}</span>

                  </p>

                </div>

              </div>

            </div>

            {/* <div>

              <button

                className="px-4 py-2 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] transition-colors flex items-center space-x-2"

                title="Save Model Lab Progress"

              >

                <span>Save</span>

              </button>

            </div> */}

          </div>

          <p className="text-gray-600 dark:text-gray-400 mt-2">

            Build, train, and evaluate machine learning models in our advanced Model Lab.

          </p>

        </div>



        {/* Comprehensive Stepper */}

        <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6">

          <div className="mb-8">

            <div className="relative">

              {/* Progress Background Line */}

              <div className="absolute top-6 left-0 right-0 h-1 bg-gradient-to-r from-gray-200 via-gray-200 to-gray-200 dark:from-gray-700 dark:via-gray-700 dark:to-gray-700 rounded-full">

                <div 

                  className="h-full bg-gradient-to-r from-blue-500 via-blue-600 to-teal-500 rounded-full transition-all duration-700 ease-out"

                  style={{ width: `${((currentStep - 1) / (steps.length - 1)) * 100}%` }}

                ></div>

              </div>

              

              {/* Steps Container */}

              <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-9 gap-2 relative z-10 overflow-x-auto">

                {steps.map((step, index) => {

                  const StepIcon = stepIcons[step.id];
                  const step1NavLocked = !step1DatasetUploadSucceeded && step.id !== 1;
                  // Model Evaluation (5) and AI Explainability (8) stay gated on MTA completion.
                  // Model Documentation (9) is reachable once Objectives (step 1) succeeded.
                  const mtaEvalTabsBlocked =
                    Boolean(activeDatasetId) &&
                    !modelTrainingStepAllowsLeaving &&
                    [5, 8].includes(step.id);
                  const objectivesOverviewNavLocked =
                    currentStep === 1 &&
                    showDatasetOverview &&
                    datasetOverviewStep1PanelsBusy &&
                    step.id !== 1;
                  const stepNavLocked = step1NavLocked || mtaEvalTabsBlocked || objectivesOverviewNavLocked;

                  return (

                    <div
                      key={step.id}
                      className={`flex flex-col items-center group ${stepNavLocked ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}`}
                      title={
                        stepNavLocked
                          ? step1NavLocked
                            ? 'Complete dataset upload on Objectives before opening this step.'
                            : objectivesOverviewNavLocked
                              ? 'Wait for Overview, Quality, and Distributions to finish loading in the dataset panel.'
                              : 'Confirm variables and RFE, finish model training, then confirm the model screener before opening this step.'
                          : undefined
                      }
                      onClick={() => {
                        if (stepNavLocked) return;
                        setCurrentStep(step.id);
                      }}
                    >

                      {/* Step Circle */}

                      <div className={`w-10 h-10 rounded-full flex items-center justify-center border-3 transition-all duration-300 shadow-lg hover:scale-110 ${

                        currentStep > step.id

                          ? 'bg-gradient-to-br from-green-500 to-green-600 border-green-500 text-white shadow-green-200 dark:shadow-green-900/50'

                          : currentStep === step.id

                          ? 'bg-gradient-to-br from-blue-600 to-blue-700 border-blue-600 text-white shadow-blue-200 dark:shadow-blue-900/50 ring-4 ring-blue-100 dark:ring-blue-900'

                          : 'bg-white dark:bg-gray-800 border-gray-300 dark:border-gray-600 text-gray-500 dark:text-gray-400 hover:border-gray-400 dark:hover:border-gray-500 hover:shadow-md'

                      }`}>

                        {currentStep > step.id ? (

                          <CheckCircle className="h-5 w-5" />

                        ) : (

                          <StepIcon className="h-5 w-5" />

                        )}

                      </div>

                      

                      {/* Step Content */}

                      <div className="mt-2 text-center w-full px-1">

                        <p className={`text-xs font-semibold leading-tight transition-colors break-words ${

                          currentStep >= step.id ? 'text-gray-900 dark:text-gray-100' : 'text-gray-600 dark:text-gray-400'

                        }`}>

                          {step.title}

                        </p>

                      </div>

                    </div>

                  );

                })}

              </div>

            </div>

          </div>



          {/* Step Content */}

          {renderStepContent()}

          {/* Navigation */}

          <div className="flex justify-between mt-8">

            <button

              onClick={() => {
                // Handle previous step navigation with step 3.5 and 4.5
                if (currentStep === 4.5) {
                  setCurrentStep(4);
                } else if (currentStep === 4) {
                  setCurrentStep(3.5);
                } else if (currentStep === 3.5) {
                  setCurrentStep(3);
                } else {
                  setCurrentStep(Math.max(1, currentStep - 1));
                }
              }}

              disabled={currentStep === 1}

              className="flex items-center space-x-2 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50"

            >

              <ArrowLeft className="h-4 w-4" />

              <span>Previous</span>

            </button>

            

            <button

              onClick={(e) => {
                // Prevent any default behavior that might block navigation
                e.preventDefault();
                e.stopPropagation();

                if (currentStep === 4.5 && !modelTrainingStepAllowsLeaving) {
                  return;
                }

                if (currentStep === 1 && showDatasetOverview && datasetOverviewStep1PanelsBusy) {
                  return;
                }
                
                // Handle next step navigation with step 3.5 and 4.5
                if (currentStep === 3) {
                  setCurrentStep(3.5);
                } else if (currentStep === 3.5) {
                  setCurrentStep(4);
                } else if (currentStep === 4) {
                  setCurrentStep(4.5);
                } else if (currentStep === 4.5) {
                  setCurrentStep(5);
                } else if (currentStep === 5) {
                  setCurrentStep(8);
                } else {
                  setCurrentStep(Math.min(9, currentStep + 1));
                }
              }}

              disabled={
                currentStep === 9 ||
                (currentStep === 1 && !step1DatasetUploadSucceeded) ||
                (currentStep === 1 && showDatasetOverview && datasetOverviewStep1PanelsBusy) ||
                (currentStep === 4.5 && !modelTrainingStepAllowsLeaving)
              }

              title={
                currentStep === 1 && !step1DatasetUploadSucceeded
                  ? 'Upload your dataset successfully (Submit) before continuing.'
                  : currentStep === 1 && showDatasetOverview && datasetOverviewStep1PanelsBusy
                    ? 'Wait for Overview, Quality, and Distributions to finish loading in the dataset panel.'
                  : currentStep === 4.5 && !modelTrainingStepAllowsLeaving
                    ? 'Confirm variables and RFE, finish model training, then confirm the model screener before continuing.'
                    : undefined
              }

              className="flex items-center space-x-2 px-4 py-2 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-md hover:bg-blue-700 dark:hover:bg-[#333380] disabled:opacity-50"

            >

              <span>Next</span>

              <ArrowRight className="h-4 w-4" />

            </button>

          </div>

        </div>

      </div>



        {/* Dataset Overview Sidebar */}
        {currentStep < 4 && (
          <DatasetOverviewSidebar

            isVisible={showDatasetOverview}

            onClose={() => setShowDatasetOverview(false)}

            datasetId={activeDatasetId}

            datasetConfig={datasetConfig}

            datasetAnalysis={datasetAnalysis}

            onWidthChange={setSidebarWidth}

            onStep1PrimaryPanelsBusyChange={setDatasetOverviewStep1PanelsBusy}

            currentStep={currentStep}

            restrictedMode={currentStep === 3 ? 'insights-only' : 'all'}

            selectedInsightSteps={displayedInsightSteps}

            insightsGenerationSource={insightsGenerationSource}

            onClearInsights={handleClearDisplayedInsights}

            problemType={problemType}

            segmentationResult={segmentationResult}

            originalEDA={originalEDA}

            currentEDA={currentEDA}

            showEDAComparison={showEDAComparison && currentStep === 2}

            edaRefreshKey={edaRefreshKey}

            forceEdaComparisonView={forceEdaComparisonView}

            onSegmentationResultChange={(result) => {
              setSegmentationResult(result);
              try {
                sessionStorage.setItem('segmentation_result', JSON.stringify(result));
              } catch {
                /* ignore quota / private mode */
              }
            }}
          />
        )}

      {/* Expanded AI Assistant Modal */}
      {isAIAssistantExpanded && expandedStepNumber !== null && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
          onClick={() => {
            setIsAIAssistantExpanded(false);
            setExpandedStepNumber(null);
          }}
        >
          <div 
            className="bg-white dark:bg-[#0b1020] rounded-xl border border-gray-200 dark:border-gray-700 shadow-2xl w-[80%] h-[80%] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                AI Assistant - Step {expandedStepNumber}
              </h2>
              <button
                type="button"
                onClick={() => {
                  setIsAIAssistantExpanded(false);
                  setExpandedStepNumber(null);
                }}
                className="flex items-center space-x-2 px-3 py-1 text-sm bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 dark:text-gray-300 rounded-md transition-colors"
                title="Close Assistant"
              >
                <X className="h-4 w-4" />
                <span>Close</span>
              </button>
            </div>

            {/* Modal Content */}
            <div className="flex-1 p-6 overflow-hidden">
              {/* Chat Messages */}
              <div className="h-full flex flex-col">
                <div 
                  className="flex-1 overflow-y-auto mb-4 border border-gray-200 dark:border-gray-700 rounded-lg p-4 bg-gray-50 dark:bg-slate-900 scroll-smooth"
                  ref={(el) => { 
                    if (el && expandedStepNumber !== null && typeof expandedStepNumber === 'number') {
                      chatContainerRefs.current[expandedStepNumber] = el;
                    }
                  }}
                >
                  {(() => {
                    // Defensive check for expandedStepNumber
                    if (expandedStepNumber === null || typeof expandedStepNumber !== 'number') {
                      return (
                        <div className="text-center text-gray-500 dark:text-gray-400 py-8">
                          <Brain className="h-12 w-12 mx-auto mb-4 text-gray-400 dark:text-gray-500" />
                          <p className="text-lg">Invalid step number</p>
                        </div>
                      );
                    }
                    
                    const stepMessages = chatMessages[expandedStepNumber] || [];
                    
                    if (stepMessages.length === 0) {
                      return (
                        <div className="text-center text-gray-500 dark:text-gray-400 py-8">
                          <Brain className="h-12 w-12 mx-auto mb-4 text-gray-400 dark:text-gray-500" />
                          <p className="text-lg">Ask me anything about this step!</p>
                          <p className="text-sm text-gray-400 dark:text-gray-500 mt-2">Start a conversation to get assistance</p>
                        </div>
                      );
                    }
                    
                    return (
                      <div className="space-y-4">
                        {stepMessages.map((message) => {
                          // Defensive check for message structure
                          if (!message || !message.id || message.content === undefined || message.content === null) {
                            console.warn('Invalid message structure:', message);
                            return null;
                          }
                          
                          return (
                            <div
                              key={message.id}
                              className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
                            >
                              <div className={`px-4 py-3 rounded-lg w-3/4 ${
                                message.type === 'user' 
                                  ? 'bg-blue-600 text-white' 
                                  : 'bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700'
                              }`}>
                                {/* Message content rendering with full JSON parsing logic */}
                                {message.type === 'assistant' ? (
                                  <div className="text-sm dark:text-gray-200">
                                    {(() => {
                                      try {
                                        // Defensive JSON parsing - check if content is a string
                                        if (typeof message.content !== 'string' || !message.content.trim()) {
                                          return <ReactMarkdown>{String(message.content || '')}</ReactMarkdown>;
                                        }
                                        
                                        const parsed = JSON.parse(message.content);

                                    // ============================================================
                                    // AUTO QC TREATMENT EXECUTION PROGRESS HANDLER (EXPANDED VIEW)
                                    // ============================================================
                                    if (parsed.isExecutingTreatment) {
                                      const statusColors = {
                                        executing: 'bg-blue-50 dark:bg-blue-900/30 border-blue-200 dark:border-blue-700',
                                        success: 'bg-green-50 dark:bg-green-900/30 border-green-200 dark:border-green-700',
                                        error: 'bg-red-50 dark:bg-red-900/30 border-red-200 dark:border-red-700'
                                      };
                                      const statusIcons = {
                                        executing: (
                                          <svg className="w-5 h-5 text-blue-500 animate-spin" fill="none" viewBox="0 0 24 24">
                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                          </svg>
                                        ),
                                        success: (
                                          <svg className="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                          </svg>
                                        ),
                                        error: (
                                          <svg className="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                          </svg>
                                        )
                                      };
                                      const status = parsed.status as 'executing' | 'success' | 'error';
                                      
                                      return (
                                        <div className={`rounded-lg border p-3 ${statusColors[status]}`}>
                                          <div className="flex items-center space-x-3">
                                            <div className="flex-shrink-0">
                                              {statusIcons[status]}
                                            </div>
                                            <div className="flex-1 min-w-0">
                                              <div className="flex items-center justify-between">
                                                <p className={`text-sm font-medium ${status === 'executing' ? 'text-blue-800 dark:text-blue-300' : status === 'success' ? 'text-green-800 dark:text-green-300' : 'text-red-800 dark:text-red-300'}`}>
                                                  {status === 'executing' ? `Executing ${parsed.treatmentLabel}...` : 
                                                   status === 'success' ? `${parsed.treatmentLabel} Applied` :
                                                   `${parsed.treatmentLabel} Failed`}
                                                </p>
                                                <span className="text-xs text-gray-500 dark:text-gray-400">
                                                  {parsed.progress}
                                                </span>
                                              </div>
                                              {parsed.response && status === 'success' && (
                                                <p className="mt-1 text-xs text-green-600 dark:text-green-400 truncate">
                                                  {parsed.response}
                                                </p>
                                              )}
                                              {parsed.error && status === 'error' && (
                                                <p className="mt-1 text-xs text-red-600 dark:text-red-400 truncate">
                                                  {parsed.error}
                                                </p>
                                              )}
                                            </div>
                                          </div>
                                        </div>
                                      );
                                    }

                                    // ============================================================
                                    // AUTO QC COMPLETION MESSAGE HANDLER (EXPANDED VIEW)
                                    // ============================================================
                                    if (parsed.isAutoQCComplete) {
                                      const isSuccess = parsed.executedCount > 0;
                                      return (
                                        <div className="space-y-3">
                                          <div className={`${isSuccess ? 'bg-green-50 dark:bg-green-900/30 border-green-200 dark:border-green-700' : 'bg-yellow-50 dark:bg-yellow-900/30 border-yellow-200 dark:border-yellow-700'} border rounded-lg p-4`}>
                                            <div className="flex items-start space-x-3">
                                              <div className="flex-shrink-0">
                                                {isSuccess ? (
                                                  <svg className="w-6 h-6 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                                  </svg>
                                                ) : (
                                                  <svg className="w-6 h-6 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                                  </svg>
                                                )}
                                              </div>
                                              <div className="flex-1">
                                                <h3 className={`text-sm font-semibold ${isSuccess ? 'text-green-800 dark:text-green-300' : 'text-yellow-800 dark:text-yellow-300'}`}>
                                                  {isSuccess ? 'All Treatments Applied Successfully!' : 'No Treatments Executed'}
                                                </h3>
                                                {isSuccess ? (
                                                  <>
                                                    <p className="mt-1 text-sm text-green-700 dark:text-green-400">
                                                      <strong>{parsed.executedCount}</strong> out of <strong>{parsed.totalTreatments}</strong> treatment{parsed.totalTreatments > 1 ? 's' : ''} executed successfully.
                                                    </p>
                                                    {parsed.summary && Array.isArray(parsed.summary) && (
                                                      <div className="mt-2 text-xs text-green-600 dark:text-green-400 space-y-0.5">
                                                        {parsed.summary.map((item: string, idx: number) => (
                                                          <div key={idx}>{item}</div>
                                                        ))}
                                                      </div>
                                                    )}
                                                  </>
                                                ) : (
                                                  <p className="mt-1 text-sm text-yellow-700 dark:text-yellow-400">
                                                    All treatments were skipped. Please upload templates for Invalid Values and Special Values to apply those treatments.
                                                  </p>
                                                )}
                                                {isSuccess && (
                                                  <button
                                                    onClick={() => {
                                                      setShowDatasetOverview(true);
                                                      setShowEDAComparison(true);
                                                      triggerEdaComparisonView(); // Open Updated EDA sub-tab
                                                    }}
                                                    className="mt-2 inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-md bg-green-100 dark:bg-green-800 text-green-800 dark:text-green-200 hover:bg-green-200 dark:hover:bg-green-700 transition-colors"
                                                  >
                                                    View Updated EDA
                                                  </button>
                                                )}
                                              </div>
                                            </div>
                                          </div>
                                        </div>
                                      );
                                    }

                                    // ============================================================
                                    // DATA QUALITY TREATMENT TABLE HANDLER (EXPANDED VIEW)
                                    // ============================================================
                                    if (parsed.treatment_type && ['invalid_values', 'special_values', 'outliers', 'missing_values'].includes(parsed.treatment_type)) {
                                      console.log('📊 [Expanded] Detected treatment_type response:', parsed.treatment_type);
                                      return (
                                        <div className="space-y-4">
                                          {/* Response text - only show when NOT skipped */}
                                          {parsed.response && !parsed.skipped && (
                                            <div className="text-sm text-gray-700 dark:text-gray-300 bg-blue-50 dark:bg-blue-900/20 p-3 rounded-lg border border-blue-200 dark:border-blue-700">
                                              <ReactMarkdown>{parsed.response}</ReactMarkdown>
                                            </div>
                                          )}
                                          
                                          {/* Treatment Table */}
                                          <DataQualityTreatmentTable
                                            treatmentType={parsed.treatment_type}
                                            qcMode={parsed.qc_mode || 'manual'}
                                            tableData={parsed.table_data}
                                            skipped={parsed.skipped}
                                            skipReason={parsed.response}
                                            code={parsed.code}
                                            specialMessages={parsed.special_messages}
                                            onApplyTreatment={(latestCode) => {
                                              const sourceCode = latestCode || parsed.code;
                                              if (sourceCode && sourceCode.trim() !== '# No code to display') {
                                                // For missing_values in manual mode, append missing_flag code if user selected it
                                                let codeToExecute = sourceCode;
                                                if (parsed.treatment_type === 'missing_values' && addMissingFlag) {
                                                  codeToExecute = sourceCode + "\n\n# Add missing_flag column (1 if any value in row is missing, 0 otherwise)\ndf['missing_flag'] = df.isna().any(axis=1).astype(int)";
                                                }
                                                
                                                // Use step-by-step handler if in Manual QC step-by-step mode
                                                if (qcStepByStepMode && (parsed.qc_mode || 'manual') === 'manual') {
                                                  handleQCApplyTreatment(parsed.treatment_type, codeToExecute);
                                                } else {
                                                  executeCode(generateCodeId(message.id, sourceCode), codeToExecute);
                                                }
                                              }
                                            }}
                                            onSkipTreatment={() => {
                                              // Use step-by-step handler if in Manual QC step-by-step mode
                                              if (qcStepByStepMode && (parsed.qc_mode || 'manual') === 'manual') {
                                                handleQCSkipTreatment(parsed.treatment_type);
                                              } else {
                                                console.log(`Skipped ${parsed.treatment_type} treatment`);
                                              }
                                            }}
                                            onRegenerateCode={({ treatmentType, selections }) =>
                                              handleQCRegenerateCode(treatmentType, selections)
                                            }
                                            isApplying={executingCodeId === generateCodeId(message.id, parsed.code) || qcIsApplyingTreatment}
                                            showMissingFlagOption={parsed.show_missing_flag_option}
                                            addMissingFlag={addMissingFlag}
                                            onMissingFlagChange={setAddMissingFlag}
                                            treatmentStatus={qcTreatmentStatuses[parsed.treatment_type]}
                                            stepInfo={qcStepByStepMode && qcTreatmentStatuses[parsed.treatment_type] === 'active' ? {
                                              currentStep: qcCurrentStepIndex + 1,
                                              totalSteps: qcTreatmentSequence.length
                                            } : undefined}
                                            onViewUpdatedEDA={() => {
                                              setShowDatasetOverview(true);
                                              setShowEDAComparison(true);
                                              triggerEdaComparisonView();
                                            }}
                                          />
                                          
                                          {/* Suggestions */}
                                          {parsed.suggestion && Array.isArray(parsed.suggestion) && parsed.suggestion.length > 0 && (
                                            <div className="mt-3">
                                              <div className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">💡 Suggestions:</div>
                                              <ul className="list-disc list-inside text-xs text-gray-500 dark:text-gray-400 space-y-0.5">
                                                {parsed.suggestion.map((s: string, i: number) => (
                                                  <li key={i}>{s}</li>
                                                ))}
                                              </ul>
                                            </div>
                                          )}
                                        </div>
                                      );
                                    }

                                    // ============================================================
                                    // DATA QUALITY COMBINED RESPONSE HANDLER (EXPANDED VIEW)
                                    // Handles the new response format with multiple treatment_messages
                                    // The response field may contain a JSON string that needs to be parsed
                                    // ============================================================
                                    
                                    // Try to detect data_quality response - could be direct or nested in response field
                                    let dataQualityDataExpanded: any = null;
                                    if (parsed.role === 'data_quality' && parsed.treatment_messages) {
                                      dataQualityDataExpanded = parsed;
                                    } else if (parsed.response && typeof parsed.response === 'string') {
                                      try {
                                        const nestedParsedExp = JSON.parse(parsed.response);
                                        if (nestedParsedExp.role === 'data_quality' && nestedParsedExp.treatment_messages) {
                                          dataQualityDataExpanded = nestedParsedExp;
                                        }
                                      } catch (e) {
                                        // Not a nested JSON, continue
                                      }
                                    }
                                    
                                    if (dataQualityDataExpanded && dataQualityDataExpanded.treatment_messages && Array.isArray(dataQualityDataExpanded.treatment_messages)) {
                                      console.log('📊 [Expanded] Detected data_quality response with treatment_messages:', dataQualityDataExpanded.treatment_messages.length);
                                      return (
                                        <div className="space-y-6">
                                          {/* Render each treatment message as a separate table */}
                                          {dataQualityDataExpanded.treatment_messages.map((treatmentMsg: any, idx: number) => (
                                            <div key={idx} className="border-b border-gray-200 dark:border-gray-700 pb-4 last:border-b-0">
                                              {/* Response text for this treatment - only show if NOT skipped (skipped shows yellow warning instead) */}
                                              {treatmentMsg.response && !treatmentMsg.skipped && (
                                                <div className="text-sm text-gray-700 dark:text-gray-300 bg-blue-50 dark:bg-blue-900/20 p-3 rounded-lg border border-blue-200 dark:border-blue-700 mb-3">
                                                  <ReactMarkdown>{treatmentMsg.response}</ReactMarkdown>
                                                </div>
                                              )}
                                              
                                              {/* Treatment Table */}
                                              <DataQualityTreatmentTable
                                                treatmentType={treatmentMsg.treatment_type}
                                                qcMode={treatmentMsg.qc_mode || dataQualityDataExpanded.qc_mode || 'manual'}
                                                tableData={treatmentMsg.table_data}
                                                skipped={treatmentMsg.skipped}
                                                skipReason={treatmentMsg.response}
                                                code={treatmentMsg.code}
                                                specialMessages={treatmentMsg.special_messages}
                                                onApplyTreatment={(latestCode) => {
                                                  const sourceCode = latestCode || treatmentMsg.code;
                                                  if (sourceCode && sourceCode.trim() !== '# No code to display') {
                                                    // For missing_values in manual mode, append missing_flag code if user selected it
                                                    let codeToExecute = sourceCode;
                                                    if (treatmentMsg.treatment_type === 'missing_values' && addMissingFlag) {
                                                      codeToExecute = sourceCode + "\n\n# Add missing_flag column (1 if any value in row is missing, 0 otherwise)\ndf['missing_flag'] = df.isna().any(axis=1).astype(int)";
                                                    }
                                                    
                                                    // Use step-by-step handler if in Manual QC step-by-step mode
                                                    const effectiveQcModeExp = treatmentMsg.qc_mode || dataQualityDataExpanded.qc_mode || 'manual';
                                                    if (qcStepByStepMode && effectiveQcModeExp === 'manual') {
                                                      handleQCApplyTreatment(treatmentMsg.treatment_type, codeToExecute);
                                                    } else {
                                                      executeCode(generateCodeId(message.id + '_' + idx, sourceCode), codeToExecute);
                                                    }
                                                  }
                                                }}
                                                onSkipTreatment={() => {
                                                  // Use step-by-step handler if in Manual QC step-by-step mode
                                                  const effectiveQcModeExp = treatmentMsg.qc_mode || dataQualityDataExpanded.qc_mode || 'manual';
                                                  if (qcStepByStepMode && effectiveQcModeExp === 'manual') {
                                                    handleQCSkipTreatment(treatmentMsg.treatment_type);
                                                  } else {
                                                    console.log(`Skipped ${treatmentMsg.treatment_type} treatment`);
                                                  }
                                                }}
                                                onRegenerateCode={({ treatmentType, selections }) =>
                                                  handleQCRegenerateCode(treatmentType, selections)
                                                }
                                                isApplying={executingCodeId === generateCodeId(message.id + '_' + idx, treatmentMsg.code) || qcIsApplyingTreatment}
                                                showMissingFlagOption={treatmentMsg.show_missing_flag_option}
                                                addMissingFlag={addMissingFlag}
                                                onMissingFlagChange={setAddMissingFlag}
                                                treatmentStatus={qcTreatmentStatuses[treatmentMsg.treatment_type]}
                                                stepInfo={qcStepByStepMode && qcTreatmentStatuses[treatmentMsg.treatment_type] === 'active' ? {
                                                  currentStep: qcCurrentStepIndex + 1,
                                                  totalSteps: qcTreatmentSequence.length
                                                } : undefined}
                                                onViewUpdatedEDA={() => {
                                                  setShowDatasetOverview(true);
                                                  setShowEDAComparison(true);
                                                  triggerEdaComparisonView();
                                                }}
                                              />
                                            </div>
                                          ))}
                                          
                                          {/* Summary section if available */}
                                          {dataQualityDataExpanded.summary && (
                                            <div className="mt-4 p-4 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-700">
                                              <h4 className="font-semibold text-green-800 dark:text-green-300 mb-2">Data Quality Treatment Summary</h4>
                                              {dataQualityDataExpanded.summary.response && (
                                                <div className="text-sm text-gray-700 dark:text-gray-300">
                                                  <ReactMarkdown>{dataQualityDataExpanded.summary.response}</ReactMarkdown>
                                                </div>
                                              )}
                                            </div>
                                          )}
                                        </div>
                                      );
                                    }

                                    // If this is a code execution response, render Column Stats + Download CSV (like minimized view)
                                    if (parsed && typeof parsed.code === 'string') {
                                      const codeId = generateCodeId(message.id, parsed.code);
                                      const exec = executionResults[codeId];
                                      // Only render execution results if we have tracked results for this code snippet
                                      if (exec) return (
                                        <div className="mt-3 space-y-3">
                                          {/* Keep code visible even after execution */}
                                          {parsed.code && 
                                           parsed.code !== "# No code to display" && 
                                           parsed.code !== "No Code to display" &&
                                           parsed.code.trim() !== "# Plan generated successfully" &&
                                           parsed.code.trim() !== "Plan generated successfully" &&
                                           parsed.code.trim().length > 0 && (
                                            <div>
                                              <div className="text-sm font-medium text-green-700 mb-2">📝 Code</div>
                                              <div className="bg-gray-900 text-green-400 p-3 rounded text-sm font-mono overflow-x-auto">
                                                <pre>{parsed.code}</pre>
                                              </div>
                                            </div>
                                          )}

                                          <div className="text-sm font-medium text-blue-700">🚀 Execution Results</div>
                                          {exec?.isLoading ? (
                                            <div className="text-sm text-gray-600">Executing code...</div>
                                          ) : exec?.error ? (
                                            <div className="text-sm text-red-600 bg-red-50 p-2 rounded">Error: {exec.error}</div>
                                          ) : (
                                            <div className="space-y-3">
                                              {/* Response output hidden */}
                                              {exec?.columns_info && (
                                                <div>
                                                  <div className="flex justify-between items-center mb-2">
                                                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300">📊 Column Stats</div>
                                                    <div className="flex items-center gap-2">
                                                      <button
                                                        onClick={downloadColumnStats}
                                                        disabled={!exec?.columns_info || exec.columns_info.length === 0}
                                                        className="px-3 py-1 bg-green-600 text-white text-xs rounded hover:bg-green-700 transition-colors flex items-center space-x-1 disabled:opacity-50 disabled:cursor-not-allowed"
                                                        title="Download Column Stats table as CSV"
                                                      >
                                                        <Download className="w-3 h-3" />
                                                        <span>Download Stats Table</span>
                                                      </button>
                                                      <button
                                                        onClick={handleCompareChanges}
                                                        disabled={isLoadingComparison}
                                                        className="px-3 py-1 bg-purple-600 text-white text-xs rounded hover:bg-purple-700 transition-colors flex items-center space-x-1 disabled:opacity-50"
                                                        title="Compare original vs processed statistics"
                                                      >
                                                        {isLoadingComparison ? (
                                                          <>
                                                            <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                                                            <span>Loading...</span>
                                                          </>
                                                        ) : (
                                                          <>
                                                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                                                            </svg>
                                                            <span>Compare Changes</span>
                                                          </>
                                                        )}
                                                      </button>
                                                    </div>
                                                  </div>
                                                  <div className="overflow-x-auto">
                                                    <table className="min-w-full text-xs border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white">
                                                      <thead>
                                                        <tr className="bg-gray-100 dark:bg-gray-800">
                                                          <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">Column</th>
                                                          <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">Type</th>
                                                          <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">Missing</th>
                                                          <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">Unique</th>
                                                          <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">Mean</th>
                                                          <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">Median</th>
                                                          <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">Mode</th>
                                                          <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">Std</th>
                                                          <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">Var</th>
                                                          <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">Min</th>
                                                          <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">p5%</th>
                                                          <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">p25%</th>
                                                          <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">p50%</th>
                                                          <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">p75%</th>
                                                          <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">p95%</th>
                                                          <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">p99%</th>
                                                          <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">Max</th>
                                                        </tr>
                                                      </thead>
                                                      <tbody>
                                                        {exec.columns_info.map((col: any, idx: number) => {
                                                          // Use improved column_type from backend API (with smart classification logic)
                                                          const columnType = col.column_type || (['int64', 'float64', 'int32', 'float32'].includes(col.data_type) ? 'Numerical' : 'Categorical');
                                                          
                                                          // Find the original column info for comparison
                                                        const colName = col.column_name || col.name;
                                                        const baselineColumns = executionBaselines[generateCodeId(message.id, parsed.code)] || originalColumnInfo;
                                                        const originalCol = baselineColumns?.find(
                                                          (oc: any) => (oc.column_name || oc.name) === colName
                                                        );
                                                          
                                                          // Helper to format value, using original if current is null
                                                          const formatValue = (currentVal: any, originalVal: any, isNumeric: boolean = true) => {
                                                            const val = (currentVal !== null && currentVal !== undefined) ? currentVal : originalVal;
                                                            if (val === null || val === undefined) return '';
                                                            if (typeof val === 'number' && isNumeric) return val.toFixed(2);
                                                            return String(val);
                                                          };
                                                          
                                                          // Helper to check if value changed and get appropriate cell class
                                                          const getCellClass = (currentValue: any, originalValue: any, isNumeric: boolean = true) => {
                                                            let isDifferent = false;
                                                            if (originalCol) {
                                                              if (
                                                                (currentValue === null || currentValue === undefined) &&
                                                                (originalValue === null || originalValue === undefined)
                                                              ) {
                                                                isDifferent = false;
                                                              } else if (
                                                                currentValue === null || currentValue === undefined ||
                                                                originalValue === null || originalValue === undefined
                                                              ) {
                                                                isDifferent = true;
                                                              } else if (typeof currentValue === 'number' && typeof originalValue === 'number' && isNumeric) {
                                                                isDifferent = Math.abs(currentValue - originalValue) > 1e-9;
                                                              } else {
                                                                isDifferent = String(currentValue) !== String(originalValue);
                                                              }
                                                            }
                                                            return `px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white ${isDifferent ? 'bg-yellow-100 text-amber-800 font-medium dark:bg-yellow-900/30 dark:text-white' : ''}`;
                                                          };
                                                          
                                                          return (
                                                          <tr key={idx} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                                                            <td className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white font-medium">{col.column_name}</td>
                                                            <td className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white" title={`pandas dtype: ${col.data_type}`}>
                                                              {columnType}
                                                            </td>
                                                            <td className={getCellClass(col.missing_count, originalCol?.missing_count, false)}>{formatValue(col.missing_count, originalCol?.missing_count, false)}</td>
                                                            <td className={getCellClass(col.unique_count, originalCol?.unique_count, false)}>{formatValue(col.unique_count, originalCol?.unique_count, false)}</td>
                                                            <td className={getCellClass(col.mean, originalCol?.mean)}>{formatValue(col.mean, originalCol?.mean)}</td>
                                                            <td className={getCellClass(col.median, originalCol?.median)}>{formatValue(col.median, originalCol?.median)}</td>
                                                            <td className={`${getCellClass(col.mode, originalCol?.mode, false)} max-w-[150px] truncate`} title={formatValue(col.mode, originalCol?.mode, false)}>
                                                              {formatValue(col.mode, originalCol?.mode, false)}
                                                            </td>
                                                            <td className={getCellClass(col.standard_deviation, originalCol?.standard_deviation)}>{formatValue(col.standard_deviation, originalCol?.standard_deviation)}</td>
                                                            <td className={getCellClass(col.variance, originalCol?.variance)}>{formatValue(col.variance, originalCol?.variance)}</td>
                                                            <td className={getCellClass(col.min_value, originalCol?.min_value)}>{formatValue(col.min_value, originalCol?.min_value)}</td>
                                                            <td className={getCellClass(col.percentile_5, originalCol?.percentile_5)}>{formatValue(col.percentile_5, originalCol?.percentile_5)}</td>
                                                            <td className={getCellClass(col.percentile_25, originalCol?.percentile_25)}>{formatValue(col.percentile_25, originalCol?.percentile_25)}</td>
                                                            <td className={getCellClass(col.percentile_50, originalCol?.percentile_50)}>{formatValue(col.percentile_50, originalCol?.percentile_50)}</td>
                                                            <td className={getCellClass(col.percentile_75, originalCol?.percentile_75)}>{formatValue(col.percentile_75, originalCol?.percentile_75)}</td>
                                                            <td className={getCellClass(col.percentile_95, originalCol?.percentile_95)}>{formatValue(col.percentile_95, originalCol?.percentile_95)}</td>
                                                            <td className={getCellClass(col.percentile_99, originalCol?.percentile_99)}>{formatValue(col.percentile_99, originalCol?.percentile_99)}</td>
                                                            <td className={getCellClass(col.max_value, originalCol?.max_value)}>{formatValue(col.max_value, originalCol?.max_value)}</td>
                                                          </tr>
                                                          );
                                                        })}
                                                      </tbody>
                                                    </table>
                                                  </div>
                                                </div>
                                              )}
                                            </div>
                                          )}
                                        </div>
                                      );
                                    }

                                    // Check if this is a planner response with role
                                    if (
                                      parsed.role === "plan_agent" ||
                                      parsed.role === "data_insight" ||
                                      message.content.includes('\"role\":\"plan_agent\"') ||
                                      message.content.includes('"role":"plan_agent"') ||
                                      message.content.includes('"role": "plan_agent"') ||
                                      message.content.includes('\"role\":\"data_insight\"') ||
                                      message.content.includes('"role":"data_insight"') ||
                                      message.content.includes('"role": "data_insight"')
                                    ) {
                                      let planData;
                                      try {
                                        planData = typeof parsed.response === 'string' ? JSON.parse(parsed.response) : 
                                                  parsed.response || parsed.plan || parsed;
                                      } catch {
                                        planData = parsed;
                                      }
                                      
                                      // Render Data Insights tables when available in expanded view
                                      if (parsed.role === 'data_insight' && planData && typeof planData === 'object') {
                                        const { insightPayload, tablesMap, dataMeta } = normalizePlanInsightPayload(planData);
                                        const ivContext = getIvContextFromNormalizedPayload(insightPayload, tablesMap, dataMeta);
                                        const llmBivar: string[] = Array.isArray(dataMeta?.bivariate_insight) ? dataMeta.bivariate_insight : (Array.isArray(dataMeta?.llm_bivariate_insight) ? dataMeta.llm_bivariate_insight : []);
                                        const llmCorr: string[] = Array.isArray(dataMeta?.correlation_insight) ? dataMeta.correlation_insight : (Array.isArray(dataMeta?.llm_correlation_insight) ? dataMeta.llm_correlation_insight : []);
                                        const llmVif: string[] = Array.isArray(dataMeta?.vif_insight) ? dataMeta.vif_insight : (Array.isArray(dataMeta?.llm_vif_insight) ? dataMeta.llm_vif_insight : []);
                                        const llmIv = ivContext.ivInsights;
                                        const llmCorrMatrix: string[] = Array.isArray(dataMeta?.correlation_matrix_insight)
                                          ? dataMeta.correlation_matrix_insight.map((item: any) =>
                                              typeof item === 'string' ? item :
                                                typeof item === 'object' && item.pattern ? item.pattern : JSON.stringify(item)
                                            )
                                          : (Array.isArray(dataMeta?.llm_correlation_matrix_insight)
                                            ? dataMeta.llm_correlation_matrix_insight.map((item: any) =>
                                                typeof item === 'string' ? item :
                                                  typeof item === 'object' && item.pattern ? item.pattern : JSON.stringify(item)
                                              )
                                            : []);
                                        const llmCorrRatio: string[] = Array.isArray(dataMeta?.correlation_ratio_insight)
                                          ? dataMeta.correlation_ratio_insight
                                          : Array.isArray(dataMeta?.llm_correlation_ratio_insight)
                                            ? dataMeta.llm_correlation_ratio_insight
                                            : [];
                                        const ivSummaryTable = Array.isArray(tablesMap?.iv_analysis_summary)
                                          ? tablesMap.iv_analysis_summary[0]
                                          : null;
                                        const corrHighTable = Array.isArray(tablesMap?.correlation_matrix_high)
                                          ? tablesMap.correlation_matrix_high[0]
                                          : null;
                                        const corrSummaryTable = Array.isArray(tablesMap?.correlation_matrix_summary)
                                          ? tablesMap.correlation_matrix_summary[0]
                                          : null;

                                        if (
                                          llmBivar.length > 0 ||
                                          llmCorr.length > 0 ||
                                          llmVif.length > 0 ||
                                          llmIv.length > 0 ||
                                          llmCorrMatrix.length > 0 ||
                                          llmCorrRatio.length > 0
                                        ) {
                                          return (
                                            <div className="space-y-6">
                                              <div className="flex items-center justify-between">
                                                <div className="text-sm font-medium text-blue-700 dark:text-blue-400">📊 Data Insights</div>
                                                <div className="flex items-center gap-2">
                                                  <button
                                                    onClick={() => downloadInsightsAsXLSX(insightPayload, expandedStepNumber)}
                                                    className="flex items-center space-x-1 px-2 py-1 text-xs bg-green-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded hover:bg-green-700 dark:hover:bg-[#333380] transition-colors"
                                                    title="Download Full Insight Report"
                                                  >
                                                    <Download className="h-3 w-3" />
                                                    <span>Download Full Insight Report</span>
                                                  </button>
                                                  {(llmIv.length > 0 || ivSummaryTable) && (
                                                    <button
                                                      onClick={() => downloadDetailedIvReport(insightPayload, expandedStepNumber)}
                                                      className="flex items-center space-x-1 px-2 py-1 text-xs bg-purple-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded hover:bg-purple-700 dark:hover:bg-[#333380] transition-colors"
                                                      title="Download Detailed IV Report"
                                                    >
                                                      <Download className="h-3 w-3" />
                                                      <span>Download Detailed IV Report</span>
                                                    </button>
                                                  )}
                                                </div>
                                              </div>
                                              {llmBivar.length > 0 && (
                                                <div className="space-y-2">
                                                  <div className="text-xs font-semibold text-gray-800 dark:text-gray-200">Bivariate Insights</div>
                                                  <ul className="list-disc list-inside text-xs text-gray-700 dark:text-gray-300">
                                                    {llmBivar.map((ins, i) => (<li key={i}>{ins}</li>))}
                                                  </ul>
                                                </div>
                                              )}
                                              {llmCorr.length > 0 && (
                                                <div className="space-y-2">
                                                  <div className="text-xs font-semibold text-gray-800 dark:text-gray-200">Correlation Insights</div>
                                                  <ul className="list-disc list-inside text-xs text-gray-700 dark:text-gray-300">
                                                    {llmCorr.map((ins, i) => (<li key={i}>{ins}</li>))}
                                                  </ul>
                                                </div>
                                              )}
                                              {llmVif.length > 0 && (
                                                <div className="space-y-2">
                                                  <div className="text-xs font-semibold text-gray-800 dark:text-gray-200">VIF Insights</div>
                                                  <ul className="list-disc list-inside text-xs text-gray-700 dark:text-gray-300">
                                                    {llmVif.map((ins, i) => (<li key={i}>{ins}</li>))}
                                                  </ul>
                                                </div>
                                              )}
                                              {llmIv.length > 0 && (
                                                <div className="space-y-2">
                                                  <div className="text-xs font-semibold text-gray-800 dark:text-gray-200">IV Insights</div>
                                                  <ul className="list-disc list-inside text-xs text-gray-700 dark:text-gray-300">
                                                    {llmIv.map((ins, i) => (<li key={i}>{ins}</li>))}
                                                  </ul>
                                                </div>
                                              )}
                                              {llmCorrMatrix.length > 0 && (
                                                <div className="space-y-2">
                                                  <div className="text-xs font-semibold text-gray-800 dark:text-gray-200">Correlation Matrix Insights</div>
                                                  <ul className="list-disc list-inside text-xs text-gray-700 dark:text-gray-300">
                                                    {llmCorrMatrix.map((ins, i) => (<li key={i}>{ins}</li>))}
                                                  </ul>
                                                </div>
                                              )}
                                              {llmCorrRatio.length > 0 && (
                                                <div className="space-y-2">
                                                  <div className="text-xs font-semibold text-gray-800 dark:text-gray-200">
                                                    Correlation ratio (η) Insights
                                                  </div>
                                                  <ul className="list-disc list-inside text-xs text-gray-700 dark:text-gray-300">
                                                    {llmCorrRatio.map((ins, i) => (
                                                      <li key={i}>{ins}</li>
                                                    ))}
                                                  </ul>
                                                </div>
                                              )}
                                              {/* {ivSummaryTable && (
                                                <div className="space-y-2">
                                                  <div className="text-xs font-semibold text-gray-800 dark:text-gray-200">IV Analysis Summary</div>
                                                  <div className="overflow-x-auto border border-gray-200 rounded-b-lg">
                                                    {ivSummaryTable.rows && ivSummaryTable.rows.length > 0 ? (
                                                      <table className="min-w-full text-xs">
                                                        <thead className="bg-gray-50">
                                                          <tr>
                                                            {ivSummaryTable.columns?.map((col: string, idx: number) => (
                                                              <th key={idx} className="px-3 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">{col}</th>
                                                            ))}
                                                          </tr>
                                                        </thead>
                                                        <tbody>
                                                          {ivSummaryTable.rows.map((row: any, rowIdx: number) => (
                                                            <tr key={rowIdx} className={rowIdx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                                                              {ivSummaryTable.columns?.map((col: string, colIdx: number) => (
                                                                <td key={colIdx} className="px-3 py-2 border-b border-gray-200 text-gray-700">
                                                                  {formatTableCellValue(row[col], col)}
                                                                </td>
                                                              ))}
                                                            </tr>
                                                          ))}
                                                        </tbody>
                                                      </table>
                                                    ) : (
                                                      <div className="px-4 py-3 text-xs text-gray-500">No IV summary rows available.</div>
                                                    )}
                                                  </div>
                                                </div>
                                              )} */}
                                              {/* {corrHighTable && (
                                                <div className="space-y-2">
                                                  <div className="text-xs font-semibold text-gray-800 dark:text-gray-200">High Correlations</div>
                                                  <div className="overflow-x-auto border border-gray-200 rounded-b-lg">
                                                    {corrHighTable.rows && corrHighTable.rows.length > 0 ? (
                                                      <table className="min-w-full text-xs">
                                                        <thead className="bg-gray-50">
                                                          <tr>
                                                            {corrHighTable.columns?.map((col: string, idx: number) => (
                                                              <th key={idx} className="px-3 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">{col}</th>
                                                            ))}
                                                          </tr>
                                                        </thead>
                                                        <tbody>
                                                          {corrHighTable.rows.map((row: any, rowIdx: number) => (
                                                            <tr key={rowIdx} className={rowIdx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                                                              {corrHighTable.columns?.map((col: string, colIdx: number) => (
                                                                <td key={colIdx} className="px-3 py-2 border-b border-gray-200 text-gray-700">
                                                                  {formatTableCellValue(row[col], col)}
                                                                </td>
                                                              ))}
                                                            </tr>
                                                          ))}
                                                        </tbody>
                                                      </table>
                                                    ) : (
                                                      <div className="px-4 py-3 text-xs text-gray-500">No high correlation rows available.</div>
                                                    )}
                                                  </div>
                                                </div>
                                              )} */}
                                              {/* {corrSummaryTable && (
                                                <div className="space-y-2">
                                                  <div className="text-xs font-semibold text-gray-800 dark:text-gray-200">Correlation Matrix Summary</div>
                                                  <div className="overflow-x-auto border border-gray-200 rounded-b-lg">
                                                    {corrSummaryTable.rows && corrSummaryTable.rows.length > 0 ? (
                                                      <table className="min-w-full text-xs">
                                                        <thead className="bg-gray-50">
                                                          <tr>
                                                            {corrSummaryTable.columns?.map((col: string, idx: number) => (
                                                              <th key={idx} className="px-3 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">{col}</th>
                                                            ))}
                                                          </tr>
                                                        </thead>
                                                        <tbody>
                                                          {corrSummaryTable.rows.map((row: any, rowIdx: number) => (
                                                            <tr key={rowIdx} className={rowIdx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                                                              {corrSummaryTable.columns?.map((col: string, colIdx: number) => (
                                                                <td key={colIdx} className="px-3 py-2 border-b border-gray-200 text-gray-700">
                                                                  {formatTableCellValue(row[col], col)}
                                                                </td>
                                                              ))}
                                                            </tr>
                                                          ))}
                                                        </tbody>
                                                      </table>
                                                    ) : (
                                                      <div className="px-4 py-3 text-xs text-gray-500">No correlation summary rows available.</div>
                                                    )}
                                                  </div>
                                                </div>
                                              )} */}
                                              {/* IV Insights duplicate removed */}
                                            </div>
                                          );
                                        }
                                      }

                                      return (
                                        <div className="space-y-3">
                                          <div className="flex items-center justify-between mb-2">
                                            <div className="text-sm font-medium text-blue-700 dark:text-blue-400">📋 Analysis Plan</div>
                                            <button
                                              onClick={() => downloadPlanAsCSV(planData, expandedStepNumber)}
                                              className="flex items-center space-x-1 px-2 py-1 text-xs bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded hover:bg-blue-700 dark:hover:bg-[#333380] transition-colors"
                                              title="Download plan as CSV"
                                            >
                                              <Download className="h-3 w-3" />
                                              <span>Download CSV</span>
                                            </button>
                                          </div>
                                          
                                          {/* Save All Updates Button */}
                                          <div className="flex justify-end mb-4">
                                            <button
                                              onClick={handleSaveAllTreatments}
                                              disabled={isUpdatingTreatment || Object.keys(customTreatments).length === 0}
                                              className="px-4 py-2 bg-green-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-green-700 dark:hover:bg-[#333380] disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center space-x-2"
                                            >
                                              {isUpdatingTreatment ? (
                                                <>
                                                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                                                  <span>Saving All Updates...</span>
                                                </>
                                              ) : (
                                                <>
                                                  <span>Save All Updates</span>
                                                </>
                                              )}
                                            </button>
                                          </div>

                                          {/* Render plan data as table */}
                                          <div className="overflow-x-auto">
                                            <table className="min-w-full text-xs border border-gray-200 dark:border-gray-700 rounded">
                                              <thead className="bg-gray-50 dark:bg-gray-700">
                                                <tr>
                                                  <th className="px-2 py-1 text-left border border-gray-200 dark:border-gray-700 font-medium text-gray-700 dark:text-gray-300">Issue</th>
                                                  <th className="px-2 py-1 text-left border border-gray-200 dark:border-gray-700 font-medium text-gray-700 dark:text-gray-300">Variable</th>
                                                  <th className="px-2 py-1 text-left border border-gray-200 dark:border-gray-700 font-medium text-gray-700 dark:text-gray-300">Observation</th>
                                                  <th className="px-2 py-1 text-left border border-gray-200 dark:border-gray-700 font-medium text-gray-700 dark:text-gray-300">Treatment</th>
                                                  <th className="px-2 py-1 text-left border border-gray-200 dark:border-gray-700 font-medium text-gray-700 dark:text-gray-300">Custom Treatment</th>
                                                </tr>
                                              </thead>
                                              <tbody>
                                                {planData && typeof planData === 'object' ? Object.entries(planData)
                                                  .map(([category, items]) => {
                                                    // Handle array of objects format
                                                    if (Array.isArray(items)) {
                                                      const validItems = items.filter(item => {
                                                        const detection = item.detection || item.strategy || item.approach || item.method || '';
                                                        const treatment = item.treatment || item.solution || item.recommendation || item.action || '';
                                                        return detection && treatment && detection.trim() !== '' && treatment.trim() !== '';
                                                      });
                                                      
                                                      if (validItems.length === 0) return null;
                                                      
                                                      return validItems.map((item, index) => {
                                                        const name = item.variable || item.field || item.column || '';
                                                        const detection = item.detection || item.strategy || item.approach || item.method || '';
                                                        const treatment = item.treatment || item.solution || item.recommendation || item.action || '';
                                                        
                                                        return (
                                                          <tr key={`${category}-${index}`} className={index % 2 === 0 ? 'bg-white dark:bg-gray-800' : 'bg-gray-50 dark:bg-gray-800/50'}>
                                                            {index === 0 ? (
                                                              <td 
                                                                rowSpan={validItems.length} 
                                                                className="px-2 py-1 border border-gray-200 dark:border-gray-700 font-medium text-gray-700 dark:text-gray-300 align-top"
                                                              >
                                                                {category.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                                                              </td>
                                                            ) : null}
                                                            <td className="px-2 py-1 border border-gray-200 dark:border-gray-700">
                                                              <span className="text-gray-800 dark:text-gray-200 font-medium">
                                                                {name || 'N/A'}
                                                              </span>
                                                            </td>
                                                            <td className="px-2 py-1 border border-gray-200 dark:border-gray-700">
                                                              <span className="text-gray-600 dark:text-gray-400">
                                                                {detection || 'Not specified'}
                                                              </span>
                                                            </td>
                                                            <td className="px-2 py-1 border border-gray-200 dark:border-gray-700">
                                                              <span className="text-gray-600 dark:text-gray-400">
                                                                {treatment || 'Not specified'}
                                                              </span>
                                                            </td>
                                                            <td className="px-2 py-1 border border-gray-200 dark:border-gray-700">
                                                              <textarea
                                                                value={customTreatments[`${category}-${index}`] || item.custom_treatment || ''}
                                                                onChange={(e) => handleCustomTreatmentChange(`${category}-${index}`, e.target.value)}
                                                                className="w-full px-2 py-1 text-xs border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none"
                                                                rows={2}
                                                                placeholder={`Original: ${treatment || 'Not specified'}\nEnter custom treatment...`}
                                                              />
                                                            </td>
                                                          </tr>
                                                        );
                                                      });
                                                    } else {
                                                      // Handle legacy object format
                                                      const detection = (items as any)?.detection || (items as any)?.strategy || (items as any)?.approach || '';
                                                      const treatment = (items as any)?.treatment || (items as any)?.solution || (items as any)?.recommendation || '';
                                                      
                                                      // Skip if detection or treatment is empty
                                                      if (!detection || !treatment || detection.trim() === '' || treatment.trim() === '') {
                                                        return null;
                                                      }
                                                      
                                                      return (
                                                        <tr key={category} className="bg-white dark:bg-gray-800">
                                                          <td className="px-2 py-1 border border-gray-200 dark:border-gray-700 font-medium text-gray-700 dark:text-gray-300">
                                                            {category.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                                                          </td>
                                                          <td className="px-2 py-1 border border-gray-200 dark:border-gray-700">
                                                            <span className="text-gray-800 dark:text-gray-200 font-medium">N/A</span>
                                                          </td>
                                                          <td className="px-2 py-1 border border-gray-200 dark:border-gray-700">
                                                            <span className="text-gray-600 dark:text-gray-400">
                                                              {detection || 'Not specified'}
                                                            </span>
                                                          </td>
                                                          <td className="px-2 py-1 border border-gray-200 dark:border-gray-700">
                                                            <span className="text-gray-600 dark:text-gray-400">
                                                              {treatment || 'Not specified'}
                                                            </span>
                                                          </td>
                                                          <td className="px-2 py-1 border border-gray-200 dark:border-gray-700">
                                                            <textarea
                                                              value={customTreatments[category] || (items as any)?.custom_treatment || ''}
                                                              onChange={(e) => handleCustomTreatmentChange(category, e.target.value)}
                                                              className="w-full px-2 py-1 text-xs border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none"
                                                              rows={2}
                                                              placeholder={`Original: ${treatment || 'Not specified'}\nEnter custom treatment...`}
                                                            />
                                                          </td>
                                                        </tr>
                                                      );
                                                    }
                                                  })
                                                  .filter(item => item !== null)
                                                  .flat() : (
                                                  <tr>
                                                    <td colSpan={5} className="px-2 py-1 border border-gray-200 dark:border-gray-700 text-center text-gray-500 dark:text-gray-400">No plan data available
                                                    </td>
                                                  </tr>
                                                )}
                                              </tbody>
                                            </table>
                                          </div>

                                          {/* Knowledge Disclaimer for expanded Analysis Plan */}
                                          {(() => {
                                            const knowledgeMetadata = getKnowledgeMetadata(message, parsed);
                                            if (!knowledgeMetadata) return null;
                                            return (
                                              <KnowledgeDisclaimer
                                                sourceFiles={knowledgeMetadata.source_files || []}
                                                useExlExpertise={knowledgeMetadata.use_exl_expertise !== false}
                                              />
                                            );
                                          })()}
                                        </div>
                                      );
                                    }

                                    // ============================================================
                                    // MANUAL QC COMPLETION MESSAGE HANDLER (EXPANDED VIEW)
                                    // ============================================================
                                    if (parsed.isManualQCComplete) {
                                      return (
                                        <div className="space-y-3">
                                          <div className="bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-700 rounded-lg p-4">
                                            <div className="flex items-start space-x-3">
                                              <div className="flex-shrink-0">
                                                <svg className="w-6 h-6 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                                </svg>
                                              </div>
                                              <div className="flex-1">
                                                <h3 className="text-sm font-semibold text-green-800 dark:text-green-300">
                                                  Data Quality Treatment Complete!
                                                </h3>
                                                <div className="mt-3 flex items-center space-x-2">
                                                  <button
                                                    onClick={() => {
                                                      setShowDatasetOverview(true);
                                                      setShowEDAComparison(true);
                                                      triggerEdaComparisonView();
                                                    }}
                                                    className="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-md bg-green-100 dark:bg-green-800 text-green-800 dark:text-green-200 hover:bg-green-200 dark:hover:bg-green-700 transition-colors"
                                                  >
                                                    <svg className="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                                                    </svg>
                                                    View Updated EDA
                                                  </button>
                                                </div>
                                              </div>
                                            </div>
                                          </div>
                                        </div>
                                      );
                                    }

                                    // Check if this is a regular API response with response, code, suggestions
                                    if (parsed.response || parsed.code || parsed.suggestions || parsed.suggestion) {
                                      return (
                                        <div className="space-y-4">
                                          {/* Explanation Section */}
                                          {parsed.response && (
                                            <div>
                                              <div className="text-sm font-medium text-blue-700 dark:text-blue-400 mb-2">💡 Explanation</div>
                                              <div className="text-sm text-gray-700 dark:text-gray-300">
                                                {typeof parsed.response === 'string' ? (
                                                  <ReactMarkdown>{parsed.response}</ReactMarkdown>
                                                ) : (
                                                  <div className="bg-gray-100 dark:bg-gray-800 p-4 rounded-lg overflow-x-auto text-xs font-mono">
                                                    {/* In expanded view, we show a JSON representation of complex tabular data to prevent UI crashes. */}
                                                    <pre>{JSON.stringify(parsed.response, null, 2)}</pre>
                                                  </div>
                                                )}
                                              </div>
                                            </div>
                                          )}

                                          {/* Code Section */}
                                          {parsed.code && 
                                           parsed.code !== "# No code to display" && 
                                           parsed.code !== "No Code to display" &&
                                           parsed.code.trim() !== "# Plan generated successfully" &&
                                           parsed.code.trim() !== "Plan generated successfully" &&
                                           parsed.code.trim().length > 0 && (
                                            <div>
                                              <div className="text-sm font-medium text-green-700 dark:text-green-400 mb-2">📝 Code</div>
                                              <div className="bg-gray-900 text-green-400 p-3 rounded text-sm font-mono overflow-x-auto">
                                               <pre>{parsed.code}</pre>
                                             </div>

                                              {/* Code Execution Results */}
                                              {executionResults[generateCodeId(message.id, parsed.code)] && (
                                                <div className="mt-3 p-3 border rounded-lg">
                                                  <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Execution Results:</div>
                                                  
                                                  {executionResults[generateCodeId(message.id, parsed.code)].success ? (
                                                    <div>
                                                      {/* Response Text - Hidden */}
                                                      
                                                      {/* Column Stats Table */}
                                                      {executionResults[generateCodeId(message.id, parsed.code)].columns_info && (
                                                        <div>
                                                          <div className="flex justify-between items-center mb-2">
                                                            <div className="text-sm font-medium text-gray-700 dark:text-gray-300">Column Stats:</div>
                                                            <div className="flex items-center gap-2">
                                                              <button
                                                                onClick={downloadColumnStats}
                                                                disabled={!executionResults[generateCodeId(message.id, parsed.code)]?.columns_info || executionResults[generateCodeId(message.id, parsed.code)].columns_info.length === 0}
                                                                className="px-3 py-1 bg-green-600 text-white text-xs rounded hover:bg-green-700 transition-colors flex items-center space-x-1 disabled:opacity-50 disabled:cursor-not-allowed"
                                                                title="Download Column Stats table as CSV"
                                                              >
                                                                <Download className="w-3 h-3" />
                                                                <span>Download Stats Table</span>
                                                              </button>
                                                              <button
                                                                onClick={handleCompareChanges}
                                                                disabled={isLoadingComparison}
                                                                className="px-3 py-1 bg-purple-600 text-white text-xs rounded hover:bg-purple-700 transition-colors flex items-center space-x-1 disabled:opacity-50"
                                                                title="Compare original vs processed statistics"
                                                              >
                                                                {isLoadingComparison ? (
                                                                  <>
                                                                    <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                                                                    <span>Loading...</span>
                                                                  </>
                                                                ) : (
                                                                  <>
                                                                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                                                                    </svg>
                                                                    <span>Compare Changes</span>
                                                                  </>
                                                                )}
                                                              </button>
                                                            </div>
                                                          </div>
                                                          <div className="overflow-x-auto">
                                                            <table className="min-w-full text-xs border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white">
                                                              <thead>
                                                                <tr className="bg-gray-100 dark:bg-gray-800">
                                                                  <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">Column</th>
                                                                  <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">Type</th>
                                                                  <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">Missing</th>
                                                                  <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">Unique</th>
                                                                  <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">Mean</th>
                                                                  <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">Median</th>
                                                                  <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">Mode</th>
                                                                  <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">Std</th>
                                                                  <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">Var</th>
                                                                  <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">Min</th>
                                                                  <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">p5%</th>
                                                                  <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">p25%</th>
                                                                  <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">p50%</th>
                                                                  <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">p75%</th>
                                                                  <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">p95%</th>
                                                                  <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">p99%</th>
                                                                  <th className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white dark:border-gray-700 text-left text-gray-700 dark:text-white">Max</th>
                                                                </tr>
                                                              </thead>
                                                              <tbody>
                                                                {executionResults[generateCodeId(message.id, parsed.code)].columns_info?.map((col: any, idx: number) => {
                                                                  // Use improved column_type from backend API (with smart classification logic)
                                                                  const columnType = col.column_type || (['int64', 'float64', 'int32', 'float32'].includes(col.data_type) ? 'Numerical' : 'Categorical');
                                                                  
                                                                  // Find the original column info for comparison
                                                                  const colName = col.column_name || col.name;
                                                                  const baselineColumns = executionBaselines[generateCodeId(message.id, parsed.code)] || originalColumnInfo;
                                                                  const originalCol = baselineColumns?.find(
                                                                    (oc: any) => (oc.column_name || oc.name) === colName
                                                                  );
                                                                  
                                                                  // Helper to format value, using original if current is null
                                                                  const formatValue = (currentVal: any, originalVal: any, isNumeric: boolean = true) => {
                                                                    const val = (currentVal !== null && currentVal !== undefined) ? currentVal : originalVal;
                                                                    if (val === null || val === undefined) return '';
                                                                    if (typeof val === 'number' && isNumeric) return val.toFixed(2);
                                                                    return String(val);
                                                                  };
                                                                  
                                                                  // Helper to check if value changed and get appropriate cell class
                                                                  const getCellClass = (currentValue: any, originalValue: any, isNumeric: boolean = true) => {
                                                                    let isDifferent = false;
                                                                    if (originalCol) {
                                                                      if (
                                                                        (currentValue === null || currentValue === undefined) &&
                                                                        (originalValue === null || originalValue === undefined)
                                                                      ) {
                                                                        isDifferent = false;
                                                                      } else if (
                                                                        currentValue === null || currentValue === undefined ||
                                                                        originalValue === null || originalValue === undefined
                                                                      ) {
                                                                        isDifferent = true;
                                                                      } else if (typeof currentValue === 'number' && typeof originalValue === 'number' && isNumeric) {
                                                                        isDifferent = Math.abs(currentValue - originalValue) > 1e-9;
                                                                      } else {
                                                                        isDifferent = String(currentValue) !== String(originalValue);
                                                                      }
                                                                    }
                                                                    return `px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white ${isDifferent ? 'bg-yellow-100 text-amber-800 font-medium dark:bg-yellow-900/30 dark:text-white' : ''}`;
                                                                  };
                                                                  
                                                                  return (
                                                                  <tr key={idx} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                                                                    <td className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white font-medium">{col.column_name}</td>
                                                                    <td className="px-2 py-1 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white" title={`pandas dtype: ${col.data_type}`}>
                                                                      {columnType}
                                                                    </td>
                                                                    <td className={getCellClass(col.missing_count, originalCol?.missing_count, false)}>{formatValue(col.missing_count, originalCol?.missing_count, false)}</td>
                                                                    <td className={getCellClass(col.unique_count, originalCol?.unique_count, false)}>{formatValue(col.unique_count, originalCol?.unique_count, false)}</td>
                                                                    <td className={getCellClass(col.mean, originalCol?.mean)}>{formatValue(col.mean, originalCol?.mean)}</td>
                                                                    <td className={getCellClass(col.median, originalCol?.median)}>{formatValue(col.median, originalCol?.median)}</td>
                                                                    <td className={`${getCellClass(col.mode, originalCol?.mode, false)} max-w-[150px] truncate`} title={formatValue(col.mode, originalCol?.mode, false)}>
                                                                      {formatValue(col.mode, originalCol?.mode, false)}
                                                                    </td>
                                                                    <td className={getCellClass(col.standard_deviation, originalCol?.standard_deviation)}>{formatValue(col.standard_deviation, originalCol?.standard_deviation)}</td>
                                                                    <td className={getCellClass(col.variance, originalCol?.variance)}>{formatValue(col.variance, originalCol?.variance)}</td>
                                                                    <td className={getCellClass(col.min_value, originalCol?.min_value)}>{formatValue(col.min_value, originalCol?.min_value)}</td>
                                                                    <td className={getCellClass(col.percentile_5, originalCol?.percentile_5)}>{formatValue(col.percentile_5, originalCol?.percentile_5)}</td>
                                                                    <td className={getCellClass(col.percentile_25, originalCol?.percentile_25)}>{formatValue(col.percentile_25, originalCol?.percentile_25)}</td>
                                                                    <td className={getCellClass(col.percentile_50, originalCol?.percentile_50)}>{formatValue(col.percentile_50, originalCol?.percentile_50)}</td>
                                                                    <td className={getCellClass(col.percentile_75, originalCol?.percentile_75)}>{formatValue(col.percentile_75, originalCol?.percentile_75)}</td>
                                                                    <td className={getCellClass(col.percentile_95, originalCol?.percentile_95)}>{formatValue(col.percentile_95, originalCol?.percentile_95)}</td>
                                                                    <td className={getCellClass(col.percentile_99, originalCol?.percentile_99)}>{formatValue(col.percentile_99, originalCol?.percentile_99)}</td>
                                                                    <td className={getCellClass(col.max_value, originalCol?.max_value)}>{formatValue(col.max_value, originalCol?.max_value)}</td>
                                                                  </tr>
                                                                  );
                                                                })}
                                                              </tbody>
                                                            </table>
                                                          </div>
                                                        </div>
                                                      )}
                                                    </div>
                                                  ) : (
                                                    <div>
                                                      <div className="text-sm text-red-700 mb-2">❌ Error</div>
                                                      <div className="text-sm text-red-600">
                                                        {executionResults[generateCodeId(message.id, parsed.code)].error || 'Unknown error occurred'}
                                                      </div>
                                                    </div>
                                                  )}
                                                </div>
                                              )}
                                            </div>
                                          )}

                                          {/* Suggestions Section */}
                                          {((parsed.suggestions && Array.isArray(parsed.suggestions) && parsed.suggestions.length > 0) || 
                                           (parsed.suggestion && Array.isArray(parsed.suggestion) && parsed.suggestion.length > 0)) && (
                                            <div>
                                              <div className="text-sm font-medium text-purple-700 mb-2">💡 Suggestions</div>
                                              <div className="space-y-1">
                                                {(parsed.suggestions || parsed.suggestion).map((suggestion: string, idx: number) => (
                                                  <div key={idx} className="text-sm text-gray-700 flex items-start space-x-2">
                                                    <span className="text-purple-600 mt-0.5">•</span>
                                                    <span>{suggestion}</span>
                                                  </div>
                                                ))}
                                              </div>
                                            </div>
                                          )}

                                          {/* Knowledge Disclaimer for expanded Explanation */}
                                          {(expandedStepNumber === 2 || expandedStepNumber === 3 || expandedStepNumber === 4) && message.knowledge_metadata && (
                                            <KnowledgeDisclaimer
                                              sourceFiles={message.knowledge_metadata.source_files || []}
                                              useExlExpertise={message.knowledge_metadata.use_exl_expertise !== false}
                                            />
                                          )}
                                        </div>
                                      );
                                    }

                                    // Regular responses and other message types
                                    return typeof (parsed.response || message.content) === 'string' ? (
                                      <ReactMarkdown>{parsed.response || message.content}</ReactMarkdown>
                                    ) : (
                                      <div className="bg-gray-100 dark:bg-gray-800 p-4 rounded-lg overflow-x-auto text-xs font-mono">
                                        <pre>{JSON.stringify(parsed.response || message.content, null, 2)}</pre>
                                      </div>
                                    );
                                  } catch (error) {
                                    // Fallback for non-JSON content or parsing errors
                                    console.warn('Failed to parse message content as JSON:', error);
                                    return (
                                      <div>
                                        <ReactMarkdown>{String(message.content || '')}</ReactMarkdown>
                                      </div>
                                    );
                                  }
                                })()}
                              </div>
                            ) : (
                              <div className="text-sm">
                                <ReactMarkdown>{String(message.content || '')}</ReactMarkdown>
                              </div>
                            )}
                            <div className="text-xs opacity-70 mt-1">
                              {message.timestamp && typeof message.timestamp.toLocaleTimeString === 'function' 
                                ? message.timestamp.toLocaleTimeString() 
                                : new Date().toLocaleTimeString()}
                            </div>
                          </div>
                        </div>
                      );
                        })}
                      
                        {/* Typing indicator */}
                        {isTyping[expandedStepNumber] && (
                          <div className="flex justify-start">
                            <div className="bg-white border border-gray-200 px-4 py-3 rounded-lg">
                              <div className="flex items-center space-x-2">
                                <div className="flex space-x-1">
                                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.1s'}}></div>
                                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>
                                </div>
                                {/* <span className="text-sm text-gray-500">AI is typing...</span> */}
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })()}
                </div>

                {/* Knowledge Disclaimer for Analysis Plan - between table and QC buttons */}
                {expandedStepNumber === 2 && lastExecutedQCTasks.length > 0 && (() => {
                  const msgs = chatMessages[2] || [];
                  const lastAssistant = [...msgs].reverse().find((m) => {
                    if (m.type !== 'assistant') return false;
                    if (m.knowledge_metadata) return true;
                    try {
                      const parsedMessage = JSON.parse(String(m.content || '{}'));
                      return !!parsedMessage?.knowledge_metadata;
                    } catch {
                      return false;
                    }
                  });

                  let knowledgeMetadata = lastAssistant?.knowledge_metadata;
                  if (!knowledgeMetadata && lastAssistant) {
                    try {
                      const parsedMessage = JSON.parse(String(lastAssistant.content || '{}'));
                      knowledgeMetadata = parsedMessage?.knowledge_metadata;
                    } catch {
                      knowledgeMetadata = undefined;
                    }
                  }

                  if (!knowledgeMetadata) return null;
                  return (
                    <KnowledgeDisclaimer
                      sourceFiles={knowledgeMetadata.source_files || []}
                      useExlExpertise={knowledgeMetadata.use_exl_expertise !== false}
                    />
                  );
                })()}

                {/* Individual QC Task Execution Buttons - Expanded View */}
                {expandedStepNumber === 2 && lastExecutedQCTasks.length > 0 && (
                  <div className="mb-4 border-t dark:border-gray-700 pt-4">
                    <div className="text-sm font-medium text-purple-700 dark:text-purple-400 mb-3">🎯 Execute Individual QC Tasks</div>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                      {lastExecutedQCTasks.map((taskId) => {
                        const actionMessage = getQCActionMessageFromTaskId(taskId);
                        
                        // Get task display name
                        let taskDisplayName = '';
                        let taskDescription = '';
                        
                        switch (taskId) {
                          case 'missing_values':
                            taskDisplayName = 'Missing Values';
                            taskDescription = 'Identify and handle missing data points';
                            break;
                          case 'outliers':
                            taskDisplayName = 'Outliers';
                            taskDescription = 'Detect and treat outlier values';
                            break;
                          case 'duplicates':
                            taskDisplayName = 'Duplicates';
                            taskDescription = 'Find and remove duplicate records';
                            break;
                          case 'data_types':
                            taskDisplayName = 'Data Types';
                            taskDescription = 'Validate and correct data types';
                            break;
                          case 'distribution':
                            taskDisplayName = 'Distribution';
                            taskDescription = 'Analyze data distributions';
                            break;
                          case 'correlation':
                            taskDisplayName = 'Correlation';
                            taskDescription = 'Analyze variable correlations';
                            break;
                          default:
                            taskDisplayName = taskId;
                            taskDescription = `Custom QC task: ${taskId}`;
                            break;
                        }
                        
                        const isExecuted = executedIndividualQCTasks.includes(taskId);
                        
                        return (
                          <button
                            key={taskId}
                            onClick={() => handleIndividualQCTaskByTaskId(taskId)}
                            disabled={isExecuted}
                            className={`flex flex-col items-start p-3 border rounded-lg transition-all duration-200 text-left group ${
                              isExecuted 
                                ? 'bg-gray-100 dark:bg-gray-800 border-gray-300 dark:border-gray-600 cursor-not-allowed opacity-60' 
                                : 'bg-gradient-to-r from-purple-50 to-indigo-50 dark:from-gray-800 dark:to-gray-800 border-purple-200 dark:border-purple-700 hover:from-purple-100 hover:to-indigo-100 dark:hover:from-gray-700 dark:hover:to-gray-700 hover:border-purple-300 dark:hover:border-purple-600'
                            }`}
                            title={isExecuted ? `${taskDisplayName} task completed` : `Execute ${taskDisplayName} QC task`}
                          >
                            <div className="flex items-center justify-between w-full mb-1">
                              <span className={`text-sm font-medium ${
                                isExecuted 
                                  ? 'text-gray-500 dark:text-gray-400' 
                                  : 'text-purple-800 dark:text-purple-400 group-hover:text-purple-900 dark:group-hover:text-purple-300'
                              }`}>
                                {taskDisplayName} {isExecuted && '✓'}
                              </span>
                              {!isExecuted && <Play className="h-3 w-3 text-purple-600 dark:text-purple-400 group-hover:text-purple-700 dark:group-hover:text-purple-300" />}
                              {isExecuted && <CheckCircle className="h-3 w-3 text-gray-500 dark:text-gray-400" />}
                            </div>
                            <span className={`text-xs ${
                              isExecuted 
                                ? 'text-gray-400 dark:text-gray-500' 
                                : 'text-purple-600 dark:text-purple-300 group-hover:text-purple-700 dark:group-hover:text-purple-200'
                            }`}>
                              {isExecuted ? 'Task completed' : taskDescription}
                            </span>
                          </button>
                        );
                      })}
                    </div>

                  </div>
                )}

                {/* Input Area */}
                <div className="flex space-x-2">
                  <input
                    type="text"
                    value={chatInputs[expandedStepNumber] || ''}
                    onChange={(e) => setChatInputs(prev => ({ ...prev, [expandedStepNumber]: e.target.value }))}
                    onKeyPress={(e) => {
                      if (e.key === 'Enter' && !isTyping[expandedStepNumber]) {
                        handleSendChatMessage(expandedStepNumber);
                      }
                    }}
                    placeholder="Ask me anything about this step..."
                    className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    disabled={isTyping[expandedStepNumber]}
                  />
                  <button
                    onClick={() => handleSendChatMessage(expandedStepNumber)}
                    disabled={isTyping[expandedStepNumber] || !chatInputs[expandedStepNumber]?.trim()}
                    className="px-4 py-2 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    Send
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Dataset ID Alert Modal */}
      {showDatasetIdAlert && pendingDatasetId && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-900 rounded-xl shadow-2xl max-w-md w-full mx-4 p-6">
            <div className="flex items-center space-x-3 mb-4">
              <div className="w-12 h-12 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center">
                <CheckCircle className="h-6 w-6 text-green-600" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Dataset Uploaded Successfully!</h3>
                <p className="text-sm text-gray-600 dark:text-gray-400">Dataset ID: {pendingDatasetId}</p>
              </div>
            </div>
            
            <div className="mb-6">
              {/* <p className="text-gray-700 mb-2">Your dataset has been uploaded successfully.</p> */}
              {/* <p className="text-sm text-gray-600">Click OK to view the dataset overview. Additional analysis will load in the background.</p> */}
            </div>

            <div className="flex justify-center space-x-3">
              <button
                onClick={handleDatasetIdAlertOk}
                className="px-6 py-2 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] transition-colors"
              >
                <span>OK</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Comparison Modal */}
      {showComparisonModal && comparisonData && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-900 rounded-xl shadow-2xl max-w-6xl w-full max-h-[90vh] overflow-hidden flex flex-col">
            {/* Header */}
            <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center bg-gradient-to-r from-purple-50 to-blue-50 dark:from-[#1b1b2f] dark:to-[#1a2238]">
              <div>
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
                  <svg className="w-6 h-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                  Column Statistics Comparison
                </h2>
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                  {comparisonData.baseline_source === 'previous_snapshot_db' && 'Previous Snapshot (DB) vs Latest Processed'}
                  {comparisonData.baseline_source === 'previous_snapshot_memory' && 'Previous Snapshot (Memory) vs Latest Processed'}
                  {comparisonData.baseline_source === 'raw_dataset_fallback' && 'Original Upload (Fallback) vs Latest Processed'}
                  {!comparisonData.baseline_source && 'Baseline vs Latest Processed'}
                </p>
              </div>
              <button
                onClick={() => setShowComparisonModal(false)}
                className="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
    </div>

            {/* Summary Cards */}
            <div className="px-6 py-4 bg-gray-50 dark:bg-[#101021] border-b border-gray-200 dark:border-gray-800">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-white dark:bg-[#0f1428] dark:border dark:border-gray-800 rounded-lg p-3 shadow-sm">
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Rows</div>
                  <div className="text-lg font-bold text-gray-900 dark:text-white">
                    {comparisonData.original_shape.rows.toLocaleString()} → {comparisonData.processed_shape.rows.toLocaleString()}
                  </div>
                  <div className={`text-xs mt-1 ${comparisonData.summary.rows_change >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {comparisonData.summary.rows_change >= 0 ? '+' : ''}{comparisonData.summary.rows_change.toLocaleString()} 
                    ({comparisonData.summary.rows_change_pct === null || comparisonData.summary.rows_change_pct === undefined ? 'N/A' : `${comparisonData.summary.rows_change_pct.toFixed(1)}%`})
                  </div>
                </div>

                <div className="bg-white dark:bg-[#0f1428] dark:border dark:border-gray-800 rounded-lg p-3 shadow-sm">
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Columns</div>
                  <div className="text-lg font-bold text-gray-900 dark:text-white">
                    {comparisonData.original_shape.columns} → {comparisonData.processed_shape.columns}
                  </div>
                  <div className={`text-xs mt-1 ${comparisonData.summary.total_columns_processed - comparisonData.summary.total_columns_original >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {comparisonData.summary.total_columns_processed - comparisonData.summary.total_columns_original >= 0 ? '+' : ''}
                    {comparisonData.summary.total_columns_processed - comparisonData.summary.total_columns_original}
                  </div>
                </div>

                <div className="bg-white dark:bg-[#0f1428] dark:border dark:border-gray-800 rounded-lg p-3 shadow-sm">
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Modified</div>
                  <div className="text-2xl font-bold text-orange-600">
                    {comparisonData.summary.columns_modified}
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">columns changed</div>
                </div>

                <div className="bg-white dark:bg-[#0f1428] dark:border dark:border-gray-800 rounded-lg p-3 shadow-sm">
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Added/Removed</div>
                  <div className="flex items-center gap-2">
                    <span className="text-lg font-bold text-green-600">+{comparisonData.summary.columns_added}</span>
                    <span className="text-gray-400 dark:text-gray-500">/</span>
                    <span className="text-lg font-bold text-red-600">-{comparisonData.summary.columns_removed}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Heatmap Overview */}
            <div className="px-6 py-4 bg-white dark:bg-[#0b1020] border-b border-gray-200 dark:border-gray-800">
              <div className="flex justify-between items-center mb-3">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                  <svg className="w-5 h-5 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" />
                  </svg>
                  Change Heatmap
                </h3>
                <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
                  </svg>
                  <span>Scroll to view all</span>
                </div>
              </div>
              
              {/* Info text */}
              <div className="mb-2 flex items-center gap-4 text-xs text-gray-600 dark:text-gray-400">
                <div className="flex items-center gap-1">
                  <svg className="w-4 h-4 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
                  </svg>
                  <span>Scroll vertically and horizontally to view all data</span>
                </div>
              </div>
              
              {/* Scrollable container with max height and custom scrollbar */}
              <style>
                {`
                  .heatmap-scroll::-webkit-scrollbar {
                    width: 10px;
                    height: 10px;
                  }
                  .heatmap-scroll::-webkit-scrollbar-track {
                    background: #F3F4F6;
                    border-radius: 5px;
                  }
                  .heatmap-scroll::-webkit-scrollbar-thumb {
                    background: #9CA3AF;
                    border-radius: 5px;
                  }
                  .heatmap-scroll::-webkit-scrollbar-thumb:hover {
                    background: #6B7280;
                  }
                  .heatmap-scroll::-webkit-scrollbar-corner {
                    background: #F3F4F6;
                  }
                  .dark .heatmap-scroll::-webkit-scrollbar-track {
                    background: #0f172a;
                  }
                  .dark .heatmap-scroll::-webkit-scrollbar-thumb {
                    background: #475569;
                  }
                  .dark .heatmap-scroll::-webkit-scrollbar-thumb:hover {
                    background: #64748b;
                  }
                  .dark .heatmap-scroll::-webkit-scrollbar-corner {
                    background: #0f172a;
                  }
                `}
              </style>
              <div 
                className="heatmap-scroll overflow-x-auto overflow-y-auto max-h-96 border-2 border-blue-200 dark:border-[#2b2f55] rounded-lg shadow-lg relative"
                style={{
                  scrollbarWidth: 'thin',
                  scrollbarColor: '#9CA3AF #F3F4F6'
                }}
              >
                <table className="w-full text-xs border-collapse" style={{ minWidth: '2000px' }}>
                  <thead className="sticky top-0 z-20">
                    <tr className="bg-gray-100 dark:bg-[#1a1f3a] text-gray-900 dark:text-gray-200">
                      <th className="px-3 py-2 border border-gray-300 dark:border-[#2b2f55] text-left font-medium sticky left-0 bg-gray-100 dark:bg-[#1a1f3a] z-30" style={{ minWidth: '150px' }}>Column</th>
                      <th className="px-3 py-2 border border-gray-300 dark:border-[#2b2f55] text-center font-medium bg-gray-100 dark:bg-[#1a1f3a]" style={{ minWidth: '100px' }}>Status</th>
                      <th className="px-3 py-2 border border-gray-300 dark:border-[#2b2f55] text-center font-medium bg-gray-100 dark:bg-[#1a1f3a]" style={{ minWidth: '120px' }}>Missing</th>
                      <th className="px-3 py-2 border border-gray-300 dark:border-[#2b2f55] text-center font-medium bg-gray-100 dark:bg-[#1a1f3a]" style={{ minWidth: '120px' }}>Unique</th>
                      <th className="px-3 py-2 border border-gray-300 dark:border-[#2b2f55] text-center font-medium bg-gray-100 dark:bg-[#1a1f3a]" style={{ minWidth: '120px' }}>Mean</th>
                      <th className="px-3 py-2 border border-gray-300 dark:border-[#2b2f55] text-center font-medium bg-gray-100 dark:bg-[#1a1f3a]" style={{ minWidth: '120px' }}>Median</th>
                      <th className="px-3 py-2 border border-gray-300 dark:border-[#2b2f55] text-center font-medium bg-gray-100 dark:bg-[#1a1f3a]" style={{ minWidth: '120px' }}>Mode</th>
                      <th className="px-3 py-2 border border-gray-300 dark:border-[#2b2f55] text-center font-medium bg-gray-100 dark:bg-[#1a1f3a]" style={{ minWidth: '120px' }}>Std Dev</th>
                      <th className="px-3 py-2 border border-gray-300 dark:border-[#2b2f55] text-center font-medium bg-gray-100 dark:bg-[#1a1f3a]" style={{ minWidth: '120px' }}>Variance</th>
                      <th className="px-3 py-2 border border-gray-300 dark:border-[#2b2f55] text-center font-medium bg-gray-100 dark:bg-[#1a1f3a]" style={{ minWidth: '120px' }}>Min</th>
                      <th className="px-3 py-2 border border-gray-300 dark:border-[#2b2f55] text-center font-medium bg-gray-100 dark:bg-[#1a1f3a]" style={{ minWidth: '120px' }}>p5%</th>
                      <th className="px-3 py-2 border border-gray-300 dark:border-[#2b2f55] text-center font-medium bg-gray-100 dark:bg-[#1a1f3a]" style={{ minWidth: '120px' }}>p25%</th>
                      <th className="px-3 py-2 border border-gray-300 dark:border-[#2b2f55] text-center font-medium bg-gray-100 dark:bg-[#1a1f3a]" style={{ minWidth: '120px' }}>p50%</th>
                      <th className="px-3 py-2 border border-gray-300 dark:border-[#2b2f55] text-center font-medium bg-gray-100 dark:bg-[#1a1f3a]" style={{ minWidth: '120px' }}>p75%</th>
                      <th className="px-3 py-2 border border-gray-300 dark:border-[#2b2f55] text-center font-medium bg-gray-100 dark:bg-[#1a1f3a]" style={{ minWidth: '120px' }}>p95%</th>
                      <th className="px-3 py-2 border border-gray-300 dark:border-[#2b2f55] text-center font-medium bg-gray-100 dark:bg-[#1a1f3a]" style={{ minWidth: '120px' }}>p99%</th>
                      <th className="px-3 py-2 border border-gray-300 dark:border-[#2b2f55] text-center font-medium bg-gray-100 dark:bg-[#1a1f3a]" style={{ minWidth: '120px' }}>Max</th>
                    </tr>
                  </thead>
                  <tbody>
                    {comparisonData.changes.map((change: any, idx: number) => {
                      const getHeatmapColor = (changeData: any) => {
                        if (!changeData) return 'bg-gray-50 dark:bg-[#0f1428]';
                        const numericPct = typeof changeData.change_pct === 'number' && Number.isFinite(changeData.change_pct)
                          ? changeData.change_pct
                          : null;
                        const intensity = Math.min(Math.abs(numericPct ?? 0) / 100, 1);
                        if (changeData.change > 0) {
                          // Positive change - green scale
                          return intensity > 0.5 ? 'bg-green-300 dark:bg-green-900/60' : intensity > 0.2 ? 'bg-green-200 dark:bg-green-900/45' : intensity > 0.05 ? 'bg-green-100 dark:bg-green-900/30' : 'bg-green-50 dark:bg-green-900/20';
                        } else if (changeData.change < 0) {
                          // Negative change - red scale
                          return intensity > 0.5 ? 'bg-red-300 dark:bg-red-900/60' : intensity > 0.2 ? 'bg-red-200 dark:bg-red-900/45' : intensity > 0.05 ? 'bg-red-100 dark:bg-red-900/30' : 'bg-red-50 dark:bg-red-900/20';
                        }
                        return 'bg-gray-50 dark:bg-[#0f1428]';
                      };

                      const getStatusColor = (status: string) => {
                        if (status === 'added') return 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-200';
                        if (status === 'removed') return 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200';
                        if (status === 'modified') return 'bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-200';
                        return 'bg-gray-50 text-gray-600 dark:bg-[#0f1428] dark:text-gray-300';
                      };

                      return (
                        <tr key={idx} className="hover:bg-gray-50 dark:hover:bg-[#1b2142] text-gray-900 dark:text-gray-200">
                          <td className="px-3 py-2 border border-gray-300 dark:border-[#2b2f55] font-medium sticky left-0 bg-white dark:bg-[#0f1428] z-10" style={{ minWidth: '150px' }}>
                            {change.column_name}
                          </td>
                          <td className={`px-3 py-2 border border-gray-300 dark:border-[#2b2f55] text-center ${getStatusColor(change.status)}`} style={{ minWidth: '100px' }}>
                            <span className="px-2 py-1 rounded text-xs font-medium">
                              {change.status === 'added' && '✚ Added'}
                              {change.status === 'removed' && '✖ Removed'}
                              {change.status === 'modified' && '⟳ Modified'}
                              {change.status === 'unchanged' && '○ Same'}
                            </span>
                          </td>
                          <td className={`px-3 py-2 border border-gray-300 dark:border-[#2b2f55] text-center ${getHeatmapColor(change.changes?.missing)}`} style={{ minWidth: '120px' }}>
                            {change.changes?.missing !== undefined ? (
                              <div className="font-medium">
                                <div>{change.changes.missing.processed ?? change.changes.missing.original ?? 0}</div>
                                {change.changes.missing.change !== 0 && (
                                  <div className={`text-xs ${change.changes.missing.change_pct > 0 ? 'text-green-600' : 'text-red-600'}`}>({formatChangePct(change.changes.missing.change_pct)})</div>
                                )}
                              </div>
                            ) : (
                              <span className="text-gray-500 dark:text-gray-400">N/A</span>
                            )}
                          </td>
                          <td className={`px-3 py-2 border border-gray-300 dark:border-[#2b2f55] text-center ${getHeatmapColor(change.changes?.unique)}`} style={{ minWidth: '120px' }}>
                            {change.changes?.unique !== undefined ? (
                              <div className="font-medium">
                                <div>{change.changes.unique.processed ?? change.changes.unique.original ?? 0}</div>
                                {change.changes.unique.change !== 0 && (
                                  <div className={`text-xs ${change.changes.unique.change_pct > 0 ? 'text-green-600' : 'text-red-600'}`}>({formatChangePct(change.changes.unique.change_pct)})</div>
                                )}
                              </div>
                            ) : (
                              <span className="text-gray-500 dark:text-gray-400">N/A</span>
                            )}
                          </td>
                          <td className={`px-3 py-2 border border-gray-300 dark:border-[#2b2f55] text-center ${getHeatmapColor(change.changes?.mean)}`} style={{ minWidth: '120px' }}>
                            {change.changes?.mean !== undefined && change.changes.mean.processed !== null ? (
                              <div className="font-medium">
                                <div>{change.changes.mean.processed?.toFixed(2)}</div>
                                {change.changes.mean.change !== 0 && (
                                  <div className={`text-xs ${change.changes.mean.change_pct > 0 ? 'text-green-600' : 'text-red-600'}`}>({formatChangePct(change.changes.mean.change_pct)})</div>
                                )}
                              </div>
                            ) : (
                              <span className="text-gray-500 dark:text-gray-400">N/A</span>
                            )}
                          </td>
                          <td className={`px-3 py-2 border border-gray-300 dark:border-[#2b2f55] text-center ${getHeatmapColor(change.changes?.median)}`} style={{ minWidth: '120px' }}>
                            {change.changes?.median !== undefined && change.changes.median.processed !== null ? (
                              <div className="font-medium">
                                <div>{change.changes.median.processed?.toFixed(2)}</div>
                                {change.changes.median.change !== 0 && (
                                  <div className={`text-xs ${change.changes.median.change_pct > 0 ? 'text-green-600' : 'text-red-600'}`}>({formatChangePct(change.changes.median.change_pct)})</div>
                                )}
                              </div>
                            ) : (
                              <span className="text-gray-500 dark:text-gray-400">N/A</span>
                            )}
                          </td>
                          <td className={`px-3 py-2 border border-gray-300 dark:border-[#2b2f55] text-center ${getHeatmapColor(change.changes?.mode)}`} style={{ minWidth: '120px' }}>
                            {change.changes?.mode !== undefined && change.changes.mode.processed !== null ? (
                              <div className="font-medium">
                                <div>{typeof change.changes.mode.processed === 'number' ? change.changes.mode.processed?.toFixed(2) : change.changes.mode.processed}</div>
                                {change.changes.mode.change !== 0 && (
                                  <div className={`text-xs ${change.changes.mode.change_pct > 0 ? 'text-green-600' : 'text-red-600'}`}>({formatChangePct(change.changes.mode.change_pct)})</div>
                                )}
                              </div>
                            ) : (
                              <span className="text-gray-500 dark:text-gray-400">N/A</span>
                            )}
                          </td>
                          <td className={`px-3 py-2 border border-gray-300 dark:border-[#2b2f55] text-center ${getHeatmapColor(change.changes?.std)}`} style={{ minWidth: '120px' }}>
                            {change.changes?.std !== undefined && change.changes.std.processed !== null ? (
                              <div className="font-medium">
                                <div>{change.changes.std.processed?.toFixed(2)}</div>
                                {change.changes.std.change !== 0 && (
                                  <div className={`text-xs ${change.changes.std.change_pct > 0 ? 'text-green-600' : 'text-red-600'}`}>({formatChangePct(change.changes.std.change_pct)})</div>
                                )}
                              </div>
                            ) : (
                              <span className="text-gray-500 dark:text-gray-400">N/A</span>
                            )}
                          </td>
                          <td className={`px-3 py-2 border border-gray-300 dark:border-[#2b2f55] text-center ${getHeatmapColor(change.changes?.var)}`} style={{ minWidth: '120px' }}>
                            {change.changes?.var !== undefined && change.changes.var.processed !== null ? (
                              <div className="font-medium">
                                <div>{change.changes.var.processed?.toFixed(2)}</div>
                                {change.changes.var.change !== 0 && (
                                  <div className={`text-xs ${change.changes.var.change_pct > 0 ? 'text-green-600' : 'text-red-600'}`}>({formatChangePct(change.changes.var.change_pct)})</div>
                                )}
                              </div>
                            ) : (
                              <span className="text-gray-500 dark:text-gray-400">N/A</span>
                            )}
                          </td>
                          <td className={`px-3 py-2 border border-gray-300 dark:border-[#2b2f55] text-center ${getHeatmapColor(change.changes?.min)}`} style={{ minWidth: '120px' }}>
                            {change.changes?.min !== undefined && change.changes.min.processed !== null ? (
                              <div className="font-medium">
                                <div>{change.changes.min.processed?.toFixed(2)}</div>
                                {change.changes.min.change !== 0 && (
                                  <div className={`text-xs ${change.changes.min.change_pct > 0 ? 'text-green-600' : 'text-red-600'}`}>({formatChangePct(change.changes.min.change_pct)})</div>
                                )}
                              </div>
                            ) : (
                              <span className="text-gray-500 dark:text-gray-400">N/A</span>
                            )}
                          </td>
                          <td className={`px-3 py-2 border border-gray-300 dark:border-[#2b2f55] text-center ${getHeatmapColor(change.changes?.p5)}`} style={{ minWidth: '120px' }}>
                            {change.changes?.p5 !== undefined && change.changes.p5.processed !== null ? (
                              <div className="font-medium">
                                <div>{change.changes.p5.processed?.toFixed(2)}</div>
                                {change.changes.p5.change !== 0 && (
                                  <div className={`text-xs ${change.changes.p5.change_pct > 0 ? 'text-green-600' : 'text-red-600'}`}>({formatChangePct(change.changes.p5.change_pct)})</div>
                                )}
                              </div>
                            ) : (
                              <span className="text-gray-500 dark:text-gray-400">N/A</span>
                            )}
                          </td>
                          <td className={`px-3 py-2 border border-gray-300 dark:border-[#2b2f55] text-center ${getHeatmapColor(change.changes?.p25)}`} style={{ minWidth: '120px' }}>
                            {change.changes?.p25 !== undefined && change.changes.p25.processed !== null ? (
                              <div className="font-medium">
                                <div>{change.changes.p25.processed?.toFixed(2)}</div>
                                {change.changes.p25.change !== 0 && (
                                  <div className={`text-xs ${change.changes.p25.change_pct > 0 ? 'text-green-600' : 'text-red-600'}`}>({formatChangePct(change.changes.p25.change_pct)})</div>
                                )}
                              </div>
                            ) : (
                              <span className="text-gray-500 dark:text-gray-400">N/A</span>
                            )}
                          </td>
                          <td className={`px-3 py-2 border border-gray-300 dark:border-[#2b2f55] text-center ${getHeatmapColor(change.changes?.p50)}`} style={{ minWidth: '120px' }}>
                            {change.changes?.p50 !== undefined && change.changes.p50.processed !== null ? (
                              <div className="font-medium">
                                <div>{change.changes.p50.processed?.toFixed(2)}</div>
                                {change.changes.p50.change !== 0 && (
                                  <div className={`text-xs ${change.changes.p50.change_pct > 0 ? 'text-green-600' : 'text-red-600'}`}>({formatChangePct(change.changes.p50.change_pct)})</div>
                                )}
                              </div>
                            ) : (
                              <span className="text-gray-500 dark:text-gray-400">N/A</span>
                            )}
                          </td>
                          <td className={`px-3 py-2 border border-gray-300 dark:border-[#2b2f55] text-center ${getHeatmapColor(change.changes?.p75)}`} style={{ minWidth: '120px' }}>
                            {change.changes?.p75 !== undefined && change.changes.p75.processed !== null ? (
                              <div className="font-medium">
                                <div>{change.changes.p75.processed?.toFixed(2)}</div>
                                {change.changes.p75.change !== 0 && (
                                  <div className={`text-xs ${change.changes.p75.change_pct > 0 ? 'text-green-600' : 'text-red-600'}`}>({formatChangePct(change.changes.p75.change_pct)})</div>
                                )}
                              </div>
                            ) : (
                              <span className="text-gray-500 dark:text-gray-400">N/A</span>
                            )}
                          </td>
                          <td className={`px-3 py-2 border border-gray-300 dark:border-[#2b2f55] text-center ${getHeatmapColor(change.changes?.p95)}`} style={{ minWidth: '120px' }}>
                            {change.changes?.p95 !== undefined && change.changes.p95.processed !== null ? (
                              <div className="font-medium">
                                <div>{change.changes.p95.processed?.toFixed(2)}</div>
                                {change.changes.p95.change !== 0 && (
                                  <div className={`text-xs ${change.changes.p95.change_pct > 0 ? 'text-green-600' : 'text-red-600'}`}>({formatChangePct(change.changes.p95.change_pct)})</div>
                                )}
                              </div>
                            ) : (
                              <span className="text-gray-500 dark:text-gray-400">N/A</span>
                            )}
                          </td>
                          <td className={`px-3 py-2 border border-gray-300 dark:border-[#2b2f55] text-center ${getHeatmapColor(change.changes?.p99)}`} style={{ minWidth: '120px' }}>
                            {change.changes?.p99 !== undefined && change.changes.p99.processed !== null ? (
                              <div className="font-medium">
                                <div>{change.changes.p99.processed?.toFixed(2)}</div>
                                {change.changes.p99.change !== 0 && (
                                  <div className={`text-xs ${change.changes.p99.change_pct > 0 ? 'text-green-600' : 'text-red-600'}`}>({formatChangePct(change.changes.p99.change_pct)})</div>
                                )}
                              </div>
                            ) : (
                              <span className="text-gray-500 dark:text-gray-400">N/A</span>
                            )}
                          </td>
                          <td className={`px-3 py-2 border border-gray-300 dark:border-[#2b2f55] text-center ${getHeatmapColor(change.changes?.max)}`} style={{ minWidth: '120px' }}>
                            {change.changes?.max !== undefined && change.changes.max.processed !== null ? (
                              <div className="font-medium">
                                <div>{change.changes.max.processed?.toFixed(2)}</div>
                                {change.changes.max.change !== 0 && (
                                  <div className={`text-xs ${change.changes.max.change_pct > 0 ? 'text-green-600' : 'text-red-600'}`}>({formatChangePct(change.changes.max.change_pct)})</div>
                                )}
                              </div>
                            ) : (
                              <span className="text-gray-500 dark:text-gray-400">N/A</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Legend */}
              <div className="mt-3">
                <div className="flex items-center gap-4 text-xs text-gray-600 dark:text-gray-400 flex-wrap">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">Legend:</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="w-4 h-4 bg-green-300 dark:bg-green-900/60 border border-gray-300 dark:border-gray-600"></div>
                    <span>Large Increase</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="w-4 h-4 bg-green-100 dark:bg-green-900/30 border border-gray-300 dark:border-gray-600"></div>
                    <span>Small Increase</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="w-4 h-4 bg-gray-50 dark:bg-[#0f1428] border border-gray-300 dark:border-gray-600"></div>
                    <span>No Change</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="w-4 h-4 bg-red-100 dark:bg-red-900/30 border border-gray-300 dark:border-gray-600"></div>
                    <span>Small Decrease</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="w-4 h-4 bg-red-300 dark:bg-red-900/60 border border-gray-300 dark:border-gray-600"></div>
                    <span>Large Decrease</span>
                  </div>
                </div>
                <div className="mt-2 text-xs text-blue-600 dark:text-blue-300 flex items-center gap-2">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span className="font-medium">Showing all 17 statistics columns - scroll horizontally to view all metrics including percentiles</span>
                </div>
              </div>
            </div>

            {/* Detailed Comparison */}
            <div className="flex-1 overflow-auto p-6">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Detailed Changes</h3>
              <div className="space-y-4">
                {comparisonData.changes
                  .filter((change: any) => change.status !== 'unchanged')
                  .map((change: any, idx: number) => (
                    <div key={idx} className="border border-gray-200 dark:border-gray-800 rounded-lg overflow-hidden">
                      {/* Column Header */}
                      <div className={`px-4 py-2 font-medium flex items-center justify-between ${
                        change.status === 'added' ? 'bg-green-50 text-green-800 dark:bg-green-900/40 dark:text-green-200' :
                        change.status === 'removed' ? 'bg-red-50 text-red-800 dark:bg-red-900/40 dark:text-red-200' :
                        'bg-orange-50 text-orange-800 dark:bg-orange-900/40 dark:text-orange-200'
                      }`}>
                        <span className="flex items-center gap-2">
                          {change.status === 'added' && <span className="text-green-600">✚</span>}
                          {change.status === 'removed' && <span className="text-red-600">✖</span>}
                          {change.status === 'modified' && <span className="text-orange-600">⟳</span>}
                          <span className="font-bold">{change.column_name}</span>
                        </span>
                        <span className="text-xs px-2 py-1 rounded bg-white dark:bg-gray-900 dark:text-gray-200">
                          {change.status.toUpperCase()}
                        </span>
                      </div>

                      {/* Changes Details */}
                      {change.status === 'modified' && change.changes && (
                        <div className="bg-white dark:bg-[#0f1428] p-4">
                          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
                            {Object.entries(change.changes).map(([metric, data]: [string, any]) => {
                              const numericPct = typeof data.change_pct === 'number' && Number.isFinite(data.change_pct)
                                ? data.change_pct
                                : 0;
                              const changeIntensity = Math.min(Math.abs(numericPct) / 100, 1);
                              const heatColor = data.change > 0 
                                ? `rgba(34, 197, 94, ${changeIntensity})` // green
                                : `rgba(239, 68, 68, ${changeIntensity})`; // red

                              return (
                                <div 
                                  key={metric}
                                  className="border border-gray-200 dark:border-gray-700 rounded p-3 text-gray-800 dark:text-gray-200"
                                  style={{ backgroundColor: heatColor }}
                                >
                                  <div className="text-xs font-medium text-gray-700 dark:text-gray-200 mb-2 uppercase">
                                    {metric}
                                  </div>
                                  <div className="space-y-1">
                                    <div className="text-xs text-gray-600 dark:text-gray-300">
                                      Original: <span className="font-bold">{data.original?.toFixed(2) ?? data.original}</span>
                                    </div>
                                    <div className="text-xs text-gray-600 dark:text-gray-300">
                                      Processed: <span className="font-bold">{data.processed?.toFixed(2) ?? data.processed}</span>
                                    </div>
                                    <div className={`text-xs font-bold ${data.change > 0 ? 'text-green-700' : 'text-red-700'}`}>
                                      {typeof data.change === 'number' && Number.isFinite(data.change)
                                        ? `${data.change > 0 ? '+' : ''}${data.change.toFixed(2)}`
                                        : 'N/A'} ({formatChangePct(data.change_pct)})
                                    </div>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      {/* Added/Removed Details */}
                      {(change.status === 'added' || change.status === 'removed') && (
                        <div className="bg-white dark:bg-[#0f1428] p-4 text-gray-800 dark:text-gray-200">
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                            {change.processed && (
                              <>
                                <div><span className="text-gray-600 dark:text-gray-400">Type:</span> <span className="font-medium">{change.processed.type}</span></div>
                                <div><span className="text-gray-600 dark:text-gray-400">Missing:</span> <span className="font-medium">{change.processed.missing}</span></div>
                                <div><span className="text-gray-600 dark:text-gray-400">Unique:</span> <span className="font-medium">{change.processed.unique}</span></div>
                                {change.processed.mean && <div><span className="text-gray-600 dark:text-gray-400">Mean:</span> <span className="font-medium">{change.processed.mean.toFixed(2)}</span></div>}
                              </>
                            )}
                            {change.original && (
                              <>
                                <div><span className="text-gray-600 dark:text-gray-400">Type:</span> <span className="font-medium">{change.original.type}</span></div>
                                <div><span className="text-gray-600 dark:text-gray-400">Missing:</span> <span className="font-medium">{change.original.missing}</span></div>
                                <div><span className="text-gray-600 dark:text-gray-400">Unique:</span> <span className="font-medium">{change.original.unique}</span></div>
                                {change.original.mean && <div><span className="text-gray-600 dark:text-gray-400">Mean:</span> <span className="font-medium">{change.original.mean.toFixed(2)}</span></div>}
                              </>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}

                {comparisonData.changes.filter((c: any) => c.status !== 'unchanged').length === 0 && (
                  <div className="text-center py-12 text-gray-500 dark:text-gray-400">
                    <svg className="w-16 h-16 mx-auto mb-4 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <p className="text-lg font-medium">No changes detected</p>
                    <p className="text-sm mt-2 dark:text-gray-500">The processed dataset is identical to the original</p>
                  </div>
                )}
              </div>
            </div>

            {/* Footer */}
            <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-[#0f1428] flex justify-between items-center">
              <div className="text-xs text-gray-600 dark:text-gray-400">
                Showing {comparisonData.changes.filter((c: any) => c.status !== 'unchanged').length} changed columns
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    // Download comparison as CSV with changes populated
                    const metrics = ['missing', 'unique', 'mean', 'median', 'mode', 'std', 'var', 'min', 'p5', 'p25', 'p50', 'p75', 'p95', 'p99', 'max'];
                    
                    // Build CSV headers
                    const headers = ['Column', 'Status'];
                    metrics.forEach(metric => {
                      headers.push(`${metric}_change`, `${metric}_change_pct`, `${metric}_original`, `${metric}_processed`);
                    });
                    
                    // Build CSV rows
                    const rows = comparisonData.changes.map((change: any) => {
                      const row: string[] = [
                        change.column_name,
                        change.status
                      ];
                      
                      metrics.forEach(metric => {
                        const changeData = change.changes?.[metric];
                        if (changeData) {
                          row.push(
                            changeData.change !== undefined && changeData.change !== null ? String(changeData.change) : 'N/A',
                            changeData.change_pct !== undefined && changeData.change_pct !== null ? String(changeData.change_pct) : 'N/A',
                            changeData.original !== undefined && changeData.original !== null ? String(changeData.original) : 'N/A',
                            changeData.processed !== undefined && changeData.processed !== null ? String(changeData.processed) : 'N/A'
                          );
                        } else {
                          // For added/removed columns, try to get values from original or processed
                          const origVal = change.original?.[metric];
                          const procVal = change.processed?.[metric];
                          row.push(
                            'N/A',  // no change value
                            'N/A',  // no change_pct
                            origVal !== undefined && origVal !== null ? String(origVal) : 'N/A',
                            procVal !== undefined && procVal !== null ? String(procVal) : 'N/A'
                          );
                        }
                      });
                      
                      return row;
                    });
                    
                    // Create CSV content
                    const csvContent = [
                      headers.join(','),
                      ...rows.map((row: string[]) => row.map((cell: string) => `"${String(cell).replace(/"/g, '""')}"`).join(','))
                    ].join('\n');
                    
                    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `comparison_stats_${new Date().toISOString().slice(0, 10)}.csv`;
                    a.click();
                    window.URL.revokeObjectURL(url);
                  }}
                  className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors text-sm"
                >
                  Download CSV
                </button>
                <button
                  onClick={() => setShowComparisonModal(false)}
                  className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors text-sm"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

    </div>

  );

};



export default ModelBuilderRefactored;
