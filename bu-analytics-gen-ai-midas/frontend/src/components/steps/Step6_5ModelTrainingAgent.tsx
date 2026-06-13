import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import {
  Brain,
  Zap,
  Settings,
  BarChart3,
  Download,
  Play,
  CheckCircle,
  AlertCircle,
  FileText,
  Rocket,
  ChevronDown,
  ChevronUp,
  Activity,
  Loader,
  Eye,
  Filter,
  TrendingUp,
  AlertTriangle,
  Lock,
  Unlock,
  Scissors,
  ListChecks,
} from 'lucide-react';
import DataSplit from '../DataSplit';
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  LineChart,
  Line
} from 'recharts';
import JSZip from 'jszip';
import { fastApiService } from '../../services/fastApiService';
import { buildModelSelectionSummary } from '../../utils/modelSelectionSummary';
import { buildMidasAuthHeaders } from '../../services/authHeaders';
import RFEStep from './model_training_rfe/RFEStep';
import FeatureReviewStep from './model_training_rfe/FeatureReviewStep';
import Step6PipelineForkLrSection, { type Step6PipelinePath } from './Step6PipelineForkLrSection';
import ModelScreenerPanel from './ModelScreenerPanel';
import ModelPruningPanel from './ModelPruningPanel';
import CrossAlgorithmRecommendationCard from './CrossAlgorithmRecommendationCard';
import { MtaPreStep6TrainingViz } from './MtaPreStep6TrainingViz';
import {
  fingerprintMtaTrainingResults,
  loadPersistedTrainingResults,
  MTA_TRAINING_RESULTS_PERSISTED_EVENT,
  notifyMtaTrainingResultsPersisted,
  readMtaScreenerPhaseDone,
  resolveNonzeroFeatureCount,
  resolveTrainingBundleUsedFeatures,
  type MtaFlowGate,
} from './modelScreenerUtils';
import type {
  RfeFinalizeResponse,
  RfePrecomputedMetric,
  RfeResultResponse,
  RfeStartRequest,
} from '../../services/rfeService';
import type { MtaSubStep } from './model_training_rfe/shared';
import { useTheme } from '../../contexts/ThemeContext';
import {
  getSoleBestIterationIndexForDisplay,
  MTA_SECTION,
  MTA_STEP_LETTER_BADGE,
  MTA_STEP_NUM,
  MTA_TABLE_SHELL,
  MTA_TITLE_PAGE,
  MTA_TITLE_SECTION,
  MTA_THEAD,
} from './modelTrainingMtaUi';

// Helper function to format metric names for display
const formatMetricName = (metricKey: string): string => {
  const metricNameMap: Record<string, string> = {
    'auc': 'AUC-ROC',
    'auc_roc': 'AUC-ROC',
    'f1_score': 'F1 Score',
    'f1': 'F1 Score',
    'accuracy': 'Accuracy',
    'precision': 'Precision',
    'recall': 'Recall',
    'log_loss': 'Log Loss',
    'test_ks_statistic': 'KS Statistic',
    'r2': 'R² Score',
    'rmse': 'RMSE',
    'mae': 'MAE',
    'mse': 'MSE'
  };
  return metricNameMap[metricKey] || metricKey.replace(/_/g, ' ').toUpperCase();
};

/** Used by background-job polling loops; must be awaited so rejections stay inside try/catch. */
function delayMs(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Target column from Objectives & Data (`dataset_config` in sessionStorage). */
function readDatasetConfigTargetVariable(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = sessionStorage.getItem('dataset_config');
    if (!raw) return null;
    const c = JSON.parse(raw);
    const t = c?.target_variable;
    return typeof t === 'string' && t.trim().length > 0 ? t.trim() : null;
  } catch {
    return null;
  }
}

interface Step6_5ModelTrainingAgentProps {
  // Chat component
  renderStepChat: (step: number) => React.ReactNode;
  // Dataset context
  activeDatasetId?: string;
  // Segment training props
  segmentTrainingMode?: boolean;
  segmentInfo?: any;
  onSegmentInfoUpdate?: (segmentInfo: any) => void;
  targetVariable?: string;
  // Dataset info for Data Split
  datasetAnalysis?: {
    totalRows: number;
  } | null;
  /** Parent navigation (ModelBuilder): gate Model Evaluation / later tabs until MTA flow is complete. */
  onMtaFlowGateChange?: (gate: MtaFlowGate) => void;
}

const Step6_5ModelTrainingAgent: React.FC<Step6_5ModelTrainingAgentProps> = ({
  renderStepChat,
  activeDatasetId,
  segmentTrainingMode = false,
  segmentInfo = null,
  onSegmentInfoUpdate,
  targetVariable,
  datasetAnalysis,
  onMtaFlowGateChange,
}) => {
  const lockedTargetColumn = useMemo(() => {
    const fromConfig = readDatasetConfigTargetVariable();
    if (fromConfig) return fromConfig;
    if (targetVariable != null && String(targetVariable).trim().length > 0) {
      return String(targetVariable).trim();
    }
    return null;
  }, [activeDatasetId, targetVariable]);

  // State management
  // Initialize trainingMode from sessionStorage if available, otherwise use prop
  const [trainingMode, setTrainingMode] = useState<'global' | 'segment-specific'>(() => {
    if (typeof window !== 'undefined' && activeDatasetId) {
      const storedMode = sessionStorage.getItem(`model_training_mode_${activeDatasetId}`);
      if (storedMode === 'global' || storedMode === 'segment-specific') {
        return storedMode;
      }
    }
    // Fallback to prop (original behavior)
    return segmentTrainingMode ? 'segment-specific' : 'global';
  });
  // Initialize activeTab from sessionStorage if available, otherwise default to 'auto'
  const [activeTab, setActiveTab] = useState<'auto' | 'manual'>(() => {
    if (typeof window !== 'undefined' && activeDatasetId) {
      const initialMode = segmentTrainingMode ? 'segment-specific' : 'global';
      const storedTab = sessionStorage.getItem(`model_training_active_tab_${activeDatasetId}_${initialMode}`);
      if (storedTab === 'auto' || storedTab === 'manual') {
        return storedTab;
      }
    }
    return 'auto';
  });
  const { isDark: isDarkMode } = useTheme();

  // Auto training state
  const [autoTargetVariable, setAutoTargetVariable] = useState<string>('');
  const [autoProblemType, setAutoProblemType] = useState<string>('');
  const [autoAnalysisData, setAutoAnalysisData] = useState<any>(null);
  const [autoVariableSelection, setAutoVariableSelection] = useState<any>(null);
  const [autoAlgorithmSelection, setAutoAlgorithmSelection] = useState<any>(null);
  const [autoTrainingResults, setAutoTrainingResults] = useState<any>(null);
  const [step6PipelinePath, setStep6PipelinePath] = useState<Step6PipelinePath>('tree');
  /** On-demand §7.2 audit when user selects the LR fork (separate from training-embedded report). */
  const [step6LrInteractiveReport, setStep6LrInteractiveReport] = useState<any>(null);
  const [step6LrInteractiveLoading, setStep6LrInteractiveLoading] = useState(false);
  const [step6LrInteractiveError, setStep6LrInteractiveError] = useState<string | null>(null);
  // Hoisted from the "VIF and Correlation state" block further down so that
  // the MTA persist/restore effects (which reference these) don't hit a
  // temporal-dead-zone error at render time.
  const [isCalculatingVIF, setIsCalculatingVIF] = useState(false);
  const [vifCorrelationData, setVifCorrelationData] = useState<any>(null);
  // User‑controllable algorithm selection for auto training
  const [autoAlgorithmChoices, setAutoAlgorithmChoices] = useState<Record<string, boolean>>({});
  const [showSelectedVariablesDropdown, setShowSelectedVariablesDropdown] = useState<boolean>(false);
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
  /** Step 1 auto/manual analysis failed (keeps Lock Variables section visible). */
  const [step1LoadError, setStep1LoadError] = useState<string | null>(null);
  const [isAutoTraining, setIsAutoTraining] = useState<boolean>(false);
  const [showAutoVariableAnalysis, setShowAutoVariableAnalysis] = useState<boolean>(false);
  const [variableSelectionMode, setVariableSelectionMode] = useState<'auto' | 'manual'>('auto');
  const [manualVariableSelection, setManualVariableSelection] = useState<Record<string, boolean>>({});
  const [variableSelectionConfirmed, setVariableSelectionConfirmed] = useState<boolean>(false);
  const [lockedVariables, setLockedVariables] = useState<Record<string, boolean>>({});

  // Model Training Agent sub-step navigation for Steps 3 (RFE) and 4 (Feature Review).
  const [mtaSubStep, setMtaSubStep] = useState<MtaSubStep>('screener');
  const [rfeStartPayload, setRfeStartPayload] = useState<RfeStartRequest | null>(null);
  const [rfeActiveJobId, setRfeActiveJobId] = useState<string | null>(null);
  const [rfeResult, setRfeResult] = useState<RfeResultResponse | null>(null);
  const [rfeFinalization, setRfeFinalization] = useState<RfeFinalizeResponse | null>(null);
  /** Bumped when training JSON is written or the tab becomes visible so Step 7 re-reads sessionStorage. */
  const [trainingPersistVersion, setTrainingPersistVersion] = useState(0);

  // Segment Auto Training State
  const [segmentAutoTrainingInProgress, setSegmentAutoTrainingInProgress] = useState<boolean>(false);
  const [segmentAutoTrainingResults, setSegmentAutoTrainingResults] = useState<any>(null);
  const [selectedSegmentFilter, setSelectedSegmentFilter] = useState<string>('all');
  const [segmentAutoStep, setSegmentAutoStep] = useState<'idle' | 'analyzing' | 'training' | 'completed' | 'error'>('idle');

  /** When multiple segmentation_scheme_* columns exist, user-selected column for detect/train */
  const [segmentSchemeColumnOverride, setSegmentSchemeColumnOverride] = useState<string | null>(null);

  // Segment Manual Training Filters
  const [selectedSegmentAlgorithmFilter, setSelectedSegmentAlgorithmFilter] = useState<string>('all');
  const [selectedSegmentManualFilter, setSelectedSegmentManualFilter] = useState<string>('all');

  // Variable Screener Filters (New flexible system)
  const [autoFilterMetric, setAutoFilterMetric] = useState<string>('correlation');
  const [autoFilterOperator, setAutoFilterOperator] = useState<string>('gte');
  const [autoFilterValue, setAutoFilterValue] = useState<string>('');
  const [autoActiveFilters, setAutoActiveFilters] = useState<Array<{metric: string, operator: string, value: number}>>([]);
  
  // Legacy filter states (keep for backward compatibility during transition)
  const [autoVifFilter, setAutoVifFilter] = useState<number | null>(null);
  const [autoCorrelationFilter, setAutoCorrelationFilter] = useState<number | null>(null);
  const [autoIvFilter, setAutoIvFilter] = useState<number | null>(null);

  // CodeBook Modal State
  const [isCodebookOpen, setIsCodebookOpen] = useState<boolean>(false);
  const [codebookContent, setCodebookContent] = useState<string>('');
  const [codebookFileName, setCodebookFileName] = useState<string>('');
  const [isLoadingCodebook, setIsLoadingCodebook] = useState<boolean>(false);

  // Preprocessing Summary State
  const [preprocessingSummaryExpanded, setPreprocessingSummaryExpanded] = useState<boolean>(false);

  // Helper function to get storage key for UI persistence (separate from documentation keys)
  const getResultsStorageKey = (type: 'auto' | 'manual' | 'segment-auto') => {
    if (!activeDatasetId) return null;
    // Use a unique prefix to avoid conflicts with other agents
    return `model_training_ui_results_${activeDatasetId}_${trainingMode}_${type}`;
  };

  // Restore results from sessionStorage on mount or when dataset/mode changes
  useEffect(() => {
    if (!activeDatasetId) return;

    const autoKey = getResultsStorageKey('auto');
    const manualKey = getResultsStorageKey('manual');
    const segmentAutoKey = getResultsStorageKey('segment-auto');

    // Restore auto training results for global mode
    if (trainingMode === 'global' && autoKey) {
      try {
        const stored = sessionStorage.getItem(autoKey);
        if (stored) {
          const parsed = JSON.parse(stored);
          setAutoTrainingResults(parsed);
          console.log('✅ Restored auto training results from sessionStorage');
        }
      } catch (e) {
        console.error('Failed to restore auto training results:', e);
      }
    }

    // Restore segment auto training results for segment-specific mode
    if (trainingMode === 'segment-specific' && segmentAutoKey) {
      try {
        const stored = sessionStorage.getItem(segmentAutoKey);
        if (stored) {
          const parsed = JSON.parse(stored);
          setSegmentAutoTrainingResults(parsed);
          console.log('✅ Restored segment auto training results from sessionStorage');
        }
      } catch (e) {
        console.error('Failed to restore segment auto training results:', e);
      }
    }

    // Restore manual training results (works for both modes)
    if (manualKey) {
      try {
        const stored = sessionStorage.getItem(manualKey);
        if (stored) {
          const parsed = JSON.parse(stored);
          setTrainingResults(parsed);
          
          // Restore algoStatus - if results exist, all algorithms are completed
          if (parsed?.results && Array.isArray(parsed.results)) {
            const restoredStatus: Record<string, 'running' | 'completed'> = {};
            parsed.results.forEach((r: any) => {
              if (r && r.algorithm) {
                restoredStatus[r.algorithm] = 'completed';
              }
            });
            setAlgoStatus(restoredStatus);
            console.log('✅ Restored algoStatus for manual training:', restoredStatus);
          }
          
          console.log('✅ Restored manual training results from sessionStorage');
        }
      } catch (e) {
        console.error('Failed to restore manual training results:', e);
      }
    }

    // Restore activeTab - prioritize user's last selected tab if it has results
    // Priority: stored tab (if has results) > manual results > auto results > default 'auto'
    const tabKey = `model_training_active_tab_${activeDatasetId}_${trainingMode}`;
    try {
      const storedTab = sessionStorage.getItem(tabKey);
      const hasManualResults = manualKey ? !!sessionStorage.getItem(manualKey) : false;
      const hasAutoResults = trainingMode === 'global' 
        ? (autoKey ? !!sessionStorage.getItem(autoKey) : false)
        : (segmentAutoKey ? !!sessionStorage.getItem(segmentAutoKey) : false);
      
      // Priority 1: If stored tab exists and has results for that tab, use it
      if (storedTab === 'manual' && hasManualResults) {
        setActiveTab('manual');
        console.log('✅ Restored to manual tab (user was on manual and has results)');
      }
      else if (storedTab === 'auto' && hasAutoResults) {
        setActiveTab('auto');
        console.log('✅ Restored to auto tab (user was on auto and has results)');
      }
      // Priority 2: If no stored tab preference, check which results exist
      else if (hasManualResults) {
        setActiveTab('manual');
        console.log('✅ Switched to manual tab (manual results found, no stored preference)');
      }
      else if (hasAutoResults) {
        setActiveTab('auto');
        console.log(`✅ Switched to auto tab (${trainingMode} auto results found, no stored preference)`);
      }
      // Priority 3: If no results but stored tab exists, use it
      else if (storedTab === 'auto' || storedTab === 'manual') {
        setActiveTab(storedTab as 'auto' | 'manual');
        console.log(`✅ Restored active tab from sessionStorage: ${storedTab} (no results found)`);
      }
      // Otherwise keep default 'auto'
    } catch (e) {
      console.error('Failed to restore active tab:', e);
    }
  }, [activeDatasetId, trainingMode]);

  // Persist activeTab when it changes
  useEffect(() => {
    if (activeDatasetId) {
      const tabKey = `model_training_active_tab_${activeDatasetId}_${trainingMode}`;
      try {
        sessionStorage.setItem(tabKey, activeTab);
        console.log(`✅ Active tab persisted: ${activeTab}`);
      } catch (e) {
        console.error('Failed to persist active tab:', e);
      }
    }
  }, [activeTab, activeDatasetId, trainingMode]);

  useEffect(() => {
    const bump = (ev: Event) => {
      const d = (ev as CustomEvent<{ datasetId?: string | null }>).detail?.datasetId;
      if (d != null && activeDatasetId != null && String(d) !== String(activeDatasetId)) return;
      setTrainingPersistVersion((n) => n + 1);
    };
    window.addEventListener(MTA_TRAINING_RESULTS_PERSISTED_EVENT, bump as EventListener);
    const onVis = () => {
      if (typeof document !== 'undefined' && document.visibilityState === 'visible') {
        setTrainingPersistVersion((n) => n + 1);
      }
    };
    document.addEventListener('visibilitychange', onVis);
    return () => {
      window.removeEventListener(MTA_TRAINING_RESULTS_PERSISTED_EVENT, bump as EventListener);
      document.removeEventListener('visibilitychange', onVis);
    };
  }, [activeDatasetId]);

  // ------------------------------------------------------------------
  // Persist Step 1 → Step 4 progress (lock / screener / RFE / review) in
  // sessionStorage so that navigating away from the page and back does not
  // discard the activity the user has already done. Keyed by dataset+mode
  // so switching datasets / training modes naturally starts fresh.
  // ------------------------------------------------------------------
  const getMtaStateStorageKey = useCallback(() => {
    if (!activeDatasetId) return null;
    return `model_training_mta_state_${activeDatasetId}_${trainingMode}`;
  }, [activeDatasetId, trainingMode]);

  // Use state to track when restoration is complete so the persist effect
  // doesn't capture a stale initial render closure and overwrite the storage.
  const [restoredMtaKey, setRestoredMtaKey] = useState<string | null>(null);

  // Tracks the last-seen count of auto-selected variables so the
  // "reset-confirmation-on-new-analysis" effect can distinguish a real
  // re-analysis from the initial null -> populated hydration that happens
  // when sessionStorage rehydrates state on page re-entry.
  const prevAutoSelectionLengthRef = useRef<number | null>(null);

  // Restore on mount (or when dataset/mode changes).
  useEffect(() => {
    const key = getMtaStateStorageKey();
    if (!key) return;
    try {
      const raw = sessionStorage.getItem(key);
      if (!raw) {
        setRestoredMtaKey(key);
        return;
      }
      const blob = JSON.parse(raw) as {
        lockedVariables?: Record<string, boolean>;
        autoActiveFilters?: Array<{ metric: string; operator: string; value: number }>;
        manualVariableSelection?: Record<string, boolean>;
        variableSelectionConfirmed?: boolean;
        mtaSubStep?: MtaSubStep;
        rfeStartPayload?: RfeStartRequest | null;
        rfeActiveJobId?: string | null;
        rfeResult?: RfeResultResponse | null;
        rfeFinalization?: RfeFinalizeResponse | null;
        // Step 1 analysis snapshots — restoring these prevents the
        // auto-trigger effect from re-firing the expensive VIF/IV/corr job
        // every time the user leaves and re-enters the Model Training page.
        autoAnalysisData?: any;
        vifCorrelationData?: any;
        autoProblemType?: string | null;
        autoVariableSelection?: any;
        autoAlgorithmSelection?: any;
        autoAlgorithmChoices?: Record<string, boolean>;
        variableSelectionMode?: 'auto' | 'manual';
      };
      if (blob.lockedVariables && typeof blob.lockedVariables === 'object') {
        setLockedVariables(blob.lockedVariables);
      }
      if (Array.isArray(blob.autoActiveFilters)) {
        setAutoActiveFilters(blob.autoActiveFilters);
      }
      if (blob.manualVariableSelection && typeof blob.manualVariableSelection === 'object') {
        setManualVariableSelection(blob.manualVariableSelection);
      }
      if (typeof blob.variableSelectionConfirmed === 'boolean') {
        setVariableSelectionConfirmed(blob.variableSelectionConfirmed);
      }
      if (blob.mtaSubStep) {
        setMtaSubStep(blob.mtaSubStep);
      }
      if (blob.rfeStartPayload !== undefined) {
        setRfeStartPayload(blob.rfeStartPayload);
      }
      if (blob.rfeActiveJobId !== undefined) {
        setRfeActiveJobId(blob.rfeActiveJobId);
      }
      if (blob.rfeResult !== undefined) {
        setRfeResult(blob.rfeResult);
      }
      if (blob.rfeFinalization !== undefined) {
        setRfeFinalization(blob.rfeFinalization);
      }
      if (blob.autoAnalysisData) {
        setAutoAnalysisData(blob.autoAnalysisData);
      }
      if (blob.vifCorrelationData) {
        setVifCorrelationData(blob.vifCorrelationData);
      }
      if (blob.autoProblemType) {
        setAutoProblemType(blob.autoProblemType);
      }
      if (blob.autoVariableSelection) {
        setAutoVariableSelection(blob.autoVariableSelection);
      }
      if (blob.autoAlgorithmSelection) {
        setAutoAlgorithmSelection(blob.autoAlgorithmSelection);
      }
      if (blob.autoAlgorithmChoices && typeof blob.autoAlgorithmChoices === 'object') {
        setAutoAlgorithmChoices(blob.autoAlgorithmChoices);
      }
      if (blob.variableSelectionMode === 'auto' || blob.variableSelectionMode === 'manual') {
        setVariableSelectionMode(blob.variableSelectionMode);
      }
      // Seed the prev-length ref with the restored count so the
      // "reset confirmation on new analysis" effect doesn't interpret
      // the hydration from null -> populated as a real change.
      prevAutoSelectionLengthRef.current =
        blob.autoVariableSelection?.selected_variables?.length ?? null;
      console.log('✅ Restored MTA step state from sessionStorage');
    } catch (e) {
      console.error('Failed to restore MTA step state:', e);
    } finally {
      setRestoredMtaKey(key);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeDatasetId, trainingMode]);

  // Persist whenever any of the tracked fields change. Gated on the restored state so we
  // don't clobber storage with default state before the restore effect above
  // has had a chance to run and commit state updates for this (dataset, mode) combination.
  useEffect(() => {
    const key = getMtaStateStorageKey();
    if (!key) return;
    if (restoredMtaKey !== key) return;
    try {
      const blob = {
        lockedVariables,
        autoActiveFilters,
        manualVariableSelection,
        variableSelectionConfirmed,
        mtaSubStep,
        rfeStartPayload,
        rfeActiveJobId,
        rfeResult,
        rfeFinalization,
        autoAnalysisData,
        vifCorrelationData,
        autoProblemType,
        autoVariableSelection,
        autoAlgorithmSelection,
        autoAlgorithmChoices,
        variableSelectionMode,
      };
      sessionStorage.setItem(key, JSON.stringify(blob));
    } catch (e) {
      // Quota / serialization errors shouldn't break the UI.
      console.error('Failed to persist MTA step state:', e);
    }
  }, [
    getMtaStateStorageKey,
    lockedVariables,
    autoActiveFilters,
    manualVariableSelection,
    variableSelectionConfirmed,
    mtaSubStep,
    rfeStartPayload,
    rfeActiveJobId,
    rfeResult,
    rfeFinalization,
    autoAnalysisData,
    vifCorrelationData,
    autoProblemType,
    autoVariableSelection,
    autoAlgorithmSelection,
    autoAlgorithmChoices,
    variableSelectionMode,
  ]);

  // Sync training mode with prop changes - but prioritize stored mode
  useEffect(() => {
    if (!activeDatasetId) return;
    
    // First check if we have a stored mode (user's last selection)
    const storedMode = sessionStorage.getItem(`model_training_mode_${activeDatasetId}`);
    if (storedMode === 'global' || storedMode === 'segment-specific') {
      // Use stored mode (preserves user's last selection and results)
      setTrainingMode(storedMode);
      return; // Don't override with prop
    }
    
    // Only use prop if no stored mode exists (first visit)
    const newMode = segmentTrainingMode ? 'segment-specific' : 'global';
    setTrainingMode(newMode);
    
    // Persist trainingMode to sessionStorage
    try {
      sessionStorage.setItem(`model_training_mode_${activeDatasetId}`, newMode);
    } catch (e) {
      console.error('Failed to persist training mode:', e);
    }
  }, [segmentTrainingMode, activeDatasetId]);

  // Also persist when user changes mode directly in UI
  useEffect(() => {
    if (activeDatasetId && trainingMode) {
      try {
        sessionStorage.setItem(`model_training_mode_${activeDatasetId}`, trainingMode);
      } catch (e) {
        console.error('Failed to persist training mode:', e);
      }
    }
  }, [trainingMode, activeDatasetId]);

  // Track previous training mode to detect actual mode changes (not just remounts)
  const prevTrainingModeRef = useRef<'global' | 'segment-specific' | null>(null);
  const step1AutoTriggerRef = useRef<Record<string, boolean>>({});
  const step1VifFallbackRef = useRef<Record<string, boolean>>({});

  // Clear results when switching training modes to ensure complete isolation
  // Use useRef to track previous mode to only clear when mode actually changes
  useEffect(() => {
    // Only clear if mode actually changed (not on initial mount)
    const prevMode = prevTrainingModeRef.current;
    const currentMode = trainingMode;
    
    // Update ref for next time
    prevTrainingModeRef.current = currentMode;
    
    // Skip clearing on initial mount (when prevMode is null)
    if (prevMode === null) {
      return;
    }
    
    // Only clear if mode actually changed
    if (prevMode !== currentMode) {
      if (currentMode === 'global') {
      // When switching to global mode, clear segment-specific results
      setSegmentAutoTrainingResults(null);
      setSegmentAutoStep('idle');
        // Clear segment-specific results from storage
        if (activeDatasetId) {
          const segmentAutoKey = `model_training_ui_results_${activeDatasetId}_segment-specific_segment-auto`;
          const segmentManualKey = `model_training_ui_results_${activeDatasetId}_segment-specific_manual`;
          try {
            sessionStorage.removeItem(segmentAutoKey);
            sessionStorage.removeItem(segmentManualKey);
          } catch (e) {
            console.error('Failed to clear segment results from storage:', e);
          }
        }
      } else if (currentMode === 'segment-specific') {
      // When switching to segment-specific mode, clear global results
      setAutoTrainingResults(null);
        // Clear global results from storage
        if (activeDatasetId) {
          const autoKey = `model_training_ui_results_${activeDatasetId}_global_auto`;
          const manualKey = `model_training_ui_results_${activeDatasetId}_global_manual`;
          try {
            sessionStorage.removeItem(autoKey);
            sessionStorage.removeItem(manualKey);
          } catch (e) {
            console.error('Failed to clear global results from storage:', e);
          }
        }
      }
      
      // Only clear manual training results state when mode actually changes
    setTrainingResults(null);
    // Clear post-modelling preview data when switching modes
    setPostModellingPreviewData(null);
    setShowPostModellingPreview(false);
    }
  }, [trainingMode, activeDatasetId]);

  // Clear preview when switching tabs (auto/manual) within same mode
  useEffect(() => {
    setPostModellingPreviewData(null);
    setShowPostModellingPreview(false);
  }, [activeTab]);

  // Update auto target variable when dataset config changes
  useEffect(() => {
    if (targetVariable) {
      setAutoTargetVariable(targetVariable);
    }
  }, [targetVariable]);

  // Debug logging for segment info
  useEffect(() => {
    console.log('🔧 ModelTrainingAgent - segmentInfo prop:', segmentInfo);
    console.log('🔧 ModelTrainingAgent - segmentTrainingMode prop:', segmentTrainingMode);
    console.log('🔧 ModelTrainingAgent - trainingMode state:', trainingMode);
  }, [segmentInfo, segmentTrainingMode, trainingMode]);

  // Trigger segment detection when training mode changes to segment-specific
  useEffect(() => {
    if (trainingMode === 'segment-specific' && activeDatasetId && !segmentInfo) {
      detectSegmentsForDataset();
    }
  }, [trainingMode]);

  // Detect segments when switching to manual tab
  useEffect(() => {
    if (activeTab === 'manual' && activeDatasetId && !segmentInfo) {
      detectSegmentsForDataset();
    }
  }, [activeTab, activeDatasetId]);

  // Function to detect segments in the dataset
  const detectSegmentsForDataset = async (schemeColumn?: string | null) => {
    if (!activeDatasetId) return;

    try {
      const segmentDetectionResult = await fastApiService.detectSegments({
        dataset_id: activeDatasetId,
        ...(schemeColumn ? { segment_column: schemeColumn } : {}),
      });

      if (segmentDetectionResult.available) {
        // Update parent component with segment info
        console.log('Segments detected:', segmentDetectionResult);
        if (onSegmentInfoUpdate) {
          onSegmentInfoUpdate(segmentDetectionResult);
        }
        if (schemeColumn) {
          setSegmentSchemeColumnOverride(schemeColumn);
        } else if (segmentDetectionResult.segment_column) {
          setSegmentSchemeColumnOverride(segmentDetectionResult.segment_column);
        }
      } else {
        console.log('No segments detected:', segmentDetectionResult.message);
        // Update parent component to indicate no segments found
        if (onSegmentInfoUpdate) {
          onSegmentInfoUpdate(segmentDetectionResult);
        }
      }
    } catch (error) {
      console.error('Error detecting segments:', error);
    }
  };

  useEffect(() => {
    if (segmentInfo?.segment_column) {
      setSegmentSchemeColumnOverride((prev) => prev ?? segmentInfo.segment_column);
    }
  }, [segmentInfo?.segment_column]);
  const [selectedAlgorithm, setSelectedAlgorithm] = useState('xgboost');
  const [optimizationMetric, setOptimizationMetric] = useState('auc');
  // Keep these for training progress display
  const [numTrials] = useState(50);
  const [cvFolds] = useState(5);
  // Removed unused state variables for cleaner code
  
  // Dataset preview state
  const [showDatasetPreview, setShowDatasetPreview] = useState(true);
  const [datasetPreviewData, setDatasetPreviewData] = useState<{
    shape: { rows: number; columns: number };
    hasSegmentColumn: boolean;
    preview: Record<string, any>[];
    columns: string[];
  } | null>(null);

  // Post Modelling Dataset Preview state
  const [showPostModellingPreview, setShowPostModellingPreview] = useState(false);
  const [postModellingPreviewData, setPostModellingPreviewData] = useState<{
    shape: { rows: number; columns: number };
    hasSegmentColumn: boolean;
    preview: Record<string, any>[];
    columns: string[];
  } | null>(null);
  
  // Training state
  const [isTraining, setIsTraining] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [currentTrial, setCurrentTrial] = useState(0);
  const [bestScore, setBestScore] = useState(0);
  const [currentScore] = useState(0);
  const [showResults, setShowResults] = useState(false);
  
  // Real-time training logs
  const [trainingLogs, setTrainingLogs] = useState<string[]>([]);
  const [isReceivingLogs, setIsReceivingLogs] = useState(false);
  
  // Auto training steps state
  const [currentAutoStep, setCurrentAutoStep] = useState(0);
  const [autoStepsCompleted, setAutoStepsCompleted] = useState<boolean[]>([false, false, false, false]);
  
  // Variable selection state (for auto training)
  const [selectedIndependentVariables, setSelectedIndependentVariables] = useState<string[]>([]);
  const [availableVariables, setAvailableVariables] = useState<string[]>([]);
  const [isIndependentDropdownOpen, setIsIndependentDropdownOpen] = useState(false);
  const [independentSearchTerm, setIndependentSearchTerm] = useState('');
  const [problemType, setProblemType] = useState<'classification' | 'regression' | null>(null);
  const [metricValue, setMetricValue] = useState<string>('');

  // Initialize state from sessionStorage (Objectives and Data section)
  useEffect(() => {
    console.log('Initializing from sessionStorage...');
    const datasetConfigStr = sessionStorage.getItem('dataset_config');
    console.log('SessionStorage dataset_config:', datasetConfigStr);
    if (datasetConfigStr) {
      try {
        const datasetConfig = JSON.parse(datasetConfigStr);
        console.log('Parsed dataset config:', datasetConfig);
        if (datasetConfig.target_variable && !autoTargetVariable) {
          console.log('Setting target variable from sessionStorage:', datasetConfig.target_variable);
          setAutoTargetVariable(datasetConfig.target_variable);
        }
        if (datasetConfig.dataset_structure_type) {
          const structureType = datasetConfig.dataset_structure_type;
          console.log('Setting problem type from sessionStorage:', structureType);
          if ((structureType === 'classification' || structureType === 'regression') && !problemType) {
            setProblemType(structureType);
          }
        }

        // Set manual target variable and problem type (only if not already set)
        if (datasetConfig.target_variable && !manualTargetVariable) {
          console.log('Setting manual target variable from sessionStorage:', datasetConfig.target_variable);
          setManualTargetVariable(datasetConfig.target_variable);
        }

        if (datasetConfig.dataset_structure_type) {
          const structureType = datasetConfig.dataset_structure_type;
          console.log('Setting manual problem type from sessionStorage:', structureType);
          if ((structureType === 'classification' || structureType === 'regression') && !manualProblemType) {
            setManualProblemType(structureType);
          }
        }
      } catch (error) {
        console.error('Error parsing dataset config:', error);
      }
    }
  }, []);

  // Reset confirmation when auto-selected variables change to a NEW value.
  // We compare the previous length against the current one, skipping the
  // null -> populated transition that happens on initial mount / restore-
  // from-sessionStorage (otherwise we'd wipe the persisted confirmation on
  // every revisit to the Model Training page). The ref itself is declared
  // higher up next to `restoredMtaKey` so the restore effect can seed it.
  useEffect(() => {
    const currentLength = autoVariableSelection?.selected_variables?.length ?? null;
    const prevLength = prevAutoSelectionLengthRef.current;
    prevAutoSelectionLengthRef.current = currentLength;

    if (
      prevLength !== null &&
      currentLength !== null &&
      prevLength !== currentLength &&
      variableSelectionMode === 'auto'
    ) {
      setVariableSelectionConfirmed(false);
    }
  }, [autoVariableSelection?.selected_variables?.length, variableSelectionMode]);

  // Close dropdown when switching modes
  useEffect(() => {
    if (variableSelectionMode === 'manual') {
      setShowSelectedVariablesDropdown(false);
    }
  }, [variableSelectionMode]);

  const [trainingResults, setTrainingResults] = useState<any>(null);
  const [showDownloadMenu, setShowDownloadMenu] = useState(false);
  const [showShortlistDrawer, setShowShortlistDrawer] = useState(false);
  const [shortlistSelection, setShortlistSelection] = useState<Record<string, boolean>>({});
  const [shortlistConfirmed, setShortlistConfirmed] = useState(false);
  const [lastUsedVariables, setLastUsedVariables] = useState<string[]>([]);

  // Variable selection state (for manual configuration)
  const [manualTargetVariable, setManualTargetVariable] = useState<string>('');
  useEffect(() => {
    if (!lockedTargetColumn) return;
    setManualTargetVariable((v) => (v === lockedTargetColumn ? v : lockedTargetColumn));
    setAutoTargetVariable((v) => (v === lockedTargetColumn ? v : lockedTargetColumn));
  }, [lockedTargetColumn]);
  const [manualSelectedIndependentVariables, setManualSelectedIndependentVariables] = useState<string[]>([]);
  const [manualIsIndependentDropdownOpen, setManualIsIndependentDropdownOpen] = useState(false);
  const [manualIndependentSearchTerm, setManualIndependentSearchTerm] = useState('');
  const [manualProblemType, setManualProblemType] = useState<'classification' | 'regression' | null>(null);


  // Max iterations for advanced settings
  const [maxIterations, setMaxIterations] = useState<number>(3); // Optimized: Reduced from 5 to 3 for faster training

  // Selected algorithm for detailed history view
  const [selectedAlgorithmForHistory, setSelectedAlgorithmForHistory] = useState<string>('');
  
  // Selected segment for iteration history filtering
  const [selectedSegmentForHistory, setSelectedSegmentForHistory] = useState<string>('all');

  // Comparison tab state
  const [comparisonTab, setComparisonTab] = useState<'score' | 'history'>('score');

  // Selected algorithms for comparison
  const [selectedAlgorithmsForComparison, setSelectedAlgorithmsForComparison] = useState<string[]>([]);
  const [expandedLrSignRows, setExpandedLrSignRows] = useState<Record<string, boolean>>({});
  
  // Interactive Algorithm Comparison Filters
  const [comparisonAlgorithmFilter, setComparisonAlgorithmFilter] = useState<string>('all');
  const [comparisonSegmentFilter, setComparisonSegmentFilter] = useState<string>('all');

  /** Unified training payload for Step 5 outcomes — prefer the tab that owns the run (manual vs auto). */
  const mtaPreStep6VizResults = useMemo(() => {
    if (trainingMode === 'segment-specific') {
      if (activeTab === 'auto') {
        return segmentAutoTrainingResults || trainingResults || null;
      }
      return trainingResults || segmentAutoTrainingResults || null;
    }
    if (activeTab === 'auto') {
      return autoTrainingResults || trainingResults || null;
    }
    return trainingResults || autoTrainingResults || null;
  }, [activeTab, trainingMode, trainingResults, autoTrainingResults, segmentAutoTrainingResults]);

  // Set default selected algorithm when results are available (prefer best model when known)
  useEffect(() => {
    const results = mtaPreStep6VizResults;
    if (!results) return;

    const flatAlgos: string[] = Array.isArray(results.results)
      ? results.results.map((r: any) => String(r?.algorithm || '').trim()).filter(Boolean)
      : [];

    const bestAlgoRaw = results.best_model_selection?.best_algorithm;
    const bestAlgo = typeof bestAlgoRaw === 'string' ? bestAlgoRaw.trim() : '';
    const bestModelId = results.best_model_selection?.best_model_id;

    const resolveDefaultFlat = (): string => {
      if (flatAlgos.length === 0) return '';
      if (bestAlgo) {
        const exact = flatAlgos.find((a) => a === bestAlgo);
        if (exact) return exact;
        const ci = flatAlgos.find((a) => a.toLowerCase() === bestAlgo.toLowerCase());
        if (ci) return ci;
      }
      if (typeof bestModelId === 'string' && bestModelId && Array.isArray(results.results)) {
        const row = results.results.find((r: any) => r?.model_id === bestModelId);
        if (row?.algorithm) return String(row.algorithm);
      }
      if (flatAlgos.length === 1) return flatAlgos[0];
      return '';
    };

    if (flatAlgos.length > 0) {
      const desired = resolveDefaultFlat();
      const currentOk =
        !!selectedAlgorithmForHistory && flatAlgos.includes(selectedAlgorithmForHistory);
      if (desired && (!selectedAlgorithmForHistory || !currentOk)) {
        setSelectedAlgorithmForHistory(desired);
        return;
      }
    }

    if (results.segment_results) {
      const bestAlgoSeg = bestAlgo;
      const algoSet = new Set<string>();
      Object.values(results.segment_results).forEach((segResult: any) => {
        segResult?.results?.forEach((r: any) => {
          if (r?.algorithm) algoSet.add(String(r.algorithm));
        });
      });
      const list = Array.from(algoSet);
      if (bestAlgoSeg) {
        const hit =
          list.find((a) => a === bestAlgoSeg) ||
          list.find((a) => a.toLowerCase() === bestAlgoSeg.toLowerCase());
        if (hit && (!selectedAlgorithmForHistory || !list.includes(selectedAlgorithmForHistory))) {
          setSelectedAlgorithmForHistory(hit);
          return;
        }
      }
      if (list.length === 1 && !selectedAlgorithmForHistory) {
        setSelectedAlgorithmForHistory(list[0]);
      }
    }
  }, [mtaPreStep6VizResults, selectedAlgorithmForHistory]);

  // Set default selected algorithms for comparison when results are available
  useEffect(() => {
    const results = mtaPreStep6VizResults;
    if (!results) return;

    if (results.results?.length) {
      const algorithms = results.results.map((r: any) => r.algorithm);
      setSelectedAlgorithmsForComparison(algorithms);
      return;
    }

    if (results.segment_results) {
      const algorithms = new Set<string>();
      Object.values(results.segment_results).forEach((segResult: any) => {
        segResult?.results?.forEach((r: any) => {
          if (r?.algorithm) algorithms.add(r.algorithm);
        });
      });
      if (algorithms.size > 0) {
        setSelectedAlgorithmsForComparison(Array.from(algorithms));
      }
    }
  }, [mtaPreStep6VizResults]);

  // Function to handle model export
  const handleModelExport = async (model: any) => {
    try {
      // Call backend API to export model
      const exportData = await fastApiService.exportModel({
        model_id: model.model_id,
        include_artifacts: true
      });

      // Create files for download
      const files = exportData.files || [];

      if (files.length === 0) {
        alert('No files available for export');
        return;
      }

      // Create a zip file containing all the exported files
      const zip = new JSZip();

      files.forEach((file: any) => {
        zip.file(file.filename, file.content, { base64: true });
      });

      // Generate zip file
      const zipBlob = await zip.generateAsync({ type: 'blob' });

      // Create download link
      const url = URL.createObjectURL(zipBlob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `model_${model.model_id}_${model.algorithm.toLowerCase()}_export.zip`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);

    } catch (error) {
      console.error('Export failed:', error);
      alert(`Export failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  // Function to get available metrics for the current problem type
  const getAvailableMetrics = () => {
    const r = mtaPreStep6VizResults;
    if (!r) return [];

    let firstResult: any = null;
    if (r.results?.length) {
      firstResult = r.results[0];
    } else if (r.segment_results) {
      for (const seg of Object.values(r.segment_results) as any[]) {
        if (seg?.results?.length) {
          firstResult = seg.results[0];
          break;
        }
      }
    }
    if (!firstResult) return [];

    const metrics = firstResult.metrics || {};
    const pt = r.problem_type || 'classification';

    if (pt === 'regression') {
      return Object.keys(metrics).filter(key =>
        ['r2', 'adjusted_r2', 'mae', 'mse', 'rmse'].includes(key) && metrics[key] != null && !isNaN(metrics[key])
      );
    }
    return Object.keys(metrics).filter(key =>
      ['accuracy', 'auc', 'f1', 'precision', 'recall', 'log_loss', 'ks_statistic'].includes(key) && metrics[key] != null && !isNaN(metrics[key])
    );
  };

  // Function to prepare data for score comparison chart with filtering support
  const getScoreComparisonData = () => {
    const trainingBundle = mtaPreStep6VizResults;
    const hasFlat = Array.isArray(trainingBundle?.results) && trainingBundle.results.length > 0;
    const hasSeg = trainingBundle?.segment_results && Object.keys(trainingBundle.segment_results).length > 0;
    if (!trainingBundle || (!hasFlat && !hasSeg)) return [];

    const availableMetrics = getAvailableMetrics();
    let resultsToProcess = [];

    // Handle segment training vs regular training
    if (trainingBundle.segment_results) {
      // Segment training - apply filters
      const segmentsToProcess = comparisonSegmentFilter === 'all' 
        ? trainingBundle.segments || []
        : [comparisonSegmentFilter];

      for (const segmentId of segmentsToProcess) {
        const segmentKey = `segment_${segmentId}`;
        const segmentResult = trainingBundle.segment_results[segmentKey];
        
        if (segmentResult && segmentResult.results) {
          segmentResult.results.forEach((result: any) => {
            // Apply algorithm filter
            if (comparisonAlgorithmFilter === 'all' || result.algorithm === comparisonAlgorithmFilter) {
              resultsToProcess.push({
                ...result,
                segment_id: segmentId,
                display_name: comparisonSegmentFilter === 'all' 
                  ? `${result.algorithm.toUpperCase()} (${segmentId})`
                  : result.algorithm.toUpperCase()
              });
            }
          });
        }
      }
    } else {
      // Regular training - use existing logic
      resultsToProcess = trainingBundle.results.map((result: any) => ({
        ...result,
        display_name: result.algorithm.toUpperCase()
      }));
    }

    return resultsToProcess.map((result: any) => {
      const bestMetrics = getBestMetricsFromHistory(result);
      const dataPoint: any = { algorithm: result.display_name };

      availableMetrics.forEach(metric => {
        dataPoint[metric] = bestMetrics[metric] || 0;
      });

      return dataPoint;
    });
  };

  // Function to prepare data for training history chart with filtering support
  const getTrainingHistoryData = (): Array<{iteration: number, [key: string]: number}> => {
    const results = mtaPreStep6VizResults;
    if (!results?.results && !results?.segment_results) return [];

    const dataMap: Record<string, Array<{iteration: number, score: number}>> = {};
    let resultsToProcess = [];

    // Handle segment training vs regular training
    if (results.segment_results) {
      // Segment training - apply filters
      const segmentsToProcess = comparisonSegmentFilter === 'all' 
        ? results.segments || []
        : [comparisonSegmentFilter];

      for (const segmentId of segmentsToProcess) {
        const segmentKey = `segment_${segmentId}`;
        const segmentResult = results.segment_results[segmentKey];
        
        if (segmentResult && segmentResult.results) {
          segmentResult.results.forEach((result: any) => {
            // Apply algorithm filter
            if (comparisonAlgorithmFilter === 'all' || result.algorithm === comparisonAlgorithmFilter) {
              resultsToProcess.push({
                ...result,
                segment_id: segmentId,
                display_name: comparisonSegmentFilter === 'all' 
                  ? `${result.algorithm.toUpperCase()} (${segmentId})`
                  : result.algorithm.toUpperCase()
              });
            }
          });
        }
      }
    } else {
      // Regular training - use existing logic
      resultsToProcess = results.results.map((result: any) => ({
        ...result,
        display_name: result.algorithm.toUpperCase()
      }));
    }

    resultsToProcess.forEach((result: any) => {
      if (selectedAlgorithmsForComparison.includes(result.algorithm) && result.iteration_history && Array.isArray(result.iteration_history)) {
        const algorithmData: Array<{iteration: number, score: number}> = [];

        // Use real iteration history data from the backend
        result.iteration_history.forEach((iteration: any, index: number) => {
          // Enhanced problem type detection for segment training
          let pt = results.problem_type;
          
          if (!pt && results.segment_results) {
            const firstSegmentResult = Object.values(results.segment_results)[0] as any;
            if (firstSegmentResult && firstSegmentResult.results && firstSegmentResult.results.length > 0) {
              const firstModel = firstSegmentResult.results[0];
              if (firstModel.metrics) {
                if (firstModel.metrics.auc !== undefined || firstModel.metrics.precision !== undefined || firstModel.metrics.recall !== undefined) {
                  pt = 'classification';
                } else if (firstModel.metrics.r2 !== undefined || firstModel.metrics.rmse !== undefined) {
                  pt = 'regression';
                }
              }
            }
          }
          
          if (!pt) {
            pt = 'classification';
          }

          const scoreKey = getPrimaryMetricKey(pt, targetMetricManual);
          const score = iteration.metrics?.[scoreKey] !== undefined ?
            iteration.metrics[scoreKey] :
            (typeof iteration.score === 'number' ? iteration.score : 0);

          algorithmData.push({
            iteration: iteration.iteration || (index + 1),
            score: score,
          });
        });

        dataMap[result.display_name] = algorithmData;
      }
    });

    // Create a single dataset with iterations, and scores for each algorithm
    const maxIterations = Math.max(...Object.values(dataMap).map(algData => algData.length), 0);
    const chartData: Array<{iteration: number, [key: string]: number}> = [];

    for (let i = 1; i <= maxIterations; i++) {
      const dataPoint: {iteration: number, [key: string]: number} = { iteration: i };

      Object.entries(dataMap).forEach(([algorithm, algData]) => {
        const iterationData = algData.find(d => d.iteration === i);
        if (iterationData) {
          dataPoint[algorithm] = iterationData.score;
        }
      });

      chartData.push(dataPoint);
    }

    return chartData;
  };

  // Function to get unique algorithms for chart rendering with filtering support
  const getSelectedAlgorithms = (): string[] => {
    const results = mtaPreStep6VizResults;
    if (!results?.results && !results?.segment_results) return [];

    let resultsToProcess = [];

    // Handle segment training vs regular training
    if (results.segment_results) {
      // Segment training - apply filters
      const segmentsToProcess = comparisonSegmentFilter === 'all' 
        ? results.segments || []
        : [comparisonSegmentFilter];

      for (const segmentId of segmentsToProcess) {
        const segmentKey = `segment_${segmentId}`;
        const segmentResult = results.segment_results[segmentKey];
        
        if (segmentResult && segmentResult.results) {
          segmentResult.results.forEach((result: any) => {
            // Apply algorithm filter
            if (comparisonAlgorithmFilter === 'all' || result.algorithm === comparisonAlgorithmFilter) {
              resultsToProcess.push({
                ...result,
                segment_id: segmentId,
                display_name: comparisonSegmentFilter === 'all' 
                  ? `${result.algorithm.toUpperCase()} (${segmentId})`
                  : result.algorithm.toUpperCase()
              });
            }
          });
        }
      }
    } else {
      // Regular training - use existing logic
      resultsToProcess = results.results.map((result: any) => ({
        ...result,
        display_name: result.algorithm.toUpperCase()
      }));
    }

    return Array.from(new Set(
      resultsToProcess
        .filter((result: any) => selectedAlgorithmsForComparison.includes(result.algorithm))
        .map((result: any) => result.display_name)
    ));
  };

  // Function to get the best score from iteration history
  const getBestScoreFromHistory = (result: any, targetMetric: string = ''): number => {
    if (!result.iteration_history || !Array.isArray(result.iteration_history) || result.iteration_history.length === 0) {
      return 0;
    }

    const pt = mtaPreStep6VizResults?.problem_type || 'classification';
    const scoreKey = getPrimaryMetricKey(pt, targetMetric);

    // Find the highest score in the iteration history for the selected metric
    return Math.max(...result.iteration_history.map((iteration: any) => {
      const score = iteration.metrics?.[scoreKey] !== undefined ?
        iteration.metrics[scoreKey] :
        (typeof iteration.score === 'number' ? iteration.score : 0);
      return score;
    }));
  };

  // Function to get the best metrics from iteration history
  const getBestMetricsFromHistory = (result: any, targetMetric: string = ''): any => {
    if (!result.iteration_history || !Array.isArray(result.iteration_history) || result.iteration_history.length === 0) {
      return result.metrics || {};  // Return top-level metrics as fallback
    }

    const pt = mtaPreStep6VizResults?.problem_type || 'classification';
    const scoreKey = getPrimaryMetricKey(pt, targetMetric);

    const bestIteration = result.iteration_history.reduce((best: any, current: any) => {
      const currentScore = current.metrics?.[scoreKey] !== undefined ?
        current.metrics[scoreKey] :
        (typeof current.score === 'number' ? current.score : 0);
      const bestScore = best.metrics?.[scoreKey] !== undefined ?
        best.metrics[scoreKey] :
        (typeof best.score === 'number' ? best.score : 0);

      return currentScore > bestScore ? current : best;
    }, {});

    // Merge iteration metrics with top-level result metrics to include final metrics like feature_importance_count
    return {
      ...result.metrics,  // Include top-level metrics first
      ...(bestIteration.metrics || {})  // Override with best iteration's metrics if they exist
    };
  };
  
  // VIF and Correlation state
  // Note: `isCalculatingVIF` and `vifCorrelationData` are hoisted to the top
  // of the component (alongside auto-training state) because the MTA
  // persist/restore effects reference them before this point in the file.
  // Declaring them here again would shadow the hoisted version and would
  // also re-introduce a TDZ error for the earlier effects.
  const [showVifPreview, setShowVifPreview] = useState(false);
  const [variableFilters, setVariableFilters] = useState<Array<{
    metric: 'correlation' | 'vif' | 'iv';
    operator: '>=' | '<=' | 'between' | '==';
    value: string;      // keep raw user input for smooth typing
    valueMax?: string;  // raw input for max when 'between'
  }>>([{ metric: 'correlation', operator: '>=', value: '0.1' }]);
  const [filteredVariables, setFilteredVariables] = useState<string[]>([]);

  // Helper function to get metric display name
  const getMetricDisplayName = (metricKey: string): string => {
    const metricMap: Record<string, string> = {
      // Base metrics (existing)
      'auc': 'AUC-ROC',
      'f1': 'F1-Score',
      'precision': 'Precision',
      'recall': 'Recall',
      'accuracy': 'Accuracy',
      'log_loss': 'Log Loss',
      'ks_statistic': 'KS Statistic',
      'r2': 'R²',
      'adjusted_r2': 'Adjusted R²',
      'mae': 'MAE',
      'mse': 'MSE',
      'rmse': 'RMSE',
      
      // NEW: Train metrics
      'train_accuracy': 'Accuracy (Train)',
      'train_precision': 'Precision (Train)',
      'train_recall': 'Recall (Train)',
      'train_f1_score': 'F1-Score (Train)',
      'train_auc': 'AUC-ROC (Train)',
      'train_log_loss': 'Log Loss (Train)',
      'train_ks_statistic': 'KS Statistic (Train)',
      
      // NEW: Test metrics
      'test_accuracy': 'Accuracy (Test)',
      'test_precision': 'Precision (Test)',
      'test_recall': 'Recall (Test)',
      'test_f1_score': 'F1-Score (Test)',
      'test_auc': 'AUC-ROC (Test)',
      'test_log_loss': 'Log Loss (Test)',
      'test_ks_statistic': 'KS Statistic (Test)',
      
      // NEW: Regression train/test metrics
      'train_r2': 'R² (Train)',
      'test_r2': 'R² (Test)',
      'train_mae': 'MAE (Train)',
      'test_mae': 'MAE (Test)',
      'train_mse': 'MSE (Train)',
      'test_mse': 'MSE (Test)',
      'train_rmse': 'RMSE (Train)',
      'test_rmse': 'RMSE (Test)',
      
      // NEW: Difference metrics
      'accuracy_diff': 'Accuracy Difference (%)',
      'auc_diff': 'AUC Difference (%)',
      'ks_statistic_diff': 'KS Statistic Difference (%)',
      
      // NEW: Feature Importance
      'feature_importance_count': 'Feature Importance Count',
    };
    return metricMap[metricKey] || metricKey.replace('_', ' ').toUpperCase();
  };

  // Helper function to get the primary metric key based on selected target metric
  const getPrimaryMetricKey = (problemType: string, targetMetric: string = ''): string => {
    if (!targetMetric) {
      // Default to AUC for classification, R² for regression if no target metric selected
      return problemType === 'classification' ? 'auc' : 'r2';
    }

    // Map target metric values to metric keys
    const metricMapping: Record<string, string> = {
      'auc': 'auc',
      'f1': 'f1',
      'precision': 'precision',
      'recall': 'recall',
      'accuracy': 'accuracy',
      'log_loss': 'log_loss',
      'r2': 'r2',
      'mae': 'mae',
      'mse': 'mse',
      'rmse': 'rmse'
    };

    return metricMapping[targetMetric] || (problemType === 'classification' ? 'auc' : 'r2');
  };

  // Helper function to get secondary metrics to display (excluding the primary metric)
  const getSecondaryMetrics = (problemType: string, primaryMetricKey: string): string[] => {
    if (problemType === 'classification') {
      const allMetrics = ['auc', 'f1', 'precision', 'recall', 'accuracy'];
      return allMetrics.filter(metric => metric !== primaryMetricKey);
    } else {
      const allMetrics = ['r2', 'adjusted_r2', 'mae', 'mse', 'rmse'];
      return allMetrics.filter(metric => metric !== primaryMetricKey);
    }
  };

  const formatStep6Number = (value: any, digits: number = 4): string => {
    return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : 'N/A';
  };

  const getFirstFiniteMetric = (metricObj: any, keys: string[]): number | null => {
    if (!metricObj || typeof metricObj !== 'object') return null;
    for (const key of keys) {
      const raw = metricObj[key];
      if (raw === null || raw === undefined) continue;
      if (typeof raw === 'string' && raw.trim() === '') continue;
      const val = typeof raw === 'number' ? raw : Number(raw);
      if (Number.isFinite(val)) return val;
    }
    return null;
  };

  const calcStep6OverfitPct = (trainVal: number | null, testVal: number | null): number | null => {
    if (trainVal === null || testVal === null || trainVal === 0) return null;
    return ((trainVal - testVal) / Math.abs(trainVal)) * 100.0;
  };

  /** Non-zero feature slots vs total design-matrix features (matches backend ``feature_importance_count`` / ``feature_count``). */
  const formatStep6NonZeroRatio = (nonZero: number | null, total: number | null): string => {
    if (nonZero !== null && total !== null && total > 0) return `${Math.round(nonZero)}/${Math.round(total)}`;
    if (nonZero !== null) return `${Math.round(nonZero)}`;
    return 'N/A';
  };

  const getStep6ViewsForDisplay = (results: any): any => {
    if (!results || typeof results !== 'object') return null;

    if (results.step6_views && typeof results.step6_views === 'object') {
      return results.step6_views;
    }

    if (!results.segment_results || typeof results.segment_results !== 'object') {
      return null;
    }

    const merged: any = {
      base_model_results: [] as any[],
      bayesian_summary: [] as any[],
      lr_backward_elimination_report: null as any,
      recommendations: {
        g1_overfit_aware: [] as any[],
        g2_test_only: [] as any[],
        lr_sign_validation: [] as any[],
      },
    };

    Object.entries(results.segment_results).forEach(([segmentKey, segmentPayload]: [string, any]) => {
      const segmentId = String(segmentKey || '').replace('segment_', '');
      const step6 = segmentPayload?.step6_views;
      if (!step6) return;

      if (!merged.lr_backward_elimination_report && step6.lr_backward_elimination_report) {
        merged.lr_backward_elimination_report = { ...step6.lr_backward_elimination_report, segment_id: segmentId };
      }

      if (Array.isArray(step6.base_model_results)) {
        step6.base_model_results.forEach((row: any) => {
          merged.base_model_results.push({ ...row, segment_id: segmentId });
        });
      }
      if (Array.isArray(step6.bayesian_summary)) {
        step6.bayesian_summary.forEach((row: any) => {
          merged.bayesian_summary.push({ ...row, segment_id: segmentId });
        });
      }

      const rec = step6.recommendations || {};
      if (Array.isArray(rec.g1_overfit_aware)) {
        rec.g1_overfit_aware.forEach((row: any) => {
          merged.recommendations.g1_overfit_aware.push({ ...row, segment_id: segmentId });
        });
      }
      if (Array.isArray(rec.g2_test_only)) {
        rec.g2_test_only.forEach((row: any) => {
          merged.recommendations.g2_test_only.push({ ...row, segment_id: segmentId });
        });
      }
      if (Array.isArray(rec.lr_sign_validation)) {
        rec.lr_sign_validation.forEach((row: any) => {
          merged.recommendations.lr_sign_validation.push({ ...row, segment_id: segmentId });
        });
      }
    });

    return merged;
  };

  // Helper function to calculate train-test difference percentage
  const calculateTrainTestDifference = (trainValue: number, testValue: number): number => {
    if (testValue === 0 || testValue === null || testValue === undefined) return 0;
    return ((trainValue - testValue) / testValue) * 100;
  };

  // Keep shortlist (checkbox) selection in sync with current filteredVariables
  useEffect(() => {
    if (!Array.isArray(filteredVariables)) return;
    setShortlistSelection((prev) => {
      const next: Record<string, boolean> = {};
      filteredVariables.forEach((v) => {
        next[v] = Object.prototype.hasOwnProperty.call(prev, v) ? prev[v] : true;
      });
      return next;
    });
  }, [filteredVariables]);
  // Manual optimization configuration (Step 2)
  const [optimizationMethodManual, setOptimizationMethodManual] = useState<'bayesian' | 'random'>('bayesian');
  const [targetMetricManual, setTargetMetricManual] = useState<string>('');
  const [manualCvFolds, setManualCvFolds] = useState<number>(5);
  const [manualOptunaTrials, setManualOptunaTrials] = useState<number>(50);
  const [manualEarlyStoppingRounds, setManualEarlyStoppingRounds] = useState<number>(10);
  const [manualLrVifThreshold, setManualLrVifThreshold] = useState<number>(5);
  const [manualLrPvalueThreshold, setManualLrPvalueThreshold] = useState<number>(0.05);
  const [manualLrPenaltyOptions, setManualLrPenaltyOptions] = useState<{
    l1: boolean;
    l2: boolean;
    elasticnet: boolean;
  }>({
    l1: true,
    l2: true,
    elasticnet: true,
  });
  // Multi-model training progress UI
  const [isMultiTraining, setIsMultiTraining] = useState(false);

  /**
   * Snapshot for Step 7 (screener / pruning): same logical run as Training insights for the
   * active auto vs manual tab, with sessionStorage fallback after reload.
   */
  const step7TrainingBundle = useMemo(() => {
    if (activeTab === 'manual') {
      return (
        trainingResults ||
        loadPersistedTrainingResults(activeDatasetId ?? null, trainingMode, 'manual')
      );
    }
    if (trainingMode === 'segment-specific') {
      return (
        segmentAutoTrainingResults ||
        loadPersistedTrainingResults(activeDatasetId ?? null, trainingMode, 'auto')
      );
    }
    return (
      autoTrainingResults ||
      loadPersistedTrainingResults(activeDatasetId ?? null, trainingMode, 'auto')
    );
  }, [
    activeTab,
    trainingMode,
    trainingResults,
    autoTrainingResults,
    segmentAutoTrainingResults,
    activeDatasetId,
    trainingPersistVersion,
  ]);

  /** Latest training snapshot — any tab; used for completion gate and fingerprint. */
  const mtaResultsBundle = useMemo(
    () =>
      trainingResults ||
      autoTrainingResults ||
      segmentAutoTrainingResults ||
      loadPersistedTrainingResults(activeDatasetId ?? null),
    [
      trainingResults,
      autoTrainingResults,
      segmentAutoTrainingResults,
      activeDatasetId,
      trainingPersistVersion,
    ],
  );

  const mtaTrainingFingerprint = useMemo(() => fingerprintMtaTrainingResults(mtaResultsBundle), [mtaResultsBundle]);

  const mtaTrainingInProgress =
    isMultiTraining || isAutoTraining || segmentAutoTrainingInProgress || isTraining;

  /** Screener + pruning only after a training run has finished (not while jobs are in flight). */
  const mtaTrainingComplete = useMemo(() => {
    if (!mtaResultsBundle) return false;
    const has = !!(mtaResultsBundle.results?.length || mtaResultsBundle.segment_results);
    return has && !mtaTrainingInProgress;
  }, [mtaResultsBundle, mtaTrainingInProgress]);

  const [mtaScreenerGateBump, setMtaScreenerGateBump] = useState(0);
  useEffect(() => {
    const onDone = () => setMtaScreenerGateBump((n) => n + 1);
    window.addEventListener('midas-mta-screener-phase-complete', onDone);
    return () => window.removeEventListener('midas-mta-screener-phase-complete', onDone);
  }, []);

  const mtaScreenerPhaseDone = useMemo(
    () => readMtaScreenerPhaseDone(activeDatasetId ?? null, mtaTrainingFingerprint),
    [activeDatasetId, mtaTrainingFingerprint, mtaScreenerGateBump],
  );

  useEffect(() => {
    onMtaFlowGateChange?.({
      trainingInProgress: mtaTrainingInProgress,
      trainingComplete: mtaTrainingComplete,
      screenerPhaseDone: mtaScreenerPhaseDone,
      variableSelectionConfirmed,
    });
  }, [
    onMtaFlowGateChange,
    mtaTrainingInProgress,
    mtaTrainingComplete,
    mtaScreenerPhaseDone,
    variableSelectionConfirmed,
  ]);

  const [multiOverallProgress, setMultiOverallProgress] = useState(0);
  const [algoProgress, setAlgoProgress] = useState<Record<string, number>>({});
  const [multiLogs, setMultiLogs] = useState<string[]>([]);
  const multiTimerRef = useRef<number | null>(null);
  const [multiResults, setMultiResults] = useState<any | null>(null);
  const [algoStatus, setAlgoStatus] = useState<Record<string, 'running' | 'completed'>>({});
  const [algoIterations, setAlgoIterations] = useState<Record<string, number>>({});
  const [isMultiPaused, setIsMultiPaused] = useState(false);
  const [animatedDots, setAnimatedDots] = useState<string>('.');

  const startMultiInterval = useCallback(() => {
    if (multiTimerRef.current) return;
    multiTimerRef.current = window.setInterval(()=>{
      setMultiOverallProgress(p=> Math.min(98, p + Math.random()*2));
      setAlgoProgress(prev=>{
        const next = { ...prev } as Record<string, number>;
        Object.keys(next).forEach(k=>{ next[k] = Math.min(98, next[k] + Math.random()*3); });
        return next;
      });
      setAlgoIterations(prev => {
        const keys = Object.keys(prev);
        if (keys.length === 0) return prev;
        const pick = keys[Math.floor(Math.random() * keys.length)];
        const next = { ...prev } as Record<string, number>;
        next[pick] = (next[pick] || 0) + Math.floor(Math.random()*3 + 1);
        const prog = (algoProgress[pick] ?? 0) / 100;
        const scoreApprox = Math.max(0, Math.min(1, 0.6 + prog * 0.4 + (Math.random()-0.5)*0.05));
        setMultiLogs(logs => [
          ...logs,
          `[${pick.toUpperCase()}] Iteration ${next[pick]}: Score = ${scoreApprox.toFixed(4)}`
        ].slice(-200));
        return next;
      });
    }, 800) as unknown as number;
  }, [algoProgress]);

  const pauseMultiTraining = () => {
    if (multiTimerRef.current) {
      window.clearInterval(multiTimerRef.current);
      multiTimerRef.current = null;
      setIsMultiPaused(true);
      setMultiLogs(logs=>[...logs, 'Training paused.']);
    }
  };

  const resumeMultiTraining = () => {
    if (!multiTimerRef.current) {
      setIsMultiPaused(false);
      setMultiLogs(logs=>[...logs, 'Training resumed.']);
      startMultiInterval();
    }
  };

  const stopMultiTraining = () => {
    if (multiTimerRef.current) {
      window.clearInterval(multiTimerRef.current);
      multiTimerRef.current = null;
    }
    setIsMultiTraining(false);
    setIsMultiPaused(false);
    setMultiOverallProgress(100);
    setAlgoStatus(prev => {
      const next: Record<string, 'running' | 'completed'> = {};
      Object.keys(prev).forEach(k=> next[k] = 'completed');
      return next;
    });
    setMultiLogs(logs=>[...logs, 'Training stopped by user.']);
  };

  // Animate dots for "Training in Progress..."
  useEffect(() => {
    if (!isMultiTraining) {
      setAnimatedDots('.');
      return;
    }

    const dotsInterval = setInterval(() => {
      setAnimatedDots(prev => {
        if (prev === '.') return '..';
        if (prev === '..') return '...';
        return '.';
      });
    }, 500); // Change dots every 500ms

    return () => clearInterval(dotsInterval);
  }, [isMultiTraining]);
  
  // Hyperparameter ranges state - aligned to Section 9 reference tables
  const PARAM_BOUNDS = {
    xgboost: {
      max_depth: { min: 2, max: 4, step: 1, defaultMin: 2, defaultMax: 4 },
      learning_rate: { min: 0.01, max: 0.05, step: 0.01, defaultMin: 0.01, defaultMax: 0.05 },
      n_estimators: { min: 10, max: 1000, step: 1, defaultMin: 10, defaultMax: 1000 },
      subsample: { min: 0.6, max: 0.8, step: 0.1, defaultMin: 0.6, defaultMax: 0.8 },
      colsample_bytree: { min: 0.6, max: 0.8, step: 0.1, defaultMin: 0.6, defaultMax: 0.8 },
      reg_lambda: { min: 0, max: 3, step: 0.1, defaultMin: 0, defaultMax: 3 },
      reg_alpha: { min: 0, max: 3, step: 0.1, defaultMin: 0, defaultMax: 3 },
      min_child_weight: { min: 0, max: 5, step: 0.5, defaultMin: 0, defaultMax: 5 },
      gamma: { min: 0, max: 2, step: 0.1, defaultMin: 0, defaultMax: 2 },
    },
    lightgbm: {
      max_depth: { min: 2, max: 5, step: 1, defaultMin: 2, defaultMax: 5 },
      learning_rate: { min: 0.05, max: 0.5, step: 0.01, defaultMin: 0.05, defaultMax: 0.5 },
      n_estimators: { min: 250, max: 400, step: 1, defaultMin: 250, defaultMax: 400 },
      min_child_samples: { min: 3000, max: 8000, step: 1, defaultMin: 3000, defaultMax: 8000 },
      lambda_l1: { min: 0.01, max: 10, step: 0.01, defaultMin: 0.1, defaultMax: 1.0 },
      lambda_l2: { min: 0.01, max: 10, step: 0.01, defaultMin: 0.1, defaultMax: 1.0 },
      feature_fraction: { min: 0.4, max: 1.0, step: 0.1, defaultMin: 0.4, defaultMax: 1.0 },
      min_split_gain: { min: 1, max: 8, step: 0.1, defaultMin: 1, defaultMax: 8 },
      max_bin: { min: 127, max: 255, step: 1, defaultMin: 127, defaultMax: 255 },
    },
    random_forest: {
      max_depth: { min: 5, max: 15, step: 1, defaultMin: 5, defaultMax: 15 },
      n_estimators: { min: 100, max: 500, step: 1, defaultMin: 100, defaultMax: 500 },
      min_samples_split: { min: 2, max: 20, step: 1, defaultMin: 2, defaultMax: 20 },
      min_samples_leaf: { min: 1, max: 10, step: 1, defaultMin: 1, defaultMax: 10 },
    },
    gradient_boosting: {
      max_depth: { min: 3, max: 6, step: 1, defaultMin: 3, defaultMax: 6 },
      learning_rate: { min: 0.01, max: 0.1, step: 0.01, defaultMin: 0.01, defaultMax: 0.1 },
      n_estimators: { min: 100, max: 500, step: 1, defaultMin: 100, defaultMax: 500 },
      min_samples_split: { min: 2, max: 20, step: 1, defaultMin: 2, defaultMax: 20 },
      min_samples_leaf: { min: 1, max: 10, step: 1, defaultMin: 1, defaultMax: 10 },
      subsample: { min: 0.6, max: 0.9, step: 0.1, defaultMin: 0.6, defaultMax: 0.9 },
    },
    catboost: {
      depth: { min: 4, max: 8, step: 1, defaultMin: 4, defaultMax: 8 },
      learning_rate: { min: 0.01, max: 0.1, step: 0.01, defaultMin: 0.01, defaultMax: 0.1 },
      iterations: { min: 500, max: 2000, step: 1, defaultMin: 500, defaultMax: 2000 },
      l2_leaf_reg: { min: 1, max: 10, step: 0.1, defaultMin: 1, defaultMax: 10 },
      bagging_temperature: { min: 0, max: 1, step: 0.1, defaultMin: 0, defaultMax: 1 },
      random_strength: { min: 1, max: 10, step: 0.1, defaultMin: 1, defaultMax: 10 },
      border_count: { min: 32, max: 255, step: 1, defaultMin: 32, defaultMax: 255 },
    },
    logistic_regression: {
      C: { min: 0.001, max: 10, step: 0.001, defaultMin: 0.001, defaultMax: 10 },
      l1_ratio: { min: 0, max: 1, step: 0.05, defaultMin: 0, defaultMax: 1 },
    },
  };

  // Generate default ranges from PARAM_BOUNDS
  const generateDefaultAlgoParamRanges = () => {
    const defaults: Record<string, any> = {};
    Object.entries(PARAM_BOUNDS).forEach(([algo, params]) => {
      defaults[algo] = {};
      Object.entries(params).forEach(([paramName, config]: [string, any]) => {
        defaults[algo][paramName] = {
          min: config.defaultMin,
          max: config.defaultMax
        };
      });
    });
    return defaults;
  };

  const generateRangeInputBuffers = () => {
    const defaults = generateDefaultAlgoParamRanges();
    const buffers: Record<string, Record<string, { min: string; max: string }>> = {};
    Object.entries(defaults).forEach(([algo, params]) => {
      buffers[algo] = {};
      (Object.entries(params) as Array<[string, { min: number; max: number }]>).forEach(([paramName, range]) => {
        buffers[algo][paramName] = {
          min: String(range.min),
          max: String(range.max)
        };
      });
    });
    return buffers;
  };

  const [algorithmParamRanges, setAlgorithmParamRanges] = useState<Record<string, any>>(
    generateDefaultAlgoParamRanges()
  );
  const [rangeInputBuffer, setRangeInputBuffer] = useState<Record<string, Record<string, { min: string; max: string }>>>(
    generateRangeInputBuffers()
  );

  // Helper to get param bounds (includes min/max limits and step)
  type AlgoParamBound = { min: number; max: number; step: number; defaultMin: number; defaultMax: number };
  const getParamBounds = (algorithm: string, paramName: string): AlgoParamBound => {
    const algoBounds = (PARAM_BOUNDS as Record<string, Record<string, AlgoParamBound>>)[algorithm];
    return algoBounds?.[paramName] || { min: 0, max: 100, step: 1, defaultMin: 0, defaultMax: 100 };
  };

  // Mock training history
  const [modelHistory] = useState([
    { modelId: 'MDL_001', algorithm: 'XGBoost', auc: 0.892, f1: 0.845, precision: 0.821, recall: 0.870, status: 'Production', isStarred: true },
    { modelId: 'MDL_002', algorithm: 'LightGBM', auc: 0.888, f1: 0.839, precision: 0.815, recall: 0.865, status: 'Ready', isStarred: false },
    { modelId: 'MDL_003', algorithm: 'CatBoost', auc: 0.885, f1: 0.841, precision: 0.825, recall: 0.858, status: 'Ready', isStarred: false },
    { modelId: 'MDL_004', algorithm: 'Random Forest', auc: 0.875, f1: 0.828, precision: 0.805, recall: 0.853, status: 'Ready', isStarred: false },
    { modelId: 'MDL_005', algorithm: 'Logistic', auc: 0.798, f1: 0.752, precision: 0.735, recall: 0.771, status: 'Baseline', isStarred: false },
  ]);

  // Mock training results
  const algorithms = [
    { id: 'xgboost', name: 'XGBoost', description: 'Fast, GPU support, best for structured data', icon: '⚡' },
    { id: 'lightgbm', name: 'LightGBM', description: 'Very fast, memory efficient', icon: '🚀' },
    { id: 'catboost', name: 'CatBoost', description: 'Categorical features auto-handled', icon: '🐱' },
    { id: 'random_forest', name: 'Random Forest', description: 'Robust, interpretable', icon: '🌲' },
    { id: 'logistic_regression', name: 'Logistic Regression', description: 'Baseline, fast training', icon: '📊' },
    { id: 'gradient_boosting', name: 'Gradient Boosting', description: 'Classic ML approach', icon: '📈' },
  ];
  const [selectedAlgorithms, setSelectedAlgorithms] = useState<string[]>(['xgboost']);

  const workflowSteps = [
    { id: 1, name: 'Algorithm Configuration', icon: Settings },
    { id: 2, name: 'Hyperparameter Optimization', icon: Activity },
    { id: 4, name: 'Performance Evaluation', icon: BarChart3 },
    { id: 5, name: 'Explainability & Insights', icon: TrendingUp },
    { id: 6, name: 'Quality Assurance & Output', icon: CheckCircle },
  ];

  // Load dataset preview data
  useEffect(() => {
    const loadDatasetPreview = async () => {
      if (!activeDatasetId) return;
      
      try {
        // Try to get segmented dataset first (priority: segmented dataset > recent dataframe)
        const response = await fastApiService.getSegmentedDatasetPreview(activeDatasetId);
        if (response.success && response.preview_data && response.shape) {
          setDatasetPreviewData({
            shape: response.shape,
            hasSegmentColumn: response.preview_data.columns.includes('segment'),
            preview: response.preview_data.rows,
            columns: response.preview_data.columns
          });
        }
      } catch (error) {
        console.error('Failed to load segmented dataset preview:', error);
        // Fallback to regular dataset preview if segmented dataset is not available
        try {
          const response = await fastApiService.getDatasetPreview(activeDatasetId);
          if (response.success && response.preview_data && response.shape) {
            setDatasetPreviewData({
              shape: response.shape,
              hasSegmentColumn: false,
              preview: response.preview_data.rows,
              columns: response.preview_data.columns
            });
          }
        } catch (fallbackError) {
          console.error('Failed to load regular dataset preview:', fallbackError);
        }
      }
    };

    loadDatasetPreview();

    // Listen for dataset scope changes and reload preview
    const handleScopeChange = async (event: Event) => {
      const customEvent = event as CustomEvent;
      if (customEvent.detail?.dataset_id === activeDatasetId) {
        // Reload preview after scope change
        await loadDatasetPreview();
      }
    };

    window.addEventListener('datasetScopeChanged', handleScopeChange);
    return () => {
      window.removeEventListener('datasetScopeChanged', handleScopeChange);
    };
  }, [activeDatasetId]);

  // Load post-modelling dataset preview when training completes
  useEffect(() => {
    const loadPostModellingPreview = async () => {
      if (!activeDatasetId) return;
      
      // Check if any training has completed
      const hasTrainingResults = trainingResults || autoTrainingResults || segmentAutoTrainingResults;
      if (!hasTrainingResults) return;
      
      try {
        // Try to get segmented dataset first (priority: segmented dataset > recent dataframe)
        const response = await fastApiService.getSegmentedDatasetPreview(activeDatasetId);
        if (response.success && response.preview_data && response.shape) {
          setPostModellingPreviewData({
            shape: response.shape,
            hasSegmentColumn: response.preview_data.columns.includes('segment'),
            preview: response.preview_data.rows,
            columns: response.preview_data.columns
          });
        }
      } catch (error) {
        console.error('Failed to load post-modelling segmented dataset preview:', error);
        // Fallback to regular dataset preview if segmented dataset is not available
        try {
          const response = await fastApiService.getDatasetPreview(activeDatasetId);
          if (response.success && response.preview_data && response.shape) {
            setPostModellingPreviewData({
              shape: response.shape,
              hasSegmentColumn: false,
              preview: response.preview_data.rows,
              columns: response.preview_data.columns
            });
          }
        } catch (fallbackError) {
          console.error('Failed to load post-modelling regular dataset preview:', fallbackError);
        }
      }
    };

    loadPostModellingPreview();
  }, [activeDatasetId, trainingResults, autoTrainingResults, segmentAutoTrainingResults]);

  // Load available variables when dataset preview data changes
  useEffect(() => {
    if (datasetPreviewData && datasetPreviewData.columns) {
      const columns = datasetPreviewData.columns;
      setAvailableVariables(columns);
      
      // Auto-select all variables except common non-feature columns
      const nonFeatureColumns = ['ID', 'MEMBER_ID', 'SEGMENT', 'segment'];
    // Do not auto-select all variables; start with an empty shortlist
    setSelectedIndependentVariables([]);

      // Set default target variable if not set
      if (!autoTargetVariable && columns.includes('TARGET_FLAG')) {
        setAutoTargetVariable('TARGET_FLAG');
      }
    }
  }, [datasetPreviewData, autoTargetVariable]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      if (!target.closest('.independent-variables-dropdown')) {
        setIsIndependentDropdownOpen(false);
      }
      if (!target.closest('.manual-independent-variables-dropdown')) {
        setManualIsIndependentDropdownOpen(false);
      }
    };

    if (isIndependentDropdownOpen || manualIsIndependentDropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isIndependentDropdownOpen, manualIsIndependentDropdownOpen]);

  // Real-time training logs polling
  useEffect(() => {
    if (isTraining && trainingResults?.model_id) {
      setIsReceivingLogs(true);
      setTrainingLogs([]); // Clear previous logs
      
      const interval = setInterval(async () => {
        try {
          const response = await fetch(`/api/v1/training-logs/${trainingResults.model_id}`, {
            headers: {
              ...buildMidasAuthHeaders(),
            },
          });
          if (response.ok) {
            const data = await response.json();
            setTrainingLogs(data.logs || []);
          }
        } catch (error) {
          console.error('Error fetching training logs:', error);
        }
      }, 1000); // Poll every second
      
      return () => {
        clearInterval(interval);
        setIsReceivingLogs(false);
      };
    }
  }, [isTraining, trainingResults?.model_id]);

  // Close download menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (showDownloadMenu && !(event.target as Element).closest('.download-dropdown')) {
        setShowDownloadMenu(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showDownloadMenu]);

  // Function to detect problem type from target variable
  const detectProblemType = (targetVar: string, data: any[]) => {
    if (!targetVar || !data || data.length === 0) return null;
    
    // Get target variable values
    const targetValues = data.map(row => row[targetVar]).filter(val => val !== null && val !== undefined);
    
    if (targetValues.length === 0) return null;
    
    // Check if values are numeric
    const isNumeric = targetValues.every(val => !isNaN(Number(val)));
    
    if (!isNumeric) {
      return 'classification';
    }
    
    // Convert to numbers for analysis
    const numericValues = targetValues.map(val => Number(val));
    const uniqueCount = new Set(numericValues).size;
    const totalCount = numericValues.length;
    const uniqueRatio = uniqueCount / totalCount;
    
    // Binary classification (0/1)
    if (uniqueCount === 2) {
      const uniqueVals = [...new Set(numericValues)].sort();
      if ((uniqueVals[0] === 0 && uniqueVals[1] === 1) || 
          (uniqueVals[0] === 0.0 && uniqueVals[1] === 1.0)) {
        return 'classification';
      }
    }
    
    // Categorical classification (few unique values)
    if (uniqueCount <= 20 && uniqueRatio <= 0.05) {
      // Check if values are mostly integers
      const integerCount = numericValues.filter(val => Number.isInteger(val)).length;
      if (integerCount / numericValues.length > 0.8) {
        return 'classification';
      }
    }
    
    // Continuous regression (many unique values)
    if (uniqueCount > 50) {
      return 'regression';
    }
    
    // Default to regression for numeric variables
    return 'regression';
  };

  // Update problem type and target variable from Objectives and Data or fallback to detection
  useEffect(() => {
    console.log('Updating problem type - targetVariable:', targetVariable, 'datasetPreviewData:', !!datasetPreviewData);

    // First try to get data from Objectives and Data section (only if not already set)
    const datasetConfigStr = sessionStorage.getItem('dataset_config');
    if (datasetConfigStr && !autoTargetVariable) {
      try {
        const datasetConfig = JSON.parse(datasetConfigStr);
        console.log('Found dataset config:', datasetConfig);

        if (datasetConfig.target_variable) {
          console.log('Setting target variable from config:', datasetConfig.target_variable);
          setAutoTargetVariable(datasetConfig.target_variable);

          // Map the dataset_structure_type to our problem type format
          if (datasetConfig.dataset_structure_type) {
            const structureType = datasetConfig.dataset_structure_type;
            console.log('Setting problem type from config:', structureType);
            if (structureType === 'classification' || structureType === 'regression') {
              setProblemType(structureType);
            } else {
              setProblemType(null);
            }
          }
          return;
        }
      } catch (error) {
        console.error('Error parsing dataset config:', error);
      }
    }

    // Fallback to existing detection logic (only if problem type not already set)
    if (autoTargetVariable && !problemType && datasetPreviewData && datasetPreviewData.preview) {
      const detectedType = detectProblemType(autoTargetVariable, datasetPreviewData.preview);
      console.log('Detected problem type from data:', detectedType);
      setProblemType(detectedType);
    } else if (!autoTargetVariable) {
      console.log('No target variable available');
      setProblemType(null);
    }
  }, [autoTargetVariable, datasetPreviewData, problemType]);

  // Update manual problem type from Objectives and Data or fallback to detection
  useEffect(() => {
    console.log('Updating manual problem type - manualTargetVariable:', manualTargetVariable, 'datasetPreviewData:', !!datasetPreviewData);

    // First try to get data from Objectives and Data section (only if not already set)
    const datasetConfigStr = sessionStorage.getItem('dataset_config');
    if (datasetConfigStr && !manualTargetVariable) {
      try {
        const datasetConfig = JSON.parse(datasetConfigStr);
        console.log('Found manual dataset config:', datasetConfig);

        if (datasetConfig.target_variable) {
          console.log('Setting manual target variable from config:', datasetConfig.target_variable);
          setManualTargetVariable(datasetConfig.target_variable);

          // Map the dataset_structure_type to our problem type format
          if (datasetConfig.dataset_structure_type) {
            const structureType = datasetConfig.dataset_structure_type;
            console.log('Setting manual problem type from config:', structureType);
            if (structureType === 'classification' || structureType === 'regression') {
              setManualProblemType(structureType);
            } else {
              setManualProblemType(null);
            }
          }
          return;
        }
      } catch (error) {
        console.error('Error parsing dataset config:', error);
      }
    }

    // Fallback to existing detection logic (only if problem type not already set)
    if (manualTargetVariable && !manualProblemType && datasetPreviewData && datasetPreviewData.preview) {
      const detectedType = detectProblemType(manualTargetVariable, datasetPreviewData.preview);
      console.log('Detected manual problem type from data:', detectedType);
      setManualProblemType(detectedType);
    } else if (!manualTargetVariable) {
      console.log('No manual target variable available');
      setManualProblemType(null);
    }
  }, [manualTargetVariable, datasetPreviewData, manualProblemType]);
  
  // Auto-select independent variables for manual configuration when target changes
  useEffect(() => {
    if (manualTargetVariable && datasetPreviewData && datasetPreviewData.columns) {
      const columns = datasetPreviewData.columns;
      const nonFeatureColumns = ['ID', 'MEMBER_ID', 'SEGMENT', 'segment'];
    // Do not auto-select all variables; start with an empty shortlist
    setManualSelectedIndependentVariables([]);
    }
  }, [manualTargetVariable, datasetPreviewData]);

  // Set default optimization metric based on problem type
  useEffect(() => {
    if (problemType === 'classification') {
      setOptimizationMetric('auc');
    } else if (problemType === 'regression') {
      setOptimizationMetric('r2');
    }
  }, [problemType]);

  // Reset metric value when optimization metric changes
  useEffect(() => {
    if (optimizationMetric && getMetricConfig(optimizationMetric)) {
      setMetricValue(getMetricConfig(optimizationMetric)?.placeholder || '');
    } else {
      setMetricValue('');
    }
  }, [optimizationMetric]);

  // Get metric configuration based on selected optimization metric
  const getMetricConfig = (metric: string) => {
    const configs: Record<string, { min: number; max: number; step: number; placeholder: string; label: string; description: string }> = {
      // Classification metrics
      'auc': { min: 0, max: 1, step: 0.01, placeholder: '0.85', label: 'AUC-ROC Threshold', description: 'Minimum AUC-ROC score (0-1)' },
      'f1': { min: 0, max: 1, step: 0.01, placeholder: '0.80', label: 'F1-Score Threshold', description: 'Minimum F1-Score (0-1)' },
      'precision': { min: 0, max: 1, step: 0.01, placeholder: '0.75', label: 'Precision Threshold', description: 'Minimum Precision (0-1)' },
      'recall': { min: 0, max: 1, step: 0.01, placeholder: '0.70', label: 'Recall Threshold', description: 'Minimum Recall (0-1)' },
      'accuracy': { min: 0, max: 1, step: 0.01, placeholder: '0.85', label: 'Accuracy Threshold', description: 'Minimum Accuracy (0-1)' },
      'log_loss': { min: 0, max: 10, step: 0.01, placeholder: '0.5', label: 'Log Loss Threshold', description: 'Maximum Log Loss (lower is better)' },
      
      // Regression metrics
      'r2': { min: 0, max: 1, step: 0.01, placeholder: '0.80', label: 'R² Threshold', description: 'Minimum R² Score (0-1)' },
      'adjusted_r2': { min: 0, max: 1, step: 0.01, placeholder: '0.75', label: 'Adjusted R² Threshold', description: 'Minimum Adjusted R² Score (0-1)' },
      'mae': { min: 0, max: 1000, step: 0.1, placeholder: '10.0', label: 'MAE Threshold', description: 'Maximum Mean Absolute Error' },
      'mse': { min: 0, max: 10000, step: 0.1, placeholder: '100.0', label: 'MSE Threshold', description: 'Maximum Mean Squared Error' },
      'rmse': { min: 0, max: 100, step: 0.1, placeholder: '10.0', label: 'RMSE Threshold', description: 'Maximum Root Mean Squared Error' }
    };
    
    return configs[metric] || null;
  };

  // Simulate training process
  const handleStartTraining = async () => {
    // Validate required fields
    if (!autoTargetVariable || !optimizationMetric || !metricValue) {
      alert('Please select target variable, optimization metric, and metric value');
      return;
    }

    if (!activeDatasetId) {
      alert('No dataset selected');
      return;
    }

    if (selectedIndependentVariables.length === 0) {
      alert('Please select at least one independent variable');
      return;
    }

    setIsTraining(true);
    setCurrentStep(1);
    setCurrentTrial(0);
    setBestScore(0);
    setShowResults(false);
    
    // Reset auto training steps
    setCurrentAutoStep(0);
    setAutoStepsCompleted([false, false, false, false]);
    
    try {
      // Prepare request
      const request = {
        dataset_id: activeDatasetId,
        target_column: autoTargetVariable,
        target_metric: optimizationMetric,
        target_value: parseFloat(metricValue),
        independent_variables: selectedIndependentVariables,
        max_runtime_secs: 300
      };

      console.log('Starting auto training with request:', request);

      // Call the API
      const result = await fastApiService.autoTrainModel(request);
      
      console.log('Auto training completed:', result);
      
      // Set results
      setTrainingResults(result);
      setIsTraining(false);
      setShowResults(true);
      
      // Mark all steps as completed
      setAutoStepsCompleted([true, true, true, true]);
      setCurrentAutoStep(4);
      
    } catch (error) {
      console.error('Auto training failed:', error);
      setIsTraining(false);
      
      // Handle different types of errors
      let errorMessage = 'Unknown error';
      
      if (error instanceof Error) {
        errorMessage = error.message;
        
        // Try to parse detailed validation errors
        try {
          const errorData = JSON.parse(errorMessage);
          if (Array.isArray(errorData)) {
            errorMessage = errorData.map(err => err.detail || err.msg || err).join(', ');
          } else if (errorData.detail) {
            errorMessage = errorData.detail;
          }
        } catch (parseError) {
          // If parsing fails, use the original message
        }
      }
      
      alert(`Auto training failed: ${errorMessage}`);
    }
  };

  const handlePauseTraining = () => {
    setIsTraining(false);
  };

  const handleStopTraining = () => {
    setIsTraining(false);
    setCurrentStep(0);
    setCurrentTrial(0);
  };

  // Render hyperparameter range inputs for an algorithm
  const updateRangeBufferValue = (algorithm: string, paramName: string, field: 'min' | 'max', value: string) => {
    setRangeInputBuffer((prev) => ({
      ...prev,
      [algorithm]: {
        ...(prev[algorithm] || {}),
        [paramName]: {
          ...(prev[algorithm]?.[paramName] || { min: '', max: '' }),
          [field]: value
        }
      }
    }));
  };

  const clampAndUpdateAlgoRange = (
    algorithm: string,
    paramName: string,
    field: 'min' | 'max',
    value: number,
    bounds: { min: number; max: number }
  ) => {
    setAlgorithmParamRanges((prev) => {
      const next = { ...prev };
      next[algorithm] = { ...(next[algorithm] || {}) };
      const existingRange = { ...(next[algorithm][paramName] || { min: bounds.min, max: bounds.max }) };
      existingRange[field] = value;
      if (field === 'min' && value > existingRange.max) {
        existingRange.max = value;
      }
      if (field === 'max' && value < existingRange.min) {
        existingRange.min = value;
      }
      next[algorithm][paramName] = existingRange;
      return next;
    });
  };

  const handleRangeInputChange = (
    algorithm: string,
    paramName: string,
    field: 'min' | 'max',
    rawValue: string
  ) => {
    const bounds = getParamBounds(algorithm, paramName);
    const parsed = parseFloat(rawValue);
    const isValidNumber = !Number.isNaN(parsed);
    const clampedValue = isValidNumber
      ? Math.max(Math.min(parsed, bounds.max), bounds.min)
      : null;

    const displayValue = isValidNumber ? String(clampedValue) : rawValue;
    updateRangeBufferValue(algorithm, paramName, field, displayValue);

    if (isValidNumber && clampedValue !== null) {
      clampAndUpdateAlgoRange(algorithm, paramName, field, clampedValue, bounds);
      // Ensure buffer reflects the clamped number (in case rounding happened)
      updateRangeBufferValue(algorithm, paramName, field, String(clampedValue));
    }
  };

  const renderHyperparameterRangeInputs = (algorithm: string) => {
    const ranges = algorithmParamRanges[algorithm] || {};
    const algoDisplayName = algorithms.find((a) => a.id === algorithm)?.name || algorithm.toUpperCase();
    const parameterNotes: Record<string, string> = {
      learning_rate: 'Step size for boosting updates.',
      n_estimators: 'Total boosting rounds / trees.',
      max_depth: 'Tree depth cap to control complexity.',
      min_child_weight: 'Prevents overfitting small leaves.',
      gamma: 'Split conservativeness threshold.',
      reg_lambda: 'L2 regularization strength.',
      reg_alpha: 'L1 regularization strength.',
      min_child_samples: 'Minimum records in one leaf.',
      lambda_l1: 'L1 regularization for leaves.',
      lambda_l2: 'L2 regularization for leaves.',
      feature_fraction: 'Column subsampling ratio per tree.',
      min_split_gain: 'Minimum gain required to split.',
      max_bin: 'Feature discretization bins.',
      subsample: 'Row subsampling ratio.',
      depth: 'Tree depth for CatBoost.',
      iterations: 'Boosting rounds.',
      l2_leaf_reg: 'L2 regularization on leaves.',
      bagging_temperature: 'Bayesian bootstrap intensity.',
      random_strength: 'Randomness in split scoring.',
      border_count: 'Numerical feature split bins.',
      min_samples_split: 'Minimum samples to split node.',
      min_samples_leaf: 'Minimum samples at leaf.',
      C: 'Inverse regularization strength.',
      l1_ratio: 'Elasticnet blending ratio (active for elasticnet).'
    };
    const getParameterType = (
      algoId: string,
      param: string,
      bounds: { min: number; max: number; step: number }
    ) => {
      const typeOverrides: Record<string, Record<string, string>> = {
        xgboost: {
          learning_rate: 'Discrete',
          subsample: 'Discrete',
          max_depth: 'Discrete',
          colsample_bytree: 'Quantized',
          reg_lambda: 'Quantized',
          reg_alpha: 'Quantized',
          gamma: 'Quantized',
          min_child_weight: 'Quantized',
        },
        lightgbm: {
          lambda_l1: 'Log-uniform',
          lambda_l2: 'Log-uniform',
        },
        catboost: {
          learning_rate: 'Log-uniform',
        },
        logistic_regression: {
          C: 'Log-uniform',
        },
      };
      const override = typeOverrides[algoId]?.[param];
      if (override) return override;
      const integerBounds = Number.isInteger(bounds.min) && Number.isInteger(bounds.max) && Number.isInteger(bounds.step);
      return integerBounds ? 'Integer' : 'Continuous';
    };

    type ExtraTableRow =
      | {
          kind: 'single_input';
          parameter: string;
          value: number;
          min: number;
          max: number;
          step: number;
          defaultValue: number;
          valueType: string;
          notes: string;
          onChange: (nextValue: number) => void;
        }
      | {
          kind: 'fixed';
          parameter: string;
          value: string;
          defaultValue: string;
          valueType: string;
          notes: string;
        };

    const extraRows: ExtraTableRow[] = [];

    if (algorithm) {
      extraRows.push(
        {
          kind: 'single_input',
          parameter: 'optuna_trials',
          value: manualOptunaTrials,
          min: 1,
          max: 100,
          step: 1,
          defaultValue: 50,
          valueType: 'Integer',
          notes: 'Bayesian optimization trials',
          onChange: (nextValue: number) => setManualOptunaTrials(Math.max(1, Math.min(100, nextValue || 50))),
        },
        {
          kind: 'single_input',
          parameter: 'early_stopping_rounds',
          value: manualEarlyStoppingRounds,
          min: 1,
          max: 100,
          step: 1,
          defaultValue: 10,
          valueType: 'Integer',
          notes: 'Within-trial early stopping',
          onChange: (nextValue: number) => setManualEarlyStoppingRounds(Math.max(1, Math.min(100, nextValue || 10))),
        }
      );
    }

    if (algorithm === 'xgboost') {
      extraRows.push(
        { kind: 'fixed', parameter: 'objective', value: 'binary:logistic', defaultValue: 'binary:logistic', valueType: 'Fixed', notes: 'Read-only' },
        { kind: 'fixed', parameter: 'tree_method', value: 'exact', defaultValue: 'exact', valueType: 'Fixed', notes: 'Read-only' },
        { kind: 'fixed', parameter: 'scale_pos_weight', value: 'Auto-calculated', defaultValue: 'Auto-calculated', valueType: 'Fixed', notes: 'Set to 1 when weight variable is present' },
        { kind: 'fixed', parameter: 'eval_metric', value: 'auc', defaultValue: 'auc', valueType: 'Fixed', notes: 'Read-only' },
        { kind: 'fixed', parameter: 'random_state', value: '42', defaultValue: '42', valueType: 'Fixed', notes: 'Read-only' }
      );
    }

    if (algorithm === 'lightgbm') {
      extraRows.push(
        { kind: 'fixed', parameter: 'objective', value: 'binary', defaultValue: 'binary', valueType: 'Fixed', notes: 'Read-only' },
        { kind: 'fixed', parameter: 'metric', value: 'auc', defaultValue: 'auc', valueType: 'Fixed', notes: 'Read-only' },
        { kind: 'fixed', parameter: 'is_unbalance', value: 'true', defaultValue: 'true', valueType: 'Fixed', notes: 'Read-only' },
        { kind: 'fixed', parameter: 'random_state', value: '42', defaultValue: '42', valueType: 'Fixed', notes: 'Read-only' },
        { kind: 'fixed', parameter: 'verbose', value: '-1', defaultValue: '-1', valueType: 'Fixed', notes: 'Suppress training logs' }
      );
    }

    if (algorithm === 'catboost') {
      extraRows.push(
        { kind: 'fixed', parameter: 'loss_function', value: 'Logloss', defaultValue: 'Logloss', valueType: 'Fixed', notes: 'Read-only' },
        { kind: 'fixed', parameter: 'eval_metric', value: 'AUC', defaultValue: 'AUC', valueType: 'Fixed', notes: 'Read-only' },
        { kind: 'fixed', parameter: 'auto_class_weights', value: 'Balanced', defaultValue: 'Balanced', valueType: 'Fixed', notes: 'Set to None when weight variable is present' },
        { kind: 'fixed', parameter: 'random_seed', value: '42', defaultValue: '42', valueType: 'Fixed', notes: 'Read-only' }
      );
    }

    if (algorithm === 'random_forest') {
      extraRows.push(
        { kind: 'fixed', parameter: 'max_features', value: 'sqrt, log2, 0.5, 0.8', defaultValue: 'sqrt', valueType: 'Categorical', notes: 'Tuned categorical choices' },
        { kind: 'fixed', parameter: 'class_weight', value: 'balanced', defaultValue: 'balanced', valueType: 'Fixed', notes: 'Set to None when weight variable is present' },
        { kind: 'fixed', parameter: 'random_state', value: '42', defaultValue: '42', valueType: 'Fixed', notes: 'Read-only' },
        { kind: 'fixed', parameter: 'n_jobs', value: '-1', defaultValue: '-1', valueType: 'Fixed', notes: 'Use all available cores' }
      );
    }

    if (algorithm === 'gradient_boosting') {
      extraRows.push(
        { kind: 'fixed', parameter: 'max_features', value: 'sqrt, log2, 0.5', defaultValue: 'sqrt', valueType: 'Categorical', notes: 'Tuned categorical choices' },
        { kind: 'fixed', parameter: 'random_state', value: '42', defaultValue: '42', valueType: 'Fixed', notes: 'Read-only' }
      );
    }

    if (algorithm === 'logistic_regression') {
      const selectedPenaltyText = (Object.entries(manualLrPenaltyOptions) as Array<[string, boolean]>)
        .filter(([, enabled]) => enabled)
        .map(([penalty]) => penalty)
        .join(', ') || 'none';
      extraRows.push(
        {
          kind: 'fixed',
          parameter: 'penalty',
          value: selectedPenaltyText,
          defaultValue: 'l2',
          valueType: 'Categorical',
          notes: 'Selected penalty options for LR optimization.'
        },
        {
          kind: 'fixed',
          parameter: 'solver',
          value: 'saga',
          defaultValue: 'saga',
          valueType: 'Fixed',
          notes: 'Read-only'
        },
        {
          kind: 'fixed',
          parameter: 'max_iter',
          value: '1000',
          defaultValue: '1000',
          valueType: 'Fixed',
          notes: 'Read-only'
        },
        {
          kind: 'fixed',
          parameter: 'class_weight',
          value: 'balanced',
          defaultValue: 'balanced',
          valueType: 'Fixed',
          notes: 'Read-only'
        },
        {
          kind: 'fixed',
          parameter: 'random_state',
          value: '42',
          defaultValue: '42',
          valueType: 'Fixed',
          notes: 'Read-only'
        }
      );
    }

    return (
      <div className="space-y-2 bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-slate-900 dark:to-slate-800 p-3 rounded-lg border border-blue-200 dark:border-slate-700">
        <div className="flex items-center justify-between">
          <h5 className="font-semibold text-gray-900 dark:text-white text-sm">{algoDisplayName} Configuration</h5>
        </div>

        <div className={`overflow-x-auto ${MTA_TABLE_SHELL}`}>
          <table className="min-w-[980px] w-full table-fixed text-xs">
            <colgroup>
              <col className="w-[18%]" />
              <col className="w-[13%]" />
              <col className="w-[13%]" />
              <col className="w-[14%]" />
              <col className="w-[10%]" />
              <col className="w-[32%]" />
            </colgroup>
            <thead className={MTA_THEAD}>
              <tr>
                <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">Parameter</th>
                <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">Lower Bound</th>
                <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">Upper Bound</th>
                <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">Auto Default</th>
                <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">Type</th>
                <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">Notes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-slate-700">
              {Object.entries(ranges).map(([paramName, range]: [string, any]) => {
                const bounds = getParamBounds(algorithm, paramName);
                const userMin = range.min;
                const userMax = range.max;
                return (
                  <tr key={paramName} className="hover:bg-gray-50 dark:hover:bg-slate-800/70">
                    <td className="px-3 py-2.5 font-medium text-gray-800 dark:text-gray-100 break-words">{paramName}</td>
                    <td className="px-3 py-2.5 align-middle">
                      <input
                        type="number"
                        step={bounds.step || 1}
                        min={bounds.min}
                        max={bounds.max}
                        value={rangeInputBuffer[algorithm]?.[paramName]?.min ?? String(userMin)}
                        onChange={(e) => handleRangeInputChange(algorithm, paramName, 'min', e.target.value)}
                        className="w-full max-w-[120px] px-2 py-1.5 border border-gray-300 dark:border-slate-700 rounded text-xs focus:ring-1 focus:ring-blue-500 focus:outline-none dark:bg-slate-900 dark:text-white"
                      />
                    </td>
                    <td className="px-3 py-2.5 align-middle">
                      <input
                        type="number"
                        step={bounds.step || 1}
                        min={bounds.min}
                        max={bounds.max}
                        value={rangeInputBuffer[algorithm]?.[paramName]?.max ?? String(userMax)}
                        onChange={(e) => handleRangeInputChange(algorithm, paramName, 'max', e.target.value)}
                        className="w-full max-w-[120px] px-2 py-1.5 border border-gray-300 dark:border-slate-700 rounded text-xs focus:ring-1 focus:ring-blue-500 focus:outline-none dark:bg-slate-900 dark:text-white"
                      />
                    </td>
                    <td className="px-3 py-2.5 text-gray-700 dark:text-gray-300 whitespace-nowrap">[{bounds.defaultMin}, {bounds.defaultMax}]</td>
                    <td className="px-3 py-2.5 text-gray-700 dark:text-gray-300 whitespace-nowrap">{getParameterType(algorithm, paramName, bounds)}</td>
                    <td className="px-3 py-2.5 text-gray-600 dark:text-gray-400 break-words">{parameterNotes[paramName] || 'Configurable search bound.'}</td>
                  </tr>
                );
              })}
              {extraRows.map((row) => {
                if (row.kind === 'single_input') {
                  return (
                    <tr key={`${algorithm}-${row.parameter}`} className="bg-gray-50 dark:bg-slate-800/40">
                      <td className="px-3 py-2.5 font-medium text-gray-800 dark:text-gray-100 break-words">{row.parameter}</td>
                      <td className="px-3 py-2.5 align-middle">
                        <input
                          type="number"
                          min={row.min}
                          max={row.max}
                          step={row.step}
                          value={row.value}
                          onChange={(e) => row.onChange(parseInt(e.target.value) || row.defaultValue)}
                          className="w-full max-w-[120px] px-2 py-1.5 border border-gray-300 dark:border-slate-700 rounded text-xs focus:ring-1 focus:ring-blue-500 focus:outline-none dark:bg-slate-900 dark:text-white"
                        />
                      </td>
                      <td className="px-3 py-2.5 text-gray-500 dark:text-gray-400 whitespace-nowrap">-</td>
                      <td className="px-3 py-2.5 text-gray-700 dark:text-gray-300 whitespace-nowrap">{row.defaultValue}</td>
                      <td className="px-3 py-2.5 text-gray-700 dark:text-gray-300 whitespace-nowrap">{row.valueType}</td>
                      <td className="px-3 py-2.5 text-gray-600 dark:text-gray-400 break-words">{row.notes}</td>
                    </tr>
                  );
                }
                return (
                  <tr key={`${algorithm}-${row.parameter}`} className="bg-gray-50 dark:bg-slate-800/40">
                    <td className="px-3 py-2.5 font-medium text-gray-800 dark:text-gray-100 break-words">{row.parameter}</td>
                    <td className="px-3 py-2.5 text-gray-500 dark:text-gray-400 whitespace-nowrap">-</td>
                    <td className="px-3 py-2.5 text-gray-700 dark:text-gray-300 break-words">{row.value}</td>
                    <td className="px-3 py-2.5 text-gray-700 dark:text-gray-300 whitespace-nowrap">{row.defaultValue}</td>
                    <td className="px-3 py-2.5 text-gray-700 dark:text-gray-300 whitespace-nowrap">{row.valueType}</td>
                    <td className="px-3 py-2.5 text-gray-600 dark:text-gray-400 break-words">{row.notes}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {algorithm === 'logistic_regression' && (
          <div className="mt-3 border border-gray-200 dark:border-slate-700 rounded bg-gray-50 dark:bg-slate-900/60 p-3">
            <div className="text-[11px] font-semibold tracking-wide text-gray-700 dark:text-gray-200 mb-2">
              BACKWARD ELIMINATION THRESHOLDS (LR-SPECIFIC)
            </div>
            <div className="mb-2 rounded border border-teal-200 dark:border-teal-800/70 bg-teal-50/80 dark:bg-teal-900/20 px-3 py-2 text-xs text-teal-900 dark:text-teal-200">
              Adjustable thresholds for the VIF and p-value backward elimination loop. Changing these affects how aggressively elimination removes variables.
            </div>
            <div className="overflow-auto rounded border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900/70">
              <table className="w-full min-w-[760px] text-xs">
                <thead className={MTA_THEAD}>
                  <tr>
                    <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">THRESHOLD</th>
                    <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">VALUE</th>
                    <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">AUTO DEFAULT</th>
                    <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">DESCRIPTION</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 dark:divide-slate-700">
                  <tr className="bg-white dark:bg-slate-950">
                    <td className="px-3 py-2.5 text-gray-900 dark:text-white whitespace-nowrap">VIF threshold</td>
                    <td className="px-3 py-2.5">
                      <input
                        type="number"
                        min="1"
                        max="20"
                        step="0.1"
                        value={manualLrVifThreshold}
                        onChange={(e) => setManualLrVifThreshold(Math.max(1, Math.min(20, Number(e.target.value) || 5)))}
                        className="w-full max-w-[120px] px-2 py-1.5 border border-gray-300 dark:border-slate-700 rounded text-xs dark:bg-slate-900 dark:text-white"
                      />
                    </td>
                    <td className="px-3 py-2.5 text-gray-500 dark:text-gray-400 whitespace-nowrap">5</td>
                    <td className="px-3 py-2.5 text-gray-600 dark:text-gray-300">Variables with VIF above this are removed (highest first). Lower = stricter.</td>
                  </tr>
                  <tr className="bg-gray-50 dark:bg-slate-900/50">
                    <td className="px-3 py-2.5 text-gray-900 dark:text-white whitespace-nowrap">p-value threshold</td>
                    <td className="px-3 py-2.5">
                      <input
                        type="number"
                        min="0.001"
                        max="1"
                        step="0.001"
                        value={manualLrPvalueThreshold}
                        onChange={(e) => setManualLrPvalueThreshold(Math.max(0.001, Math.min(1, Number(e.target.value) || 0.05)))}
                        className="w-full max-w-[120px] px-2 py-1.5 border border-gray-300 dark:border-slate-700 rounded text-xs dark:bg-slate-900 dark:text-white"
                      />
                    </td>
                    <td className="px-3 py-2.5 text-gray-500 dark:text-gray-400 whitespace-nowrap">0.05</td>
                    <td className="px-3 py-2.5 text-gray-600 dark:text-gray-300">Variables with p-value above this are removed (highest first). Lower = stricter.</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div className="mt-3">
              <div className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">
                Penalty Options
              </div>
              <div className="flex flex-wrap gap-4">
                {(['l1', 'l2', 'elasticnet'] as const).map((penalty) => (
                  <label key={penalty} className="inline-flex items-center space-x-2 text-xs text-gray-700 dark:text-gray-300">
                    <input
                      type="checkbox"
                      checked={manualLrPenaltyOptions[penalty]}
                      onChange={(e) =>
                        setManualLrPenaltyOptions((prev) => ({
                          ...prev,
                          [penalty]: e.target.checked,
                        }))
                      }
                      className="rounded border-gray-300 dark:border-slate-700"
                    />
                    <span>{penalty}</span>
                  </label>
                ))}
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-300 mt-2">
                Selected penalty options are sent with LR manual configuration and can be explored during optimization.
              </p>
            </div>
          </div>
        )}
      </div>
    );
  };

  // Helper function to get available variables for manual selection
  const getAvailableVariablesForManualSelection = () => {
    if (!autoAnalysisData?.variable_analysis?.variable_statistics || !autoTargetVariable) {
      return [];
    }

    const exclude = ['ID', 'MEMBER_ID', 'SEGMENT', 'segment'];
    return autoAnalysisData.variable_analysis.variable_statistics.filter((stat: any) => {
      return stat.variable !== autoTargetVariable && !exclude.includes(stat.variable?.toUpperCase());
    });
  };

  const getLockedVariableList = () =>
    Object.keys(lockedVariables).filter((variable) => !!lockedVariables[variable]);

  /** Manual multi-train: same gates as the MTA pipeline (lock → confirm & RFE → feature review done). */
  const canRunManualSelectedModels = useMemo(() => {
    const lockedOk = getLockedVariableList().length > 0;
    return (
      lockedOk &&
      variableSelectionConfirmed &&
      rfeResult != null &&
      mtaSubStep === 'completed'
    );
  }, [lockedVariables, variableSelectionConfirmed, rfeResult, mtaSubStep]);

  const runStep6InteractiveLrElimination = useCallback(
    async (payload: { results: any; segmentId?: string }) => {
      if (!activeDatasetId) {
        setStep6LrInteractiveError('No active dataset.');
        return;
      }
      const { results, segmentId } = payload;
      const vars =
        Array.isArray(results?.used_features) && results.used_features.length > 0
          ? results.used_features
          : lastUsedVariables;
      const targetCol =
        manualTargetVariable ||
        autoTargetVariable ||
        (typeof results?.target_column === 'string' ? results.target_column : '');
      if (!targetCol || !Array.isArray(vars) || vars.length === 0) {
        setStep6LrInteractiveError('Missing target column or feature list. Complete a training run first.');
        return;
      }
      setStep6LrInteractiveLoading(true);
      setStep6LrInteractiveError(null);
      try {
        const lockedList = Object.keys(lockedVariables).filter((variable) => !!lockedVariables[variable]);
        const body = {
          dataset_id: activeDatasetId,
          target_column: targetCol,
          independent_variables: vars as string[],
          locked_variables: lockedList,
          vif_threshold: manualLrVifThreshold,
          p_value_threshold: manualLrPvalueThreshold,
          ...(segmentId && segmentId !== 'all' ? { segment_id: segmentId } : {}),
        };
        const data = await fastApiService.runLrBackwardElimination(body);
        setStep6LrInteractiveReport(data.lr_backward_elimination ?? null);
      } catch (e: any) {
        setStep6LrInteractiveReport(null);
        setStep6LrInteractiveError(e?.message || String(e));
      } finally {
        setStep6LrInteractiveLoading(false);
      }
    },
    [
      activeDatasetId,
      lastUsedVariables,
      manualTargetVariable,
      autoTargetVariable,
      lockedVariables,
      manualLrVifThreshold,
      manualLrPvalueThreshold,
    ]
  );

  useEffect(() => {
    setStep6LrInteractiveReport(null);
    setStep6LrInteractiveError(null);
    setStep6LrInteractiveLoading(false);
  }, [activeDatasetId, trainingResults, autoTrainingResults, segmentAutoTrainingResults, multiResults]);

  const getNormalizedVifValue = (stat: any): number | null => {
    const rawVif = stat?.vif ?? stat?.vif_value ?? stat?.VIF;
    if (rawVif === null || rawVif === undefined) return null;
    const numericVif = typeof rawVif === 'number' ? rawVif : Number(rawVif);
    return Number.isFinite(numericVif) ? numericVif : null;
  };

  const getLockCandidatesFromAutoAnalysis = () => {
    if (!autoAnalysisData?.variable_analysis?.variable_statistics || !autoTargetVariable) {
      return [];
    }
    const exclude = ['ID', 'MEMBER_ID', 'SEGMENT', 'segment'];
    return autoAnalysisData.variable_analysis.variable_statistics.filter((stat: any) => {
      const variableName = String(stat?.variable ?? '');
      if (!variableName) return false;
      return variableName !== autoTargetVariable && !exclude.includes(variableName.toUpperCase());
    });
  };

  const getLockCandidatesFromManualAnalysis = () => {
    if (!vifCorrelationData?.variable_statistics || !manualTargetVariable) {
      return [];
    }
    const exclude = ['ID', 'MEMBER_ID', 'SEGMENT', 'segment'];
    return vifCorrelationData.variable_statistics.filter((stat: any) => {
      const variableName = String(stat?.variable ?? '');
      if (!variableName) return false;
      return variableName !== manualTargetVariable && !exclude.includes(variableName.toUpperCase());
    });
  };

  const getCommonLockCandidates = () => {
    const autoCandidates = getLockCandidatesFromAutoAnalysis();
    const manualCandidates = getLockCandidatesFromManualAnalysis();

    if (autoCandidates.length === 0) return manualCandidates;
    if (manualCandidates.length === 0) return autoCandidates;

    const autoVifCount = autoCandidates.reduce(
      (count: number, stat: any) => count + (getNormalizedVifValue(stat) !== null ? 1 : 0),
      0
    );
    const manualVifCount = manualCandidates.reduce(
      (count: number, stat: any) => count + (getNormalizedVifValue(stat) !== null ? 1 : 0),
      0
    );

    // Prefer whichever source has more usable VIF values for Step 1 display.
    return manualVifCount > autoVifCount ? manualCandidates : autoCandidates;
  };

  const getCommonScreenerCandidates = () => {
    return getCommonLockCandidates().filter((stat: any) => {
      const variableName = String(stat?.variable ?? '');
      return !!variableName;
    });
  };

  const getCommonUnlockedScreenerCandidates = () => {
    return getCommonScreenerCandidates().filter((stat: any) => {
      const variableName = String(stat?.variable ?? '');
      return !lockedVariables[variableName];
    });
  };

  const getScreenerMetricValue = (stat: any, metric: string): number | null => {
    if (metric === 'correlation') {
      return Math.abs(Number(stat?.correlation ?? 0));
    }
    if (metric === 'vif') {
      return getNormalizedVifValue(stat);
    }
    if (metric === 'iv') {
      const iv = stat?.iv;
      if (iv === null || iv === undefined) return null;
      const ivNum = Number(iv);
      return Number.isFinite(ivNum) ? ivNum : null;
    }
    return null;
  };

  const doesScreenerFilterPass = (
    stat: any,
    filter: { metric: string; operator: string; value: number }
  ) => {
    const metricValue = getScreenerMetricValue(stat, filter.metric);
    if (metricValue === null) return false;

    switch (filter.operator) {
      case 'gte':
        return metricValue >= filter.value;
      case 'lte':
        return metricValue <= filter.value;
      case 'gt':
        return metricValue > filter.value;
      case 'lt':
        return metricValue < filter.value;
      case 'eq':
        return Math.abs(metricValue - filter.value) <= 0.0001;
      default:
        return true;
    }
  };

  const getCommonFilteredScreenerCandidates = () => {
    const candidates = getCommonUnlockedScreenerCandidates();
    if (!autoActiveFilters || autoActiveFilters.length === 0) return candidates;

    return candidates.filter((stat: any) => {
      for (const filter of autoActiveFilters) {
        if (!doesScreenerFilterPass(stat, filter)) return false;
      }

      return true;
    });
  };

  // Step 5 input bridge:
  // If Step 4 output is available (from external implementation), use it as
  // the variable input for Step 5. Otherwise, fall back to existing Step 2 flow.
  const extractStep4SelectedVariables = (payload: any): string[] => {
    if (!payload || typeof payload !== 'object') return [];

    const normalizeList = (list: any): string[] => {
      if (!Array.isArray(list)) return [];
      return list
        .map((item) => String(item ?? '').trim())
        .filter((name) => !!name);
    };

    const directLists = [
      payload.selected_variables,
      payload.selected_features,
      payload.variables_for_step5,
      payload.final_variables,
      payload.features,
    ];

    for (const list of directLists) {
      const vars = normalizeList(list);
      if (vars.length > 0) return vars;
    }

    const nestedCandidates = [
      payload.feature_review,
      payload.step4_output,
      payload.output,
      payload.data,
    ];

    for (const nested of nestedCandidates) {
      if (nested && typeof nested === 'object') {
        const nestedVars = extractStep4SelectedVariables(nested);
        if (nestedVars.length > 0) return nestedVars;
      }
    }

    const tableLikeRows = [
      payload.rows,
      payload.variables,
      payload.review_rows,
      payload.features_table,
    ];

    for (const rows of tableLikeRows) {
      if (!Array.isArray(rows)) continue;
      const vars = rows
        .filter((row: any) => {
          const includeFlag = row?.include ?? row?.selected ?? row?.is_selected ?? row?.enabled;
          return includeFlag === true;
        })
        .map((row: any) => String(row?.variable ?? row?.name ?? row?.feature ?? row?.column ?? '').trim())
        .filter((name: string) => !!name);
      if (vars.length > 0) return vars;
    }

    return [];
  };

  const getStep4SelectedVariablesForStep5 = useCallback((): string[] => {
    if (typeof window === 'undefined') return [];

    const dedupe = (items: string[]): string[] => Array.from(new Set(items.filter((x) => !!x)));

    const datasetScopedKeys = activeDatasetId
      ? [
          `model_training_step4_output_${activeDatasetId}`,
          `model_training_feature_review_${activeDatasetId}`,
          `step4_output_${activeDatasetId}`,
        ]
      : [];

    const genericKeys = [
      'model_training_step4_output',
      'model_training_feature_review',
      'step4_output',
    ];

    const keysToTry = [...datasetScopedKeys, ...genericKeys];
    for (const key of keysToTry) {
      try {
        const raw = sessionStorage.getItem(key);
        if (!raw) continue;
        const parsed = JSON.parse(raw);
        const vars = dedupe(extractStep4SelectedVariables(parsed));
        if (vars.length > 0) return vars;
      } catch (e) {
        // Ignore malformed/non-JSON values and continue to next key.
      }
    }

    const runtimeCandidates = [
      (window as any).__MODEL_TRAINING_STEP4_OUTPUT__,
      activeDatasetId ? (window as any).__MODEL_TRAINING_STEP4_BY_DATASET__?.[activeDatasetId] : null,
    ];

    for (const candidate of runtimeCandidates) {
      const vars = dedupe(extractStep4SelectedVariables(candidate));
      if (vars.length > 0) return vars;
    }

    return [];
  }, [activeDatasetId]);

  const resolveStep5InputVariables = useCallback(
    (fallbackVariables: string[]): string[] => {
      const step4Variables = getStep4SelectedVariablesForStep5();
      if (step4Variables.length > 0) {
        console.log(`✅ Step 5 using Step 4 input (${step4Variables.length} variables)`);
        return step4Variables;
      }
      return Array.from(new Set((fallbackVariables || []).map((v) => String(v || '').trim()).filter((v) => !!v)));
    },
    [getStep4SelectedVariablesForStep5]
  );

  // Helper function to get filtered variables for manual selection (applies active filters)
  const getFilteredVariablesForManualSelection = () => {
    if (!autoAnalysisData?.variable_analysis?.variable_statistics || !autoTargetVariable) {
      return [];
    }

    const exclude = ['ID', 'MEMBER_ID', 'SEGMENT', 'segment'];
    const allStats = autoAnalysisData.variable_analysis.variable_statistics.filter((stat: any) => {
      return stat.variable !== autoTargetVariable && !exclude.includes(stat.variable?.toUpperCase());
    });

    // If no filters are active, return all variables
    if (!autoActiveFilters || autoActiveFilters.length === 0) {
      return allStats;
    }

    // Apply the same filters as the table (matching lines 3520-3562 logic)
    return allStats.filter((stat: any) => {
      const absCorr = Math.abs(stat.correlation || 0);
      const vif = stat.vif;
      const iv = stat.iv !== null && stat.iv !== undefined ? Number(stat.iv) : null;

      // Apply all active filters
      let passesFilters = true;
      for (const filter of autoActiveFilters) {
        let metricValue: number | null = null;
        
        if (filter.metric === 'correlation') {
          metricValue = absCorr;
        } else if (filter.metric === 'vif') {
          metricValue = vif !== null && vif !== undefined ? vif : null;
        } else if (filter.metric === 'iv') {
          metricValue = iv;
        }

        if (metricValue === null) {
          passesFilters = false;
          break;
        }

        // Apply operator
        switch (filter.operator) {
          case 'gte':
            if (metricValue < filter.value) passesFilters = false;
            break;
          case 'lte':
            if (metricValue > filter.value) passesFilters = false;
            break;
          case 'gt':
            if (metricValue <= filter.value) passesFilters = false;
            break;
          case 'lt':
            if (metricValue >= filter.value) passesFilters = false;
            break;
          case 'eq':
            if (Math.abs(metricValue - filter.value) > 0.0001) passesFilters = false;
            break;
        }

        if (!passesFilters) break;
      }

      return passesFilters;
    });
  };

  // Calculate VIF and Correlation
  // Calculate VIF for manually selected variables
  // Uses async background job with polling to prevent timeout errors in Azure
  // Works for both Global Manual and Segment Manual training modes
  const handleCalculateVIF = async () => {
    if (!manualTargetVariable || manualSelectedIndependentVariables.length === 0) {
      alert('Please select target variable and independent variables first');
      return;
    }

    if (!activeDatasetId) {
      alert('No dataset selected');
      return;
    }

    setIsCalculatingVIF(true);
    setVifCorrelationData(null);
    setStep1LoadError(null);

    try {
      const startResponse = await fastApiService.startCalculateVifCorrelation({
        dataset_id: activeDatasetId,
        target_column: manualTargetVariable,
        independent_variables: manualSelectedIndependentVariables
      });

      if (!startResponse.success || !startResponse.job_id) {
        throw new Error('Failed to start VIF calculation job');
      }

      const jobId = startResponse.job_id;
      console.log('✅ VIF calculation job started:', jobId);

      const pollInterval = 2000;
      let polls = 0;

      for (;;) {
        polls++;
        const statusResponse = await fastApiService.getVifCorrelationStatus(jobId);

        if (statusResponse.status === 'completed') {
          if (statusResponse.result) {
            setVifCorrelationData(statusResponse.result);
            setShowVifPreview(true);
            setIsCalculatingVIF(false);
            console.log('✅ VIF calculation completed');
          } else {
            throw new Error('Calculation completed but no result returned');
          }
          return;
        }
        if (statusResponse.status === 'failed') {
          setIsCalculatingVIF(false);
          throw new Error(statusResponse.error || 'VIF calculation failed');
        }
        if (statusResponse.status === 'running' || statusResponse.status === 'pending') {
          if (polls % 10 === 0) {
            console.log(`VIF calculation in progress... (${polls * 2}s elapsed)`);
          }
          await delayMs(pollInterval);
          continue;
        }
        setIsCalculatingVIF(false);
        throw new Error(`Unknown job status: ${statusResponse.status}`);
      }
    } catch (error) {
      console.error('VIF calculation failed:', error);
      const msg = error instanceof Error ? error.message : 'Unknown error';
      setStep1LoadError(msg);
      alert(`VIF calculation failed: ${msg}`);
      setIsCalculatingVIF(false);
    }
  };

  // Quick Variable Analysis for Auto step: use all remaining variables after selecting target
  // Uses async background job with polling to prevent timeout errors in Azure
  const handleAutoVariableAnalysis = async () => {
    if (!activeDatasetId || !autoTargetVariable) {
      alert('Please select the target variable first');
      return;
    }
    if (!availableVariables || availableVariables.length === 0) {
      alert('No variables available');
      return;
    }

    // Compute remaining variables (exclude obvious identifiers and target)
    const exclude = ['ID', 'MEMBER_ID', 'SEGMENT', 'segment'];
    const remaining = availableVariables.filter(v => v !== autoTargetVariable && !exclude.includes(v.toUpperCase()));
    if (remaining.length === 0) {
      alert('No independent variables available after excluding the target variable');
      return;
    }

    setIsCalculatingVIF(true);
    setVifCorrelationData(null);
    setStep1LoadError(null);

    try {
      const startResponse = await fastApiService.startCalculateVifCorrelation({
        dataset_id: activeDatasetId,
        target_column: autoTargetVariable,
        independent_variables: remaining
      });

      if (!startResponse.success || !startResponse.job_id) {
        throw new Error('Failed to start variable analysis job');
      }

      const jobId = startResponse.job_id;
      console.log('✅ Variable analysis job started:', jobId);

      const pollInterval = 2000;
      let polls = 0;

      for (;;) {
        polls++;
        const statusResponse = await fastApiService.getVifCorrelationStatus(jobId);

        if (statusResponse.status === 'completed') {
          if (statusResponse.result) {
            setVifCorrelationData(statusResponse.result);
            setShowVifPreview(true);
            setIsCalculatingVIF(false);
            console.log('✅ Variable analysis completed');
          } else {
            throw new Error('Analysis completed but no result returned');
          }
          return;
        }
        if (statusResponse.status === 'failed') {
          setIsCalculatingVIF(false);
          throw new Error(statusResponse.error || 'Variable analysis failed');
        }
        if (statusResponse.status === 'running' || statusResponse.status === 'pending') {
          if (polls % 10 === 0) {
            console.log(`Variable analysis in progress... (${polls * 2}s elapsed)`);
          }
          await delayMs(pollInterval);
          continue;
        }
        setIsCalculatingVIF(false);
        throw new Error(`Unknown job status: ${statusResponse.status}`);
      }
    } catch (error) {
      console.error('Variable analysis failed:', error);
      const msg = error instanceof Error ? error.message : 'Unknown error';
      setStep1LoadError(msg);
      alert(`Variable analysis failed: ${msg}`);
      setIsCalculatingVIF(false);
    }
  };

  // Auto training handlers
  // Uses async background job with polling to prevent timeout errors in Azure.
  // Works for both Global Auto and Segment Auto modes.
  //
  // Retry contract (per user spec):
  //   - On any failure (job failed, interrupted, network error) increment
  //     consecutiveFailures. If consecutiveFailures < MAX_CONSECUTIVE_FAILURES,
  //     re-enqueue a brand-new job and keep going.
  //   - If a job completes successfully, reset consecutiveFailures to 0.
  //   - Only surface the error to the user when consecutiveFailures reaches
  //     MAX_CONSECUTIVE_FAILURES (3 consecutive failures with no success in
  //     between).
  const MAX_CONSECUTIVE_FAILURES = 3;
  const POLL_INTERVAL_MS = 2000;

  const handleAutoAnalysis = async () => {
    if (!activeDatasetId || !autoTargetVariable) return;

    setIsAnalyzing(true);
    setStep1LoadError(null);

    let consecutiveFailures = 0;

    const applyResult = (response: any) => {
      setAutoAnalysisData(response);
      setAutoProblemType(response.problem_type.problem_type);
      setAutoVariableSelection(response.variable_selection);
      setAutoAlgorithmSelection(response.algorithm_selection);

      const initialSelection: Record<string, boolean> = {};
      response.variable_selection.selected_variables.forEach((variable: string) => {
        initialSelection[variable] = true;
      });
      setManualVariableSelection(initialSelection);

      const initialAlgoChoices: Record<string, boolean> = {};
      (response.algorithm_selection?.selected_algorithms || []).forEach((algo: any) => {
        const key = algo.name || algo.display_name;
        if (key) initialAlgoChoices[key] = true;
      });
      setAutoAlgorithmChoices(initialAlgoChoices);
    };

    // Outer retry loop — each iteration is one full job attempt.
    while (consecutiveFailures < MAX_CONSECUTIVE_FAILURES) {
      const attempt = consecutiveFailures + 1;
      try {
        console.log(`🔄 Auto analysis attempt ${attempt}/${MAX_CONSECUTIVE_FAILURES}`);

        const startResponse = await fastApiService.startAnalyzeDatasetForAutoTraining({
          dataset_id: activeDatasetId,
          target_column: autoTargetVariable,
        });

        if (!startResponse.success || !startResponse.job_id) {
          throw new Error('Failed to start auto analysis job');
        }

        const jobId = startResponse.job_id;
        console.log('✅ Auto analysis job started:', jobId);

        let polls = 0;
        let jobSucceeded = false;

        // Inner polling loop — poll until terminal state.
        for (;;) {
          polls++;
          const statusResponse = await fastApiService.getAutoTrainingAnalyzeStatus(jobId);

          if (statusResponse.status === 'completed') {
            if (!statusResponse.result) {
              throw new Error('Analysis completed but no result returned');
            }
            applyResult(statusResponse.result);
            jobSucceeded = true;
            break;
          }

          if (statusResponse.status === 'failed') {
            throw new Error(statusResponse.error || 'Auto analysis failed');
          }

          if (statusResponse.status === 'running' || statusResponse.status === 'pending') {
            if (polls % 10 === 0) {
              console.log(`Auto analysis in progress... (${polls * POLL_INTERVAL_MS / 1000}s elapsed)`);
            }
            await delayMs(POLL_INTERVAL_MS);
            continue;
          }

          throw new Error(`Unknown job status: ${statusResponse.status}`);
        }

        if (jobSucceeded) {
          // Success — reset counter and exit.
          consecutiveFailures = 0;
          setIsAnalyzing(false);
          console.log('✅ Auto analysis completed');
          return;
        }

      } catch (error) {
        consecutiveFailures++;
        const msg = error instanceof Error ? error.message : 'Unknown error';
        console.warn(
          `⚠️ Auto analysis attempt ${attempt} failed (consecutive failures: ${consecutiveFailures}/${MAX_CONSECUTIVE_FAILURES}): ${msg}`
        );

        if (consecutiveFailures < MAX_CONSECUTIVE_FAILURES) {
          // Not yet at limit — wait briefly before retrying.
          const backoffMs = 3000 * consecutiveFailures;
          console.log(`🔁 Retrying in ${backoffMs / 1000}s…`);
          await delayMs(backoffMs);
        }
        // If consecutiveFailures === MAX_CONSECUTIVE_FAILURES the while
        // condition will be false on next evaluation and we fall through
        // to the terminal error block below.
      }
    }

    // Reached here only when all 3 consecutive attempts failed.
    const finalMsg =
      `Auto analysis failed after ${MAX_CONSECUTIVE_FAILURES} consecutive attempts. ` +
      `Please check the server logs and retry.`;
    console.error('Error in auto analysis:', finalMsg);
    setStep1LoadError(finalMsg);
    alert(`Failed to analyze dataset for auto training: ${finalMsg}`);
    setIsAnalyzing(false);
  };

  // Fetch CodeBook Function
  const handleViewCodebook = async () => {
    try {
      setIsLoadingCodebook(true);
      setIsCodebookOpen(true);
      
      // Determine training mode and type based on current state
      const mode = trainingMode; // 'global' or 'segment-specific'
      const type = activeTab === 'auto' ? 'auto' : 'manual';
      
      // Map 'segment-specific' to 'segment' for API call
      const apiMode = mode === 'segment-specific' ? 'segment' : 'global';
      
      console.log(`Fetching codebook for ${apiMode}/${type}`);
      
      // Use fastApiService instead of direct fetch to handle Azure routing correctly
      const data = await fastApiService.getCodebook(apiMode, type);
      
      if (!data.source_code) {
        throw new Error('No source code returned from server');
      }
      
      setCodebookContent(data.source_code);
      setCodebookFileName(data.file_name);
      setIsLoadingCodebook(false);
      
      console.log(`✅ Successfully loaded codebook: ${data.file_name} (${data.source_code.length} characters)`);
    } catch (error) {
      console.error('❌ Error fetching codebook:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      alert(`Failed to load codebook.\n\nError: ${errorMessage}\n\nPlease check the browser console (F12) for full details.`);
      setIsCodebookOpen(false);
      setIsLoadingCodebook(false);
    }
  };

  const handleAutoTraining = async () => {
    if (!activeDatasetId || !autoTargetVariable) return;
    if (!variableSelectionConfirmed) {
      alert('Confirm your variables and run RFE in the variable screener (Step 2) before starting auto training.');
      return;
    }

    setIsAutoTraining(true);

    try {
      // Prefer Step 4 reviewed variables whenever available.
      // Fallback to the previous step selections until Step 4 is available.
      let fallbackVariables: string[] = [];
      if (variableSelectionMode === 'manual') {
        fallbackVariables = Object.keys(manualVariableSelection).filter((variable) => manualVariableSelection[variable]);
      } else {
        fallbackVariables = autoVariableSelection?.selected_variables || [];
      }
      const selectedVariables = resolveStep5InputVariables(fallbackVariables);

      if (selectedVariables.length === 0) {
        alert('No variables available for Auto Training. Please complete variable selection (or Step 4 once available) and try again.');
        setIsAutoTraining(false);
        return;
      }

      // Keep algorithm selection in backend-defined auto flow.
      const selectedAlgorithms: string[] | undefined = undefined;

      const response = await fastApiService.runCompleteAutoTraining({
        dataset_id: activeDatasetId,
        target_column: autoTargetVariable,
        selected_variables: selectedVariables,
        locked_variables: getLockedVariableList(),
        selection_mode: 'auto',
        selected_algorithms: selectedAlgorithms
      });

      // Extract the results from the response (backend wraps in success object)
      console.log('📊 Full Response:', response);
      console.log('📈 Response Results:', response.results);
      console.log('🔍 Response Type:', typeof response);
      
      const results = response.results || response;
      console.log('✅ Setting Auto Training Results:', {
        hasResults: !!results?.results,
        resultsLength: results?.results?.length,
        numModelsTrained: results?.auto_selection_summary?.num_models_trained,
        usedFeatures: results?.used_features?.length,
        algorithms: results?.algorithm_selection?.selected_algorithms?.length,
        problemType: results?.problem_type
      });
      
      setAutoTrainingResults(results);
      setActiveTab('auto');
      
      // ✅ PRESERVE: Store training results in sessionStorage for documentation (Documentation agent needs this)
      try {
        sessionStorage.setItem('training_results', JSON.stringify(results));
        console.log('✅ Training results stored in sessionStorage for documentation');
        
        const selectionSummary = buildModelSelectionSummary(results);
        sessionStorage.setItem('model_selection_summary', JSON.stringify(selectionSummary));
        console.log('✅ Model selection summary cached for documentation');
      } catch (e) {
        console.error('Failed to store training results in sessionStorage:', e);
      }

      // ✅ NEW: Store results for UI persistence (keyed by dataset and mode)
      const storageKey = getResultsStorageKey('auto');
      if (storageKey) {
        try {
          sessionStorage.setItem(storageKey, JSON.stringify(results));
          console.log('✅ Auto training results stored for UI persistence');
        } catch (e) {
          console.error('Failed to store auto training results for UI persistence:', e);
        }
      }
      notifyMtaTrainingResultsPersisted(activeDatasetId);
    } catch (error) {
      console.error('Error in auto training:', error);

      // If the user cancelled, silently exit without showing an error
      if (error instanceof Error && error.message === 'cancelled') {
        return;
      }

      // Provide more specific error messages based on the error type
      let errorMessage = 'Failed to complete auto training';

      if (error instanceof Error) {
        if (error.message.includes('Failed to load dataset')) {
          errorMessage = 'Failed to load the dataset. Please check if the dataset exists and try again.';
        } else if (error.message.includes('Failed to detect problem type')) {
          errorMessage = 'Failed to analyze the target variable. Please ensure the target variable is valid.';
        } else if (error.message.includes('Failed to select variables')) {
          errorMessage = 'Failed to select appropriate variables for training. Please try with different variables.';
        } else if (error.message.includes('Failed to train models')) {
          errorMessage = 'Failed to train the models. This might be due to insufficient data or incompatible parameters.';
        } else if (error.message.includes('HTTP error')) {
          errorMessage = 'Network error occurred. Please check your connection and try again.';
        } else {
          errorMessage = `Auto training failed: ${error.message}`;
        }
      }

      alert(errorMessage);
    } finally {
      setIsAutoTraining(false);
    }
  };

  // Segment Auto Training Handler
  const handleSegmentAutoTraining = async () => {
    if (!activeDatasetId || !autoTargetVariable) {
      alert('Please select a dataset and target variable');
      return;
    }

    if (!segmentInfo || !segmentInfo.available) {
      alert('No segments detected in the dataset. Please ensure your dataset has a segment column.');
      return;
    }

    if (!variableSelectionConfirmed) {
      alert('Confirm your variables and run RFE in the variable screener (Step 2) before starting segment auto training.');
      return;
    }

    setSegmentAutoTrainingInProgress(true);
    setSegmentAutoStep('analyzing');

    try {
      console.log('🚀 Starting Segment Auto Training...');

      // Prefer Step 4 reviewed variables whenever available.
      // Fallback to the previous step selections until Step 4 is available.
      let fallbackVariables: string[] = [];
      if (variableSelectionMode === 'manual') {
        fallbackVariables = Object.keys(manualVariableSelection).filter((variable) => manualVariableSelection[variable]);
      } else {
        fallbackVariables = autoVariableSelection?.selected_variables || [];
      }
      const selectedVariables = resolveStep5InputVariables(fallbackVariables);
      if (!selectedVariables.length) {
        alert('No variables available for Auto Training. Please complete variable selection (or Step 4 once available) and try again.');
        setSegmentAutoTrainingInProgress(false);
        setSegmentAutoStep('idle');
        return;
      }

      // Keep algorithm selection in backend-defined auto flow.
      const selectedAlgorithms: string[] | undefined = undefined;

      setSegmentAutoStep('training');

      // Run segment auto training
      const result = await fastApiService.runSegmentAutoTraining({
        dataset_id: activeDatasetId,
        target_column: autoTargetVariable,
        selected_variables: selectedVariables,
        locked_variables: getLockedVariableList(),
        selection_mode: 'auto',
        selected_algorithms: selectedAlgorithms
      });

      console.log('✅ Segment Auto Training completed:', result);

      // Store results
      setSegmentAutoTrainingResults(result);
      setActiveTab('auto');
      setSegmentAutoStep('completed');

      // ✅ PRESERVE: Store training results in sessionStorage for documentation (Documentation agent needs this)
      try {
        sessionStorage.setItem('training_results', JSON.stringify(result));
        console.log('✅ Segment auto training results stored in sessionStorage for documentation');
        
        const selectionSummary = buildModelSelectionSummary(result);
        sessionStorage.setItem('model_selection_summary', JSON.stringify(selectionSummary));
        console.log('✅ Model selection summary cached for documentation (segment auto training)');
      } catch (e) {
        console.error('Failed to store segment auto training results in sessionStorage:', e);
      }

      // ✅ NEW: Store results for UI persistence (keyed by dataset and mode)
      const segmentAutoStorageKey = getResultsStorageKey('segment-auto');
      if (segmentAutoStorageKey) {
        try {
          sessionStorage.setItem(segmentAutoStorageKey, JSON.stringify(result));
          console.log('✅ Segment auto training results stored for UI persistence');
        } catch (e) {
          console.error('Failed to store segment auto training results for UI persistence:', e);
        }
      }
      notifyMtaTrainingResultsPersisted(activeDatasetId);

      // Show success message
      alert(`Segment Auto Training completed successfully! Trained models for ${result.successful_segments} out of ${result.total_segments} segments.`);

    } catch (error) {
      console.error('❌ Segment Auto Training failed:', error);

      // If user cancelled, treat as normal stop
      if (error instanceof Error && error.message === 'cancelled') {
        setSegmentAutoStep('idle');
        return;
      }

      setSegmentAutoStep('error');
      
      let errorMessage = 'Segment Auto Training failed';
      if (error instanceof Error) {
        errorMessage = `Segment Auto Training failed: ${error.message}`;
      }
      alert(errorMessage);
    } finally {
      setSegmentAutoTrainingInProgress(false);
    }
  };

  // Cancel handlers for long-running training jobs
  const handleCancelAutoTrainingClick = async () => {
    if (!isAutoTraining) return;
    const confirmed = window.confirm('Cancel current global auto training?');
    if (!confirmed) return;

    try {
      await fastApiService.cancelAutoTrainingJob();
    } catch (error) {
      console.error('Failed to cancel auto training', error);
      alert('Could not cancel auto training. Please check the console for details.');
    } finally {
      setIsAutoTraining(false);
    }
  };

  const handleCancelSegmentAutoTrainingClick = async () => {
    if (!segmentAutoTrainingInProgress) return;
    const confirmed = window.confirm('Cancel current segment auto training?');
    if (!confirmed) return;

    try {
      await fastApiService.cancelSegmentAutoTrainingJob();
    } catch (error) {
      console.error('Failed to cancel segment auto training', error);
      alert('Could not cancel segment auto training. Please check the console for details.');
    } finally {
      setSegmentAutoTrainingInProgress(false);
      setSegmentAutoStep('idle');
    }
  };

  // Quick Variable Analysis for Manual step: use all remaining variables after selecting target
  // Uses async background job with polling to prevent timeout errors in Azure
  const handleManualVariableAnalysis = async () => {
    if (!activeDatasetId || !manualTargetVariable) {
      alert('Please select the target variable first');
      return;
    }
    if (!availableVariables || availableVariables.length === 0) {
      alert('No variables available');
      return;
    }

    const exclude = ['ID', 'MEMBER_ID', 'SEGMENT', 'segment'];
    const remaining = availableVariables.filter(v => v !== manualTargetVariable && !exclude.includes(v.toUpperCase()));
    if (remaining.length === 0) {
      alert('No independent variables available after excluding the target variable');
      return;
    }

    setIsCalculatingVIF(true);
    setVifCorrelationData(null);
    setStep1LoadError(null);

    try {
      const startResponse = await fastApiService.startCalculateVifCorrelation({
        dataset_id: activeDatasetId,
        target_column: manualTargetVariable,
        independent_variables: remaining
      });

      if (!startResponse.success || !startResponse.job_id) {
        throw new Error('Failed to start variable analysis job');
      }

      const jobId = startResponse.job_id;
      console.log('✅ Variable analysis job started:', jobId);

      const pollInterval = 2000;
      let polls = 0;

      for (;;) {
        polls++;
        const statusResponse = await fastApiService.getVifCorrelationStatus(jobId);

        if (statusResponse.status === 'completed') {
          if (statusResponse.result) {
            setVifCorrelationData(statusResponse.result);
            setShowVifPreview(true);
            setIsCalculatingVIF(false);
            console.log('✅ Variable analysis completed');
          } else {
            throw new Error('Analysis completed but no result returned');
          }
          return;
        }
        if (statusResponse.status === 'failed') {
          setIsCalculatingVIF(false);
          throw new Error(statusResponse.error || 'Variable analysis failed');
        }
        if (statusResponse.status === 'running' || statusResponse.status === 'pending') {
          if (polls % 10 === 0) {
            console.log(`Variable analysis in progress... (${polls * 2}s elapsed)`);
          }
          await delayMs(pollInterval);
          continue;
        }
        setIsCalculatingVIF(false);
        throw new Error(`Unknown job status: ${statusResponse.status}`);
      }
    } catch (error) {
      console.error('Variable analysis failed:', error);
      const msg = error instanceof Error ? error.message : 'Unknown error';
      setStep1LoadError(msg);
      alert(`Variable analysis failed: ${msg}`);
      setIsCalculatingVIF(false);
    }
  };

  // Apply variable screener filters to variable stats
  useEffect(() => {
    if (!vifCorrelationData?.variable_statistics) {
      setFilteredVariables([]);
      return;
    }
    const stats: Array<{ variable: string; correlation: number; vif: number | null; iv?: number | null }> =
      vifCorrelationData.variable_statistics;

    const passesAll = (s: { correlation: number; vif: number | null; iv?: number | null }) => {
      return variableFilters.every((f) => {
        const minVal = f.value === '' ? undefined : parseFloat(f.value);
        const maxVal = f.valueMax === '' || typeof f.valueMax === 'undefined' ? undefined : parseFloat(f.valueMax);
        let metricVal: number;
        if (f.metric === 'correlation') {
          metricVal = Math.abs(s.correlation || 0);
        } else if (f.metric === 'vif') {
          metricVal = s.vif ?? Number.POSITIVE_INFINITY;
        } else {
          metricVal = typeof s.iv === 'number' ? s.iv : -Infinity;
        }
        if (f.operator === '>=') return typeof minVal === 'number' ? metricVal >= minVal : true;
        if (f.operator === '<=') return typeof minVal === 'number' ? metricVal <= minVal : true;
        if (f.operator === '==') return typeof minVal === 'number' ? metricVal === minVal : true;
        if (f.operator === 'between') return (typeof minVal === 'number' ? metricVal >= minVal : true) && (typeof maxVal === 'number' ? metricVal <= maxVal : true);
        return true;
      });
    };

    const selected = stats.filter(passesAll).map((x) => x.variable);
    setFilteredVariables(selected);
  }, [vifCorrelationData, variableFilters]);

  // Auto-trigger Step 1 variable analysis when Model Training opens (once per dataset+target).
  // Guards:
  //   - Skip if MTA state has not been restored from sessionStorage yet for
  //     this (dataset, mode) combo — otherwise we race the restore effect and
  //     re-fire analysis while it's still inflating autoAnalysisData.
  //   - Skip if sessionStorage already has step-1 analysis data for this
  //     dataset+mode (the restore effect will hydrate it on the next render).
  //   - Skip if state already has data or is busy.
  useEffect(() => {
    if (!activeDatasetId) return;

    const mtaKey = getMtaStateStorageKey();
    if (!mtaKey) return;
    if (restoredMtaKey !== mtaKey) return;

    // If persisted state already has step-1 analysis, let the restore effect
    // populate state and don't re-run the API.
    try {
      const raw = sessionStorage.getItem(mtaKey);
      if (raw) {
        const persisted = JSON.parse(raw) as {
          autoAnalysisData?: any;
          vifCorrelationData?: any;
        };
        if (persisted?.autoAnalysisData || persisted?.vifCorrelationData) {
          return;
        }
      }
    } catch {
      // Parsing errors are non-fatal — fall through to the in-memory checks.
    }

    const hasStep1Data = !!(autoAnalysisData || vifCorrelationData);
    const step1IsBusy = isAnalyzing || isCalculatingVIF;
    if (hasStep1Data || step1IsBusy) return;

    const targetForKey = autoTargetVariable || manualTargetVariable || '';
    if (!targetForKey) return;

    const triggerKey = `${activeDatasetId}::${targetForKey}`;
    if (step1AutoTriggerRef.current[triggerKey]) return;

    // Prefer auto analysis flow; fallback to manual analysis if auto target is unavailable.
    if (autoTargetVariable) {
      step1AutoTriggerRef.current[triggerKey] = true;
      void handleAutoAnalysis();
      return;
    }

    if (manualTargetVariable && availableVariables.length > 0) {
      step1AutoTriggerRef.current[triggerKey] = true;
      void handleManualVariableAnalysis();
    }
  }, [
    activeDatasetId,
    autoTargetVariable,
    manualTargetVariable,
    autoAnalysisData,
    vifCorrelationData,
    isAnalyzing,
    isCalculatingVIF,
    availableVariables.length,
    getMtaStateStorageKey,
  ]);

  // If auto-analysis stats exist but VIF is unusable, fallback to manual VIF endpoint once.
  useEffect(() => {
    if (!activeDatasetId || isAnalyzing || isCalculatingVIF) return;
    if (!manualTargetVariable || availableVariables.length === 0) return;
    if (vifCorrelationData?.variable_statistics?.length) return;

    const autoStats = autoAnalysisData?.variable_analysis?.variable_statistics;
    if (!Array.isArray(autoStats) || autoStats.length === 0) return;

    const autoHasAnyVif = autoStats.some((stat: any) => getNormalizedVifValue(stat) !== null);
    if (autoHasAnyVif) return;

    const fallbackKey = `${activeDatasetId}::${manualTargetVariable}`;
    if (step1VifFallbackRef.current[fallbackKey]) return;

    step1VifFallbackRef.current[fallbackKey] = true;
    void handleManualVariableAnalysis();
  }, [
    activeDatasetId,
    manualTargetVariable,
    autoAnalysisData,
    vifCorrelationData,
    isAnalyzing,
    isCalculatingVIF,
    availableVariables.length,
  ]);

  // Set sensible default target metric based on detected manual problem type
  useEffect(() => {
    if (manualProblemType === 'classification') {
      setTargetMetricManual('auc');
    } else if (manualProblemType === 'regression') {
      setTargetMetricManual('r2');
    } else {
      setTargetMetricManual('');
    }
  }, [manualProblemType]);

  // Download handler for model artifacts
  const handleDownloadArtifacts = async (format: 'csv' | 'excel' | 'txt') => {
    if (!trainingResults?.model_id) {
      alert('No model results available for download');
      return;
    }

    try {
      const response = await fetch(`/api/v1/models/${trainingResults.model_id}/download-artifacts?format=${format}`, {
        method: 'GET',
        headers: {
          ...buildMidasAuthHeaders(),
        },
      });

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${trainingResults.model_id}_metrics.${format}`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        // Close download menu
        setShowDownloadMenu(false);
      } else {
        throw new Error(`Download failed: ${response.statusText}`);
      }
    } catch (error) {
      console.error('Download failed:', error);
      alert(`Download failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  return (
    <div className="space-y-6 model-training-step mta-training-page">
      {/* Data Split Component */}
      <DataSplit activeDatasetId={activeDatasetId} datasetAnalysis={datasetAnalysis} stepKey={4.5} showSamplingUI={false} />

      {/* Header */}
      <div className={`${MTA_SECTION} bg-gradient-to-r from-blue-50 via-indigo-50/80 to-white dark:from-slate-900 dark:via-slate-900 dark:to-slate-800 border-blue-200/80 dark:border-slate-600 p-6 md:p-8`}>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4 min-w-0">
            <div className="p-3.5 bg-gradient-to-br from-blue-600 to-indigo-700 rounded-2xl shadow-lg shadow-blue-600/25 ring-2 ring-white/40 dark:ring-slate-900/50 shrink-0">
              <Brain className="h-8 w-8 text-white" />
            </div>
            <div className="min-w-0">
              <h3 className={MTA_TITLE_PAGE}>Model Training Agent</h3>
              <p className="text-sm md:text-base text-gray-600 dark:text-gray-300 mt-2 max-w-2xl leading-relaxed">
                Automated ML training workflow with hyperparameter optimization.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-sm shrink-0">
            <div className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-100 dark:bg-emerald-900/40 text-emerald-800 dark:text-emerald-200 rounded-full font-medium border border-emerald-200/80 dark:border-emerald-800/50 shadow-sm">
              <Activity className="h-4 w-4" />
              <span>Live workspace</span>
            </div>
          </div>
        </div>
      </div>

      {/* Workflow Overview - Hidden */}
      {/* 
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h4 className="font-semibold text-gray-900 mb-4 flex items-center space-x-2">
          <Info className="h-5 w-5 text-blue-600" />
          <span>6-Step Automated Training Workflow</span>
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {workflowSteps.map((step) => {
            const Icon = step.icon;
            const isCompleted = currentStep > step.id;
            const isActive = currentStep === step.id && isTraining;
            
            return (
              <div
                key={step.id}
                className={`p-4 rounded-lg border-2 transition-all ${
                  isActive
                    ? 'border-blue-600 bg-blue-50'
                    : isCompleted
                    ? 'border-green-600 bg-green-50'
                    : 'border-gray-200 bg-gray-50'
                }`}
              >
                <div className="flex items-center space-x-3">
                  <div className={`p-2 rounded-lg ${
                    isActive
                      ? 'bg-blue-600'
                      : isCompleted
                      ? 'bg-green-600'
                      : 'bg-gray-400'
                  }`}>
                    {isCompleted ? (
                      <CheckCircle className="h-5 w-5 text-white" />
                    ) : isActive ? (
                      <Icon className="h-5 w-5 text-white animate-pulse" />
                    ) : (
                      <Icon className="h-5 w-5 text-white opacity-50" />
                    )}
                  </div>
                  <div className="flex-1">
                    <div className="text-xs text-gray-500 font-medium">Step {step.id}/6</div>
                    <div className={`text-sm font-medium ${
                      isActive ? 'text-blue-900' : isCompleted ? 'text-green-900' : 'text-gray-600'
                    }`}>
                      {step.name}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="mt-4 pt-4 border-t border-gray-200">
          <div className="text-xs font-medium text-gray-500 mb-2">QUALITY ASSURANCE CHECKPOINTS:</div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="flex items-center space-x-2 text-sm text-gray-600">
              <div className="w-2 h-2 bg-amber-500 rounded-full"></div>
              <span><strong>Optimization Gate</strong></span>
            </div>
            <div className="flex items-center space-x-2 text-sm text-gray-600">
              <div className="w-2 h-2 bg-amber-500 rounded-full"></div>
              <span><strong>After Step 5:</strong> Performance Gate</span>
            </div>
            <div className="flex items-center space-x-2 text-sm text-gray-600">
              <div className="w-2 h-2 bg-amber-500 rounded-full"></div>
              <span><strong>Before Step 7:</strong> Production Readiness</span>
            </div>
          </div>
        </div>
      </div>
      */}

      {/* DataSet Preview */}
      {datasetPreviewData && (
        <div className="hidden bg-white rounded-lg border border-gray-200">
          <div className="flex items-center justify-between p-4 border-b border-gray-200">
            <div className="flex items-center space-x-2">
              <h4 className="font-semibold text-gray-900">DataSet Preview</h4>
              <ChevronUp className="h-4 w-4 text-gray-500" />
            </div>
            <button
              onClick={() => setShowDatasetPreview(!showDatasetPreview)}
              className="text-sm text-gray-500 hover:text-gray-700 transition-colors"
            >
              {showDatasetPreview ? 'Hide' : 'Show'}
            </button>
          </div>
          
          {showDatasetPreview && (
            <div className="p-4">
              <div className="mb-4 space-y-1">
                <div className="text-sm text-gray-600">
                  <strong>Dataset Shape:</strong> {datasetPreviewData.shape.rows.toLocaleString()} rows × {datasetPreviewData.shape.columns} columns
                </div>
              </div>
              
              <div className="overflow-x-auto border border-gray-200 rounded-lg max-h-96">
                <table className="w-full text-sm min-w-max">
                  <thead className={`${MTA_THEAD} sticky top-0`}>
                    <tr>
                      {datasetPreviewData.columns.map((column) => (
                        <th key={column} className="px-3 py-2 text-left font-medium text-gray-700 border-r border-gray-200 last:border-r-0 whitespace-nowrap min-w-24">
                          {column}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {datasetPreviewData.preview.map((row, index) => (
                      <tr key={index} className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                        {datasetPreviewData.columns.map((column) => (
                          <td key={column} className="px-3 py-2 text-gray-900 border-r border-gray-200 last:border-r-0 whitespace-nowrap">
                            {(() => {
                              const value = row[column];
                              if (value === null || value === undefined) {
                                return 'N/A';
                              }
                              if (typeof value === 'number') {
                                return value.toLocaleString();
                              }
                              if (typeof value === 'object') {
                                return JSON.stringify(value);
                              }
                              return String(value);
                            })()}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Step 1 (Common): Lock Variables */}
      {(autoAnalysisData || vifCorrelationData || isAnalyzing || isCalculatingVIF || step1LoadError) && (
        <div className={`mt-6 ${MTA_SECTION} p-5 md:p-6 bg-gradient-to-br from-amber-50/90 via-white to-amber-50/40 dark:from-slate-900 dark:via-slate-900 dark:to-slate-800`}>
          <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
            <div className="flex items-start gap-3 md:gap-4 min-w-0">
              <span className={MTA_STEP_NUM} title="Step 1">
                1
              </span>
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-amber-500/20 dark:bg-amber-500/15 ring-1 ring-amber-400/40 dark:ring-amber-600/30">
                <Lock className="h-6 w-6 text-amber-800 dark:text-amber-200" />
              </div>
              <div className="min-w-0">
                <h4 className={MTA_TITLE_SECTION}>Lock variables</h4>
                <p className="text-sm text-gray-600 dark:text-gray-300 mt-1.5 max-w-3xl">
                  Shared for auto and manual modes. Mark must-keep predictors before screening and training.
                </p>
              </div>
            </div>
            <div className="text-xs px-3 py-1.5 rounded-full bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-100 font-semibold border border-amber-200/80 dark:border-amber-700/50 shadow-sm">
              {getLockedVariableList().length} locked
            </div>
          </div>

          {step1LoadError && (
            <div className="mb-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/40 px-4 py-3 text-sm text-red-800 dark:text-red-200">
              <div className="flex items-start gap-2 min-w-0">
                <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
                <span className="min-w-0 break-words">{step1LoadError}</span>
              </div>
              <button
                type="button"
                className="shrink-0 rounded-md bg-red-100 dark:bg-red-900/50 px-3 py-1.5 text-xs font-medium text-red-900 dark:text-red-100 hover:bg-red-200 dark:hover:bg-red-900 border border-red-200 dark:border-red-800"
                onClick={() => {
                  setStep1LoadError(null);
                  const tk = `${activeDatasetId || ''}::${autoTargetVariable || manualTargetVariable || ''}`;
                  delete step1AutoTriggerRef.current[tk];
                  if (autoTargetVariable) void handleAutoAnalysis();
                  else if (manualTargetVariable && availableVariables.length > 0) {
                    void handleManualVariableAnalysis();
                  }
                }}
              >
                Retry
              </button>
            </div>
          )}

          {(() => {
            const isStep1Loading = isAnalyzing || isCalculatingVIF;
            const lockCandidates = getCommonLockCandidates();

            if (isStep1Loading && lockCandidates.length === 0) {
              return (
                <div className="border border-amber-200 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-900/60 p-6">
                  <div className="flex items-center justify-center space-x-3 text-amber-800 dark:text-amber-200">
                    <Loader className="h-5 w-5 animate-spin" />
                    <div>
                      <div className="text-sm font-medium">Loading Step 1 variable statistics...</div>
                      <div className="text-xs text-gray-600 dark:text-gray-300">Calculating IV, VIF, |Corr|, Type, Source and Miss %</div>
                    </div>
                  </div>
                </div>
              );
            }

            if (!isStep1Loading && lockCandidates.length === 0 && !step1LoadError) {
              return (
                <div className="border border-amber-200 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-900/60 p-4 text-xs text-gray-600 dark:text-gray-300">
                  Run variable analysis to load Step 1 lock candidates.
                </div>
              );
            }

            if (!isStep1Loading && lockCandidates.length === 0 && step1LoadError) {
              return null;
            }

            return (
              <div className={MTA_TABLE_SHELL}>
                {/* Inner scroll: MTA_TABLE_SHELL uses overflow-hidden for chrome; scrolling must be on a child */}
                <div className="max-h-72 min-h-0 overflow-y-auto overflow-x-auto overscroll-contain">
                <table className="w-full min-w-[980px] table-fixed text-xs">
                  <colgroup>
                    <col className="w-[12.5%]" />
                    <col className="w-[12.5%]" />
                    <col className="w-[12.5%]" />
                    <col className="w-[12.5%]" />
                    <col className="w-[12.5%]" />
                    <col className="w-[12.5%]" />
                    <col className="w-[12.5%]" />
                    <col className="w-[12.5%]" />
                  </colgroup>
                  <thead className={`${MTA_THEAD} sticky top-0 z-10`}>
                    <tr>
                      <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">Lock</th>
                      <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">Variable</th>
                      <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">Type</th>
                      <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">Source</th>
                      <th className="px-3 py-2.5 text-right font-semibold whitespace-nowrap">IV</th>
                      <th className="px-3 py-2.5 text-right font-semibold whitespace-nowrap">VIF</th>
                      <th className="px-3 py-2.5 text-right font-semibold whitespace-nowrap">|Corr|</th>
                      <th className="px-3 py-2.5 text-right font-semibold whitespace-nowrap">Miss %</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-slate-700">
                    {lockCandidates.map((stat: any, index: number) => {
                      const variableName = String(stat?.variable ?? '');
                      const isLocked = !!lockedVariables[variableName];
                      const absCorr = Math.abs(Number(stat?.correlation ?? 0));
                      const variableType = String(stat?.type ?? (stat?.is_categorical ? 'Categorical' : 'Continuous'));
                      const variableSource = String(stat?.source ?? 'Original');
                      const missingPct = Number(stat?.missing_pct ?? 0);
                      return (
                        <tr
                          key={`${variableName}_${index}`}
                          className="bg-white dark:bg-slate-950 hover:bg-blue-50/50 dark:hover:bg-slate-800/60 transition-colors"
                        >
                          <td className="px-3 py-2.5">
                            <button
                              type="button"
                              onClick={() => {
                                if (variableSelectionConfirmed) return;
                                setLockedVariables((prev) => ({
                                  ...prev,
                                  [variableName]: !prev[variableName],
                                }));
                              }}
                              disabled={variableSelectionConfirmed}
                              className={`inline-flex items-center justify-center h-6 w-6 rounded border ${
                                isLocked
                                  ? 'bg-amber-600 border-amber-600 text-white'
                                  : 'bg-white dark:bg-slate-900 border-gray-300 dark:border-slate-600 text-gray-500 dark:text-gray-300'
                              } ${variableSelectionConfirmed ? 'opacity-60 cursor-not-allowed' : ''}`}
                            >
                              {isLocked ? <Lock className="h-3.5 w-3.5" /> : <Unlock className="h-3.5 w-3.5" />}
                            </button>
                          </td>
                          <td className="px-3 py-2.5 text-gray-900 dark:text-white whitespace-nowrap">{variableName}</td>
                          <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{variableType}</td>
                          <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{variableSource}</td>
                          <td className="px-3 py-2.5 text-right text-gray-700 dark:text-gray-200 whitespace-nowrap">
                            {stat?.iv !== null && stat?.iv !== undefined ? Number(stat.iv).toFixed(3) : 'N/A'}
                          </td>
                          <td className="px-3 py-2.5 text-right text-gray-700 dark:text-gray-200 whitespace-nowrap">
                            {(() => {
                              const vifValue = getNormalizedVifValue(stat);
                              return vifValue !== null ? vifValue.toFixed(2) : 'N/A';
                            })()}
                          </td>
                          <td className="px-3 py-2.5 text-right text-gray-700 dark:text-gray-200 whitespace-nowrap">{absCorr.toFixed(3)}</td>
                          <td className="px-3 py-2.5 text-right text-gray-700 dark:text-gray-200 whitespace-nowrap">{missingPct.toFixed(1)}%</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                </div>
              </div>
            );
          })()}
        </div>
      )}

      {/* Step 2 (Common): Variable Screener */}
      {(autoAnalysisData || vifCorrelationData || isAnalyzing || isCalculatingVIF || step1LoadError) &&
        (getLockedVariableList().length > 0 || variableSelectionConfirmed) && (
        <div className={`mt-6 ${MTA_SECTION} p-5 md:p-6 bg-gradient-to-br from-blue-50/90 via-white to-indigo-50/50 dark:from-slate-900 dark:via-slate-900 dark:to-slate-800`}>
          <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
            <div className="flex items-start gap-3 md:gap-4 min-w-0">
              <span className={MTA_STEP_NUM} title="Step 2">
                2
              </span>
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-blue-500/15 dark:bg-blue-500/20 ring-1 ring-blue-300/50 dark:ring-blue-600/30">
                <Filter className="h-6 w-6 text-blue-700 dark:text-blue-300" />
              </div>
              <div className="min-w-0">
                <h4 className={MTA_TITLE_SECTION}>Variable screener</h4>
                <p className="text-sm text-gray-600 dark:text-gray-300 mt-1.5 max-w-3xl">
                  Dynamic filters on unlocked variables. Shared for auto and manual before training mode selection.
                </p>
              </div>
            </div>
            <div className="text-xs px-3 py-1.5 rounded-full bg-blue-100 text-blue-900 dark:bg-blue-900/40 dark:text-blue-100 font-semibold border border-blue-200/80 dark:border-blue-700/50 shadow-sm">
              {(() => {
                const lockedCount = getLockedVariableList().length;
                const screenedCount = getCommonFilteredScreenerCandidates().length;
                const liveCount = lockedCount + screenedCount;
                const confirmedCount = Object.values(manualVariableSelection).filter(Boolean).length;
                return variableSelectionConfirmed ? confirmedCount : liveCount;
              })()} selected
            </div>
          </div>

          {(() => {
            const allCandidates = getCommonScreenerCandidates();
            const filteredCandidates = getCommonFilteredScreenerCandidates();

            if (!(isAnalyzing || isCalculatingVIF) && allCandidates.length === 0) {
              return (
                <div className="border border-blue-200 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-900/60 p-4 text-xs text-gray-600 dark:text-gray-300">
                  Run variable analysis to load Step 2 screener candidates.
                </div>
              );
            }

            return (
              <div className="space-y-4">
                {(() => {
                  const unlockedCandidates = getCommonUnlockedScreenerCandidates();
                  const screenedUnlocked = filteredCandidates;
                  const lockedCount = getLockedVariableList().length;
                  const workingSetCount = lockedCount + screenedUnlocked.length;
                  const combinedPassLabel = `${screenedUnlocked.length} of ${unlockedCandidates.length}`;
                  const selectionSummary = `${lockedCount} locked + ${screenedUnlocked.length} screened = ${workingSetCount} variables`;
                  const operatorLabel = (op: string) => (op === 'gte' ? '≥' : op === 'lte' ? '≤' : op === 'gt' ? '>' : op === 'lt' ? '<' : '=');
                  const metricLabel = (m: string) => (m === 'correlation' ? '|Correlation|' : m === 'vif' ? 'VIF' : 'IV');

                  return (
                    <>
                      <div className="bg-white dark:bg-slate-900/60 border border-blue-200 dark:border-slate-700 rounded-lg p-4">
                        <div className="flex items-center justify-between mb-3">
                          <div>
                            <div className="text-sm font-semibold text-gray-900 dark:text-white">Dynamic screening filters</div>
                            <div className="text-xs text-gray-600 dark:text-gray-300 mt-1">
                              Filters operate on {unlockedCandidates.length} unlocked variables only. Add as many as needed.
                            </div>
                          </div>
                        </div>

                        <div className="space-y-2">
                          {autoActiveFilters.map((filter: any, index: number) => {
                            const passCount = unlockedCandidates.filter((stat: any) => doesScreenerFilterPass(stat, filter)).length;
                            return (
                              <div key={`filter_row_${index}`} className="grid grid-cols-12 gap-2 items-center rounded bg-gray-50 dark:bg-slate-900/80 border border-gray-200 dark:border-slate-700 p-2">
                                <div className="col-span-1 text-xs text-gray-500 dark:text-gray-300">{index + 1}</div>
                                <div className="col-span-3">
                                  <select
                                    value={filter.metric}
                                    disabled={variableSelectionConfirmed}
                                    onChange={(e) => {
                                      const next = [...autoActiveFilters];
                                      next[index] = { ...next[index], metric: e.target.value };
                                      setAutoActiveFilters(next);
                                    }}
                                    className={`w-full px-2 py-1.5 text-xs border border-gray-300 dark:border-slate-700 rounded bg-white dark:bg-slate-900 dark:text-white ${variableSelectionConfirmed ? 'opacity-70 cursor-not-allowed' : ''}`}
                                  >
                                    <option value="iv">IV</option>
                                    <option value="correlation">|Correlation|</option>
                                    <option value="vif">VIF</option>
                                  </select>
                                </div>
                                <div className="col-span-2">
                                  <select
                                    value={filter.operator}
                                    disabled={variableSelectionConfirmed}
                                    onChange={(e) => {
                                      const next = [...autoActiveFilters];
                                      next[index] = { ...next[index], operator: e.target.value };
                                      setAutoActiveFilters(next);
                                    }}
                                    className={`w-full px-2 py-1.5 text-xs border border-gray-300 dark:border-slate-700 rounded bg-white dark:bg-slate-900 dark:text-white ${variableSelectionConfirmed ? 'opacity-70 cursor-not-allowed' : ''}`}
                                  >
                                    <option value="gte">≥</option>
                                    <option value="lte">≤</option>
                                    <option value="gt">&gt;</option>
                                    <option value="lt">&lt;</option>
                                    <option value="eq">=</option>
                                  </select>
                                </div>
                                <div className="col-span-2">
                                  <input
                                    type="number"
                                    step="0.01"
                                    value={Number.isFinite(filter.value) ? filter.value : 0}
                                    disabled={variableSelectionConfirmed}
                                    onChange={(e) => {
                                      const nextValue = Number(e.target.value);
                                      const next = [...autoActiveFilters];
                                      next[index] = { ...next[index], value: Number.isFinite(nextValue) ? nextValue : 0 };
                                      setAutoActiveFilters(next);
                                    }}
                                    className={`w-full px-2 py-1.5 text-xs border border-gray-300 dark:border-slate-700 rounded bg-white dark:bg-slate-900 dark:text-white ${variableSelectionConfirmed ? 'opacity-70 cursor-not-allowed' : ''}`}
                                  />
                                </div>
                                <div className="col-span-3 text-xs text-green-700 dark:text-green-300 font-medium">
                                  {`✓ ${passCount} pass`}
                                </div>
                                <div className="col-span-1 text-right">
                                  <button
                                    disabled={variableSelectionConfirmed}
                                    onClick={() => setAutoActiveFilters(autoActiveFilters.filter((_: any, i: number) => i !== index))}
                                    className={`text-red-500 hover:text-red-700 text-sm ${variableSelectionConfirmed ? 'opacity-40 cursor-not-allowed' : ''}`}
                                    title="Remove filter"
                                  >
                                    ×
                                  </button>
                                </div>
                              </div>
                            );
                          })}
                        </div>

                        <div className="flex items-center space-x-4 mt-3">
                          <button
                            disabled={variableSelectionConfirmed}
                            onClick={() =>
                              setAutoActiveFilters([
                                ...autoActiveFilters,
                                {
                                  metric: autoFilterMetric || 'correlation',
                                  operator: autoFilterOperator || 'gte',
                                  value: Number(autoFilterValue || 0.1),
                                },
                              ])
                            }
                            className={`text-xs px-3 py-1.5 rounded border border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-slate-800 ${variableSelectionConfirmed ? 'opacity-40 cursor-not-allowed' : ''}`}
                          >
                            + Add filter
                          </button>
                          <button
                            onClick={() => setAutoActiveFilters([])}
                            disabled={autoActiveFilters.length === 0 || variableSelectionConfirmed}
                            className="text-xs text-orange-700 dark:text-orange-300 disabled:opacity-40 disabled:cursor-not-allowed"
                          >
                            Clear all
                          </button>
                        </div>
                      </div>

                      <div className="bg-white dark:bg-slate-900/60 border border-blue-200 dark:border-slate-700 rounded-lg p-3">
                        <div className="flex flex-wrap items-center gap-2 text-xs text-gray-700 dark:text-gray-200">
                          <span>Filters applied:</span>
                          <span className="font-semibold">{autoActiveFilters.length}</span>
                          <span>(AND logic)</span>
                          <span className="mx-1">|</span>
                          <span>Combined result:</span>
                          <span className="font-semibold text-orange-700 dark:text-orange-300">{combinedPassLabel}</span>
                          <span>unlocked pass all filters</span>
                          <span className="mx-1">|</span>
                          <span>Working set:</span>
                          <span className="font-semibold text-orange-700 dark:text-orange-300">{selectionSummary}</span>
                        </div>
                      </div>

                      <div className="max-h-64 overflow-auto border border-gray-200 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-900/60">
                        <table className="w-full min-w-[620px] table-fixed text-xs">
                          <colgroup>
                            <col className="w-[25%]" />
                            <col className="w-[25%]" />
                            <col className="w-[25%]" />
                            <col className="w-[25%]" />
                          </colgroup>
                          <thead className={`${MTA_THEAD} sticky top-0 z-10`}>
                            <tr>
                              <th className="px-3 py-2.5 text-left font-semibold text-blue-700 dark:text-blue-300 whitespace-nowrap">Variable</th>
                              <th className="px-3 py-2.5 text-right font-semibold text-blue-700 dark:text-blue-300 whitespace-nowrap">|Corr|</th>
                              <th className="px-3 py-2.5 text-right font-semibold text-blue-700 dark:text-blue-300 whitespace-nowrap">VIF</th>
                              <th className="px-3 py-2.5 text-right font-semibold text-blue-700 dark:text-blue-300 whitespace-nowrap">IV</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-gray-200 dark:divide-slate-700">
                            {screenedUnlocked.map((stat: any, index: number) => {
                              const variableName = String(stat?.variable ?? '');
                              const absCorr = Math.abs(Number(stat?.correlation ?? 0));
                              const vifValue = getNormalizedVifValue(stat);
                              const iv = stat?.iv !== null && stat?.iv !== undefined ? Number(stat.iv) : null;
                              return (
                                <tr key={variableName || index} className="bg-white dark:bg-slate-950 hover:bg-gray-50 dark:hover:bg-slate-900/70">
                                  <td className="px-3 py-2.5 text-gray-900 dark:text-white font-medium whitespace-nowrap">{variableName}</td>
                                  <td className="px-3 py-2.5 text-right text-gray-700 dark:text-gray-200 whitespace-nowrap">{absCorr.toFixed(4)}</td>
                                  <td className="px-3 py-2.5 text-right text-gray-700 dark:text-gray-200 whitespace-nowrap">{vifValue !== null ? vifValue.toFixed(2) : 'N/A'}</td>
                                  <td className="px-3 py-2.5 text-right text-gray-700 dark:text-gray-200 whitespace-nowrap">{iv !== null ? iv.toFixed(4) : 'N/A'}</td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>

                      <div className="flex justify-end">
                        <button
                          onClick={() => {
                            if (variableSelectionConfirmed) return;
                            const lockedList = getLockedVariableList();
                            const screenedList = screenedUnlocked.map((stat: any) => String(stat?.variable ?? '')).filter(Boolean);
                            const next: Record<string, boolean> = {};
                            lockedList.forEach((name) => { next[name] = true; });
                            screenedList.forEach((name: string) => { next[name] = true; });
                            setManualVariableSelection(next);

                            const precomputedMetrics: Record<string, RfePrecomputedMetric> = {};
                            const allStats: any[] = autoAnalysisData?.variable_analysis?.variable_statistics || [];
                            for (const stat of allStats) {
                              const name = String(stat?.variable ?? '');
                              if (!name) continue;
                              precomputedMetrics[name] = {
                                iv: stat?.iv ?? null,
                                orig_vif: getNormalizedVifValue(stat) ?? null,
                                abs_corr: stat?.correlation != null ? Math.abs(Number(stat.correlation)) : null,
                                signed_corr: stat?.correlation != null ? Number(stat.correlation) : null,
                                missing_pct: stat?.missing_pct ?? stat?.missing_percentage ?? null,
                              };
                            }

                            const tgt = (autoTargetVariable && autoTargetVariable.trim()) || (targetVariable || '').trim();
                            const dsId = activeDatasetId || '';
                            if (!tgt || !dsId) {
                              // Fallback: skip RFE if we cannot form a valid start payload.
                              setVariableSelectionConfirmed(true);
                              return;
                            }

                            const startPayload: RfeStartRequest = {
                              dataset_id: dsId,
                              target: tgt,
                              working_set: {
                                locked: lockedList,
                                screened: screenedList,
                                precomputed_metrics: precomputedMetrics,
                              },
                            };
                            setRfeStartPayload(startPayload);
                            setRfeActiveJobId(null);
                            setRfeResult(null);
                            setRfeFinalization(null);
                            // Lock Step 1 and Step 2 immediately after confirmation.
                            setVariableSelectionConfirmed(true);
                            setMtaSubStep('rfe');
                          }}
                          disabled={workingSetCount === 0 || variableSelectionConfirmed}
                          className="px-4 py-2 bg-orange-600 text-white text-sm font-semibold rounded-lg hover:bg-orange-700 disabled:opacity-50 disabled:cursor-not-allowed"
                          title={
                            autoActiveFilters.length > 0
                              ? `Using ${autoActiveFilters
                                  .map((f: any) => `${metricLabel(f.metric)} ${operatorLabel(f.operator)} ${f.value}`)
                                  .join(' AND ')}`
                              : 'No filters applied'
                          }
                        >
                          {variableSelectionConfirmed ? 'Confirmed variables for RFE ' : `Confirm ${workingSetCount} variables & Run RFE ↓`}
                        </button>
                      </div>
                    </>
                  );
                })()}
              </div>
            );
          })()}
        </div>
      )}

      {/* Step 3 pane: Iterative Feature Elimination (XGBoost-SHAP RFE).
          Rendered in its own container once the user has kicked off an RFE job.
          Stays visible (read-only) after Step 4 is confirmed so the user can
          still inspect the iteration history. */}
      {(mtaSubStep === 'rfe' || mtaSubStep === 'review' || mtaSubStep === 'completed') && rfeStartPayload && (
        <div className={`mt-6 ${MTA_SECTION} p-5 md:p-6 bg-gradient-to-br from-indigo-50/90 via-white to-blue-50/50 dark:from-slate-900 dark:via-slate-900 dark:to-slate-800`}>
          <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
            <div className="flex items-start gap-3 md:gap-4 min-w-0">
              <span className={MTA_STEP_NUM} title="Step 3">
                3
              </span>
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-indigo-500/15 dark:bg-indigo-500/20 ring-1 ring-indigo-300/50 dark:ring-indigo-600/30">
                <Scissors className="h-6 w-6 text-indigo-700 dark:text-indigo-200" />
              </div>
              <div className="min-w-0">
                <h4 className={MTA_TITLE_SECTION}>Iterative feature elimination</h4>
                <p className="text-sm text-gray-600 dark:text-gray-300 mt-1.5 max-w-3xl">
                  XGBoost-SHAP RFE on the full training partition. Locked variables are preserved across iterations.
                </p>
              </div>
            </div>
          </div>

          <RFEStep
            startPayload={rfeStartPayload}
            isDarkMode={isDarkMode}
            activeJobId={rfeActiveJobId}
            initialResult={rfeResult}
            readOnly={mtaSubStep === 'completed'}
            lockedCount={rfeStartPayload.working_set.locked.length}
            screenedCount={rfeStartPayload.working_set.screened.length}
            onJobIdAssigned={(jobId) => setRfeActiveJobId(jobId)}
            onCompleted={(res) => {
              setRfeResult(res);
              // Never regress the sub-step: when the RFE pane remounts after a
              // page change it re-subscribes to the SSE stream, which replays
              // the final event and re-invokes this handler. We must not
              // overwrite 'completed' with 'review' in that case.
              setMtaSubStep((prev) => (prev === 'rfe' ? 'review' : prev));
            }}
            onBack={() => setMtaSubStep('screener')}
          />
        </div>
      )}

      {/* Step 4 pane: Feature Review & Override.
          Rendered as its own container below Step 3 once the RFE job has a
          final result. The confirm button lives inside this pane; after
          confirmation the pane becomes read-only with a "Confirmed" banner
          rather than being replaced by a separate "Done" pane. */}
      {(mtaSubStep === 'review' || mtaSubStep === 'completed') && rfeResult && (
        <div className={`mt-6 ${MTA_SECTION} p-5 md:p-6 bg-gradient-to-br from-violet-50/80 via-white to-blue-50/50 dark:from-slate-900 dark:via-slate-900 dark:to-slate-800`}>
          <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
            <div className="flex items-start gap-3 md:gap-4 min-w-0">
              <span className={MTA_STEP_NUM} title="Step 4">
                4
              </span>
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-violet-500/15 dark:bg-violet-500/20 ring-1 ring-violet-300/50 dark:ring-violet-600/30">
                <ListChecks className="h-6 w-6 text-violet-800 dark:text-violet-200" />
              </div>
              <div className="min-w-0">
                <h4 className={MTA_TITLE_SECTION}>Feature review &amp; override</h4>
                <p className="text-sm text-gray-600 dark:text-gray-300 mt-1.5 max-w-3xl">
                  Toggle include/exclude and monotone direction per variable, then confirm to lock the selection for training.
                </p>
              </div>
            </div>
          </div>

          <FeatureReviewStep
            result={rfeResult}
            isDarkMode={isDarkMode}
            readOnly={mtaSubStep === 'completed'}
            finalization={rfeFinalization}
            onFinalized={(resp) => {
              setRfeFinalization(resp);
              const next: Record<string, boolean> = {};
              resp.features.forEach((name) => { next[name] = true; });
              setManualVariableSelection(next);
              setVariableSelectionConfirmed(true);
              
              try {
                const blob = JSON.stringify({ features: resp.features, locked: resp.locked, monotone: resp.monotone });
                if (activeDatasetId) {
                  sessionStorage.setItem(`model_training_step4_output_${activeDatasetId}`, blob);
                }
                sessionStorage.setItem('model_training_step4_output', blob);
              } catch (e) {
                console.error('Failed to store Step 4 output:', e);
              }

              // Same guard as in Step 3: don't regress once we're already completed.
              setMtaSubStep((prev) => (prev === 'review' ? 'completed' : prev));
            }}
            onEditOverrides={() => {
              setRfeFinalization(null);
              
              try {
                if (activeDatasetId) {
                  sessionStorage.removeItem(`model_training_step4_output_${activeDatasetId}`);
                }
                sessionStorage.removeItem('model_training_step4_output');
              } catch (e) {
                console.error('Failed to clear Step 4 output:', e);
              }

              setMtaSubStep('review');
            }}
          />
        </div>
      )}

      {/* Training Mode Selection */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h4 className="font-semibold text-gray-900 dark:text-white mb-4">Training Mode Selection</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <label className={`flex items-start space-x-3 p-4 border-2 rounded-lg cursor-pointer hover:bg-gray-50 dark:hover:bg-slate-800 transition-all ${
            trainingMode === 'global' ? 'border-blue-600 bg-blue-50 dark:border-blue-400 dark:bg-slate-800' : 'border-gray-200 dark:border-slate-700 dark:bg-slate-900/40'
          }`}>
            <input
              type="radio"
              name="trainingMode"
              checked={trainingMode === 'global'}
              onChange={() => setTrainingMode('global')}
              className="mt-1"
            />
            <div className="flex-1">
              <div className="font-medium text-gray-900 dark:text-white flex items-center space-x-2">
                <span>🌍 Global Model Training</span>
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-300 mt-1">
                Train a single model on entire dataset with full 6-step optimization
              </div>
            </div>
          </label>
          
          <label className={`flex items-start space-x-3 p-4 border-2 rounded-lg cursor-pointer hover:bg-gray-50 dark:hover:bg-slate-800 transition-all ${
            trainingMode === 'segment-specific' ? 'border-blue-600 bg-blue-50 dark:border-blue-400 dark:bg-slate-800' : 'border-gray-200 dark:border-slate-700 dark:bg-slate-900/40'
          }`}>
            <input
              type="radio"
              name="trainingMode"
              checked={trainingMode === 'segment-specific'}
              onChange={() => {
                setTrainingMode('segment-specific');
                // Trigger segment detection when user selects segment-specific mode
                if (activeDatasetId && !segmentInfo) {
                  detectSegmentsForDataset();
                }
              }}
              className="mt-1"
            />
            <div className="flex-1">
              <div className="font-medium text-gray-900 dark:text-white flex items-center space-x-2">
                <span>🎯 Segment-Specific Training</span>
                {segmentInfo?.available ? (
                  <span className="text-xs bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300 px-2 py-1 rounded">
                    {segmentInfo.total_segments} segments available
                  </span>
                ) : segmentInfo?.message ? (
                  <span className="text-xs bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300 px-2 py-1 rounded">
                    No segments found
                  </span>
                ) : (
                  <span className="text-xs bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300 px-2 py-1 rounded">
                    Detection in progress...
                  </span>
                )}
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-300 mt-1">
                Train specialized models for each segment
              </div>
            </div>
          </label>
        </div>
        {trainingMode === 'segment-specific' &&
          segmentInfo?.available &&
          Array.isArray(segmentInfo.segment_column_candidates) &&
          segmentInfo.segment_column_candidates.length > 1 && (
            <div className="mt-4 p-4 rounded-lg border border-gray-200 dark:border-slate-600 bg-gray-50 dark:bg-slate-800/60">
              <label className="block text-sm font-medium text-gray-800 dark:text-gray-200 mb-1">
                Segmentation column for training
              </label>
              <select
                className="w-full max-w-md border border-gray-300 dark:border-slate-600 rounded-md px-3 py-2 text-sm bg-white dark:bg-slate-900 text-gray-900 dark:text-gray-100"
                value={segmentSchemeColumnOverride || segmentInfo.segment_column || ''}
                onChange={async (e) => {
                  const col = e.target.value;
                  await detectSegmentsForDataset(col);
                }}
              >
                {segmentInfo.segment_column_candidates.map((c: string) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Multiple scheme columns were found (e.g. segmentation_scheme_1, segmentation_scheme_2). Choose which
                one defines segments for this training run.
              </p>
            </div>
          )}
      </div>

      {/* View CodeBook Button - Always Available */}
      <div className={`${MTA_SECTION} p-6 md:p-7`}>
        <div className="flex flex-wrap items-start justify-between gap-3 mb-5">
          <div className="flex items-start gap-3">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-slate-800 dark:bg-slate-700 text-white shadow-md">
              <FileText className="h-6 w-6" />
            </div>
            <div>
              <h4 className={MTA_TITLE_SECTION}>CodeBook</h4>
              <p className="text-sm text-gray-600 dark:text-gray-300 mt-1 max-w-2xl">
                Inspect the backend Python for this {trainingMode === 'global' ? 'global' : 'segment-specific'} training workflow.
              </p>
            </div>
          </div>
        </div>
        <button
          onClick={handleViewCodebook}
          className="w-full px-4 py-3.5 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-xl hover:bg-blue-700 dark:hover:bg-[#333380] transition-all flex items-center justify-center gap-2 font-semibold shadow-md hover:shadow-lg hover:scale-[1.01] active:scale-[0.99]"
        >
          <FileText className="h-5 w-5" />
          <span>View CodeBook</span>
          <span className="text-xs bg-white/20 px-2 py-1 rounded-md">Python</span>
        </button>
      </div>

      {/* Step 5: Auto vs manual training mode — avoid overflow-hidden so native target <select> lists are not clipped */}
      <div className={MTA_SECTION}>
        <div className="px-5 md:px-6 pt-5 pb-4 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
          <div className="flex flex-wrap items-start gap-3">
            <span className={MTA_STEP_NUM} title="Step 5">
              5
            </span>
            <div className="min-w-0 flex-1">
              <h4 className={MTA_TITLE_SECTION}>Training mode</h4>
            
            </div>
          </div>
        </div>
        <div className="flex border-b border-gray-200 dark:border-gray-700 bg-gray-50/80 dark:bg-slate-900/50">
          <button
            onClick={() => {
              if (mtaTrainingInProgress) return;
              setActiveTab('auto');
            }}
            type="button"
            disabled={mtaTrainingInProgress}
            title={
              mtaTrainingInProgress
                ? 'Wait until training finishes or cancel it before switching between Auto and Manual.'
                : undefined
            }
            className={`flex-1 px-5 py-4 md:py-5 font-semibold transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed ${
              activeTab === 'auto'
                ? 'text-blue-700 border-b-[3px] border-blue-600 bg-white dark:text-blue-200 dark:border-blue-400 dark:bg-slate-900 shadow-[0_-2px_0_0_rgba(37,99,235,0.15)]'
                : 'text-gray-600 hover:text-gray-900 hover:bg-white/70 dark:text-slate-300 dark:hover:text-white dark:hover:bg-slate-800/80'
            }`}
          >
            <div className="flex items-center justify-center gap-2">
              <Zap className={`h-5 w-5 ${activeTab === 'auto' ? 'text-amber-500' : 'text-gray-400'}`} />
              <span>Auto training</span>
            </div>
          </button>
          <button
            onClick={() => {
              if (mtaTrainingInProgress) return;
              setActiveTab('manual');
            }}
            type="button"
            disabled={mtaTrainingInProgress}
            title={
              mtaTrainingInProgress
                ? 'Wait until training finishes or cancel it before switching between Auto and Manual.'
                : undefined
            }
            className={`flex-1 px-5 py-4 md:py-5 font-semibold transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed ${
              activeTab === 'manual'
                ? 'text-blue-700 border-b-[3px] border-blue-600 bg-white dark:text-blue-200 dark:border-blue-400 dark:bg-slate-900 shadow-[0_-2px_0_0_rgba(37,99,235,0.15)]'
                : 'text-gray-600 hover:text-gray-900 hover:bg-white/70 dark:text-slate-300 dark:hover:text-white dark:hover:bg-slate-800/80'
            }`}
          >
            <div className="flex items-center justify-center gap-2">
              <Settings className={`h-5 w-5 ${activeTab === 'manual' ? 'text-indigo-600 dark:text-indigo-400' : 'text-gray-400'}`} />
              <span>Manual configuration</span>
            </div>
          </button>
        </div>

        <div className="p-6 md:p-8">
          {/* Auto Training Tab */}
          {activeTab === 'auto' && (
            <div className="space-y-6">
              <div className="flex items-start gap-3">
                <div className="mt-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-200">
                  <Zap className="h-5 w-5" />
                </div>
                <div>
                <h4 className={`${MTA_TITLE_SECTION} mb-2`}>
                  {trainingMode === 'segment-specific' ? 'Segment-wise automated training' : 'Automated training'}
                </h4>
                <p className="text-sm text-gray-600 dark:text-gray-300 mb-4 leading-relaxed">
                Let AI automatically analyze your data, select the best variables, and train optimal models
                </p>
                </div>
              </div>

              {/* Segment Info Banner for Segment-Specific Mode - Hidden per user request */}
              {false && trainingMode === 'segment-specific' && segmentInfo?.available && (
                <div className="bg-gradient-to-r from-purple-50 to-blue-50 border border-purple-200 rounded-lg p-4">
                  <div className="flex items-center space-x-2 mb-2">
                    <div className="w-3 h-3 bg-purple-600 rounded-full"></div>
                    <span className="text-sm font-medium text-purple-900">
                      📊 {segmentInfo.total_segments} segments detected in column: <span className="font-semibold">{segmentInfo.segment_column}</span>
                    </span>
                  </div>
                  <div className="text-sm text-purple-700 ml-5">
                    Segments: {segmentInfo.segments.map((seg: string) => (
                      <span key={seg} className="inline-block bg-white px-2 py-1 rounded mr-2 mb-1 text-xs">
                        {seg} ({segmentInfo.counts[seg]} records)
                      </span>
                    ))}
                  </div>
                  <div className="text-xs text-purple-600 mt-2 ml-5">
                    Each segment will be trained independently with optimized variables and algorithms
                  </div>
                </div>
              )}

              {/* Variable Selection Section - Same as Manual Configuration */}
              <div className="border border-gray-200 dark:border-slate-700 rounded-lg p-4 bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-slate-900 dark:to-slate-800">
                <h4 className="font-medium text-gray-900 dark:text-white mb-4">Variable Selection</h4>
                
                <div className="space-y-4">
                  <div
                    className={
                      autoProblemType
                        ? 'flex flex-col gap-4 md:flex-row md:items-stretch md:gap-4'
                        : ''
                    }
                  >
                    <div className="min-w-0 flex-1">
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-2">
                        Target Variable
                      </label>
                      {lockedTargetColumn ? (
                        <>
                          <div className="relative z-20 flex w-full items-center justify-between gap-2 rounded-lg border border-gray-300 bg-gray-100 px-3 py-2 text-gray-900 dark:border-slate-600 dark:bg-slate-800/90 dark:text-white">
                            <span className="truncate font-mono text-sm" title={lockedTargetColumn}>
                              {lockedTargetColumn}
                            </span>
                            <Lock className="h-4 w-4 shrink-0 text-gray-500 dark:text-gray-400" aria-hidden />
                          </div>
                          <p className="mt-1.5 text-xs text-gray-500 dark:text-gray-400">
                            Defined in Objectives &amp; Data; not editable on this step.
                          </p>
                        </>
                      ) : (
                        <select
                          value={autoTargetVariable}
                          onChange={(e) => {
                            const v = e.target.value;
                            setAutoTargetVariable(v);
                            setManualTargetVariable(v);
                          }}
                          className="relative z-20 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 focus:border-transparent focus:ring-2 focus:ring-blue-500 dark:border-slate-700 dark:bg-slate-900 dark:text-white"
                        >
                          <option value="">Select target variable</option>
                          {availableVariables.map((variable) => (
                            <option key={variable} value={variable}>
                              {variable}
                            </option>
                          ))}
                        </select>
                      )}
                    </div>

                    {autoProblemType && (
                      <div className="bg-blue-50 border border-blue-200 dark:bg-slate-900 dark:border-slate-700 rounded-lg p-4 md:flex-1 md:min-w-[220px] flex flex-col justify-center shrink-0">
                        <div className="flex items-center space-x-2">
                          <div className="w-3 h-3 bg-blue-600 rounded-full shrink-0" />
                          <span className="text-sm font-medium text-blue-900 dark:text-white">
                            Problem Type: <span className="font-semibold capitalize">{autoProblemType}</span>
                          </span>
                        </div>
                        <p className="text-xs text-blue-700 dark:text-gray-200 mt-1">
                          {autoProblemType === 'classification'
                            ? 'Predicting discrete categories or classes'
                            : 'Predicting continuous numerical values'}
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Variable Analysis Section - hidden for auto mode */}
              {false && (
              <div className="border border-gray-200 rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                <div>
                    <h4 className="font-medium text-gray-900">Variable Analysis</h4>
                    <p className="text-xs text-gray-600 mt-1">
                      Calculate VIF (multicollinearity) and correlation with target variable
                    </p>
                  </div>
                    <button
                    onClick={handleAutoAnalysis}
                    disabled={isAnalyzing || !autoTargetVariable}
                      className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center space-x-2 text-sm font-medium"
                    >
                    {isAnalyzing ? (
                        <>
                          <Loader className="h-4 w-4 animate-spin" />
                          <span>Calculating...</span>
                        </>
                      ) : (
                        <>
                          <Activity className="h-4 w-4" />
                          <span>Calculate Variable Analysis</span>
                        </>
                      )}
                    </button>
                  </div>

                {/* VIF Preview Dropdown - Same as Manual Configuration */}
                {autoAnalysisData && (
                  <div className="mt-4">
                    <button
                      onClick={() => setShowAutoVariableAnalysis(!showAutoVariableAnalysis)}
                      className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 border border-gray-200 dark:bg-slate-900/70 dark:hover:bg-slate-900 dark:border-slate-700 rounded-lg transition-colors"
                    >
                      <div className="flex items-center space-x-2">
                        <Eye className="h-4 w-4 text-gray-600 dark:text-gray-300" />
                        <span className="text-sm font-medium text-gray-900 dark:text-white">
                          View VIF, Correlation & IV Results ({autoAnalysisData.variable_analysis?.variable_statistics?.length || 0} variables)
                        </span>
                      </div>
                      <ChevronDown className={`h-4 w-4 text-gray-600 dark:text-gray-300 transition-transform ${showAutoVariableAnalysis ? 'rotate-180' : ''}`} />
                    </button>

                    {showAutoVariableAnalysis && (
                      <div className="mt-3 border border-gray-200 dark:border-slate-700 rounded-lg overflow-hidden">
                        {/* Summary Stats */}
                        <div className="bg-gradient-to-r from-purple-50 to-pink-50 dark:from-slate-900 dark:to-slate-800 p-4 border-b border-gray-200 dark:border-slate-700">
                          <h5 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">Analysis Summary</h5>
                          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                            <div className="bg-white dark:bg-slate-900/70 rounded-lg p-3 border border-transparent dark:border-slate-700">
                              <div className="text-xs text-gray-600 dark:text-gray-300">Total Variables</div>
                              <div className="text-lg font-bold text-gray-900 dark:text-white">{autoAnalysisData.variable_analysis?.summary?.total_variables || 0}</div>
                            </div>
                            <div className="bg-white dark:bg-slate-900/70 rounded-lg p-3 border border-transparent dark:border-slate-700">
                              <div className="text-xs text-green-600">Correlation (&ge;0.05)</div>
                              <div className="text-lg font-bold text-green-900 dark:text-green-300">{autoAnalysisData.variable_analysis?.summary?.high_correlation_count || 0}</div>
                            </div>
                            <div className="bg-white dark:bg-slate-900/70 rounded-lg p-3 border border-transparent dark:border-slate-700">
                              <div className="text-xs text-green-600">VIF (&le;10)</div>
                              <div className="text-lg font-bold text-green-900 dark:text-green-300">{autoAnalysisData.variable_analysis?.summary?.good_vif_count || 0}</div>
                            </div>
                            <div className="bg-white dark:bg-slate-900/70 rounded-lg p-3 border border-transparent dark:border-slate-700">
                              <div className="text-xs text-purple-600">IV (&ge;0.02)</div>
                              <div className="text-lg font-bold text-purple-900 dark:text-purple-300">{autoAnalysisData.variable_analysis?.summary?.strong_iv_count || 0}</div>
                            </div>
                            <div className="bg-white dark:bg-slate-900/70 rounded-lg p-3 border border-transparent dark:border-slate-700">
                              <div className="text-xs text-teal-600">Good Variance</div>
                              <div className="text-lg font-bold text-teal-900 dark:text-teal-300">{autoAnalysisData.variable_analysis?.summary?.good_variance_count || 0}</div>
                              {((autoAnalysisData.variable_analysis?.summary?.zero_variance_count || 0) > 0 || (autoAnalysisData.variable_analysis?.summary?.near_zero_variance_count || 0) > 0) && (
                                <div className="text-xs text-red-500 mt-1">
                                  {(autoAnalysisData.variable_analysis?.summary?.zero_variance_count || 0) > 0 && `${autoAnalysisData.variable_analysis?.summary?.zero_variance_count} zero`}
                                  {(autoAnalysisData.variable_analysis?.summary?.zero_variance_count || 0) > 0 && (autoAnalysisData.variable_analysis?.summary?.near_zero_variance_count || 0) > 0 && ', '}
                                  {(autoAnalysisData.variable_analysis?.summary?.near_zero_variance_count || 0) > 0 && `${autoAnalysisData.variable_analysis?.summary?.near_zero_variance_count} low`}
                                </div>
                              )}
                            </div>
                          </div>
                        </div>

                        {/* Excluded / Non-feature Columns Notice (dynamic) */}
                        {(() => {
                          const excluded = (autoAnalysisData?.excluded_columns as string[])
                            ?? (autoAnalysisData?.available_variables?.non_feature_columns as string[])
                            ?? [];
                          return (
                            <div className="px-4 py-3 bg-white dark:bg-slate-900/70 border-b border-gray-200 dark:border-slate-700">
                              <div className="text-xs font-semibold text-gray-700 dark:text-gray-200 mb-1">Excluded non-feature columns</div>
                              <div className="text-xs text-gray-700 dark:text-gray-200">
                                {excluded.length > 0 ? excluded.join(', ') : 'None'}
                              </div>
                              <div className="mt-1 text-[11px] text-gray-500 dark:text-gray-400">These are identifier or segment columns excluded from modeling by default.</div>
                            </div>
                          );
                        })()}

                        {/* Variable Statistics Table */}
                        <div className="overflow-x-auto max-h-96 overflow-y-auto">
                          <table className="w-full text-sm">
                            <thead className={`${MTA_THEAD} sticky top-0`}>
                              <tr>
                                <th className="px-4 py-3 text-left font-semibold text-gray-700 dark:text-gray-200">Variable</th>
                                <th className="px-4 py-3 text-right font-semibold text-gray-700 dark:text-gray-200">Correlation</th>
                                <th className="px-4 py-3 text-right font-semibold text-gray-700 dark:text-gray-200">VIF</th>
                                <th className="px-4 py-3 text-right font-semibold text-gray-700 dark:text-gray-200">IV</th>
                                <th className="px-4 py-3 text-right font-semibold text-gray-700 dark:text-gray-200">Variance (Std)</th>
                                <th className="px-4 py-3 text-left font-semibold text-gray-700 dark:text-gray-200">Interpretation</th>
                              </tr>
                            </thead>
                            <tbody className="bg-white dark:bg-slate-950 divide-y divide-gray-200 dark:divide-slate-800">
                              {autoAnalysisData.variable_analysis?.variable_statistics?.map((stat: any, index: number) => {
                                const absCorr = Math.abs(stat.correlation);
                                const corrColor = absCorr > 0.8 ? 'text-green-900 font-bold' : absCorr > 0.5 ? 'text-blue-900 font-medium' : absCorr < 0.1 ? 'text-red-600 font-bold' : 'text-gray-900';
                                const vifColor = stat.vif && stat.vif > 10 ? 'text-red-600 font-bold' : stat.vif && stat.vif > 5 ? 'text-orange-900 font-medium' : 'text-gray-900';
                                const varianceColor = stat.variance_status === 'zero' ? 'text-red-600 font-bold' : stat.variance_status === 'near_zero' ? 'text-orange-600 font-medium' : 'text-gray-900 dark:text-gray-200';

                      return (
                                  <tr key={index} className={index % 2 === 0 ? 'bg-white dark:bg-slate-950' : 'bg-gray-50 dark:bg-slate-900/60'}>
                                    <td className="px-4 py-3 text-gray-900 dark:text-white font-medium">{stat.variable}</td>
                                    <td className={`px-4 py-3 text-right ${corrColor}`}>
                                      {stat.correlation?.toFixed(4) || 'N/A'}
                                    </td>
                                    <td className={`px-4 py-3 text-right ${vifColor}`}>
                                      {stat.vif !== null && stat.vif !== undefined ? stat.vif.toFixed(2) : 'N/A'}
                                    </td>
                                    <td className="px-4 py-3 text-right text-purple-900 dark:text-purple-300">
                                      {stat.iv !== null && stat.iv !== undefined ? Number(stat.iv).toFixed(4) : 'N/A'}
                                    </td>
                                    <td className={`px-4 py-3 text-right ${varianceColor}`}>
                                      {stat.std !== null && stat.std !== undefined ? stat.std.toFixed(4) : 'N/A'}
                                      {stat.variance_status === 'zero' && <span className="ml-1 text-xs">(Zero)</span>}
                                      {stat.variance_status === 'near_zero' && <span className="ml-1 text-xs">(Low)</span>}
                                    </td>
                                    <td className="px-4 py-3 text-xs text-gray-600 dark:text-gray-300">
                                      {absCorr > 0.8 && <span className="inline-block px-2 py-1 bg-green-100 text-green-800 rounded-full mr-1">Strong</span>}
                                      {absCorr < 0.1 && <span className="inline-block px-2 py-1 bg-orange-100 text-orange-800 rounded-full mr-1">Weak</span>}
                                      {stat.vif && stat.vif > 10 && <span className="inline-block px-2 py-1 bg-red-100 text-red-800 rounded-full mr-1">High VIF</span>}
                                      {stat.iv !== null && stat.iv !== undefined && stat.iv >= 0.3 && <span className="inline-block px-2 py-1 bg-purple-100 text-purple-800 rounded-full mr-1">Strong IV</span>}
                                      {stat.variance_status === 'zero' && <span className="inline-block px-2 py-1 bg-red-100 text-red-800 rounded-full mr-1">Zero Var</span>}
                                      {stat.variance_status === 'near_zero' && <span className="inline-block px-2 py-1 bg-yellow-100 text-yellow-800 rounded-full mr-1">Low Var</span>}
                                    </td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>

                        {/* Interpretation Guide */}
                        <div className="bg-gray-50 dark:bg-slate-900/60 p-4 border-t border-gray-200 dark:border-slate-700">
                          <h6 className="text-xs font-semibold text-gray-700 dark:text-gray-200 mb-2">Interpretation Guide:</h6>
                          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-2 text-xs text-gray-600 dark:text-gray-300">
                            <div>
                              <strong>Correlation:</strong> Measures linear relationship with target (-1 to 1)
                              <ul className="ml-4 mt-1 space-y-1">
                                <li>• &gt;0.8: Strong positive/negative relationship</li>
                                <li>• 0.5-0.8: Moderate relationship</li>
                                <li>• &lt;0.1: Weak relationship (consider removing)</li>
                              </ul>
                            </div>
                            <div>
                              <strong>VIF:</strong> Variance Inflation Factor (multicollinearity)
                              <ul className="ml-4 mt-1 space-y-1">
                                <li>• &gt;10: High multicollinearity (consider removing)</li>
                                <li>• 5-10: Moderate multicollinearity</li>
                                <li>• &lt;5: Low multicollinearity (good)</li>
                              </ul>
                            </div>
                            <div>
                              <strong>IV:</strong> Information Value (predictive power)
                              <ul className="ml-4 mt-1 space-y-1">
                                <li>• &gt;0.3: Strong predictor</li>
                                <li>• 0.1-0.3: Medium predictor</li>
                                <li>• &lt;0.02: Useless predictor</li>
                              </ul>
                            </div>
                            <div>
                              <strong>Variance (Std):</strong> Standard deviation of values
                              <ul className="ml-4 mt-1 space-y-1">
                                <li>• Zero: Only 1 unique value (exclude)</li>
                                <li>• Low: &gt;95% same value or std&lt;0.01</li>
                                <li>• Normal: Good variability for modeling</li>
                              </ul>
                            </div>
                          </div>
                          {/* Excluded / Non-feature Columns (Manual VIF Section) - dynamic only */}
                          {Array.isArray(vifCorrelationData?.excluded_from_analysis) && vifCorrelationData.excluded_from_analysis.length > 0 && (
                            <div className="mt-3 bg-white dark:bg-slate-900/70 rounded-lg p-3 border border-gray-200 dark:border-slate-700">
                              <div className="text-[11px] font-semibold text-gray-700 dark:text-gray-200 mb-0.5">Excluded non-feature columns</div>
                              <div className="text-[11px] text-gray-700 dark:text-gray-200">
                                {vifCorrelationData.excluded_from_analysis.join(', ')}
                              </div>
                              <div className="mt-0.5 text-[11px] text-gray-500 dark:text-gray-400">Identifier/segment columns are excluded from modeling by default.</div>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Variable Selection Mode Toggle (hidden in auto mode) */}
                {false && autoAnalysisData && autoVariableSelection && (
                  <div className="mt-6 border border-gray-200 dark:border-slate-700 rounded-lg p-4 bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-slate-900 dark:to-slate-800">
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <h5 className="font-medium text-gray-900 dark:text-white flex items-center space-x-2">
                          <Filter className="h-4 w-4 text-blue-600" />
                          <span>Variable Selection</span>
                        </h5>
                        <div className="text-sm text-gray-600 dark:text-gray-300">
                          Choose how to select variables for model training
                        </div>
                      </div>
                    </div>

                    {/* Mode Toggle */}
                    <div className="bg-white dark:bg-slate-900/70 border border-blue-200 dark:border-slate-700 rounded-lg p-4 mb-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-4">
                          <button
                            onClick={() => {
                              setVariableSelectionMode('auto');
                              setVariableSelectionConfirmed(true);
                              // Reset manual selection to auto-selected variables
                              const resetSelection: Record<string, boolean> = {};
                              autoVariableSelection.selected_variables.forEach((variable: string) => {
                                resetSelection[variable] = true;
                              });
                              setManualVariableSelection(resetSelection);
                            }}
                            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                              variableSelectionMode === 'auto'
                                ? 'bg-green-600 text-white'
                                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                            }`}
                          >
                            🤖 AI Selection
                          </button>
                          <button
                            onClick={() => {
                              setVariableSelectionMode('manual');
                              setVariableSelectionConfirmed(false);
                            }}
                            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                              variableSelectionMode === 'manual'
                                ? 'bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] hover:bg-blue-700 dark:hover:bg-[#333380]'
                                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                            }`}
                          >
                            ✋ Manual Selection
                          </button>
                            </div>
                        <div className="text-xs text-gray-600">
                          {variableSelectionMode === 'auto'
                            ? `${autoVariableSelection.summary?.selected_count || 0} variables auto-selected`
                            : `${Object.values(manualVariableSelection).filter(Boolean).length} of ${getAvailableVariablesForManualSelection().length} manually selected`
                          }
                              </div>
                            </div>

                      {/* Selection Summary */}
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
                        <div className="text-center">
                          <div className="text-2xl font-bold text-blue-900">
                            {variableSelectionMode === 'auto'
                              ? autoVariableSelection.summary?.selected_count || 0
                              : Object.values(manualVariableSelection).filter(Boolean).length
                            }
                          </div>
                          <div className="text-xs text-gray-600">Selected</div>
                        </div>
                        <div className="text-center">
                          <div className="text-2xl font-bold text-gray-900">{getAvailableVariablesForManualSelection().length}</div>
                          <div className="text-xs text-gray-600">Analyzed</div>
                        </div>
                        <div className="text-center">
                          <div className="text-2xl font-bold text-red-800 dark:text-red-300">
                            {getAvailableVariablesForManualSelection().length - Object.values(manualVariableSelection).filter(Boolean).length}
                          </div>
                          <div className="text-xs text-gray-600">Not Selected</div>
                        </div>
                  </div>
                </div>

                    {/* Auto Selection Display */}
                    {variableSelectionMode === 'auto' && (
                      <div className="bg-white border border-green-200 rounded-lg p-4">
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center space-x-2">
                            <span className="text-xs text-green-700 bg-green-100 px-2 py-1 rounded-full">
                              Auto-selected
                            </span>
                            <span className="text-sm text-gray-700">
                              {autoVariableSelection.summary?.selected_count || 0} variables automatically selected
                            </span>
                          </div>
                          <div className="flex items-center space-x-2">
                            {!variableSelectionConfirmed && autoVariableSelection?.selected_variables?.length > 0 && (
                              <button
                                onClick={() => {
                                  // Confirm the auto-selected variables
                                  setVariableSelectionConfirmed(true);
                                  // Sync manual selection with auto selection for consistency
                                  const newManualSelection: Record<string, boolean> = {};
                                  autoVariableSelection.selected_variables?.forEach((variable: string) => {
                                    newManualSelection[variable] = true;
                                  });
                                  setManualVariableSelection(newManualSelection);
                                }}
                                className="px-3 py-1 bg-green-600 text-white rounded-lg text-xs hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                disabled={!autoVariableSelection?.selected_variables?.length}
                                title="Confirm the AI-selected variables for training"
                              >
                                ✓ Confirm Selection
                              </button>
                            )}
                            <button
                              onClick={() => setVariableSelectionMode('manual')}
                              className="px-3 py-1 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg text-xs hover:bg-blue-700 dark:hover:bg-[#333380]"
                            >
                              Modify Selection
                            </button>
                          </div>
                </div>

                        <div className="text-xs text-blue-700 bg-blue-50 dark:bg-slate-900/70 dark:text-white rounded-lg p-3">
                          Variables automatically selected based on correlation strength, VIF (multicollinearity), and IV (information value) analysis.
                        </div>

                        {/* Selected Variables Dropdown */}
                        {autoVariableSelection?.selected_variables?.length > 0 && (
                          <div className="mt-4 border border-gray-200 dark:border-slate-700 rounded-lg bg-gray-50 dark:bg-slate-900/70">
                            <button
                              onClick={() => setShowSelectedVariablesDropdown(!showSelectedVariablesDropdown)}
                              className="w-full flex items-center justify-between p-3 hover:bg-gray-100 dark:hover:bg-slate-900 transition-colors"
                            >
                              <div className="flex items-center space-x-2">
                                <Eye className="h-4 w-4 text-gray-600 dark:text-gray-300" />
                                <span className="text-sm font-medium text-gray-900 dark:text-white">
                                  View AI Selection Details ({autoVariableSelection.selected_variables.length} variables)
                                </span>
                              </div>
                              <ChevronDown className={`h-4 w-4 text-gray-600 dark:text-gray-300 transition-transform ${showSelectedVariablesDropdown ? 'rotate-180' : ''}`} />
                            </button>

                            {showSelectedVariablesDropdown && (
                              <div className="border-t border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-950 rounded-b-lg">
                                <div className="p-3 max-h-48 overflow-y-auto">
                                  <div className="text-xs text-gray-600 dark:text-gray-300 mb-2 font-medium">
                                    Variables selected by AI algorithm (sorted by importance):
                                  </div>
                                  <div className="text-xs text-gray-500 dark:text-gray-200 mb-3 p-2 bg-blue-50 dark:bg-slate-900/70 rounded">
                                    <div className="mb-2"><strong>Selection criteria:</strong> |Correlation| ≥ 0.05, VIF ≤ 10, IV ≥ 0.02</div>
                                    <div className="flex flex-wrap gap-2 text-xs">
                                      <span className="flex items-center space-x-1">
                                        <span className="w-3 h-3 bg-green-100 border border-green-300 rounded"></span>
                                        <span>Strong correlation/IV</span>
                                      </span>
                                      <span className="flex items-center space-x-1">
                                        <span className="w-3 h-3 bg-blue-100 border border-blue-300 rounded"></span>
                                        <span>Moderate correlation/IV</span>
                                      </span>
                                      <span className="flex items-center space-x-1">
                                        <span className="w-3 h-3 bg-yellow-100 border border-yellow-300 rounded"></span>
                                        <span>Weak correlation/IV</span>
                                      </span>
                                      <span className="flex items-center space-x-1">
                                        <span className="w-3 h-3 bg-red-100 border border-red-300 rounded"></span>
                                        <span>Poor correlation/high VIF</span>
                                      </span>
                                    </div>
                                  </div>
                                  <div className="grid grid-cols-1 gap-1">
                                    {autoVariableSelection.selected_variables
                                      .map((variable: string) => ({
                                        variable,
                                        stats: autoAnalysisData?.variable_analysis?.variable_statistics?.find((s: any) => s.variable === variable)
                                      }))
                                      .sort((a: any, b: any) => {
                                        // Sort by absolute correlation (highest first), then by IV (highest first)
                                        const corrA = Math.abs(a.stats?.correlation || 0);
                                        const corrB = Math.abs(b.stats?.correlation || 0);
                                        if (corrA !== corrB) return corrB - corrA;
                                        return (b.stats?.iv || 0) - (a.stats?.iv || 0);
                                      })
                                      .map((item: any, index: number) => {
                                      const { variable, stats } = item;
                                      return (
                                        <div key={variable} className="flex items-center justify-between p-2 bg-gray-50 rounded text-sm">
                                          <div className="flex items-center space-x-2">
                                            <span className="text-gray-600 font-mono text-xs">#{index + 1}</span>
                                            <span className="font-medium text-gray-900">{variable}</span>
                                          </div>
                                          <div className="flex items-center space-x-2 text-xs">
                                            {stats?.correlation !== null && stats?.correlation !== undefined && (
                                              <span className={`px-2 py-1 rounded-full ${
                                                Math.abs(stats.correlation) > 0.8 ? 'bg-green-100 text-green-800' :
                                                Math.abs(stats.correlation) > 0.5 ? 'bg-blue-100 text-blue-800' :
                                                Math.abs(stats.correlation) < 0.1 ? 'bg-orange-100 text-orange-800' :
                                                'bg-gray-100 text-gray-800'
                                              }`}>
                                                Corr: {stats.correlation.toFixed(3)}
                                              </span>
                                            )}
                                            {stats?.vif !== null && stats?.vif !== undefined && (
                                              <span className={`px-2 py-1 rounded-full ${
                                                stats.vif > 10 ? 'bg-red-100 text-red-800' :
                                                stats.vif > 5 ? 'bg-orange-100 text-orange-800' :
                                                'bg-green-100 text-green-800'
                                              }`}>
                                                VIF: {stats.vif.toFixed(2)}
                                              </span>
                                            )}
                                            {stats?.iv !== null && stats?.iv !== undefined && (
                                              <span className={`px-2 py-1 rounded-full ${
                                                stats.iv >= 0.3 ? 'bg-green-100 text-green-800' :
                                                stats.iv >= 0.1 ? 'bg-blue-100 text-blue-800' :
                                                stats.iv >= 0.02 ? 'bg-yellow-100 text-yellow-800' :
                                                'bg-red-100 text-red-800'
                                              }`}>
                                                IV: {Number(stats.iv).toFixed(3)}
                                              </span>
                                            )}
                                          </div>
                                        </div>
                                      );
                                    })}
                                  </div>
                                </div>
                              </div>
                            )}
                          </div>
                        )}

                        {variableSelectionConfirmed && (
                          <div className="mt-3 text-green-700 text-xs flex items-center space-x-2">
                            <span className="inline-block w-2 h-2 bg-green-600 rounded-full"></span>
                            <span>✓ Auto-selected variables confirmed for training.</span>
                          </div>
                        )}

                        {!variableSelectionConfirmed && autoVariableSelection?.selected_variables?.length > 0 && (
                          <div className="mt-3 text-amber-700 text-xs flex items-center space-x-2">
                            <span className="inline-block w-2 h-2 bg-amber-500 rounded-full"></span>
                            <span>Click "Confirm Selection" to proceed with training.</span>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Manual Selection Display */}
                    {variableSelectionMode === 'manual' && (
                      <div className="bg-white border border-blue-200 rounded-lg p-4">
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center space-x-2">
                            <span className="text-xs text-blue-700 bg-blue-100 px-2 py-1 rounded-full">
                              Manual Selection
                            </span>
                            <span className="text-sm text-gray-700">
                              Select variables for model training
                            </span>
                          </div>
                          <div className="flex items-center space-x-2">
                            <span className="text-xs text-gray-600">
                              {Object.values(manualVariableSelection).filter(Boolean).length} of {getAvailableVariablesForManualSelection().length} variables selected
                            </span>
                          </div>
                        </div>

                      {/* Excluded / Non-feature Columns (Manual) */}
                      {Array.isArray(datasetPreviewData?.columns) && (
                        <div className="mb-3 px-3 py-2 bg-gray-50 border border-gray-200 rounded">
                          <div className="text-[11px] font-semibold text-gray-700 mb-0.5">Excluded non-feature columns</div>
                          <div className="text-[11px] text-gray-700">
                            {(() => {
                              const base = ['ID', 'MEMBER_ID', 'SEGMENT', 'segment', 'id', 'member_id'];
                              const present = (datasetPreviewData?.columns || []).filter((c: string) => base.includes(c));
                              return present.length > 0 ? present.join(', ') : 'None';
                            })()}
                          </div>
                          <div className="mt-0.5 text-[11px] text-gray-500">Identifier/segment columns are excluded from modeling by default.</div>
                        </div>
                      )}

                        {/* Variable Screener Filters */}
                        <div className="hidden bg-white border border-gray-300 rounded-lg p-4 mb-4">
                          <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center space-x-2">
                              <Filter className="h-5 w-5 text-blue-600" />
                              <h6 className="text-base font-semibold text-gray-900">Variable Screener</h6>
                            </div>
                            <div className="text-sm text-gray-600">
                              {(() => {
                                const allStats = autoAnalysisData?.variable_analysis?.variable_statistics || [];
                                const exclude = ['ID', 'MEMBER_ID', 'SEGMENT', 'segment'];
                                
                                // Count only valid variables (excluding target and special columns)
                                const validVars = allStats.filter((stat: any) => {
                                  return stat.variable !== autoTargetVariable && !exclude.includes(stat.variable?.toUpperCase());
                                });
                                
                                const totalVars = validVars.length;
                                
                                // Apply filters
                                const filtered = validVars.filter((stat: any) => {
                                  const absCorr = Math.abs(stat.correlation || 0);
                                  const vif = stat.vif;
                                  const iv = stat.iv !== null && stat.iv !== undefined ? Number(stat.iv) : null;
                                  
                                  // Apply all active filters
                                  for (const filter of autoActiveFilters) {
                                    let metricValue: number | null = null;
                                    
                                    if (filter.metric === 'correlation') {
                                      metricValue = absCorr;
                                    } else if (filter.metric === 'vif') {
                                      metricValue = vif !== null && vif !== undefined ? vif : null;
                                    } else if (filter.metric === 'iv') {
                                      metricValue = iv;
                                    }

                                    if (metricValue === null) return false;

                                    // Apply operator
                                    switch (filter.operator) {
                                      case 'gte':
                                        if (metricValue < filter.value) return false;
                                        break;
                                      case 'lte':
                                        if (metricValue > filter.value) return false;
                                        break;
                                      case 'gt':
                                        if (metricValue <= filter.value) return false;
                                        break;
                                      case 'lt':
                                        if (metricValue >= filter.value) return false;
                                        break;
                                      case 'eq':
                                        if (Math.abs(metricValue - filter.value) > 0.0001) return false;
                                        break;
                                    }
                                  }
                                  
                                  return true;
                                }).length;
                                
                                return `${filtered} of ${totalVars} variables match your criteria`;
                              })()}
                            </div>
                          </div>
                          
                          {/* Filter Row */}
                          <div className="grid grid-cols-12 gap-3 items-end mb-3">
                            <div className="col-span-3">
                              <label className="text-xs font-medium text-gray-700 block mb-1.5">
                                Metric
                              </label>
                              <select
                                value={autoFilterMetric || 'correlation'}
                                onChange={(e) => setAutoFilterMetric(e.target.value)}
                                className="w-full px-3 py-2 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white"
                              >
                                <option value="correlation">Absolute Correlation</option>
                                <option value="vif">VIF</option>
                                <option value="iv">IV</option>
                              </select>
                            </div>

                            <div className="col-span-4">
                              <label className="text-xs font-medium text-gray-700 block mb-1.5">
                                Operator
                              </label>
                              <select
                                value={autoFilterOperator || 'gte'}
                                onChange={(e) => setAutoFilterOperator(e.target.value)}
                                className="w-full px-3 py-2 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white"
                              >
                                <option value="gte">Greater than or equal (≥)</option>
                                <option value="lte">Less than or equal (≤)</option>
                                <option value="gt">Greater than (&gt;)</option>
                                <option value="lt">Less than (&lt;)</option>
                                <option value="eq">Equal (=)</option>
                              </select>
                            </div>

                            <div className="col-span-2">
                              <label className="text-xs font-medium text-gray-700 block mb-1.5">
                                Value
                              </label>
                              <input
                                type="number"
                                step="0.01"
                                value={autoFilterValue || ''}
                                onChange={(e) => setAutoFilterValue(e.target.value)}
                                placeholder="0.1"
                                className="w-full px-3 py-2 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white"
                              />
                            </div>

                            <div className="col-span-3 flex items-center space-x-2">
                              <button
                                onClick={() => {
                                  if (autoFilterMetric && autoFilterOperator && autoFilterValue) {
                                    const newFilter = {
                                      metric: autoFilterMetric,
                                      operator: autoFilterOperator,
                                      value: parseFloat(autoFilterValue)
                                    };
                                    setAutoActiveFilters([...autoActiveFilters, newFilter]);
                                    setAutoFilterValue('');
                                  }
                                }}
                                disabled={!autoFilterMetric || !autoFilterOperator || !autoFilterValue}
                                className="px-4 py-2 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] text-sm rounded hover:bg-blue-700 dark:hover:bg-[#333380] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                              >
                                Add Filter
                              </button>
                              <button
                                onClick={() => {
                                  setAutoActiveFilters([]);
                                  setAutoFilterValue('');
                                }}
                                disabled={autoActiveFilters.length === 0}
                                className="px-4 py-2 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] text-sm rounded hover:bg-blue-700 dark:hover:bg-[#333380] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                              >
                                Reset
                              </button>
                            </div>
                          </div>

                          {/* Active Filters Display */}
                          {autoActiveFilters.length > 0 && (
                            <div className="flex flex-wrap gap-2">
                              {autoActiveFilters.map((filter: any, index: number) => {
                                const metricLabel = filter.metric === 'correlation' ? 'Abs Corr' : 
                                                   filter.metric === 'vif' ? 'VIF' : 'IV';
                                const operatorLabel = filter.operator === 'gte' ? '≥' :
                                                     filter.operator === 'lte' ? '≤' :
                                                     filter.operator === 'gt' ? '>' :
                                                     filter.operator === 'lt' ? '<' : '=';
                                const colorClass = filter.metric === 'correlation' ? 'bg-green-100 text-green-800' :
                                                  filter.metric === 'vif' ? 'bg-red-100 text-red-800' :
                                                  'bg-purple-100 text-purple-800';
                                
                                return (
                                  <span
                                    key={index}
                                    className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium ${colorClass}`}
                                  >
                                    {metricLabel} {operatorLabel} {filter.value}
                                    <button
                                      onClick={() => {
                                        setAutoActiveFilters(autoActiveFilters.filter((_: any, i: number) => i !== index));
                                      }}
                                      className="ml-2 hover:opacity-70"
                                    >
                                      ×
                                    </button>
                                  </span>
                                );
                              })}
                            </div>
                          )}
                        </div>

                        {/* Variable Selection Interface */}
                        <div className="max-h-64 overflow-y-auto border border-gray-200 rounded-lg">
                          <table className="w-full text-sm">
                            <thead className={`${MTA_THEAD} sticky top-0`}>
                              <tr>
                                <th className="px-3 py-2 text-left font-semibold text-gray-700 w-8">
                      <input
                                    type="checkbox"
                                    checked={(() => {
                                      const availableVars = getAvailableVariablesForManualSelection();
                                      const selectedCount = Object.values(manualVariableSelection).filter(Boolean).length;
                                      return selectedCount === availableVars.length && availableVars.length > 0;
                                    })()}
                                    onChange={(e) => {
                                      const availableVars = getAvailableVariablesForManualSelection();
                                      const newSelection: Record<string, boolean> = {};
                                      availableVars.forEach((stat: any) => {
                                        newSelection[stat.variable] = e.target.checked;
                                      });
                                      setManualVariableSelection(newSelection);
                                    }}
                                    className="rounded border-gray-300"
                                  />
                                </th>
                                <th className="px-3 py-2 text-left font-semibold text-gray-700">Variable</th>
                                <th className="px-3 py-2 text-right font-semibold text-gray-700">Correlation</th>
                                <th className="px-3 py-2 text-right font-semibold text-gray-700">VIF</th>
                                <th className="px-3 py-2 text-right font-semibold text-gray-700">IV</th>
                                <th className="px-3 py-2 text-right font-semibold text-gray-700">Variance</th>
                              </tr>
                            </thead>
                            <tbody className="bg-white divide-y divide-gray-200">
                              {autoAnalysisData?.variable_analysis?.variable_statistics?.map((stat: any, index: number) => {
                                // Skip target variable and non-feature columns
                                const exclude = ['ID', 'MEMBER_ID', 'SEGMENT', 'segment'];
                                if (stat.variable === autoTargetVariable || exclude.includes(stat.variable?.toUpperCase())) {
                                  return null;
                                }

                                // Get variable metrics
                                const absCorr = Math.abs(stat.correlation || 0);
                                const vif = stat.vif;
                                const iv = stat.iv !== null && stat.iv !== undefined ? Number(stat.iv) : null;

                                // Apply new flexible filters
                                let passesFilters = true;
                                for (const filter of autoActiveFilters) {
                                  let metricValue: number | null = null;
                                  
                                  if (filter.metric === 'correlation') {
                                    metricValue = absCorr;
                                  } else if (filter.metric === 'vif') {
                                    metricValue = vif !== null && vif !== undefined ? vif : null;
                                  } else if (filter.metric === 'iv') {
                                    metricValue = iv;
                                  }

                                  if (metricValue === null) {
                                    passesFilters = false;
                                    break;
                                  }

                                  // Apply operator
                                  switch (filter.operator) {
                                    case 'gte':
                                      if (metricValue < filter.value) passesFilters = false;
                                      break;
                                    case 'lte':
                                      if (metricValue > filter.value) passesFilters = false;
                                      break;
                                    case 'gt':
                                      if (metricValue <= filter.value) passesFilters = false;
                                      break;
                                    case 'lt':
                                      if (metricValue >= filter.value) passesFilters = false;
                                      break;
                                    case 'eq':
                                      if (Math.abs(metricValue - filter.value) > 0.0001) passesFilters = false;
                                      break;
                                  }

                                  if (!passesFilters) break;
                                }

                                if (!passesFilters) {
                                  return null;
                                }

                                const corrColor = absCorr > 0.8 ? 'text-green-900 font-bold' : absCorr > 0.5 ? 'text-blue-900 font-medium' : absCorr < 0.1 ? 'text-red-600 font-bold' : 'text-gray-900';
                                const vifColor = vif && vif > 10 ? 'text-red-600 font-bold' : vif && vif > 5 ? 'text-orange-900 font-medium' : 'text-gray-900';
                                const varianceColor = stat.variance_status === 'zero' ? 'text-red-600 font-bold' : stat.variance_status === 'near_zero' ? 'text-orange-600 font-medium' : 'text-gray-900';

                                return (
                                  <tr key={stat.variable} className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                                    <td className="px-3 py-2">
                                      <input
                                        type="checkbox"
                                        checked={manualVariableSelection[stat.variable] || false}
                                        onChange={(e) => {
                                          setManualVariableSelection(prev => ({
                                            ...prev,
                                            [stat.variable]: e.target.checked
                                          }));
                                        }}
                                        className="rounded border-gray-300"
                                      />
                                    </td>
                                    <td className="px-3 py-2 text-gray-900 font-medium">{stat.variable}</td>
                                    <td className={`px-3 py-2 text-right ${corrColor}`}>
                                      {stat.correlation?.toFixed(4) || 'N/A'}
                                    </td>
                                    <td className={`px-3 py-2 text-right ${vifColor}`}>
                                      {vif !== null && vif !== undefined ? vif.toFixed(2) : 'N/A'}
                                    </td>
                                    <td className="px-3 py-2 text-right text-purple-900 dark:text-purple-300">
                                      {iv !== null ? iv.toFixed(4) : 'N/A'}
                                    </td>
                                    <td className={`px-3 py-2 text-right ${varianceColor}`}>
                                      {stat.std !== null && stat.std !== undefined ? stat.std.toFixed(4) : 'N/A'}
                                      {stat.variance_status === 'zero' && <span className="ml-1 text-xs text-red-600">(Zero)</span>}
                                      {stat.variance_status === 'near_zero' && <span className="ml-1 text-xs text-orange-600">(Low)</span>}
                                    </td>
                                  </tr>
                                );
                              }).filter(Boolean)}
                            </tbody>
                          </table>
                        </div>

                        {/* Selection Actions */}
                        <div className="flex items-center justify-between mt-4">
                          <div className="text-xs text-gray-600">
                            {Object.values(manualVariableSelection).filter(Boolean).length} of {getAvailableVariablesForManualSelection().length} variables selected
                            {autoActiveFilters.length > 0 && (
                              <span className="ml-2 text-blue-600">
                                ({getFilteredVariablesForManualSelection().length} match filters)
                              </span>
                            )}
                          </div>
                          <div className="flex items-center space-x-2">
                            {/* Select Filtered Variables Button - Only selects variables matching current filters */}
                            <button
                              onClick={() => {
                                const filteredVars = getFilteredVariablesForManualSelection();
                                const newSelection: Record<string, boolean> = {};
                                // Only select filtered variables - deselect everything else
                                filteredVars.forEach((stat: any) => {
                                  newSelection[stat.variable] = true;
                                });
                                // Don't preserve existing selections - only filtered variables should be selected
                                setManualVariableSelection(newSelection);
                              }}
                              disabled={autoActiveFilters.length === 0 || getFilteredVariablesForManualSelection().length === 0}
                              className="px-3 py-1 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg text-xs hover:bg-blue-700 dark:hover:bg-[#333380] disabled:opacity-50 disabled:cursor-not-allowed"
                              title={autoActiveFilters.length === 0 ? "Add filters first to use this button" : `Select ${getFilteredVariablesForManualSelection().length} filtered variables`}
                            >
                              Select Filtered
                            </button>
                            {/* Select All Button - Selects all available variables */}
                            <button
                              onClick={() => {
                                const availableVars = getAvailableVariablesForManualSelection();
                                const newSelection: Record<string, boolean> = {};
                                availableVars.forEach((stat: any) => {
                                  newSelection[stat.variable] = true;
                                });
                                setManualVariableSelection(newSelection);
                              }}
                              className="px-3 py-1 bg-green-600 text-white rounded-lg text-xs hover:bg-green-700"
                            >
                              Select All
                            </button>
                            <button
                              onClick={() => {
                                const availableVars = getAvailableVariablesForManualSelection();
                                const newSelection: Record<string, boolean> = {};
                                availableVars.forEach((stat: any) => {
                                  newSelection[stat.variable] = false;
                                });
                                setManualVariableSelection(newSelection);
                              }}
                              className="px-3 py-1 bg-gray-600 text-white rounded-lg text-xs hover:bg-gray-700"
                            >
                              Deselect All
                            </button>
                            <button
                              onClick={() => {
                                setVariableSelectionConfirmed(true);
                              }}
                              disabled={Object.values(manualVariableSelection).filter(Boolean).length === 0}
                              className="px-3 py-1 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg text-xs hover:bg-blue-700 dark:hover:bg-[#333380] disabled:opacity-50"
                            >
                              Confirm Selection
                            </button>
                  </div>
                </div>

                        {variableSelectionConfirmed && (
                          <div className="mt-3 text-green-700 text-xs flex items-center space-x-2">
                            <span className="inline-block w-2 h-2 bg-green-600 rounded-full"></span>
                            <span>Manual variable selection confirmed for training.</span>
                  </div>
                        )}
                </div>
                    )}
                  </div>
                )}

                {/* Algorithm Selection Results (hidden in auto mode) */}
                {false && autoAnalysisData && autoAlgorithmSelection && (
                  <div className="border border-gray-200 dark:border-slate-700 rounded-lg p-4 bg-gradient-to-br from-purple-50 to-pink-50 dark:from-slate-900 dark:to-slate-800">
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <h5 className="font-medium text-gray-900 dark:text-white flex items-center space-x-2">
                          <Brain className="h-4 w-4 text-purple-600" />
                          <span>AI Algorithm Selection</span>
                        </h5>
                        <div className="text-sm text-gray-600 dark:text-white">
                          {(() => {
                            const total = autoAlgorithmSelection.selected_algorithms?.length || 0;
                            const selectedCount =
                              Object.values(autoAlgorithmChoices).filter(Boolean).length || total;
                            return `${selectedCount} of ${total} algorithms selected for training`;
                          })()}
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className="text-xs text-purple-700 bg-purple-100 dark:bg-purple-900/40 dark:text-purple-200 px-2 py-1 rounded-full">
                          Auto-selected (customizable)
                        </span>
                      </div>
                    </div>

                    <div className="bg-white dark:bg-slate-900/70 border border-purple-200 dark:border-slate-700 rounded-lg p-4">
                      <div className="mb-4">
                        <h6 className="text-sm font-semibold text-gray-900 dark:text-white mb-1">
                          Selected Algorithms (Select/Deselect to customize)
                        </h6>
                        <div className="text-xs text-gray-600 dark:text-gray-300 mb-3">
                          Choose which of the AI-suggested algorithms you want to train.
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                          {autoAlgorithmSelection.selected_algorithms?.map((algo: any, index: number) => {
                            const key = algo.name || algo.display_name || `algo_${index}`;
                            const checked = autoAlgorithmChoices[key] ?? true;
                            return (
                              <label
                                key={key}
                                className={`cursor-pointer bg-purple-50 dark:bg-slate-900/80 border rounded-lg p-3 flex flex-col space-y-1 ${
                                  checked
                                    ? 'border-purple-400 ring-1 ring-purple-300 dark:border-purple-400'
                                    : 'border-purple-100 opacity-70 dark:border-slate-700'
                                }`}
                              >
                                <div className="flex items-center justify-between mb-1">
                                  <div className="flex items-center space-x-2">
                                    <input
                                      type="checkbox"
                                      className="rounded text-purple-600"
                                      checked={checked}
                                      onChange={(e) =>
                                        setAutoAlgorithmChoices((prev) => ({
                                          ...prev,
                                          [key]: e.target.checked,
                                        }))
                                      }
                                    />
                                    <span className="text-sm font-medium text-purple-900 dark:text-purple-300">
                                      {algo.display_name}
                                    </span>
                                  </div>
                                </div>
                                <p className="text-xs text-purple-700 dark:text-purple-300">{algo.reason}</p>
                              </label>
                            );
                          })}
                        </div>
                      </div>

                      {/* COMMENTED OUT: User requested to remove this text
                      <div className="text-xs text-purple-700 bg-purple-50 rounded-lg p-3">
                        Algorithms were auto-selected based on dataset size, problem type, and feature
                        characteristics. You can refine which algorithms are actually used for training.
                      </div>
                      */}
                    </div>
                  </div>
                )}
              </div>
              )}

              {/* Auto training run — actions only (no surrounding tinted card) */}
              {!!autoTargetVariable && !variableSelectionConfirmed && (
                <div
                  className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-900/25 dark:text-amber-100"
                  role="status"
                >
                  Complete Step 2 (variable screener): confirm your variables and run RFE, then you can run auto
                  training here.
                </div>
              )}
              {!!autoTargetVariable && (
                <div className="flex flex-wrap items-center justify-end gap-3">
                  {(isAutoTraining || segmentAutoTrainingInProgress) && (
                    <button
                      type="button"
                      onClick={
                        trainingMode === 'segment-specific'
                          ? handleCancelSegmentAutoTrainingClick
                          : handleCancelAutoTrainingClick
                      }
                      className="px-4 py-2 border border-red-500 text-red-600 rounded-lg text-sm hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                    >
                      Cancel
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={trainingMode === 'segment-specific' ? handleSegmentAutoTraining : handleAutoTraining}
                    disabled={
                      !variableSelectionConfirmed ||
                      (trainingMode === 'segment-specific' ? segmentAutoTrainingInProgress : isAutoTraining)
                    }
                    title={
                      !variableSelectionConfirmed
                        ? 'Confirm variables and run RFE in Step 2 (variable screener) before auto training.'
                        : undefined
                    }
                    className="px-6 py-3 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] disabled:opacity-50 disabled:cursor-not-allowed transition-colors inline-flex items-center gap-2 font-medium"
                  >
                    {(trainingMode === 'segment-specific' ? segmentAutoTrainingInProgress : isAutoTraining) ? (
                      <>
                        <Loader className="h-5 w-5 animate-spin" />
                        <span>Training Models...</span>
                      </>
                    ) : (
                      <>
                        <Zap className="h-5 w-5 shrink-0" />
                        <span>{trainingMode === 'segment-specific' ? '🎯 Run Auto Training (All Segments)' : '🚀 Run Auto Training'}</span>
                      </>
                    )}
                  </button>
                </div>
              )}

              {/* Training Progress */}
              {(isAutoTraining || segmentAutoTrainingInProgress) && (
                <div className="border border-gray-200 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-4">
                    <h4 className="font-medium text-gray-900">
                      {trainingMode === 'segment-specific' ? 'Segment Auto Training Progress' : 'Auto Training Progress'}
                    </h4>
                    <div className="text-sm text-gray-600">
                      {segmentAutoStep === 'analyzing' ? 'Analyzing segments...' :
                       segmentAutoStep === 'training' ? 'Training models...' :
                       'Training in progress...'}
                    </div>
                </div>

                  <div className="space-y-3">
                    <div className="w-full bg-gray-200 rounded-full h-3">
                      <div className={`${trainingMode === 'segment-specific' ? 'bg-gradient-to-r from-purple-500 to-blue-500' : 'bg-gradient-to-r from-green-500 to-blue-500'} h-3 rounded-full animate-pulse`} style={{ width: '60%' }} />
                    </div>
                    <div className="text-xs text-gray-600 text-center">
                      {trainingMode === 'segment-specific'
                        ? `AI is automatically analyzing ${segmentInfo?.total_segments || 'all'} segments and optimizing models for each...`
                        : 'AI is automatically optimizing hyperparameters and training models...'
                      }
                    </div>
                  </div>
                </div>
              )}

              {/* Training Results */}
              {autoTrainingResults && trainingMode === 'global' && (
                <div className="border border-gray-200 rounded-lg p-4">
                  <div className="flex items-center space-x-2 mb-4">
                    <CheckCircle className="h-5 w-5 text-green-600" />
                    <h4 className="font-medium text-gray-900">Auto Training Complete</h4>
                  </div>

                  {/* Preprocessing Summary Card */}
                  {autoTrainingResults.preprocessing_summary && (
                    <div className="mb-6 bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-slate-900 dark:to-slate-800 rounded-lg border-2 border-blue-200 dark:border-slate-700 shadow-md">
                      <div className="p-4">
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center space-x-2">
                            <div className="p-2 bg-blue-600 rounded-full">
                              <Activity className="h-4 w-4 text-white" />
                            </div>
                            <div>
                              <h5 className="font-semibold text-gray-900 dark:text-white">🔄 Data Preprocessing Summary</h5>
                              <p className="text-xs text-gray-600 dark:text-gray-300">Training Mode: Global Auto</p>
                            </div>
                          </div>
                          <button
                            onClick={() => setPreprocessingSummaryExpanded(!preprocessingSummaryExpanded)}
                            className="text-blue-600 hover:text-blue-800 dark:text-blue-300 dark:hover:text-blue-200 transition-colors"
                          >
                            {preprocessingSummaryExpanded ? (
                              <ChevronUp className="h-5 w-5" />
                            ) : (
                              <ChevronDown className="h-5 w-5" />
                            )}
                          </button>
                        </div>
                        
                        {!preprocessingSummaryExpanded ? (
                          <div className="mt-2">
                            <p className="text-sm text-gray-700 dark:text-gray-200">
                              📊 Summary: {autoTrainingResults.preprocessing_summary.total_processed || 0} variables processed | {autoTrainingResults.preprocessing_summary.total_dropped || 0} variables dropped
                            </p>
                            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">[▼ Expand Details]</p>
                          </div>
                        ) : (
                          <div className="mt-4">
                            {autoTrainingResults.preprocessing_summary.is_already_preprocessed ? (
                              <div className="bg-white dark:bg-slate-900/70 rounded-lg p-4 border border-green-200 dark:border-slate-700">
                                <p className="text-sm text-green-800 dark:text-green-300 font-medium mb-2">✅ Data appears to be already preprocessed.</p>
                                <ul className="text-xs text-gray-700 dark:text-gray-200 space-y-1">
                                  <li>✓ No missing values detected</li>
                                  <li>✓ No categorical variables found</li>
                                  <li>✓ All features are numeric and normalized</li>
                                  <li>✓ No constant variables detected</li>
                                </ul>
                                <p className="text-xs text-gray-600 dark:text-gray-300 mt-2">No additional preprocessing required.</p>
                              </div>
                            ) : (
                              <div className="bg-white dark:bg-slate-900/70 rounded-lg border border-gray-200 dark:border-slate-700 max-h-96 overflow-y-auto">
                                <div className="p-4 space-y-4">
                                  {autoTrainingResults.preprocessing_summary.variables?.map((variable: any, idx: number) => (
                                    <div key={idx} className="border-b border-gray-200 dark:border-slate-700 pb-4 last:border-b-0 last:pb-0">
                                      <h6 className="font-semibold text-gray-900 dark:text-white mb-2">VARIABLE: {variable.variable}</h6>
                                      
                                      {variable.missing_imputation && (
                                        <div className="ml-4 mb-2">
                                          <div className="flex items-start space-x-2">
                                            <span className="text-green-600">✓</span>
                                            <div>
                                              <p className="text-sm font-medium text-gray-800 dark:text-gray-200">Missing Value Imputation</p>
                                              <p className="text-xs text-gray-600 dark:text-gray-300">Reason: {variable.missing_imputation.reason}</p>
                                              <p className="text-xs text-gray-500 dark:text-gray-400">Method: {variable.missing_imputation.method === 'median' ? `Median = ${variable.missing_imputation.value}` : `Mode = "${variable.missing_imputation.value}"`}</p>
                                            </div>
                                          </div>
                                        </div>
                                      )}
                                      
                                      {variable.encoding && (
                                        <div className="ml-4 mb-2">
                                          <div className="flex items-start space-x-2">
                                            <span className="text-green-600">✓</span>
                                            <div>
                                              <p className="text-sm font-medium text-gray-800 dark:text-gray-200">Label Encoding Applied</p>
                                              <p className="text-xs text-gray-600 dark:text-gray-300">Reason: {variable.encoding.reason}</p>
                                              {variable.encoding.mapping_sample && (
                                                <p className="text-xs text-gray-500 dark:text-gray-400">
                                                  Transformation: {Object.entries(variable.encoding.mapping_sample).slice(0, 3).map(([k, v]) => `"${k}"→${v}`).join(', ')}
                                                  {Object.keys(variable.encoding.mapping_sample).length > 3 ? '...' : ''}
                                                </p>
                                              )}
                                            </div>
                                          </div>
                                        </div>
                                      )}
                                      
                                      {variable.scaling && (
                                        <div className="ml-4 mb-2">
                                          <div className="flex items-start space-x-2">
                                            <span className="text-green-600">✓</span>
                                            <div>
                                              <p className="text-sm font-medium text-gray-800 dark:text-gray-200">Standard Scaling Applied</p>
                                              <p className="text-xs text-gray-600 dark:text-gray-300">Reason: {variable.scaling.reason}</p>
                                              {variable.scaling.original_range && variable.scaling.scaled_range && (
                                                <p className="text-xs text-gray-500 dark:text-gray-400">
                                                  Transformation: [{variable.scaling.original_range[0].toFixed(1)}, {variable.scaling.original_range[1].toFixed(1)}] → [{variable.scaling.scaled_range[0].toFixed(2)}, {variable.scaling.scaled_range[1].toFixed(2)}]
                                                </p>
                                              )}
                                            </div>
                                          </div>
                                        </div>
                                      )}
                                    </div>
                                  ))}
                                  
                                  {autoTrainingResults.preprocessing_summary.dropped_variables?.map((dropped: any, idx: number) => (
                                    <div key={idx} className="border-b border-gray-200 dark:border-slate-700 pb-4 last:border-b-0 last:pb-0">
                                      <h6 className="font-semibold text-gray-900 dark:text-white mb-2">VARIABLE: {dropped.variable}</h6>
                                      <div className="ml-4">
                                        <div className="flex items-start space-x-2">
                                          <span className="text-red-600">✗</span>
                                          <div>
                                            <p className="text-sm font-medium text-red-800 dark:text-red-300">DROPPED</p>
                                            <p className="text-xs text-gray-600 dark:text-gray-300">Reason: {dropped.reason}</p>
                                            {dropped.details && (
                                              <p className="text-xs text-gray-500 dark:text-gray-400">Details: {dropped.details}</p>
                                            )}
                                          </div>
                                        </div>
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                            
                            <div className="mt-3 pt-3 border-t border-gray-200 dark:border-slate-700">
                              <p className="text-sm text-gray-700 dark:text-gray-200">
                                📊 Summary: {autoTrainingResults.preprocessing_summary.total_processed || 0} variables processed | {autoTrainingResults.preprocessing_summary.total_dropped || 0} variables dropped
                              </p>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
                    <div className="bg-green-50 border border-green-200 dark:bg-slate-900/70 dark:border-slate-700 rounded-lg p-3">
                      <div className="text-xs text-green-600 dark:text-white">Models Trained</div>
                      <div className="text-xl font-bold text-green-900 dark:text-white">{autoTrainingResults.auto_selection_summary?.num_models_trained || autoTrainingResults.training_results?.auto_selection_summary?.num_models_trained || 0}</div>
                    </div>
                    <div className="bg-blue-50 border border-blue-200 dark:bg-slate-900/70 dark:border-slate-700 rounded-lg p-3">
                      <div className="text-xs text-blue-600 dark:text-white">Variables Used</div>
                      <div className="text-xl font-bold text-blue-900 dark:text-white">{autoTrainingResults.used_features?.length || 0}</div>
                      <div className="text-xs text-blue-700 dark:text-gray-200 mt-1">
                        {autoTrainingResults.auto_selection_summary?.variable_selection_mode || (autoTrainingResults.training_results?.auto_selection_summary ? 'AI selected' : 'Unknown')}
                      </div>
                    </div>
                    <div className="bg-purple-50 border border-purple-200 dark:bg-slate-900/70 dark:border-slate-700 rounded-lg p-3">
                      <div className="text-xs text-purple-600 dark:text-white">Algorithms Tested</div>
                      <div className="text-xl font-bold text-purple-900 dark:text-white">{autoTrainingResults.algorithm_selection?.selected_algorithms?.length || 0}</div>
                    </div>
                    <div className="bg-orange-50 border border-orange-200 dark:bg-slate-900/70 dark:border-slate-700 rounded-lg p-3">
                      <div className="text-xs text-orange-600 dark:text-white">Best Score</div>
                      <div className="text-xl font-bold text-orange-900 dark:text-white">
                        {(() => {
                          // Filter out error results and get valid metrics
                          const validResults = autoTrainingResults.results?.filter((r: any) => !r.error && r.metrics) || [];
                          if (validResults.length > 0) {
                            const primaryMetric = autoTrainingResults.problem_type === 'classification' ? 'f1' : 'r2';
                            const scores = validResults.map((r: any) => r.metrics?.[primaryMetric] || 0);
                            return Math.max(...scores).toFixed(4);
                          }
                          return '0.0000';
                        })()}
                        </div>
                  </div>
                </div>

                  {/* Model Results — "All Models Performance" (hidden) */}
                  {false && autoTrainingResults?.results && autoTrainingResults.results.length > 0 && (
                    <div className="space-y-3">
                      <h5 className="font-medium text-gray-900">All Models Performance</h5>
                      {autoTrainingResults.results.map((result: any, index: number) => {
                        if (result.error) {
                          return (
                            <div key={index} className="bg-red-50 border border-red-200 rounded-lg p-3">
                              <div className="flex items-center space-x-2">
                                <AlertCircle className="h-4 w-4 text-red-600" />
                                <span className="text-sm font-medium text-red-900">{result.algorithm}</span>
                              </div>
                              <p className="text-xs text-red-700 mt-1">Training failed: {result.error}</p>
                            </div>
                          );
                        }

                        const primaryMetric = autoTrainingResults?.problem_type === 'classification' ? 'f1' : 'r2';
                        const primaryScore = result?.metrics?.[primaryMetric] || 0;
                        const isBest = autoTrainingResults?.best_model_selection?.best_model_id === result.model_id;

                        return (
                            <div key={index} className={`rounded-lg p-3 ${isBest ? 'bg-green-50 border-2 border-green-300 dark:bg-slate-900/70 dark:border-slate-700' : 'bg-gray-50 border border-gray-200 dark:bg-slate-900/60 dark:border-slate-700'}`}>
                            <div className="flex items-center justify-between">
                              <div className="flex items-center space-x-2">
                                {isBest ? (
                                  <div className="flex items-center space-x-2">
                                    <TrendingUp className="h-4 w-4 text-green-600" />
                                    <span className="text-xs bg-green-600 text-white px-2 py-1 rounded-full font-bold">BEST</span>
                                  </div>
                                ) : (
                                  <CheckCircle className="h-4 w-4 text-green-600" />
                                )}
                                <span className={`text-sm font-medium ${isBest ? 'text-green-900 dark:text-white' : 'text-gray-900 dark:text-white'}`}>{result?.algorithm || 'Unknown'}</span>
                                <span className="text-xs text-gray-500 dark:text-gray-300">({result?.model_id || 'N/A'})</span>
                              </div>
                              <div className="text-right">
                                <div className={`text-sm font-bold ${isBest ? 'text-green-900 dark:text-white' : 'text-gray-900 dark:text-white'}`}>
                                  {primaryMetric === 'f1' ? 'F1' : 'R²'}: {primaryScore.toFixed(4)}
                                </div>
                                <div className="text-xs text-gray-500 dark:text-gray-300">Primary Metric</div>
                              </div>
                            </div>
                            <div className="mt-2 grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                              {(() => {
                                const metrics = result?.metrics || {};
                                const problemType = autoTrainingResults?.problem_type || 'classification';
                                
                                // For classification, prioritize: accuracy, precision, recall, AUC (if available)
                                // For regression, show: r2, mae, mse, rmse
                                let metricsToShow: string[] = [];
                                
                                if (problemType === 'classification') {
                                  // Show all classification metrics including KS Statistic
                                  metricsToShow = ['accuracy', 'precision', 'recall'];
                                  // Add KS statistic if available
                                  if (metrics['test_ks_statistic'] !== undefined) {
                                    metricsToShow.push('test_ks_statistic');
                                  }
                                  // Add AUC or F1
                                  if (metrics['auc'] !== undefined) {
                                    metricsToShow.push('auc');
                                  } else if (metrics['f1'] !== undefined) {
                                    metricsToShow.push('f1');
                                  }
                                } else {
                                  // Regression metrics
                                  metricsToShow = ['r2', 'mae', 'mse', 'rmse'].filter(m => metrics[m] !== undefined);
                                }
                                
                                return metricsToShow.map((key: string) => {
                                  const value = metrics[key];
                                  // Friendly metric names
                                  const metricNameMap: Record<string, string> = {
                                    'accuracy': 'ACCURACY',
                                    'precision': 'PRECISION',
                                    'recall': 'RECALL',
                                    'f1': 'F1-SCORE',
                                    'auc': 'AUC-ROC',
                                    'test_ks_statistic': 'KS STATISTIC',
                                    'r2': 'R²',
                                    'mae': 'MAE',
                                    'mse': 'MSE',
                                    'rmse': 'RMSE'
                                  };
                                  
                                  const displayName = metricNameMap[key] || String(key).toUpperCase();
                                  
                                  return (
                                    <div key={key}>
                                      <span className="text-gray-600 dark:text-gray-300">{displayName}:</span>
                                      <span className="ml-1 font-medium">{typeof value === 'number' ? value.toFixed(4) : (typeof value === 'object' ? JSON.stringify(value) : String(value || 'N/A'))}</span>
                                    </div>
                                  );
                                });
                              })()}
                            </div>
                          </div>
                        );
                      })}
              </div>
                  )}

                  {/* Model Comparison Ranking (auto only; standalone — full "Best Model" card stays hidden) */}
                  {autoTrainingResults?.best_model_selection?.metrics_comparison &&
                    autoTrainingResults.best_model_selection.metrics_comparison.length > 1 && (
                      <div className={`mt-4 ${MTA_SECTION} p-4 md:p-5`}>
                        <div className="mb-3 flex flex-wrap items-center gap-2">
                          <ListChecks
                            className="h-5 w-5 shrink-0 text-emerald-600 dark:text-emerald-400"
                            aria-hidden
                          />
                          <h5 className={`${MTA_TITLE_SECTION} !text-base md:!text-lg`}>
                            Model Comparison Ranking
                          </h5>
                        </div>
                        <div className={`overflow-x-auto ${MTA_TABLE_SHELL}`}>
                          <table className="w-full min-w-[280px] text-sm">
                            <thead className={MTA_THEAD}>
                              <tr>
                                <th className="px-3 py-2.5 text-left">Rank</th>
                                <th className="px-3 py-2.5 text-left">Algorithm</th>
                                <th className="px-3 py-2.5 text-left">Status</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-200 bg-white dark:divide-slate-700 dark:bg-slate-950">
                              {(() => {
                                const bms = autoTrainingResults.best_model_selection;
                                const bestId = bms.best_model_id;
                                const bestAlgoNorm = String(bms.best_algorithm || '')
                                  .trim()
                                  .toLowerCase();
                                const bestTier = (m: any): number => {
                                  if (bestId != null && m?.model_id === bestId) return 0;
                                  if (m?.is_best) return 1;
                                  if (
                                    bestAlgoNorm &&
                                    String(m?.algorithm || '').trim().toLowerCase() === bestAlgoNorm
                                  )
                                    return 1;
                                  return 2;
                                };
                                const sorted = [...bms.metrics_comparison].sort((a: any, b: any) => {
                                  const ta = bestTier(a);
                                  const tb = bestTier(b);
                                  if (ta !== tb) return ta - tb;
                                  return (Number(a?.rank) || 999) - (Number(b?.rank) || 999);
                                });
                                const anyIdMatch =
                                  bestId != null && sorted.some((m: any) => m?.model_id === bestId);
                                const anyIsBestFlag = sorted.some((m: any) => m?.is_best);
                                const isChosenBest = (m: any) => {
                                  if (anyIdMatch) return m?.model_id === bestId;
                                  if (anyIsBestFlag) return Boolean(m?.is_best);
                                  if (
                                    bestAlgoNorm &&
                                    String(m?.algorithm || '').trim().toLowerCase() === bestAlgoNorm
                                  )
                                    return true;
                                  return false;
                                };
                                return sorted.map((model: any, idx: number) => {
                                  const displayRank = idx + 1;
                                  const showBest = isChosenBest(model);
                                  return (
                                    <tr
                                      key={model.model_id ?? `rank-${idx}`}
                                      className={
                                        showBest
                                          ? 'bg-green-50 dark:bg-emerald-950/35'
                                          : idx % 2 === 0
                                            ? 'bg-white dark:bg-slate-950'
                                            : 'bg-gray-50/90 dark:bg-slate-900/55'
                                      }
                                    >
                                      <td className="px-3 py-2.5">
                                        <div className="flex items-center gap-2">
                                          {displayRank === 1 && (
                                            <span className="text-lg leading-none" aria-hidden>
                                              🥇
                                            </span>
                                          )}
                                          {displayRank === 2 && (
                                            <span className="text-lg leading-none" aria-hidden>
                                              🥈
                                            </span>
                                          )}
                                          {displayRank === 3 && (
                                            <span className="text-lg leading-none" aria-hidden>
                                              🥉
                                            </span>
                                          )}
                                          <span className="font-medium text-gray-900 dark:text-white">
                                            {displayRank}
                                          </span>
                                        </div>
                                      </td>
                                      <td className="px-3 py-2.5 font-medium text-gray-900 dark:text-white">
                                        {model.algorithm}
                                      </td>
                                      <td className="px-3 py-2.5">
                                        {showBest ? (
                                          <span className="inline-flex items-center rounded-full bg-green-600 px-2.5 py-1 text-xs font-semibold text-white dark:bg-green-700 dark:text-white">
                                            ✓ Best Model
                                          </span>
                                        ) : (
                                          <span className="text-xs text-gray-600 dark:text-gray-400">
                                            Alternative
                                          </span>
                                        )}
                                      </td>
                                    </tr>
                                  );
                                });
                              })()}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                  {/* Best Model Recommendation (hidden per product request) */}
                  {false && autoTrainingResults?.best_model_selection && autoTrainingResults.best_model_selection.best_model && (
                    <div className="mt-6 border-2 border-green-300 dark:border-slate-700 bg-gradient-to-br from-green-50 to-emerald-50 dark:from-slate-900 dark:to-slate-800 rounded-lg p-5 shadow-lg">
                      <div className="flex items-center space-x-3 mb-4">
                        <div className="flex-shrink-0">
                          <div className="w-12 h-12 bg-green-600 rounded-full flex items-center justify-center">
                            <TrendingUp className="h-6 w-6 text-white" />
                          </div>
                        </div>
                        <div className="flex-1">
                          <h5 className="text-lg font-bold text-gray-900 dark:text-white">🏆 Best Model Selected</h5>
                          <p className="text-sm text-gray-600 dark:text-gray-300">AI-powered model recommendation based on comprehensive performance analysis</p>
                        </div>
                      </div>

                      <div className="bg-white dark:bg-slate-900/70 rounded-lg p-4 mb-4 border border-green-200 dark:border-slate-700">
                        <div className="flex items-center justify-between mb-3">
                          <div>
                            <div className="text-2xl font-bold text-green-900 dark:text-white mb-1">
                              {autoTrainingResults.best_model_selection.best_algorithm}
                            </div>
                            <div className="text-xs text-gray-600 dark:text-gray-300">
                              Model ID: {autoTrainingResults.best_model_selection.best_model_id}
                            </div>
                          </div>
                        </div>

                        {/* Key Performance Metrics (best model) — mirrors segment auto + manual training detail density */}
                        {autoTrainingResults.best_model_selection.best_model?.metrics && (
                          <div className="mb-4">
                            <h6 className="text-sm font-semibold text-gray-900 dark:text-white mb-2">📊 Key Performance Metrics</h6>
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                              {(() => {
                                const metrics = autoTrainingResults.best_model_selection.best_model.metrics;
                                const baseMetrics =
                                  autoTrainingResults.problem_type === 'regression'
                                    ? ['r2', 'adjusted_r2', 'mae', 'mse', 'rmse']
                                    : ['accuracy', 'auc', 'f1', 'precision', 'recall', 'log_loss', 'ks_statistic'];
                                return baseMetrics.slice(0, 4).map((key) => {
                                  const value = metrics[key];
                                  if (value === undefined || value === null) return null;
                                  return (
                                    <div
                                      key={key}
                                      className="bg-gray-50 dark:bg-slate-900/70 rounded-lg p-3 text-center border border-transparent dark:border-slate-700"
                                    >
                                      <div className="text-xs text-gray-600 dark:text-gray-300 uppercase mb-1">{key}</div>
                                      <div className="text-lg font-bold text-gray-900 dark:text-white">
                                        {typeof value === 'number'
                                          ? value.toFixed(4)
                                          : typeof value === 'object'
                                            ? JSON.stringify(value)
                                            : String(value || 'N/A')}
                                      </div>
                                    </div>
                                  );
                                }).filter(Boolean);
                              })()}
                            </div>
                          </div>
                        )}

                        <div className="border-t border-gray-200 dark:border-slate-700 pt-3 mt-3">
                          <div className="text-sm font-medium text-gray-700 dark:text-gray-200 mb-2">💡 Why This Model?</div>
                          <p className="text-sm text-gray-600 dark:text-gray-300 leading-relaxed">
                            {autoTrainingResults.best_model_selection.reasoning}
                          </p>
                        </div>

                        {/* Key Metrics from selection rationale (when final model metrics blob is not on the payload) */}
                        {autoTrainingResults.best_model_selection.reasoning_details?.primary_metrics &&
                          !autoTrainingResults.best_model_selection.best_model?.metrics && (
                          <div className="border-t border-gray-200 dark:border-slate-700 pt-3 mt-3">
                            <div className="text-sm font-medium text-gray-700 dark:text-gray-200 mb-3">📊 Key Performance Metrics</div>
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                              {Object.entries(autoTrainingResults.best_model_selection.reasoning_details.primary_metrics)
                                .filter(([metric]) => {
                                  // Skip ks_statistic (the backward-compat alias) and train_ks_statistic, show only test_ks_statistic
                                  if (metric === 'ks_statistic' || metric === 'train_ks_statistic') return false;
                                  return true;
                                })
                                .map(([metric, value]: [string, any]) => {
                                  return (
                                    <div key={metric} className="bg-gray-50 dark:bg-slate-900/70 rounded-lg p-3 text-center border border-gray-200 dark:border-slate-700 hover:border-gray-300 transition-colors">
                                      <div className="text-xs text-gray-600 dark:text-gray-300 font-semibold mb-1">{formatMetricName(metric)}</div>
                                      <div className="text-lg font-bold text-gray-900 dark:text-white">
                                        {typeof value === 'number' ? value.toFixed(4) : (typeof value === 'object' ? JSON.stringify(value) : String(value || 'N/A'))}
                                      </div>
                                    </div>
                                  );
                                })}
                            </div>
                          </div>
                        )}

                        {/* Action buttons */}
                        <div className="border-t border-gray-200 dark:border-slate-700 pt-3 mt-3 flex space-x-3">
                          <button
                            onClick={() => {
                              // Set selected algorithm to show iteration history
                              setSelectedAlgorithmForHistory(autoTrainingResults.best_model_selection.best_algorithm);
                              // Scroll to iteration history section (if exists)
                              const historySection = document.getElementById('iteration-history-section');
                              if (historySection) {
                                historySection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                              }
                            }}
                            className="flex-1 px-4 py-2 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] transition-colors text-sm font-medium flex items-center justify-center space-x-2"
                          >
                            <Activity className="h-4 w-4" />
                            <span>View Training History</span>
                          </button>
                          <button
                            onClick={() => handleModelExport(autoTrainingResults.best_model_selection.best_model)}
                            className="flex-1 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm font-medium flex items-center justify-center space-x-2"
                          >
                            <Download className="h-4 w-4" />
                            <span>Export Best Model</span>
                          </button>
                        </div>
                      </div>

                    </div>
                  )}

                  {/* Iteration History for Best Model (hidden; use Step 6 viz + selected algorithm) */}
                  {false && autoTrainingResults?.best_model_selection && autoTrainingResults.best_model_selection.best_model && (
                    <div id="iteration-history-section" className="mt-6 border border-gray-200 rounded-lg p-4 bg-white">
                      <div className="mb-4">
                        <h5 className="text-lg font-bold text-gray-900 mb-2">
                          📈 Training History - {autoTrainingResults.best_model_selection.best_algorithm}
                        </h5>
                        <p className="text-sm text-gray-600">
                          Detailed iteration-by-iteration performance progression of the best model
                        </p>
                      </div>

                      {autoTrainingResults.best_model_selection.best_model.iteration_history && 
                       autoTrainingResults.best_model_selection.best_model.iteration_history.length > 0 ? (
                        <>
                          {/* Iteration History Chart */}
                          <div className="mb-4 h-64">
                            <ResponsiveContainer width="100%" height="100%">
                              <LineChart
                                data={autoTrainingResults.best_model_selection.best_model.iteration_history.map((iter: any) => ({
                                  iteration: iter.iteration,
                                  score: iter.metrics?.[autoTrainingResults.problem_type === 'classification' ? 'auc' : 'r2'] || iter.score || 0
                                }))}
                                margin={{ top: 10, right: 30, left: 10, bottom: 10 }}
                              >
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis 
                                  dataKey="iteration" 
                                  label={{ value: 'Iteration', position: 'insideBottom', offset: -5 }}
                                />
                                <YAxis 
                                  label={{ value: 'Score', angle: -90, position: 'insideLeft' }}
                                  domain={[0, 1]}
                                />
                                <Tooltip 
                                  formatter={(value: number) => [value.toFixed(4), 'Score']}
                                  labelFormatter={(label) => `Iteration ${label}`}
                                  cursor={isDarkMode ? { fill: 'rgba(15, 23, 42, 0.4)' } : { fill: 'rgba(0, 0, 0, 0.05)' }}
                                  contentStyle={{
                                    backgroundColor: isDarkMode ? 'rgba(15, 23, 42, 0.95)' : 'rgba(255, 255, 255, 0.95)',
                                    border: isDarkMode ? '1px solid #334155' : '1px solid #e5e7eb',
                                    borderRadius: '8px',
                                    color: isDarkMode ? '#e2e8f0' : '#111827'
                                  }}
                                  labelStyle={{ color: isDarkMode ? '#e2e8f0' : '#111827' }}
                                  itemStyle={{ color: isDarkMode ? '#e2e8f0' : '#111827' }}
                                />
                                <Legend />
                                <Line 
                                  type="monotone" 
                                  dataKey="score" 
                                  stroke="#10b981" 
                                  strokeWidth={2}
                                  name={autoTrainingResults.problem_type === 'classification' ? 'AUC-ROC' : 'R² Score'}
                                  dot={{ fill: '#10b981', r: 4 }}
                                  activeDot={{ r: 6 }}
                                />
                              </LineChart>
                            </ResponsiveContainer>
                          </div>

                          {/* Iteration Details Table */}
                          <div className="border border-gray-200 rounded-lg overflow-hidden">
                            <div className="overflow-x-auto max-h-96">
                              <table className="w-full text-sm">
                              <thead className={`${MTA_THEAD} sticky top-0`}>
                                <tr>
                                  <th className="px-4 py-3 text-left font-semibold text-gray-700 dark:text-gray-200">Iteration</th>
                                  <th className="px-4 py-3 text-right font-semibold text-gray-700 dark:text-gray-200">Accuracy</th>
                                  <th className="px-4 py-3 text-right font-semibold text-gray-700 dark:text-gray-200">Precision</th>
                                  <th className="px-4 py-3 text-right font-semibold text-gray-700 dark:text-gray-200">Recall</th>
                                  <th className="px-4 py-3 text-right font-semibold text-gray-700 dark:text-gray-200">F1-Score</th>
                                  <th className="px-4 py-3 text-right font-semibold text-gray-700 dark:text-gray-200">KS Statistic</th>
                                  {autoTrainingResults.problem_type === 'classification' ? (
                                    <th className="px-4 py-3 text-right font-semibold text-gray-700 dark:text-gray-200">AUC-ROC</th>
                                  ) : (
                                    <th className="px-4 py-3 text-right font-semibold text-gray-700 dark:text-gray-200">R²</th>
                                  )}
                                  {autoTrainingResults.problem_type === 'classification' && (
                                    <th className="px-4 py-3 text-right font-semibold text-gray-700 dark:text-gray-200">Log Loss</th>
                                  )}
                                  <th className="px-4 py-3 text-left font-semibold text-gray-700 dark:text-gray-200">Hyperparameters</th>
                                  <th className="px-4 py-3 text-right font-semibold text-gray-700 dark:text-gray-200">Improvement</th>
                                  <th className="px-4 py-3 text-left font-semibold text-gray-700 dark:text-gray-200">Status</th>
                                </tr>
                              </thead>
                              <tbody className="bg-white dark:bg-slate-950 divide-y divide-gray-200 dark:divide-slate-700">
                                {(() => {
                                  const hist = autoTrainingResults.best_model_selection.best_model.iteration_history;
                                  const soleBestIdx = getSoleBestIterationIndexForDisplay(hist);
                                  const formatHpCell = (hp: any) => {
                                    if (hp == null) return 'N/A';
                                    if (typeof hp === 'object') {
                                      const formatted = Object.entries(hp)
                                        .map(([k, v]) => `${k}:${v}`)
                                        .join(', ');
                                      return formatted.length > 50 ? `${formatted.slice(0, 47)}...` : formatted;
                                    }
                                    return String(hp);
                                  };
                                  return hist.map((iter: any, idx: number) => {
                                  const isBestIteration = soleBestIdx !== null && idx === soleBestIdx;
                                  const ll =
                                    iter.metrics?.log_loss ??
                                    iter.metrics?.test_log_loss;
                                  return (
                                    <tr
                                      key={idx}
                                      className={`transition-colors hover:bg-gray-50 dark:hover:bg-slate-700/95 ${
                                        isBestIteration
                                          ? 'bg-green-50 dark:bg-slate-900/70'
                                          : idx % 2 === 0
                                            ? 'bg-white dark:bg-slate-950'
                                            : 'bg-gray-50 dark:bg-slate-900/60'
                                      }`}
                                    >
                                      <td className="px-4 py-3 font-medium text-gray-900 dark:text-white">{iter.iteration}</td>
                                      {autoTrainingResults.problem_type === 'classification' ? (
                                        <>
                                          <td className="px-4 py-3 text-right text-gray-700 dark:text-gray-200">
                                            {iter.metrics?.test_accuracy?.toFixed(4) || iter.metrics?.accuracy?.toFixed(4) || 'N/A'}
                                          </td>
                                          <td className="px-4 py-3 text-right text-gray-700 dark:text-gray-200">
                                            {iter.metrics?.test_precision?.toFixed(4) || iter.metrics?.precision?.toFixed(4) || 'N/A'}
                                          </td>
                                          <td className="px-4 py-3 text-right text-gray-700 dark:text-gray-200">
                                            {iter.metrics?.test_recall?.toFixed(4) || iter.metrics?.recall?.toFixed(4) || 'N/A'}
                                          </td>
                                          <td className="px-4 py-3 text-right text-gray-700 dark:text-gray-200">
                                            {iter.metrics?.test_f1?.toFixed(4) || iter.metrics?.f1?.toFixed(4) || 'N/A'}
                                          </td>
                                          <td className="px-4 py-3 text-right text-gray-700 dark:text-gray-200">
                                            {iter.metrics?.test_ks_statistic?.toFixed(4) || iter.metrics?.ks_statistic?.toFixed(4) || 'N/A'}
                                          </td>
                                          <td className="px-4 py-3 text-right text-gray-700 dark:text-gray-200">
                                            {iter.metrics?.test_auc?.toFixed(4) || iter.metrics?.auc?.toFixed(4) || 'N/A'}
                                          </td>
                                          <td className="px-4 py-3 text-right text-gray-700 dark:text-gray-200">
                                            {typeof ll === 'number' && Number.isFinite(ll) ? ll.toFixed(4) : 'N/A'}
                                          </td>
                                        </>
                                      ) : (
                                        <>
                                          <td className="px-4 py-3 text-right text-gray-700 dark:text-gray-200">N/A</td>
                                          <td className="px-4 py-3 text-right text-gray-700 dark:text-gray-200">N/A</td>
                                          <td className="px-4 py-3 text-right text-gray-700 dark:text-gray-200">N/A</td>
                                          <td className="px-4 py-3 text-right text-gray-700 dark:text-gray-200">N/A</td>
                                          <td className="px-4 py-3 text-right text-gray-700 dark:text-gray-200">N/A</td>
                                          <td className="px-4 py-3 text-right text-gray-700 dark:text-gray-200">
                                            {iter.metrics?.test_r2?.toFixed(4) || iter.metrics?.r2?.toFixed(4) || 'N/A'}
                                          </td>
                                        </>
                                      )}
                                      <td className="px-4 py-3 text-sm text-gray-900 dark:text-slate-100">
                                        <div
                                          className="font-mono text-xs bg-gray-50 dark:bg-slate-800 p-2 rounded max-w-xs truncate"
                                          title={formatHpCell(iter.hyperparameters)}
                                        >
                                          {formatHpCell(iter.hyperparameters)}
                                        </div>
                                      </td>
                                        <td className={`px-4 py-3 text-right font-medium ${
                                          iter.improvement > 0 ? 'text-green-600' : 
                                          iter.improvement < 0 ? 'text-red-600' : 
                                          'text-gray-500'
                                        }`}>
                                          {iter.improvement > 0 && '+'}
                                          {iter.improvement?.toFixed(4) || '0.0000'}
                                        </td>
                                        <td className="px-4 py-3">
                                          {isBestIteration ? (
                                            <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-200">
                                              ⭐ Best
                                            </span>
                                          ) : (
                                            <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200">
                                              Completed
                                            </span>
                                          )}
                                        </td>
                                      </tr>
                                    );
                                  });
                                })()}
                                </tbody>
                              </table>
                            </div>
                          </div>

                          {/* Hyperparameters used */}
                          {autoTrainingResults.best_model_selection.best_model.hyperparameters && (
                            <div className="mt-4 p-4 bg-gray-50 rounded-lg">
                              <div className="flex items-center justify-between mb-2">
                                <h6 className="text-sm font-semibold text-gray-900">⚙️ Optimized Hyperparameters</h6>
                                {autoTrainingResults.best_model_selection.best_model.optimization_method && (
                                  <span className="text-xs px-2 py-1 rounded-full bg-blue-100 text-blue-700 font-medium">
                                    {autoTrainingResults.best_model_selection.best_model.optimization_method === 'bayesian_optimization' ? '🧠 Bayesian Optimization' :
                                     autoTrainingResults.best_model_selection.best_model.optimization_method === 'random_search' ? '🎲 Random Search' :
                                     '⚙️ Default'}
                                  </span>
                                )}
                              </div>
                              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                                {Object.entries(autoTrainingResults.best_model_selection.best_model.hyperparameters)
                                  .filter(([key]) => !['random_state', 'verbose', 'n_jobs'].includes(key))
                                  .slice(0, 8)
                                  .map(([key, value]: [string, any]) => (
                                    <div key={key} className="bg-white rounded-lg p-3 border border-gray-200">
                                      <div className="text-xs text-gray-600 mb-1">{key.replace(/_/g, ' ')}</div>
                                      <div className="text-sm font-bold text-gray-900">
                                        {typeof value === 'number' 
                                          ? (Number.isInteger(value) ? value : value.toFixed(4))
                                          : String(value)}
                                      </div>
                                    </div>
                                  ))}
                              </div>
                            </div>
                          )}
                        </>
                      ) : (
                        <div className="text-center py-8 text-gray-500">
                          <Activity className="h-12 w-12 mx-auto mb-2 opacity-30" />
                          <p className="text-sm">No iteration history available for this model</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Segment Auto Training Results */}
              {segmentAutoTrainingResults && trainingMode === 'segment-specific' && (
                <div className="border border-purple-200 dark:border-slate-700 rounded-lg p-4 bg-gradient-to-br from-purple-50 to-blue-50 dark:from-slate-900 dark:to-slate-800">
                  <div className="flex items-center space-x-2 mb-4">
                    <CheckCircle className="h-5 w-5 text-purple-600" />
                    <h4 className="font-medium text-gray-900 dark:text-white">Segment Auto Training Complete</h4>
                  </div>

                  {/* Preprocessing Summary Card - Show for selected segment */}
                  {selectedSegmentFilter !== 'all' && (() => {
                    const segmentResult = segmentAutoTrainingResults.segment_results?.[`segment_${selectedSegmentFilter}`];
                    const preprocessingSummary = segmentResult?.preprocessing_summary;
                    return preprocessingSummary ? (
                      <div className="space-y-4">
                        {/* Compact yellow panel for dropped variables (segment auto) */}
                        {Array.isArray(preprocessingSummary.dropped_variables) &&
                          preprocessingSummary.dropped_variables.length > 0 && (
                            <div className="mb-4 border border-yellow-300 bg-yellow-50 rounded-lg p-4 text-sm text-yellow-900">
                              <div className="flex items-start space-x-2 mb-2">
                                <AlertTriangle className="h-4 w-4 text-yellow-600 mt-0.5" />
                                <div>
                                  <div className="font-semibold">
                                    Variables Dropped During Preprocessing
                                  </div>
                                  <p className="text-xs">
                                    The following{' '}
                                    {preprocessingSummary.dropped_variables.length}{' '}
                                    variable(s) were dropped due to missing values or preprocessing rules:
                                  </p>
                                </div>
                              </div>

                              <ul className="list-disc list-inside text-xs space-y-0.5">
                                {preprocessingSummary.dropped_variables.map(
                                  (dropped: any, idx: number) => (
                                    <li key={idx}>{dropped.variable}</li>
                                  )
                                )}
                              </ul>

                              <p className="text-xs mt-3">
                                Model trained on{' '}
                                <strong>{preprocessingSummary.total_processed || 0}</strong>{' '}
                                variables (out of{' '}
                                <strong>
                                  {(preprocessingSummary.total_processed || 0) +
                                    (preprocessingSummary.total_dropped ??
                                      preprocessingSummary.dropped_variables.length ??
                                      0)}
                                </strong>{' '}
                                selected).
                              </p>
                            </div>
                          )}

                        <div className="mb-6 bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-slate-900 dark:to-slate-800 rounded-lg border-2 border-blue-200 dark:border-slate-700 shadow-md">
                          <div className="p-4">
                            <div className="flex items-center justify-between mb-2">
                              <div className="flex items-center space-x-2">
                                <div className="p-2 bg-blue-600 rounded-full">
                                  <Activity className="h-4 w-4 text-white" />
                                </div>
                                <div>
                                  <h5 className="font-semibold text-gray-900 dark:text-white">🔄 Data Preprocessing Summary</h5>
                                  <p className="text-xs text-gray-600 dark:text-gray-300">
                                    Training Mode: Segment Auto | Segment: {selectedSegmentFilter}
                                  </p>
                                </div>
                              </div>
                              <button
                                onClick={() => setPreprocessingSummaryExpanded(!preprocessingSummaryExpanded)}
                                className="text-blue-600 hover:text-blue-800 dark:text-blue-300 dark:hover:text-blue-200 transition-colors"
                              >
                                {preprocessingSummaryExpanded ? (
                                  <ChevronUp className="h-5 w-5" />
                                ) : (
                                  <ChevronDown className="h-5 w-5" />
                                )}
                              </button>
                            </div>
                            
                            {!preprocessingSummaryExpanded ? (
                              <div className="mt-2">
                                <p className="text-sm text-gray-700 dark:text-gray-200">
                                  📊 Summary: {preprocessingSummary.total_processed || 0} variables processed | {preprocessingSummary.total_dropped || 0} variables dropped
                                </p>
                                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">[▼ Expand Details]</p>
                              </div>
                            ) : (
                              <div className="mt-4">
                                {preprocessingSummary.is_already_preprocessed ? (
                                  <div className="bg-white dark:bg-slate-900/70 rounded-lg p-4 border border-green-200 dark:border-slate-700">
                                    <p className="text-sm text-green-800 dark:text-green-300 font-medium mb-2">✅ Data appears to be already preprocessed.</p>
                                    <ul className="text-xs text-gray-700 dark:text-gray-200 space-y-1">
                                      <li>✓ No missing values detected</li>
                                      <li>✓ No categorical variables found</li>
                                      <li>✓ All features are numeric and normalized</li>
                                      <li>✓ No constant variables detected</li>
                                    </ul>
                                    <p className="text-xs text-gray-600 dark:text-gray-300 mt-2">No additional preprocessing required.</p>
                                  </div>
                                ) : (
                                  <div className="bg-white dark:bg-slate-900/70 rounded-lg border border-gray-200 dark:border-slate-700 max-h-96 overflow-y-auto">
                                    <div className="p-4 space-y-4">
                                      {preprocessingSummary.variables?.map((variable: any, idx: number) => (
                                        <div key={idx} className="border-b border-gray-200 dark:border-slate-700 pb-4 last:border-b-0 last:pb-0">
                                          <h6 className="font-semibold text-gray-900 dark:text-white mb-2">VARIABLE: {variable.variable}</h6>
                                          
                                          {variable.missing_imputation && (
                                            <div className="ml-4 mb-2">
                                              <div className="flex items-start space-x-2">
                                                <span className="text-green-600">✓</span>
                                                <div>
                                                  <p className="text-sm font-medium text-gray-800 dark:text-gray-200">Missing Value Imputation</p>
                                                  <p className="text-xs text-gray-600 dark:text-gray-300">Reason: {variable.missing_imputation.reason}</p>
                                                  <p className="text-xs text-gray-500 dark:text-gray-400">Method: {variable.missing_imputation.method === 'median' ? `Median = ${variable.missing_imputation.value}` : `Mode = "${variable.missing_imputation.value}"`}</p>
                                                </div>
                                              </div>
                                            </div>
                                          )}
                                          
                                          {variable.encoding && (
                                            <div className="ml-4 mb-2">
                                              <div className="flex items-start space-x-2">
                                                <span className="text-green-600">✓</span>
                                                <div>
                                                  <p className="text-sm font-medium text-gray-800 dark:text-gray-200">Label Encoding Applied</p>
                                                  <p className="text-xs text-gray-600 dark:text-gray-300">Reason: {variable.encoding.reason}</p>
                                                  {variable.encoding.mapping_sample && (
                                                    <p className="text-xs text-gray-500 dark:text-gray-400">
                                                      Transformation: {Object.entries(variable.encoding.mapping_sample).slice(0, 3).map(([k, v]) => `"${k}"→${v}`).join(', ')}
                                                      {Object.keys(variable.encoding.mapping_sample).length > 3 ? '...' : ''}
                                                    </p>
                                                  )}
                                                </div>
                                              </div>
                                            </div>
                                          )}
                                          
                                          {variable.scaling && (
                                            <div className="ml-4 mb-2">
                                              <div className="flex items-start space-x-2">
                                                <span className="text-green-600">✓</span>
                                                <div>
                                                  <p className="text-sm font-medium text-gray-800 dark:text-gray-200">Standard Scaling Applied</p>
                                                  <p className="text-xs text-gray-600 dark:text-gray-300">Reason: {variable.scaling.reason}</p>
                                                  {variable.scaling.original_range && variable.scaling.scaled_range && (
                                                    <p className="text-xs text-gray-500 dark:text-gray-400">
                                                      Transformation: [{variable.scaling.original_range[0].toFixed(1)}, {variable.scaling.original_range[1].toFixed(1)}] → [{variable.scaling.scaled_range[0].toFixed(2)}, {variable.scaling.scaled_range[1].toFixed(2)}]
                                                    </p>
                                                  )}
                                                </div>
                                              </div>
                                            </div>
                                          )}
                                        </div>
                                      ))}
                                      
                                      {preprocessingSummary.dropped_variables?.map((dropped: any, idx: number) => (
                                        <div key={idx} className="border-b border-gray-200 dark:border-slate-700 pb-4 last:border-b-0 last:pb-0">
                                          <h6 className="font-semibold text-gray-900 dark:text-white mb-2">VARIABLE: {dropped.variable}</h6>
                                          <div className="ml-4">
                                            <div className="flex items-start space-x-2">
                                              <span className="text-red-600">✗</span>
                                              <div>
                                                <p className="text-sm font-medium text-red-800 dark:text-red-300">DROPPED</p>
                                                <p className="text-xs text-gray-600 dark:text-gray-300">Reason: {dropped.reason}</p>
                                                {dropped.details && (
                                                  <p className="text-xs text-gray-500 dark:text-gray-400">Details: {dropped.details}</p>
                                                )}
                                              </div>
                                            </div>
                                          </div>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                
                                <div className="mt-3 pt-3 border-t border-gray-200">
                                  <p className="text-sm text-gray-700">
                                    📊 Summary: {preprocessingSummary.total_processed || 0} variables processed | {preprocessingSummary.total_dropped || 0} variables dropped
                                  </p>
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    ) : null;
                  })()}

                  {/* Summary Stats */}
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
                    <div className="bg-purple-100 border border-purple-300 rounded-lg p-3">
                      <div className="text-xs text-purple-700">Segments Trained</div>
                      <div className="text-xl font-bold text-purple-900">
                        {segmentAutoTrainingResults.successful_segments} / {segmentAutoTrainingResults.total_segments}
                      </div>
                    </div>
                    <div className="bg-blue-100 border border-blue-300 rounded-lg p-3">
                      <div className="text-xs text-blue-700">Segment Column</div>
                      <div className="text-sm font-bold text-blue-900 truncate">
                        {segmentAutoTrainingResults.segment_column}
                      </div>
                    </div>
                    <div className="bg-green-100 border border-green-300 rounded-lg p-3">
                      <div className="text-xs text-green-700">Training Mode</div>
                      <div className="text-sm font-bold text-green-900">
                        Auto (AI-Selected)
                      </div>
                    </div>
                    <div className="bg-orange-100 border border-orange-300 rounded-lg p-3">
                      <div className="text-xs text-orange-700">Status</div>
                      <div className="text-sm font-bold text-orange-900">
                        ✓ Complete
                      </div>
                    </div>
                  </div>

                  {/* Segment Filter Dropdown */}
                  <div className="mb-4 bg-white border border-purple-200 rounded-lg p-4">
                    <div className="flex items-center justify-between">
                      <label className="text-sm font-medium text-gray-900 flex items-center space-x-2">
                        <Filter className="h-4 w-4 text-purple-600" />
                        <span>Filter by Segment:</span>
                      </label>
                      <select
                        value={selectedSegmentFilter}
                        onChange={(e) => setSelectedSegmentFilter(e.target.value)}
                        className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 bg-white"
                      >
                        <option value="all">📊 All Segments (Aggregated View)</option>
                        {segmentAutoTrainingResults.segments?.map((seg: string) => (
                          <option key={seg} value={seg}>
                            🎯 Segment: {seg}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="text-xs text-gray-600 mt-2">
                      {selectedSegmentFilter === 'all' 
                        ? 'Showing results for all segments' 
                        : `Showing results for segment: ${selectedSegmentFilter}`
                      }
                    </div>
                  </div>

                  {/* Segment Results Display */}
                  {selectedSegmentFilter === 'all' ? (
                    /* Aggregated View - Show summary for all segments */
                    <div className="space-y-3">
                      <h5 className="font-medium text-gray-900">Segment Overview</h5>
                      {segmentAutoTrainingResults.segments?.map((seg: string) => {
                        const segmentResult = segmentAutoTrainingResults.segment_results?.[`segment_${seg}`];
                        if (!segmentResult || segmentResult.error) {
                          return (
                            <div key={seg} className="bg-red-50 border border-red-200 rounded-lg p-3">
                              <div className="flex items-center justify-between">
                                <span className="text-sm font-medium text-red-900">Segment: {seg}</span>
                                <AlertCircle className="h-4 w-4 text-red-600" />
                              </div>
                              <p className="text-xs text-red-700 mt-1">
                                {segmentResult?.error || 'Training failed'}
                              </p>
                            </div>
                          );
                        }

                        const numModels = segmentResult.results?.length || 0;
                        const bestScore = segmentResult.results?.length > 0
                          ? Math.max(...segmentResult.results.map((r: any) =>
                              r.metrics?.f1 || r.metrics?.auc || r.metrics?.r2 || 0))
                          : 0;

                        return (
                          <div key={seg} className="bg-white border border-purple-200 rounded-lg p-4 hover:shadow-md transition-shadow">
                            <div className="flex items-center justify-between mb-2">
                              <div className="flex items-center space-x-2">
                                <div className="w-3 h-3 bg-purple-600 rounded-full"></div>
                                <span className="text-sm font-medium text-gray-900">Segment: {seg}</span>
                              </div>
                              <span className="text-xs bg-purple-100 text-purple-800 px-2 py-1 rounded">
                                {numModels} models trained
                              </span>
                            </div>
                            <div className="grid grid-cols-3 gap-2 text-xs">
                              <div>
                                <span className="text-gray-600">Best Score:</span>
                                <span className="ml-1 font-semibold text-gray-900">{bestScore.toFixed(4)}</span>
                              </div>
                              <div>
                                <span className="text-gray-600">Variables:</span>
                                <span className="ml-1 font-semibold text-gray-900">
                                  {segmentResult.used_features?.length || 0}
                                </span>
                              </div>
                              <div>
                                <span className="text-gray-600">Problem:</span>
                                <span className="ml-1 font-semibold text-gray-900 capitalize">
                                  {segmentResult.problem_type || 'N/A'}
                                </span>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    /* Specific Segment View - Show detailed results for selected segment */
                    <div className="space-y-3">
                      {(() => {
                        const segmentResult = segmentAutoTrainingResults.segment_results?.[`segment_${selectedSegmentFilter}`];
                        if (!segmentResult) {
                          return (
                            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-center">
                              <p className="text-sm text-gray-600">No results found for segment: {selectedSegmentFilter}</p>
                            </div>
                          );
                        }

                        if (segmentResult.error) {
                          return (
                            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                              <div className="flex items-center space-x-2 mb-2">
                                <AlertCircle className="h-4 w-4 text-red-600" />
                                <span className="text-sm font-medium text-red-900">Training Failed</span>
                              </div>
                              <p className="text-xs text-red-700">{segmentResult.error}</p>
                            </div>
                          );
                        }

                        const primaryMetric = segmentResult.problem_type === 'classification' ? 'f1' : 'r2';
                        const bestModelId = segmentResult.best_model_selection?.best_model_id;

                        return (
                          <>
                            <h5 className="font-medium text-gray-900">Models for Segment: {selectedSegmentFilter}</h5>
                            {segmentResult.results?.map((result: any, index: number) => {
                              const isBest = bestModelId === result.model_id;
                              const primaryScore = result?.metrics?.[primaryMetric] || 0;

                              return (
                                <div key={index} className={`rounded-lg p-4 ${isBest ? 'bg-green-50 border-2 border-green-300' : 'bg-white border border-purple-200'}`}>
                                  <div className="flex items-center justify-between mb-2">
                                    <div className="flex items-center space-x-2">
                                      {isBest && (
                                        <span className="text-xs bg-green-600 text-white px-2 py-1 rounded-full font-bold">⭐ BEST</span>
                                      )}
                                      <span className={`font-medium ${isBest ? 'text-green-900' : 'text-gray-900'}`}>{result.algorithm}</span>
                                    </div>
                                    <div className="text-right">
                                      <div className={`text-sm font-bold ${isBest ? 'text-green-900' : 'text-gray-900'}`}>
                                        {primaryMetric === 'f1' ? 'F1' : 'R²'}: {primaryScore.toFixed(4)}
                                      </div>
                                      <span className="text-xs bg-purple-100 text-purple-800 px-2 py-1 rounded">
                                        {result.model_id || `Model #${index + 1}`}
                                      </span>
                                    </div>
                                  </div>
                                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                                    {(() => {
                                      // Define base metrics to display (exclude train/test variants)
                                      const baseMetrics = trainingResults?.problem_type === 'regression'
                                        ? ['r2', 'adjusted_r2', 'mae', 'mse', 'rmse']
                                        : ['accuracy', 'auc', 'f1', 'precision', 'recall', 'log_loss', 'ks_statistic'];
                                      
                                      return baseMetrics.map((key) => {
                                        const value = result.metrics?.[key];
                                        if (value === undefined || value === null) return null;
                                        
                                        return (
                                          <div key={key} className="bg-gray-50 rounded p-2">
                                            <div className="text-gray-600 capitalize">{key}</div>
                                            <div className="font-semibold text-gray-900">
                                              {(() => {
                                                if (typeof value === 'number') {
                                                  return value.toFixed(4);
                                                }
                                                if (value === null || value === undefined) {
                                                  return 'N/A';
                                                }
                                                if (typeof value === 'object') {
                                                  return JSON.stringify(value);
                                                }
                                                return String(value);
                                              })()}
                                            </div>
                                          </div>
                                        );
                                      }).filter(Boolean);
                                    })()}
                                  </div>
                                </div>
                              );
                            })}

                            {/* Best Model Selected Section (hidden per product request) */}
                            {false && segmentResult.best_model_selection && (
                              <div className="mt-6 border-2 border-green-300 dark:border-slate-700 bg-gradient-to-br from-green-50 to-emerald-50 dark:from-slate-900 dark:to-slate-800 rounded-lg p-5 shadow-lg">
                                <div className="flex items-center space-x-3 mb-4">
                                  <div className="flex-shrink-0">
                                    <div className="w-12 h-12 bg-green-600 rounded-full flex items-center justify-center">
                                      <TrendingUp className="h-6 w-6 text-white" />
                                    </div>
                                  </div>
                                  <div className="flex-1">
                                    <h5 className="text-lg font-bold text-gray-900 dark:text-white">🏆 Best Model Selected</h5>
                                    <p className="text-sm text-gray-600 dark:text-gray-300">AI-powered model recommendation based on comprehensive performance analysis</p>
                                  </div>
                                </div>

                                <div className="bg-white dark:bg-slate-900/70 rounded-lg p-4 mb-4 border border-green-200 dark:border-slate-700">
                                  <div className="flex items-center justify-between mb-3">
                                    <div>
                                      <div className="text-2xl font-bold text-green-900 dark:text-white mb-1">
                                        {segmentResult.best_model_selection.best_algorithm}
                                      </div>
                                      <div className="text-xs text-gray-600 dark:text-gray-300">
                                        Model ID: {segmentResult.best_model_selection.best_model_id}
                                      </div>
                                    </div>
                                  </div>

                                  {/* Key Performance Metrics */}
                                  <div className="mb-4">
                                    <h6 className="text-sm font-semibold text-gray-900 dark:text-white mb-2">📊 Key Performance Metrics</h6>
                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                                      {(() => {
                                        if (!segmentResult.best_model_selection.best_model?.metrics) return null;
                                        
                                        // Define base metrics to display (exclude train/test variants)
                                        const baseMetrics = trainingResults?.problem_type === 'regression'
                                          ? ['r2', 'adjusted_r2', 'mae', 'mse', 'rmse']
                                          : ['accuracy', 'auc', 'f1', 'precision', 'recall', 'log_loss', 'ks_statistic'];
                                        
                                        const metrics = segmentResult.best_model_selection.best_model.metrics;
                                        
                                        return baseMetrics.slice(0, 4).map((key) => {
                                          const value = metrics[key];
                                          if (value === undefined || value === null) return null;
                                          
                                          return (
                                            <div key={key} className="bg-gray-50 dark:bg-slate-900/70 rounded-lg p-3 text-center border border-transparent dark:border-slate-700">
                                              <div className="text-xs text-gray-600 dark:text-gray-300 uppercase mb-1">{key}</div>
                                              <div className="text-lg font-bold text-gray-900 dark:text-white">
                                                {typeof value === 'number' ? value.toFixed(4) : (typeof value === 'object' ? JSON.stringify(value) : String(value || 'N/A'))}
                                              </div>
                                            </div>
                                          );
                                        }).filter(Boolean);
                                      })()}
                                    </div>
                                  </div>

                                  {/* Action Buttons */}
                                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                    <button
                                      onClick={() => {
                                        // Show training history (scroll to it)
                                        const historySection = document.querySelector('[data-training-history]');
                                        if (historySection) {
                                          historySection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                                        }
                                      }}
                                      className="px-4 py-3 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] hover:bg-blue-700 dark:hover:bg-[#333380] rounded-lg transition-colors flex items-center justify-center space-x-2 font-medium"
                                    >
                                      <Activity className="h-4 w-4" />
                                      <span>View Training History</span>
                                    </button>
                                    <button
                                      onClick={async () => {
                                        try {
                                          // Export the best model for this segment as ZIP (with pkl + json)
                                          const mainModelId = segmentAutoTrainingResults.model_id; // Main segment auto training ID
                                          const segmentId = selectedSegmentFilter; // Current segment ID
                                          const algorithm = segmentResult.best_model_selection.best_algorithm;
                                          const bestModelId = segmentResult.best_model_selection.best_model_id;
                                          
                                          console.log('🎯 Exporting segment model:', { mainModelId, segmentId });
                                          
                                          // Use window.location to construct the URL properly
                                          const apiUrl = window.location.origin + '/api/v1/export-segment-model/' + mainModelId + '/' + segmentId;
                                          
                                          const response = await fetch(apiUrl, {
                                            method: 'GET',
                                            credentials: 'include',
                                            headers: {
                                              ...buildMidasAuthHeaders(),
                                            },
                                          });

                                          if (!response.ok) {
                                            const errorText = await response.text();
                                            console.error('Export error response:', errorText);
                                            throw new Error('Failed to export model');
                                          }

                                          // Download as ZIP file
                                          const blob = await response.blob();
                                          const url = window.URL.createObjectURL(blob);
                                          const a = document.createElement('a');
                                          a.href = url;
                                          a.download = `${algorithm}_segment_${segmentId}_${bestModelId}.zip`;
                                          
                                          document.body.appendChild(a);
                                          a.click();
                                          window.URL.revokeObjectURL(url);
                                          document.body.removeChild(a);

                                          alert(`✅ Model exported successfully as ZIP!\n\n` +
                                                `Algorithm: ${algorithm}\n` +
                                                `Segment: ${segmentId}\n` +
                                                `Contains: Model (.pkl) + Results (.json)`);
                                        } catch (error) {
                                          console.error('❌ Export error:', error);
                                          alert('❌ Failed to export model. Please try again.');
                                        }
                                      }}
                                      className="px-4 py-3 bg-green-600 hover:bg-green-700 text-white rounded-lg transition-all flex items-center justify-center space-x-2 font-medium"
                                    >
                                      <Download className="h-4 w-4" />
                                      <span>Export Best Model</span>
                                    </button>
                                  </div>
                                </div>

                                {/* Model Comparison Ranking */}
                                {segmentResult.results && segmentResult.results.length > 1 && (
                                  <div className="bg-white dark:bg-slate-900/70 rounded-lg p-4 border border-green-200 dark:border-slate-700">
                                    <h6 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">📈 Model Comparison Ranking</h6>
                                    <div className="overflow-x-auto">
                                      <table className="w-full text-sm">
                                        <thead className={MTA_THEAD}>
                                          <tr>
                                            <th className="px-4 py-2 text-left font-semibold text-gray-700 dark:text-gray-200">Rank</th>
                                            <th className="px-4 py-2 text-left font-semibold text-gray-700 dark:text-gray-200">Algorithm</th>
                                            <th className="px-4 py-2 text-right font-semibold text-gray-700 dark:text-gray-200">Score</th>
                                            <th className="px-4 py-2 text-left font-semibold text-gray-700 dark:text-gray-200">Status</th>
                                          </tr>
                                        </thead>
                                        <tbody className="bg-white dark:bg-slate-950 divide-y divide-gray-200 dark:divide-slate-700">
                                          {[...segmentResult.results]
                                            .sort((a, b) => {
                                              const scoreA = a.metrics?.[primaryMetric] || 0;
                                              const scoreB = b.metrics?.[primaryMetric] || 0;
                                              return scoreB - scoreA;
                                            })
                                            .map((model: any, idx: number) => {
                                              const isBest = model.model_id === segmentResult.best_model_selection.best_model_id;
                                              const score = model.metrics?.[primaryMetric] || 0;

                                              return (
                                                <tr key={idx} className={isBest ? 'bg-green-50 dark:bg-slate-900/70' : idx % 2 === 0 ? 'bg-white dark:bg-slate-950' : 'bg-gray-50 dark:bg-slate-900/60'}>
                                                  <td className="px-4 py-3 font-medium text-gray-900 dark:text-white">
                                                    {isBest && <span className="mr-1">🏆</span>}
                                                    {idx + 1}
                                                  </td>
                                                  <td className="px-4 py-3 font-medium text-gray-900 dark:text-white">{model.algorithm}</td>
                                                  <td className="px-4 py-3 text-right font-bold text-gray-900 dark:text-white">
                                                    {score.toFixed(4)}
                                                  </td>
                                                  <td className="px-4 py-3">
                                                    {isBest ? (
                                                      <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-200">
                                                        ✓ Best Model
                                                      </span>
                                                    ) : (
                                                      <span className="text-xs text-gray-500 dark:text-gray-300">Alternative</span>
                                                    )}
                                                  </td>
                                                </tr>
                                              );
                                            })}
                                        </tbody>
                                      </table>
                                    </div>
                                  </div>
                                )}

                                {/* Why This Model */}
                                {segmentResult.best_model_selection.reasoning && (
                                  <div className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
                                    <h6 className="text-sm font-semibold text-gray-900 mb-2">💡 Why This Model?</h6>
                                    <p className="text-sm text-gray-700">{segmentResult.best_model_selection.reasoning}</p>
                                  </div>
                                )}
                              </div>
                            )}

                            {/* Training History Section for Segment (hidden; use Step 6 viz) */}
                            {false && segmentResult.best_model_selection?.best_model?.iteration_history && (
                              <div data-training-history className="mt-6 border-2 border-purple-300 bg-gradient-to-br from-purple-50 to-blue-50 rounded-lg p-5 shadow-lg">
                                <div className="flex items-center space-x-3 mb-4">
                                  <Activity className="h-5 w-5 text-purple-600" />
                                  <h5 className="text-lg font-bold text-gray-900">
                                    📈 Training History - {segmentResult.best_model_selection.best_algorithm}
                                  </h5>
                                </div>

                                <p className="text-sm text-gray-600 mb-4">
                                  Detailed iteration-by-iteration performance progression of the best model for this segment
                                </p>

                                {/* Iteration Chart */}
                                <div className="bg-white rounded-lg p-4 mb-4 border border-purple-200">
                                  <ResponsiveContainer width="100%" height={250}>
                                    <LineChart data={segmentResult.best_model_selection.best_model.iteration_history}>
                                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                                      <XAxis 
                                        dataKey="iteration" 
                                        stroke="#6b7280"
                                        label={{ value: 'Iteration', position: 'insideBottom', offset: -5 }}
                                      />
                                      <YAxis 
                                        stroke="#6b7280"
                                        label={{ value: 'Score', angle: -90, position: 'insideLeft' }}
                                      />
                                      <Tooltip 
                                        cursor={isDarkMode ? { fill: 'rgba(15, 23, 42, 0.4)' } : { fill: 'rgba(0, 0, 0, 0.05)' }}
                                        contentStyle={{ 
                                          backgroundColor: isDarkMode ? 'rgba(15, 23, 42, 0.95)' : 'rgba(255, 255, 255, 0.95)',
                                          border: isDarkMode ? '1px solid #334155' : '1px solid #e5e7eb',
                                          borderRadius: '8px',
                                          padding: '8px',
                                          color: isDarkMode ? '#e2e8f0' : '#111827'
                                        }}
                                        labelStyle={{ color: isDarkMode ? '#e2e8f0' : '#111827' }}
                                        itemStyle={{ color: isDarkMode ? '#e2e8f0' : '#111827' }}
                                      />
                                      <Line 
                                        type="monotone" 
                                        dataKey={segmentResult.problem_type === 'classification' ? 'metrics.auc' : 'metrics.r2'}
                                        stroke="#9333ea" 
                                        strokeWidth={3}
                                        dot={{ fill: '#9333ea', r: 5 }}
                                        activeDot={{ r: 7 }}
                                        name={segmentResult.problem_type === 'classification' ? 'AUC-ROC' : 'R²'}
                                      />
                                    </LineChart>
                                  </ResponsiveContainer>
                                </div>

                                {/* Iteration Details Table */}
                                <div className="border border-purple-200 rounded-lg overflow-hidden">
                                  <div className="overflow-x-auto max-h-96">
                                    <table className="w-full text-sm">
                                      <thead className={`${MTA_THEAD} sticky top-0`}>
                                        <tr>
                                          <th className="px-4 py-3 text-left font-semibold text-gray-700 dark:text-gray-200">Iteration</th>
                                          <th className="px-4 py-3 text-right font-semibold text-gray-700 dark:text-gray-200">
                                            {segmentResult.problem_type === 'classification' ? 'AUC-ROC' : 'R²'}
                                          </th>
                                          {segmentResult.problem_type === 'classification' ? (
                                            <>
                                              <th className="px-4 py-3 text-right font-semibold text-gray-700 dark:text-gray-200">F1-Score</th>
                                              <th className="px-4 py-3 text-right font-semibold text-gray-700 dark:text-gray-200">Precision</th>
                                              <th className="px-4 py-3 text-right font-semibold text-gray-700 dark:text-gray-200">Recall</th>
                                              <th className="px-4 py-3 text-right font-semibold text-gray-700 dark:text-gray-200">Accuracy</th>
                                            </>
                                          ) : (
                                            <>
                                              <th className="px-4 py-3 text-right font-semibold text-gray-700 dark:text-gray-200">RMSE</th>
                                              <th className="px-4 py-3 text-right font-semibold text-gray-700 dark:text-gray-200">MAE</th>
                                              <th className="px-4 py-3 text-right font-semibold text-gray-700 dark:text-gray-200">MSE</th>
                                            </>
                                          )}
                                          {segmentResult.problem_type === 'classification' && (
                                            <th className="px-4 py-3 text-right font-semibold text-gray-700 dark:text-gray-200">Log Loss</th>
                                          )}
                                          <th className="px-4 py-3 text-left font-semibold text-gray-700 dark:text-gray-200">Hyperparameters</th>
                                          <th className="px-4 py-3 text-right font-semibold text-gray-700 dark:text-gray-200">Improvement</th>
                                          <th className="px-4 py-3 text-left font-semibold text-gray-700 dark:text-gray-200">Status</th>
                                        </tr>
                                      </thead>
                                      <tbody className="bg-white dark:bg-slate-950 divide-y divide-gray-200 dark:divide-slate-700">
                                        {(() => {
                                          const hist = segmentResult.best_model_selection.best_model.iteration_history;
                                          const soleBestIdx = getSoleBestIterationIndexForDisplay(hist);
                                          const formatHpCellSeg = (hp: any) => {
                                            if (hp == null) return 'N/A';
                                            if (typeof hp === 'object') {
                                              const formatted = Object.entries(hp)
                                                .map(([k, v]) => `${k}:${v}`)
                                                .join(', ');
                                              return formatted.length > 50 ? `${formatted.slice(0, 47)}...` : formatted;
                                            }
                                            return String(hp);
                                          };
                                          return hist.map((iter: any, idx: number) => {
                                          const isBestIteration = soleBestIdx !== null && idx === soleBestIdx;
                                          const llSeg =
                                            iter.metrics?.log_loss ??
                                            iter.metrics?.test_log_loss;
                                          return (
                                            <tr
                                              key={idx}
                                              className={`transition-colors hover:bg-gray-50 dark:hover:bg-slate-700/95 ${
                                                isBestIteration
                                                  ? 'bg-green-50 dark:bg-slate-900/70'
                                                  : idx % 2 === 0
                                                    ? 'bg-white dark:bg-slate-950'
                                                    : 'bg-gray-50 dark:bg-slate-900/60'
                                              }`}
                                            >
                                              <td className="px-4 py-3 font-medium text-gray-900 dark:text-white">{iter.iteration}</td>
                                              <td className="px-4 py-3 text-right font-medium text-gray-900 dark:text-white">
                                                {iter.metrics?.[segmentResult.problem_type === 'classification' ? 'auc' : 'r2']?.toFixed(4) || 
                                                 iter.score?.toFixed(4) || 'N/A'}
                                              </td>
                                              {segmentResult.problem_type === 'classification' ? (
                                                <>
                                                  <td className="px-4 py-3 text-right text-gray-700 dark:text-gray-200">
                                                    {iter.metrics?.f1?.toFixed(4) || 'N/A'}
                                                  </td>
                                                  <td className="px-4 py-3 text-right text-gray-700 dark:text-gray-200">
                                                    {iter.metrics?.precision?.toFixed(4) || 'N/A'}
                                                  </td>
                                                  <td className="px-4 py-3 text-right text-gray-700 dark:text-gray-200">
                                                    {iter.metrics?.recall?.toFixed(4) || 'N/A'}
                                                  </td>
                                                  <td className="px-4 py-3 text-right text-gray-700 dark:text-gray-200">
                                                    {iter.metrics?.test_accuracy?.toFixed(4) || iter.metrics?.accuracy?.toFixed(4) || 'N/A'}
                                                  </td>
                                                  <td className="px-4 py-3 text-right text-gray-700 dark:text-gray-200">
                                                    {typeof llSeg === 'number' && Number.isFinite(llSeg) ? llSeg.toFixed(4) : 'N/A'}
                                                  </td>
                                                </>
                                              ) : (
                                                <>
                                                  <td className="px-4 py-3 text-right text-gray-700 dark:text-gray-200">
                                                    {iter.metrics?.rmse?.toFixed(4) || 'N/A'}
                                                  </td>
                                                  <td className="px-4 py-3 text-right text-gray-700 dark:text-gray-200">
                                                    {iter.metrics?.mae?.toFixed(4) || 'N/A'}
                                                  </td>
                                                  <td className="px-4 py-3 text-right text-gray-700 dark:text-gray-200">
                                                    {iter.metrics?.mse?.toFixed(4) || 'N/A'}
                                                  </td>
                                                </>
                                              )}
                                              <td className="px-4 py-3 text-sm text-gray-900 dark:text-slate-100">
                                                <div
                                                  className="font-mono text-xs bg-gray-50 dark:bg-slate-800 p-2 rounded max-w-xs truncate"
                                                  title={formatHpCellSeg(iter.hyperparameters)}
                                                >
                                                  {formatHpCellSeg(iter.hyperparameters)}
                                                </div>
                                              </td>
                                              <td className={`px-4 py-3 text-right font-medium ${
                                                iter.improvement > 0 ? 'text-green-600' : 
                                                iter.improvement < 0 ? 'text-red-600' : 
                                                'text-gray-500'
                                              }`}>
                                                {iter.improvement > 0 && '+'}
                                                {iter.improvement?.toFixed(4) || '0.0000'}
                                              </td>
                                              <td className="px-4 py-3">
                                                {isBestIteration ? (
                                                  <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-200">
                                                    ⭐ Best
                                                  </span>
                                                ) : (
                                                  <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200">
                                                    Completed
                                                  </span>
                                                )}
                                              </td>
                                            </tr>
                                          );
                                        });
                                        })()}
                                      </tbody>
                                    </table>
                                  </div>
                                </div>

                                {/* Hyperparameters */}
                                {segmentResult.best_model_selection.best_model.hyperparameters && (
                                  <div className="mt-4 p-4 bg-white rounded-lg border border-purple-200">
                                    <div className="flex items-center justify-between mb-2">
                                      <h6 className="text-sm font-semibold text-gray-900">⚙️ Optimized Hyperparameters</h6>
                                      {segmentResult.best_model_selection.best_model.optimization_method && (
                                        <span className="text-xs px-2 py-1 rounded-full bg-purple-100 text-purple-700 font-medium">
                                          {segmentResult.best_model_selection.best_model.optimization_method === 'bayesian_optimization' ? '🧠 Bayesian Optimization' :
                                           segmentResult.best_model_selection.best_model.optimization_method === 'random_search' ? '🎲 Random Search' :
                                           '⚙️ Default'}
                                        </span>
                                      )}
                                    </div>
                                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                                      {Object.entries(segmentResult.best_model_selection.best_model.hyperparameters)
                                        .filter(([key]) => !['random_state', 'verbose', 'n_jobs'].includes(key))
                                        .slice(0, 8)
                                        .map(([key, value]: [string, any]) => (
                                          <div key={key} className="bg-purple-50 rounded-lg p-3 border border-purple-200">
                                            <div className="text-xs text-gray-600 mb-1">{key.replace(/_/g, ' ')}</div>
                                            <div className="text-sm font-bold text-gray-900">
                                              {typeof value === 'number' 
                                                ? (Number.isInteger(value) ? value : value.toFixed(4))
                                                : String(value)}
                                            </div>
                                          </div>
                                        ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                            )}
                          </>
                        );
                      })()}
                    </div>
                  )}

                  <div className="mt-4 p-3 bg-purple-50 dark:bg-slate-900/70 border border-purple-200 dark:border-slate-700 rounded-lg">
                    <p className="text-xs text-purple-700 dark:text-purple-300">
                      💡 Each segment was analyzed independently with automatic variable selection and algorithm optimization.
                      Use the segment filter above to view detailed results for specific segments.
                    </p>
                  </div>
                </div>
              )}

              <MtaPreStep6TrainingViz
                viz={mtaPreStep6VizResults}
                isDarkMode={isDarkMode}
                targetMetricManual={targetMetricManual}
                selectedAlgorithmForHistory={selectedAlgorithmForHistory}
                setSelectedAlgorithmForHistory={setSelectedAlgorithmForHistory}
                selectedSegmentForHistory={selectedSegmentForHistory}
                setSelectedSegmentForHistory={setSelectedSegmentForHistory}
                comparisonTab={comparisonTab}
                setComparisonTab={setComparisonTab}
                comparisonAlgorithmFilter={comparisonAlgorithmFilter}
                setComparisonAlgorithmFilter={setComparisonAlgorithmFilter}
                comparisonSegmentFilter={comparisonSegmentFilter}
                setComparisonSegmentFilter={setComparisonSegmentFilter}
                selectedAlgorithmsForComparison={selectedAlgorithmsForComparison}
                setSelectedAlgorithmsForComparison={setSelectedAlgorithmsForComparison}
                getAvailableMetrics={getAvailableMetrics}
                getScoreComparisonData={getScoreComparisonData}
                getTrainingHistoryData={getTrainingHistoryData}
                getSelectedAlgorithms={getSelectedAlgorithms}
                getPrimaryMetricKey={getPrimaryMetricKey}
                getMetricDisplayName={getMetricDisplayName}
                getBestScoreFromHistory={getBestScoreFromHistory}
              />

              {(() => {
                const results = segmentAutoTrainingResults || autoTrainingResults;
                const step6Views = getStep6ViewsForDisplay(results);
                if (!step6Views) return null;

                const baseRows = Array.isArray(step6Views.base_model_results) ? step6Views.base_model_results : [];
                const bayesianRows = Array.isArray(step6Views.bayesian_summary) ? step6Views.bayesian_summary : [];
                const rec = step6Views.recommendations || {};
                const g1Rows = Array.isArray(rec.g1_overfit_aware) ? rec.g1_overfit_aware : [];
                const g2Rows = Array.isArray(rec.g2_test_only) ? rec.g2_test_only : [];
                const lrRows = Array.isArray(rec.lr_sign_validation) ? rec.lr_sign_validation : [];
                const lrBackwardReport = step6Views?.lr_backward_elimination_report;
                const displayLrBackwardReport = step6LrInteractiveReport ?? lrBackwardReport;

                const hasData =
                  baseRows.length > 0 ||
                  bayesianRows.length > 0 ||
                  g1Rows.length > 0 ||
                  g2Rows.length > 0 ||
                  lrRows.length > 0 ||
                  !!lrBackwardReport;
                if (!hasData) return null;

                return (
                  <div className={`mt-6 ${MTA_SECTION} p-5 md:p-6 bg-gradient-to-br from-blue-50/90 via-white to-indigo-50/50 dark:from-slate-900 dark:via-slate-900 dark:to-slate-800`}>
                    <div className="flex flex-wrap items-center gap-3 mb-4">
                      <span className={MTA_STEP_NUM} title="Step 6">
                        6
                      </span>
                      <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-blue-500/15 dark:bg-blue-500/20 ring-1 ring-blue-300/50">
                        <BarChart3 className="h-6 w-6 text-blue-700 dark:text-blue-200" />
                      </div>
                      <h4 className={MTA_TITLE_SECTION}>Training insights</h4>
                    </div>


                    {baseRows.length > 0 && (
                      <div className="mb-5">
                        <div className="flex items-center justify-between mb-1">
                          <div className="text-sm font-semibold text-gray-900 dark:text-white">Iteration 0: Base models (default hyperparameters)</div>
                          <div className="text-[11px] font-medium px-2 py-1 rounded-full bg-blue-50 text-blue-700 border border-blue-100 dark:bg-blue-900/30 dark:text-blue-200 dark:border-blue-800">
                            {baseRows.length} base models
                          </div>
                        </div>
                        
                        <div className={`overflow-x-auto ${MTA_TABLE_SHELL}`}>
                          <table className="w-full min-w-[980px] table-fixed text-xs">
                            <thead className={MTA_THEAD}>
                              <tr>
                                <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">ALGORITHM</th>
                                <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">AUC (TR)</th>
                                <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">AUC (TE)</th>
                                <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">KS (TR)</th>
                                <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">KS (TE)</th>
                                <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">GINI (TR)</th>
                                <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">GINI (TE)</th>
                                <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">OVERFIT</th>
                                <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">NON-ZERO</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-200 dark:divide-slate-700">
                              {baseRows.slice(0, 20).map((row: any, idx: number) => {
                                const baseMetrics = row?.base_metrics || {};
                                const recRow = g2Rows.find((r: any) =>
                                  String(r?.model_id || '') === String(row?.model_id || '') ||
                                  (
                                    String(r?.algorithm || '').toLowerCase() === String(row?.algorithm || '').toLowerCase() &&
                                    String(r?.segment_id || '') === String(row?.segment_id || '')
                                  )
                                ) || {};
                                const aucTr = getFirstFiniteMetric(baseMetrics, ['train_auc', 'auc']) ?? getFirstFiniteMetric(recRow, ['train_score']);
                                const aucTe = getFirstFiniteMetric(baseMetrics, ['test_auc', 'auc']) ?? getFirstFiniteMetric(recRow, ['score']) ?? getFirstFiniteMetric(row, ['base_score']);
                                const ksTr = getFirstFiniteMetric(baseMetrics, ['train_ks_statistic', 'ks_statistic']);
                                const ksTe = getFirstFiniteMetric(baseMetrics, ['test_ks_statistic', 'ks_statistic']);
                                const giniTr = getFirstFiniteMetric(baseMetrics, ['train_gini']) ?? (aucTr !== null ? (2 * aucTr - 1) : null);
                                const giniTe = getFirstFiniteMetric(baseMetrics, ['test_gini']) ?? (aucTe !== null ? (2 * aucTe - 1) : null);
                                const overfitPct = getFirstFiniteMetric(baseMetrics, ['overfit_pct']) ?? calcStep6OverfitPct(aucTr, aucTe);
                                const bundleUF = resolveTrainingBundleUsedFeatures(results, row?.segment_id);
                                const totalFeat =
                                  getFirstFiniteMetric(baseMetrics, ['feature_count']) ??
                                  getFirstFiniteMetric(recRow, ['feature_count']) ??
                                  (Array.isArray(bundleUF) ? bundleUF.length : null);
                                const nzFeat =
                                  resolveNonzeroFeatureCount(
                                    { ...row, used_features: row.used_features ?? bundleUF },
                                    { ...baseMetrics, ...(recRow && typeof recRow === 'object' ? recRow : {}) },
                                    bundleUF,
                                  ) ??
                                  getFirstFiniteMetric(baseMetrics, ['feature_importance_count']) ??
                                  getFirstFiniteMetric(recRow, ['feature_importance_count']);
                                const nonZeroLabel = formatStep6NonZeroRatio(nzFeat, totalFeat);

                                return (
                                  <tr key={`base_auto_${idx}`} className="bg-white dark:bg-slate-950 hover:bg-gray-50 dark:hover:bg-slate-900/70">
                                    <td className="px-3 py-2.5 text-gray-900 dark:text-white whitespace-nowrap">{String(row.algorithm || '-')}</td>
                                    <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{formatStep6Number(aucTr)}</td>
                                    <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{formatStep6Number(aucTe)}</td>
                                    <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{formatStep6Number(ksTr, 3)}</td>
                                    <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{formatStep6Number(ksTe, 3)}</td>
                                    <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{formatStep6Number(giniTr, 3)}</td>
                                    <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{formatStep6Number(giniTe, 3)}</td>
                                    <td className={`px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap ${overfitPct !== null && overfitPct <= 10 ? 'text-green-700 dark:text-green-400 font-semibold' : ''}`}>
                                      {overfitPct !== null ? `${overfitPct.toFixed(2)}%` : 'N/A'}
                                    </td>
                                    <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{nonZeroLabel}</td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {baseRows.length > 0 && (
                      <Step6PipelineForkLrSection
                        pipelinePath={step6PipelinePath}
                        onPipelinePathChange={setStep6PipelinePath}
                        onRunLrElimination={() =>
                          runStep6InteractiveLrElimination({
                            results,
                            segmentId:
                              trainingMode === 'segment-specific' && selectedSegmentFilter !== 'all'
                                ? selectedSegmentFilter
                                : undefined,
                          })
                        }
                        lrReport={displayLrBackwardReport}
                        trainingLrConfig={results?.training_configuration?.lr_backward_elimination}
                        startingFeatureCount={Array.isArray(results?.used_features) ? results.used_features.length : null}
                        liveLoading={step6LrInteractiveLoading}
                        liveError={step6LrInteractiveError}
                      />
                    )}

                    {bayesianRows.length > 0 && (
                      <div className="mb-5 border border-blue-200 dark:border-slate-700 rounded-lg p-4 bg-white dark:bg-slate-900/60">
                        <div className="flex items-center justify-between mb-1">
                          <div className="text-sm font-semibold text-gray-900 dark:text-white">Bayesian optimization summary (Optuna)</div>
                          <span className="text-[11px] px-2 py-1 rounded-full bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300 font-medium">Completed</span>
                        </div>
                        <div className="text-xs text-gray-600 dark:text-gray-300 mb-3">
                          Objective: max {String(bayesianRows[0]?.target_metric || 'AUC').toUpperCase()}. {bayesianRows[0]?.cv_folds ?? '-'} folds per algorithm.
                          {typeof bayesianRows[0]?.early_stopping_rounds === 'number' ? ` Early stopping: ${bayesianRows[0]?.early_stopping_rounds} rounds.` : ''}
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                          {bayesianRows.slice(0, 3).map((row: any, idx: number) => (
                            <div key={`bayes_card_auto_${idx}`} className="border border-gray-200 dark:border-slate-700 rounded-lg p-3 bg-gray-50 dark:bg-slate-900/80">
                              <div className="text-[10px] uppercase tracking-wide text-gray-500 dark:text-gray-400">{String(row.algorithm || '-')} trials</div>
                              <div className="text-2xl font-semibold text-gray-900 dark:text-white">{row.trials_run ?? 0}</div>
                              <div className="text-[11px] text-gray-500 dark:text-gray-400">
                                {typeof row.configured_trials === 'number' && row.configured_trials > 0 && row.trials_run === row.configured_trials ? 'full budget' : `${row.configured_trials ?? 0} configured`}
                              </div>
                            </div>
                          ))}
                          <div className="border border-green-300 dark:border-emerald-700 rounded-lg p-3 bg-green-50 dark:bg-emerald-950/40">
                            <div className="text-[10px] uppercase tracking-wide text-gray-500 dark:text-gray-400">Best test {String(bayesianRows[0]?.target_metric || 'AUC').toUpperCase()}</div>
                            <div className="text-2xl font-semibold text-green-700 dark:text-green-400">
                              {formatStep6Number(
                                bayesianRows.reduce((acc: number, r: any) => {
                                  const v = Number(r?.best_score);
                                  return Number.isFinite(v) ? Math.max(acc, v) : acc;
                                }, -Infinity)
                              )}
                            </div>
                            <div className="text-[11px] text-gray-500 dark:text-gray-400">
                              {(() => {
                                const bestRow = bayesianRows.reduce((acc: any, r: any) => {
                                  const v = Number(r?.best_score);
                                  if (!Number.isFinite(v)) return acc;
                                  if (!acc || v > Number(acc.best_score)) return r;
                                  return acc;
                                }, null);
                                if (!bestRow) return '-';
                                return `${String(bestRow.algorithm || '-')} #${bestRow.best_iteration ?? '-'}`;
                              })()}
                            </div>
                          </div>
                        </div>
                      </div>
                    )}

                    {(g1Rows.length > 0 || g2Rows.length > 0) && (
                      <div className="mb-5 border border-blue-200 dark:border-slate-700 rounded-lg p-4 bg-white dark:bg-slate-900/60">
                        <div className="text-sm font-semibold text-gray-900 dark:text-white mb-1">Model recommendations (max 2 per algorithm)</div>
                        <div className="text-xs text-gray-600 dark:text-gray-300 mb-3">G1: best test score with overfit &lt;= 10%. G2: best test score regardless.</div>
                        {(() => {
                          const modelLookup = new Map<string, any>();
                          const sourceRows: any[] = [];
                          if (Array.isArray(results?.results)) {
                            sourceRows.push(...results.results);
                          }
                          if (results?.segment_results && typeof results.segment_results === 'object') {
                            Object.entries(results.segment_results).forEach(([segmentKey, segPayload]: [string, any]) => {
                              const segmentId = String(segmentKey || '').replace('segment_', '');
                              (segPayload?.results || []).forEach((r: any) => sourceRows.push({ ...r, segment_id: segmentId }));
                            });
                          }
                          sourceRows.forEach((r: any) => {
                            const key = `${String(r?.model_id || '')}__${String(r?.segment_id || '')}`;
                            modelLookup.set(key, r);
                          });

                          const allRows = [
                            ...g1Rows.map((r: any) => ({ ...r, guideline: 'G1' })),
                            ...g2Rows.map((r: any) => ({ ...r, guideline: 'G2' })),
                          ];

                          const grouped = new Map<string, any[]>();
                          allRows.forEach((row: any) => {
                            const key = `${String(row.algorithm || '').toLowerCase()}__${String(row.segment_id || '')}`;
                            const arr = grouped.get(key) || [];
                            arr.push(row);
                            grouped.set(key, arr);
                          });

                          const recRows: any[] = [];
                          grouped.forEach((rows) => {
                            const sorted = [...rows].sort((a, b) => {
                              const g = String(a.guideline).localeCompare(String(b.guideline));
                              if (g !== 0) return g;
                              return (Number(b.score) || -Infinity) - (Number(a.score) || -Infinity);
                            });
                            recRows.push(...sorted.slice(0, 2));
                          });

                          if (recRows.length === 0) return null;

                          return (
                            <div className={`overflow-x-auto ${MTA_TABLE_SHELL}`}>
                              <table className="w-full min-w-[980px] table-fixed text-xs">
                                <thead className={MTA_THEAD}>
                                  <tr>
                                    <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">ALGORITHM</th>
                                    <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">GUIDELINE</th>
                                    <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">AUC (TR)</th>
                                    <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">AUC (TE)</th>
                                    <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">KS (TR)</th>
                                    <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">KS (TE)</th>
                                    <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">GINI (TR)</th>
                                    <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">GINI (TE)</th>
                                    <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">OVERFIT</th>
                                    <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">FEAT.</th>
                                    <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">FLAGS</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-200 dark:divide-slate-700">
                                  {recRows.map((row: any, idx: number) => {
                                    const model = modelLookup.get(`${String(row?.model_id || '')}__${String(row?.segment_id || '')}`) || {};
                                    const metrics = model?.metrics || {};
                                    const aucTr = getFirstFiniteMetric(metrics, ['train_auc']) ?? getFirstFiniteMetric(row, ['train_score']);
                                    const aucTe = getFirstFiniteMetric(metrics, ['test_auc', 'auc']) ?? getFirstFiniteMetric(row, ['score']);
                                    const ksTr = getFirstFiniteMetric(metrics, ['train_ks_statistic', 'ks_statistic']);
                                    const ksTe = getFirstFiniteMetric(metrics, ['test_ks_statistic', 'ks_statistic']);
                                    const giniTr = getFirstFiniteMetric(metrics, ['train_gini']) ?? (aucTr !== null ? (2 * aucTr - 1) : null);
                                    const giniTe = getFirstFiniteMetric(metrics, ['test_gini']) ?? (aucTe !== null ? (2 * aucTe - 1) : null);
                                    const overfitPct = getFirstFiniteMetric(row, ['overfit_pct']) ?? getFirstFiniteMetric(metrics, ['overfit_pct']) ?? calcStep6OverfitPct(aucTr, aucTe);
                                    const bundleUF = resolveTrainingBundleUsedFeatures(results, row?.segment_id);
                                    const totalFeat =
                                      getFirstFiniteMetric(metrics, ['feature_count']) ??
                                      getFirstFiniteMetric(row, ['feature_count']) ??
                                      (Array.isArray(model?.used_features) ? model.used_features.length : null) ??
                                      (Array.isArray(bundleUF) ? bundleUF.length : null);
                                    const nzFeat =
                                      resolveNonzeroFeatureCount(model, { ...metrics, ...row }, bundleUF) ??
                                      getFirstFiniteMetric(metrics, ['feature_importance_count']) ??
                                      getFirstFiniteMetric(row, ['feature_importance_count']);
                                    const featDisplay = formatStep6NonZeroRatio(nzFeat, totalFeat);
                                    const flags = row?.is_recommended
                                      ? 'Best overall'
                                      : (overfitPct !== null && overfitPct > 10 ? 'Overfit >10%' : (String(row.algorithm || '').toLowerCase().includes('logistic') ? 'Post-elim' : '-'));

                                    return (
                                      <tr key={`rec_auto_${idx}`} className={row.guideline === 'G1' ? 'bg-green-50 dark:bg-emerald-950/40 hover:bg-green-100/80 dark:hover:bg-emerald-950/55' : 'bg-white dark:bg-slate-950 hover:bg-gray-50 dark:hover:bg-slate-900/70'}>
                                        <td className="px-3 py-2.5 text-gray-900 dark:text-white whitespace-nowrap">{String(row.algorithm || '-')}</td>
                                        <td className="px-3 py-2.5 whitespace-nowrap">
                                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${row.guideline === 'G1' ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300' : 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-200'}`}>
                                            {row.guideline}
                                          </span>
                                        </td>
                                        <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{formatStep6Number(aucTr, 3)}</td>
                                        <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{formatStep6Number(aucTe, 3)}</td>
                                        <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{formatStep6Number(ksTr, 3)}</td>
                                        <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{formatStep6Number(ksTe, 3)}</td>
                                        <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{formatStep6Number(giniTr, 3)}</td>
                                        <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{formatStep6Number(giniTe, 3)}</td>
                                        <td className={`px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap ${overfitPct !== null && overfitPct <= 10 ? 'text-green-700 dark:text-green-400 font-semibold' : ''}`}>
                                          {overfitPct !== null ? `${overfitPct.toFixed(2)}%` : 'N/A'}
                                        </td>
                                        <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{featDisplay}</td>
                                        <td className="px-3 py-2.5 whitespace-nowrap">
                                          <span className="px-1.5 py-0.5 rounded text-[10px] bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-200">{flags}</span>
                                        </td>
                                      </tr>
                                    );
                                  })}
                                </tbody>
                              </table>
                            </div>
                          );
                        })()}
                      </div>
                    )}

                    {(g1Rows.length > 0 || g2Rows.length > 0) && (
                      <CrossAlgorithmRecommendationCard
                        datasetId={activeDatasetId ?? null}
                        problemType={String(results?.problem_type || 'classification')}
                        results={results}
                        g1Rows={g1Rows}
                        g2Rows={g2Rows}
                        lrRows={lrRows}
                        variant="auto"
                      />
                    )}

                    {lrRows.length > 0 && (
                      <div>
                        <div className="text-sm font-medium text-gray-800 dark:text-gray-200 mb-2">LR Sign Validation</div>
                        <div className={`overflow-x-auto ${MTA_TABLE_SHELL}`}>
                          <table className="w-full min-w-[980px] table-fixed text-xs">
                            <thead className={MTA_THEAD}>
                              <tr>
                                <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">Algorithm</th>
                                <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">Segment</th>
                                <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">Status</th>
                                <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">Matched</th>
                                <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">Mismatched</th>
                                <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">Unknown</th>
                                <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">Details</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-200 dark:divide-slate-700">
                              {lrRows.slice(0, 20).map((row: any, idx: number) => {
                                const rowKey = `${row.model_id || idx}_${row.segment_id || 'all'}_auto`;
                                const hasDetails = Array.isArray(row.details) && row.details.length > 0;
                                const isOpen = !!expandedLrSignRows[rowKey];

                                return (
                                  <React.Fragment key={`lr_auto_${rowKey}`}>
                                    <tr className="bg-white dark:bg-slate-950 hover:bg-gray-50 dark:hover:bg-slate-900/70">
                                      <td className="px-3 py-2.5 text-gray-900 dark:text-white whitespace-nowrap">{String(row.algorithm || '-').toUpperCase()}</td>
                                      <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{row.segment_id || '-'}</td>
                                      <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{row.status || '-'}</td>
                                      <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{row.matched_count ?? '-'}</td>
                                      <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{row.mismatched_count ?? '-'}</td>
                                      <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{row.unknown_count ?? '-'}</td>
                                      <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">
                                        {hasDetails ? (
                                          <button
                                            type="button"
                                            onClick={() => setExpandedLrSignRows((prev) => ({ ...prev, [rowKey]: !prev[rowKey] }))}
                                            className="inline-flex items-center space-x-1 text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
                                          >
                                            <span>{isOpen ? 'Hide' : 'View'}</span>
                                            {isOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                                          </button>
                                        ) : (
                                          <span className="text-gray-400 dark:text-gray-500">-</span>
                                        )}
                                      </td>
                                    </tr>
                                    {isOpen && hasDetails && (
                                      <tr className="bg-gray-50 dark:bg-slate-900/80">
                                        <td className="px-3 py-2.5" colSpan={7}>
                                          <div className="overflow-x-auto rounded border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-950">
                                            <table className="w-full min-w-[640px] table-fixed text-xs">
                                              <thead className={MTA_THEAD}>
                                                <tr>
                                                  <th className="px-3 py-2 text-left font-semibold whitespace-nowrap">Feature</th>
                                                  <th className="px-3 py-2 text-left font-semibold whitespace-nowrap">Coeff</th>
                                                  <th className="px-3 py-2 text-left font-semibold whitespace-nowrap">Coeff Sign</th>
                                                  <th className="px-3 py-2 text-left font-semibold whitespace-nowrap">Bivariate Corr</th>
                                                  <th className="px-3 py-2 text-left font-semibold whitespace-nowrap">Corr Sign</th>
                                                  <th className="px-3 py-2 text-left font-semibold whitespace-nowrap">Status</th>
                                                </tr>
                                              </thead>
                                              <tbody className="divide-y divide-gray-200 dark:divide-slate-700">
                                                {row.details.slice(0, 30).map((d: any, didx: number) => (
                                                  <tr key={`${rowKey}_d_${didx}`} className="bg-white dark:bg-slate-950 hover:bg-gray-50 dark:hover:bg-slate-900/70">
                                                    <td className="px-3 py-2 text-gray-900 dark:text-white whitespace-nowrap">{d.feature || '-'}</td>
                                                    <td className="px-3 py-2 text-gray-700 dark:text-gray-200 whitespace-nowrap">{formatStep6Number(d.coefficient, 6)}</td>
                                                    <td className="px-3 py-2 text-gray-700 dark:text-gray-200 whitespace-nowrap">{d.coefficient_sign ?? '-'}</td>
                                                    <td className="px-3 py-2 text-gray-700 dark:text-gray-200 whitespace-nowrap">{formatStep6Number(d.bivariate_correlation, 6)}</td>
                                                    <td className="px-3 py-2 text-gray-700 dark:text-gray-200 whitespace-nowrap">{d.bivariate_sign ?? '-'}</td>
                                                    <td className="px-3 py-2 text-gray-700 dark:text-gray-200 whitespace-nowrap">{d.status || '-'}</td>
                                                  </tr>
                                                ))}
                                              </tbody>
                                            </table>
                                          </div>
                                        </td>
                                      </tr>
                                    )}
                                  </React.Fragment>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })()}

            </div>
          )}

          {/* Manual Configuration Tab */}
          {activeTab === 'manual' && (
            <div className="space-y-6">
              <div className="flex items-start gap-3">
                <div className="mt-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-200">
                  <Settings className="h-5 w-5" />
                </div>
                <div>
                  <h4 className={`${MTA_TITLE_SECTION} mb-2`}>Step-by-step configuration</h4>
                  <p className="text-sm text-gray-600 dark:text-gray-300 mb-1 leading-relaxed">
                    Configure algorithms, optimization, and training options in order.
                  </p>
                </div>
              </div>

              {/* Variable Selection Section */}
              <div className={`${MTA_SECTION} p-5 md:p-6 bg-gradient-to-br from-blue-50/80 via-white to-indigo-50/40 dark:from-slate-900 dark:via-slate-900 dark:to-slate-800`}>
                <div className="flex items-center gap-3 mb-5">
                  <Eye className="h-6 w-6 text-blue-600 dark:text-blue-400 shrink-0" />
                  <h4 className={`${MTA_TITLE_SECTION} !text-lg md:!text-xl`}>Variable selection</h4>
                </div>

                <div className="space-y-4">
                  <div
                    className={
                      manualProblemType
                        ? 'flex flex-col gap-4 md:flex-row md:items-stretch md:gap-4'
                        : ''
                    }
                  >
                    <div className="min-w-0 flex-1">
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-2">
                        Target Variable
                      </label>
                      {lockedTargetColumn ? (
                        <>
                          <div className="relative z-20 flex w-full items-center justify-between gap-2 rounded-lg border border-gray-300 bg-gray-100 px-3 py-2 text-gray-900 dark:border-slate-600 dark:bg-slate-800/90 dark:text-white">
                            <span className="truncate font-mono text-sm" title={lockedTargetColumn}>
                              {lockedTargetColumn}
                            </span>
                            <Lock className="h-4 w-4 shrink-0 text-gray-500 dark:text-gray-400" aria-hidden />
                          </div>
                          <p className="mt-1.5 text-xs text-gray-500 dark:text-gray-400">
                            Defined in Objectives &amp; Data; not editable on this step.
                          </p>
                        </>
                      ) : (
                        <select
                          value={manualTargetVariable}
                          onChange={(e) => {
                            const v = e.target.value;
                            setManualTargetVariable(v);
                            setAutoTargetVariable(v);
                          }}
                          className="relative z-20 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 focus:border-transparent focus:ring-2 focus:ring-blue-500 dark:border-slate-700 dark:bg-slate-900 dark:text-white"
                        >
                          <option value="">Select target variable</option>
                          {availableVariables.map((variable) => (
                            <option key={variable} value={variable}>
                              {variable}
                            </option>
                          ))}
                        </select>
                      )}
                    </div>

                    {manualProblemType && (
                      <div className="bg-blue-50 border border-blue-200 dark:bg-slate-900 dark:border-slate-700 rounded-lg p-4 md:flex-1 md:min-w-[220px] flex flex-col justify-center shrink-0">
                        <div className="flex items-center space-x-2">
                          <div className="w-3 h-3 bg-blue-600 rounded-full shrink-0" />
                          <span className="text-sm font-medium text-blue-900 dark:text-white">
                            Problem Type: <span className="font-semibold capitalize">{manualProblemType}</span>
                          </span>
                        </div>
                        <p className="text-xs text-blue-700 dark:text-gray-200 mt-1">
                          {manualProblemType === 'classification'
                            ? 'Predicting discrete categories or classes'
                            : 'Predicting continuous numerical values'}
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Excluded / Non-feature Columns (Manual - Global/Segment) - dynamic only */}
                  {Array.isArray(vifCorrelationData?.excluded_from_analysis) && (
                    <div className="px-3 py-2 bg-gray-50 dark:bg-slate-900/70 border border-gray-200 dark:border-slate-700 rounded">
                      <div className="text-[11px] font-semibold text-gray-700 dark:text-gray-200 mb-0.5">Excluded non-feature columns</div>
                      <div className="text-[11px] text-gray-700 dark:text-gray-200">
                        {vifCorrelationData.excluded_from_analysis.length > 0 ? vifCorrelationData.excluded_from_analysis.join(', ') : 'None'}
                      </div>
                      <div className="mt-0.5 text-[11px] text-gray-500 dark:text-gray-400">Identifier/segment columns are excluded from modeling by default.</div>
                    </div>
                  )}
                </div>
              </div>

              {/* VIF and Correlation Analysis */}
              {false && (
              <div className="border border-gray-200 rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h4 className="font-medium text-gray-900">Variable Analysis</h4>
                    <p className="text-xs text-gray-600 mt-1">
                      Calculate VIF (multicollinearity) and correlation with target variable
                    </p>
                  </div>
                  <button
                    onClick={handleManualVariableAnalysis}
                    disabled={isCalculatingVIF || !manualTargetVariable}
                    className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center space-x-2 text-sm font-medium"
                  >
                    {isCalculatingVIF ? (
                      <>
                        <Loader className="h-4 w-4 animate-spin" />
                        <span>Calculating...</span>
                      </>
                    ) : (
                      <>
                        <Activity className="h-4 w-4" />
                        <span>Calculate Variable Analysis</span>
                      </>
                    )}
                  </button>
                </div>

                {/* VIF Preview Dropdown */}
                {vifCorrelationData && (
                  <div className="mt-4">
                    <button
                      onClick={() => setShowVifPreview(!showVifPreview)}
                      className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 border border-gray-200 dark:bg-slate-900/70 dark:hover:bg-slate-900 dark:border-slate-700 rounded-lg transition-colors"
                    >
                      <div className="flex items-center space-x-2">
                        <Eye className="h-4 w-4 text-gray-600 dark:text-gray-300" />
                        <span className="text-sm font-medium text-gray-900 dark:text-white">
                          View VIF, Correlation & IV Results ({vifCorrelationData.variable_statistics?.length || 0} variables)
                        </span>
                      </div>
                      <ChevronDown className={`h-4 w-4 text-gray-600 dark:text-gray-300 transition-transform ${showVifPreview ? 'rotate-180' : ''}`} />
                    </button>

                    {showVifPreview && (
                      <div className="mt-3 border border-gray-200 dark:border-slate-700 rounded-lg overflow-hidden">
                        {/* Summary Stats */}
                        <div className="bg-gradient-to-r from-purple-50 to-pink-50 dark:from-slate-900 dark:to-slate-800 p-4 border-b border-gray-200 dark:border-slate-700">
                          <h5 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">Analysis Summary</h5>
                          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                            <div className="bg-white dark:bg-slate-900/70 rounded-lg p-3 border border-transparent dark:border-slate-700">
                              <div className="text-xs text-gray-600 dark:text-gray-300">Total Variables</div>
                              <div className="text-lg font-bold text-gray-900 dark:text-white">{vifCorrelationData.summary?.total_variables || 0}</div>
                            </div>
                            <div className="bg-white dark:bg-slate-900/70 rounded-lg p-3 border border-transparent dark:border-slate-700">
                              <div className="text-xs text-green-600">Correlation (&ge;0.05)</div>
                              <div className="text-lg font-bold text-green-900 dark:text-green-300">{vifCorrelationData.summary?.high_correlation_count || 0}</div>
                            </div>
                            <div className="bg-white dark:bg-slate-900/70 rounded-lg p-3 border border-transparent dark:border-slate-700">
                              <div className="text-xs text-green-600">VIF (&le;10)</div>
                              <div className="text-lg font-bold text-green-900 dark:text-green-300">{vifCorrelationData.summary?.good_vif_count || 0}</div>
                            </div>
                            <div className="bg-white dark:bg-slate-900/70 rounded-lg p-3 border border-transparent dark:border-slate-700">
                              <div className="text-xs text-purple-600">IV (&ge;0.02)</div>
                              <div className="text-lg font-bold text-purple-900 dark:text-purple-300">{vifCorrelationData.summary?.strong_iv_count || 0}</div>
                            </div>
                            <div className="bg-white dark:bg-slate-900/70 rounded-lg p-3 border border-transparent dark:border-slate-700">
                              <div className="text-xs text-teal-600">Good Variance</div>
                              <div className="text-lg font-bold text-teal-900 dark:text-teal-300">{vifCorrelationData.summary?.good_variance_count || 0}</div>
                              {(vifCorrelationData.summary?.zero_variance_count > 0 || vifCorrelationData.summary?.near_zero_variance_count > 0) && (
                                <div className="text-xs text-red-500 mt-1">
                                  {vifCorrelationData.summary?.zero_variance_count > 0 && `${vifCorrelationData.summary.zero_variance_count} zero`}
                                  {vifCorrelationData.summary?.zero_variance_count > 0 && vifCorrelationData.summary?.near_zero_variance_count > 0 && ', '}
                                  {vifCorrelationData.summary?.near_zero_variance_count > 0 && `${vifCorrelationData.summary.near_zero_variance_count} low`}
                                </div>
                              )}
                            </div>
                          </div>
                        </div>

                        {/* Variable Statistics Table */}
                        <div className="overflow-x-auto max-h-96 overflow-y-auto">
                          <table className="w-full text-sm">
                            <thead className={`${MTA_THEAD} sticky top-0`}>
                              <tr>
                                <th className="px-4 py-3 text-left font-semibold text-gray-700 dark:text-gray-200">Variable</th>
                                <th className="px-4 py-3 text-right font-semibold text-gray-700 dark:text-gray-200">Correlation</th>
                                <th className="px-4 py-3 text-right font-semibold text-gray-700 dark:text-gray-200">VIF</th>
                                <th className="px-4 py-3 text-right font-semibold text-gray-700 dark:text-gray-200">IV</th>
                                <th className="px-4 py-3 text-right font-semibold text-gray-700 dark:text-gray-200">Variance (Std)</th>
                                <th className="px-4 py-3 text-left font-semibold text-gray-700 dark:text-gray-200">Interpretation</th>
                              </tr>
                            </thead>
                            <tbody className="bg-white dark:bg-slate-950 divide-y divide-gray-200 dark:divide-slate-800">
                              {vifCorrelationData.variable_statistics?.map((stat: any, index: number) => {
                                const absCorr = Math.abs(stat.correlation);
                                const corrColor = absCorr > 0.8 ? 'text-green-900 font-bold' : absCorr > 0.5 ? 'text-blue-900 font-medium' : absCorr < 0.1 ? 'text-red-600 font-bold' : 'text-gray-900';
                                const vifColor = stat.vif && stat.vif > 10 ? 'text-red-800 font-bold' : stat.vif && stat.vif > 5 ? 'text-orange-900 font-medium' : 'text-gray-900';
                                const varianceColor = stat.variance_status === 'zero' ? 'text-red-600 font-bold' : stat.variance_status === 'near_zero' ? 'text-orange-600 font-medium' : 'text-gray-900 dark:text-gray-200';
                                
                                return (
                                  <tr key={index} className={index % 2 === 0 ? 'bg-white dark:bg-slate-950' : 'bg-gray-50 dark:bg-slate-900/60'}>
                                    <td className="px-4 py-3 text-gray-900 dark:text-white font-medium">{stat.variable}</td>
                                    <td className={`px-4 py-3 text-right ${corrColor}`}>
                                      {stat.correlation.toFixed(4)}
                                    </td>
                                    <td className={`px-4 py-3 text-right ${vifColor}`}>
                                      {stat.vif !== null && stat.vif !== undefined ? stat.vif.toFixed(2) : 'N/A'}
                                    </td>
                                    <td className="px-4 py-3 text-right text-purple-900 dark:text-purple-300">
                                      {stat.iv !== null && stat.iv !== undefined ? Number(stat.iv).toFixed(4) : 'N/A'}
                                    </td>
                                    <td className={`px-4 py-3 text-right ${varianceColor}`}>
                                      {stat.std !== null && stat.std !== undefined ? stat.std.toFixed(4) : 'N/A'}
                                      {stat.variance_status === 'zero' && <span className="ml-1 text-xs">(Zero)</span>}
                                      {stat.variance_status === 'near_zero' && <span className="ml-1 text-xs">(Low)</span>}
                                    </td>
                                    <td className="px-4 py-3 text-xs text-gray-600 dark:text-gray-300">
                                      {absCorr > 0.8 && <span className="inline-block px-2 py-1 bg-green-100 text-green-800 rounded-full mr-1">Strong</span>}
                                      {absCorr < 0.1 && <span className="inline-block px-2 py-1 bg-orange-100 text-orange-800 rounded-full mr-1">Weak</span>}
                                      {stat.vif && stat.vif > 10 && <span className="inline-block px-2 py-1 bg-red-100 text-red-800 rounded-full mr-1">High VIF</span>}
                                      {stat.iv !== null && stat.iv !== undefined && stat.iv >= 0.3 && <span className="inline-block px-2 py-1 bg-purple-100 text-purple-800 rounded-full mr-1">Strong IV</span>}
                                      {stat.variance_status === 'zero' && <span className="inline-block px-2 py-1 bg-red-100 text-red-800 rounded-full mr-1">Zero Var</span>}
                                      {stat.variance_status === 'near_zero' && <span className="inline-block px-2 py-1 bg-yellow-100 text-yellow-800 rounded-full mr-1">Low Var</span>}
                                    </td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>

                        {/* Interpretation Guide */}
                        <div className="bg-gray-50 dark:bg-slate-900/60 p-4 border-t border-gray-200 dark:border-slate-700">
                          <h6 className="text-xs font-semibold text-gray-700 dark:text-gray-200 mb-2">Interpretation Guide:</h6>
                          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-2 text-xs text-gray-600 dark:text-gray-300">
                            <div>
                              <strong>Correlation:</strong> Measures linear relationship with target (-1 to 1)
                              <ul className="ml-4 mt-1 space-y-1">
                                <li>• &gt;0.8: Strong positive/negative relationship</li>
                                <li>• 0.5-0.8: Moderate relationship</li>
                                <li>• &lt;0.1: Weak relationship (consider removing)</li>
                              </ul>
                            </div>
                            <div>
                              <strong>VIF:</strong> Variance Inflation Factor (multicollinearity)
                              <ul className="ml-4 mt-1 space-y-1">
                                <li>• &gt;10: High multicollinearity (consider removing)</li>
                                <li>• 5-10: Moderate multicollinearity</li>
                                <li>• &lt;5: Low multicollinearity (good)</li>
                              </ul>
                            </div>
                            <div>
                              <strong>IV:</strong> Information Value (predictive power)
                              <ul className="ml-4 mt-1 space-y-1">
                                <li>• &gt;0.3: Strong predictor</li>
                                <li>• 0.1-0.3: Medium predictor</li>
                                <li>• &lt;0.02: Useless predictor</li>
                              </ul>
                            </div>
                            <div>
                              <strong>Variance (Std):</strong> Standard deviation of values
                              <ul className="ml-4 mt-1 space-y-1">
                                <li>• Zero: Only 1 unique value (exclude)</li>
                                <li>• Low: &gt;95% same value or std&lt;0.01</li>
                                <li>• Normal: Good variability for modeling</li>
                              </ul>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Variable Screener (VIF & Correlation) */}
                {vifCorrelationData && (
                  <div className="mt-6 border border-gray-200 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-2">
                      <h5 className="font-medium text-gray-900 flex items-center space-x-2">
                        <Filter className="h-4 w-4 text-blue-600" />
                        <span>Variable Screener</span>
                      </h5>
                      <div className="text-sm text-gray-600">
                        {filteredVariables.length} of {vifCorrelationData.variable_statistics?.length || 0} variables match your criteria
                      </div>
                    </div>

                    <div className="space-y-3">
                      {variableFilters.map((f, idx) => (
                        <div key={idx} className="grid grid-cols-1 md:grid-cols-3 gap-3 items-center">
                          <div>
                            <label className="block text-xs font-medium text-gray-600 mb-1">Metric</label>
                            <select
                              value={f.metric}
                              onChange={(e) => {
                                const nf = [...variableFilters];
                                nf[idx] = { ...nf[idx], metric: e.target.value as 'correlation' | 'vif' | 'iv' };
                                setVariableFilters(nf);
                              }}
                              className="w-full px-3 py-2 border border-gray-300 dark:border-slate-700 rounded-lg text-sm dark:bg-slate-900 dark:text-white"
                            >
                              <option value="correlation">Absolute Correlation</option>
                              <option value="vif">VIF</option>
                              <option value="iv">IV</option>
                            </select>
                          </div>

                          <div>
                            <label className="block text-xs font-medium text-gray-600 mb-1">Operator</label>
                            <select
                              value={f.operator}
                              onChange={(e) => {
                                const op = e.target.value as ('>=' | '<=' | 'between');
                                const nf = [...variableFilters];
                                nf[idx] = { ...nf[idx], operator: op };
                                setVariableFilters(nf);
                              }}
                              className="w-full px-3 py-2 border border-gray-300 dark:border-slate-700 rounded-lg text-sm dark:bg-slate-900 dark:text-white"
                            >
                              <option value=">=">Greater than or equal (≥)</option>
                              <option value="<=">Less than or equal (≤)</option>
                              <option value="==">Equal to (=)</option>
                              <option value="between">Between</option>
                            </select>
                          </div>

                          <div>
                            <label className="block text-xs font-medium text-gray-600 mb-1">Value</label>
                            <input
                              type="text"
                              inputMode="decimal"
                              value={f.value}
                              onChange={(e) => {
                                const nf = [...variableFilters];
                                nf[idx] = { ...nf[idx], value: e.target.value };
                                setVariableFilters(nf);
                              }}
                              className="w-full px-3 py-2 border border-gray-300 dark:border-slate-700 rounded-lg text-sm dark:bg-slate-900 dark:text-white"
                            />
                          </div>
                        </div>
                      ))}

                      <div className="flex items-center justify-between mt-2">
                        <div className="space-x-2">
                          <button
                            onClick={() => setVariableFilters([...variableFilters, { metric: 'correlation', operator: '>=', value: '0.1' }])}
                            className="px-3 py-2 text-sm bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] transition-colors"
                          >
                            Add Filter
                          </button>
                          <button
                            onClick={() => setVariableFilters([{ metric: 'correlation', operator: '>=', value: '0.1' }])}
                            className="px-3 py-2 text-sm bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] transition-colors"
                          >
                            Reset
                          </button>
                        </div>

                        <div className="flex items-center space-x-2" />
                      </div>

                      {/* Shortlisted Variables (post-screening) */}
                      <div className="mt-4 border-t pt-4">
                        <div className="flex items-center justify-between mb-2">
                          <h6 className="text-sm font-semibold text-gray-900">Shortlisted Variables</h6>
                          <div className="text-xs text-gray-600">Toggle to include/exclude for model training</div>
                        </div>
                        {filteredVariables.length === 0 ? (
                          <div className="text-xs text-gray-600">No variables match current filters.</div>
                        ) : (
                          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2 max-h-56 overflow-y-auto">
                            {filteredVariables.map((v) => (
                              <label key={v} className={`flex items-center space-x-2 border rounded px-2 py-1 text-sm ${shortlistSelection[v] ? 'bg-white' : 'bg-gray-50 opacity-70'}`}>
                                <input
                                  type="checkbox"
                                  checked={!!shortlistSelection[v]}
                                  onChange={(e)=> setShortlistSelection((prev)=> ({...prev, [v]: e.target.checked}))}
                                />
                                <span className="truncate" title={v}>{v}</span>
                              </label>
                            ))}
                          </div>
                        )}
                        <div className="mt-3 flex items-center justify-between">
                          <div className="text-xs text-gray-600">
                            {Object.values(shortlistSelection).filter(Boolean).length} of {filteredVariables.length} shortlisted variables selected for training
                          </div>
                          <div className="flex items-center space-x-2">
                            <button
                              onClick={() => {
                                const newSelection: Record<string, boolean> = {};
                                filteredVariables.forEach((v) => {
                                  newSelection[v] = true;
                                });
                                setShortlistSelection(newSelection);
                              }}
                              disabled={filteredVariables.length === 0}
                              className="px-3 py-2 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700 disabled:opacity-50"
                            >
                              Select All
                            </button>
                            <button
                              onClick={() => {
                                const newSelection: Record<string, boolean> = {};
                                filteredVariables.forEach((v) => {
                                  newSelection[v] = false;
                                });
                                setShortlistSelection(newSelection);
                              }}
                              disabled={Object.values(shortlistSelection).filter(Boolean).length === 0}
                              className="px-3 py-2 bg-gray-600 text-white rounded-lg text-sm hover:bg-gray-700 disabled:opacity-50"
                            >
                              Deselect All
                            </button>
                            <button
                              onClick={() => {
                                const finalVars = filteredVariables.filter((v)=> !!shortlistSelection[v]);
                                setManualSelectedIndependentVariables(finalVars);
                                setShortlistConfirmed(true);
                              }}
                              disabled={Object.values(shortlistSelection).filter(Boolean).length === 0}
                              className="px-3 py-2 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg text-sm hover:bg-blue-700 dark:hover:bg-[#333380] disabled:opacity-50"
                            >
                              Use Selected For Training
                            </button>
                          </div>
                        </div>
                        {shortlistConfirmed && (
                          <div className="mt-2 text-green-700 text-xs flex items-center space-x-2">
                            <span className="inline-block w-2 h-2 bg-green-600 rounded-full"></span>
                            <span>Shortlisted variables will be used for model training.</span>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
              )}

              {/* Step A: Algorithm configuration */}
              <div className={`${MTA_SECTION} p-5 md:p-6`}>
                <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
                  <div className="flex items-center gap-3 min-w-0">
                    <span className={MTA_STEP_LETTER_BADGE} title="Step A">
                      Step A
                    </span>
                    <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-blue-500/15 dark:bg-blue-500/20 ring-1 ring-blue-300/40">
                      <Settings className="h-6 w-6 text-blue-700 dark:text-blue-300" />
                    </div>
                    <h4 className={`${MTA_TITLE_SECTION} !text-lg md:!text-xl`}>Algorithm configuration</h4>
                  </div>
                  <ChevronDown className="h-5 w-5 text-gray-400 dark:text-gray-300 shrink-0" />
                </div>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-3">
                      Select Algorithm(s)
                    </label>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                      {algorithms.map((algo) => {
                        const isSelected = selectedAlgorithms.includes(algo.id);
                        return (
                          <button
                            key={algo.id}
                            onClick={() => {
                              setSelectedAlgorithms((prev) =>
                                prev.includes(algo.id) ? prev.filter((a) => a !== algo.id) : [...prev, algo.id]
                              );
                              // initialize params if missing
                              // setAlgorithmParams((prev) => ({ ...defaultAlgoParams, ...prev }));
                            }}
                            className={`p-4 border-2 rounded-lg text-left transition-all ${
                              isSelected
                                ? 'border-blue-600 bg-blue-50 dark:border-blue-400 dark:bg-slate-800'
                                : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50 dark:border-slate-700 dark:hover:border-slate-600 dark:hover:bg-slate-800 dark:bg-slate-900/40'
                            }`}
                          >
                            <div className="text-2xl mb-1">{algo.icon}</div>
                            <div className="font-medium text-gray-900 dark:text-white text-sm">{algo.name}</div>
                            <div className="text-xs text-gray-600 dark:text-gray-300 mt-1">{algo.description}</div>
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  <div className="bg-gray-50 dark:bg-slate-900/70 rounded-lg p-3 border border-transparent dark:border-slate-700">
                    <h6 className="text-sm font-medium text-gray-700 dark:text-gray-200 mb-2">Search Space Definition</h6>
                    <div className="text-sm text-gray-600 dark:text-gray-300">
                      Hyperparameter ranges will be automatically configured based on selected algorithm
                      and dataset characteristics.
                    </div>
                  </div>

                  {/* Hyperparameter Range Configuration - Always Visible */}
                  <div className="mt-4 space-y-2">
                    <div className="border-l-4 border-blue-500 pl-3">
                      <h3 className="text-base font-semibold text-gray-900 dark:text-white">🎯 Hyperparameter Search Ranges</h3>
                    </div>
                    
                    <div className="grid grid-cols-1 gap-3">
                      {selectedAlgorithms.map((algo) => (
                        <div key={algo}>
                          {renderHyperparameterRangeInputs(algo)}
                        </div>
                      ))}
                    </div>
                    
                    {selectedAlgorithms.length === 0 && (
                      <div className="bg-yellow-50 border border-yellow-200 rounded p-3 text-xs text-yellow-700">
                        ⚠️ Please select at least one algorithm to configure hyperparameter ranges
                      </div>
                    )}
                  </div>

                  {/* DEPRECATED: Old parameter forms - replaced with range inputs above
                  <div style={{ display: 'none' }}>
                    {selectedAlgorithms.length > 0 && (
                      <div className="space-y-4">
                        {selectedAlgorithms.map((algoId) => (
                          <div key={algoId} className="border border-gray-200 rounded-lg p-4 bg-gray-50">
                            <div className="font-medium text-gray-900 mb-3">{algorithms.find(a => a.id === algoId)?.name} Parameters</div>
                            {algoId === 'xgboost' && (
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                              <div>
                                <label className="block text-xs font-medium text-gray-600 mb-1">max_depth</label>
                                <input type="number" value={algorithmParams.xgboost.max_depth}
                                  onChange={(e)=>setAlgorithmParams(p=>({...p,xgboost:{...p.xgboost,max_depth:Number(e.target.value)}}))}
                                  className="w-full px-3 py-2 border rounded" />
                                <div className="text-[11px] text-gray-500">Maximum tree depth (default: 6)</div>
                              </div>
                              <div>
                                <label className="block text-xs font-medium text-gray-600 mb-1">min_child_weight</label>
                                <input type="number" step="0.01" value={algorithmParams.xgboost.min_child_weight}
                                  onChange={(e)=>setAlgorithmParams(p=>({...p,xgboost:{...p.xgboost,min_child_weight:Number(e.target.value)}}))}
                                  className="w-full px-3 py-2 border rounded" />
                                <div className="text-[11px] text-gray-500">Minimum sum of instance weight in a child (default: 1)</div>
                              </div>
                              <div>
                                <label className="block text-xs font-medium text-gray-600 mb-1">gamma</label>
                                <input type="number" step="0.01" value={algorithmParams.xgboost.gamma}
                                  onChange={(e)=>setAlgorithmParams(p=>({...p,xgboost:{...p.xgboost,gamma:Number(e.target.value)}}))}
                                  className="w-full px-3 py-2 border rounded" />
                                <div className="text-[11px] text-gray-500">Minimum loss reduction for split (default: 0)</div>
                              </div>
                              <div>
                                <label className="block text-xs font-medium text-gray-600 mb-1">learning_rate (eta)</label>
                                <input type="number" step="0.01" value={algorithmParams.xgboost.learning_rate}
                                  onChange={(e)=>setAlgorithmParams(p=>({...p,xgboost:{...p.xgboost,learning_rate:Number(e.target.value)}}))}
                                  className="w-full px-3 py-2 border rounded" />
                                <div className="text-[11px] text-gray-500">Step size shrinkage (default: 0.3)</div>
                              </div>
                              <div>
                                <label className="block text-xs font-medium text-gray-600 mb-1">n_estimators</label>
                                <input type="number" value={algorithmParams.xgboost.n_estimators}
                                  onChange={(e)=>setAlgorithmParams(p=>({...p,xgboost:{...p.xgboost,n_estimators:Number(e.target.value)}}))}
                                  className="w-full px-3 py-2 border rounded" />
                                <div className="text-[11px] text-gray-500">Number of boosting rounds (default: 100)</div>
                              </div>
                            </div>
                          )}

                          {algoId === 'lightgbm' && (
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                              <div>
                                <label className="block text-xs font-medium text-gray-600 mb-1">max_depth</label>
                                <input type="number" value={algorithmParams.lightgbm.max_depth}
                                  onChange={(e)=>setAlgorithmParams(p=>({...p,lightgbm:{...p.lightgbm,max_depth:Number(e.target.value)}}))}
                                  className="w-full px-3 py-2 border rounded" />
                                <div className="text-[11px] text-gray-500">Maximum tree depth (default: -1)</div>
                              </div>
                              <div>
                                <label className="block text-xs font-medium text-gray-600 mb-1">num_leaves</label>
                                <input type="number" value={algorithmParams.lightgbm.num_leaves}
                                  onChange={(e)=>setAlgorithmParams(p=>({...p,lightgbm:{...p.lightgbm,num_leaves:Number(e.target.value)}}))}
                                  className="w-full px-3 py-2 border rounded" />
                                <div className="text-[11px] text-gray-500">Maximum leaves per tree (default: 31)</div>
                              </div>
                              <div>
                                <label className="block text-xs font-medium text-gray-600 mb-1">min_child_samples</label>
                                <input type="number" value={algorithmParams.lightgbm.min_child_samples}
                                  onChange={(e)=>setAlgorithmParams(p=>({...p,lightgbm:{...p.lightgbm,min_child_samples:Number(e.target.value)}}))}
                                  className="w-full px-3 py-2 border rounded" />
                                <div className="text-[11px] text-gray-500">Minimum data in one leaf (default: 20)</div>
                              </div>
                              <div>
                                <label className="block text-xs font-medium text-gray-600 mb-1">min_child_weight</label>
                                <input type="number" step="0.0001" value={algorithmParams.lightgbm.min_child_weight}
                                  onChange={(e)=>setAlgorithmParams(p=>({...p,lightgbm:{...p.lightgbm,min_child_weight:Number(e.target.value)}}))}
                                  className="w-full px-3 py-2 border rounded" />
                                <div className="text-[11px] text-gray-500">Minimum sum of hessian in one leaf (default: 1e-3)</div>
                              </div>
                              <div>
                                <label className="block text-xs font-medium text-gray-600 mb-1">learning_rate</label>
                                <input type="number" step="0.01" value={algorithmParams.lightgbm.learning_rate}
                                  onChange={(e)=>setAlgorithmParams(p=>({...p,lightgbm:{...p.lightgbm,learning_rate:Number(e.target.value)}}))}
                                  className="w-full px-3 py-2 border rounded" />
                                <div className="text-[11px] text-gray-500">Shrinkage rate (default: 0.1)</div>
                              </div>
                              <div>
                                <label className="block text-xs font-medium text-gray-600 mb-1">n_estimators</label>
                                <input type="number" value={algorithmParams.lightgbm.n_estimators}
                                  onChange={(e)=>setAlgorithmParams(p=>({...p,lightgbm:{...p.lightgbm,n_estimators:Number(e.target.value)}}))}
                                  className="w-full px-3 py-2 border rounded" />
                                <div className="text-[11px] text-gray-500">Boosting iterations (default: 100)</div>
                              </div>
                            </div>
                          )}

                          {algoId === 'catboost' && (
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                              <div>
                                <label className="block text-xs font-medium text-gray-600 mb-1">depth</label>
                                <input type="number" value={algorithmParams.catboost.depth}
                                  onChange={(e)=>setAlgorithmParams(p=>({...p,catboost:{...p.catboost,depth:Number(e.target.value)}}))}
                                  className="w-full px-3 py-2 border rounded" />
                                <div className="text-[11px] text-gray-500">Tree depth (default: 6)</div>
                              </div>
                              <div>
                                <label className="block text-xs font-medium text-gray-600 mb-1">min_data_in_leaf</label>
                                <input type="number" value={algorithmParams.catboost.min_data_in_leaf}
                                  onChange={(e)=>setAlgorithmParams(p=>({...p,catboost:{...p.catboost,min_data_in_leaf:Number(e.target.value)}}))}
                                  className="w-full px-3 py-2 border rounded" />
                                <div className="text-[11px] text-gray-500">Minimum samples in leaf (default: 1)</div>
                              </div>
                              <div>
                                <label className="block text-xs font-medium text-gray-600 mb-1">learning_rate</label>
                                <input type="number" step="0.01" value={algorithmParams.catboost.learning_rate}
                                  onChange={(e)=>setAlgorithmParams(p=>({...p,catboost:{...p.catboost,learning_rate:Number(e.target.value)}}))}
                                  className="w-full px-3 py-2 border rounded" />
                                <div className="text-[11px] text-gray-500">Learning rate (default: 0.03)</div>
                              </div>
                              <div>
                                <label className="block text-xs font-medium text-gray-600 mb-1">iterations</label>
                                <input type="number" value={algorithmParams.catboost.iterations}
                                  onChange={(e)=>setAlgorithmParams(p=>({...p,catboost:{...p.catboost,iterations:Number(e.target.value)}}))}
                                  className="w-full px-3 py-2 border rounded" />
                                <div className="text-[11px] text-gray-500">Number of trees (default: 100)</div>
                              </div>
                            </div>
                          )}

                          {algoId === 'random_forest' && (
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                              <div>
                                <label className="block text-xs font-medium text-gray-600 mb-1">max_depth</label>
                                <input type="number" value={algorithmParams.random_forest.max_depth || '1'}
                                  onChange={(e)=>setAlgorithmParams(p=>({...p,random_forest:{...p.random_forest,max_depth:e.target.value === '' ? null : Number(e.target.value)}}))}
                                  className="w-full px-3 py-2 border rounded" />
                                <div className="text-[11px] text-gray-500">Maximum tree depth (default: 1)</div>
                              </div>
                              <div>
                                <label className="block text-xs font-medium text-gray-600 mb-1">min_samples_split</label>
                                <input type="number" value={algorithmParams.random_forest.min_samples_split}
                                  onChange={(e)=>setAlgorithmParams(p=>({...p,random_forest:{...p.random_forest,min_samples_split:Number(e.target.value)}}))}
                                  className="w-full px-3 py-2 border rounded" />
                                <div className="text-[11px] text-gray-500">Minimum samples to split node (default: 2)</div>
                              </div>
                              <div>
                                <label className="block text-xs font-medium text-gray-600 mb-1">min_samples_leaf</label>
                                <input type="number" value={algorithmParams.random_forest.min_samples_leaf}
                                  onChange={(e)=>setAlgorithmParams(p=>({...p,random_forest:{...p.random_forest,min_samples_leaf:Number(e.target.value)}}))}
                                  className="w-full px-3 py-2 border rounded" />
                                <div className="text-[11px] text-gray-500">Minimum samples in leaf (default: 1)</div>
                              </div>
                              <div>
                                <label className="block text-xs font-medium text-gray-600 mb-1">max_leaf_nodes</label>
                                <input type="number" value={algorithmParams.random_forest.max_leaf_nodes || '1'}
                                  onChange={(e)=>setAlgorithmParams(p=>({...p,random_forest:{...p.random_forest,max_leaf_nodes:e.target.value === '' ? null : Number(e.target.value)}}))}
                                  className="w-full px-3 py-2 border rounded" />
                                <div className="text-[11px] text-gray-500">Maximum leaf nodes (default: 1)</div>
                              </div>
                              <div>
                                <label className="block text-xs font-medium text-gray-600 mb-1">n_estimators</label>
                                <input type="number" value={algorithmParams.random_forest.n_estimators}
                                  onChange={(e)=>setAlgorithmParams(p=>({...p,random_forest:{...p.random_forest,n_estimators:Number(e.target.value)}}))}
                                  className="w-full px-3 py-2 border rounded" />
                                <div className="text-[11px] text-gray-500">Number of trees (default: 100)</div>
                              </div>
                              <div>
                                <label className="block text-xs font-medium text-gray-600 mb-1">max_features</label>
                                <input type="text" value={algorithmParams.random_forest.max_features}
                                  onChange={(e)=>setAlgorithmParams(p=>({...p,random_forest:{...p.random_forest,max_features:e.target.value}}))}
                                  className="w-full px-3 py-2 border rounded" />
                                <div className="text-[11px] text-gray-500">Features to consider for split (e.g., 'sqrt', 1.0)</div>
                              </div>
                            </div>
                          )}

                          {algoId === 'gradient_boosting' && (
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                              <div>
                                <label className="block text-xs font-medium text-gray-600 mb-1">max_depth</label>
                                <input type="number" value={algorithmParams.gradient_boosting.max_depth}
                                  onChange={(e)=>setAlgorithmParams(p=>({...p,gradient_boosting:{...p.gradient_boosting,max_depth:Number(e.target.value)}}))}
                                  className="w-full px-3 py-2 border rounded" />
                                <div className="text-[11px] text-gray-500">Maximum tree depth (default: 3)</div>
                              </div>
                              <div>
                                <label className="block text-xs font-medium text-gray-600 mb-1">min_samples_split</label>
                                <input type="number" value={algorithmParams.gradient_boosting.min_samples_split}
                                  onChange={(e)=>setAlgorithmParams(p=>({...p,gradient_boosting:{...p.gradient_boosting,min_samples_split:Number(e.target.value)}}))}
                                  className="w-full px-3 py-2 border rounded" />
                                <div className="text-[11px] text-gray-500">Min samples to split (default: 2)</div>
                              </div>
                              <div>
                                <label className="block text-xs font-medium text-gray-600 mb-1">min_samples_leaf</label>
                                <input type="number" value={algorithmParams.gradient_boosting.min_samples_leaf}
                                  onChange={(e)=>setAlgorithmParams(p=>({...p,gradient_boosting:{...p.gradient_boosting,min_samples_leaf:Number(e.target.value)}}))}
                                  className="w-full px-3 py-2 border rounded" />
                                <div className="text-[11px] text-gray-500">Min samples in leaf (default: 1)</div>
                              </div>
                              <div>
                                <label className="block text-xs font-medium text-gray-600 mb-1">n_estimators</label>
                                <input type="number" value={algorithmParams.gradient_boosting.n_estimators}
                                  onChange={(e)=>setAlgorithmParams(p=>({...p,gradient_boosting:{...p.gradient_boosting,n_estimators:Number(e.target.value)}}))}
                                  className="w-full px-3 py-2 border rounded" />
                                <div className="text-[11px] text-gray-500">Number of trees (default: 100)</div>
                              </div>
                              <div>
                                <label className="block text-xs font-medium text-gray-600 mb-1">learning_rate</label>
                                <input type="number" step="0.01" value={algorithmParams.gradient_boosting.learning_rate}
                                  onChange={(e)=>setAlgorithmParams(p=>({...p,gradient_boosting:{...p.gradient_boosting,learning_rate:Number(e.target.value)}}))}
                                  className="w-full px-3 py-2 border rounded" />
                                <div className="text-[11px] text-gray-500">Learning rate (default: 0.1)</div>
                              </div>
                              <div>
                                <label className="block text-xs font-medium text-gray-600 mb-1">subsample</label>
                                <input type="number" step="0.1" value={algorithmParams.gradient_boosting.subsample}
                                  onChange={(e)=>setAlgorithmParams(p=>({...p,gradient_boosting:{...p.gradient_boosting,subsample:Number(e.target.value)}}))}
                                  className="w-full px-3 py-2 border rounded" />
                                <div className="text-[11px] text-gray-500">Subsample ratio (default: 1.0)</div>
                              </div>
                            </div>
                          )}

                          {algoId === 'logistic_regression' && (
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                              <div>
                                <label className="block text-xs font-medium text-gray-600 mb-1">C</label>
                                <input type="number" step="0.1" value={algorithmParams.logistic_regression.C}
                                  onChange={(e)=>setAlgorithmParams(p=>({...p,logistic_regression:{...p.logistic_regression,C:Number(e.target.value)}}))}
                                  className="w-full px-3 py-2 border rounded" />
                                <div className="text-[11px] text-gray-500">Regularization strength (default: 1.0)</div>
                              </div>
                              <div>
                                <label className="block text-xs font-medium text-gray-600 mb-1">max_iter</label>
                                <input type="number" value={algorithmParams.logistic_regression.max_iter}
                                  onChange={(e)=>setAlgorithmParams(p=>({...p,logistic_regression:{...p.logistic_regression,max_iter:Number(e.target.value)}}))}
                                  className="w-full px-3 py-2 border rounded" />
                                <div className="text-[11px] text-gray-500">Maximum iterations (default: 1000)</div>
                              </div>
                              <div>
                                <label className="block text-xs font-medium text-gray-600 mb-1">solver</label>
                                <select value={algorithmParams.logistic_regression.solver}
                                  onChange={(e)=>setAlgorithmParams(p=>({...p,logistic_regression:{...p.logistic_regression,solver:e.target.value}}))}
                                  className="w-full px-3 py-2 border rounded">
                                  <option value="liblinear">liblinear</option>
                                  <option value="lbfgs">lbfgs</option>
                                  <option value="newton-cg">newton-cg</option>
                                  <option value="sag">sag</option>
                                  <option value="saga">saga</option>
                                </select>
                                <div className="text-[11px] text-gray-500">Optimization algorithm</div>
                              </div>
                              <div>
                                <label className="block text-xs font-medium text-gray-600 mb-1">penalty</label>
                                <select value={algorithmParams.logistic_regression.penalty}
                                  onChange={(e)=>setAlgorithmParams(p=>({...p,logistic_regression:{...p.logistic_regression,penalty:e.target.value}}))}
                                  className="w-full px-3 py-2 border rounded">
                                  <option value="l2">l2</option>
                                  <option value="l1">l1</option>
                                  <option value="elasticnet">elasticnet</option>
                                  <option value="none">none</option>
                                </select>
                                <div className="text-[11px] text-gray-500">Regularization type</div>
                              </div>
                            </div>
                          )}

                        </div>
                      ))}
                    </div>
                  )}
                  </div>
                  */}
                </div>
              </div>

              {/* Step B: Optimization configuration */}
              <div className={`${MTA_SECTION} p-5 md:p-6`}>
                <div className="flex flex-wrap items-center gap-3 mb-5">
                  <span className={MTA_STEP_LETTER_BADGE} title="Step B">
                    Step B
                  </span>
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-purple-500/15 dark:bg-purple-500/20 ring-1 ring-purple-300/40">
                    <Activity className="h-6 w-6 text-purple-700 dark:text-purple-200" />
                  </div>
                  <h4 className={`${MTA_TITLE_SECTION} !text-lg md:!text-xl`}>Optimization configuration</h4>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Cross-validation folds */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Cross-validation Folds</label>
                    <input
                      type="number"
                      min="3"
                      max="10"
                      value={manualCvFolds}
                      onChange={(e) => setManualCvFolds(Math.max(3, Math.min(10, parseInt(e.target.value) || 5)))}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-slate-700 rounded-lg dark:bg-slate-900 dark:text-white"
                      placeholder="5"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Applies globally across selected algorithms. Recommended range: 3 to 10.
                    </p>
                  </div>

                  {/* Optimization Method */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Optimization Method</label>
                    <select
                      value={optimizationMethodManual}
                      onChange={(e) => setOptimizationMethodManual(e.target.value as 'bayesian' | 'random')}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-slate-700 rounded-lg dark:bg-slate-900 dark:text-white"
                    >
                      <option value="bayesian">Bayesian Optimization</option>
                      <option value="random">Random Search</option>
                    </select>
                  </div>

                  {/* Target Metric (Optional) */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Target Metric (Optional)</label>
                    <select
                      value={targetMetricManual}
                      onChange={(e) => setTargetMetricManual(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-slate-700 rounded-lg dark:bg-slate-900 dark:text-white"
                    >
                      <option value="">Select primary metric (optional)</option>
                      {manualProblemType === 'classification' ? (
                        <>
                          <option value="auc">AUC-ROC</option>
                          <option value="f1">F1-Score</option>
                          <option value="precision">Precision</option>
                          <option value="recall">Recall</option>
                          <option value="accuracy">Accuracy</option>
                          <option value="log_loss">Log Loss</option>
                        </>
                      ) : manualProblemType === 'regression' ? (
                        <>
                          <option value="r2">R²</option>
                          <option value="mae">MAE</option>
                          <option value="mse">MSE</option>
                          <option value="rmse">RMSE</option>
                        </>
                      ) : null}
                    </select>
                  </div>

                  {/* Max Iterations (Advanced Setting) */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Max Iterations</label>
                    <input
                      type="number"
                      min="1"
                      max="100"
                      value={maxIterations}
                      onChange={(e) => setMaxIterations(parseInt(e.target.value) || 3)} // Optimized: Default 5→3
                      className="w-full px-3 py-2 border border-gray-300 dark:border-slate-700 rounded-lg dark:bg-slate-900 dark:text-white"
                      placeholder="3"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Determines the maximum number of training iterations. Higher values may lead to better accuracy but longer training times.
                    </p>
                  </div>

                </div>
              </div>

              {/* Removed Step 3 and Step 4 blocks as requested */}

              <div className="flex justify-end mt-3">
                <button
                  onClick={async () => {
                    if (!activeDatasetId || !manualTargetVariable) {
                      alert('Select dataset and target variable');
                      return;
                    }
                    const step4Variables = getStep4SelectedVariablesForStep5();
                    const hasStep4Input = step4Variables.length > 0;

                    // Reuse previously selected variables if shortlist confirmation flag
                    // was lost (e.g., component remount/session transitions).
                    const persistedManualVars = Array.from(
                      new Set(
                        (manualSelectedIndependentVariables || [])
                          .map((v) => String(v || '').trim())
                          .filter((v) => !!v)
                      )
                    );
                    const shortlistedVars = filteredVariables.filter((v) => !!shortlistSelection[v]);

                    // Prefer Step 4 output when available; otherwise use shortlist,
                    // and finally fallback to persisted manual selections.
                    const selectedVars = hasStep4Input
                      ? step4Variables
                      : (shortlistedVars.length > 0 ? shortlistedVars : persistedManualVars);

                    if (selectedVars.length === 0) {
                      alert('No variables selected. Please select variables in Variable Screener (Use Selected For Training) before running.');
                      return;
                    }

                    const variables = resolveStep5InputVariables(selectedVars);

                    if (selectedAlgorithms.length === 0) {
                      alert('Select at least one algorithm');
                      return;
                    }

                    // Show immediate feedback that training started
                    setIsMultiTraining(true);

                  try {
                    // Reset state when starting new training
                    setSelectedAlgorithmForHistory('');
                    setTrainingResults(null);

                    // Initialize progress UI
                    setMultiOverallProgress(5);
                    const initProgress: Record<string, number> = {};
                    const initStatus: Record<string, 'running' | 'completed'> = {};
                    const initIters: Record<string, number> = {};
                    selectedAlgorithms.forEach(a=>{ initProgress[a]=1; initStatus[a]='running'; initIters[a]=0; });
                    setAlgoProgress(initProgress);
                    setAlgoStatus(initStatus);
                    setAlgoIterations(initIters);
                    setMultiLogs([]);
                    if (multiTimerRef.current) window.clearInterval(multiTimerRef.current);
                    startMultiInterval();

                    // Use segment training if in segment mode and segments are available
                    let data;
                    const selectedLrPenalties = (Object.entries(manualLrPenaltyOptions) as Array<[keyof typeof manualLrPenaltyOptions, boolean]>)
                      .filter(([, enabled]) => enabled)
                      .map(([penalty]) => penalty);
                    const manualAlgorithmParams = selectedAlgorithms.includes('logistic_regression')
                      ? {
                          logistic_regression: {
                            penalty_options: selectedLrPenalties,
                            l1_ratio_min: algorithmParamRanges?.logistic_regression?.l1_ratio?.min,
                            l1_ratio_max: algorithmParamRanges?.logistic_regression?.l1_ratio?.max,
                          },
                        }
                      : undefined;
                    if (trainingMode === 'segment-specific' && segmentInfo?.available) {
                      // Call segment training API - train on all segments
                      data = await fastApiService.runSegmentTraining({
                        dataset_id: activeDatasetId,
                        target_column: manualTargetVariable,
                        independent_variables: variables,
                        locked_variables: getLockedVariableList(),
                        algorithms: selectedAlgorithms,
                        algorithm_param_ranges: algorithmParamRanges,  // Use ranges instead of single values
                        max_iterations: maxIterations,
                        optimization_method: optimizationMethodManual,
                        target_metric: targetMetricManual || undefined,
                        cv_folds: manualCvFolds,
                        optuna_trials: manualOptunaTrials,
                        early_stopping_rounds: manualEarlyStoppingRounds,
                        algorithm_params: manualAlgorithmParams,
                        lr_backward_elimination: {
                          vif_threshold: manualLrVifThreshold,
                          p_value_threshold: manualLrPvalueThreshold,
                        },
                        segment_column: segmentInfo?.segment_column || segmentSchemeColumnOverride || null,
                      } as any);
                    } else {
                      // Use regular training API with hyperparameter ranges
                      const trainingPayload: any = {
                        dataset_id: activeDatasetId,
                        target_column: manualTargetVariable,
                        independent_variables: variables,
                        locked_variables: getLockedVariableList(),
                        algorithms: selectedAlgorithms,
                        algorithm_param_ranges: algorithmParamRanges,  // Always send ranges
                        max_iterations: maxIterations,
                        optimization_method: optimizationMethodManual,
                        target_metric: targetMetricManual || undefined,
                        cv_folds: manualCvFolds,
                        optuna_trials: manualOptunaTrials,
                        early_stopping_rounds: manualEarlyStoppingRounds,
                        algorithm_params: manualAlgorithmParams,
                        lr_backward_elimination: {
                          vif_threshold: manualLrVifThreshold,
                          p_value_threshold: manualLrPvalueThreshold,
                        },
                      };
                      
                      data = await fastApiService.trainMultipleModels(trainingPayload);
                    }
                    console.log('Multi-model results', data);
                    setMultiResults(data as any);
                    setLastUsedVariables(variables); // Track which variables were actually used for training
                    setMultiOverallProgress(100);

                    // Handle different result structures for regular vs segment training
                    let processedResults = data;
                    if (data.segment_results) {
                      // Convert segment results to regular results format for display
                      const allResults: any[] = [];
                      Object.values(data.segment_results).forEach((segmentResult: any) => {
                        // Handle case where segmentResult is an error string or object with error
                        if (typeof segmentResult === 'string') {
                          // Skip error strings
                          return;
                        }
                        if (segmentResult && segmentResult.error) {
                          // Skip objects with error property
                          return;
                        }
                        if (segmentResult && segmentResult.results && Array.isArray(segmentResult.results)) {
                          // Filter out any results without model_id or with error property
                          const validResults = segmentResult.results.filter((r: any) => 
                            r && r.model_id && !r.error
                          );
                          allResults.push(...validResults);
                        }
                      });

                      processedResults = {
                        ...data,
                        results: allResults
                      };
                      console.log('Converted segment results for display:', processedResults);
                    }

                    const doneStatus: Record<string, 'running' | 'completed'> = {};
                    (processedResults.results || []).forEach((r: any) => {
                      if (r && r.algorithm) {
                        doneStatus[r.algorithm] = 'completed';
                      }
                    });
                    setAlgoStatus(doneStatus);
                    if (multiTimerRef.current) { window.clearInterval(multiTimerRef.current); multiTimerRef.current = null; }
                    // Append final metric per algorithm, then completion line
                    setTrainingResults(processedResults);

                    // ✅ PRESERVE: Cache results for documentation (Model Selection section) so Step 9 can render them
                    try {
                      sessionStorage.setItem('training_results', JSON.stringify(processedResults));
                      const selectionSummary = buildModelSelectionSummary(processedResults);
                      sessionStorage.setItem('model_selection_summary', JSON.stringify(selectionSummary));
                      console.log('✅ Model selection summary cached for documentation (manual/segment training)');
                    } catch (e) {
                      console.error('Failed to store model selection summary for documentation:', e);
                    }

                    // ✅ NEW: Store results for UI persistence (keyed by dataset and mode)
                    const manualStorageKey = getResultsStorageKey('manual');
                    if (manualStorageKey) {
                      try {
                        sessionStorage.setItem(manualStorageKey, JSON.stringify(processedResults));
                        console.log('✅ Manual training results stored for UI persistence');
                      } catch (e) {
                        console.error('Failed to store manual training results for UI persistence:', e);
                      }
                    }
                    notifyMtaTrainingResultsPersisted(activeDatasetId);
                    // Training completed successfully
                    // Note: Manual training results are displayed via the trainingResults section at line ~3906
                    // showResults is only used for auto training (line ~4742)
                    } catch (err) {
                      console.error(err);

                      // If user cancelled, do not show an error toast
                      if (err instanceof Error && err.message === 'cancelled') {
                        return;
                      }

                      // Special-case: when running manual segment-specific training in
                      // active_scope='entire' the code can sometimes surface a
                      // TypeError reading 'segment_results' (data undefined). The
                      // underlying training actually completes successfully but the
                      // UI shows this misleading error message. Change the popup
                      // text in that narrow case to the friendly success message
                      // used in dev mode. Do NOT change functionality.
                      try {
                        const msg = err && (err as any).message ? String((err as any).message) : '';
                        if (trainingMode === 'segment-specific' && /segment_results|Cannot read properties of undefined/i.test(msg)) {
                          alert('Segment Training completed successfully!');
                        } else {
                          alert(`Multi-model training failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
                        }
                      } catch (e) {
                        // Fallback to original behaviour if something unexpected happens
                        alert(`Multi-model training failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
                      }
                    } finally {
                      // Reset training state regardless of success or failure
                      setIsMultiTraining(false);
                      setMultiLogs([]); // Clear training logs
                      setTrainingLogs([]); // Clear regular training logs
                      setIsReceivingLogs(false); // Reset log receiving state
                      if (multiTimerRef.current) { window.clearInterval(multiTimerRef.current); multiTimerRef.current = null; }
                    }
                  }}
                  disabled={isMultiTraining || !canRunManualSelectedModels}
                  title={
                    !isMultiTraining && !canRunManualSelectedModels
                      ? 'Lock variables, confirm variables & run RFE, then complete Feature review & override before training.'
                      : undefined
                  }
                  className={`px-6 py-3 text-white rounded-lg transition-all flex items-center justify-center space-x-2 font-semibold shadow-lg ${
                    isMultiTraining || !canRunManualSelectedModels
                      ? 'bg-gray-400 cursor-not-allowed'
                      : 'bg-blue-600 dark:bg-[#292966] hover:bg-blue-700 dark:hover:bg-[#333380]'
                  }`}
                >
                  {isMultiTraining ? (
                    <>
                      <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                      <span>Training in Progress...</span>
                    </>
                  ) : (
                    <>
                      <Play className="h-5 w-5" />
                      <span>Run Selected Models</span>
                    </>
                  )}
                </button>

                {isMultiTraining && (
                  <button
                    type="button"
                    onClick={async () => {
                      const label =
                        trainingMode === 'segment-specific'
                          ? 'segment manual training'
                          : 'global manual training';

                      const confirmed = window.confirm(`Cancel current ${label}?`);
                      if (!confirmed) return;

                      try {
                        if (trainingMode === 'segment-specific') {
                          await fastApiService.cancelSegmentTrainingJob();
                        } else {
                          await fastApiService.cancelTrainMultipleModelsJob();
                        }
                      } catch (error) {
                        console.error('Failed to cancel manual training', error);
                        alert('Could not cancel manual training. Please check the console for details.');
                      } finally {
                        // Stop local progress UI and timers
                        stopMultiTraining();
                      }
                    }}
                    className="px-4 py-2 border border-red-500 text-red-600 rounded-lg text-sm hover:bg-red-50 transition-colors"
                  >
                    Cancel
                  </button>
                )}
              </div>
              {isMultiTraining && (
                <div className={`mt-6 ${MTA_SECTION} p-5 border-blue-200/60 dark:border-blue-900/40`}>
                  <div className="flex items-center gap-3 mb-3">
                    <Loader className="h-7 w-7 text-blue-600 animate-spin shrink-0" />
                    <h4 className={MTA_TITLE_SECTION}>Multi-algorithm training</h4>
                  </div>
                  {/* Removed duplicate overall progress bar here to avoid double rendering */}

                  {/* Controls removed here as requested; controls appear below in the results section */}
                  {/* Intentionally no logs here; single consolidated log shown after model stats below */}
                </div>
              )}

              {/* Results view mirroring provided layout */}
              {trainingResults && (
                <div className={`mt-6 ${MTA_SECTION} p-5 md:p-6`}>
                  <div className="flex flex-wrap items-center gap-3 mb-2">
                    <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-emerald-500/15 dark:bg-emerald-500/20 ring-1 ring-emerald-300/40">
                      <Play className="h-6 w-6 text-emerald-700 dark:text-emerald-200" />
                    </div>
                    <h3 className={MTA_TITLE_SECTION}>Multi-algorithm training progress</h3>
                  </div>
                  <div className="text-sm text-gray-600 dark:text-gray-300 mb-4">
                    Training {trainingResults.results?.length || 0} algorithm(s) in parallel
                  </div>

                  {/* Preprocessing Summary Card */}
                  {(() => {
                    // For segment training, get preprocessing summary from selected segment
                    // For global training, get from top level
                    let preprocessingSummary = null;
                    if (trainingResults.segment_results && selectedSegmentManualFilter !== 'all') {
                      const segmentResult = trainingResults.segment_results[`segment_${selectedSegmentManualFilter}`];
                      preprocessingSummary = segmentResult?.preprocessing_summary;
                    } else if (trainingResults.segment_results && selectedSegmentManualFilter === 'all') {
                      // Show first segment's preprocessing as example
                      const firstSegmentKey = Object.keys(trainingResults.segment_results || {})[0];
                      if (firstSegmentKey) {
                        preprocessingSummary = trainingResults.segment_results[firstSegmentKey]?.preprocessing_summary;
                      }
                    } else {
                      preprocessingSummary = trainingResults.preprocessing_summary;
                    }
                    
                    return preprocessingSummary ? (
                      <div className="space-y-4">
                        {Array.isArray(preprocessingSummary.dropped_variables) &&
                          preprocessingSummary.dropped_variables.length > 0 && (
                            <div className="mb-4 border border-yellow-300 bg-yellow-50 rounded-lg p-4 text-sm text-yellow-900">
                              <div className="flex items-start space-x-2 mb-2">
                                <AlertTriangle className="h-4 w-4 text-yellow-600 mt-0.5" />
                                <div>
                                  <div className="font-semibold">
                                    Variables Dropped During Preprocessing
                                  </div>
                                  <p className="text-xs">
                                    The following{' '}
                                    {preprocessingSummary.dropped_variables.length}{' '}
                                    variable(s) were dropped due to missing values or preprocessing rules:
                                  </p>
                                </div>
                              </div>

                              <ul className="list-disc list-inside text-xs space-y-0.5">
                                {preprocessingSummary.dropped_variables.map(
                                  (dropped: any, idx: number) => (
                                    <li key={idx}>{dropped.variable}</li>
                                  )
                                )}
                              </ul>

                              <p className="text-xs mt-3">
                                Model trained on{' '}
                                <strong>{preprocessingSummary.total_processed || 0}</strong>{' '}
                                variables (out of{' '}
                                <strong>
                                  {(preprocessingSummary.total_processed || 0) +
                                    (preprocessingSummary.total_dropped ??
                                      preprocessingSummary.dropped_variables.length ??
                                      0)}
                                </strong>{' '}
                                selected).
                              </p>
                            </div>
                          )}

                        <div className="mb-6 bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-slate-900 dark:to-slate-800 rounded-lg border-2 border-blue-200 dark:border-slate-700 shadow-md">
                          <div className="p-4">
                            <div className="flex items-center justify-between mb-2">
                              <div className="flex items-center space-x-2">
                                <div className="p-2 bg-blue-600 rounded-full">
                                  <Activity className="h-4 w-4 text-white" />
                                </div>
                                <div>
                                  <h5 className="font-semibold text-gray-900 dark:text-white">🔄 Data Preprocessing Summary</h5>
                                  <p className="text-xs text-gray-600 dark:text-gray-300">
                                    Training Mode: {trainingResults.segment_results ? 'Segment Manual' : 'Global Manual'}
                                    {trainingResults.segment_results && selectedSegmentManualFilter !== 'all' && ` | Segment: ${selectedSegmentManualFilter}`}
                                    {trainingResults.segment_results && selectedSegmentManualFilter === 'all' && ' | (Showing example from first segment)'}
                                  </p>
                                </div>
                              </div>
                              <button
                                onClick={() => setPreprocessingSummaryExpanded(!preprocessingSummaryExpanded)}
                                className="text-blue-600 hover:text-blue-800 dark:text-blue-300 dark:hover:text-blue-200 transition-colors"
                              >
                                {preprocessingSummaryExpanded ? (
                                  <ChevronUp className="h-5 w-5" />
                                ) : (
                                  <ChevronDown className="h-5 w-5" />
                                )}
                              </button>
                            </div>
                            
                            {!preprocessingSummaryExpanded ? (
                              <div className="mt-2">
                                <p className="text-sm text-gray-700 dark:text-gray-200">
                                  📊 Summary: {preprocessingSummary.total_processed || 0} variables processed | {preprocessingSummary.total_dropped || 0} variables dropped
                                </p>
                                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">[▼ Expand Details]</p>
                              </div>
                            ) : (
                              <div className="mt-4">
                                {preprocessingSummary.is_already_preprocessed ? (
                                  <div className="bg-white dark:bg-slate-900/70 rounded-lg p-4 border border-green-200 dark:border-slate-700">
                                    <p className="text-sm text-green-800 dark:text-green-300 font-medium mb-2">✅ Data appears to be already preprocessed.</p>
                                    <ul className="text-xs text-gray-700 dark:text-gray-200 space-y-1">
                                      <li>✓ No missing values detected</li>
                                      <li>✓ No categorical variables found</li>
                                      <li>✓ All features are numeric and normalized</li>
                                      <li>✓ No constant variables detected</li>
                                    </ul>
                                    <p className="text-xs text-gray-600 dark:text-gray-300 mt-2">No additional preprocessing required.</p>
                                  </div>
                                ) : (
                                  <div className="bg-white dark:bg-slate-900/70 rounded-lg border border-gray-200 dark:border-slate-700 max-h-96 overflow-y-auto">
                                    <div className="p-4 space-y-4">
                                      {preprocessingSummary.variables?.map((variable: any, idx: number) => (
                                        <div key={idx} className="border-b border-gray-200 dark:border-slate-700 pb-4 last:border-b-0 last:pb-0">
                                          <h6 className="font-semibold text-gray-900 dark:text-white mb-2">VARIABLE: {variable.variable}</h6>
                                          
                                          {variable.missing_imputation && (
                                            <div className="ml-4 mb-2">
                                              <div className="flex items-start space-x-2">
                                                <span className="text-green-600">✓</span>
                                                <div>
                                                  <p className="text-sm font-medium text-gray-800 dark:text-gray-200">Missing Value Imputation</p>
                                                  <p className="text-xs text-gray-600 dark:text-gray-300">Reason: {variable.missing_imputation.reason}</p>
                                                  <p className="text-xs text-gray-500 dark:text-gray-400">Method: {variable.missing_imputation.method === 'median' ? `Median = ${variable.missing_imputation.value}` : `Mode = "${variable.missing_imputation.value}"`}</p>
                                                </div>
                                              </div>
                                            </div>
                                          )}
                                          
                                          {variable.encoding && (
                                            <div className="ml-4 mb-2">
                                              <div className="flex items-start space-x-2">
                                                <span className="text-green-600">✓</span>
                                                <div>
                                                  <p className="text-sm font-medium text-gray-800 dark:text-gray-200">Label Encoding Applied</p>
                                                  <p className="text-xs text-gray-600 dark:text-gray-300">Reason: {variable.encoding.reason}</p>
                                                  {variable.encoding.mapping_sample && (
                                                    <p className="text-xs text-gray-500 dark:text-gray-400">
                                                      Transformation: {Object.entries(variable.encoding.mapping_sample).slice(0, 3).map(([k, v]) => `"${k}"→${v}`).join(', ')}
                                                      {Object.keys(variable.encoding.mapping_sample).length > 3 ? '...' : ''}
                                                    </p>
                                                  )}
                                                </div>
                                              </div>
                                            </div>
                                          )}
                                          
                                          {variable.scaling && (
                                            <div className="ml-4 mb-2">
                                              <div className="flex items-start space-x-2">
                                                <span className="text-green-600">✓</span>
                                                <div>
                                                  <p className="text-sm font-medium text-gray-800 dark:text-gray-200">Standard Scaling Applied</p>
                                                  <p className="text-xs text-gray-600 dark:text-gray-300">Reason: {variable.scaling.reason}</p>
                                                  {variable.scaling.original_range && variable.scaling.scaled_range && (
                                                    <p className="text-xs text-gray-500 dark:text-gray-400">
                                                      Transformation: [{variable.scaling.original_range[0].toFixed(1)}, {variable.scaling.original_range[1].toFixed(1)}] → [{variable.scaling.scaled_range[0].toFixed(2)}, {variable.scaling.scaled_range[1].toFixed(2)}]
                                                    </p>
                                                  )}
                                                </div>
                                              </div>
                                            </div>
                                          )}
                                        </div>
                                      ))}
                                      
                                      {preprocessingSummary.dropped_variables?.map((dropped: any, idx: number) => (
                                        <div key={idx} className="border-b border-gray-200 pb-4 last:border-b-0 last:pb-0">
                                          <h6 className="font-semibold text-gray-900 mb-2">VARIABLE: {dropped.variable}</h6>
                                          <div className="ml-4">
                                            <div className="flex items-start space-x-2">
                                              <span className="text-red-600">✗</span>
                                              <div>
                                                <p className="text-sm font-medium text-red-800">DROPPED</p>
                                                <p className="text-xs text-gray-600">Reason: {dropped.reason}</p>
                                                {dropped.details && (
                                                  <p className="text-xs text-gray-500">Details: {dropped.details}</p>
                                                )}
                                              </div>
                                            </div>
                                          </div>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                
                                <div className="mt-3 pt-3 border-t border-gray-200">
                                  <p className="text-sm text-gray-700">
                                    📊 Summary: {preprocessingSummary.total_processed || 0} variables processed | {preprocessingSummary.total_dropped || 0} variables dropped
                                  </p>
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    ) : null;
                  })()}
                  <div className="mb-4">
                    <div className="text-sm font-medium mb-1">Overall Progress</div>
                    <div className="w-full bg-gray-200 rounded h-3 overflow-hidden">
                      <div className="bg-blue-600 h-3" style={{ width: `${multiOverallProgress}%` }} />
                    </div>
                  </div>
                  {lastUsedVariables.length > 0 && (
                    <div className="mb-4 text-xs text-green-700 flex items-center space-x-2">
                      <span className="inline-block w-2 h-2 bg-green-600 rounded-full" />
                      <span>Model trained on {lastUsedVariables.length} variables selected from the screener.</span>
                    </div>
                  )}

                  {/* Segment Manual Training Filters */}
                  {trainingResults && trainingResults.segment_results && (
                    <div className="mb-6 bg-white border border-purple-200 rounded-lg p-4">
                      <div className="flex items-center space-x-2 mb-3">
                        <Filter className="h-4 w-4 text-purple-600" />
                        <h5 className="font-medium text-gray-900">Filter Results</h5>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {/* Algorithm Filter */}
                        <div>
                          <label className="text-sm font-medium text-gray-900 flex items-center space-x-2 mb-2">
                            <Settings className="h-4 w-4 text-purple-600" />
                            <span>Filter by Algorithm:</span>
                          </label>
                          <select
                            value={selectedSegmentAlgorithmFilter}
                            onChange={(e) => setSelectedSegmentAlgorithmFilter(e.target.value)}
                            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 bg-white"
                          >
                            <option value="all">🔧 All Algorithms</option>
                            {Array.from(new Set(
                              Object.values(trainingResults.segment_results || {})
                                .flatMap((segResult: any) => 
                                  segResult.results?.map((r: any) => r.algorithm) || []
                                )
                            )).map((algorithm: any) => (
                              <option key={algorithm} value={algorithm}>
                                🤖 {algorithm.toUpperCase()}
                              </option>
                            ))}
                          </select>
                        </div>

                        {/* Segment Filter */}
                        <div>
                          <label className="text-sm font-medium text-gray-900 flex items-center space-x-2 mb-2">
                            <Filter className="h-4 w-4 text-purple-600" />
                            <span>Filter by Segment:</span>
                          </label>
                          <select
                            value={selectedSegmentManualFilter}
                            onChange={(e) => setSelectedSegmentManualFilter(e.target.value)}
                            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 bg-white"
                          >
                            <option value="all">📊 All Segments</option>
                            {trainingResults.segments?.map((seg: string) => (
                              <option key={seg} value={seg}>
                                🎯 Segment: {seg}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>
                      
                      <div className="text-xs text-gray-600 mt-3 p-2 bg-gray-50 rounded">
                        {selectedSegmentAlgorithmFilter === 'all' && selectedSegmentManualFilter === 'all' 
                          ? 'Showing all results from all segments and algorithms'
                          : `Showing ${selectedSegmentAlgorithmFilter === 'all' ? 'all algorithms' : selectedSegmentAlgorithmFilter.toUpperCase()} 
                             for ${selectedSegmentManualFilter === 'all' ? 'all segments' : `segment ${selectedSegmentManualFilter}`}`
                        }
                      </div>
                    </div>
                  )}

                  {/* Per-algorithm performance cards (same role as auto "All Models Performance"; hidden per product request) */}
                  {false && (() => {
                    // Determine which results to use (manual or auto training)
                    const results = trainingResults || autoTrainingResults;
                    
                    // Filter results based on selected filters for segment training
                    let filteredResults = results.results || [];
                    
                    if (trainingResults && trainingResults.segment_results) {
                      // For segment training, apply filters
                      filteredResults = [];
                      
                      Object.entries(trainingResults.segment_results).forEach(([segmentKey, segmentResult]: [string, any]) => {
                        const segmentId = segmentKey.replace('segment_', '');
                        
                        // Apply segment filter
                        if (selectedSegmentManualFilter !== 'all' && segmentId !== selectedSegmentManualFilter) {
                          return;
                        }
                        
                        if (segmentResult.results) {
                          segmentResult.results.forEach((r: any) => {
                            // Apply algorithm filter
                            if (selectedSegmentAlgorithmFilter !== 'all' && r.algorithm !== selectedSegmentAlgorithmFilter) {
                              return;
                            }
                            
                            // Add segment info to result
                            filteredResults.push({
                              ...r,
                              segment_id: segmentId,
                              segment_key: segmentKey
                            });
                          });
                        }
                      });
                    }
                    
                    return filteredResults.map((r: any, idx: number) => {
                      const pt = results.problem_type;
                      const scoreKey = getPrimaryMetricKey(pt, targetMetricManual);
                      const cv = Array.isArray(r.cv_scores) ? r.cv_scores : [];
                    const meanCv = cv.length ? (cv.reduce((a:number,b:number)=>a+b,0)/cv.length) : undefined;
                    const algorithmName = r.algorithm as string;
                    // If result exists with metrics, it's completed; otherwise check algoStatus
                    const status = (r && r.metrics && Object.keys(r.metrics).length > 0) 
                      ? 'completed' 
                      : ((algoStatus as Record<string, string>)[algorithmName] || 'running');
                      const segmentId = r.segment_id;
                      
                    return (
                      <div key={idx} className="border rounded-lg p-4 bg-gray-50 mb-3">
                        <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center space-x-2">
                          <div className="text-sm font-semibold">{String(algorithmName).toUpperCase()}</div>
                              {segmentId && (
                                <span className="text-xs bg-purple-100 text-purple-800 px-2 py-1 rounded-full">
                                  🎯 Segment: {segmentId}
                                </span>
                              )}
                            </div>
                          <span className={`text-xs px-2 py-1 rounded ${status==='completed'?'bg-green-100 text-green-700':'bg-gray-200 text-gray-700'}`}>{status}</span>
                        </div>
                        <div className="flex justify-between text-sm text-gray-700">
                          <div>Best ({getMetricDisplayName(scoreKey)}): <span className="font-semibold">{getBestScoreFromHistory(r, targetMetricManual).toFixed(4)}</span></div>
                          {/* Best CV max hidden as requested */}
                          {/* <div>Best{cv.length ? ' (CV max)' : ''}: <span className="font-semibold">{bestCv.toFixed(4)}</span></div> */}
                        </div>
                        {/* Detailed metrics straight from backend for accuracy */}
                        {r.metrics && (() => {
                          // Define base metrics to display (exclude train/test variants)
                          const baseMetrics = trainingResults?.problem_type === 'regression'
                            ? ['r2', 'adjusted_r2', 'mae', 'mse', 'rmse']
                            : ['accuracy', 'auc', 'f1', 'precision', 'recall', 'log_loss', 'ks_statistic'];
                          
                          const filteredMetrics = baseMetrics.filter(k => r.metrics[k] !== undefined && r.metrics[k] !== null);
                          
                          if (filteredMetrics.length === 0) return null;
                          
                          return (
                            <div className="mt-3 grid grid-cols-2 md:grid-cols-3 gap-2 text-xs text-gray-700">
                              {filteredMetrics.map((k) => {
                                const v = r.metrics[k];
                                return (
                                  <div key={k} className="flex justify-between bg-white border rounded px-2 py-1">
                                    <span className="font-medium">
                                      {getMetricDisplayName(k)}
                                    </span>
                                    <span className="ml-2">{typeof v === 'number' ? v.toFixed(4) : String(v)}</span>
                                  </div>
                                );
                              })}
                              {meanCv !== undefined && (
                                <div className="flex justify-between bg-white border rounded px-2 py-1">
                                  <span className="font-medium">cv mean</span>
                                  <span className="ml-2">{meanCv.toFixed(4)}</span>
                                </div>
                              )}
                            </div>
                          );
                        })()}
                        {(r.model_id || r.artifact_path) && (
                          <div className="mt-3 text-xs text-gray-600">
                            {r.model_id && <div className="mb-1">Model ID: <span className="font-mono">{r.model_id}</span></div>}
                            {r.artifact_path && <div className="mb-1">Artifact: <span className="font-mono break-all">{r.artifact_path}</span></div>}
                          </div>
                        )}
                        {Array.isArray(results.used_features) && results.used_features.length > 0 && (
                          <div className="mt-2 text-xs text-gray-600">
                            Features used: <span className="font-mono">{results.used_features.join(', ')}</span>
                          </div>
                        )}
                      </div>
                    );
                  });
                  })()}

                  <MtaPreStep6TrainingViz
                    viz={mtaPreStep6VizResults}
                    isDarkMode={isDarkMode}
                    targetMetricManual={targetMetricManual}
                    selectedAlgorithmForHistory={selectedAlgorithmForHistory}
                    setSelectedAlgorithmForHistory={setSelectedAlgorithmForHistory}
                    selectedSegmentForHistory={selectedSegmentForHistory}
                    setSelectedSegmentForHistory={setSelectedSegmentForHistory}
                    comparisonTab={comparisonTab}
                    setComparisonTab={setComparisonTab}
                    comparisonAlgorithmFilter={comparisonAlgorithmFilter}
                    setComparisonAlgorithmFilter={setComparisonAlgorithmFilter}
                    comparisonSegmentFilter={comparisonSegmentFilter}
                    setComparisonSegmentFilter={setComparisonSegmentFilter}
                    selectedAlgorithmsForComparison={selectedAlgorithmsForComparison}
                    setSelectedAlgorithmsForComparison={setSelectedAlgorithmsForComparison}
                    getAvailableMetrics={getAvailableMetrics}
                    getScoreComparisonData={getScoreComparisonData}
                    getTrainingHistoryData={getTrainingHistoryData}
                    getSelectedAlgorithms={getSelectedAlgorithms}
                    getPrimaryMetricKey={getPrimaryMetricKey}
                    getMetricDisplayName={getMetricDisplayName}
                    getBestScoreFromHistory={getBestScoreFromHistory}
                  />

                  {(() => {
                    const results = trainingResults || autoTrainingResults;
                    const step6Views = getStep6ViewsForDisplay(results);
                    if (!step6Views) return null;

                    const baseRows = Array.isArray(step6Views.base_model_results) ? step6Views.base_model_results : [];
                    const bayesianRows = Array.isArray(step6Views.bayesian_summary) ? step6Views.bayesian_summary : [];
                    const rec = step6Views.recommendations || {};
                    const g1Rows = Array.isArray(rec.g1_overfit_aware) ? rec.g1_overfit_aware : [];
                    const g2Rows = Array.isArray(rec.g2_test_only) ? rec.g2_test_only : [];
                    const lrRows = Array.isArray(rec.lr_sign_validation) ? rec.lr_sign_validation : [];
                    const lrBackwardReport = step6Views?.lr_backward_elimination_report;
                    const displayLrBackwardReportManual = step6LrInteractiveReport ?? lrBackwardReport;

                    const hasData =
                      baseRows.length > 0 ||
                      bayesianRows.length > 0 ||
                      g1Rows.length > 0 ||
                      g2Rows.length > 0 ||
                      lrRows.length > 0 ||
                      !!lrBackwardReport;
                    if (!hasData) return null;

                    return (
                      <div className={`mt-6 ${MTA_SECTION} p-5 md:p-6 bg-gradient-to-br from-blue-50/90 via-white to-indigo-50/50 dark:from-slate-900 dark:via-slate-900 dark:to-slate-800`}>
                        <div className="flex flex-wrap items-center gap-3 mb-4">
                          <span className={MTA_STEP_NUM} title="Step 6">
                            6
                          </span>
                          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-blue-500/15 dark:bg-blue-500/20 ring-1 ring-blue-300/50">
                            <BarChart3 className="h-6 w-6 text-blue-700 dark:text-blue-200" />
                          </div>
                          <h4 className={MTA_TITLE_SECTION}>Step 6 — Training insights</h4>
                        </div>

                        {baseRows.length > 0 && (
                          <div className="mb-5">
                            <div className="flex items-center justify-between mb-1">
                              <div className="text-sm font-semibold text-gray-900 dark:text-white">Iteration 0: Base models (default hyperparameters)</div>
                              <div className="text-[11px] font-medium px-2 py-1 rounded-full bg-blue-50 text-blue-700 border border-blue-100 dark:bg-blue-900/30 dark:text-blue-200 dark:border-blue-800">
                                {baseRows.length} base models
                              </div>
                            </div>
                            
                            <div className={`overflow-x-auto ${MTA_TABLE_SHELL}`}>
                              <table className="w-full min-w-[980px] table-fixed text-xs">
                                <thead className={MTA_THEAD}>
                                  <tr>
                                    <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">ALGORITHM</th>
                                    <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">AUC (TR)</th>
                                    <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">AUC (TE)</th>
                                    <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">KS (TR)</th>
                                    <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">KS (TE)</th>
                                    <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">GINI (TR)</th>
                                    <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">GINI (TE)</th>
                                    <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">OVERFIT</th>
                                    <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">NON-ZERO</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-200 dark:divide-slate-700">
                                  {baseRows.slice(0, 20).map((row: any, idx: number) => {
                                    const baseMetrics = row?.base_metrics || {};
                                    const recRow = g2Rows.find((r: any) =>
                                      String(r?.model_id || '') === String(row?.model_id || '') ||
                                      (
                                        String(r?.algorithm || '').toLowerCase() === String(row?.algorithm || '').toLowerCase() &&
                                        String(r?.segment_id || '') === String(row?.segment_id || '')
                                      )
                                    ) || {};
                                    const aucTr = getFirstFiniteMetric(baseMetrics, ['train_auc', 'auc']) ?? getFirstFiniteMetric(recRow, ['train_score']);
                                    const aucTe = getFirstFiniteMetric(baseMetrics, ['test_auc', 'auc']) ?? getFirstFiniteMetric(recRow, ['score']) ?? getFirstFiniteMetric(row, ['base_score']);
                                    const ksTr = getFirstFiniteMetric(baseMetrics, ['train_ks_statistic', 'ks_statistic']);
                                    const ksTe = getFirstFiniteMetric(baseMetrics, ['test_ks_statistic', 'ks_statistic']);
                                    const giniTr = getFirstFiniteMetric(baseMetrics, ['train_gini']) ?? (aucTr !== null ? (2 * aucTr - 1) : null);
                                    const giniTe = getFirstFiniteMetric(baseMetrics, ['test_gini']) ?? (aucTe !== null ? (2 * aucTe - 1) : null);
                                    const overfitPct = getFirstFiniteMetric(baseMetrics, ['overfit_pct']) ?? calcStep6OverfitPct(aucTr, aucTe);
                                    const bundleUF = resolveTrainingBundleUsedFeatures(results, row?.segment_id);
                                    const totalFeat =
                                      getFirstFiniteMetric(baseMetrics, ['feature_count']) ??
                                      getFirstFiniteMetric(recRow, ['feature_count']) ??
                                      (Array.isArray(bundleUF) ? bundleUF.length : null);
                                    const nzFeat =
                                      resolveNonzeroFeatureCount(
                                        { ...row, used_features: row.used_features ?? bundleUF },
                                        { ...baseMetrics, ...(recRow && typeof recRow === 'object' ? recRow : {}) },
                                        bundleUF,
                                      ) ??
                                      getFirstFiniteMetric(baseMetrics, ['feature_importance_count']) ??
                                      getFirstFiniteMetric(recRow, ['feature_importance_count']);
                                    const nonZeroLabel = formatStep6NonZeroRatio(nzFeat, totalFeat);

                                    return (
                                      <tr key={`base_${idx}`} className="bg-white dark:bg-slate-950 hover:bg-gray-50 dark:hover:bg-slate-900/70">
                                        <td className="px-3 py-2.5 text-gray-900 dark:text-white whitespace-nowrap">{String(row.algorithm || '-')}</td>
                                        <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{formatStep6Number(aucTr)}</td>
                                        <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{formatStep6Number(aucTe)}</td>
                                        <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{formatStep6Number(ksTr, 3)}</td>
                                        <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{formatStep6Number(ksTe, 3)}</td>
                                        <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{formatStep6Number(giniTr, 3)}</td>
                                        <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{formatStep6Number(giniTe, 3)}</td>
                                        <td className={`px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap ${overfitPct !== null && overfitPct <= 10 ? 'text-green-700 dark:text-green-400 font-semibold' : ''}`}>
                                          {overfitPct !== null ? `${overfitPct.toFixed(2)}%` : 'N/A'}
                                        </td>
                                        <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{nonZeroLabel}</td>
                                      </tr>
                                    );
                                  })}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        )}

                        {baseRows.length > 0 && (
                          <Step6PipelineForkLrSection
                            pipelinePath={step6PipelinePath}
                            onPipelinePathChange={setStep6PipelinePath}
                            onRunLrElimination={() =>
                              runStep6InteractiveLrElimination({
                                results,
                                segmentId:
                                  trainingMode === 'segment-specific' && selectedSegmentManualFilter !== 'all'
                                    ? selectedSegmentManualFilter
                                    : undefined,
                              })
                            }
                            lrReport={displayLrBackwardReportManual}
                            trainingLrConfig={results?.training_configuration?.lr_backward_elimination}
                            startingFeatureCount={Array.isArray(results?.used_features) ? results.used_features.length : null}
                            liveLoading={step6LrInteractiveLoading}
                            liveError={step6LrInteractiveError}
                          />
                        )}

                        {bayesianRows.length > 0 && (
                          <div className="mb-5 border border-blue-200 dark:border-slate-700 rounded-lg p-4 bg-white dark:bg-slate-900/60">
                            <div className="flex items-center justify-between mb-1">
                              <div className="text-sm font-semibold text-gray-900 dark:text-white">Bayesian optimization summary (Optuna)</div>
                              <span className="text-[11px] px-2 py-1 rounded-full bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300 font-medium">Completed</span>
                            </div>
                            <div className="text-xs text-gray-600 dark:text-gray-300 mb-3">
                              Objective: max {String(bayesianRows[0]?.target_metric || 'AUC').toUpperCase()}. {bayesianRows[0]?.cv_folds ?? '-'} folds per algorithm.
                              {typeof bayesianRows[0]?.early_stopping_rounds === 'number' ? ` Early stopping: ${bayesianRows[0]?.early_stopping_rounds} rounds.` : ''}
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                              {bayesianRows.slice(0, 3).map((row: any, idx: number) => (
                                <div key={`bayes_card_${idx}`} className="border border-gray-200 dark:border-slate-700 rounded-lg p-3 bg-gray-50 dark:bg-slate-900/80">
                                  <div className="text-[10px] uppercase tracking-wide text-gray-500 dark:text-gray-400">{String(row.algorithm || '-')} trials</div>
                                  <div className="text-2xl font-semibold text-gray-900 dark:text-white">{row.trials_run ?? 0}</div>
                                  <div className="text-[11px] text-gray-500 dark:text-gray-400">
                                    {typeof row.configured_trials === 'number' && row.configured_trials > 0 && row.trials_run === row.configured_trials ? 'full budget' : `${row.configured_trials ?? 0} configured`}
                                  </div>
                                </div>
                              ))}
                              <div className="border border-green-300 dark:border-emerald-700 rounded-lg p-3 bg-green-50 dark:bg-emerald-950/40">
                                <div className="text-[10px] uppercase tracking-wide text-gray-500 dark:text-gray-400">Best test {String(bayesianRows[0]?.target_metric || 'AUC').toUpperCase()}</div>
                                <div className="text-2xl font-semibold text-green-700 dark:text-green-400">
                                  {formatStep6Number(
                                    bayesianRows.reduce((acc: number, r: any) => {
                                      const v = Number(r?.best_score);
                                      return Number.isFinite(v) ? Math.max(acc, v) : acc;
                                    }, -Infinity)
                                  )}
                                </div>
                                <div className="text-[11px] text-gray-500 dark:text-gray-400">
                                  {(() => {
                                    const bestRow = bayesianRows.reduce((acc: any, r: any) => {
                                      const v = Number(r?.best_score);
                                      if (!Number.isFinite(v)) return acc;
                                      if (!acc || v > Number(acc.best_score)) return r;
                                      return acc;
                                    }, null);
                                    if (!bestRow) return '-';
                                    return `${String(bestRow.algorithm || '-')} #${bestRow.best_iteration ?? '-'}`;
                                  })()}
                                </div>
                              </div>
                            </div>
                          </div>
                        )}

                        {(g1Rows.length > 0 || g2Rows.length > 0) && (
                          <div className="mb-5 border border-blue-200 dark:border-slate-700 rounded-lg p-4 bg-white dark:bg-slate-900/60">
                            <div className="text-sm font-semibold text-gray-900 dark:text-white mb-1">Model recommendations (max 2 per algorithm)</div>
                            <div className="text-xs text-gray-600 dark:text-gray-300 mb-3">G1: best test score with overfit &lt;= 10%. G2: best test score regardless.</div>
                            {(() => {
                              const modelLookup = new Map<string, any>();
                              const sourceRows: any[] = [];
                              if (Array.isArray(results?.results)) {
                                sourceRows.push(...results.results);
                              }
                              if (results?.segment_results && typeof results.segment_results === 'object') {
                                Object.entries(results.segment_results).forEach(([segmentKey, segPayload]: [string, any]) => {
                                  const segmentId = String(segmentKey || '').replace('segment_', '');
                                  (segPayload?.results || []).forEach((r: any) => sourceRows.push({ ...r, segment_id: segmentId }));
                                });
                              }
                              sourceRows.forEach((r: any) => {
                                const key = `${String(r?.model_id || '')}__${String(r?.segment_id || '')}`;
                                modelLookup.set(key, r);
                              });

                              const allRows = [
                                ...g1Rows.map((r: any) => ({ ...r, guideline: 'G1' })),
                                ...g2Rows.map((r: any) => ({ ...r, guideline: 'G2' })),
                              ];

                              const grouped = new Map<string, any[]>();
                              allRows.forEach((row: any) => {
                                const key = `${String(row.algorithm || '').toLowerCase()}__${String(row.segment_id || '')}`;
                                const arr = grouped.get(key) || [];
                                arr.push(row);
                                grouped.set(key, arr);
                              });

                              const recRows: any[] = [];
                              grouped.forEach((rows) => {
                                const sorted = [...rows].sort((a, b) => {
                                  const g = String(a.guideline).localeCompare(String(b.guideline));
                                  if (g !== 0) return g;
                                  return (Number(b.score) || -Infinity) - (Number(a.score) || -Infinity);
                                });
                                recRows.push(...sorted.slice(0, 2));
                              });

                              if (recRows.length === 0) return null;

                              return (
                                <div className={`overflow-x-auto ${MTA_TABLE_SHELL}`}>
                                  <table className="w-full min-w-[980px] table-fixed text-xs">
                                    <thead className={MTA_THEAD}>
                                      <tr>
                                        <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">ALGORITHM</th>
                                        <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">GUIDELINE</th>
                                        <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">AUC (TR)</th>
                                        <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">AUC (TE)</th>
                                        <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">KS (TR)</th>
                                        <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">KS (TE)</th>
                                        <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">GINI (TR)</th>
                                        <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">GINI (TE)</th>
                                        <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">OVERFIT</th>
                                        <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">FEAT.</th>
                                        <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">FLAGS</th>
                                      </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-200 dark:divide-slate-700">
                                      {recRows.map((row: any, idx: number) => {
                                        const model = modelLookup.get(`${String(row?.model_id || '')}__${String(row?.segment_id || '')}`) || {};
                                        const metrics = model?.metrics || {};
                                        const aucTr = getFirstFiniteMetric(metrics, ['train_auc']) ?? getFirstFiniteMetric(row, ['train_score']);
                                        const aucTe = getFirstFiniteMetric(metrics, ['test_auc', 'auc']) ?? getFirstFiniteMetric(row, ['score']);
                                        const ksTr = getFirstFiniteMetric(metrics, ['train_ks_statistic', 'ks_statistic']);
                                        const ksTe = getFirstFiniteMetric(metrics, ['test_ks_statistic', 'ks_statistic']);
                                        const giniTr = getFirstFiniteMetric(metrics, ['train_gini']) ?? (aucTr !== null ? (2 * aucTr - 1) : null);
                                        const giniTe = getFirstFiniteMetric(metrics, ['test_gini']) ?? (aucTe !== null ? (2 * aucTe - 1) : null);
                                        const overfitPct = getFirstFiniteMetric(row, ['overfit_pct']) ?? getFirstFiniteMetric(metrics, ['overfit_pct']) ?? calcStep6OverfitPct(aucTr, aucTe);
                                        const bundleUF = resolveTrainingBundleUsedFeatures(results, row?.segment_id);
                                        const totalFeat =
                                          getFirstFiniteMetric(metrics, ['feature_count']) ??
                                          getFirstFiniteMetric(row, ['feature_count']) ??
                                          (Array.isArray(model?.used_features) ? model.used_features.length : null) ??
                                          (Array.isArray(bundleUF) ? bundleUF.length : null);
                                        const nzFeat =
                                          resolveNonzeroFeatureCount(model, { ...metrics, ...row }, bundleUF) ??
                                          getFirstFiniteMetric(metrics, ['feature_importance_count']) ??
                                          getFirstFiniteMetric(row, ['feature_importance_count']);
                                        const featDisplay = formatStep6NonZeroRatio(nzFeat, totalFeat);
                                        const flags = row?.is_recommended
                                          ? 'Best overall'
                                          : (overfitPct !== null && overfitPct > 10 ? 'Overfit >10%' : (String(row.algorithm || '').toLowerCase().includes('logistic') ? 'Post-elim' : '-'));

                                        return (
                                          <tr key={`rec_${idx}`} className={row.guideline === 'G1' ? 'bg-green-50 dark:bg-emerald-950/40 hover:bg-green-100/80 dark:hover:bg-emerald-950/55' : 'bg-white dark:bg-slate-950 hover:bg-gray-50 dark:hover:bg-slate-900/70'}>
                                            <td className="px-3 py-2.5 text-gray-900 dark:text-white whitespace-nowrap">{String(row.algorithm || '-')}</td>
                                            <td className="px-3 py-2.5 whitespace-nowrap">
                                              <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${row.guideline === 'G1' ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300' : 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-200'}`}>
                                                {row.guideline}
                                              </span>
                                            </td>
                                            <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{formatStep6Number(aucTr, 3)}</td>
                                            <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{formatStep6Number(aucTe, 3)}</td>
                                            <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{formatStep6Number(ksTr, 3)}</td>
                                            <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{formatStep6Number(ksTe, 3)}</td>
                                            <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{formatStep6Number(giniTr, 3)}</td>
                                            <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{formatStep6Number(giniTe, 3)}</td>
                                            <td className={`px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap ${overfitPct !== null && overfitPct <= 10 ? 'text-green-700 dark:text-green-400 font-semibold' : ''}`}>
                                              {overfitPct !== null ? `${overfitPct.toFixed(2)}%` : 'N/A'}
                                            </td>
                                            <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{featDisplay}</td>
                                            <td className="px-3 py-2.5 whitespace-nowrap">
                                              <span className="px-1.5 py-0.5 rounded text-[10px] bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-200">{flags}</span>
                                            </td>
                                          </tr>
                                        );
                                      })}
                                    </tbody>
                                  </table>
                                </div>
                              );
                            })()}
                          </div>
                        )}

                        {(g1Rows.length > 0 || g2Rows.length > 0) && (
                          <CrossAlgorithmRecommendationCard
                            datasetId={activeDatasetId ?? null}
                            problemType={String(results?.problem_type || 'classification')}
                            results={results}
                            g1Rows={g1Rows}
                            g2Rows={g2Rows}
                            lrRows={lrRows}
                            variant="manual"
                          />
                        )}

                        {lrRows.length > 0 && (
                          <div>
                            <div className="text-sm font-medium text-gray-800 dark:text-gray-200 mb-2">LR Sign Validation</div>
                            <div className={`overflow-x-auto ${MTA_TABLE_SHELL}`}>
                              <table className="w-full min-w-[980px] table-fixed text-xs">
                                <thead className={MTA_THEAD}>
                                  <tr>
                                    <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">Algorithm</th>
                                    <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">Segment</th>
                                    <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">Status</th>
                                    <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">Matched</th>
                                    <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">Mismatched</th>
                                    <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">Unknown</th>
                                    <th className="px-3 py-2.5 text-left font-semibold whitespace-nowrap">Details</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-200 dark:divide-slate-700">
                                  {lrRows.slice(0, 20).map((row: any, idx: number) => {
                                    const rowKey = `${row.model_id || idx}_${row.segment_id || 'all'}`;
                                    const hasDetails = Array.isArray(row.details) && row.details.length > 0;
                                    const isOpen = !!expandedLrSignRows[rowKey];

                                    return (
                                      <React.Fragment key={`lr_${rowKey}`}>
                                        <tr className="bg-white dark:bg-slate-950 hover:bg-gray-50 dark:hover:bg-slate-900/70">
                                          <td className="px-3 py-2.5 text-gray-900 dark:text-white whitespace-nowrap">{String(row.algorithm || '-').toUpperCase()}</td>
                                          <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{row.segment_id || '-'}</td>
                                          <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{row.status || '-'}</td>
                                          <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{row.matched_count ?? '-'}</td>
                                          <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{row.mismatched_count ?? '-'}</td>
                                          <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">{row.unknown_count ?? '-'}</td>
                                          <td className="px-3 py-2.5 text-gray-700 dark:text-gray-200 whitespace-nowrap">
                                            {hasDetails ? (
                                              <button
                                                type="button"
                                                onClick={() => setExpandedLrSignRows((prev) => ({ ...prev, [rowKey]: !prev[rowKey] }))}
                                                className="inline-flex items-center space-x-1 text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
                                              >
                                                <span>{isOpen ? 'Hide' : 'View'}</span>
                                                {isOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                                              </button>
                                            ) : (
                                              <span className="text-gray-400 dark:text-gray-500">-</span>
                                            )}
                                          </td>
                                        </tr>
                                        {isOpen && hasDetails && (
                                          <tr className="bg-gray-50 dark:bg-slate-900/80">
                                            <td className="px-3 py-2.5" colSpan={7}>
                                              <div className="overflow-x-auto rounded border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-950">
                                                <table className="w-full min-w-[640px] table-fixed text-xs">
                                                  <thead className={MTA_THEAD}>
                                                    <tr>
                                                      <th className="px-3 py-2 text-left font-semibold whitespace-nowrap">Feature</th>
                                                      <th className="px-3 py-2 text-left font-semibold whitespace-nowrap">Coeff</th>
                                                      <th className="px-3 py-2 text-left font-semibold whitespace-nowrap">Coeff Sign</th>
                                                      <th className="px-3 py-2 text-left font-semibold whitespace-nowrap">Bivariate Corr</th>
                                                      <th className="px-3 py-2 text-left font-semibold whitespace-nowrap">Corr Sign</th>
                                                      <th className="px-3 py-2 text-left font-semibold whitespace-nowrap">Status</th>
                                                    </tr>
                                                  </thead>
                                                  <tbody className="divide-y divide-gray-200 dark:divide-slate-700">
                                                    {row.details.slice(0, 30).map((d: any, didx: number) => (
                                                      <tr key={`${rowKey}_d_${didx}`} className="bg-white dark:bg-slate-950 hover:bg-gray-50 dark:hover:bg-slate-900/70">
                                                        <td className="px-3 py-2 text-gray-900 dark:text-white whitespace-nowrap">{d.feature || '-'}</td>
                                                        <td className="px-3 py-2 text-gray-700 dark:text-gray-200 whitespace-nowrap">{formatStep6Number(d.coefficient, 6)}</td>
                                                        <td className="px-3 py-2 text-gray-700 dark:text-gray-200 whitespace-nowrap">{d.coefficient_sign ?? '-'}</td>
                                                        <td className="px-3 py-2 text-gray-700 dark:text-gray-200 whitespace-nowrap">{formatStep6Number(d.bivariate_correlation, 6)}</td>
                                                        <td className="px-3 py-2 text-gray-700 dark:text-gray-200 whitespace-nowrap">{d.bivariate_sign ?? '-'}</td>
                                                        <td className="px-3 py-2 text-gray-700 dark:text-gray-200 whitespace-nowrap">{d.status || '-'}</td>
                                                      </tr>
                                                    ))}
                                                  </tbody>
                                                </table>
                                              </div>
                                            </td>
                                          </tr>
                                        )}
                                      </React.Fragment>
                                    );
                                  })}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })()}

                </div>
              )}
            </div>
          )}

          {/* Training History Tab (removed from screen) */}
          {false && (
            <div className="space-y-4">
              <div>
                <h4 className="font-medium text-gray-900 mb-2">Model Training History</h4>
                <p className="text-sm text-gray-600 mb-4">
                  View and compare previously trained models
                </p>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className={MTA_THEAD}>
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Model ID</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Algorithm</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">AUC</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">F1</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Precision</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Recall</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {modelHistory.map((model) => (
                      <tr key={model.modelId} className="hover:bg-gray-50 dark:hover:bg-slate-800 transition-colors">
                        <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                          {model.isStarred && '⭐ '}{model.modelId}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{model.algorithm}</td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 font-medium">{model.auc.toFixed(3)}</td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{model.f1.toFixed(3)}</td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{model.precision.toFixed(3)}</td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{model.recall.toFixed(3)}</td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                            model.status === 'Production' 
                              ? 'bg-green-100 text-green-800' 
                              : model.status === 'Baseline'
                              ? 'bg-gray-100 text-gray-800'
                              : 'bg-blue-100 text-blue-800'
                          }`}>
                            {model.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm">
                          <div className="flex space-x-2">
                            <button
                              className="text-blue-600 hover:text-blue-800 transition-colors"
                              title="Download"
                            >
                              <Download className="h-4 w-4" />
                            </button>
                            <button
                              className="text-purple-600 hover:text-purple-800 transition-colors"
                              title="View Details"
                            >
                              <FileText className="h-4 w-4" />
                            </button>
                            <button
                              className="text-green-600 hover:text-green-800 transition-colors"
                              title="Deploy"
                            >
                              <Rocket className="h-4 w-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="flex space-x-3">
                <button className="px-4 py-2 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] transition-colors flex items-center space-x-2">
                  <BarChart3 className="h-4 w-4" />
                  <span>Compare Selected Models</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Training Progress (shown when training) */}
      {isMultiTraining && (
        <div className="bg-white rounded-lg border-2 border-blue-300 shadow-lg p-6">
          <div className="flex flex-col items-center justify-center text-center">
            <h4 className="font-semibold text-gray-900 flex items-center space-x-2 mb-3">
              <Brain className="h-6 w-6 text-blue-600 animate-pulse" />
              <span>Training in Progress{animatedDots}</span>
            </h4>
            <p className="text-sm text-gray-600">
              Please wait while models are being trained...
            </p>
          </div>
        </div>
      )}

      {/* Training Results (shown after completion) - Only for Auto Training */}
      {showResults && !isTraining && !isMultiTraining && trainingResults && trainingResults.optimization_method && (
        <div className="bg-white rounded-lg border-2 border-green-300 shadow-lg p-6">
          <div className="flex items-center space-x-3 mb-6">
            <div className="p-3 bg-green-600 rounded-full">
              <CheckCircle className="h-8 w-8 text-white" />
            </div>
            <div>
              <h4 className="text-xl font-bold text-gray-900">✅ Training Complete!</h4>
              <p className="text-sm text-gray-600">
                Model ID: {trainingResults.model_id} | 
                Problem Type: {trainingResults.problem_type} | 
                Time: {trainingResults.training_time_seconds}s | 
                Method: {trainingResults.optimization_method}
                {trainingResults.selected_algorithm && ` | Algorithm: ${trainingResults.selected_algorithm}`}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            {/* User Defined Metric */}
            <div className="bg-gradient-to-br from-purple-50 to-pink-50 rounded-lg p-4 border border-purple-200">
              <h5 className="font-semibold text-gray-900 mb-4 flex items-center space-x-2">
                <Activity className="h-5 w-5 text-purple-600" />
                <span>Target Metric Achievement</span>
              </h5>
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-700 font-medium">Target {trainingResults.user_defined_metric.metric_name}:</span>
                  <span className="text-lg font-bold text-purple-900">
                    {trainingResults.user_defined_metric.target_value.toFixed(4)}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-700 font-medium">Achieved {trainingResults.user_defined_metric.metric_name}:</span>
                  <span className="text-lg font-bold text-green-900">
                    {trainingResults.user_defined_metric.achieved_value.toFixed(4)}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-700 font-medium">Difference:</span>
                  <span className={`text-lg font-bold ${trainingResults.user_defined_metric.difference <= 0.05 ? 'text-green-900' : 'text-orange-900'}`}>
                    {trainingResults.user_defined_metric.difference.toFixed(4)}
                  </span>
                </div>
                <div className="pt-2 border-t border-purple-200">
                  <div className="flex items-center space-x-2 p-3 bg-green-100 rounded-lg border border-green-300">
                    <CheckCircle className="h-5 w-5 text-green-700 flex-shrink-0" />
                    <span className="text-sm text-green-800 font-medium">
                      {trainingResults.user_defined_metric.difference <= 0.05 ? 'Target achieved!' : 'Close to target'}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Cross-Validation Scores */}
            <div className="bg-gradient-to-br from-green-50 to-emerald-50 rounded-lg p-4 border border-green-200">
              <h5 className="font-semibold text-gray-900 mb-4 flex items-center space-x-2">
                <AlertCircle className="h-5 w-5 text-green-600" />
                <span>Cross-Validation Results</span>
              </h5>
              <div className="space-y-3">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-700">Mean Score:</span>
                  <span className="font-bold text-gray-900">
                    {(trainingResults.cross_validation_scores.reduce((a: number, b: number) => a + b, 0) / trainingResults.cross_validation_scores.length).toFixed(4)}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-700">Std Deviation:</span>
                  <span className="font-bold text-gray-900">
                    {Math.sqrt(trainingResults.cross_validation_scores.reduce((sq: number, n: number) => sq + Math.pow(n - (trainingResults.cross_validation_scores.reduce((a: number, b: number) => a + b, 0) / trainingResults.cross_validation_scores.length), 2), 0) / trainingResults.cross_validation_scores.length).toFixed(4)}
                  </span>
                </div>
                <div className="text-xs text-gray-600 bg-white rounded p-2">
                  <strong>Fold Results:</strong> [{trainingResults.cross_validation_scores.map((r: number) => r.toFixed(3)).join(', ')}]
                </div>
              </div>
            </div>

            {/* Model Artifact */}
            <div className="bg-gradient-to-br from-amber-50 to-orange-50 rounded-lg p-4 border border-amber-200">
              <h5 className="font-semibold text-gray-900 mb-4">Model Artifact</h5>
              <div className="space-y-3">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-700">Artifact Path:</span>
                  <span className="font-bold text-gray-900 text-xs">{trainingResults.artifact_path}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-700">Training Time:</span>
                  <span className="font-bold text-gray-900">{trainingResults.training_time_seconds}s</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-700">Optimization Method:</span>
                  <span className="font-bold text-gray-900 capitalize">{trainingResults.optimization_method}</span>
                </div>
                {trainingResults.selected_algorithm && (
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-700">Selected Algorithm:</span>
                    <span className="font-bold text-gray-900 capitalize">{trainingResults.selected_algorithm}</span>
                  </div>
                )}
                {trainingResults.hyperparameters && Object.keys(trainingResults.hyperparameters).length > 0 && (
                  <div className="pt-2 border-t border-amber-200">
                    <div className="text-xs text-gray-600 mb-2">
                      <strong>Hyperparameters:</strong>
                    </div>
                    <div className="text-xs text-gray-600 bg-white rounded p-2 max-h-20 overflow-y-auto">
                      {Object.entries(trainingResults.hyperparameters).map(([key, value]) => (
                        <div key={key} className="flex justify-between">
                          <span className="font-medium">{key}:</span>
                          <span>{String(value)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Feature Importance - REMOVED */}

          {/* Action Buttons - Only Download Model & Artifacts */}
          <div className="flex flex-wrap gap-3">
            {/* Hidden: View Full Explainability Report (SHAP, PDP) */}
            {/* Hidden: Deploy to Production */}
            {/* Hidden: Generate Model Card */}
            {/* Hidden: Train Another Model */}
            
            {/* Download Button with Dropdown */}
            <div className="relative download-dropdown">
              <button 
                onClick={() => setShowDownloadMenu(!showDownloadMenu)}
                className="px-4 py-2 border-2 border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-all flex items-center space-x-2 font-medium"
              >
                <Download className="h-4 w-4" />
                <span>Download Model & Artifacts</span>
                <ChevronDown className="h-4 w-4" />
              </button>
              
              {showDownloadMenu && (
                <div className="absolute top-full left-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-10 min-w-48">
                  <button 
                    onClick={() => { handleDownloadArtifacts('csv'); setShowDownloadMenu(false); }}
                    className="w-full px-4 py-2 text-left hover:bg-gray-50 flex items-center space-x-2 border-b border-gray-100"
                  >
                    <FileText className="h-4 w-4 text-green-600" />
                    <span>Download as CSV</span>
                  </button>
                  <button 
                    onClick={() => { handleDownloadArtifacts('excel'); setShowDownloadMenu(false); }}
                    className="w-full px-4 py-2 text-left hover:bg-gray-50 flex items-center space-x-2 border-b border-gray-100"
                  >
                    <FileText className="h-4 w-4 text-green-600" />
                    <span>Download as Excel</span>
                  </button>
                  <button 
                    onClick={() => { handleDownloadArtifacts('txt'); setShowDownloadMenu(false); }}
                    className="w-full px-4 py-2 text-left hover:bg-gray-50 flex items-center space-x-2"
                  >
                    <FileText className="h-4 w-4 text-blue-600" />
                    <span>Download as TXT Report</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Variable Shortlist Drawer */}
      {showShortlistDrawer && (
        <div className="fixed inset-0 z-40">
          <div className="absolute inset-0 bg-black bg-opacity-30" onClick={() => setShowShortlistDrawer(false)} />
          <div className="absolute right-0 top-0 h-full w-full max-w-xl bg-white shadow-xl z-50 flex flex-col">
            <div className="p-4 border-b flex items-center justify-between">
              <h4 className="font-semibold text-gray-900">Variable Shortlist</h4>
              <button onClick={() => setShowShortlistDrawer(false)} className="text-gray-500 hover:text-gray-700">Close</button>
            </div>
            <div className="p-4 flex-1 overflow-auto">
              <div className="text-sm text-gray-600 mb-2">Add/remove variables and then run training on the final list.</div>
              <div className="flex items-center space-x-2 mb-3">
                <input
                  type="text"
                  placeholder="Add variable by name..."
                  className="flex-1 px-3 py-2 border rounded"
                  onKeyDown={(e)=>{
                    const input = e.currentTarget as HTMLInputElement;
                    if(e.key==='Enter' && input.value.trim()){
                      setManualSelectedIndependentVariables(prev => Array.from(new Set([...prev, input.value.trim()])));
                      input.value='';
                    }
                  }}
                />
                <button
                  className="px-3 py-2 border rounded"
                  onClick={()=>setManualSelectedIndependentVariables(filteredVariables)}
                >Use Filtered</button>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {manualSelectedIndependentVariables.map(v => (
                  <div key={v} className="flex items-center justify-between border rounded px-2 py-1">
                    <span className="text-sm text-gray-800 truncate mr-2">{v}</span>
                    <button
                      className="text-red-600 text-xs"
                      onClick={()=> setManualSelectedIndependentVariables(prev => prev.filter(x=>x!==v))}
                    >Remove</button>
                  </div>
                ))}
              </div>
            </div>
            <div className="p-4 border-t flex items-center justify-between">
              <div className="text-sm text-gray-600">{manualSelectedIndependentVariables.length} variables selected</div>
              <button
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                onClick={()=>{ setShowShortlistDrawer(false); /* training will use manualSelectedIndependentVariables */ }}
              >Save & Close</button>
            </div>
          </div>
        </div>
      )}

      {/* CodeBook Modal */}
      {isCodebookOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black bg-opacity-50" onClick={() => setIsCodebookOpen(false)} />
          <div className="relative bg-white rounded-lg shadow-2xl w-full max-w-6xl max-h-[90vh] flex flex-col">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-4 border-b border-gray-200 bg-gradient-to-r from-blue-600 to-indigo-600">
              <div className="flex items-center space-x-3">
                <FileText className="h-6 w-6 text-white" />
                <div>
                  <h3 className="text-xl font-bold text-white">CodeBook</h3>
                  <p className="text-xs text-blue-100">{codebookFileName}</p>
                </div>
              </div>
              <button
                onClick={() => setIsCodebookOpen(false)}
                className="text-white hover:text-gray-200 transition-colors p-2 hover:bg-white/10 rounded"
              >
                <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Modal Body */}
            <div className="flex-1 overflow-auto p-4 bg-gray-50">
              {isLoadingCodebook ? (
                <div className="flex items-center justify-center h-64">
                  <Loader className="h-8 w-8 text-blue-600 animate-spin" />
                  <span className="ml-3 text-gray-600">Loading source code...</span>
                </div>
              ) : (
                <div className="bg-gray-900 rounded-lg overflow-hidden">
                  <pre className="text-xs text-gray-100 p-4 overflow-x-auto leading-relaxed font-mono">
                    <code>{codebookContent}</code>
                  </pre>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t border-gray-200 bg-gray-50 flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <div className="text-sm text-gray-600">
                  <span className="font-medium">Mode:</span> {trainingMode === 'global' ? 'Global Model' : 'Segment-Specific Model'} → 
                  <span className="font-medium ml-1">Type:</span> {activeTab === 'auto' ? 'Auto Training' : 'Manual Configuration'}
                </div>
              </div>
              <div className="flex items-center space-x-2">
                {/* Download as Python (.py) */}
                <button
                  onClick={() => {
                    const blob = new Blob([codebookContent], { type: 'text/x-python' });
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = codebookFileName;
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);
                  }}
                  className="px-3 py-2 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] text-sm rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] transition-colors flex items-center space-x-1"
                  title="Download as Python file"
                >
                  <Download className="h-4 w-4" />
                  <span>.py</span>
                </button>

                {/* Download as IPYNB (Jupyter Notebook) */}
                <button
                  onClick={() => {
                    const notebookContent = {
                      cells: [{
                        cell_type: 'code',
                        execution_count: null,
                        metadata: {},
                        outputs: [],
                        source: codebookContent.split('\n')
                      }],
                      metadata: {
                        kernelspec: {
                          display_name: 'Python 3',
                          language: 'python',
                          name: 'python3'
                        },
                        language_info: {
                          name: 'python',
                          version: '3.8.0'
                        }
                      },
                      nbformat: 4,
                      nbformat_minor: 4
                    };
                    const blob = new Blob([JSON.stringify(notebookContent, null, 2)], { type: 'application/json' });
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = codebookFileName.replace('.py', '.ipynb');
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);
                  }}
                  className="px-3 py-2 bg-orange-600 text-white text-sm rounded-lg hover:bg-orange-700 transition-colors flex items-center space-x-1"
                  title="Download as Jupyter Notebook"
                >
                  <Download className="h-4 w-4" />
                  <span>.ipynb</span>
                </button>

                {/* Close Button */}
                <button
                  onClick={() => setIsCodebookOpen(false)}
                  className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}


      {/* Post Modelling Dataset Preview */}
      {postModellingPreviewData && (() => {
        // Only show preview if results match current training mode
        if (trainingMode === 'global') {
          // Global mode: show only if results match current tab
          if (activeTab === 'manual') {
            // Global Manual: only show if trainingResults exists and NOT segment training
            return trainingResults && !trainingResults.segment_results;
          } else if (activeTab === 'auto') {
            // Global Auto: only show if autoTrainingResults exists
            return autoTrainingResults;
          }
        } else if (trainingMode === 'segment-specific') {
          // Segment mode: show only if results match current tab
          if (activeTab === 'manual') {
            // Segment Manual: only show if trainingResults has segment_results
            return trainingResults && trainingResults.segment_results;
          } else if (activeTab === 'auto') {
            // Segment Auto: only show if segmentAutoTrainingResults exists
            return segmentAutoTrainingResults;
          }
        }
        return false;
      })() && (
        <div className="bg-white rounded-lg border border-gray-200">
          <div className="flex items-center justify-between p-4 border-b border-gray-200">
            <div className="flex items-center space-x-2">
              <h4 className="font-semibold text-gray-900">Post Modelling Dataset Preview</h4>
              {showPostModellingPreview ? (
                <ChevronUp className="h-4 w-4 text-gray-500" />
              ) : (
                <ChevronDown className="h-4 w-4 text-gray-500" />
              )}
            </div>
            <button
              onClick={() => setShowPostModellingPreview(!showPostModellingPreview)}
              className="text-sm text-gray-500 hover:text-gray-700 transition-colors"
            >
              {showPostModellingPreview ? 'Hide' : 'Show'}
            </button>
          </div>
          
          {showPostModellingPreview && (() => {
            // Extract preprocessed columns from training results
            const getPreprocessedColumns = () => {
              // Try to get from training results (manual training - global)
              if (trainingResults?.used_features && Array.isArray(trainingResults.used_features)) {
                return trainingResults.used_features;
              }
              // Also check in results array for manual training
              if (trainingResults?.results && Array.isArray(trainingResults.results) && trainingResults.results.length > 0) {
                const firstResult = trainingResults.results[0];
                if (firstResult?.used_features && Array.isArray(firstResult.used_features)) {
                  return firstResult.used_features;
                }
              }
              
              // Try to get from auto training results (global)
              if (autoTrainingResults?.used_features && Array.isArray(autoTrainingResults.used_features)) {
                return autoTrainingResults.used_features;
              }
              
              // Try to get from segment auto training results
              if (segmentAutoTrainingResults) {
                // Check segment_results for used_features
                if (segmentAutoTrainingResults.segment_results) {
                  const firstSegmentKey = Object.keys(segmentAutoTrainingResults.segment_results)[0];
                  const firstSegmentResult = segmentAutoTrainingResults.segment_results[firstSegmentKey];
                  if (firstSegmentResult?.used_features && Array.isArray(firstSegmentResult.used_features)) {
                    return firstSegmentResult.used_features;
                  }
                }
                // Check unified_results
                if (segmentAutoTrainingResults.unified_results?.segments_data) {
                  const firstSegment = Object.values(segmentAutoTrainingResults.unified_results.segments_data)[0] as any;
                  if (firstSegment?.used_features && Array.isArray(firstSegment.used_features)) {
                    return firstSegment.used_features;
                  }
                }
              }
              
              // Try to get from segment manual training results
              if (trainingResults?.segment_results) {
                const firstSegmentKey = Object.keys(trainingResults.segment_results)[0];
                const firstSegmentResult = trainingResults.segment_results[firstSegmentKey];
                if (firstSegmentResult?.used_features && Array.isArray(firstSegmentResult.used_features)) {
                  return firstSegmentResult.used_features;
                }
                // Also check in results array
                if (firstSegmentResult?.results && Array.isArray(firstSegmentResult.results) && firstSegmentResult.results.length > 0) {
                  const firstResult = firstSegmentResult.results[0];
                  if (firstResult?.used_features && Array.isArray(firstResult.used_features)) {
                    return firstResult.used_features;
                  }
                }
              }
              
              return null;
            };

            const preprocessedColumns = getPreprocessedColumns();

            return (
              <div className="p-4">
                <div className="mb-4">
                  <div className="text-sm text-gray-600">
                    <strong>Dataset Shape:</strong> {postModellingPreviewData.shape.rows.toLocaleString()} rows × {postModellingPreviewData.shape.columns} columns
                  </div>
                </div>
                
                <div className="overflow-x-auto border border-gray-200 rounded-lg max-h-96">
                  <table className="w-full text-sm min-w-max">
                    <thead className={`${MTA_THEAD} sticky top-0`}>
                      <tr>
                        {postModellingPreviewData.columns.map((column) => (
                          <th key={column} className="px-3 py-2 text-left font-medium text-gray-700 border-r border-gray-200 last:border-r-0 whitespace-nowrap min-w-24">
                            {column}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {postModellingPreviewData.preview.map((row, index) => (
                        <tr key={index} className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                          {postModellingPreviewData.columns.map((column) => (
                            <td key={column} className="px-3 py-2 text-gray-900 border-r border-gray-200 last:border-r-0 whitespace-nowrap">
                              {(() => {
                                const value = row[column];
                                if (value === null || value === undefined) {
                                  return 'N/A';
                                }
                                if (typeof value === 'number') {
                                  return value.toLocaleString();
                                }
                                if (typeof value === 'object') {
                                  return JSON.stringify(value);
                                }
                                return String(value);
                              })()}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Preprocessed columns info below table */}
                {preprocessedColumns && preprocessedColumns.length > 0 && (
                  <div className="mt-4 pt-4 border-t border-gray-200">
                    <div className="text-sm text-gray-900 font-medium">
                      ✅ Preprocessed: {preprocessedColumns.join(', ')} ({preprocessedColumns.length} {preprocessedColumns.length === 1 ? 'column' : 'columns'})
                    </div>
                  </div>
                )}
              </div>
            );
          })()}
        </div>
      )}

      {mtaTrainingComplete && (
        <div className="mt-10 space-y-6 border-t border-gray-200 dark:border-gray-700 pt-10">
          <div className={`${MTA_SECTION} p-5 md:p-6 bg-gradient-to-r from-slate-50/90 to-blue-50/40 dark:from-slate-900 dark:to-slate-800/80`}>
            <div className="flex flex-wrap items-start gap-3 mb-6">
              <span className={MTA_STEP_NUM} title="Step 7">
                7
              </span>
              <div
                className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-teal-500 to-emerald-600 text-white shadow-md ring-2 ring-teal-400/30"
                title="After training"
              >
                <Rocket className="h-6 w-6" />
              </div>
              <div className="min-w-0">
                <h4 className={MTA_TITLE_SECTION}>Shortlist &amp; Pruning</h4>
                <p className="text-sm text-gray-600 dark:text-gray-300 mt-1 max-w-3xl">
                  Shown after training completes. Confirm your shortlist in <span className="font-medium">Step A</span>, then
                  optional pruning in <span className="font-medium">Step B</span> — same for auto and manual.
                </p>
              </div>
            </div>

            <div className="space-y-6">
              <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900/80 p-4 md:p-5 shadow-sm">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-xs font-bold uppercase tracking-wider text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-950/50 px-2 py-0.5 rounded">
                    Step A
                  </span>
                </div>
                <ModelScreenerPanel
                  activeDatasetId={activeDatasetId ?? null}
                  pruningPhaseUnlocked={mtaScreenerPhaseDone}
                  trainingBundle={step7TrainingBundle}
                />
              </div>

              {!mtaScreenerPhaseDone && (
                <div
                  className={`${MTA_SECTION} p-5 border-dashed border-amber-300/80 dark:border-amber-700/60 bg-amber-50/50 dark:bg-amber-950/20`}
                >
                  <p className="text-sm text-amber-950 dark:text-amber-100">
                    <span className="font-semibold">Step B (model pruning)</span> stays locked until you confirm your shortlist
                    in Step A — select at least one model, then use{' '}
                    <span className="font-medium">Confirm shortlist &amp; unlock pruning</span>.
                  </p>
                </div>
              )}

              {mtaScreenerPhaseDone && (
                <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900/80 p-4 md:p-5 shadow-sm">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-xs font-bold uppercase tracking-wider text-emerald-800 dark:text-emerald-200 bg-emerald-50 dark:bg-emerald-950/40 px-2 py-0.5 rounded">
                      Step B
                    </span>
                  </div>
                  <ModelPruningPanel
                    activeDatasetId={activeDatasetId ?? null}
                    trainingBundle={step7TrainingBundle}
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Chat Component */}
      {renderStepChat(6.5)}
    </div>
  );
};

export default Step6_5ModelTrainingAgent;


