import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import {
  Database,
  FileText,
  BarChart3,
  Users,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle,
  X,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  Download,
  Eye,
  Settings,
  Info,
  Calendar,
  Hash,
  Target,
  Activity,
  Calculator,
  GripVertical,
  Save,
  Loader,
  Network,
  Wrench,
  Brain,
  Maximize2,
  Upload,
  Sparkles,
  Edit3,
  GitMerge,
  Check,
  Undo2,
  BookOpen
} from 'lucide-react';
import {
    DatasetColumnInfo,
    fastApiService,
    ConfigUpdateRequest,
    ColumnDistributionResponse,
    VariableClassificationResponse,
    ColumnInfoResponse,
    ColumnInfo,
    KnowledgeGraphProcessingInfo,
    KnowledgeGraphResultPayload,
    DQSResponse,
    CutoffEditRequest,
    SegmentationWorkflowState,
    ModelCodebookResponse,
  } from '../services/fastApiService';

import { authService } from '../services/authService';
import BivariateAnalysisComponent from './BivariateAnalysisComponent';
import CorrelationAnalysisComponent from './CorrelationAnalysisComponent';
import MulticollinearityAnalysisComponent from './MulticollinearityAnalysisComponent';
import IVAnalysisComponent from './IVAnalysisComponent';
import VIFAnalysisComponent from './VIFAnalysisComponent';
import CorrelationRatioAnalysisComponent from './CorrelationRatioAnalysisComponent';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
  ArcElement,
} from 'chart.js';
import { Bar, Pie } from 'react-chartjs-2';
import JSZip from 'jszip';
import { useTheme } from '../contexts/ThemeContext';
import {
  chartJsDefaultFontColor,
  chartJsScaleBorder,
  chartJsTooltipColors,
} from '../utils/chartJsTheme';
import {
  displayTotalIv,
  formatMergeRecommendationExplanationForDisplay,
  formatOosEventRateDriftPp,
  formatOosEventRatePercent,
  formatSegmentationChiSquaredPLabel,
  perSegmentWoeIvContributions,
} from '../utils/segmentationMetricsDisplay';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
  ArcElement
);

/**
 * EDA Snapshot interface for comparison functionality
 */
interface EDASnapshot {
  timestamp: string;
  totalRows: number;
  totalColumns: number;
  numericStats: Array<{
    column: string;
    count: number;
    mean: number;
    std: number;
    min: number;
    percentile_25: number;
    percentile_50: number;
    percentile_75: number;
    max: number;
    missing_count: number;
    missing_percentage: number;
  }>;
  categoricalStats: Array<{
    column: string;
    unique_count: number;
    top_category: string | null;
    top_category_count: number;
    top_category_percentage: number;
    missing_count: number;
    missing_percentage: number;
    value_distribution: Record<string, number>;
  }>;
  dateStats: Array<{
    column: string;
    min_date: string | null;
    max_date: string | null;
    date_range_days: number;
    unique_count: number;
    missing_count: number;
    missing_percentage: number;
    most_frequent_date: string | null;
    most_frequent_count: number;
  }>;
  treatmentApplied?: string;
}

/**
 * Unified `/segmentation/run` responses use `segment.event_rate` as 0–100 (mean×100).
 * Merge/cutoff paths typically use 0–1 fractions. Normalize to [0, 1] for math and charts.
 */
function segmentEventRateToFraction(rate: unknown): number {
  const r = typeof rate === 'number' && !Number.isNaN(rate) ? rate : parseFloat(String(rate ?? 'NaN'));
  if (!Number.isFinite(r) || r < 0) return 0;
  if (r <= 1) return r;
  return r / 100;
}

/** API `segment_iv` key order is not guaranteed; sort as Seg 1, Seg 2, … (trailing number). */
function sortVariableRelevanceSegmentKeys(keys: string[]): string[] {
  const trailingIndex = (k: string): number => {
    const m = k.match(/(\d+)\s*$/);
    return m ? parseInt(m[1], 10) : 0;
  };
  return [...keys].sort((a, b) => {
    const da = trailingIndex(a);
    const db = trailingIndex(b);
    if (da !== db) return da - db;
    return a.localeCompare(b, undefined, { numeric: true });
  });
}

/** AI Summary: show as bullets when the text uses line-leading list markers; otherwise one paragraph. */
function renderRecommendationNarrativeBody(raw: string): React.ReactNode {
  const stripped = raw.trim();
  if (!stripped) return null;
  const stripMdBold = (s: string) => s.replace(/\*\*([^*]+)\*\*/g, '$1');
  const lines = stripped.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  const bulletLines = lines.filter((l) => /^[-*•]\s/.test(l));
  if (bulletLines.length >= 2) {
    return (
      <ul className="list-disc space-y-1.5 pl-1 text-sm text-gray-700 dark:text-gray-300 leading-snug marker:text-gray-400 dark:marker:text-gray-500">
        {bulletLines.map((line, i) => (
          <li key={i} className="pl-0.5">
            {stripMdBold(line.replace(/^[-*•]\s+/, ''))}
          </li>
        ))}
      </ul>
    );
  }
  return <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">{stripMdBold(stripped)}</p>;
}

/** Build and trigger download for segmentation codebook (same formats as Step 3.5). */
function downloadSegmentationCodebookFile(
  codebookData: ModelCodebookResponse,
  format: 'py' | 'csv' | 'ipynb'
): void {
  const timestamp = new Date().toISOString().slice(0, 10);
  const baseFilename = `${codebookData.algorithm}_segmentation_codebook_${timestamp}`;
  let content: string;
  let mimeType: string;
  let filename: string;

  if (format === 'py') {
    content = `# ${codebookData.title}\n# ${codebookData.description}\n\n`;
    codebookData.sections.forEach((section) => {
      content += `# ${'='.repeat(80)}\n# ${section.title}\n# ${'='.repeat(80)}\n\n${section.content}\n\n\n`;
    });
    mimeType = 'text/plain';
    filename = `${baseFilename}.py`;
  } else if (format === 'csv') {
    content = 'Section Number,Section Title,Section Type,Code Content\n';
    codebookData.sections.forEach((section, index) => {
      const sectionNum = index + 1;
      const title = `"${section.title.replace(/"/g, '""')}"`;
      const type = `"${section.type}"`;
      const code = `"${section.content.replace(/"/g, '""').replace(/\n/g, '\\n')}"`;
      content += `${sectionNum},${title},${type},${code}\n`;
    });
    mimeType = 'text/csv';
    filename = `${baseFilename}.csv`;
  } else {
    const notebookData = {
      cells: [
        {
          cell_type: 'markdown',
          metadata: {},
          source: [`# ${codebookData.title}\n`, `\n`, `${codebookData.description}\n`],
        },
        ...codebookData.sections
          .map((section) => {
            return [
              { cell_type: 'markdown', metadata: {}, source: [`## ${section.title}\n`] },
              {
                cell_type: 'code',
                execution_count: null,
                metadata: {},
                outputs: [],
                source: section.content.split('\n').map((line) => line + '\n'),
              },
            ];
          })
          .flat(),
      ],
      metadata: {
        kernelspec: {
          display_name: 'Python 3',
          language: 'python',
          name: 'python3',
        },
        language_info: {
          codemirror_mode: { name: 'ipython', version: 3 },
          file_extension: '.py',
          mimetype: 'text/x-python',
          name: 'python',
          nbconvert_exporter: 'python',
          pygments_lexer: 'ipython3',
          version: '3.8.0',
        },
      },
      nbformat: 4,
      nbformat_minor: 4,
    };
    content = JSON.stringify(notebookData, null, 2);
    mimeType = 'application/json';
    filename = `${baseFilename}.ipynb`;
  }
  const blob = new Blob([content], { type: mimeType });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}

function SegmentationAddToDataBar(props: {
  onAddToData: () => void;
  onCodebook: () => void;
  codebookLoading: boolean;
}) {
  const { onAddToData, onCodebook, codebookLoading } = props;
  return (
    <div className="flex gap-3">
      <button
        type="button"
        onClick={onAddToData}
        className="flex-1 px-4 py-2 bg-indigo-600 dark:bg-indigo-700 text-white rounded-lg hover:bg-indigo-700 dark:hover:bg-indigo-600 transition-colors flex items-center justify-center gap-2 text-sm font-medium"
      >
        <Database className="h-4 w-4" />
        <span>Add to Data</span>
      </button>
      <button
        type="button"
        onClick={onCodebook}
        disabled={codebookLoading}
        className="px-4 py-2 bg-gray-600 dark:bg-gray-700 text-white rounded-lg hover:bg-gray-700 dark:hover:bg-gray-600 transition-colors flex items-center justify-center gap-2 text-sm font-medium disabled:opacity-50"
      >
        <BookOpen className="h-4 w-4" />
        <span>Codebook</span>
      </button>
    </div>
  );
}

interface DatasetOverviewSidebarProps {
  isVisible: boolean;
  onClose: () => void;
  datasetId?: string | null;
  selectedInsightSteps?: string[];
  /** Last Step 3 generate action: auto (five panels) vs standard (checkboxes). Bivariate binning UI only when `standard`. */
  insightsGenerationSource?: 'auto' | 'standard' | null;
  onClearInsights?: () => void;
  datasetConfig?: {
    target_variable: string;
    target_variable_type: 'Numerical' | 'Categorical';
    problem_statement: string;
    data_dictionary: string;
  } | null;
  datasetAnalysis?: {
    columns: DatasetColumnInfo[];
    suggestedTargetVariable: string | null;
    totalRows: number;
    totalColumns: number;
  } | null;
  onWidthChange?: (width: number) => void;
  /** Step 1 only: true while Overview / Quality / Distributions panels are still fetching (parent may block flow navigation). */
  onStep1PrimaryPanelsBusyChange?: (busy: boolean) => void;
  currentStep?: number;
  restrictedMode?: 'all' | 'insights-only';
  problemType?: 'classification' | 'regression';
  segmentationResult?: any | null;
  /** Original EDA snapshot (before any treatment) - for Data Treatment page */
  originalEDA?: EDASnapshot | null;
  /** Current EDA snapshot (after treatment) - for Data Treatment page */
  currentEDA?: EDASnapshot | null;
  /** Whether to show EDA comparison tab */
  showEDAComparison?: boolean;
  /** Key to force refetch of EDA comparison data */
  edaRefreshKey?: number;
  /**
   * Counter that forces a switch to the EDA Comparison > "Updated EDA" sub-tab whenever its
   * value changes. The parent increments it (e.g. on the "View Updated EDA" button click);
   * this component watches the value and jumps to the Updated EDA view on each change.
   * Using a counter (instead of a boolean + reset callback) makes the behaviour idempotent
   * and guarantees the sub-tab opens even when the sidebar is already on the EDA tab.
   */
  forceEdaComparisonView?: number;
  onSegmentationResultChange?: (result: any) => void;
}

interface DatasetStats {
  totalRecords: number;
  totalColumns: number;
  missingValues: number;
  duplicateRows: number;
  dataTypes: {
    numerical: number;
    categorical: number;
    datetime: number;
  };
  targetDistribution?: {
    [key: string]: number;
  };
}

const DatasetOverviewSidebar: React.FC<DatasetOverviewSidebarProps> = ({
  isVisible,
  onClose,
  datasetId,
  selectedInsightSteps = [],
  insightsGenerationSource = null,
  onClearInsights,
  datasetConfig,
  datasetAnalysis,
  onWidthChange,
  onStep1PrimaryPanelsBusyChange,
  currentStep = 1,
  restrictedMode = 'all',
  problemType,
  segmentationResult = null,
  onSegmentationResultChange,
  originalEDA = null,
  currentEDA = null,
  showEDAComparison = false,
  edaRefreshKey = 0,
  forceEdaComparisonView = 0,
}) => {
  const { isDark, theme } = useTheme();
  const [collapsed, setCollapsed] = useState(false);
  const [activeTab, setActiveTab] = useState<'overview' | 'quality' | 'insights' | 'config' | 'segmentation' | 'eda'>('overview');
  
  // EDA comparison state
  const [edaActiveTab, setEdaActiveTab] = useState<'original' | 'comparison'>('original');
  const [edaExpandedSections, setEdaExpandedSections] = useState<Record<string, boolean>>({
    numeric: true,
    categorical: true,
    date: true
  });
  // EDA Comparison tab — compare-column-stats data
  const [edaComparisonData, setEdaComparisonData] = useState<any>(null);
  const [isLoadingEdaComparison, setIsLoadingEdaComparison] = useState(false);
  const [edaComparisonError, setEdaComparisonError] = useState<string | null>(null);
  // EDA Comparison sub-view: 'updated' shows updated EDA stats, 'heatmap' shows change heatmap
  const [edaComparisonSubView, setEdaComparisonSubView] = useState<'updated' | 'heatmap'>('updated');
  // View Data scope for EDA Comparison (mirrors Original EDA scope options)
  const [edaComparisonScope, setEdaComparisonScope] = useState<'entire' | 'train' | 'test' | 'validation'>('entire');
  const [resultsView, setResultsView] = useState<'global' | 'segmentation' | 'both'>('both');
  
  // Local state for dataset config to allow updates without page refresh
  const [localDatasetConfig, setLocalDatasetConfig] = useState(datasetConfig);
  
  // Sync local config with prop changes
  useEffect(() => {
    setLocalDatasetConfig(datasetConfig);
  }, [datasetConfig]);
  
  const [segmentSizesExpanded, setSegmentSizesExpanded] = useState(true);
  const [segmentProportionsExpanded, setSegmentProportionsExpanded] = useState(true);
  const [expandedChart, setExpandedChart] = useState<'sizes' | 'proportions' | null>(null);
  
  // Enhanced segmentation UI state (Phase 1)
  const [selectedSegmentsForMerge, setSelectedSegmentsForMerge] = useState<number[]>([]);
  const [isApplyingMerge, setIsApplyingMerge] = useState(false);
  
  // Local segmentation result state (allows updates from merge operations)
  const [localSegmentationResult, setLocalSegmentationResult] = useState<any>(segmentationResult);
  const [segmentationUndoStack, setSegmentationUndoStack] = useState<any[]>([]);
  const [lastMergeImpact, setLastMergeImpact] = useState<any>(null);
  
  // Cutoff editing state
  const [showCutoffEditModal, setShowCutoffEditModal] = useState(false);
  const [editingSegment, setEditingSegment] = useState<any>(null);
  const [cutoffEditPreview, setCutoffEditPreview] = useState<any>(null);
  const [isLoadingCutoffPreview, setIsLoadingCutoffPreview] = useState(false);
  const [cutoffEditValue, setCutoffEditValue] = useState<string>('');
  
  // LLM Narrative state
  const [recommendationNarrative, setRecommendationNarrative] = useState<string>('');
  const [isLoadingNarrative, setIsLoadingNarrative] = useState(false);
  const [mergeExplanation, setMergeExplanation] = useState<string>('');
  /** Variable relevance matrix: sort rows by this column (Overall IV or a segment name), descending. */
  const [variableRelevanceSortBy, setVariableRelevanceSortBy] = useState<'overall' | string>('overall');
  const addToDataIdempotencyRef = useRef<string | null>(null);
  const [segCodebookOpen, setSegCodebookOpen] = useState(false);
  const [segCodebookData, setSegCodebookData] = useState<ModelCodebookResponse | null>(null);
  const [segCodebookLoading, setSegCodebookLoading] = useState(false);
  const [segCodebookDownloadFormat, setSegCodebookDownloadFormat] = useState<'py' | 'csv' | 'ipynb'>('py');
  
  // Sync local state with prop changes; clear merge banner when a new run replaces the session
  // (merged payloads carry merge_history; fresh unified runs typically do not).
  useEffect(() => {
    if (segmentationResult) {
      setLocalSegmentationResult(segmentationResult);
      const mh = segmentationResult.merge_history;
      if (!Array.isArray(mh) || mh.length === 0) {
        setLastMergeImpact(null);
        setMergeExplanation('');
        setSelectedSegmentsForMerge([]);
        addToDataIdempotencyRef.current = null;
      }
    }
  }, [segmentationResult]);
  
  // Use local state if available, otherwise use prop
  const activeSegmentationResult = localSegmentationResult || segmentationResult;

  // New variable relevance matrix: default to Overall IV (desc) when the matrix payload or segment count changes
  useEffect(() => {
    setVariableRelevanceSortBy('overall');
  }, [
    activeSegmentationResult?.variable_relevance?.variables?.join('\u0001') ?? '',
    activeSegmentationResult?.num_segments,
  ]);
  
  // Generate recommendation narrative when segmentation result changes
  useEffect(() => {
    const generateRecommendationNarrative = async () => {
      if (!activeSegmentationResult?.segments || activeSegmentationResult.segments.length === 0) {
        setRecommendationNarrative('');
        return;
      }
      
      setIsLoadingNarrative(true);
      
      try {
        const segments = activeSegmentationResult.segments;
        const apiIv = activeSegmentationResult.validation?.total_iv;
        const summedRounded = segments.reduce((sum: number, s: any) => sum + (s.iv_contribution || 0), 0);
        const totalIv =
          apiIv != null && Number.isFinite(Number(apiIv)) && Math.abs(Number(apiIv)) > 1e-12
            ? Number(apiIv)
            : summedRounded;
        const numSegments = segments.length;
        
        // Determine recommendation category based on IV
        let recommendationCategory = 'unknown';
        if (totalIv >= 0.30) recommendationCategory = 'strong';
        else if (totalIv >= 0.10) recommendationCategory = 'acceptable';
        else if (totalIv >= 0.02) recommendationCategory = 'weak';
        else recommendationCategory = 'useless';
        
        const response = await fastApiService.generateSegmentationNarrative('recommendation', {
          validation_result: activeSegmentationResult.validation || {},
          num_segments: numSegments,
          total_iv: totalIv,
          recommendation_category: recommendationCategory
        });
        
        if (response.success) {
          setRecommendationNarrative(response.narrative);
        }
      } catch (error) {
        console.warn('Failed to generate recommendation narrative:', error);
        setRecommendationNarrative('');
      } finally {
        setIsLoadingNarrative(false);
      }
    };
    
    generateRecommendationNarrative();
  }, [activeSegmentationResult?.segments?.length]);

  /** Merges the first two selected segment ids (API merges a pair at a time). */
  const performSegmentMerge = async (segmentIds: number[]) => {
    if (segmentIds.length < 2 || !datasetId || !activeSegmentationResult) {
      return;
    }
    
    setIsApplyingMerge(true);
    
    try {
      // Save current state for undo
      setSegmentationUndoStack(prev => [...prev.slice(-4), activeSegmentationResult]);
      
      // Get segment details for LLM explanation
      const segments = activeSegmentationResult?.segments || [];
      const segmentA = segments.find((s: any) => s.segment_id === segmentIds[0]);
      const segmentB = segments.find((s: any) => s.segment_id === segmentIds[1]);
      
      // Call the merge API
      const response = await fastApiService.mergeSegments(
        datasetId,
        segmentIds[0],
        segmentIds[1],
        activeSegmentationResult
      );
      
      if (response.success) {
        // Full `validation` (chi², merge recs, OOS, bootstrap, category) from server rebuild
        const next: SegmentationWorkflowState = {
          ...(activeSegmentationResult as SegmentationWorkflowState),
          ...response.updated_segmentation,
        };
        setLocalSegmentationResult(next);
        setLastMergeImpact(response.merge_impact);
        
        // Notify parent component if callback provided
        if (onSegmentationResultChange) {
          onSegmentationResultChange(next);
        }
        
        // Clear selection
        setSelectedSegmentsForMerge([]);
        
        // Generate LLM explanation for the merge (async, don't block)
        if (segmentA && segmentB && response.merge_impact) {
          fastApiService.generateSegmentationNarrative('merge', {
            segment_a: {
              name: segmentA.name || `Segment ${segmentA.segment_id}`,
              record_count: segmentA.record_count || segmentA.size,
              event_rate: segmentA.event_rate,
              iv_contribution: segmentA.iv_contribution
            },
            segment_b: {
              name: segmentB.name || `Segment ${segmentB.segment_id}`,
              record_count: segmentB.record_count || segmentB.size,
              event_rate: segmentB.event_rate,
              iv_contribution: segmentB.iv_contribution
            },
            merge_reason: 'user_initiated',
            combined_stats: {
              combined_records: response.merge_impact.combined_records,
              combined_event_rate: response.merge_impact.combined_event_rate,
              iv_change: response.merge_impact.iv_change
            }
          }).then(narrativeResponse => {
            if (narrativeResponse.success) {
              setMergeExplanation(narrativeResponse.narrative);
            }
          }).catch(err => console.warn('Merge explanation generation failed:', err));
        }
        
        console.log('Merge successful:', response.message);
      } else {
        console.error('Merge failed:', response.message);
        alert(`Merge failed: ${response.message}`);
      }
    } catch (error: any) {
      console.error('Error merging segments:', error);
      alert(`Error merging segments: ${error.message || 'Unknown error'}`);
    } finally {
      setIsApplyingMerge(false);
    }
  };

  const handleMergeSegments = async () => {
    if (selectedSegmentsForMerge.length < 2 || !datasetId || !activeSegmentationResult) {
      return;
    }
    await performSegmentMerge(selectedSegmentsForMerge);
  };
  
  const handleUndoMerge = () => {
    if (segmentationUndoStack.length === 0) return;
    
    const previousState = segmentationUndoStack[segmentationUndoStack.length - 1];
    setSegmentationUndoStack(prev => prev.slice(0, -1));
    setLocalSegmentationResult(previousState);
    setLastMergeImpact(null);
    
    // Notify parent
    if (onSegmentationResultChange) {
      onSegmentationResultChange(previousState);
    }
    
    // Clear selection
    setSelectedSegmentsForMerge([]);
  };

  const handleSidebarAddToData = useCallback(async () => {
    if (!datasetId || !activeSegmentationResult?.success) return;
    try {
      const segmentation_result = {
        ...activeSegmentationResult,
        merge_history: Array.isArray(activeSegmentationResult.merge_history)
          ? activeSegmentationResult.merge_history
          : [],
        cutoff_edits: Array.isArray(activeSegmentationResult.cutoff_edits)
          ? activeSegmentationResult.cutoff_edits
          : [],
      };
      if (!addToDataIdempotencyRef.current) {
        addToDataIdempotencyRef.current =
          typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
            ? crypto.randomUUID()
            : `${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
      }
      const result = await fastApiService.addSegmentationToData({
        dataset_id: datasetId,
        segmentation_result,
        scheme_name: null,
        idempotency_key: addToDataIdempotencyRef.current,
      });
      if (result.success) {
        addToDataIdempotencyRef.current = null;
        alert(`Segmentation saved as "${result.column_name}"!`);
        window.dispatchEvent(new CustomEvent('segmentationSchemeAdded'));
      }
    } catch (error) {
      alert(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }, [datasetId, activeSegmentationResult]);

  const handleSidebarSegmentationCodebook = useCallback(async () => {
    if (!datasetId) {
      alert('No dataset loaded');
      return;
    }
    setSegCodebookLoading(true);
    try {
      const raw = String(activeSegmentationResult?.method || '').toLowerCase();
      const algo: 'cart' | 'chaid' = raw.includes('chaid') ? 'chaid' : 'cart';
      const variablesToUse = Array.isArray(activeSegmentationResult?.variables_used)
        ? activeSegmentationResult.variables_used
        : undefined;
      const response = await fastApiService.getModelCodebook(algo, {
        dataset_id: datasetId,
        target_variable: localDatasetConfig?.target_variable,
        selected_variables: variablesToUse,
        problem_type: problemType,
      });
      setSegCodebookData(response);
      setSegCodebookOpen(true);
    } catch (error) {
      console.error('Error fetching segmentation codebook:', error);
      alert('Failed to load segmentation codebook. Please try again.');
    } finally {
      setSegCodebookLoading(false);
    }
  }, [datasetId, activeSegmentationResult, localDatasetConfig?.target_variable, problemType]);

  const handleSegCodebookDownload = useCallback(() => {
    if (!segCodebookData) return;
    downloadSegmentationCodebookFile(segCodebookData, segCodebookDownloadFormat);
  }, [segCodebookData, segCodebookDownloadFormat]);
  
  // Cutoff editing handlers
  const parseRuleForCutoff = (rule: string): { variable: string; operator: string; value: number } | null => {
    // Parse rules like "age > 30", "income <= 50000", "var == 100"
    const match = rule.match(/(\w+)\s*(>|>=|<|<=|==|!=)\s*([\d.]+)/);
    if (match) {
      return {
        variable: match[1],
        operator: match[2],
        value: parseFloat(match[3])
      };
    }
    return null;
  };
  
  const handleOpenCutoffEdit = (segment: any) => {
    const parsed = parseRuleForCutoff(segment.rule_definition || '');
    if (parsed) {
      setEditingSegment({ ...segment, ...parsed });
      setCutoffEditValue(parsed.value.toString());
      setCutoffEditPreview(null);
      setShowCutoffEditModal(true);
    } else {
      alert('Cannot edit cutoff: Rule format not recognized. Rules must be in format "variable > value".');
    }
  };
  
  const handlePreviewCutoff = async () => {
    if (!editingSegment || !datasetId || !activeSegmentationResult) return;
    
    const newValue = parseFloat(cutoffEditValue);
    if (isNaN(newValue)) {
      alert('Please enter a valid number');
      return;
    }
    
    setIsLoadingCutoffPreview(true);
    try {
      const request: CutoffEditRequest = {
        dataset_id: datasetId,
        segment_id: editingSegment.segment_id,
        variable: editingSegment.variable,
        operator: editingSegment.operator,
        old_value: editingSegment.value,
        new_value: newValue,
        preview_only: true,
        current_segmentation: activeSegmentationResult
      };
      
      const response = await fastApiService.editSegmentCutoff(request);
      if (response.success) {
        setCutoffEditPreview(response.impact);
      } else {
        alert(`Preview failed: ${response.message}`);
      }
    } catch (error: any) {
      console.error('Error previewing cutoff:', error);
      alert(`Error previewing cutoff: ${error.message || 'Unknown error'}`);
    } finally {
      setIsLoadingCutoffPreview(false);
    }
  };
  
  const handleApplyCutoff = async () => {
    if (!editingSegment || !datasetId || !activeSegmentationResult) return;
    
    const newValue = parseFloat(cutoffEditValue);
    if (isNaN(newValue)) {
      alert('Please enter a valid number');
      return;
    }
    
    setIsLoadingCutoffPreview(true);
    try {
      // Save current state for undo
      setSegmentationUndoStack(prev => [...prev.slice(-4), activeSegmentationResult]);
      
      const request: CutoffEditRequest = {
        dataset_id: datasetId,
        segment_id: editingSegment.segment_id,
        variable: editingSegment.variable,
        operator: editingSegment.operator,
        old_value: editingSegment.value,
        new_value: newValue,
        preview_only: false,
        current_segmentation: activeSegmentationResult
      };
      
      const response = await fastApiService.editSegmentCutoff(request);
      if (response.success && response.updated_segmentation) {
        const next: SegmentationWorkflowState = {
          ...(activeSegmentationResult as SegmentationWorkflowState),
          ...response.updated_segmentation,
        };
        setLocalSegmentationResult(next);
        
        // Notify parent
        if (onSegmentationResultChange) {
          onSegmentationResultChange(next);
        }
        
        setShowCutoffEditModal(false);
        setEditingSegment(null);
        setCutoffEditPreview(null);
      } else {
        alert(`Apply failed: ${response.message}`);
      }
    } catch (error: any) {
      console.error('Error applying cutoff:', error);
      alert(`Error applying cutoff: ${error.message || 'Unknown error'}`);
    } finally {
      setIsLoadingCutoffPreview(false);
    }
  };

  // Set default tab based on restricted mode and current step
  useEffect(() => {
    if (restrictedMode === 'insights-only') {
      setActiveTab('insights');
    } else if (currentStep === 3.5) {
      setActiveTab('segmentation');
    } else if (currentStep === 2) {
      // Data Treatment page always shows the EDA tab (it is the only tab available)
      setActiveTab('eda');
    } else {
      // Reset to default tab when not on step 3.5/2 and an invalid tab is active
      if (activeTab === 'segmentation' || activeTab === 'eda') {
        setActiveTab('overview');
      }
    }
  }, [restrictedMode, currentStep, showEDAComparison]);

  // Force switch to EDA Comparison > "Updated EDA" sub-tab whenever the parent increments
  // `forceEdaComparisonView`. The initial mount (value 0) is skipped so the user's natural
  // browsing state on load is not overridden. We also expand the sidebar if it was collapsed
  // so the user lands directly on the Updated EDA view without needing a second click.
  useEffect(() => {
    if (forceEdaComparisonView > 0 && currentStep === 2) {
      setCollapsed(false);
      setActiveTab('eda');
      setEdaActiveTab('comparison');
      setEdaComparisonSubView('updated');
    }
  }, [forceEdaComparisonView, currentStep]);

  // Determine if we should show placeholder content based on current step
  const shouldShowPlaceholder = (step: number) => {
    return step >= 4; // Steps 4-9 show placeholder content
  };

  // Function to get section name based on current step
  const getSectionName = (step: number): string => {
    switch (step) {
      case 1:
        return 'Objectives';
      case 2:
        return 'Data Treatment';
      case 3:
        return 'Data Insights';
      case 4:
        return 'Feature Engineering';
      case 5:
        return 'Model Selection';
      case 6:
        return 'Training & Validation';
      case 7:
        return 'Evaluation & Testing';
      case 8:
        return 'Deployment';
      case 9:
        return 'Monitoring & Maintenance';
      default:
        return 'Dataset Overview';
    }
  };

  // Step-specific placeholder content
  const renderStepPlaceholder = (step: number) => {
    const stepInfo = {
      4: { title: 'Feature Engineering', description: 'Transform and create features for model training', icon: Wrench },
      5: { title: 'Model Evaluation', description: 'Model performance evaluation', icon: BarChart3 },
      6: { title: 'Algorithm Selection', description: 'Select and configure ML algorithms', icon: Brain },
      7: { title: 'Model Training', description: 'Train and optimize selected models', icon: TrendingUp },
      8: { title: 'AI/ML Explainability', description: 'Model interpretability and explainability', icon: Activity },
      9: { title: 'Auto Documentation', description: 'Automated documentation generation', icon: FileText }
    };

    const info = stepInfo[step as keyof typeof stepInfo];
    if (!info) return null;

    const IconComponent = info.icon;

    return (
      <div className="space-y-6">
        <div className="text-center py-12">
          <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center mx-auto mb-4">
            <IconComponent className="h-8 w-8 text-blue-600 dark:text-blue-400" />
          </div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">{info.title}</h3>
          <p className="text-gray-600 dark:text-gray-400 mb-4">{info.description}</p>
          <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-700 rounded-lg p-4">
            <p className="text-sm text-yellow-800 dark:text-yellow-300">
              <strong>Coming Soon:</strong> This step will be implemented in the next phase. 
              The dataset overview will show relevant information for this step once implemented.
            </p>
          </div>
        </div>
      </div>
    );
  };
  const [sidebarWidth, setSidebarWidth] = useState(800); // Default width: 800px (maximum width)
  const [isResizing, setIsResizing] = useState(false);
  const [showWidthIndicator, setShowWidthIndicator] = useState(false);
  const [isDataQualityExpanded, setIsDataQualityExpanded] = useState(false);
  const [isConsistencyExpanded, setIsConsistencyExpanded] = useState(false);
  const resizeRef = useRef<HTMLDivElement>(null);
  
  // Calculate real dataset statistics from analysis data
  const [datasetStats, setDatasetStats] = useState<DatasetStats>({
    totalRecords: 0,
    totalColumns: 0,
    missingValues: 0,
    duplicateRows: 0,
    dataTypes: {
      numerical: 0,
      categorical: 0,
      datetime: 0
    },
    targetDistribution: {}
  });

  const [qualityScore, setQualityScore] = useState(95);
  const [lastUpdated] = useState(new Date());
  
  // Chart state
  const [selectedColumn, setSelectedColumn] = useState<string>('');
  const [selectedColumns, setSelectedColumns] = useState<string[]>([]); // Multi-select (max 4)
  const [isColumnDropdownOpen, setIsColumnDropdownOpen] = useState(false); // Dropdown open state
  const [columnDistribution, setColumnDistribution] = useState<{[key: string]: number}>({});
  const [multiColumnDistributions, setMultiColumnDistributions] = useState<{[columnName: string]: {distribution: {[key: string]: number}, data: ColumnDistributionResponse | null}}>({});
  const [distributionData, setDistributionData] = useState<ColumnDistributionResponse | null>(null);
  const [isLoadingDistribution, setIsLoadingDistribution] = useState(false);
  const [distributionScope, setDistributionScope] = useState<'entire' | 'train' | 'test' | 'validation'>('entire');
  const [columnInfo, setColumnInfo] = useState<ColumnInfoResponse | null>(null);
  const [isLoadingColumnInfo, setIsLoadingColumnInfo] = useState(false);
  const [columnInfoScope, setColumnInfoScope] = useState<'entire' | 'train' | 'test' | 'validation'>('entire');
  const MAX_SELECTED_COLUMNS = 4;
  const columnDropdownRef = React.useRef<HTMLDivElement>(null);

  // DQS (Data Quality Score) state
  const [dqsData, setDqsData] = useState<DQSResponse | null>(null);
  const [isLoadingDqs, setIsLoadingDqs] = useState(false);
  const [dqsError, setDqsError] = useState<string | null>(null);
  const [dqsScope, setDqsScope] = useState<'entire' | 'train' | 'test' | 'validation'>('entire');

  /** Train / test / validation / entire for Step 3 Data Insights panels (backend scope + sessionStorage `data_scope`). */
  type DataPartitionScope = 'entire' | 'train' | 'test' | 'validation';
  const [insightsDataScope, setInsightsDataScope] = useState<DataPartitionScope>('entire');
  const [isApplyingInsightsScope, setIsApplyingInsightsScope] = useState(false);

  const readDataScopeFromSession = (): DataPartitionScope => {
    try {
      const raw = sessionStorage.getItem('dataset_config');
      if (raw) {
        const parsed = JSON.parse(raw) as { data_scope?: string };
        const s = parsed?.data_scope;
        if (s === 'train' || s === 'test' || s === 'validation' || s === 'entire') {
          return s;
        }
      }
    } catch {
      /* ignore */
    }
    return 'entire';
  };

  const persistDataScopeToSession = (scope: DataPartitionScope) => {
    try {
      const raw = sessionStorage.getItem('dataset_config');
      const parsed = raw ? (JSON.parse(raw) as Record<string, unknown>) : {};
      parsed.data_scope = scope;
      sessionStorage.setItem('dataset_config', JSON.stringify(parsed));
    } catch (e) {
      console.error('Failed to persist data_scope to sessionStorage:', e);
    }
  };

  useEffect(() => {
    if (!datasetId) return;
    setInsightsDataScope(readDataScopeFromSession());
  }, [datasetId]);

  useEffect(() => {
    const handler = (e: Event) => {
      const ev = e as CustomEvent<{ dataset_id?: string; scope?: string }>;
      const { dataset_id, scope } = ev.detail || {};
      if (dataset_id !== datasetId || !scope) return;
      if (scope === 'train' || scope === 'test' || scope === 'validation' || scope === 'entire') {
        setInsightsDataScope(scope);
      }
    };
    window.addEventListener('datasetScopeChanged', handler);
    return () => window.removeEventListener('datasetScopeChanged', handler);
  }, [datasetId]);

  const applyInsightsDataScope = async (newScope: DataPartitionScope) => {
    if (!datasetId) return;
    setIsApplyingInsightsScope(true);
    try {
      await fastApiService.setDatasetScope({ dataset_id: datasetId, scope: newScope, seed: 42 });
      persistDataScopeToSession(newScope);
      setInsightsDataScope(newScope);
      window.dispatchEvent(
        new CustomEvent('datasetScopeChanged', { detail: { dataset_id: datasetId, scope: newScope } })
      );
    } catch (err) {
      console.error('Failed to set data scope for insights:', err);
    } finally {
      setIsApplyingInsightsScope(false);
    }
  };
  
  // DQS AI Recommendations state
  type DQSRecommendation = { title: string; description: string; type: 'info' | 'warning' | 'success'; priority: 'high' | 'medium' | 'low' };
  const [dqsRecommendations, setDqsRecommendations] = useState<DQSRecommendation[]>([]);
  const [isLoadingDqsRecommendations, setIsLoadingDqsRecommendations] = useState(false);
  const [showAllDqsRecommendations, setShowAllDqsRecommendations] = useState(false);

  // Column insights state
  type ColumnInsight = { title: string; description: string; type: 'info' | 'warning' | 'success' };
  const [columnInsights, setColumnInsights] = useState<ColumnInsight[]>([]);
  const [isLoadingInsights, setIsLoadingInsights] = useState(false);
  const [showAllInsights, setShowAllInsights] = useState(false);

  const step1PrimaryPanelsBusy = useMemo(
    () =>
      currentStep === 1 &&
      isVisible &&
      Boolean(datasetId) &&
      (isLoadingColumnInfo ||
        isLoadingDqs ||
        isLoadingDqsRecommendations ||
        isLoadingDistribution ||
        isLoadingInsights ||
        isApplyingInsightsScope),
    [
      currentStep,
      isVisible,
      datasetId,
      isLoadingColumnInfo,
      isLoadingDqs,
      isLoadingDqsRecommendations,
      isLoadingDistribution,
      isLoadingInsights,
      isApplyingInsightsScope,
    ],
  );

  useEffect(() => {
    onStep1PrimaryPanelsBusyChange?.(step1PrimaryPanelsBusy);
    return () => {
      onStep1PrimaryPanelsBusyChange?.(false);
    };
  }, [step1PrimaryPanelsBusy, onStep1PrimaryPanelsBusyChange]);

  // Variable classification state
  const [variableClassification, setVariableClassification] = useState<VariableClassificationResponse | null>(null);

  // Helper to get logical/semantic type for a dataset column, including Date
  const getColumnLogicalType = (column: DatasetColumnInfo | any): 'Numerical' | 'Categorical' | 'Date' => {
    if (!column) return 'Categorical';
    if (column.logical_type === 'Date' || column.is_date) {
      return 'Date';
    }
    if (column.logical_type === 'Numerical' || column.logical_type === 'Categorical') {
      return column.logical_type;
    }
    return column.type || 'Categorical';
  };

  // Check if dataset is valid (exists on server)
  const checkDatasetValidity = async (datasetId: string): Promise<boolean> => {
    try {
      const res = await fastApiService.get('/datasets');
      const result = res.data;
      return Array.isArray(result.datasets) && result.datasets.includes(datasetId);
    } catch (error) {
      console.error('Failed to check dataset validity:', error);
      return false;
    }
  };

  // Fetch real column distribution data from backend (with scope support)
  const fetchColumnDistribution = async (columnName: string, scope?: 'entire' | 'train' | 'test' | 'validation'): Promise<void> => {
    if (!datasetId || !columnName) {
      setColumnDistribution({});
      setDistributionData(null);
      return;
    }

    const currentScope = scope || distributionScope;
    setIsLoadingDistribution(true);
    setColumnInsights([]);
    setShowAllInsights(false);
    try {
      console.log('Fetching real distribution data for column:', columnName, 'scope:', currentScope);
      const result = await fastApiService.getColumnDistributionByScope(datasetId, columnName, currentScope, 10);

      setDistributionData(result);
      setColumnDistribution(result.distribution);
      console.log('Real distribution data loaded:', result);
      
      // Fetch AI insights for the column distribution
      fetchColumnInsights(columnName, result);
    } catch (error) {
      console.error('Failed to fetch column distribution:', error);
      
      // Fallback to estimated data if real data fails
      const fallbackDistribution = getFallbackDistribution(columnName);
      setColumnDistribution(fallbackDistribution);
      setDistributionData(null);
      
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      if (errorMessage.includes('Dataset not found') || errorMessage.includes('upload')) {
        // Don't show alert for known dataset issues, user will see in other parts of UI
        console.warn('Dataset not available for distribution calculation');
      } else {
        console.warn(`Using estimated distribution data due to error: ${errorMessage}`);
      }
    } finally {
      setIsLoadingDistribution(false);
    }
  };

  // Fetch AI-generated insights for column distribution
  const fetchColumnInsights = async (columnName: string, distData: ColumnDistributionResponse): Promise<void> => {
    if (!datasetId || !columnName || !distData) return;
    
    setIsLoadingInsights(true);
    try {
      const columnType = getColumnType(columnName);
      const result = await fastApiService.generateColumnDistributionInsights(
        datasetId,
        columnName,
        columnType,
        distData.distribution,
        distData.statistics
      );
      
      if (result.success && result.insights && result.insights.length > 0) {
        // Take only the first (most important) insight per column
        setColumnInsights([result.insights[0]]);
        console.log('Column insight loaded: 1');
      } else {
        console.warn('Failed to generate insights:', result.error);
        setColumnInsights([]);
      }
    } catch (error) {
      console.error('Failed to fetch column insights:', error);
      setColumnInsights([]);
    } finally {
      setIsLoadingInsights(false);
    }
  };

  // Fallback to estimated distribution (original logic)
  const getFallbackDistribution = (columnName: string): {[key: string]: number} => {
    if (!datasetAnalysis) return {};
    
    const column = datasetAnalysis.columns.find(col => col.name === columnName);
    if (!column) return {};

    if (column.type === 'Categorical' && column.sample_values) {
      return column.sample_values;
    } else if (column.type === 'Numerical' && column.numerical_stats) {
      // Estimated quantile-based distribution for numerical columns
      const stats = column.numerical_stats;
      if (stats.min !== null && stats.max !== null && stats.mean !== null) {
        const distribution: {[key: string]: number} = {};
        const numBins = 5;
        
        // Simulate quantile-based bins by creating unequal width bins
        // that would be more representative of actual data distribution
        const range = stats.max - stats.min;
        
        // Create bins that are smaller around the mean (higher density)
        // and larger at the extremes (lower density)
        for (let i = 0; i < numBins; i++) {
          let binStart: number, binEnd: number;
          
          if (i === 0) {
            // First bin: min to first quartile (estimated)
            binStart = stats.min;
            binEnd = stats.min + (range * 0.15);
          } else if (i === 1) {
            // Second bin: first quartile to below mean
            binStart = stats.min + (range * 0.15);
            binEnd = stats.mean - (range * 0.1);
          } else if (i === 2) {
            // Third bin: around mean (highest density)
            binStart = stats.mean - (range * 0.1);
            binEnd = stats.mean + (range * 0.1);
          } else if (i === 3) {
            // Fourth bin: above mean to third quartile
            binStart = stats.mean + (range * 0.1);
            binEnd = stats.min + (range * 0.85);
          } else {
            // Last bin: third quartile to max
            binStart = stats.min + (range * 0.85);
            binEnd = stats.max;
          }
          
          const binLabel = `${binStart.toFixed(1)}-${binEnd.toFixed(1)}`;
          
          // Quantile-based distribution: center bins get more records
          let estimatedCount: number;
          if (i === 2) { // Center bin around mean
            estimatedCount = Math.floor(200 + Math.random() * 50);
          } else if (i === 1 || i === 3) { // Bins adjacent to center
            estimatedCount = Math.floor(120 + Math.random() * 40);
          } else { // Extreme bins
            estimatedCount = Math.floor(40 + Math.random() * 30);
          }
          
          distribution[binLabel] = Math.max(estimatedCount, 15);
        }
        return distribution;
      }
    }
    
    return {};
  };

  // Get column type helper function
  const getColumnType = (columnName: string): 'Numerical' | 'Categorical' => {
    if (!datasetAnalysis || !columnName) return 'Categorical';
    const column = datasetAnalysis.columns.find(col => col.name === columnName);
    // For visualization, treat Date as Categorical by default
    const logicalType = column ? getColumnLogicalType(column) : 'Categorical';
    return logicalType === 'Numerical' ? 'Numerical' : 'Categorical';
  };

  // Calculate data quality metrics
  const getDataQualityMetrics = () => {
    if (!datasetAnalysis) {
      return {
        emptyColumns: 0,
        constantColumns: 0,
        sparseColumns: 0,
        emptyColumnNames: [],
        constantColumnNames: [],
        sparseColumnNames: []
      };
    }

    const emptyColumns = datasetAnalysis.columns.filter(col => 
      col.missing_count === datasetAnalysis.totalRows
    );
    
    const constantColumns = datasetAnalysis.columns.filter(col => 
      col.unique_count === 1
    );
    
    const sparseColumns = datasetAnalysis.columns.filter(col => {
      const missingPercentage = (col.missing_count / datasetAnalysis.totalRows) * 100;
      return missingPercentage > 50 && missingPercentage < 100;
    });

    return {
      emptyColumns: emptyColumns.length,
      constantColumns: constantColumns.length,
      sparseColumns: sparseColumns.length,
      emptyColumnNames: emptyColumns.map(col => col.name),
      constantColumnNames: constantColumns.map(col => col.name),
      sparseColumnNames: sparseColumns.map(col => col.name)
    };
  };

  // Calculate consistency metrics
  const getConsistencyMetrics = () => {
    if (!datasetAnalysis) {
      return {
        formattingIssues: 0,
        formattingIssueColumnNames: []
      };
    }

    // Detect potential formatting issues based on column characteristics
    const formattingIssueColumns = datasetAnalysis.columns.filter(col => {
      // For categorical columns, check if there are potential formatting inconsistencies
      if (col.type === 'Categorical' && col.sample_values) {
        const values = Object.keys(col.sample_values);
        
        // Check for mixed case variations (e.g., "Yes", "yes", "YES")
        const lowerCaseValues = values.map(v => v.toLowerCase());
        const uniqueLowerCase = new Set(lowerCaseValues);
        if (uniqueLowerCase.size < values.length) {
          return true;
        }
        
        // Check for whitespace inconsistencies (leading/trailing spaces)
        const hasWhitespaceIssues = values.some(v => v !== v.trim());
        if (hasWhitespaceIssues) {
          return true;
        }
        
        // Check for mixed separators or formatting (e.g., "N/A", "n/a", "NA", "null")
        const nullVariants = ['n/a', 'na', 'null', 'none', 'nil', '', 'missing', 'unknown'];
        const valueVariants = values.map(v => v.toLowerCase().trim());
        const nullVariantCount = valueVariants.filter(v => nullVariants.includes(v)).length;
        if (nullVariantCount > 1) {
          return true;
        }
      }
      
      // For numerical columns that might have been parsed as categorical due to formatting issues
      if (col.type === 'Categorical' && col.unique_count > 10) {
        const values = col.sample_values ? Object.keys(col.sample_values) : [];
        // Check if most values look like numbers but with formatting issues
        const numberLikeCount = values.filter(v => {
          const cleaned = v.replace(/[,$%\s]/g, '');
          return !isNaN(Number(cleaned)) && cleaned !== '';
        }).length;
        
        if (numberLikeCount / values.length > 0.7) {
          return true;
        }
      }
      
      return false;
    });

    return {
      formattingIssues: formattingIssueColumns.length,
      formattingIssueColumnNames: formattingIssueColumns.map(col => col.name)
    };
  };

  // Handle column selection for distribution chart (single select - legacy)
  const handleColumnSelect = (columnName: string) => {
    setSelectedColumn(columnName);
    fetchColumnDistribution(columnName);
  };

  // Handle multi-column selection (max 4)
  const handleMultiColumnToggle = (columnName: string) => {
    setSelectedColumns(prev => {
      const isSelected = prev.includes(columnName);
      if (isSelected) {
        // Remove column
        const newSelection = prev.filter(c => c !== columnName);
        // Also remove from distributions
        setMultiColumnDistributions(prevDist => {
          const newDist = { ...prevDist };
          delete newDist[columnName];
          return newDist;
        });
        return newSelection;
      } else {
        // Add column (if under max limit)
        if (prev.length >= MAX_SELECTED_COLUMNS) {
          return prev; // Don't add more
        }
        // Fetch distribution for the new column
        fetchMultiColumnDistribution(columnName);
        return [...prev, columnName];
      }
    });
  };

  // Clear all selected columns
  const clearAllSelectedColumns = () => {
    setSelectedColumns([]);
    setMultiColumnDistributions({});
    setColumnInsights([]);
    setShowAllInsights(false);
  };

  // Fetch distribution for multi-select (with scope support)
  const fetchMultiColumnDistribution = async (columnName: string, scope?: 'entire' | 'train' | 'test' | 'validation'): Promise<void> => {
    if (!datasetId || !columnName) return;

    const currentScope = scope || distributionScope;
    try {
      console.log('Fetching distribution for multi-select column:', columnName, 'scope:', currentScope);
      const result = await fastApiService.getColumnDistributionByScope(datasetId, columnName, currentScope, 10);

      setMultiColumnDistributions(prev => ({
        ...prev,
        [columnName]: {
          distribution: result.distribution,
          data: result
        }
      }));
      console.log('Multi-column distribution loaded for:', columnName);
    } catch (error) {
      console.error('Failed to fetch distribution for column:', columnName, error);
      // Fallback to estimated data
      const fallbackDistribution = getFallbackDistribution(columnName);
      setMultiColumnDistributions(prev => ({
        ...prev,
        [columnName]: {
          distribution: fallbackDistribution,
          data: null
        }
      }));
    }
  };

  /** Insights/Distributions tab: backend scope + Step 1–2 column distribution refetch */
  const handleInsightsTabDataScopeChange = async (v: DataPartitionScope) => {
    await applyInsightsDataScope(v);
    if (currentStep !== 3) {
      setDistributionScope(v);
      selectedColumns.forEach((col) => {
        void fetchMultiColumnDistribution(col, v);
      });
      if (selectedColumn) {
        void fetchColumnDistribution(selectedColumn, v);
      }
    }
  };

  useEffect(() => {
    if (currentStep === 3) return;
    setDistributionScope(insightsDataScope);
  }, [insightsDataScope, currentStep]);

  // Generate insights for all selected columns
  const generateMultiColumnInsights = async () => {
    if (!datasetId || selectedColumns.length === 0) {
      setColumnInsights([]);
      return;
    }

    setIsLoadingInsights(true);
    setColumnInsights([]);
    
    try {
      const allInsights: Array<{ title: string; description: string; type: 'info' | 'warning' | 'success' }> = [];
      
      for (const columnName of selectedColumns) {
        const distInfo = multiColumnDistributions[columnName];
        if (distInfo && distInfo.data) {
          const columnType = getColumnType(columnName);
          const result = await fastApiService.generateColumnDistributionInsights(
            datasetId,
            columnName,
            columnType,
            distInfo.distribution,
            distInfo.data.statistics
          );
          
          if (result.success && result.insights && result.insights.length > 0) {
            // Take only the first (most important) insight per column
            const topInsight = result.insights[0];
            allInsights.push({
              ...topInsight,
              title: `[${columnName}] ${topInsight.title}`
            });
          }
        }
      }
      
      setColumnInsights(allInsights);
      console.log('Multi-column insights generated:', allInsights.length);
    } catch (error) {
      console.error('Failed to generate multi-column insights:', error);
      setColumnInsights([]);
    } finally {
      setIsLoadingInsights(false);
    }
  };

  // Fetch variable classification from backend
  const fetchVariableClassification = async (): Promise<void> => {
    if (!datasetId) {
      setVariableClassification(null);
      return;
    }

    try {
      console.log('Fetching variable classification for dataset:', datasetId);
      const result = await fastApiService.classifyDatasetVariables(datasetId);
      
      setVariableClassification(result);
      console.log('Variable classification loaded:', result);
    } catch (error) {
      console.error('Failed to fetch variable classification:', error);
      setVariableClassification(null);
      
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      if (errorMessage.includes('Dataset not found') || errorMessage.includes('upload')) {
        console.warn('Dataset not available for variable classification');
      } else {
        console.warn(`Variable classification failed: ${errorMessage}`);
      }
    }
  };

  // Initialize selected column when datasetAnalysis changes (P1.4: only when visible
  // — auto-select triggers a column-distribution fetch + LLM insights, so we don't
  // want it firing while the sidebar is hidden).
  useEffect(() => {
    if (!isVisible) return;
    if (datasetAnalysis && datasetAnalysis.columns.length > 0 && !selectedColumn) {
      // Prefer categorical columns first (they have better distribution data)
      const categoricalColumns = datasetAnalysis.columns.filter(col => col.type === 'Categorical' && col.sample_values);
      const firstColumn = categoricalColumns.length > 0 ? categoricalColumns[0] : datasetAnalysis.columns[0];
      handleColumnSelect(firstColumn.name);
    }
  }, [isVisible, datasetAnalysis, selectedColumn]);

  // Close column dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (columnDropdownRef.current && !columnDropdownRef.current.contains(event.target as Node)) {
        setIsColumnDropdownOpen(false);
      }
    };
    
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Fetch column info when dataset or scope changes (P1.4: only when visible).
  // P1.4 part 2: prefer the one-shot overview-bundle endpoint when the column
  // and DQS scopes match (the default case). Bundling cuts the Step 2 sidebar
  // open from 2-N parallel fan-outs to a single round-trip; when scopes differ
  // we fall through to the single-purpose endpoint.
  useEffect(() => {
    if (!isVisible) return;
    if (!datasetId) {
      setColumnInfo(null);
      return;
    }
    let cancelled = false;
    const loadColumnInfo = async () => {
      setIsLoadingColumnInfo(true);
      try {
        if (columnInfoScope === dqsScope) {
          const bundle = await fastApiService.loadOverviewBundle(datasetId, columnInfoScope);
          if (cancelled) return;
          setColumnInfo(bundle.columnInfo);
          // Opportunistically update DQS too - the dqs effect below will see
          // a cache hit on the backend and complete quickly, but this also
          // shortcuts the loading spinner if data arrives before that effect.
          setDqsData(bundle.dqs);
        } else {
          const info = await fastApiService.getColumnInfoByScope(datasetId, columnInfoScope);
          if (!cancelled) setColumnInfo(info);
        }
      } catch (error) {
        if (!cancelled) {
          console.error('Failed to fetch column info:', error);
          setColumnInfo(null);
        }
      } finally {
        if (!cancelled) setIsLoadingColumnInfo(false);
      }
    };
    loadColumnInfo();
    return () => { cancelled = true; };
  }, [isVisible, datasetId, columnInfoScope, dqsScope]);

  // Fetch compare-column-stats when EDA comparison is triggered (step 2 after duplicate removal)
  // edaRefreshKey is incremented to force a refetch after Auto QC executes all treatments
  // edaComparisonScope re-triggers fetch when the View Data filter changes
  // P1.4: only when visible.
  useEffect(() => {
    if (!isVisible) return;
    if (!datasetId || !showEDAComparison || currentStep !== 2) return;
    console.log('📊 Loading EDA comparison data (refreshKey:', edaRefreshKey, 'scope:', edaComparisonScope, ')');
    let cancelled = false;
    const loadComparison = async () => {
      setIsLoadingEdaComparison(true);
      setEdaComparisonError(null);
      try {
        const data = await fastApiService.compareColumnStats(datasetId, edaComparisonScope);
        if (!cancelled) {
          console.log('📊 EDA comparison data loaded:', data);
          setEdaComparisonData(data);
        }
      } catch (err) {
        if (!cancelled) {
          console.error('❌ Failed to load EDA comparison:', err);
          setEdaComparisonError(err instanceof Error ? err.message : 'Failed to load comparison');
          setEdaComparisonData(null);
        }
      } finally {
        if (!cancelled) setIsLoadingEdaComparison(false);
      }
    };
    loadComparison();
    return () => { cancelled = true; };
  }, [isVisible, datasetId, showEDAComparison, currentStep, edaRefreshKey, edaComparisonScope]);

  // Fetch DQS (Data Quality Score) when dataset or dqsScope changes (P1.4: only when visible).
  useEffect(() => {
    if (!isVisible) return;
    if (!datasetId) {
      setDqsData(null);
      setDqsError(null);
      setDqsRecommendations([]);
      return;
    }
    let cancelled = false;
    const loadDqs = async () => {
      setIsLoadingDqs(true);
      setDqsError(null);
      try {
        const dqs = await fastApiService.getDataQualityScoreByScope(datasetId, dqsScope);
        if (!cancelled) setDqsData(dqs);
      } catch (error) {
        if (!cancelled) {
          console.error('Failed to fetch DQS:', error);
          setDqsData(null);
          setDqsError(error instanceof Error ? error.message : 'Failed to calculate DQS');
        }
      } finally {
        if (!cancelled) setIsLoadingDqs(false);
      }
    };
    loadDqs();
    return () => { cancelled = true; };
  }, [isVisible, datasetId, dqsScope]);

  // Fetch DQS AI Recommendations when DQS data is available (P1.4: only when visible).
  useEffect(() => {
    if (!isVisible) return;
    if (!datasetId || !dqsData) {
      setDqsRecommendations([]);
      return;
    }
    let cancelled = false;
    const loadDqsRecommendations = async () => {
      setIsLoadingDqsRecommendations(true);
      try {
        const result = await fastApiService.generateDqsRecommendations(datasetId, dqsData);
        if (cancelled) return;
        if (result.success && result.recommendations) {
          setDqsRecommendations(result.recommendations);
        } else {
          console.warn('Failed to generate DQS recommendations:', result.error);
          setDqsRecommendations([]);
        }
      } catch (error) {
        if (!cancelled) {
          console.error('Failed to fetch DQS recommendations:', error);
          setDqsRecommendations([]);
        }
      } finally {
        if (!cancelled) setIsLoadingDqsRecommendations(false);
      }
    };
    loadDqsRecommendations();
    return () => { cancelled = true; };
  }, [isVisible, datasetId, dqsData]);

  // Fetch variable classification when dataset changes (P1.4: only when visible).
  useEffect(() => {
    if (!isVisible) return;
    if (datasetId && datasetAnalysis) {
      fetchVariableClassification();
    }
  }, [isVisible, datasetId, datasetAnalysis]);

  // Get category description helper function
  const getCategoryDescription = (category: string): string => {
    const descriptions: { [key: string]: string } = {
      'Borrower Demographics': 'Personal information about loan applicants',
      'Loan Characteristics': 'Details about the loan terms and structure',
      'Credit History': 'Past credit behavior and scores',
      'Financial Information': 'Income, employment, and financial status',
      'Risk Indicators': 'Factors that indicate potential default risk',
      'Temporal Variables': 'Time-based features and dates',
      'Geographic Data': 'Location-based information',
      'Behavioral Patterns': 'Historical behavior and patterns',
      'External Factors': 'Economic and market conditions',
      'Unknown': 'Uncategorized variables'
    };
    return descriptions[category] || 'Variable category information';
  };

  // CSV Download functionality
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
          // Convert to string and escape quotes
          const stringValue = String(value).replace(/"/g, '""');
          return `"${stringValue}"`;
        }).join(',')
      )
    ].join('\n');
    
    return csvContent;
  };

  const downloadPreviewAsCSV = () => {
    if (rawData.length === 0) {
      alert('No data to download');
      return;
    }

    try {
      // Convert data to CSV
      const csvContent = convertToCSV(rawData);
      
      // Create blob and download
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      
      if (link.download !== undefined) {
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', `${datasetId || 'dataset'}_preview_${rawData.length}_rows.csv`);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
      }
    } catch (error) {
      console.error('Failed to download CSV:', error);
      alert('Failed to download CSV file');
    }
  };

  // Download Chart and AI Insights as PNG image
  const downloadChartAndInsightsAsImage = async () => {
    try {
      const html2canvas = (await import('html2canvas')).default;
      
      // Find the full distribution section (chart + insights)
      const distributionSection = document.querySelector('[data-testid="distribution-section"]');
      
      if (!distributionSection) {
        alert('Distribution section not found');
        return;
      }
      
      // Capture as canvas with high quality
      const canvas = await html2canvas(distributionSection as HTMLElement, {
        backgroundColor: '#ffffff',
        scale: 2,
        useCORS: true,
        allowTaint: true,
        logging: false,
        onclone: (clonedDoc) => {
          // Ensure dark mode elements render with light background for export
          const clonedSection = clonedDoc.querySelector('[data-testid="distribution-section"]');
          if (clonedSection) {
            (clonedSection as HTMLElement).style.backgroundColor = '#ffffff';
            // Make all text dark for better visibility
            clonedSection.querySelectorAll('*').forEach((el) => {
              const element = el as HTMLElement;
              if (element.classList.contains('dark:text-gray-100') || 
                  element.classList.contains('dark:text-gray-200') ||
                  element.classList.contains('dark:text-gray-300') ||
                  element.classList.contains('dark:text-gray-400')) {
                element.style.color = '#374151';
              }
              if (element.classList.contains('dark:bg-gray-800') ||
                  element.classList.contains('dark:bg-gray-900')) {
                element.style.backgroundColor = '#ffffff';
              }
              if (element.classList.contains('dark:border-gray-700') ||
                  element.classList.contains('dark:border-gray-600')) {
                element.style.borderColor = '#e5e7eb';
              }
            });
          }
        }
      });
      
      // Convert to image and download
      const link = document.createElement('a');
      const columnName = selectedColumns.length > 0 
        ? selectedColumns.join('_').substring(0, 50) 
        : selectedColumn || 'distribution';
      link.download = `Distribution_${columnName}_${new Date().toISOString().split('T')[0]}.png`;
      link.href = canvas.toDataURL('image/png');
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (error) {
      console.error('Failed to download chart and insights as image:', error);
      alert('Failed to download image');
    }
  };

  const downloadKnowledgeGraphCSV = async () => {
    try {
      if (!knowledgeGraphData?.html_content) {
        alert('No feature graph data available to export');
        return;
      }

      // Extract nodes and links data from HTML content
      // Include the interactive HTML file
      const htmlContent = knowledgeGraphData.html_content;
      
      // Extract nodesData and linksData from the embedded JavaScript
      const nodesMatch = htmlContent.match(/const nodesData = (\[[\s\S]*?\]);/);
      const linksMatch = htmlContent.match(/const linksData = (\[[\s\S]*?\]);/);
      
      if (!nodesMatch || !linksMatch) {
        alert('Unable to extract feature graph data from HTML');
        return;
      }

      let nodesData, linksData;
      try {
        nodesData = JSON.parse(nodesMatch[1]);
        linksData = JSON.parse(linksMatch[1]);
      } catch (e) {
        alert('Error parsing feature graph data');
        return;
      }

      // Create nodes CSV content
      const nodesCsvContent = [
        'Node Name,Category Name',
        ...nodesData.map((node: any) => 
          `"${node.id}","${node.group === 'category' ? 'Categorical Node' : node.group}"`
        )
      ].join('\n');

      // Create relationships CSV content
      const relationshipsCsvContent = [
        'Source Node,Source Category,Target Node,Target Category',
        ...linksData.map((link: any) => {
          const sourceNode = nodesData.find((n: any) => n.id === link.source);
          const targetNode = nodesData.find((n: any) => n.id === link.target);
          
          const sourceCategory = sourceNode ? (sourceNode.group === 'category' ? 'Categorical Node' : sourceNode.group) : '';
          const targetCategory = targetNode ? (targetNode.group === 'category' ? 'Categorical Node' : targetNode.group) : '';
          
          return `"${link.source}","${sourceCategory}","${link.target}","${targetCategory}"`;
        })
      ].join('\n');

      // Create ZIP file with CSVs and screenshot
      const zip = new JSZip();
      zip.file('nodes.csv', nodesCsvContent);
      zip.file('relationships.csv', relationshipsCsvContent);
      zip.file('knowledge_graph.html', htmlContent);

      
      // Generate and download ZIP file
      const zipBlob = await zip.generateAsync({ type: 'blob' });
      const url = URL.createObjectURL(zipBlob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'FeatureGraph.zip';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);

    } catch (error) {
      console.error('Error exporting feature graph:', error);
      alert('Failed to export feature graph data');
    }
  };

  type KnowledgeGraphState = {
    html_content?: string;
    algorithm_explanation?: string;
    relationship_mapping?: string;
    usage_instructions?: string;
    processing_info?: KnowledgeGraphProcessingInfo;
    error?: string;
    variableCategoryDistribution?: {
      categories: Record<string, number>;
      colors: Record<string, string>;
    };
  };
  
  const DEFAULT_ALGORITHM_EXPLANATION =
    'Knowledge graph generated from dataset metadata and data dictionary.';
  const DEFAULT_RELATIONSHIP_MAPPING =
    'Variables are connected based on their semantic relationships and the curated data dictionary.';
  const DEFAULT_USAGE_INSTRUCTIONS =
    'Interact with the graph to explore relationships between variables. Use the controls to filter and navigate the visualization.';

  // Action handlers
  const handleViewRawData = async () => {
    console.log('handleViewRawData called with datasetId:', datasetId);
    
    if (!datasetId) {
      alert('No dataset selected. Please upload a dataset first.');
      return;
    }

    // Check if dataset still exists on server
    const isValid = await checkDatasetValidity(datasetId);
    if (!isValid) {
      alert('Dataset no longer exists on the server. This usually happens after a server restart. Please upload your dataset again.');
      return;
    }

    setIsLoadingRawData(true);
    try {
      console.log('Calling fastApiService.getRawData with datasetId:', datasetId);
      const result = await fastApiService.getRawData(datasetId, 10);
      console.log('Raw data result:', result);
      setRawData(result.data);
      setShowRawDataModal(true);
    } catch (error) {
      console.error('Failed to load raw data:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
      console.error('Error details:', {
        message: errorMessage,
        stack: error instanceof Error ? error.stack : undefined,
        datasetId: datasetId
      });
      
      // Provide more specific and helpful error messages
      if (errorMessage.includes('Failed to fetch')) {
        alert('Unable to connect to the backend server. Please check if the backend is running on port 8000.');
      } else if (errorMessage.includes('Dataset not found') || errorMessage.includes('missing file') || errorMessage.includes('upload a dataset first')) {
        alert('Dataset not found. This usually happens after a server restart. Please upload your dataset again to view raw data.');
      } else if (errorMessage.includes('Dataset was removed due to missing file')) {
        alert('Dataset file is missing from server storage. Please upload your dataset again.');
      } else if (errorMessage.includes('404')) {
        alert('Dataset not found on server. Please upload your dataset again.');
      } else if (errorMessage.includes('500') || errorMessage.includes('Internal server error')) {
        alert('Server error occurred. The dataset file may be corrupted or inaccessible. Please try uploading your dataset again.');
      } else {
        alert(`Failed to load raw data: ${errorMessage}`);
      }
    } finally {
      setIsLoadingRawData(false);
    }
  };


  const handleEditConfig = () => {
    // Update form with current dataset config when opening modal
    setConfigForm({
      target_variable: localDatasetConfig?.target_variable || '',
      target_variable_type: localDatasetConfig?.target_variable_type || 'Numerical',
      problem_statement: localDatasetConfig?.problem_statement || '',
      data_dictionary: localDatasetConfig?.data_dictionary || ''
    });
    setDataDictionaryFile(null); // Clear file state when opening modal
    setShowConfigModal(true);
  };

  const handleDataDictionaryFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (file.name.endsWith('.csv')) {
        setDataDictionaryFile(file);
      } else {
        alert('Please select a CSV file');
      }
    }
  };

  const handleRemoveDataDictionaryFile = () => {
    setDataDictionaryFile(null);
  };

  const handleSaveConfig = async () => {
    if (!datasetId) {
      alert('No dataset selected');
      return;
    }

    setIsLoadingConfig(true);
    try {
      const response = await fastApiService.updateDatasetConfig(datasetId, configForm, dataDictionaryFile);
      console.log('Configuration updated successfully:', response);
      
      // Update local dataset config with the response
      if (response.config) {
        // Extract only the properties we need and ensure type safety
        setLocalDatasetConfig({
          target_variable: response.config.target_variable,
          target_variable_type: response.config.target_variable_type as 'Numerical' | 'Categorical',
          problem_statement: response.config.problem_statement,
          data_dictionary: response.config.data_dictionary,
        });
        console.log('Local dataset config updated:', response.config);
        if (datasetId) {
          setKnowledgeGraphCache(prev => {
            const next = new Map(prev);
            next.delete(datasetId);
            return next;
          });
        }
      }
      
      // Close config modal and clear file state
      setShowConfigModal(false);
      setDataDictionaryFile(null);
      
      // Show success modal
      setShowConfigSuccessModal(true);
    } catch (error) {
      console.error('Failed to update configuration:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
      alert(`Failed to update configuration: ${errorMessage}`);
    } finally {
      setIsLoadingConfig(false);
    }
  };

  const handleGenerateKnowledgeGraph = async (forceRefresh: boolean = false) => {
    if (!datasetId) {
      alert('No dataset selected');
      return;
    }

    // Check if data dictionary is uploaded
    if (!localDatasetConfig?.data_dictionary) {
      console.warn('No data dictionary uploaded');
      setShowNoDictionaryModal(true);
      return;
    }

    // Show loading immediately
    setIsLoadingKnowledgeGraph(true);

    try {
      // First, check local cache (instant) - this might have been populated by SSE
      if (!forceRefresh) {
        const cached = knowledgeGraphCache.get(getKgCacheKey(datasetId));
        if (cached && cached.html_content) {
          console.log('📦 Found cached feature graph, displaying inline');
          const { timestamp: _timestamp, ...graphState } = cached;
          setKnowledgeGraphData(graphState);
          setIsLoadingKnowledgeGraph(false);
          
          // Still subscribe to SSE for updates if not complete
          if (graphState.processing_info?.status !== 'complete') {
            ensureRealtimeUpdates(datasetId, graphState.processing_info?.status);
          }
          return;
        }
      }

      // Check backend cache (network call)
      const hydrationStatus = await hydrateKnowledgeGraphFromBackend(datasetId);

      if (hydrationStatus === 'ready' || hydrationStatus === 'pending') {
        // Re-check cache after hydration (it might have been updated)
        const cached = knowledgeGraphCache.get(getKgCacheKey(datasetId));
        if (cached && cached.html_content) {
          // We have a partial or complete result - show it inline
          const { timestamp: _timestamp, ...graphState } = cached;
          setKnowledgeGraphData(graphState);
          setIsLoadingKnowledgeGraph(false);
          
          // Subscribe to SSE for updates if not complete
          if (graphState.processing_info?.status !== 'complete') {
            ensureRealtimeUpdates(datasetId, 'partial');
          }
        } else {
          // No cached data yet - show "generating" message inline
          setKnowledgeGraphData({
            algorithm_explanation: 'Feature graph is being generated in the background...',
            relationship_mapping: 'This may take a few moments depending on dataset size.',
            usage_instructions: 'The graph will appear here once generation completes.',
            processing_info: { status: 'partial' },
          });
          setIsLoadingKnowledgeGraph(false);
          
          // Subscribe to SSE - it will update the graph when first batch is ready
          ensureRealtimeUpdates(datasetId, 'partial');
        }
        return;
      }

      // No cache found - trigger new generation
      console.log('🕸️ No cached graph found, triggering generation for dataset:', datasetId);
      const response = await fastApiService.generateKnowledgeGraph(datasetId);

      if (response.success && response.html_content) {
        const graphState = buildGraphState(response);
        cacheKnowledgeGraphResult(datasetId, graphState);
        showKnowledgeGraphToUser(datasetId, graphState);
      } else {
        const errorMessage = response.error || response.message || 'Failed to generate feature graph';
        console.error('Feature graph generation failed:', errorMessage);
        const errorData: KnowledgeGraphState = {
          error: errorMessage,
          algorithm_explanation: '',
          relationship_mapping: '',
          usage_instructions: '',
        };
        cacheKnowledgeGraphResult(datasetId, errorData);
        setKnowledgeGraphData(errorData);
      }
    } catch (error) {
      console.error('Failed to generate feature graph:', error);
      const message = error instanceof Error ? error.message : 'Unknown error occurred';
      setKnowledgeGraphData({
        error: `Network error: ${message}`,
        algorithm_explanation: '',
        relationship_mapping: '',
        usage_instructions: '',
      });
    } finally {
      setIsLoadingKnowledgeGraph(false);
    }
  };
  
  // Add this new function right after handleGenerateKnowledgeGraph
  // Replace polling with Server-Sent Events
  const startPollingForUpdates = (datasetId: string) => {
    if (sseCleanupRef.current) {
      sseCleanupRef.current();
    }

    console.log('📡 Starting SSE stream for knowledge graph updates');
    const token = authService.getToken();

    if (!token) {
      console.error('❌ No auth token available for SSE stream');
      return;
    }

    const eventSource = fastApiService.createKnowledgeGraphStream(datasetId, token);

    const cleanup = () => {
      console.log('Closing knowledge graph SSE connection');
      eventSource.close();
      sseCleanupRef.current = null;
    };

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.event === 'complete') {
          console.log('✅ Knowledge graph generation completed!');
          setIsLoadingKnowledgeGraph(false);
          cleanup();
          return;
        }

        if (data.event === 'error') {
          console.error('❌ Knowledge graph generation error:', data.message);
          setIsLoadingKnowledgeGraph(false);
          cleanup();
          return;
        }

        if (data.event === 'timeout') {
          console.warn('⏱️ Knowledge graph generation timeout');
          setIsLoadingKnowledgeGraph(false);
          cleanup();
          return;
        }

        if (data.html_content) {
          console.log('📊 SSE: Received knowledge graph update', {
            hasHtml: !!data.html_content,
            hasNodes: data.nodes?.length,
            hasCategories: data.categories?.length,
            status: data.processing_info?.status,
            batches: `${data.processing_info?.completed_batches}/${data.processing_info?.total_batches}`
          });
          
          const graphState = buildGraphState(data);
          console.log('📊 SSE: Graph state after build:', {
            hasVariableDist: !!graphState.variableCategoryDistribution,
            categoryCount: graphState.variableCategoryDistribution ? Object.keys(graphState.variableCategoryDistribution.categories).length : 0,
            variableCount: graphState.variableCategoryDistribution ? Object.values(graphState.variableCategoryDistribution.categories).reduce((a, b) => a + b, 0) : 0
          });
          
          cacheKnowledgeGraphResult(datasetId, graphState);

          // Always update the data - this ensures the inline Graph tab gets all updates
          setKnowledgeGraphData(prev => {
            console.log('📊 SSE: Updating knowledgeGraphData', {
              hadPrev: !!prev,
              willUpdate: true,
              newStatus: graphState.processing_info?.status,
              prevStatus: prev?.processing_info?.status
            });
            // Always use the new graphState to ensure we have latest data
            return graphState;
          });

          // Stop loading indicator when we have content
          if (graphState.html_content) {
            setIsLoadingKnowledgeGraph(false);
          }

          if (graphState.processing_info?.status === 'complete') {
            console.log('✅ SSE: Knowledge graph complete, cleaning up');
            cleanup();
          }
        }
      } catch (error) {
        console.error('Error parsing SSE data:', error);
      }
    };

    eventSource.onerror = (error) => {
      console.error('SSE connection error:', error);
      cleanup();
    };

    sseCleanupRef.current = cleanup;
    return cleanup;
  };


  const handleExportToPDF = async () => {
    if (!datasetId || !datasetAnalysis) {
      alert('No dataset available for export');
      return;
    }

    console.log('Starting PDF export...');
    console.log('Dataset ID:', datasetId);
    console.log('Dataset Analysis:', datasetAnalysis);
    console.log('Variable Classification:', variableClassification);
    console.log('Selected Column:', selectedColumn);
    console.log('Column Distribution:', columnDistribution);
    console.log('Dataset Stats:', datasetStats);

    setIsLoadingPDFExport(true);
    try {
      // Dynamic import of jsPDF and html2canvas to avoid SSR issues
      const [jsPDF, html2canvas] = await Promise.all([
        import('jspdf'),
        import('html2canvas')
      ]);

      const { default: jsPDFDefault } = jsPDF;
      const { default: html2canvasDefault } = html2canvas;
      
      console.log('jsPDF and html2canvas imported successfully');

      // Create PDF document
      const pdf = new jsPDFDefault('p', 'mm', 'a4');
      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();
      const margin = 20;
      const contentWidth = pageWidth - (2 * margin);
      let yPosition = margin;

      // Helper function to add text with word wrapping
      const addWrappedText = (text: string, y: number, fontSize: number = 12, fontStyle: string = 'normal') => {
        pdf.setFontSize(fontSize);
        pdf.setFont('helvetica', fontStyle);
        
        const lines = pdf.splitTextToSize(text, contentWidth);
        pdf.text(lines, margin, y);
        return y + (lines.length * fontSize * 0.4);
      };

      // Helper function to add a section header
      const addSectionHeader = (text: string, y: number) => {
        yPosition = addWrappedText(text, y, 16, 'bold');
        yPosition += 5;
        return yPosition;
      };

      // Helper function to add a subsection
      const addSubsection = (title: string, content: string, y: number) => {
        yPosition = addWrappedText(title, y, 14, 'bold');
        yPosition += 2;
        yPosition = addWrappedText(content, yPosition, 10, 'normal');
        yPosition += 5;
        return yPosition;
      };

      // Helper function to add a table row
      const addTableRow = (label: string, value: string, y: number) => {
        pdf.setFontSize(10);
        pdf.setFont('helvetica', 'normal');
        pdf.text(label, margin, y);
        pdf.text(value, margin + 80, y);
        return y + 5;
      };

      // Check if we need a new page
      const checkNewPage = (requiredSpace: number) => {
        if (yPosition + requiredSpace > pageHeight - margin) {
          pdf.addPage();
          yPosition = margin;
        }
      };

      // Title Page
      pdf.setFillColor(59, 130, 246, 0.1);
      pdf.rect(0, 0, pageWidth, pageHeight, 'F');
      
      yPosition = addWrappedText('DATASET SUMMARY REPORT', pageHeight / 2 - 20, 24, 'bold');
      yPosition = addWrappedText(`Dataset ID: ${datasetId}`, yPosition + 10, 14, 'normal');
      yPosition = addWrappedText(`Generated: ${new Date().toLocaleDateString()}`, yPosition + 5, 12, 'normal');
      
      pdf.addPage();
      yPosition = margin;

      // Dataset Overview Section
      yPosition = addSectionHeader('1. DATASET OVERVIEW', yPosition);
      
      checkNewPage(30);
      yPosition = addSubsection('Basic Information', 
        `This dataset contains ${datasetAnalysis.totalRows.toLocaleString()} records with ${datasetAnalysis.totalColumns} columns.`, 
        yPosition
      );

      checkNewPage(40);
      yPosition = addSubsection('Data Types', 
        `Numerical: ${datasetStats.dataTypes.numerical}, Categorical: ${datasetStats.dataTypes.categorical}, Datetime: ${datasetStats.dataTypes.datetime}`, 
        yPosition
      );

      // Dataset Summary Table
      checkNewPage(60);
      yPosition = addSectionHeader('2. DATASET SUMMARY TABLE', yPosition);
      
      // Create summary table
      const summaryTableData = [
        ['Metric', 'Value', 'Details'],
        ['Total Records', datasetAnalysis.totalRows.toLocaleString(), 'Total number of data rows'],
        ['Total Columns', datasetAnalysis.totalColumns.toString(), 'Total number of columns'],
        ['Numerical Columns', datasetStats.dataTypes.numerical.toString(), 'Columns with numerical data'],
        ['Categorical Columns', datasetStats.dataTypes.categorical.toString(), 'Columns with categorical data'],
        ['Datetime Columns', datasetStats.dataTypes.datetime.toString(), 'Columns with datetime data'],
        ['High Missing (>95%)', datasetStats.missingValues.toString(), 'Columns with >95% missing values'],
        ['Duplicate Rows', datasetStats.duplicateRows.toString(), 'Rows with duplicate values'],
        ['Quality Score', `${qualityScore}%`, 'Overall data quality assessment']
      ];

      // Add table header
      pdf.setFontSize(10);
      pdf.setFont('helvetica', 'bold');
      pdf.text('Metric', margin, yPosition);
      pdf.text('Value', margin + 80, yPosition);
      pdf.text('Details', margin + 160, yPosition);
      yPosition += 8;

      // Add table rows
      pdf.setFont('helvetica', 'normal');
      for (let i = 1; i < summaryTableData.length; i++) {
        checkNewPage(20);
        const row = summaryTableData[i];
        pdf.text(row[0], margin, yPosition);
        pdf.text(row[1], margin + 80, yPosition);
        pdf.text(row[2], margin + 160, yPosition);
        yPosition += 6;
      }
      yPosition += 10;

      // Key Statistics Table
      checkNewPage(50);
      yPosition = addSectionHeader('3. KEY STATISTICS', yPosition);
      
      checkNewPage(30);
      yPosition = addTableRow('Total Records:', datasetStats.totalRecords.toLocaleString(), yPosition);
      yPosition = addTableRow('Total Columns:', datasetStats.totalColumns.toString(), yPosition);
      yPosition = addTableRow('High Missing (>95%):', datasetStats.missingValues.toLocaleString(), yPosition);
      yPosition = addTableRow('Duplicate Rows:', datasetStats.duplicateRows.toLocaleString(), yPosition);

      // Data Treatment Section
      checkNewPage(40);
      yPosition = addSectionHeader('4. DATA QUALITY ASSESSMENT', yPosition);
      
      const qualityMetrics = getDataQualityMetrics();
      const consistencyMetrics = getConsistencyMetrics();
      
      checkNewPage(30);
      yPosition = addSubsection('Structural Issues', 
        `Empty Columns: ${qualityMetrics.emptyColumns}, Constant Columns: ${qualityMetrics.constantColumns}, Sparse Columns: ${qualityMetrics.sparseColumns}`, 
        yPosition
      );

      // Data Treatment Summary Table
      checkNewPage(80);
      yPosition = addWrappedText('Data Treatment Summary:', yPosition, 12, 'bold');
      yPosition += 5;
      
      // Create quality summary table
      const qualityTableData = [
        ['Quality Metric', 'Count', 'Status'],
        ['Empty Columns (100% missing)', qualityMetrics.emptyColumns.toString(), qualityMetrics.emptyColumns === 0 ? '✅ Good' : '⚠️ Needs Attention'],
        ['Constant Columns', qualityMetrics.constantColumns.toString(), qualityMetrics.constantColumns === 0 ? '✅ Good' : '⚠️ Needs Attention'],
        ['Sparse Columns (>90% missing)', qualityMetrics.sparseColumns.toString(), qualityMetrics.sparseColumns === 0 ? '✅ Good' : '⚠️ Needs Attention'],
        ['Formatting Issues', consistencyMetrics.formattingIssues.toString(), consistencyMetrics.formattingIssues === 0 ? '✅ Good' : '⚠️ Needs Attention'],
        ['Total Issues', (qualityMetrics.emptyColumns + qualityMetrics.constantColumns + qualityMetrics.sparseColumns + consistencyMetrics.formattingIssues).toString(), 'Overall Assessment']
      ];

      // Add quality table header
      pdf.setFontSize(9);
      pdf.setFont('helvetica', 'bold');
      pdf.text('Quality Metric', margin, yPosition);
      pdf.text('Count', margin + 100, yPosition);
      pdf.text('Status', margin + 160, yPosition);
      yPosition += 6;

      // Add quality table rows
      pdf.setFont('helvetica', 'normal');
      for (let i = 1; i < qualityTableData.length; i++) {
        checkNewPage(20);
        const row = qualityTableData[i];
        pdf.text(row[0], margin, yPosition);
        pdf.text(row[1], margin + 100, yPosition);
        pdf.text(row[2], margin + 160, yPosition);
        yPosition += 5;
      }
      yPosition += 10;

      checkNewPage(30);
      yPosition = addSubsection('Consistency Issues', 
        `Formatting Issues: ${consistencyMetrics.formattingIssues}`, 
        yPosition
      );

      // Target Variable Information
      if (localDatasetConfig?.target_variable) {
        checkNewPage(40);
        yPosition = addSectionHeader('5. TARGET VARIABLE', yPosition);
        
        checkNewPage(30);
        yPosition = addSubsection('Configuration', 
          `Name: ${localDatasetConfig?.target_variable || 'N/A'}, Type: ${localDatasetConfig?.target_variable_type || 'N/A'}`,
          yPosition
        );

        // Target Variable Summary Table
        if (datasetStats.targetDistribution && Object.keys(datasetStats.targetDistribution).length > 0) {
          checkNewPage(60);
          yPosition = addWrappedText('Target Variable Distribution:', yPosition, 12, 'bold');
          yPosition += 5;
          
          // Create target distribution table
          const targetTableData = [
            ['Class/Value', 'Count', 'Percentage', 'Cumulative %']
          ];
          
          let cumulativeCount = 0;
          const totalRecords = datasetStats.totalRecords;
          
          Object.entries(datasetStats.targetDistribution).forEach(([key, value]) => {
            const percentage = (value / totalRecords * 100).toFixed(1);
            cumulativeCount += value;
            const cumulativePercentage = (cumulativeCount / totalRecords * 100).toFixed(1);
            targetTableData.push([key, value.toLocaleString(), `${percentage}%`, `${cumulativePercentage}%`]);
          });
          
          // Add target table header
          pdf.setFontSize(9);
          pdf.setFont('helvetica', 'bold');
          pdf.text('Class/Value', margin, yPosition);
          pdf.text('Count', margin + 80, yPosition);
          pdf.text('Percentage', margin + 130, yPosition);
          pdf.text('Cumulative %', margin + 180, yPosition);
          yPosition += 6;

          // Add target table rows
          pdf.setFont('helvetica', 'normal');
          for (let i = 1; i < targetTableData.length; i++) {
            checkNewPage(20);
            const row = targetTableData[i];
            pdf.text(row[0], margin, yPosition);
            pdf.text(row[1], margin + 80, yPosition);
            pdf.text(row[2], margin + 130, yPosition);
            pdf.text(row[3], margin + 180, yPosition);
            yPosition += 5;
          }
          yPosition += 10;
        }
      }

      // Column Details Section
      if (columnInfo && columnInfo.columns_info.length > 0) {
        checkNewPage(40);
        yPosition = addSectionHeader('6. COLUMN DETAILS', yPosition);
        
        // Add column information table
        for (let i = 0; i < columnInfo.columns_info.length; i++) {
          const col = columnInfo.columns_info[i];
          const columnType = col.column_type || (['int64', 'float64', 'int32', 'float32'].includes(col.data_type) ? 'Numerical' : 'Categorical');
          
          checkNewPage(40);
          yPosition = addSubsection(`Column ${i + 1}: ${col.column_name}`, 
            `Type: ${columnType} (${col.data_type}), Missing: ${col.missing_count}, Unique: ${col.unique_count}`, 
            yPosition
          );

          if (col.mean !== null && col.mean !== undefined || col.median !== null && col.median !== undefined || col.mode !== null && col.mode !== undefined) {
            checkNewPage(20);
            const stats = [];
            if (col.mean !== null && col.mean !== undefined) stats.push(`Mean: ${col.mean.toFixed(2)}`);
            if (col.median !== null && col.median !== undefined) stats.push(`Median: ${col.median.toFixed(2)}`);
            if (col.mode !== null && col.mode !== undefined) stats.push(`Mode: ${col.mode}`);
            yPosition = addWrappedText(`Statistics: ${stats.join(', ')}`, yPosition, 10, 'normal');
            yPosition += 5;
          }

          // Add percentile information if available
          if (col.percentile_5 !== null && col.percentile_5 !== undefined || 
              col.percentile_25 !== null && col.percentile_25 !== undefined || 
              col.percentile_75 !== null && col.percentile_75 !== undefined ||
              col.percentile_95 !== null && col.percentile_95 !== undefined ||
              col.percentile_99 !== null && col.percentile_99 !== undefined) {
            checkNewPage(20);
            const percentiles = [];
            if (col.percentile_5 !== null && col.percentile_5 !== undefined) percentiles.push(`p5%: ${col.percentile_5.toFixed(2)}`);
            if (col.percentile_25 !== null && col.percentile_25 !== undefined) percentiles.push(`p25%: ${col.percentile_25.toFixed(2)}`);
            if (col.percentile_75 !== null && col.percentile_75 !== undefined) percentiles.push(`p75%: ${col.percentile_75.toFixed(2)}`);
            if (col.percentile_95 !== null && col.percentile_95 !== undefined) percentiles.push(`p95%: ${col.percentile_95.toFixed(2)}`);
            if (col.percentile_99 !== null && col.percentile_99 !== undefined) percentiles.push(`p99%: ${col.percentile_99.toFixed(2)}`);
            yPosition = addWrappedText(`Percentiles: ${percentiles.join(', ')}`, yPosition, 10, 'normal');
            yPosition += 5;
          }

          // Check if we need a new page after each column
          if (i < columnInfo.columns_info.length - 1) {
            checkNewPage(30);
          }
        }
      }

      // Variable Classification Section
      if (variableClassification && variableClassification.classification) {
        checkNewPage(40);
        yPosition = addSectionHeader('7. VARIABLE CLASSIFICATION', yPosition);
        
        const categoryCounts: Record<string, number> = {};
        variableClassification.classification.variables.forEach(variable => {
          const category = variable.category || 'Unknown';
          categoryCounts[category] = (categoryCounts[category] || 0) + 1;
        });

        checkNewPage(30);
        yPosition = addSubsection('Category Distribution', 
          Object.entries(categoryCounts)
            .map(([category, count]) => `${category}: ${count} variables`)
            .join(', '), 
          yPosition
        );

        // Variable Classification Summary Table
        checkNewPage(60);
        yPosition = addWrappedText('Variable Categories Summary:', yPosition, 12, 'bold');
        yPosition += 5;
        
        // Create variable classification table
        const variableTableData = [
          ['Category', 'Count', 'Percentage', 'Description']
        ];
        
        const totalVariables = variableClassification.classification.variables.length;
        
        Object.entries(categoryCounts).forEach(([category, count]) => {
          const percentage = (count / totalVariables * 100).toFixed(1);
          const description = getCategoryDescription(category);
          variableTableData.push([category, count.toString(), `${percentage}%`, description]);
        });
        
        // Add variable table header
        pdf.setFontSize(9);
        pdf.setFont('helvetica', 'bold');
        pdf.text('Category', margin, yPosition);
        pdf.text('Count', margin + 80, yPosition);
        pdf.text('Percentage', margin + 130, yPosition);
        pdf.text('Description', margin + 180, yPosition);
        yPosition += 6;

        // Add variable table rows
        pdf.setFont('helvetica', 'normal');
        for (let i = 1; i < variableTableData.length; i++) {
          checkNewPage(20);
          const row = variableTableData[i];
          pdf.text(row[0], margin, yPosition);
          pdf.text(row[1], margin + 80, yPosition);
          pdf.text(row[2], margin + 130, yPosition);
          pdf.text(row[3], margin + 180, yPosition);
          yPosition += 5;
        }
        yPosition += 10;
      }

      // Distribution Charts Section
      yPosition = addSectionHeader('8. DISTRIBUTION CHARTS', yPosition);
      
      // Capture and add Variable Classification Pie Chart
      if (variableClassification && variableClassification.classification) {
        try {
          console.log('Attempting to capture pie chart...');
          console.log('Variable classification data:', variableClassification);
          
          // Small delay to ensure charts are fully rendered
          await new Promise(resolve => setTimeout(resolve, 500));
          
          // Find the pie chart element - try multiple selectors
          const pieChartElement = document.querySelector('[data-testid="variable-classification-pie-chart"]') || 
                                 document.querySelector('.h-96 canvas') ||
                                 document.querySelector('.h-96 .chartjs-render-monitor') ||
                                 document.querySelector('.h-96');
          
          console.log('Pie chart element found:', pieChartElement);
          console.log('Pie chart element type:', pieChartElement?.tagName);
          console.log('Pie chart element classes:', pieChartElement?.className);
          
          if (pieChartElement) {
            checkNewPage(80);
            yPosition = addSubsection('Variable Categories Distribution', 
              'Pie chart showing the distribution of variables across different categories.', 
              yPosition
            );
            
            console.log('Attempting to capture pie chart with html2canvas...');
            // Capture the chart as image
            const pieChartImage = await html2canvasDefault(pieChartElement as HTMLElement, {
              backgroundColor: '#ffffff',
              scale: 2,
              logging: true, // Enable logging for debugging
              useCORS: true,
              allowTaint: true
            });
            
            console.log('Pie chart captured successfully:', pieChartImage);
            console.log('Pie chart dimensions:', pieChartImage.width, 'x', pieChartImage.height);
            
            // Add the image to PDF
            const imgData = pieChartImage.toDataURL('image/png');
            console.log('Pie chart image data length:', imgData.length);
            
            const imgWidth = 120;
            const imgHeight = (pieChartImage.height * imgWidth) / pieChartImage.width;
            
            pdf.addImage(imgData, 'PNG', margin, yPosition, imgWidth, imgHeight);
            console.log('Pie chart added to PDF at position:', yPosition);
            yPosition += imgHeight + 10;
          } else {
            console.warn('Pie chart element not found');
          }
        } catch (error) {
          console.error('Failed to capture pie chart:', error);
          yPosition = addSubsection('Variable Categories Distribution', 
            'Chart capture failed. Distribution data available in text format.', 
            yPosition
          );
        }
      }
      
      // Try to capture any other Chart.js charts that might be present
      try {
        console.log('Attempting to capture additional canvas elements...');
        const allChartCanvases = document.querySelectorAll('canvas');
        console.log('Total canvas elements found:', allChartCanvases.length);
        
        if (allChartCanvases.length > 0) {
          checkNewPage(80);
          yPosition = addSubsection('Additional Charts', 
            'Additional charts found in the dataset overview.', 
            yPosition
          );
          
          for (let i = 0; i < Math.min(allChartCanvases.length, 3); i++) { // Limit to 3 charts
            const canvas = allChartCanvases[i];
            console.log(`Processing canvas ${i}:`, canvas);
            console.log(`Canvas ${i} dimensions:`, canvas.width, 'x', canvas.height);
            
            try {
              const chartImage = await html2canvasDefault(canvas as HTMLElement, {
                backgroundColor: '#ffffff',
                scale: 2,
                logging: true, // Enable logging for debugging
                useCORS: true,
                allowTaint: true
              });
              
              console.log(`Canvas ${i} captured successfully:`, chartImage);
              
              const imgData = chartImage.toDataURL('image/png');
              console.log(`Canvas ${i} image data length:`, imgData.length);
              
              const imgWidth = 100;
              const imgHeight = (chartImage.height * imgWidth) / chartImage.width;
              
              pdf.addImage(imgData, 'PNG', margin, yPosition, imgWidth, imgHeight);
              console.log(`Canvas ${i} added to PDF at position:`, yPosition);
              yPosition += imgHeight + 10;
            } catch (canvasError) {
              console.error(`Failed to capture canvas ${i}:`, canvasError);
            }
          }
        } else {
          console.log('No canvas elements found in the DOM');
        }
      } catch (error) {
        console.error('Failed to capture additional charts:', error);
      }
      
      // Capture and add Column Distribution Bar Chart
      if (selectedColumn && Object.keys(columnDistribution).length > 0) {
        try {
          console.log('Attempting to capture bar chart...');
          console.log('Selected column:', selectedColumn);
          console.log('Column distribution data:', columnDistribution);
          
          // Small delay to ensure charts are fully rendered
          await new Promise(resolve => setTimeout(resolve, 500));
          
          // Find the bar chart element - try multiple selectors
          const barChartElement = document.querySelector('[data-testid="column-distribution-bar-chart"]') || 
                                 document.querySelector('.h-64 canvas') ||
                                 document.querySelector('.h-64 .chartjs-render-monitor') ||
                                 document.querySelector('.h-64');
          
          console.log('Bar chart element found:', barChartElement);
          console.log('Bar chart element type:', barChartElement?.tagName);
          console.log('Bar chart element classes:', barChartElement?.className);
          
          if (barChartElement) {
            checkNewPage(80);
            yPosition = addSubsection(`Column Distribution: ${selectedColumn}`, 
              `Bar chart showing the distribution of values in the "${selectedColumn}" column.`, 
              yPosition
            );
            
            console.log('Attempting to capture bar chart with html2canvas...');
            // Capture the chart as image
            const barChartImage = await html2canvasDefault(barChartElement as HTMLElement, {
              backgroundColor: '#ffffff',
              scale: 2,
              logging: true, // Enable logging for debugging
              useCORS: true,
              allowTaint: true
            });
            
            console.log('Bar chart captured successfully:', barChartImage);
            console.log('Bar chart dimensions:', barChartImage.height, 'x', barChartImage.width);
            
            // Add the image to PDF
            const imgData = barChartImage.toDataURL('image/png');
            console.log('Bar chart image data length:', imgData.length);
            
            const imgWidth = 120;
            const imgHeight = (barChartImage.height * imgWidth) / barChartImage.width;
            
            pdf.addImage(imgData, 'PNG', margin, yPosition, imgWidth, imgHeight);
            console.log('Bar chart added to PDF at position:', yPosition);
            yPosition += imgHeight + 10;
          } else {
            console.warn('Bar chart element not found');
          }
        } catch (error) {
          console.error('Failed to capture bar chart:', error);
          yPosition = addSubsection(`Column Distribution: ${selectedColumn}`, 
            'Chart capture failed. Distribution data available in text format.', 
            yPosition
          );
        }
        
        // Add distribution data table as backup
        checkNewPage(30);
        yPosition = addWrappedText('Distribution Data:', yPosition, 12, 'bold');
        yPosition += 5;
        
        Object.entries(columnDistribution).forEach(([key, value]) => {
          checkNewPage(15);
          yPosition = addTableRow(key, value.toString(), yPosition);
        });
      }

      // Recommendations Section
      checkNewPage(40);
      yPosition = addSectionHeader('9. RECOMMENDATIONS', yPosition);
      
      const recommendations = [];
      if (datasetStats.missingValues > 0) {
        recommendations.push(`${datasetStats.missingValues} columns have 100% missing rate. Consider dropping them.`);
      }
      if (qualityMetrics.constantColumns > 0) {
        recommendations.push(`${qualityMetrics.constantColumns} constant columns found. Consider removing them.`);
      }
      if (consistencyMetrics.formattingIssues > 0) {
        recommendations.push(`${consistencyMetrics.formattingIssues} formatting issues detected. Review data consistency.`);
      }
      
      if (recommendations.length > 0) {
        recommendations.forEach((rec, index) => {
          checkNewPage(20);
          yPosition = addWrappedText(`${index + 1}. ${rec}`, yPosition, 10, 'normal');
          yPosition += 3;
        });
      } else {
        yPosition = addWrappedText('No major issues detected. Dataset appears to be in good condition.', yPosition, 10, 'normal');
      }

      // Final Summary Table
      checkNewPage(60);
      yPosition = addSectionHeader('10. EXECUTIVE SUMMARY', yPosition);
      
      // Create executive summary table
      const executiveSummaryData = [
        ['Aspect', 'Status', 'Summary'],
        ['Data Completeness', datasetStats.missingValues === 0 ? '✅ Excellent' : '⚠️ Needs Attention', 
         `${datasetStats.missingValues === 0 ? 'No missing values detected' : `${datasetStats.missingValues} columns with 100% missing rate`}`],
        ['Data Treatment', qualityScore >= 80 ? '✅ Good' : qualityScore >= 60 ? '⚠️ Fair' : '❌ Poor', 
         `Overall quality score: ${qualityScore}%`],
        ['Data Structure', (qualityMetrics.emptyColumns + qualityMetrics.constantColumns) === 0 ? '✅ Good' : '⚠️ Needs Review', 
         `${qualityMetrics.emptyColumns + qualityMetrics.constantColumns} structural issues detected`],
        ['Data Consistency', consistencyMetrics.formattingIssues === 0 ? '✅ Good' : '⚠️ Needs Review', 
         `${consistencyMetrics.formattingIssues} formatting inconsistencies found`],
        ['Target Variable', localDatasetConfig?.target_variable ? '✅ Configured' : '⚠️ Not Set', 
         localDatasetConfig?.target_variable || 'No target variable specified'],
        ['Variable Classification', variableClassification ? '✅ Available' : '⚠️ Not Available', 
         variableClassification ? `${variableClassification.classification?.variables?.length || 0} variables classified` : 'Variable classification not performed']
      ];

      // Add executive summary table header
      pdf.setFontSize(10);
      pdf.setFont('helvetica', 'bold');
      pdf.text('Aspect', margin, yPosition);
      pdf.text('Status', margin + 80, yPosition);
      pdf.text('Summary', margin + 160, yPosition);
      yPosition += 8;

      // Add executive summary table rows
      pdf.setFont('helvetica', 'normal');
      for (let i = 1; i < executiveSummaryData.length; i++) {
        checkNewPage(20);
        const row = executiveSummaryData[i];
        pdf.text(row[0], margin, yPosition);
        pdf.text(row[1], margin + 80, yPosition);
        pdf.text(row[2], margin + 160, yPosition);
        yPosition += 6;
      }
      yPosition += 10;

      // Footer
      pdf.addPage();
      yPosition = margin;
      yPosition = addSectionHeader('11. REPORT METADATA', yPosition);
      yPosition = addSubsection('Generated By', 'EXLdecision.ai Dataset Overview System', yPosition);
      yPosition = addSubsection('Report Type', 'Comprehensive Dataset Analysis', yPosition);
      yPosition = addSubsection('Data Source', `Dataset ID: ${datasetId}`, yPosition);
      yPosition = addSubsection('Generation Time', new Date().toLocaleString(), yPosition);

      // Save the PDF
      const filename = `dataset_summary_${datasetId}_${new Date().toISOString().split('T')[0]}.pdf`;
      pdf.save(filename);

      alert('PDF export completed successfully!');
    } catch (error) {
      console.error('Failed to export PDF:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
      alert(`Failed to export PDF: ${errorMessage}`);
    } finally {
      setIsLoadingPDFExport(false);
    }
  };

  // Modal states
  const [showRawDataModal, setShowRawDataModal] = useState(false);
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [showNoDictionaryModal, setShowNoDictionaryModal] = useState(false);
  const [showConfigSuccessModal, setShowConfigSuccessModal] = useState(false);
  const [rawData, setRawData] = useState<Record<string, any>[]>([]);
  const [isLoadingRawData, setIsLoadingRawData] = useState(false);
  const [isLoadingConfig, setIsLoadingConfig] = useState(false);
  const [isLoadingKnowledgeGraph, setIsLoadingKnowledgeGraph] = useState(false);
  const [isLoadingPDFExport, setIsLoadingPDFExport] = useState(false);
  const [dataDictionaryFile, setDataDictionaryFile] = useState<File | null>(null);
  const [knowledgeGraphData, setKnowledgeGraphData] = useState<KnowledgeGraphState | null>(null);
  const [knowledgeGraphCache, setKnowledgeGraphCache] = useState<
    Map<string, KnowledgeGraphState & { timestamp: number }>
  >(new Map());
  const sseCleanupRef = useRef<(() => void) | null>(null);
  const getKgCacheKey = (dataset: string) => `${dataset}::default`;

  const buildGraphState = (payload: KnowledgeGraphResultPayload): KnowledgeGraphState => {
    // Extract category distribution from nodes
    let variableCategoryDistribution: { categories: Record<string, number>; colors: Record<string, string> } | undefined;
    
    if (payload.nodes && payload.categories) {
      const categoryCounts: Record<string, number> = {};
      const categoryColors: Record<string, string> = {};
      
      // Build color map from categories
      payload.categories.forEach(cat => {
        categoryColors[cat.name] = cat.color;
        categoryCounts[cat.name] = 0; // Initialize all categories
      });
      
      // Count variables per category (exclude category nodes themselves)
      payload.nodes.forEach(node => {
        if (node.group && node.group !== 'category') {
          const categoryName = node.group;
          if (categoryCounts[categoryName] !== undefined) {
            categoryCounts[categoryName]++;
          } else {
            categoryCounts[categoryName] = 1;
          }
        }
      });
      
      variableCategoryDistribution = {
        categories: categoryCounts,
        colors: categoryColors
      };
      
      console.log('📊 Extracted variable category distribution:', variableCategoryDistribution);
      console.log(`   Total categories: ${Object.keys(categoryCounts).length}`);
      console.log(`   Total variables: ${Object.values(categoryCounts).reduce((a, b) => a + b, 0)}`);
    } else {
      console.warn('⚠️ No nodes or categories in payload:', {
        hasNodes: !!payload.nodes,
        nodesCount: payload.nodes?.length,
        hasCategories: !!payload.categories,
        categoriesCount: payload.categories?.length
      });
    }
    
    return {
      html_content: payload.html_content,
      algorithm_explanation: payload.algorithm_explanation || DEFAULT_ALGORITHM_EXPLANATION,
      relationship_mapping: payload.relationship_mapping || DEFAULT_RELATIONSHIP_MAPPING,
      usage_instructions: payload.usage_instructions || DEFAULT_USAGE_INSTRUCTIONS,
      processing_info: payload.processing_info,
      error: payload.error,
      variableCategoryDistribution,
    };
  };

  const cacheKnowledgeGraphResult = (dataset: string, graphState: KnowledgeGraphState) => {
    setKnowledgeGraphCache(prev => {
      const next = new Map(prev);
      next.set(getKgCacheKey(dataset), { ...graphState, timestamp: Date.now() });
      return next;
    });
  };

  const ensureRealtimeUpdates = (dataset: string, status?: string) => {
    const shouldStream = status !== 'complete';

    if (shouldStream && !sseCleanupRef.current) {
      startPollingForUpdates(dataset);
    } else if (!shouldStream && sseCleanupRef.current) {
      sseCleanupRef.current();
    }
  };

  const showKnowledgeGraphToUser = (dataset: string, graphState: KnowledgeGraphState) => {
    setKnowledgeGraphData(graphState);
    // Display inline in the Graph tab, no modal needed
    ensureRealtimeUpdates(dataset, graphState.processing_info?.status);
    
    // Store in sessionStorage for documentation feature
    sessionStorage.setItem('knowledge_graph_result', JSON.stringify(graphState));
  };

  const hydrateKnowledgeGraphFromBackend = async (
    dataset: string,
    options: { silent?: boolean } = {}
  ): Promise<'ready' | 'pending' | 'missing'> => {
    try {
      console.log('🔍 Hydrate: Polling backend for dataset:', dataset);
      const progress = await fastApiService.pollKnowledgeGraphProgress(dataset);
      console.log('🔍 Hydrate: Progress response:', {
        available: progress?.available,
        hasResult: !!progress?.result,
        hasHtml: !!progress?.result?.html_content,
        hasNodes: progress?.result?.nodes?.length,
        hasCategories: progress?.result?.categories?.length,
        message: progress?.message
      });

      if (progress?.available && progress.result?.html_content) {
        console.log('✅ Hydrate: Building graph state from result');
        const graphState = buildGraphState(progress.result);
        console.log('✅ Hydrate: Graph state built:', {
          hasVariableDist: !!graphState.variableCategoryDistribution,
          status: graphState.processing_info?.status
        });
        cacheKnowledgeGraphResult(dataset, graphState);

        if (!options.silent) {
          console.log('📺 Hydrate: Showing to user (not silent)');
          showKnowledgeGraphToUser(dataset, graphState);
        } else {
          console.log('🤫 Hydrate: Silent mode, not showing modal');
        }

        const completionStatus = graphState.processing_info?.status;
        return completionStatus === 'complete' ? 'ready' : 'pending';
      }

      // If not available but progress message indicates it's being generated
      if (progress?.message) {
        console.log('⏳ Hydrate: Pending - ', progress.message);
        return 'pending';
      }

      console.log('❌ Hydrate: Missing - no cached result');
      return 'missing';
    } catch (error) {
      console.info('⚠️ Hydrate: No backend knowledge graph cached yet', error);
      return 'missing';
    }
  };

  // Debug: Watch knowledgeGraphData changes
  useEffect(() => {
    console.log('🔍 knowledgeGraphData changed:', {
      hasData: !!knowledgeGraphData,
      hasVariableDist: !!knowledgeGraphData?.variableCategoryDistribution,
      categoryCount: knowledgeGraphData?.variableCategoryDistribution ? Object.keys(knowledgeGraphData.variableCategoryDistribution.categories).length : 0,
      status: knowledgeGraphData?.processing_info?.status,
      timestamp: new Date().toISOString()
    });
  }, [knowledgeGraphData]);

  useEffect(() => {
    if (!datasetId) {
      if (sseCleanupRef.current) {
        sseCleanupRef.current();
      }
      return;
    }

    let cancelled = false;

    const bootstrap = async () => {
      console.log('🔄 Bootstrap: Starting for dataset:', datasetId);
      
      // First, check for cached results
      const status = await hydrateKnowledgeGraphFromBackend(datasetId, { silent: true });
      console.log('🔄 Bootstrap: Hydration status:', status);
      
      // Populate knowledgeGraphData from cache if available
      const cached = knowledgeGraphCache.get(getKgCacheKey(datasetId));
      console.log('🔄 Bootstrap: Cache lookup result:', {
        hasCached: !!cached,
        hasVariableDist: !!cached?.variableCategoryDistribution,
        categoryCount: cached?.variableCategoryDistribution ? Object.keys(cached.variableCategoryDistribution.categories).length : 0,
        variableCount: cached?.variableCategoryDistribution ? Object.values(cached.variableCategoryDistribution.categories).reduce((a: number, b: number) => a + b, 0) : 0,
        status: cached?.processing_info?.status
      });
      
      if (cached) {
        const { timestamp: _timestamp, ...graphState } = cached;
        console.log('📊 Setting knowledgeGraphData from cache:', {
          hasHtml: !!graphState.html_content,
          hasVariableDist: !!graphState.variableCategoryDistribution,
          categoryCount: graphState.variableCategoryDistribution ? Object.keys(graphState.variableCategoryDistribution.categories).length : 0,
          status: graphState.processing_info?.status
        });
        setKnowledgeGraphData(graphState);
      } else {
        console.log('⚠️ No cached data available yet');
      }
      
      // Always establish SSE immediately if not already connected
      // This ensures we receive updates as soon as batch 1 is cached
      if (!cancelled && !sseCleanupRef.current) {
        // Check if we have a cached result to determine status
        const inferredStatus = cached?.processing_info?.status || 
                               (status === 'ready' ? 'complete' : 'partial');
        
        console.log('🔄 Bootstrap: Inferred status:', inferredStatus);
        
        // Only establish SSE if not complete (or if we don't know the status yet)
        if (inferredStatus !== 'complete') {
          console.log('📡 Bootstrap: Starting SSE for updates');
          ensureRealtimeUpdates(datasetId, inferredStatus);
        } else {
          console.log('✅ Bootstrap: Knowledge graph already complete, no SSE needed');
        }
      }
    };

    bootstrap();

    return () => {
      cancelled = true;
      if (sseCleanupRef.current) {
        sseCleanupRef.current();
      }
    };
  }, [datasetId]);

  const [configForm, setConfigForm] = useState<ConfigUpdateRequest>({
    target_variable: '',
    target_variable_type: 'Numerical',
    problem_statement: '',
    data_dictionary: ''
  });
  const [showBivariateAnalysis, setShowBivariateAnalysis] = useState(false);
  const [showCorrelationAnalysis, setShowCorrelationAnalysis] = useState(false);
  const [showIVAnalysis, setShowIVAnalysis] = useState(false);
  const [showVIFAnalysis, setShowVIFAnalysis] = useState(false);
  
  // Segment Profiling state
  const [showSegmentProfiling, setShowSegmentProfiling] = useState(true); // Start expanded
  const [segmentProfilingResult, setSegmentProfilingResult] = useState<any>(null);
  const [isRunningProfiling, setIsRunningProfiling] = useState(false);
  const [profilingProgress, setProfilingProgress] = useState(0);
  const [profilingStep, setProfilingStep] = useState(0);
  const [profilingMessage, setProfilingMessage] = useState('');
  const [showMulticollinearity, setShowMulticollinearity] = useState(false);
  const [showCorrelationRatioAnalysis, setShowCorrelationRatioAnalysis] = useState(false);

  const prevDisplayedInsightStepsRef = useRef<string[] | null>(null);

  // When new analyses appear in the right pane (e.g. Auto Insights or Standard Generate), expand those sections so charts are visible.
  useEffect(() => {
    if (currentStep !== 3) {
      prevDisplayedInsightStepsRef.current = selectedInsightSteps ? [...selectedInsightSteps] : [];
      return;
    }
    const cur = selectedInsightSteps || [];
    const prev = prevDisplayedInsightStepsRef.current;
    prevDisplayedInsightStepsRef.current = [...cur];

    // Auto Data Insights: always expand every selected panel on each Generate so child components mount
    // immediately and fetch/cache as REST steps complete (avoids "ticks done but pane empty" when step
    // list is unchanged and the previous run left sections collapsed).
    if (insightsGenerationSource === 'auto' && cur.length > 0) {
      if (cur.includes('bivariate_analysis')) setShowBivariateAnalysis(true);
      if (cur.includes('correlation_analysis')) setShowCorrelationAnalysis(true);
      if (cur.includes('correlation_matrix')) setShowMulticollinearity(true);
      if (cur.includes('iv_analysis')) setShowIVAnalysis(true);
      if (cur.includes('variance_inflation_factor')) setShowVIFAnalysis(true);
      if (cur.includes('correlation_ratio_analysis')) setShowCorrelationRatioAnalysis(true);
      return;
    }

    if (!prev) {
      if (cur.includes('bivariate_analysis')) setShowBivariateAnalysis(true);
      if (cur.includes('correlation_analysis')) setShowCorrelationAnalysis(true);
      if (cur.includes('correlation_matrix')) setShowMulticollinearity(true);
      if (cur.includes('iv_analysis')) setShowIVAnalysis(true);
      if (cur.includes('variance_inflation_factor')) setShowVIFAnalysis(true);
      if (cur.includes('correlation_ratio_analysis')) setShowCorrelationRatioAnalysis(true);
      return;
    }
    const added = cur.filter((s) => !prev.includes(s));
    if (added.includes('bivariate_analysis')) setShowBivariateAnalysis(true);
    if (added.includes('correlation_analysis')) setShowCorrelationAnalysis(true);
    if (added.includes('correlation_matrix')) setShowMulticollinearity(true);
    if (added.includes('iv_analysis')) setShowIVAnalysis(true);
    if (added.includes('variance_inflation_factor')) setShowVIFAnalysis(true);
    if (added.includes('correlation_ratio_analysis')) setShowCorrelationRatioAnalysis(true);
  }, [currentStep, selectedInsightSteps, insightsGenerationSource]);

  // Update config form when localDatasetConfig changes
  useEffect(() => {
    if (localDatasetConfig) {
      setConfigForm({
        target_variable: localDatasetConfig.target_variable || '',
        target_variable_type: localDatasetConfig.target_variable_type || 'Numerical',
        problem_statement: localDatasetConfig.problem_statement || '',
        data_dictionary: localDatasetConfig.data_dictionary || ''
      });
    }
  }, [localDatasetConfig]);

  // Update dataset stats when analysis data changes
  useEffect(() => {
    if (datasetAnalysis) {
      // Calculate columns with more than 95% missing values
      const columnsWithHighMissingValues = datasetAnalysis.columns.filter(col => {
        const missingPercentage = (col.missing_count / datasetAnalysis.totalRows) * 100;
        return missingPercentage > 95;
      });
      const highMissingColumnsCount = columnsWithHighMissingValues.length;
      
      const numericalCount = datasetAnalysis.columns.filter(col => getColumnLogicalType(col) === 'Numerical').length;
      const categoricalCount = datasetAnalysis.columns.filter(col => getColumnLogicalType(col) === 'Categorical').length;
      const dateCount = datasetAnalysis.columns.filter(col => getColumnLogicalType(col) === 'Date').length;
      
      // Calculate target distribution if target variable is set
      let targetDistribution: { [key: string]: number } = {};
      if (localDatasetConfig?.target_variable) {
        const targetColumn = datasetAnalysis.columns.find(col => col.name === localDatasetConfig.target_variable);
        if (targetColumn?.sample_values) {
          targetDistribution = targetColumn.sample_values;
        }
      }

      // Store duplicate rows count locally (to be calculated from backend in future)
      const duplicateRowsCount = 0;
      
      setDatasetStats({
        totalRecords: datasetAnalysis.totalRows,
        totalColumns: datasetAnalysis.totalColumns,
        missingValues: highMissingColumnsCount, // Now represents count of columns with >95% missing values
        duplicateRows: duplicateRowsCount,
        dataTypes: {
          numerical: numericalCount,
          categorical: categoricalCount,
        datetime: dateCount
        },
        targetDistribution
      });

      // Calculate comprehensive quality score based on multiple quality issues
      const qualityMetrics = getDataQualityMetrics();
      const consistencyMetrics = getConsistencyMetrics();
      
      // Count all quality issues (7 types as per new logic)
      const issues_count = (
        duplicateRowsCount +  // 1. Full row duplicates (using local variable, not stale state)
        consistencyMetrics.formattingIssues +  // 2. Formatting issues
        qualityMetrics.emptyColumns +  // 3. Empty columns (100% missing)
        qualityMetrics.constantColumns +  // 4. Constant columns (single value)
        qualityMetrics.sparseColumns +  // 5. Sparse columns (>50% missing)
        0 +  // 6. Data leakage risks (to be implemented if needed)
        0    // 7. Range issues (to be implemented if needed)
      );
      
      // Calculate max possible issues (columns * 2 as rough estimate)
      const max_possible_issues = datasetAnalysis.totalColumns * 2;
      
      // Quality score formula: 100 - (issues_count / max_possible_issues * 100)
      const calculatedQualityScore = Math.max(0, 100 - (issues_count / max_possible_issues * 100));
      setQualityScore(Math.round(calculatedQualityScore));
    }
  }, [datasetAnalysis, datasetConfig]);

  // Handle resize functionality
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing) return;
      
      const newWidth = window.innerWidth - e.clientX;
      // Constrain width between 250px and 800px (increased range)
      const constrainedWidth = Math.max(250, Math.min(800, newWidth));
      setSidebarWidth(constrainedWidth);
    };

    const handleMouseUp = () => {
      setIsResizing(false);
      setShowWidthIndicator(false);
    };

    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing]);

  // Notify parent component when width changes
  useEffect(() => {
    if (onWidthChange) {
      onWidthChange(collapsed ? 64 : sidebarWidth);
    }
  }, [sidebarWidth, collapsed, onWidthChange]);

  useEffect(() => {
    return () => {
      if (sseCleanupRef.current) {
        sseCleanupRef.current();
      }
    };
  }, []);
  
  useEffect(() => {
    if (!datasetId) {
      if (sseCleanupRef.current) {
        sseCleanupRef.current();
      }
      return;
    }
  
    const status = knowledgeGraphData?.processing_info?.status;
    if (status === 'partial' && !sseCleanupRef.current) {
      startPollingForUpdates(datasetId);
    } else if (status === 'complete' && sseCleanupRef.current) {
      sseCleanupRef.current();
    }
  }, [datasetId, knowledgeGraphData?.processing_info?.status]);

  const handleResizeStart = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
    setShowWidthIndicator(true);
  };

  const renderOverviewTab = () => (
    <div className="space-y-6">
      {/* Column Details - Grouped by Data Type */}
      {datasetAnalysis && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="font-medium text-gray-900 dark:text-gray-100">Column Details</h4>
          </div>

          {/* Scope Filter Dropdown */}
          <div className="flex items-center space-x-3 mb-4">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">View Data:</label>
            <select
              value={columnInfoScope}
              onChange={(e) => setColumnInfoScope(e.target.value as 'entire' | 'train' | 'test' | 'validation')}
              className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="entire">Full Data (Entire)</option>
              <option value="train">Train</option>
              <option value="test">Test</option>
              <option value="validation">Validation</option>
            </select>
            {columnInfo?.total_rows !== undefined && (
              <span className="text-xs text-gray-500 dark:text-gray-400">
                ({columnInfo.total_rows.toLocaleString()} rows)
              </span>
            )}
          </div>
          
          {isLoadingColumnInfo ? (
            <div className="p-3 text-sm text-gray-600 dark:text-gray-400">Loading column statistics...</div>
          ) : columnInfo && columnInfo.columns_info.length > 0 && (() => {
            // Helper function to get column type
            const getColType = (col: ColumnInfo): 'Numerical' | 'Categorical' | 'Date' => {
              return col.column_type || 
                (col.data_type && (col.data_type.toLowerCase().includes('date') || col.data_type.toLowerCase().includes('time')) ? 'Date' :
                ['int64', 'float64', 'int32', 'float32'].includes(col.data_type) ? 'Numerical' : 'Categorical') as 'Numerical' | 'Categorical' | 'Date';
            };
            
            // Reusable CSV download helper function
            const downloadTableAsCSV = (rows: Record<string, any>[], filename: string) => {
              if (rows.length === 0) return;
              const headers = Object.keys(rows[0]);
              const csv = [
                headers.join(','),
                ...rows.map((r) => headers.map((h) => {
                  const v = r[h];
                  if (v === null || v === undefined) return '';
                  const s = String(v).replace(/"/g, '""');
                  return `"${s}"`;
                }).join(','))
              ].join('\n');
              const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
              const link = document.createElement('a');
              const url = URL.createObjectURL(blob);
              link.href = url;
              link.download = filename;
              document.body.appendChild(link);
              link.click();
              document.body.removeChild(link);
              URL.revokeObjectURL(url);
            };
            
            // Group columns by type
            const numericalCols = columnInfo.columns_info.filter(col => getColType(col) === 'Numerical');
            const categoricalCols = columnInfo.columns_info.filter(col => getColType(col) === 'Categorical');
            const dateCols = columnInfo.columns_info.filter(col => getColType(col) === 'Date');
            
            const fmt = (v?: number | null) => (v === null || v === undefined ? '-' : v.toFixed(2));
            
            return (
              <div className="space-y-4">
                {/* Numerical Columns Table */}
                {numericalCols.length > 0 && (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <Hash className="h-4 w-4 text-blue-500" />
                        <h5 className="text-sm font-medium text-gray-800 dark:text-gray-200">
                          Numerical Variables ({numericalCols.length})
                        </h5>
                      </div>
                      <button
                        onClick={() => {
                          const rows = numericalCols.map((col) => {
                            const missingPct = col.total_count > 0 ? ((col.missing_count / col.total_count) * 100).toFixed(2) : '0.00';
                            return {
                              column_name: col.column_name,
                              total_obs: col.total_count,
                              missing_count: col.missing_count,
                              missing_pct: `${missingPct}%`,
                              distinct: col.unique_count,
                              min: col.min_value ?? '',
                              max: col.max_value ?? '',
                              mean: col.mean ?? '',
                              median: col.median ?? '',
                              mode: col.mode ?? '',
                              p1: col.percentile_1 ?? '',
                              p5: col.percentile_5 ?? '',
                              p25: col.percentile_25 ?? '',
                              p75: col.percentile_75 ?? '',
                              p95: col.percentile_95 ?? '',
                              p99: col.percentile_99 ?? '',
                              variance: col.variance ?? '',
                              std_dev: col.standard_deviation ?? '',
                              skewness: col.skewness ?? '',
                            };
                          });
                          downloadTableAsCSV(rows, `numerical_variables_${datasetId || 'dataset'}.csv`);
                        }}
                        className="inline-flex items-center space-x-1.5 px-2.5 py-1 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] text-xs font-medium rounded-md hover:bg-blue-700 dark:hover:bg-[#333380] transition-colors"
                        title="Download numerical variables as CSV"
                      >
                        <Download className="h-3 w-3" />
                        <span>Download CSV</span>
                      </button>
                    </div>
                    <div className="max-h-56 overflow-y-auto overflow-x-auto border border-blue-200 dark:border-blue-800 rounded-lg bg-white dark:bg-gray-800">
                      <table className="min-w-[1600px] w-full text-xs border-collapse">
                        <thead className="bg-blue-50 dark:bg-gray-800 sticky top-0 z-10">
                          <tr>
                            <th className="px-3 py-2 text-left font-semibold text-blue-700 dark:text-blue-300 border-b border-blue-200 dark:border-blue-800 whitespace-nowrap min-w-[120px]">Column</th>
                            <th className="px-3 py-2 text-right font-semibold text-blue-700 dark:text-blue-300 border-b border-blue-200 dark:border-blue-800 whitespace-nowrap min-w-[70px]">Total Obs</th>
                            <th className="px-3 py-2 text-right font-semibold text-blue-700 dark:text-blue-300 border-b border-blue-200 dark:border-blue-800 whitespace-nowrap min-w-[70px]">Missing #</th>
                            <th className="px-3 py-2 text-right font-semibold text-blue-700 dark:text-blue-300 border-b border-blue-200 dark:border-blue-800 whitespace-nowrap min-w-[70px]">Missing %</th>
                            <th className="px-3 py-2 text-right font-semibold text-blue-700 dark:text-blue-300 border-b border-blue-200 dark:border-blue-800 whitespace-nowrap min-w-[60px]">Distinct</th>
                            <th className="px-3 py-2 text-right font-semibold text-blue-700 dark:text-blue-300 border-b border-blue-200 dark:border-blue-800 whitespace-nowrap min-w-[70px]">Min</th>
                            <th className="px-3 py-2 text-right font-semibold text-blue-700 dark:text-blue-300 border-b border-blue-200 dark:border-blue-800 whitespace-nowrap min-w-[70px]">Max</th>
                            <th className="px-3 py-2 text-right font-semibold text-blue-700 dark:text-blue-300 border-b border-blue-200 dark:border-blue-800 whitespace-nowrap min-w-[70px]">Mean</th>
                            <th className="px-3 py-2 text-right font-semibold text-blue-700 dark:text-blue-300 border-b border-blue-200 dark:border-blue-800 whitespace-nowrap min-w-[70px]">Median</th>
                            <th className="px-3 py-2 text-right font-semibold text-blue-700 dark:text-blue-300 border-b border-blue-200 dark:border-blue-800 whitespace-nowrap min-w-[70px]">Mode</th>
                            <th className="px-3 py-2 text-right font-semibold text-blue-700 dark:text-blue-300 border-b border-blue-200 dark:border-blue-800 whitespace-nowrap min-w-[60px]">P1</th>
                            <th className="px-3 py-2 text-right font-semibold text-blue-700 dark:text-blue-300 border-b border-blue-200 dark:border-blue-800 whitespace-nowrap min-w-[60px]">P5</th>
                            <th className="px-3 py-2 text-right font-semibold text-blue-700 dark:text-blue-300 border-b border-blue-200 dark:border-blue-800 whitespace-nowrap min-w-[60px]">P25</th>
                            <th className="px-3 py-2 text-right font-semibold text-blue-700 dark:text-blue-300 border-b border-blue-200 dark:border-blue-800 whitespace-nowrap min-w-[60px]">P75</th>
                            <th className="px-3 py-2 text-right font-semibold text-blue-700 dark:text-blue-300 border-b border-blue-200 dark:border-blue-800 whitespace-nowrap min-w-[60px]">P95</th>
                            <th className="px-3 py-2 text-right font-semibold text-blue-700 dark:text-blue-300 border-b border-blue-200 dark:border-blue-800 whitespace-nowrap min-w-[60px]">P99</th>
                            <th className="px-3 py-2 text-right font-semibold text-blue-700 dark:text-blue-300 border-b border-blue-200 dark:border-blue-800 whitespace-nowrap min-w-[80px]">Variance</th>
                            <th className="px-3 py-2 text-right font-semibold text-blue-700 dark:text-blue-300 border-b border-blue-200 dark:border-blue-800 whitespace-nowrap min-w-[70px]">Std Dev</th>
                            <th className="px-3 py-2 text-right font-semibold text-blue-700 dark:text-blue-300 border-b border-blue-200 dark:border-blue-800 whitespace-nowrap min-w-[70px]">Skewness</th>
                          </tr>
                        </thead>
                        <tbody>
                          {numericalCols.map((col) => {
                            const missingPct = col.total_count > 0 ? ((col.missing_count / col.total_count) * 100).toFixed(2) : '0.00';
                            return (
                              <tr key={col.column_name} className="border-b border-blue-100 dark:border-blue-900 hover:bg-blue-50/50 dark:hover:bg-blue-900/20">
                                <td className="px-3 py-1.5 text-gray-900 dark:text-gray-100 font-medium max-w-[120px] truncate whitespace-nowrap" title={col.column_name}>{col.column_name}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.total_count.toLocaleString()}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.missing_count.toLocaleString()}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{missingPct}%</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.unique_count.toLocaleString()}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.min_value)}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.max_value)}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.mean)}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.median)}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.mode !== null && col.mode !== undefined ? fmt(Number(col.mode)) : '-'}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.percentile_1)}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.percentile_5)}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.percentile_25)}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.percentile_75)}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.percentile_95)}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.percentile_99)}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.variance)}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.standard_deviation)}</td>
                                <td className="px-2 py-1.5 text-right text-gray-700 dark:text-gray-300">{fmt(col.skewness)}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
                
                {/* Categorical Columns Table */}
                {categoricalCols.length > 0 && (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <Activity className="h-4 w-4 text-green-500" />
                        <h5 className="text-sm font-medium text-gray-800 dark:text-gray-200">
                          Categorical Variables ({categoricalCols.length})
                        </h5>
                      </div>
                      <button
                        onClick={() => {
                          const rows = categoricalCols.map((col) => {
                            const missingPct = col.total_count > 0 ? ((col.missing_count / col.total_count) * 100).toFixed(2) : '0.00';
                            return {
                              column_name: col.column_name,
                              total_obs: col.total_count,
                              missing_count: col.missing_count,
                              missing_pct: `${missingPct}%`,
                              distinct: col.unique_count,
                              mode: col.mode ?? '',
                              top_category_pct: col.top_category_pct !== null && col.top_category_pct !== undefined ? `${col.top_category_pct.toFixed(1)}%` : '',
                              lowest_category_pct: col.lowest_category_pct !== null && col.lowest_category_pct !== undefined ? `${col.lowest_category_pct.toFixed(1)}%` : '',
                            };
                          });
                          downloadTableAsCSV(rows, `categorical_variables_${datasetId || 'dataset'}.csv`);
                        }}
                        className="inline-flex items-center space-x-1.5 px-2.5 py-1 bg-green-600 dark:bg-[#296629] text-white dark:text-[#ccffcc] text-xs font-medium rounded-md hover:bg-green-700 dark:hover:bg-[#338033] transition-colors"
                        title="Download categorical variables as CSV"
                      >
                        <Download className="h-3 w-3" />
                        <span>Download CSV</span>
                      </button>
                    </div>
                    <div className="max-h-56 overflow-y-auto overflow-x-auto border border-green-200 dark:border-green-800 rounded-lg bg-white dark:bg-gray-800">
                      <table className="min-w-[800px] w-full text-xs border-collapse">
                        <thead className="bg-green-50 dark:bg-gray-800 sticky top-0 z-10">
                          <tr>
                            <th className="px-3 py-2 text-left font-semibold text-green-700 dark:text-green-300 border-b border-green-200 dark:border-green-800 whitespace-nowrap min-w-[140px]">Column</th>
                            <th className="px-3 py-2 text-right font-semibold text-green-700 dark:text-green-300 border-b border-green-200 dark:border-green-800 whitespace-nowrap min-w-[80px]">Total Obs</th>
                            <th className="px-3 py-2 text-right font-semibold text-green-700 dark:text-green-300 border-b border-green-200 dark:border-green-800 whitespace-nowrap min-w-[80px]">Missing #</th>
                            <th className="px-3 py-2 text-right font-semibold text-green-700 dark:text-green-300 border-b border-green-200 dark:border-green-800 whitespace-nowrap min-w-[80px]">Missing %</th>
                            <th className="px-3 py-2 text-right font-semibold text-green-700 dark:text-green-300 border-b border-green-200 dark:border-green-800 whitespace-nowrap min-w-[70px]">Distinct</th>
                            <th className="px-3 py-2 text-left font-semibold text-green-700 dark:text-green-300 border-b border-green-200 dark:border-green-800 whitespace-nowrap min-w-[100px]">Mode</th>
                            <th className="px-3 py-2 text-right font-semibold text-green-700 dark:text-green-300 border-b border-green-200 dark:border-green-800 whitespace-nowrap min-w-[100px]">Top Category %</th>
                            <th className="px-3 py-2 text-right font-semibold text-green-700 dark:text-green-300 border-b border-green-200 dark:border-green-800 whitespace-nowrap min-w-[110px]">Lowest Category %</th>
                          </tr>
                        </thead>
                        <tbody>
                          {categoricalCols.map((col) => {
                            const missingPct = col.total_count > 0 ? ((col.missing_count / col.total_count) * 100).toFixed(2) : '0.00';
                            return (
                              <tr key={col.column_name} className="border-b border-green-100 dark:border-green-900 hover:bg-green-50/50 dark:hover:bg-green-900/20">
                                <td className="px-3 py-1.5 text-gray-900 dark:text-gray-100 font-medium max-w-[150px] truncate whitespace-nowrap" title={col.column_name}>{col.column_name}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.total_count.toLocaleString()}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.missing_count.toLocaleString()}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{missingPct}%</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.unique_count.toLocaleString()}</td>
                                <td className="px-3 py-1.5 text-gray-700 dark:text-gray-300 max-w-[120px] truncate whitespace-nowrap" title={col.mode !== null && col.mode !== undefined ? String(col.mode) : ''}>
                                  {col.mode !== null && col.mode !== undefined ? String(col.mode) : '-'}
                                </td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">
                                  {col.top_category_pct !== null && col.top_category_pct !== undefined ? `${col.top_category_pct.toFixed(1)}%` : '-'}
                                </td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">
                                  {col.lowest_category_pct !== null && col.lowest_category_pct !== undefined ? `${col.lowest_category_pct.toFixed(1)}%` : '-'}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
                
                {/* DateTime Columns Table */}
                {dateCols.length > 0 && (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <Calendar className="h-4 w-4 text-purple-500" />
                        <h5 className="text-sm font-medium text-gray-800 dark:text-gray-200">
                          DateTime Variables ({dateCols.length})
                        </h5>
                      </div>
                      <button
                        onClick={() => {
                          const rows = dateCols.map((col) => {
                            const nonNullCount = col.total_count - col.missing_count;
                            const missingPct = col.total_count > 0 ? ((col.missing_count / col.total_count) * 100).toFixed(2) : '0.00';
                            return {
                              column_name: col.column_name,
                              non_null: nonNullCount,
                              missing_pct: `${missingPct}%`,
                              min: col.date_min ?? '',
                              max: col.date_max ?? '',
                              distinct: col.unique_count,
                              most_frequent: col.most_frequent_date ?? col.mode ?? '',
                            };
                          });
                          downloadTableAsCSV(rows, `datetime_variables_${datasetId || 'dataset'}.csv`);
                        }}
                        className="inline-flex items-center space-x-1.5 px-2.5 py-1 bg-purple-600 dark:bg-[#462966] text-white dark:text-[#e6ccff] text-xs font-medium rounded-md hover:bg-purple-700 dark:hover:bg-[#593380] transition-colors"
                        title="Download datetime variables as CSV"
                      >
                        <Download className="h-3 w-3" />
                        <span>Download CSV</span>
                      </button>
                    </div>
                    <div className="max-h-48 overflow-y-auto overflow-x-auto border border-purple-200 dark:border-purple-800 rounded-lg bg-white dark:bg-gray-800">
                      <table className="min-w-[700px] w-full text-xs border-collapse">
                        <thead className="bg-purple-50 dark:bg-gray-800 sticky top-0 z-10">
                          <tr>
                            <th className="px-3 py-2 text-left font-semibold text-purple-700 dark:text-purple-300 border-b border-purple-200 dark:border-purple-800 whitespace-nowrap min-w-[140px]">Column</th>
                            <th className="px-3 py-2 text-right font-semibold text-purple-700 dark:text-purple-300 border-b border-purple-200 dark:border-purple-800 whitespace-nowrap min-w-[80px]">Non-null</th>
                            <th className="px-3 py-2 text-right font-semibold text-purple-700 dark:text-purple-300 border-b border-purple-200 dark:border-purple-800 whitespace-nowrap min-w-[80px]">Missing %</th>
                            <th className="px-3 py-2 text-right font-semibold text-purple-700 dark:text-purple-300 border-b border-purple-200 dark:border-purple-800 whitespace-nowrap min-w-[80px]">Min</th>
                            <th className="px-3 py-2 text-right font-semibold text-purple-700 dark:text-purple-300 border-b border-purple-200 dark:border-purple-800 whitespace-nowrap min-w-[80px]">Max</th>
                            <th className="px-3 py-2 text-right font-semibold text-purple-700 dark:text-purple-300 border-b border-purple-200 dark:border-purple-800 whitespace-nowrap min-w-[70px]">Distinct</th>
                            <th className="px-3 py-2 text-right font-semibold text-purple-700 dark:text-purple-300 border-b border-purple-200 dark:border-purple-800 whitespace-nowrap min-w-[100px]">Most Frequent</th>
                          </tr>
                        </thead>
                        <tbody>
                          {dateCols.map((col) => {
                            const nonNullCount = col.total_count - col.missing_count;
                            const missingPct = col.total_count > 0 ? ((col.missing_count / col.total_count) * 100).toFixed(2) : '0.00';
                            return (
                              <tr key={col.column_name} className="border-b border-purple-100 dark:border-purple-900 hover:bg-purple-50/50 dark:hover:bg-purple-900/20">
                                <td className="px-3 py-1.5 text-gray-900 dark:text-gray-100 font-medium whitespace-nowrap">{col.column_name}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{nonNullCount.toLocaleString()}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{missingPct}%</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.date_min ?? '-'}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.date_max ?? '-'}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.unique_count.toLocaleString()}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.most_frequent_date ?? col.mode ?? '-'}</td>
                              </tr>
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


      {/* Variable Categories Pie Chart */}
      {(() => {
        const debugInfo = {
          hasKnowledgeGraphData: !!knowledgeGraphData,
          knowledgeGraphDataKeys: knowledgeGraphData ? Object.keys(knowledgeGraphData) : [],
          hasVariableCategoryDistribution: !!knowledgeGraphData?.variableCategoryDistribution,
          variableDistKeys: knowledgeGraphData?.variableCategoryDistribution ? Object.keys(knowledgeGraphData.variableCategoryDistribution) : [],
          categoryCount: knowledgeGraphData?.variableCategoryDistribution ? Object.keys(knowledgeGraphData.variableCategoryDistribution.categories || {}).length : 0,
          categories: knowledgeGraphData?.variableCategoryDistribution?.categories,
          status: knowledgeGraphData?.processing_info?.status,
          willRender: !!knowledgeGraphData?.variableCategoryDistribution,
          timestamp: new Date().toISOString()
        };
        console.log('🥧 Pie Chart Condition Check:', debugInfo);
        
        // Log every render to catch when it stops rendering
        if (knowledgeGraphData && !knowledgeGraphData.variableCategoryDistribution) {
          console.warn('⚠️ knowledgeGraphData exists but variableCategoryDistribution is missing!', {
            graphDataKeys: Object.keys(knowledgeGraphData),
            status: knowledgeGraphData.processing_info?.status
          });
        }
        
        return null;
      })()}
      {knowledgeGraphData?.variableCategoryDistribution && (
        <div className="space-y-3">
          <h4 className="font-medium text-gray-900 flex items-center space-x-2">
            <BarChart3 className="h-4 w-4" />
            <span>Variable Categories</span>
            {knowledgeGraphData.processing_info?.status === 'partial' && (
              <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                <Loader className="h-3 w-3 mr-1 animate-spin" />
                Processing... {knowledgeGraphData.processing_info.completed_batches}/{knowledgeGraphData.processing_info.total_batches}
              </span>
            )}
            {knowledgeGraphData.processing_info?.status === 'complete' && (
              <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                <CheckCircle className="h-3 w-3 mr-1" />
                Complete
              </span>
            )}
          </h4>
          
          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
            {isLoadingKnowledgeGraph ? (
              <div className="h-96 flex items-center justify-center">
                <div className="text-center">
                  <Loader className="h-8 w-8 text-blue-500 animate-spin mx-auto mb-2" />
                  <p className="text-sm text-gray-600 dark:text-gray-400">Generating feature graph...</p>
                </div>
              </div>
            ) : (
              <>
                <div className="h-96 mb-4" data-testid="variable-classification-pie-chart">
                  <Pie
                    key={theme}
                    data={{
                      labels: Object.keys(knowledgeGraphData.variableCategoryDistribution.categories),
                      datasets: [
                        {
                          data: Object.values(knowledgeGraphData.variableCategoryDistribution.categories),
                          backgroundColor: Object.keys(knowledgeGraphData.variableCategoryDistribution.categories).map(
                            category => {
                              const color = knowledgeGraphData.variableCategoryDistribution?.colors[category] || '#94a3b8';
                              // Convert hex to rgba with opacity
                              const r = parseInt(color.slice(1, 3), 16);
                              const g = parseInt(color.slice(3, 5), 16);
                              const b = parseInt(color.slice(5, 7), 16);
                              return `rgba(${r}, ${g}, ${b}, 0.8)`;
                            }
                          ),
                          borderColor: Object.keys(knowledgeGraphData.variableCategoryDistribution.categories).map(
                            category => knowledgeGraphData.variableCategoryDistribution?.colors[category] || '#64748b'
                          ),
                          borderWidth: 2,
                        },
                      ],
                    }}
                    options={{
                      color: chartJsDefaultFontColor(isDark),
                      responsive: true,
                      maintainAspectRatio: false,
                      plugins: {
                        title: {
                          display: true,
                          text: 'Variable Categories Distribution',
                          font: {
                            size: 14,
                            weight: 'bold',
                          },
                          color: isDark ? '#e5e7eb' : '#374151',
                          padding: {
                            bottom: 20,
                          },
                        },
                        legend: {
                          position: 'bottom',
                          labels: {
                            padding: 15,
                            font: {
                              size: 11,
                            },
                            color: isDark ? '#d1d5db' : '#6B7280',
                          },
                        },
                        tooltip: {
                          ...chartJsTooltipColors(isDark),
                          callbacks: {
                            label: (context) => {
                              const total = Object.values(knowledgeGraphData.variableCategoryDistribution?.categories || {}).reduce((a, b) => a + b, 0);
                              const count = context.parsed;
                              const percentage = ((count / total) * 100).toFixed(1);
                              return `${context.label}: ${count} variables (${percentage}%)`;
                            },
                          },
                        },
                      },
                    }}
                  />
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Last Updated */}
      <div className="flex items-center space-x-2 text-sm text-gray-500 dark:text-gray-400">
        <Calendar className="h-4 w-4" />
        <span>Last updated: {lastUpdated.toLocaleDateString()}</span>
      </div>
    </div>
  );

  const renderQualityTab = () => {
    // Helper function for score status
    const getScoreStatus = (score: number) => {
      if (score >= 90) return { label: 'Excellent', color: 'text-green-600', bgColor: 'bg-green-500' };
      if (score >= 70) return { label: 'Good', color: 'text-yellow-600', bgColor: 'bg-yellow-500' };
      if (score >= 50) return { label: 'Fair', color: 'text-orange-600', bgColor: 'bg-orange-500' };
      return { label: 'Poor', color: 'text-red-600', bgColor: 'bg-red-500' };
    };

    // Loading state
    if (isLoadingDqs) {
      return (
        <div className="flex items-center justify-center p-8">
          <div className="flex flex-col items-center space-y-3">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
            <p className="text-sm text-gray-500 dark:text-gray-400">Calculating Data Quality Score...</p>
          </div>
        </div>
      );
    }

    // Check if error is "no data for scope" - show warning with dropdown instead of blocking error
    const isNoDataForScopeError = dqsError && dqsError.toLowerCase().includes('no data available for scope');

    // Error state (only for non-scope-related errors)
    if (dqsError && !isNoDataForScopeError) {
      return (
        <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="h-5 w-5 text-red-500" />
            <p className="text-sm text-red-700 dark:text-red-300">Failed to calculate DQS: {dqsError}</p>
          </div>
        </div>
      );
    }

    // No data state (no dataset loaded at all)
    if (!dqsData && !isNoDataForScopeError) {
      return (
        <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg text-center">
          <p className="text-sm text-gray-500 dark:text-gray-400">No dataset loaded. Upload a dataset to see quality metrics.</p>
        </div>
      );
    }

    // Show dropdown with warning when scope has no data
    if (isNoDataForScopeError) {
      return (
        <div className="space-y-5">
          {/* Scope Filter Dropdown - always accessible */}
          <div className="flex items-center space-x-3 mb-4">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">View Data:</label>
            <select
              value={dqsScope}
              onChange={(e) => setDqsScope(e.target.value as 'entire' | 'train' | 'test' | 'validation')}
              className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="entire">Full Data (Entire)</option>
              <option value="train">Train</option>
              <option value="test">Test</option>
              <option value="validation">Validation</option>
            </select>
          </div>

          {/* Warning message for no data in selected scope */}
          <div className="p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg">
            <div className="flex items-center space-x-2">
              <AlertTriangle className="h-5 w-5 text-yellow-500" />
              <p className="text-sm text-yellow-700 dark:text-yellow-300">
                No data available for "{dqsScope}" partition. Please select a different data scope.
              </p>
            </div>
          </div>
        </div>
      );
    }

    // Extract data from backend response
    const { 
      composite_score: dqsScore, 
      score_label: dqsLabel,
      completeness, 
      consistency, 
      structural_integrity: structural, 
      uniqueness,
      target_readiness: targetReadiness
    } = dqsData;

    const dqsStatus = getScoreStatus(dqsScore);

    return (
      <div className="space-y-5">
        {/* Scope Filter Dropdown */}
        <div className="flex items-center space-x-3 mb-4">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">View Data:</label>
          <select
            value={dqsScope}
            onChange={(e) => setDqsScope(e.target.value as 'entire' | 'train' | 'test' | 'validation')}
            className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="entire">Full Data (Entire)</option>
            <option value="train">Train</option>
            <option value="test">Test</option>
            <option value="validation">Validation</option>
          </select>
          {dqsData?.total_rows !== undefined && (
            <span className="text-xs text-gray-500 dark:text-gray-400">
              ({dqsData.total_rows.toLocaleString()} rows)
            </span>
          )}
        </div>

        {/* DQS Composite Score */}
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/30 dark:to-indigo-900/30 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="font-semibold text-gray-900 dark:text-gray-100">Data Quality Score</h4>
              <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                Composite assessment of data readiness
              </p>
            </div>
            <div className="text-right">
              <div className={`text-3xl font-bold ${dqsStatus.color}`}>{dqsScore}</div>
              <div className="flex items-center justify-end space-x-1 mt-1">
                {dqsScore >= 70 ? (
                  <CheckCircle className={`h-4 w-4 ${dqsStatus.color}`} />
                ) : (
                  <AlertTriangle className={`h-4 w-4 ${dqsStatus.color}`} />
                )}
                <span className={`text-sm font-medium ${dqsStatus.color}`}>{dqsLabel}</span>
              </div>
            </div>
          </div>
          
          {/* Score Breakdown Bar */}
          <div className="mt-4">
            <div className="flex h-2 rounded-full overflow-hidden bg-gray-200 dark:bg-gray-700">
              <div 
                className="bg-blue-500 transition-all duration-500" 
                style={{ width: `${completeness.weighted_contribution}%` }}
                title={`Completeness: ${completeness.score}%`}
              />
              <div 
                className="bg-purple-500 transition-all duration-500" 
                style={{ width: `${consistency.weighted_contribution}%` }}
                title={`Consistency: ${consistency.score}%`}
              />
              <div 
                className="bg-teal-500 transition-all duration-500" 
                style={{ width: `${structural.weighted_contribution}%` }}
                title={`Structural: ${structural.score}%`}
              />
              <div 
                className="bg-orange-500 transition-all duration-500" 
                style={{ width: `${uniqueness.weighted_contribution}%` }}
                title={`Uniqueness: ${uniqueness.score}%`}
              />
            </div>
            <div className="flex justify-between mt-1 text-xs text-gray-500 dark:text-gray-400">
              <span>0</span>
              <span>100</span>
            </div>
          </div>
        </div>

        {/* Dimension Scores */}
        <div className="space-y-3">
          <h4 className="font-medium text-gray-900 dark:text-gray-100 text-sm">Score Breakdown</h4>
          
          {/* Completeness */}
          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-3">
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 rounded-full bg-blue-500"></div>
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Completeness</span>
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-5 space-y-0.5">
              {completeness.details.columns_with_high_missing > 0 && (
                <p>Columns with high missing (&gt;50%): {completeness.details.columns_with_high_missing}</p>
              )}
              {completeness.details.row_sparseness_penalty > 0 && (
                <p>Row sparseness penalty: -{completeness.details.row_sparseness_penalty} points</p>
              )}
              {completeness.details.sparse_row_percentage > 0 && (
                <p>Sparse rows (&gt;50% missing): {completeness.details.sparse_row_percentage.toFixed(1)}%</p>
              )}
              {completeness.details.columns_with_high_missing === 0 && completeness.details.row_sparseness_penalty === 0 && completeness.details.sparse_row_percentage === 0 && (
                <p className="text-green-600 dark:text-green-400">No completeness issues detected</p>
              )}
            </div>
          </div>
          
          {/* Consistency */}
          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-3">
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 rounded-full bg-purple-500"></div>
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Consistency</span>
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-5 space-y-0.5">
              {consistency.details.formatting_issues > 0 && (
                <p>Format issues: {consistency.details.formatting_issues} columns</p>
              )}
              {consistency.details.placeholder_count > 0 && (
                <p>Placeholder values: {consistency.details.placeholder_count} columns</p>
              )}
              {consistency.details.invalid_range_count > 0 && (
                <p>Invalid ranges: {consistency.details.invalid_range_count} columns</p>
              )}
              {consistency.details.formatting_issues === 0 && consistency.details.placeholder_count === 0 && consistency.details.invalid_range_count === 0 && (
                <p className="text-green-600 dark:text-green-400">No consistency issues detected</p>
              )}
            </div>
          </div>
          
          {/* Structural Integrity */}
          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-3">
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 rounded-full bg-teal-500"></div>
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Structural Integrity</span>
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-5 space-y-0.5">
              {structural.details.constant_columns > 0 && (
                <p>Constant columns: {structural.details.constant_columns}</p>
              )}
              {structural.details.near_constant_columns > 0 && (
                <p>Near-constant columns: {structural.details.near_constant_columns}</p>
              )}
              {structural.details.duplicate_columns > 0 && (
                <p>Duplicate columns: {structural.details.duplicate_columns}</p>
              )}
              {structural.details.constant_columns === 0 && structural.details.near_constant_columns === 0 && structural.details.duplicate_columns === 0 && (
                <p className="text-green-600 dark:text-green-400">No structural issues detected</p>
              )}
            </div>
          </div>
          
          {/* Uniqueness */}
          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-3">
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 rounded-full bg-orange-500"></div>
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Uniqueness</span>
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-5 space-y-0.5">
              {uniqueness.details.duplicate_row_count > 0 ? (
                <p>Duplicate rows: {uniqueness.details.duplicate_row_count.toLocaleString()} ({uniqueness.details.duplicate_row_percentage.toFixed(1)}%)</p>
              ) : (
                <p className="text-green-600 dark:text-green-400">No duplicate rows detected</p>
              )}
            </div>
          </div>
        </div>

        {/* Target Readiness (Informational Panel) */}
        {targetReadiness && targetReadiness.target_variable && (
          <div className="bg-gray-50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
            <div className="flex items-center space-x-2 mb-3">
              <Target className="h-4 w-4 text-indigo-500" />
              <h4 className="font-medium text-gray-900 dark:text-gray-100 text-sm">Target Readiness</h4>
              <span className="text-xs px-2 py-0.5 bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400 rounded">Informational</span>
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600 dark:text-gray-400">Target Variable</span>
                <span className="text-sm font-medium text-gray-900 dark:text-gray-100">{targetReadiness.target_variable}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600 dark:text-gray-400">Missing Rate</span>
                <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                  {targetReadiness.target_missing_rate !== null && targetReadiness.target_missing_rate !== undefined 
                    ? `${targetReadiness.target_missing_rate.toFixed(2)}%` 
                    : 'N/A'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600 dark:text-gray-400">Event Rate (Class Balance)</span>
                <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                  {targetReadiness.event_rate !== null && targetReadiness.event_rate !== undefined 
                    ? `${targetReadiness.event_rate.toFixed(2)}%` 
                    : 'N/A'}
                </span>
              </div>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-2 italic">
              Class imbalance is a data characteristic, not a defect. Interpret in context.
            </p>
          </div>
        )}

        {/* AI Recommendations Section */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h4 className="font-medium text-gray-900 dark:text-gray-100 flex items-center space-x-2">
              <Brain className="h-4 w-4 text-purple-500" />
              <span>AI Recommendations</span>
            </h4>
            {isLoadingDqsRecommendations && (
              <Loader className="h-4 w-4 text-purple-500 animate-spin" />
            )}
          </div>
          
          {isLoadingDqsRecommendations ? (
            <div className="flex items-center justify-center py-6">
              <div className="text-center">
                <Loader className="h-6 w-6 text-purple-500 animate-spin mx-auto mb-2" />
                <p className="text-xs text-gray-500 dark:text-gray-400">Generating AI recommendations...</p>
              </div>
            </div>
          ) : dqsRecommendations.length > 0 ? (
            <div className="space-y-2">
              {/* Show recommendations sorted by priority */}
              {(showAllDqsRecommendations 
                ? dqsRecommendations 
                : dqsRecommendations.slice(0, 3)
              ).sort((a, b) => {
                const priorityOrder = { high: 0, medium: 1, low: 2 };
                return priorityOrder[a.priority] - priorityOrder[b.priority];
              }).map((rec, index) => (
                <div 
                  key={index} 
                  className={`p-3 rounded-lg border ${
                    rec.type === 'warning' 
                      ? 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800' 
                      : rec.type === 'success' 
                        ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'
                        : 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800'
                  }`}
                >
                  <div className="flex items-start space-x-2">
                    {rec.type === 'warning' ? (
                      <AlertTriangle className="h-4 w-4 text-amber-500 mt-0.5 flex-shrink-0" />
                    ) : rec.type === 'success' ? (
                      <CheckCircle className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
                    ) : (
                      <Info className="h-4 w-4 text-blue-500 mt-0.5 flex-shrink-0" />
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center space-x-2">
                        <p className={`text-xs font-medium ${
                          rec.type === 'warning' 
                            ? 'text-amber-800 dark:text-amber-300' 
                            : rec.type === 'success' 
                              ? 'text-green-800 dark:text-green-300'
                              : 'text-blue-800 dark:text-blue-300'
                        }`}>
                          {rec.title}
                        </p>
                        <span className={`px-1.5 py-0.5 text-[10px] font-medium rounded ${
                          rec.priority === 'high'
                            ? 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300'
                            : rec.priority === 'medium'
                              ? 'bg-yellow-100 dark:bg-yellow-900/40 text-yellow-700 dark:text-yellow-300'
                              : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
                        }`}>
                          {rec.priority}
                        </span>
                      </div>
                      <p className={`text-xs mt-1 ${
                        rec.type === 'warning' 
                          ? 'text-amber-700 dark:text-amber-400' 
                          : rec.type === 'success' 
                            ? 'text-green-700 dark:text-green-400'
                            : 'text-blue-700 dark:text-blue-400'
                      }`}>
                        {rec.description}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
              
              {/* View All / View Less button */}
              {dqsRecommendations.length > 3 && (
                <button
                  onClick={() => setShowAllDqsRecommendations(!showAllDqsRecommendations)}
                  className="w-full mt-2 py-2 px-3 text-xs font-medium text-purple-600 dark:text-purple-400 bg-purple-50 dark:bg-purple-900/20 hover:bg-purple-100 dark:hover:bg-purple-900/30 rounded-lg border border-purple-200 dark:border-purple-800 transition-colors flex items-center justify-center space-x-1"
                >
                  {showAllDqsRecommendations ? (
                    <>
                      <ChevronUp className="h-3 w-3" />
                      <span>Show Less</span>
                    </>
                  ) : (
                    <>
                      <ChevronDown className="h-3 w-3" />
                      <span>View All {dqsRecommendations.length} Recommendations</span>
                    </>
                  )}
                </button>
              )}
            </div>
          ) : (
            <div className="text-center py-4">
              <p className="text-xs text-gray-500 dark:text-gray-400">
                No recommendations available. AI recommendations will appear once DQS is calculated.
              </p>
            </div>
          )}
        </div>

      </div>
    );
  };

  const renderInsightsTab = () => {
    // For Step 3, show only selected standard analyses; nothing initially
    if (currentStep === 3) {
      return (
        <div className="space-y-6">
          {/* IV Analysis Section */}
          {/* {localDatasetConfig?.target_variable && selectedInsightSteps?.includes('iv_analysis') && (
            <div className="space-y-4">
              
              <button
                onClick={() => setShowIVAnalysis(!showIVAnalysis)}
                className="w-full flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg border border-gray-200 dark:border-gray-700 transition-all duration-200 group"
              >
                <div className="flex items-center space-x-2">
                  <Tag className="h-5 w-5 text-indigo-600" />
                  <span className="font-medium text-gray-900 dark:text-gray-100">IV Analysis</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="text-sm text-gray-500">
                    {showIVAnalysis ? 'Hide Analysis' : 'Show Analysis'}
                  </span>
                  {showIVAnalysis ? (
                    <ChevronUp className="h-4 w-4 text-gray-500 transition-transform duration-200" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-gray-500 transition-transform duration-200" />
                  )}
                </div>
              </button>

              
              {showIVAnalysis && (
                <div className="mt-4 animate-in slide-in-from-top-2 duration-200">
                  <IVAnalysisComponent
                    datasetId={datasetId || null}
                    targetVariable={localDatasetConfig.target_variable || ''}
                    currentStep={currentStep}
                  />
                </div>
              )}
            </div>
          )} */}

          {/* Bivariate Analysis Section */}
          {localDatasetConfig?.target_variable && selectedInsightSteps?.includes('bivariate_analysis') ? (
            <div className="space-y-4">
              {/* Collapsible Header */}
              <button
                onClick={() => setShowBivariateAnalysis(!showBivariateAnalysis)}
                className="w-full flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg border border-gray-200 dark:border-gray-700 transition-all duration-200 group"
              >
                <div className="flex items-center space-x-2">
                  <BarChart3 className="h-5 w-5 text-blue-600" />
                  <span className="font-medium text-gray-900 dark:text-gray-100">Bivariate Analysis</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="text-sm text-gray-500 dark:text-gray-400">
                    {showBivariateAnalysis ? 'Hide Analysis' : 'Show Analysis'}
                  </span>
                  {showBivariateAnalysis ? (
                    <ChevronUp className="h-4 w-4 text-gray-500 dark:text-gray-400 transition-transform duration-200" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-gray-500 dark:text-gray-400 transition-transform duration-200" />
                  )}
                </div>
              </button>
              
              {/* Collapsible Content */}
              {showBivariateAnalysis && (
                <div
                  data-insight-report-root="bivariate_analysis"
                  className="mt-4 animate-in slide-in-from-top-2 duration-200 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 overflow-hidden p-4 sm:p-5"
                >
                  <BivariateAnalysisComponent
                    datasetId={datasetId || null}
                    targetVariable={localDatasetConfig.target_variable || ''}
                    currentStep={currentStep}
                    allowBinningCustomization={insightsGenerationSource === 'standard'}
                  />
                </div>
              )}
            </div>
          ) : null}

          {/* Correlation Analysis Section */}
          {localDatasetConfig?.target_variable && selectedInsightSteps?.includes('correlation_analysis') && (
            <div className="space-y-4">
              {/* Collapsible Header */}
              <button
                onClick={() => setShowCorrelationAnalysis(!showCorrelationAnalysis)}
                className="w-full flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg border border-gray-200 dark:border-gray-700 transition-all duration-200 group"
              >
                <div className="flex items-center space-x-2">
                  <TrendingUp className="h-5 w-5 text-green-600" />
                  <span className="font-medium text-gray-900 dark:text-gray-100">Correlation Analysis</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="text-sm text-gray-500 dark:text-gray-400">
                    {showCorrelationAnalysis ? 'Hide Analysis' : 'Show Analysis'}
                  </span>
                  {showCorrelationAnalysis ? (
                    <ChevronUp className="h-4 w-4 text-gray-500 dark:text-gray-400 transition-transform duration-200" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-gray-500 dark:text-gray-400 transition-transform duration-200" />
                  )}
                </div>
              </button>
              
              {/* Collapsible Content */}
              {showCorrelationAnalysis && (
                <div
                  data-insight-report-root="correlation_analysis"
                  className="mt-4 animate-in slide-in-from-top-2 duration-200 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 overflow-hidden p-4 sm:p-5"
                >
                  <CorrelationAnalysisComponent
                    datasetId={datasetId || null}
                    targetVariable={localDatasetConfig.target_variable || ''}
                    currentStep={currentStep}
                    enableDisplayThresholdControls={insightsGenerationSource === 'standard'}
                  />
                </div>
              )}
            </div>
          )}

          {/* IV Analysis Section */}
          {localDatasetConfig?.target_variable && selectedInsightSteps?.includes('iv_analysis') && (
            <div className="space-y-4">
              {/* Collapsible Header */}
              <button
                onClick={() => setShowIVAnalysis(!showIVAnalysis)}
                className="w-full flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg border border-gray-200 dark:border-gray-700 transition-all duration-200 group"
              >
                <div className="flex items-center space-x-2">
                  <TrendingUp className="h-5 w-5 text-blue-600" />
                  <span className="font-medium text-gray-900 dark:text-gray-100">Information Value (IV) Analysis</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="text-sm text-gray-500 dark:text-gray-400">
                    {showIVAnalysis ? 'Hide Analysis' : 'Show Analysis'}
                  </span>
                  {showIVAnalysis ? (
                    <ChevronUp className="h-4 w-4 text-gray-500 dark:text-gray-400 transition-transform duration-200" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-gray-500 dark:text-gray-400 transition-transform duration-200" />
                  )}
                </div>
              </button>
              
              {/* Collapsible Content */}
              {showIVAnalysis && (
                <div
                  data-insight-report-root="iv_analysis"
                  className="mt-4 animate-in slide-in-from-top-2 duration-200 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 overflow-hidden p-4 sm:p-5"
                >
                  <IVAnalysisComponent
                    datasetId={datasetId || null}
                    targetVariable={localDatasetConfig.target_variable || ''}
                    currentStep={currentStep}
                  />
                </div>
              )}
            </div>
          )}

          {/* VIF Analysis Section */}
          {localDatasetConfig?.target_variable && selectedInsightSteps?.includes('variance_inflation_factor') && (
            <div className="space-y-4">
              {/* Collapsible Header */}
              <button
                onClick={() => setShowVIFAnalysis(!showVIFAnalysis)}
                className="w-full flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg border border-gray-200 dark:border-gray-700 transition-all duration-200 group"
              >
                <div className="flex items-center space-x-2">
                  <Calculator className="h-5 w-5 text-orange-600" />
                  <span className="font-medium text-gray-900 dark:text-gray-100">Variance Inflation Factor (VIF) Analysis</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="text-sm text-gray-500 dark:text-gray-400">
                    {showVIFAnalysis ? 'Hide Analysis' : 'Show Analysis'}
                  </span>
                  {showVIFAnalysis ? (
                    <ChevronUp className="h-4 w-4 text-gray-500 dark:text-gray-400 transition-transform duration-200" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-gray-500 dark:text-gray-400 transition-transform duration-200" />
                  )}
                </div>
              </button>
              
              {/* Collapsible Content */}
              {showVIFAnalysis && (
                <div
                  data-insight-report-root="variance_inflation_factor"
                  className="mt-4 animate-in slide-in-from-top-2 duration-200 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 overflow-hidden p-4 sm:p-5"
                >
                  <VIFAnalysisComponent
                    datasetId={datasetId || null}
                    targetVariable={localDatasetConfig.target_variable || ''}
                    currentStep={currentStep}
                  />
                </div>
              )}
            </div>
          )}

          {/* Correlation ratio (η) */}
          {localDatasetConfig?.target_variable && selectedInsightSteps?.includes('correlation_ratio_analysis') && (
            <div className="space-y-4">
              <button
                onClick={() => setShowCorrelationRatioAnalysis(!showCorrelationRatioAnalysis)}
                className="w-full flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg border border-gray-200 dark:border-gray-700 transition-all duration-200 group"
              >
                <div className="flex items-center space-x-2">
                  <Activity className="h-5 w-5 text-teal-600" />
                  <span className="font-medium text-gray-900 dark:text-gray-100">Correlation ratio (η)</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="text-sm text-gray-500 dark:text-gray-400">
                    {showCorrelationRatioAnalysis ? 'Hide Analysis' : 'Show Analysis'}
                  </span>
                  {showCorrelationRatioAnalysis ? (
                    <ChevronUp className="h-4 w-4 text-gray-500 dark:text-gray-400 transition-transform duration-200" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-gray-500 dark:text-gray-400 transition-transform duration-200" />
                  )}
                </div>
              </button>
              {showCorrelationRatioAnalysis && (
                <div
                  data-insight-report-root="correlation_ratio_analysis"
                  className="mt-4 animate-in slide-in-from-top-2 duration-200 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 overflow-hidden p-4 sm:p-5"
                >
                  <CorrelationRatioAnalysisComponent
                    datasetId={datasetId || null}
                    targetVariable={localDatasetConfig.target_variable || ''}
                    currentStep={currentStep}
                  />
                </div>
              )}
            </div>
          )}

          {/* Correlation Matrix Section */}
          {localDatasetConfig?.target_variable && selectedInsightSteps?.includes('correlation_matrix') && (
            <div className="space-y-4">
              {/* Collapsible Header */}
              <button
                onClick={() => setShowMulticollinearity(!showMulticollinearity)}
                className="w-full flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg border border-gray-200 dark:border-gray-700 transition-all duration-200 group"
              >
                <div className="flex items-center space-x-2">
                  <TrendingUp className="h-5 w-5 text-purple-600" />
                  <span className="font-medium text-gray-900 dark:text-gray-100">Correlation Matrix</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="text-sm text-gray-500 dark:text-gray-400">
                    {showMulticollinearity ? 'Hide Matrix' : 'Show Matrix'}
                  </span>
                  {showMulticollinearity ? (
                    <ChevronUp className="h-4 w-4 text-gray-500 dark:text-gray-400 transition-transform duration-200" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-gray-500 dark:text-gray-400 transition-transform duration-200" />
                  )}
                </div>
              </button>

              {/* Collapsible Content */}
              {showMulticollinearity && (
                <div
                  data-insight-report-root="correlation_matrix"
                  className="mt-4 animate-in slide-in-from-top-2 duration-200 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 overflow-hidden p-4 sm:p-5"
                >
                  <MulticollinearityAnalysisComponent
                    datasetId={datasetId || null}
                    targetVariable={localDatasetConfig?.target_variable || ''}
                    currentStep={currentStep}
                  />
                </div>
              )}
            </div>
          )}

          {/* Empty state when no right-pane analyses are selected/displayed */}
          {!(
            selectedInsightSteps?.includes('bivariate_analysis') ||
            selectedInsightSteps?.includes('correlation_analysis') ||
            selectedInsightSteps?.includes('correlation_matrix') ||
            selectedInsightSteps?.includes('iv_analysis') ||
            selectedInsightSteps?.includes('variance_inflation_factor') ||
            selectedInsightSteps?.includes('correlation_ratio_analysis')
          ) && (
            <div className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center text-gray-600 dark:text-gray-400">
              In Step 3, choose Auto or Standard under Data Insights, run an analysis, and the matching panels will open here.
            </div>
          )}
        </div>
      );
    }

    // For other steps, show the original insights content
    const insights = [];
    
    if (datasetAnalysis) {
      // Data distribution insight (including Date type)
      const numericalColumns = datasetAnalysis.columns.filter(col => getColumnLogicalType(col) === 'Numerical');
      const categoricalColumns = datasetAnalysis.columns.filter(col => getColumnLogicalType(col) === 'Categorical');
      const dateColumns = datasetAnalysis.columns.filter(col => getColumnLogicalType(col) === 'Date');
      
      insights.push({
        icon: TrendingUp,
        color: 'blue',
        title: 'Data Distribution',
        description: `${numericalColumns.length} numerical, ${categoricalColumns.length} categorical and ${dateColumns.length} date columns detected`
      });

      // Missing values insight
      if (datasetStats.missingValues > 0) {
        insights.push({
          icon: AlertTriangle,
          color: 'orange',
          title: 'Missing Values',
          description: `${datasetStats.missingValues.toLocaleString()} columns has missing rate 100% & 4 columns with missing rate >50%`
        });
      } else {
        insights.push({
          icon: CheckCircle,
          color: 'green',
          title: 'Complete Dataset',
          description: 'No missing values detected in the dataset'
        });
      }

      // High cardinality columns
      const highCardinalityColumns = datasetAnalysis.columns.filter(col => col.unique_count > datasetAnalysis.totalRows * 0.5);
      if (highCardinalityColumns.length > 0) {
        insights.push({
          icon: AlertTriangle,
          color: 'purple',
          title: 'High Cardinality',
          description: `${highCardinalityColumns.length} columns with high unique value counts`
        });
      }

      // Target variable insight
      if (localDatasetConfig?.target_variable) {
        const targetColumn = datasetAnalysis.columns.find(col => col.name === localDatasetConfig.target_variable);
        if (targetColumn) {
          if (targetColumn.type === 'Categorical' && targetColumn.sample_values) {
            const classCount = Object.keys(targetColumn.sample_values).length;
            insights.push({
              icon: Target,
              color: 'blue',
              title: 'Target Variable',
              description: `${targetColumn.name} has ${classCount} classes`
            });
          } else if (targetColumn.type === 'Numerical') {
            insights.push({
              icon: Target,
              color: 'blue',
              title: 'Target Variable',
              description: `${targetColumn.name} is numerical with ${targetColumn.unique_count} unique values`
            });
          }
        }
      }
    }



    return (
      <div className="space-y-6">
        {/* View Data scope lives in sidebar header (shared with Step 3 standard/auto analyses) */}

        {/* Column Distribution Visualization */}
        {datasetAnalysis && (
          <div className="space-y-3">
            <h4 className="font-medium text-gray-900 dark:text-gray-100">Column Distribution</h4>
            
            {/* Multi-Select Column Picker */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-sm text-gray-600 dark:text-gray-400">
                  Select Columns (max {MAX_SELECTED_COLUMNS}):
                </label>
                {selectedColumns.length > 0 && (
                  <button
                    onClick={clearAllSelectedColumns}
                    className="text-xs text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
                  >
                    Clear All
                  </button>
                )}
              </div>
              
              {/* Checkbox Dropdown for selecting columns */}
              <div className="relative" ref={columnDropdownRef}>
                {/* Dropdown Trigger Button */}
                <button
                  onClick={() => setIsColumnDropdownOpen(!isColumnDropdownOpen)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm text-left flex items-center justify-between"
                >
                  <span className={selectedColumns.length === 0 ? 'text-gray-500 dark:text-gray-400' : ''}>
                    {selectedColumns.length === 0 
                      ? 'Select columns to analyze...'
                      : `${selectedColumns.length} column${selectedColumns.length > 1 ? 's' : ''} selected`
                    }
                  </span>
                  <ChevronDown className={`h-4 w-4 text-gray-500 transition-transform ${isColumnDropdownOpen ? 'rotate-180' : ''}`} />
                </button>
                
                {/* Dropdown Menu */}
                {isColumnDropdownOpen && (
                  <div className="absolute z-50 w-full mt-1 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg shadow-lg max-h-64 overflow-y-auto">
                    {/* Header with selection count */}
                    <div className="sticky top-0 bg-gray-50 dark:bg-gray-700 px-3 py-2 border-b border-gray-200 dark:border-gray-600 flex items-center justify-between">
                      <span className="text-xs font-medium text-gray-600 dark:text-gray-300">
                        {selectedColumns.length}/{MAX_SELECTED_COLUMNS} selected
                      </span>
                      {selectedColumns.length > 0 && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            clearAllSelectedColumns();
                          }}
                          className="text-xs text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
                        >
                          Clear All
                        </button>
                      )}
                    </div>
                    
                    {/* Column List with Checkboxes */}
                    <div className="py-1">
                      {datasetAnalysis.columns.map((column) => {
                        const isSelected = selectedColumns.includes(column.name);
                        const isDisabled = !isSelected && selectedColumns.length >= MAX_SELECTED_COLUMNS;
                        
                        return (
                          <label
                            key={column.name}
                            className={`flex items-center px-3 py-2 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 ${
                              isDisabled ? 'opacity-50 cursor-not-allowed' : ''
                            } ${isSelected ? 'bg-blue-50 dark:bg-blue-900/20' : ''}`}
                          >
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={() => !isDisabled && handleMultiColumnToggle(column.name)}
                              disabled={isDisabled}
                              className="h-4 w-4 text-blue-600 border-gray-300 dark:border-gray-600 rounded focus:ring-blue-500 dark:bg-gray-700"
                            />
                            <span className={`ml-3 text-sm ${isSelected ? 'font-medium text-blue-700 dark:text-blue-300' : 'text-gray-700 dark:text-gray-300'}`}>
                              {column.name}
                            </span>
                            <span className={`ml-auto text-xs ${
                              column.type === 'Numerical' 
                                ? 'text-green-600 dark:text-green-400' 
                                : column.type === 'Categorical'
                                  ? 'text-purple-600 dark:text-purple-400'
                                  : 'text-gray-500 dark:text-gray-400'
                            }`}>
                              {column.type}
                            </span>
                          </label>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
              
              {/* Selected Columns Pills */}
              {selectedColumns.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-2">
                  {selectedColumns.map((col) => (
                    <span
                      key={col}
                      className="inline-flex items-center px-2 py-1 text-xs font-medium bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-300 rounded-full"
                    >
                      {col}
                      <button
                        onClick={() => handleMultiColumnToggle(col)}
                        className="ml-1 hover:text-blue-600 dark:hover:text-blue-200"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </span>
                  ))}
                </div>
              )}
              
              {/* Generate Insights Button */}
              {selectedColumns.length > 0 && (
                <button
                  onClick={generateMultiColumnInsights}
                  disabled={isLoadingInsights || Object.keys(multiColumnDistributions).length < selectedColumns.length}
                  className={`w-full mt-2 py-2 px-4 text-sm font-medium text-white bg-purple-600 hover:bg-purple-700 rounded-lg transition-colors flex items-center justify-center space-x-2 ${
                    isLoadingInsights || Object.keys(multiColumnDistributions).length < selectedColumns.length
                      ? 'opacity-50 cursor-not-allowed'
                      : ''
                  }`}
                >
                  <Brain className="h-4 w-4" />
                  <span>
                    {isLoadingInsights 
                      ? 'Generating Insights...' 
                      : `Generate Insights for ${selectedColumns.length} Column${selectedColumns.length > 1 ? 's' : ''}`
                    }
                  </span>
                </button>
              )}
            </div>

            {/* Multi-Column Distribution Section (Charts + Insights) */}
            {selectedColumns.length > 0 && (
              <div data-testid="distribution-section" className="space-y-4">
                {/* Download Button Header */}
                <div className="flex items-center justify-between">
                  <h5 className="text-sm font-medium text-gray-900 dark:text-gray-100">
                    Distribution Charts ({selectedColumns.length} column{selectedColumns.length > 1 ? 's' : ''})
                  </h5>
                  <button
                    onClick={downloadChartAndInsightsAsImage}
                    className="flex items-center space-x-1.5 px-2.5 py-1.5 text-xs font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg transition-colors"
                    title="Download chart and insights as image"
                  >
                    <Download className="h-3.5 w-3.5" />
                    <span>Download as Image</span>
                  </button>
                </div>

                {/* Charts Grid */}
                <div className={`grid gap-4 ${selectedColumns.length === 1 ? 'grid-cols-1' : selectedColumns.length === 2 ? 'grid-cols-2' : 'grid-cols-2'}`}>
                {selectedColumns.map((colName) => {
                  const distInfo = multiColumnDistributions[colName];
                  const colDistribution = distInfo?.distribution || {};
                  const colData = distInfo?.data || null;
                  const isLoading = !distInfo;
                  
                  return (
                    <div key={colName} className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-3">
                      {isLoading ? (
                        <div className="h-48 flex items-center justify-center">
                          <div className="text-center">
                            <Loader className="h-6 w-6 text-blue-500 animate-spin mx-auto mb-2" />
                            <p className="text-xs text-gray-500">Loading...</p>
                          </div>
                        </div>
                      ) : Object.keys(colDistribution).length > 0 ? (
                        <div className="h-48">
                          <Bar
                            data={{
                              labels: Object.keys(colDistribution),
                              datasets: [{
                                label: 'Count',
                                data: Object.values(colDistribution),
                                backgroundColor: colData ? 'rgba(34, 197, 94, 0.6)' : 'rgba(59, 130, 246, 0.6)',
                                borderColor: colData ? 'rgba(34, 197, 94, 1)' : 'rgba(59, 130, 246, 1)',
                                borderWidth: 1,
                                borderRadius: getColumnType(colName) === 'Numerical' ? 0 : 4,
                                categoryPercentage: getColumnType(colName) === 'Numerical' ? 1.0 : 0.8,
                                barPercentage: getColumnType(colName) === 'Numerical' ? 1.0 : 0.8,
                              }],
                            }}
                            options={{
                              responsive: true,
                              maintainAspectRatio: false,
                              plugins: {
                                legend: { display: false },
                                title: {
                                  display: true,
                                  text: `"${colName}"`,
                                  font: { size: 11, weight: 'bold' },
                                  color: isDark ? '#d1d5db' : '#374151',
                                },
                                tooltip: {
                                  backgroundColor: 'rgba(0, 0, 0, 0.8)',
                                  callbacks: {
                                    title: (ctx) => getColumnType(colName) === 'Numerical' ? `Range: ${ctx[0].label}` : `Category: ${ctx[0].label}`,
                                    label: (ctx) => `Count: ${ctx.parsed.y}`,
                                  },
                                },
                              },
                              scales: {
                                y: {
                                  beginAtZero: true,
                                  title: { display: true, text: 'Frequency', font: { size: 10, weight: 'bold' as const }, color: isDark ? '#e5e7eb' : '#374151' },
                                  grid: { color: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)' },
                                  border: { display: false },
                                  ticks: { 
                                    font: { size: 9, weight: 'bold' as const }, 
                                    color: isDark ? '#a1a1aa' : '#52525b',
                                    padding: 4,
                                    callback: function(value) {
                                      const numValue = Number(value);
                                      if (numValue >= 1000000) return (numValue / 1000000).toFixed(1) + 'M';
                                      if (numValue >= 10000) return (numValue / 1000).toFixed(0) + 'K';
                                      if (numValue >= 1000) return (numValue / 1000).toFixed(1) + 'K';
                                      return numValue.toLocaleString();
                                    },
                                  },
                                },
                                x: {
                                  title: { display: true, text: getColumnType(colName) === 'Numerical' ? 'Value Range' : 'Categories', font: { size: 10, weight: 'bold' as const }, color: isDark ? '#e5e7eb' : '#374151' },
                                  grid: { display: false },
                                  border: { display: true, color: isDark ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.1)' },
                                  ticks: {
                                    font: { size: 9 },
                                    color: isDark ? '#a1a1aa' : '#52525b',
                                    maxRotation: 35,
                                    minRotation: 0,
                                    autoSkip: true,
                                    maxTicksLimit: 8,
                                    padding: 4,
                                    callback: function(_value, index) {
                                      const label = this.getLabelForValue(index);
                                      const columnType = getColumnType(colName);
                                      
                                      if (columnType === 'Numerical') {
                                        // Format numerical range labels: "[0.00, 100.00)" -> "0-100"
                                        const rangeMatch = String(label).match(/\[?([-\d.,]+)\s*[,\-]\s*([-\d.,]+)\)?/);
                                        if (rangeMatch) {
                                          const start = parseFloat(rangeMatch[1].replace(/,/g, ''));
                                          const end = parseFloat(rangeMatch[2].replace(/,/g, ''));
                                          const formatNum = (n: number) => {
                                            if (Math.abs(n) >= 1000000) return (n / 1000000).toFixed(1) + 'M';
                                            if (Math.abs(n) >= 1000) return (n / 1000).toFixed(0) + 'K';
                                            if (Number.isInteger(n)) return n.toString();
                                            return n.toFixed(0);
                                          };
                                          return `${formatNum(start)}-${formatNum(end)}`;
                                        }
                                      }
                                      // Truncate long category names
                                      return typeof label === 'string' && label.length > 10 ? label.substring(0, 8) + '…' : label;
                                    },
                                  },
                                },
                              },
                            }}
                          />
                        </div>
                      ) : (
                        <div className="h-48 flex items-center justify-center">
                          <p className="text-xs text-gray-500">No data for "{colName}"</p>
                        </div>
                      )}
                    </div>
                  );
                })}
                </div>

                {/* AI Insights Section for Multi-Select */}
                {columnInsights.length > 0 && (
                  <div 
                    className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4"
                  >
                    <div className="flex items-center justify-between mb-3">
                      <h5 className="text-sm font-medium text-gray-900 dark:text-gray-100 flex items-center space-x-2">
                        <Brain className="h-4 w-4 text-purple-500" />
                        <span>AI Insights ({columnInsights.length})</span>
                      </h5>
                    </div>
                
                <div className="space-y-2">
                  {(showAllInsights ? columnInsights : columnInsights.slice(0, 3)).map((insight, index) => (
                    <div 
                      key={index} 
                      className={`p-3 rounded-lg border ${
                        insight.type === 'warning' 
                          ? 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800' 
                          : insight.type === 'success' 
                            ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'
                            : 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800'
                      }`}
                    >
                      <div className="flex items-start space-x-2">
                        {insight.type === 'warning' ? (
                          <AlertTriangle className="h-4 w-4 text-amber-500 mt-0.5 flex-shrink-0" />
                        ) : insight.type === 'success' ? (
                          <CheckCircle className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
                        ) : (
                          <Info className="h-4 w-4 text-blue-500 mt-0.5 flex-shrink-0" />
                        )}
                        <div className="flex-1 min-w-0">
                          <p className={`text-xs font-medium ${
                            insight.type === 'warning' 
                              ? 'text-amber-800 dark:text-amber-300' 
                              : insight.type === 'success' 
                                ? 'text-green-800 dark:text-green-300'
                                : 'text-blue-800 dark:text-blue-300'
                          }`}>
                            {insight.title}
                          </p>
                          <p className={`text-xs mt-1 ${
                            insight.type === 'warning' 
                              ? 'text-amber-700 dark:text-amber-400' 
                              : insight.type === 'success' 
                                ? 'text-green-700 dark:text-green-400'
                                : 'text-blue-700 dark:text-blue-400'
                          }`}>
                            {insight.description}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                  
                  {columnInsights.length > 3 && (
                    <button
                      onClick={() => setShowAllInsights(!showAllInsights)}
                      className="w-full mt-2 py-2 px-3 text-xs font-medium text-purple-600 dark:text-purple-400 bg-purple-50 dark:bg-purple-900/20 hover:bg-purple-100 dark:hover:bg-purple-900/30 rounded-lg border border-purple-200 dark:border-purple-800 transition-colors flex items-center justify-center space-x-1"
                    >
                      {showAllInsights ? (
                        <>
                          <ChevronUp className="h-3 w-3" />
                          <span>Show Less</span>
                        </>
                      ) : (
                        <>
                          <ChevronDown className="h-3 w-3" />
                          <span>View All {columnInsights.length} Insights</span>
                        </>
                      )}
                    </button>
                  )}
                  </div>
                </div>
                )}
              </div>
            )}

            {/* Single Column Chart Container (hidden when multi-select is active) */}
            {selectedColumns.length === 0 && selectedColumn && (
              <div 
                data-testid="distribution-section"
                className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4"
              >
                <div className="flex items-center justify-between mb-3">
                  <h5 className="text-sm font-medium text-gray-900 dark:text-gray-100">
                    Distribution of "{selectedColumn}"
                  </h5>
                  <div className="flex items-center space-x-2">
                    {!isLoadingDistribution && Object.keys(columnDistribution).length > 0 && (
                      <button
                        onClick={downloadChartAndInsightsAsImage}
                        className="flex items-center space-x-1.5 px-2.5 py-1.5 text-xs font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg transition-colors"
                        title="Download chart and insights as image"
                      >
                        <Download className="h-3.5 w-3.5" />
                        <span>Download</span>
                      </button>
                    )}
                    {isLoadingDistribution && (
                      <Loader className="h-4 w-4 text-blue-500 animate-spin" />
                    )}
                  </div>
                </div>

                {isLoadingDistribution ? (
                  <div className="h-64 flex items-center justify-center bg-gray-50 dark:bg-gray-800 rounded-lg">
                    <div className="text-center">
                      <Loader className="h-8 w-8 text-blue-500 animate-spin mx-auto mb-2" />
                      <p className="text-sm text-gray-600 dark:text-gray-400">Loading distribution data...</p>
                    </div>
                  </div>
                ) : Object.keys(columnDistribution).length > 0 ? (
                  <>
                    <div className="h-64" data-testid="column-distribution-bar-chart">
                      <Bar
                        data={{
                          labels: Object.keys(columnDistribution),
                          datasets: [
                            {
                              label: 'Count',
                              data: Object.values(columnDistribution),
                              backgroundColor: distributionData ? 'rgba(34, 197, 94, 0.6)' : 'rgba(59, 130, 246, 0.6)',
                              borderColor: distributionData ? 'rgba(34, 197, 94, 1)' : 'rgba(59, 130, 246, 1)',
                              borderWidth: 1,
                              // Different styling for numerical vs categorical
                              borderRadius: getColumnType(selectedColumn) === 'Numerical' ? 0 : 4,
                              borderSkipped: getColumnType(selectedColumn) === 'Numerical' ? false : false,
                              categoryPercentage: getColumnType(selectedColumn) === 'Numerical' ? 1.0 : 0.8,
                              barPercentage: getColumnType(selectedColumn) === 'Numerical' ? 1.0 : 0.8,
                            },
                          ],
                        }}
                        options={{
                          responsive: true,
                          maintainAspectRatio: false,
                          plugins: {
                            legend: {
                              display: false,
                            },
                            title: {
                              display: true,
                              text: getColumnType(selectedColumn) === 'Numerical' ? 
                                `"${selectedColumn}"` : 
                                `Distribution of "${selectedColumn}"`,
                              font: {
                                size: 14,
                                weight: 'bold',
                              },
                              color: isDark ? '#d1d5db' : '#374151',
                              padding: {
                                bottom: 20,
                              },
                            },
                            tooltip: {
                              backgroundColor: 'rgba(0, 0, 0, 0.8)',
                              titleColor: 'white',
                              bodyColor: 'white',
                              borderColor: distributionData ? 'rgba(34, 197, 94, 1)' : 'rgba(59, 130, 246, 1)',
                              borderWidth: 1,
                              callbacks: {
                                title: (context) => {
                                  const columnType = getColumnType(selectedColumn);
                                  if (columnType === 'Numerical') {
                                    return `Range: ${context[0].label}`;
                                  } else {
                                    return `Category: ${context[0].label}`;
                                  }
                                },
                                label: (context) => {
                                  const count = context.parsed.y;
                                  if (distributionData) {
                                    const percentage = ((count / distributionData.statistics.valid_count) * 100).toFixed(1);
                                    return `Count: ${count} (${percentage}% of valid records)`;
                                  } else {
                                    return `Count: ${count}`;
                                  }
                                },
                                afterLabel: getColumnType(selectedColumn) === 'Numerical' ? () => {
                                  return '';
                                } : undefined,
                              },
                            },
                          },
                          scales: {
                            y: {
                              beginAtZero: true,
                              title: {
                                display: true,
                                text: 'Frequency',
                                font: {
                                  size: 12,
                                  weight: 'bold' as const,
                                },
                                color: isDark ? '#e5e7eb' : '#374151',
                                padding: { bottom: 4 },
                              },
                              grid: {
                                color: isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.08)',
                              },
                              border: {
                                display: false,
                              },
                              ticks: {
                                font: {
                                  size: 11,
                                  weight: 'bold' as const,
                                },
                                color: isDark ? '#a1a1aa' : '#52525b',
                                padding: 8,
                                callback: function(value) {
                                  // Format Y-axis values with K/M notation
                                  const numValue = Number(value);
                                  if (numValue >= 1000000) return (numValue / 1000000).toFixed(1) + 'M';
                                  if (numValue >= 10000) return (numValue / 1000).toFixed(0) + 'K';
                                  if (numValue >= 1000) return (numValue / 1000).toFixed(1) + 'K';
                                  return numValue.toLocaleString();
                                },
                              },
                            },
                            x: {
                              title: {
                                display: true,
                                text: getColumnType(selectedColumn) === 'Numerical' ? 
                                  'Value Range' : 
                                  'Categories',
                                font: {
                                  size: 12,
                                  weight: 'bold' as const,
                                },
                                color: isDark ? '#e5e7eb' : '#374151',
                                padding: { top: 8 },
                              },
                              grid: {
                                display: false,
                              },
                              border: {
                                display: true,
                                color: isDark ? 'rgba(255, 255, 255, 0.15)' : 'rgba(0, 0, 0, 0.1)',
                              },
                              ticks: {
                                font: {
                                  size: 11,
                                  weight: 'bold' as const,
                                },
                                color: isDark ? '#a1a1aa' : '#52525b',
                                maxRotation: 35,
                                minRotation: 0,
                                autoSkip: true,
                                maxTicksLimit: 12,
                                padding: 6,
                                callback: function(value) {
                                  const label = this.getLabelForValue(Number(value));
                                  const columnType = getColumnType(selectedColumn);
                                  
                                  if (columnType === 'Numerical') {
                                    // Format numerical range labels cleanly: "[0.00, 100.00)" -> "0-100"
                                    const rangeMatch = label.match(/\[?([-\d.,]+)\s*[,\-]\s*([-\d.,]+)\)?/);
                                    if (rangeMatch) {
                                      const start = parseFloat(rangeMatch[1].replace(/,/g, ''));
                                      const end = parseFloat(rangeMatch[2].replace(/,/g, ''));
                                      const formatNum = (n: number) => {
                                        if (Math.abs(n) >= 1000000) return (n / 1000000).toFixed(1) + 'M';
                                        if (Math.abs(n) >= 10000) return (n / 1000).toFixed(0) + 'K';
                                        if (Math.abs(n) >= 1000) return (n / 1000).toFixed(1) + 'K';
                                        if (Number.isInteger(n)) return n.toString();
                                        return n.toFixed(1);
                                      };
                                      return `${formatNum(start)}-${formatNum(end)}`;
                                    }
                                    return label;
                                  } else {
                                    // Truncate long category names with ellipsis
                                    if (label.length > 12) {
                                      return label.substring(0, 10) + '…';
                                    }
                                    return label;
                                  }
                                },
                              },
                            },
                          },
                          interaction: {
                            intersect: false,
                            mode: 'index',
                          },
                        }}
                      />
                    </div>
                    
                    {/* Enhanced Chart Info */}
                    <div className="mt-3 space-y-2">
                      <div className="flex items-center space-x-2 text-xs">
                        {distributionData ? (
                          <div className="flex items-center space-x-1">
                            <div className="w-3 h-3 rounded bg-green-500"></div>
                            <span className="text-green-700 dark:text-green-400 font-medium">Real Data</span>
                          </div>
                        ) : (
                          <div className="flex items-center space-x-1">
                            <div className="w-3 h-3 rounded bg-blue-500"></div>
                            <span className="text-blue-700 dark:text-blue-400 font-medium">Estimated Data</span>
                          </div>
                        )}
                      </div>
                      
                      <div className="text-xs text-gray-600 dark:text-gray-400">
                        {distributionData ? (
                          <div className="space-y-1">
                            <p>
                              {distributionData.is_numerical 
                                ? `📊 Quantile-based Histogram: ${Object.keys(distributionData.distribution).length} bins with equal sample sizes`
                                : `📋 Bar Chart: ${Object.keys(distributionData.distribution).length} categories with value counts`}
                            </p>
                            <p>
                              Total: {distributionData.statistics.total_count.toLocaleString()} records, 
                              Valid: {distributionData.statistics.valid_count.toLocaleString()}, 
                              Missing: {distributionData.statistics.missing_count.toLocaleString()}
                            </p>
                          </div>
                        ) : (
                          <p>
                            {getColumnType(selectedColumn) === 'Categorical' 
                              ? `📋 Estimated Bar Chart: Value counts for categorical column "${selectedColumn}"`
                              : `📊 Estimated Quantile-based Histogram: Simulated distribution bins for numerical column "${selectedColumn}"`
                            }
                          </p>
                        )}
                      </div>
                    </div>
                    
                    {/* AI-Generated Insights Section */}
                    <div className="mt-4 border-t border-gray-200 dark:border-gray-700 pt-4">
                      <div className="flex items-center justify-between mb-3">
                        <h5 className="text-sm font-medium text-gray-900 dark:text-gray-100 flex items-center space-x-2">
                          <Brain className="h-4 w-4 text-purple-500" />
                          <span>AI Insights</span>
                        </h5>
                        {isLoadingInsights && (
                          <Loader className="h-4 w-4 text-purple-500 animate-spin" />
                        )}
                      </div>
                      
                      {isLoadingInsights ? (
                        <div className="flex items-center justify-center py-4">
                          <div className="text-center">
                            <Loader className="h-6 w-6 text-purple-500 animate-spin mx-auto mb-2" />
                            <p className="text-xs text-gray-500 dark:text-gray-400">Generating insights...</p>
                          </div>
                        </div>
                      ) : columnInsights.length > 0 ? (
                        <div className="space-y-2">
                          {/* Show top 3 insights by default */}
                          {(showAllInsights ? columnInsights : columnInsights.slice(0, 3)).map((insight, index) => (
                            <div 
                              key={index} 
                              className={`p-3 rounded-lg border ${
                                insight.type === 'warning' 
                                  ? 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800' 
                                  : insight.type === 'success' 
                                    ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'
                                    : 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800'
                              }`}
                            >
                              <div className="flex items-start space-x-2">
                                {insight.type === 'warning' ? (
                                  <AlertTriangle className="h-4 w-4 text-amber-500 mt-0.5 flex-shrink-0" />
                                ) : insight.type === 'success' ? (
                                  <CheckCircle className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
                                ) : (
                                  <Info className="h-4 w-4 text-blue-500 mt-0.5 flex-shrink-0" />
                                )}
                                <div className="flex-1 min-w-0">
                                  <p className={`text-xs font-medium ${
                                    insight.type === 'warning' 
                                      ? 'text-amber-800 dark:text-amber-300' 
                                      : insight.type === 'success' 
                                        ? 'text-green-800 dark:text-green-300'
                                        : 'text-blue-800 dark:text-blue-300'
                                  }`}>
                                    {insight.title}
                                  </p>
                                  <p className={`text-xs mt-1 ${
                                    insight.type === 'warning' 
                                      ? 'text-amber-700 dark:text-amber-400' 
                                      : insight.type === 'success' 
                                        ? 'text-green-700 dark:text-green-400'
                                        : 'text-blue-700 dark:text-blue-400'
                                  }`}>
                                    {insight.description}
                                  </p>
                                </div>
                              </div>
                            </div>
                          ))}
                          
                          {/* View All / View Less button */}
                          {columnInsights.length > 3 && (
                            <button
                              onClick={() => setShowAllInsights(!showAllInsights)}
                              className="w-full mt-2 py-2 px-3 text-xs font-medium text-purple-600 dark:text-purple-400 bg-purple-50 dark:bg-purple-900/20 hover:bg-purple-100 dark:hover:bg-purple-900/30 rounded-lg border border-purple-200 dark:border-purple-800 transition-colors flex items-center justify-center space-x-1"
                            >
                              {showAllInsights ? (
                                <>
                                  <ChevronUp className="h-3 w-3" />
                                  <span>Show Less</span>
                                </>
                              ) : (
                                <>
                                  <ChevronDown className="h-3 w-3" />
                                  <span>View All {columnInsights.length} Insights</span>
                                </>
                              )}
                            </button>
                          )}
                        </div>
                      ) : (
                        <div className="text-center py-3">
                          <p className="text-xs text-gray-500 dark:text-gray-400">No insights available</p>
                        </div>
                      )}
                    </div>
                  </>
                ) : (
                  <div className="h-64 flex items-center justify-center bg-gray-50 dark:bg-gray-800 rounded-lg">
                    <div className="text-center">
                      <BarChart3 className="h-8 w-8 text-gray-400 mx-auto mb-2" />
                      <p className="text-sm text-gray-600 dark:text-gray-400">
                        No distribution data available for "{selectedColumn}"
                      </p>
                    </div>
                  </div>
                )}
              </div>
            )}


          </div>
        )}

        {/* Bivariate Analysis Section */}
        {currentStep === 3 && localDatasetConfig?.target_variable && (
          <div className="space-y-4">
            <div className="border-t border-gray-200 dark:border-gray-700 pt-6">
              <h4 className="font-medium text-gray-900 dark:text-gray-100 mb-4 flex items-center space-x-2">
                <BarChart3 className="h-5 w-5 text-blue-600" />
                <span>Bivariate Analysis</span>
              </h4>
              <BivariateAnalysisComponent
                datasetId={datasetId || null}
                targetVariable={localDatasetConfig.target_variable || ''}
                currentStep={currentStep}
                allowBinningCustomization={insightsGenerationSource === 'standard'}
              />
            </div>
          </div>
        )}
      </div>
    );
  };

  /**
   * Render EDA Comparison Tab (Data Treatment page — step 2)
   *
   * "Original EDA" sub-tab: reuses the same columnInfo + View Data dropdown as the
   *   Overview tab so the user sees the exact same detailed statistics.
   *
   * "EDA Comparison" sub-tab: reuses the compareColumnStats endpoint (same data as
   *   the "Compare Changes" modal in ModelBuilder) and renders it inline.
   */
  const renderEDAComparisonTab = () => {
    // Helper: format a numeric value for the heatmap cells
    const fmtCell = (v: any): string => {
      if (v === null || v === undefined) return '-';
      if (typeof v === 'number') return Number.isFinite(v) ? v.toFixed(2) : '-';
      return String(v);
    };

    // Helper: heatmap cell colour based on change direction
    const getHeatmapColor = (changeData: any): string => {
      if (!changeData) return 'bg-gray-50 dark:bg-[#0f1428]';
      const pct = typeof changeData.change_pct === 'number' && Number.isFinite(changeData.change_pct)
        ? changeData.change_pct : null;
      const intensity = Math.min(Math.abs(pct ?? 0) / 100, 1);
      if (changeData.change > 0) {
        return intensity > 0.5 ? 'bg-green-300 dark:bg-green-900/60'
          : intensity > 0.2 ? 'bg-green-200 dark:bg-green-900/45'
          : intensity > 0.05 ? 'bg-green-100 dark:bg-green-900/30'
          : 'bg-green-50 dark:bg-green-900/20';
      } else if (changeData.change < 0) {
        return intensity > 0.5 ? 'bg-red-300 dark:bg-red-900/60'
          : intensity > 0.2 ? 'bg-red-200 dark:bg-red-900/45'
          : intensity > 0.05 ? 'bg-red-100 dark:bg-red-900/30'
          : 'bg-red-50 dark:bg-red-900/20';
      }
      return 'bg-gray-50 dark:bg-[#0f1428]';
    };

    const getStatusColor = (status: string): string => {
      if (status === 'added') return 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-200';
      if (status === 'removed') return 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200';
      if (status === 'modified') return 'bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-200';
      return 'bg-gray-50 text-gray-600 dark:bg-[#0f1428] dark:text-gray-300';
    };

    // ── Original EDA sub-tab ──────────────────────────────────────────────────
    const renderOriginalEDA = () => {
      // Reuse columnInfo state (same as renderOverviewTab) with View Data dropdown
      const getColType = (col: ColumnInfo): 'Numerical' | 'Categorical' | 'Date' => {
        return col.column_type ||
          (col.data_type && (col.data_type.toLowerCase().includes('date') || col.data_type.toLowerCase().includes('time'))
            ? 'Date'
            : ['int64', 'float64', 'int32', 'float32'].includes(col.data_type) ? 'Numerical' : 'Categorical') as 'Numerical' | 'Categorical' | 'Date';
      };

      const downloadTableAsCSV = (rows: Record<string, any>[], filename: string) => {
        if (rows.length === 0) return;
        const headers = Object.keys(rows[0]);
        const csv = [
          headers.join(','),
          ...rows.map((r) => headers.map((h) => {
            const v = r[h];
            if (v === null || v === undefined) return '';
            const s = String(v).replace(/"/g, '""');
            return `"${s}"`;
          }).join(','))
        ].join('\n');
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
      };

      const fmt = (v?: number | null) => (v === null || v === undefined ? '-' : v.toFixed(2));

      return (
        <div className="space-y-4">
          {/* View Data scope dropdown — identical to Overview tab */}
          <div className="flex items-center space-x-3">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">View Data:</label>
            <select
              value={columnInfoScope}
              onChange={(e) => setColumnInfoScope(e.target.value as 'entire' | 'train' | 'test' | 'validation')}
              className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="entire">Full Data (Entire)</option>
              <option value="train">Train</option>
              <option value="test">Test</option>
              <option value="validation">Validation</option>
            </select>
            {columnInfo?.total_rows !== undefined && (
              <span className="text-xs text-gray-500 dark:text-gray-400">
                ({columnInfo.total_rows.toLocaleString()} rows)
              </span>
            )}
          </div>

          {isLoadingColumnInfo ? (
            <div className="p-3 text-sm text-gray-600 dark:text-gray-400">Loading column statistics…</div>
          ) : columnInfo && columnInfo.columns_info.length > 0 ? (() => {
            const numericalCols = columnInfo.columns_info.filter(col => getColType(col) === 'Numerical');
            const categoricalCols = columnInfo.columns_info.filter(col => getColType(col) === 'Categorical');
            const dateCols = columnInfo.columns_info.filter(col => getColType(col) === 'Date');

            return (
              <div className="space-y-4">
                {/* Numerical */}
                {numericalCols.length > 0 && (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <Hash className="h-4 w-4 text-blue-500" />
                        <h5 className="text-sm font-medium text-gray-800 dark:text-gray-200">
                          Numerical Variables ({numericalCols.length})
                        </h5>
                      </div>
                      <button
                        onClick={() => {
                          const rows = numericalCols.map((col) => ({
                            column_name: col.column_name,
                            total_obs: col.total_count,
                            missing_count: col.missing_count,
                            missing_pct: `${col.total_count > 0 ? ((col.missing_count / col.total_count) * 100).toFixed(2) : '0.00'}%`,
                            distinct: col.unique_count,
                            min: col.min_value ?? '',
                            max: col.max_value ?? '',
                            mean: col.mean ?? '',
                            median: col.median ?? '',
                            mode: col.mode ?? '',
                            p1: col.percentile_1 ?? '',
                            p5: col.percentile_5 ?? '',
                            p25: col.percentile_25 ?? '',
                            p75: col.percentile_75 ?? '',
                            p95: col.percentile_95 ?? '',
                            p99: col.percentile_99 ?? '',
                            variance: col.variance ?? '',
                            std_dev: col.standard_deviation ?? '',
                            skewness: col.skewness ?? '',
                          }));
                          downloadTableAsCSV(rows, `numerical_eda_${datasetId || 'dataset'}.csv`);
                        }}
                        className="inline-flex items-center space-x-1.5 px-2.5 py-1 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] text-xs font-medium rounded-md hover:bg-blue-700 dark:hover:bg-[#333380] transition-colors"
                      >
                        <Download className="h-3 w-3" />
                        <span>Download CSV</span>
                      </button>
                    </div>
                    <div className="max-h-56 overflow-y-auto overflow-x-auto border border-blue-200 dark:border-blue-800 rounded-lg bg-white dark:bg-gray-800">
                      <table className="min-w-[1600px] w-full text-xs border-collapse">
                        <thead className="bg-blue-50 dark:bg-gray-800 sticky top-0 z-10">
                          <tr>
                            {['Column','Total Obs','Missing #','Missing %','Distinct','Min','Max','Mean','Median','Mode','P1','P5','P25','P75','P95','P99','Variance','Std Dev','Skewness'].map(h => (
                              <th key={h} className="px-3 py-2 text-left font-semibold text-blue-700 dark:text-blue-300 border-b border-blue-200 dark:border-blue-800 whitespace-nowrap">{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {numericalCols.map((col) => {
                            const missingPct = col.total_count > 0 ? ((col.missing_count / col.total_count) * 100).toFixed(2) : '0.00';
                            return (
                              <tr key={col.column_name} className="border-b border-blue-100 dark:border-blue-900 hover:bg-blue-50/50 dark:hover:bg-blue-900/20">
                                <td className="px-3 py-1.5 font-medium text-gray-900 dark:text-gray-100 max-w-[120px] truncate whitespace-nowrap" title={col.column_name}>{col.column_name}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.total_count.toLocaleString()}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.missing_count.toLocaleString()}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{missingPct}%</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.unique_count.toLocaleString()}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.min_value)}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.max_value)}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.mean)}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.median)}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.mode !== null && col.mode !== undefined ? String(col.mode) : '-'}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.percentile_1)}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.percentile_5)}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.percentile_25)}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.percentile_75)}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.percentile_95)}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.percentile_99)}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.variance)}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.standard_deviation)}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.skewness)}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Categorical */}
                {categoricalCols.length > 0 && (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <Activity className="h-4 w-4 text-purple-500" />
                        <h5 className="text-sm font-medium text-gray-800 dark:text-gray-200">
                          Categorical Variables ({categoricalCols.length})
                        </h5>
                      </div>
                      <button
                        onClick={() => {
                          const rows = categoricalCols.map((col) => ({
                            column_name: col.column_name,
                            total_obs: col.total_count,
                            missing_count: col.missing_count,
                            missing_pct: `${col.total_count > 0 ? ((col.missing_count / col.total_count) * 100).toFixed(2) : '0.00'}%`,
                            distinct: col.unique_count,
                            mode: col.mode ?? '',
                            top_category_pct: col.top_category_pct ?? '',
                            lowest_category_pct: col.lowest_category_pct ?? '',
                          }));
                          downloadTableAsCSV(rows, `categorical_eda_${datasetId || 'dataset'}.csv`);
                        }}
                        className="inline-flex items-center space-x-1.5 px-2.5 py-1 bg-purple-600 dark:bg-[#3a2966] text-white dark:text-[#ddccff] text-xs font-medium rounded-md hover:bg-purple-700 transition-colors"
                      >
                        <Download className="h-3 w-3" />
                        <span>Download CSV</span>
                      </button>
                    </div>
                    <div className="max-h-56 overflow-y-auto overflow-x-auto border border-purple-200 dark:border-purple-800 rounded-lg bg-white dark:bg-gray-800">
                      <table className="min-w-[800px] w-full text-xs border-collapse">
                        <thead className="bg-purple-50 dark:bg-gray-800 sticky top-0 z-10">
                          <tr>
                            {['Column','Total Obs','Missing #','Missing %','Distinct','Mode','Top Category %','Lowest Category %'].map(h => (
                              <th key={h} className="px-3 py-2 text-left font-semibold text-purple-700 dark:text-purple-300 border-b border-purple-200 dark:border-purple-800 whitespace-nowrap">{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {categoricalCols.map((col) => {
                            const missingPct = col.total_count > 0 ? ((col.missing_count / col.total_count) * 100).toFixed(2) : '0.00';
                            return (
                              <tr key={col.column_name} className="border-b border-purple-100 dark:border-purple-900 hover:bg-purple-50/50 dark:hover:bg-purple-900/20">
                                <td className="px-3 py-1.5 font-medium text-gray-900 dark:text-gray-100 max-w-[120px] truncate whitespace-nowrap" title={col.column_name}>{col.column_name}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.total_count.toLocaleString()}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.missing_count.toLocaleString()}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{missingPct}%</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.unique_count.toLocaleString()}</td>
                                <td className="px-3 py-1.5 text-gray-700 dark:text-gray-300 max-w-[150px] truncate whitespace-nowrap" title={col.mode !== null && col.mode !== undefined ? String(col.mode) : ''}>
                                  {col.mode !== null && col.mode !== undefined ? String(col.mode) : '-'}
                                </td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.top_category_pct !== null && col.top_category_pct !== undefined ? `${col.top_category_pct.toFixed(2)}%` : '-'}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.lowest_category_pct !== null && col.lowest_category_pct !== undefined ? `${col.lowest_category_pct.toFixed(2)}%` : '-'}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Date */}
                {dateCols.length > 0 && (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <Calendar className="h-4 w-4 text-green-500" />
                        <h5 className="text-sm font-medium text-gray-800 dark:text-gray-200">
                          Date Variables ({dateCols.length})
                        </h5>
                      </div>
                      <button
                        onClick={() => {
                          const rows = dateCols.map((col) => ({
                            column_name: col.column_name,
                            non_null: col.total_count - col.missing_count,
                            missing_pct: `${col.total_count > 0 ? ((col.missing_count / col.total_count) * 100).toFixed(2) : '0.00'}%`,
                            min: col.date_min ?? '',
                            max: col.date_max ?? '',
                            distinct: col.unique_count,
                            most_frequent: col.most_frequent_date ?? '',
                          }));
                          downloadTableAsCSV(rows, `date_eda_${datasetId || 'dataset'}.csv`);
                        }}
                        className="inline-flex items-center space-x-1.5 px-2.5 py-1 bg-green-600 dark:bg-[#1a3a29] text-white dark:text-[#ccffdd] text-xs font-medium rounded-md hover:bg-green-700 transition-colors"
                      >
                        <Download className="h-3 w-3" />
                        <span>Download CSV</span>
                      </button>
                    </div>
                    <div className="max-h-56 overflow-y-auto overflow-x-auto border border-green-200 dark:border-green-800 rounded-lg bg-white dark:bg-gray-800">
                      <table className="min-w-[700px] w-full text-xs border-collapse">
                        <thead className="bg-green-50 dark:bg-gray-800 sticky top-0 z-10">
                          <tr>
                            {['Column','Non-null','Missing %','Min','Max','Distinct','Most Frequent'].map(h => (
                              <th key={h} className="px-3 py-2 text-left font-semibold text-green-700 dark:text-green-300 border-b border-green-200 dark:border-green-800 whitespace-nowrap">{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {dateCols.map((col) => {
                            const missingPct = col.total_count > 0 ? ((col.missing_count / col.total_count) * 100).toFixed(2) : '0.00';
                            const nonNull = col.total_count - col.missing_count;
                            return (
                              <tr key={col.column_name} className="border-b border-green-100 dark:border-green-900 hover:bg-green-50/50 dark:hover:bg-green-900/20">
                                <td className="px-3 py-1.5 font-medium text-gray-900 dark:text-gray-100 max-w-[120px] truncate whitespace-nowrap" title={col.column_name}>{col.column_name}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{nonNull.toLocaleString()}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{missingPct}%</td>
                                <td className="px-3 py-1.5 text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.date_min || '-'}</td>
                                <td className="px-3 py-1.5 text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.date_max || '-'}</td>
                                <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.unique_count.toLocaleString()}</td>
                                <td className="px-3 py-1.5 text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.most_frequent_date || '-'}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {numericalCols.length === 0 && categoricalCols.length === 0 && dateCols.length === 0 && (
                  <p className="text-sm text-gray-500 dark:text-gray-400 italic">No column statistics available.</p>
                )}
              </div>
            );
          })() : (
            <div className="text-center py-8 text-gray-500 dark:text-gray-400">
              <BarChart3 className="h-12 w-12 mx-auto mb-3 opacity-50" />
              <p>No EDA data available</p>
              <p className="text-sm mt-1">Upload a dataset to see EDA statistics</p>
            </div>
          )}
        </div>
      );
    };

    // ── EDA Comparison sub-tab ────────────────────────────────────────────────
    // Reuses the same compare-column-stats data as the "Compare Changes" modal.
    // Field names match the backend response exactly (same as ModelBuilder modal).
    const formatChangePct = (value: any): string => {
      if (typeof value === 'number' && Number.isFinite(value)) {
        return `${value > 0 ? '+' : ''}${value.toFixed(1)}%`;
      }
      return 'N/A';
    };

    const renderEDAComparison = () => {
      if (isLoadingEdaComparison) {
        return (
          <div className="flex items-center justify-center p-8">
            <div className="flex flex-col items-center space-y-3">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
              <p className="text-sm text-gray-500 dark:text-gray-400">Loading comparison…</p>
            </div>
          </div>
        );
      }

      if (edaComparisonError) {
        return (
          <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
            <div className="flex items-center space-x-2">
              <AlertTriangle className="h-5 w-5 text-red-500" />
              <p className="text-sm text-red-700 dark:text-red-300">{edaComparisonError}</p>
            </div>
          </div>
        );
      }

      if (!edaComparisonData) {
        return (
          <div className="text-center py-8 text-gray-500 dark:text-gray-400">
            <BarChart3 className="h-12 w-12 mx-auto mb-3 opacity-50" />
            <p>No comparison data yet</p>
            <p className="text-sm mt-1">Remove duplicates to see EDA comparison</p>
          </div>
        );
      }

      const cd = edaComparisonData;

      // Detect the failure mode where the latest treatment reduced the processed dataset to 0 rows
      // (e.g. a dropna on a high-missing column before that column is itself dropped). In that
      // case every statistic would render as 0/– which is confusing; surface a clear warning
      // instead so the user understands the Original EDA is still valid and the last treatment
      // needs review.
      const processedRows = cd?.processed_shape?.rows ?? 0;
      const originalRows = cd?.original_shape?.rows ?? 0;
      const isProcessedEmpty = processedRows === 0 && originalRows > 0;

      return (
        <div className="space-y-4">
          {/* View Data scope filter — same options as Original EDA */}
          <div className="flex items-center space-x-3">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">View Data:</label>
            <select
              value={edaComparisonScope}
              onChange={(e) => setEdaComparisonScope(e.target.value as 'entire' | 'train' | 'test' | 'validation')}
              className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="entire">Full Data (Entire)</option>
              <option value="train">Train</option>
              <option value="test">Test</option>
              <option value="validation">Validation</option>
            </select>
            {isLoadingEdaComparison && (
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-500" />
            )}
            {cd?.processed_shape?.rows !== undefined && !isLoadingEdaComparison && (
              <span className="text-xs text-gray-500 dark:text-gray-400">
                ({cd.processed_shape.rows.toLocaleString()} rows)
              </span>
            )}
          </div>

          {/* Warning banner: treatment emptied the dataset */}
          {isProcessedEmpty && (
            <div className="p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-300 dark:border-amber-700 rounded-lg">
              <div className="flex items-start space-x-2">
                <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
                <div className="text-sm text-amber-800 dark:text-amber-200">
                  <div className="font-semibold mb-1">Processed dataset is empty for this scope.</div>
                  <div className="text-xs leading-relaxed">
                    The last treatment removed all {originalRows.toLocaleString()} rows from the{' '}
                    <span className="font-medium">{edaComparisonScope === 'entire' ? 'full dataset' : edaComparisonScope}</span>{' '}
                    view, so summary statistics cannot be computed (all values below will read as 0 or N/A).
                    This usually happens when a <code className="px-1 py-0.5 bg-amber-100 dark:bg-amber-800/40 rounded">dropna</code>{' '}
                    step runs on a column that is almost entirely missing before that column is dropped.
                    Please review the last treatment step — the <span className="font-medium">Original EDA</span> tab still shows the unmodified baseline.
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Toggle: Updated EDA vs Change Heatmap */}
          <div className="flex items-center space-x-2 bg-gray-100 dark:bg-gray-800 rounded-lg p-1 w-fit">
            <button
              type="button"
              onClick={() => setEdaComparisonSubView('updated')}
              className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                edaComparisonSubView === 'updated'
                  ? 'bg-white dark:bg-gray-700 text-blue-600 dark:text-blue-400 shadow-sm'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
              }`}
            >
              Updated EDA
            </button>
            <button
              type="button"
              onClick={() => setEdaComparisonSubView('heatmap')}
              className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                edaComparisonSubView === 'heatmap'
                  ? 'bg-white dark:bg-gray-700 text-blue-600 dark:text-blue-400 shadow-sm'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
              }`}
            >
              Change Heatmap
            </button>
          </div>

          {edaComparisonSubView === 'updated' ? (
            /* Updated EDA View */
            <div className="space-y-4">
              {(() => {
                const fmt = (v?: number | null) => (v === null || v === undefined ? '-' : v.toFixed(2));

                const downloadTableAsCSV = (rows: Record<string, any>[], filename: string) => {
                  if (rows.length === 0) return;
                  const headers = Object.keys(rows[0]);
                  const csv = [
                    headers.join(','),
                    ...rows.map(row => headers.map(h => {
                      const val = row[h];
                      const str = val === null || val === undefined ? '' : String(val);
                      return str.includes(',') || str.includes('"') || str.includes('\n') ? `"${str.replace(/"/g, '""')}"` : str;
                    }).join(','))
                  ].join('\n');
                  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url; a.download = filename; a.click();
                  URL.revokeObjectURL(url);
                };

                // Build column info from changes data
                const processedCols = cd.changes
                  .filter((c: any) => c.status !== 'removed')
                  .map((change: any) => ({
                    column_name: change.column_name,
                    column_type: change.column_type || change.processed_type || change.original_type,
                    status: change.status === 'added' ? 'New' : change.status === 'removed' ? 'Removed' : 'Existing',
                    total_count: cd.processed_shape.rows,
                    missing_count: change.changes?.missing?.processed ?? 0,
                    unique_count: change.changes?.unique?.processed ?? 0,
                    min_value: change.changes?.min?.processed ?? null,
                    max_value: change.changes?.max?.processed ?? null,
                    mean: change.changes?.mean?.processed ?? null,
                    median: change.changes?.median?.processed ?? null,
                    mode: change.changes?.mode_str?.processed ?? (change.changes?.mode?.processed != null ? String(change.changes.mode.processed) : null),
                    standard_deviation: change.changes?.std?.processed ?? null,
                    variance: change.changes?.var?.processed ?? null,
                    skewness: change.changes?.skewness?.processed ?? null,
                    data_type: change.processed_type || change.original_type || 'unknown',
                    // Percentiles
                    percentile_1: change.changes?.p1?.processed ?? null,
                    percentile_5: change.changes?.p5?.processed ?? null,
                    percentile_25: change.changes?.p25?.processed ?? null,
                    percentile_75: change.changes?.p75?.processed ?? null,
                    percentile_95: change.changes?.p95?.processed ?? null,
                    percentile_99: change.changes?.p99?.processed ?? null,
                    // Date fields
                    date_min: change.changes?.date_min?.processed ?? null,
                    date_max: change.changes?.date_max?.processed ?? null,
                    most_frequent_date: change.changes?.most_frequent_date?.processed ?? null,
                    // Categorical fields
                    top_category_pct: change.changes?.top_category_pct?.processed ?? null,
                    lowest_category_pct: change.changes?.lowest_category_pct?.processed ?? null,
                  }));

                // Helper to determine column type (same logic as Original EDA)
                const getColType = (col: any): 'Numerical' | 'Categorical' | 'Date' => {
                  const validTypes = ['Numerical', 'Categorical', 'Date'];
                  // Use column_type if it's a valid type
                  if (col.column_type && validTypes.includes(col.column_type)) {
                    return col.column_type as 'Numerical' | 'Categorical' | 'Date';
                  }
                  // Otherwise infer from data_type
                  if (col.data_type) {
                    const dt = col.data_type.toLowerCase();
                    if (dt.includes('date') || dt.includes('time')) return 'Date';
                    if (['int64', 'float64', 'int32', 'float32', 'number'].some(t => dt.includes(t))) return 'Numerical';
                  }
                  return 'Categorical';
                };

                const numericalCols = processedCols.filter((c: any) => getColType(c) === 'Numerical');
                const dateCols = processedCols.filter((c: any) => getColType(c) === 'Date');
                const categoricalCols = processedCols.filter((c: any) => getColType(c) === 'Categorical');

                return (
                  <>
                    {/* Numerical Variables */}
                    {numericalCols.length > 0 && (
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center space-x-2">
                            <Hash className="h-4 w-4 text-blue-500" />
                            <h5 className="text-sm font-medium text-gray-800 dark:text-gray-200">
                              Numerical Variables ({numericalCols.length})
                            </h5>
                          </div>
                          <button
                            onClick={() => {
                              const rows = numericalCols.map((col: any) => ({
                                column_name: col.column_name,
                                total_obs: col.total_count,
                                missing_count: col.missing_count,
                                missing_pct: `${col.total_count > 0 ? ((col.missing_count / col.total_count) * 100).toFixed(2) : '0.00'}%`,
                                distinct: col.unique_count,
                                min: col.min_value ?? '',
                                max: col.max_value ?? '',
                                mean: col.mean ?? '',
                                median: col.median ?? '',
                                mode: col.mode ?? '',
                                p1: col.percentile_1 ?? '',
                                p5: col.percentile_5 ?? '',
                                p25: col.percentile_25 ?? '',
                                p75: col.percentile_75 ?? '',
                                p95: col.percentile_95 ?? '',
                                p99: col.percentile_99 ?? '',
                                variance: col.variance ?? '',
                                std_dev: col.standard_deviation ?? '',
                                skewness: col.skewness ?? '',
                              }));
                              downloadTableAsCSV(rows, `updated_numerical_eda_${datasetId || 'dataset'}.csv`);
                            }}
                            className="inline-flex items-center space-x-1.5 px-2.5 py-1 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] text-xs font-medium rounded-md hover:bg-blue-700 dark:hover:bg-[#333380] transition-colors"
                          >
                            <Download className="h-3 w-3" />
                            <span>Download CSV</span>
                          </button>
                        </div>
                        <div className="max-h-56 overflow-y-auto overflow-x-auto border border-blue-200 dark:border-blue-800 rounded-lg bg-white dark:bg-gray-800">
                          <table className="min-w-[1600px] w-full text-xs border-collapse">
                            <thead className="bg-blue-50 dark:bg-gray-800 sticky top-0 z-10">
                              <tr>
                                {['Column','Total Obs','Missing #','Missing %','Distinct','Min','Max','Mean','Median','Mode','P1','P5','P25','P75','P95','P99','Variance','Std Dev','Skewness'].map(h => (
                                  <th key={h} className="px-3 py-2 text-left font-semibold text-blue-700 dark:text-blue-300 border-b border-blue-200 dark:border-blue-800 whitespace-nowrap">{h}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {numericalCols.map((col: any) => {
                                const missingPct = col.total_count > 0 ? ((col.missing_count / col.total_count) * 100).toFixed(2) : '0.00';
                                return (
                                  <tr key={col.column_name} className="border-b border-blue-100 dark:border-blue-900 hover:bg-blue-50/50 dark:hover:bg-blue-900/20">
                                    <td className="px-3 py-1.5 font-medium text-gray-900 dark:text-gray-100 max-w-[120px] truncate whitespace-nowrap" title={col.column_name}>{col.column_name}</td>
                                    <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.total_count.toLocaleString()}</td>
                                    <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.missing_count.toLocaleString()}</td>
                                    <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{missingPct}%</td>
                                    <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.unique_count.toLocaleString()}</td>
                                    <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.min_value)}</td>
                                    <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.max_value)}</td>
                                    <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.mean)}</td>
                                    <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.median)}</td>
                                    <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.mode !== null && col.mode !== undefined ? String(col.mode) : '-'}</td>
                                    <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.percentile_1)}</td>
                                    <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.percentile_5)}</td>
                                    <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.percentile_25)}</td>
                                    <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.percentile_75)}</td>
                                    <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.percentile_95)}</td>
                                    <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.percentile_99)}</td>
                                    <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.variance)}</td>
                                    <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.standard_deviation)}</td>
                                    <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(col.skewness)}</td>
                                  </tr>
                                );
                              })}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      )}

                    {/* Categorical Variables */}
                    {categoricalCols.length > 0 && (
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center space-x-2">
                            <Activity className="h-4 w-4 text-purple-500" />
                            <h5 className="text-sm font-medium text-gray-800 dark:text-gray-200">
                              Categorical Variables ({categoricalCols.length})
                            </h5>
                          </div>
                          <button
                            onClick={() => {
                              const rows = categoricalCols.map((col: any) => ({
                                column_name: col.column_name,
                                total_obs: col.total_count,
                                missing_count: col.missing_count,
                                missing_pct: `${col.total_count > 0 ? ((col.missing_count / col.total_count) * 100).toFixed(2) : '0.00'}%`,
                                distinct: col.unique_count,
                                mode: col.mode ?? '',
                                top_category_pct: col.top_category_pct != null ? `${col.top_category_pct.toFixed(2)}%` : '',
                                lowest_category_pct: col.lowest_category_pct != null ? `${col.lowest_category_pct.toFixed(2)}%` : '',
                              }));
                              downloadTableAsCSV(rows, `updated_categorical_eda_${datasetId || 'dataset'}.csv`);
                            }}
                            className="inline-flex items-center space-x-1.5 px-2.5 py-1 bg-purple-600 dark:bg-[#3a2966] text-white dark:text-[#ddccff] text-xs font-medium rounded-md hover:bg-purple-700 transition-colors"
                          >
                            <Download className="h-3 w-3" />
                            <span>Download CSV</span>
                          </button>
                        </div>
                        <div className="max-h-56 overflow-y-auto overflow-x-auto border border-purple-200 dark:border-purple-800 rounded-lg bg-white dark:bg-gray-800">
                          <table className="min-w-[800px] w-full text-xs border-collapse">
                            <thead className="bg-purple-50 dark:bg-gray-800 sticky top-0 z-10">
                              <tr>
                                {['Column','Total Obs','Missing #','Missing %','Distinct','Mode','Top Category %','Lowest Category %'].map(h => (
                                  <th key={h} className="px-3 py-2 text-left font-semibold text-purple-700 dark:text-purple-300 border-b border-purple-200 dark:border-purple-800 whitespace-nowrap">{h}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {categoricalCols.map((col: any) => {
                                const missingPct = col.total_count > 0 ? ((col.missing_count / col.total_count) * 100).toFixed(2) : '0.00';
                                return (
                                  <tr key={col.column_name} className="border-b border-purple-100 dark:border-purple-900 hover:bg-purple-50/50 dark:hover:bg-purple-900/20">
                                    <td className="px-3 py-1.5 font-medium text-gray-900 dark:text-gray-100 max-w-[120px] truncate whitespace-nowrap" title={col.column_name}>{col.column_name}</td>
                                    <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.total_count.toLocaleString()}</td>
                                    <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.missing_count.toLocaleString()}</td>
                                    <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{missingPct}%</td>
                                    <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.unique_count.toLocaleString()}</td>
                                    <td className="px-3 py-1.5 text-gray-700 dark:text-gray-300 max-w-[150px] truncate whitespace-nowrap" title={col.mode !== null && col.mode !== undefined ? String(col.mode) : ''}>
                                      {col.mode !== null && col.mode !== undefined ? String(col.mode) : '-'}
                                    </td>
                                    <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.top_category_pct !== null && col.top_category_pct !== undefined ? `${col.top_category_pct.toFixed(2)}%` : '-'}</td>
                                    <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.lowest_category_pct !== null && col.lowest_category_pct !== undefined ? `${col.lowest_category_pct.toFixed(2)}%` : '-'}</td>
                                  </tr>
                                );
                              })}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      )}

                    {/* Date Variables */}
                    {dateCols.length > 0 && (
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center space-x-2">
                            <Calendar className="h-4 w-4 text-green-500" />
                            <h5 className="text-sm font-medium text-gray-800 dark:text-gray-200">
                              Date Variables ({dateCols.length})
                            </h5>
                          </div>
                          <button
                            onClick={() => {
                              const rows = dateCols.map((col: any) => ({
                                column_name: col.column_name,
                                non_null: col.total_count - col.missing_count,
                                missing_pct: `${col.total_count > 0 ? ((col.missing_count / col.total_count) * 100).toFixed(2) : '0.00'}%`,
                                min: col.date_min ?? '',
                                max: col.date_max ?? '',
                                distinct: col.unique_count,
                                most_frequent: col.most_frequent_date ?? '',
                              }));
                              downloadTableAsCSV(rows, `updated_date_eda_${datasetId || 'dataset'}.csv`);
                            }}
                            className="inline-flex items-center space-x-1.5 px-2.5 py-1 bg-green-600 dark:bg-[#1a3a29] text-white dark:text-[#ccffdd] text-xs font-medium rounded-md hover:bg-green-700 transition-colors"
                          >
                            <Download className="h-3 w-3" />
                            <span>Download CSV</span>
                          </button>
                        </div>
                        <div className="max-h-56 overflow-y-auto overflow-x-auto border border-green-200 dark:border-green-800 rounded-lg bg-white dark:bg-gray-800">
                          <table className="min-w-[700px] w-full text-xs border-collapse">
                            <thead className="bg-green-50 dark:bg-gray-800 sticky top-0 z-10">
                              <tr>
                                {['Column','Non-null','Missing %','Min','Max','Distinct','Most Frequent'].map(h => (
                                  <th key={h} className="px-3 py-2 text-left font-semibold text-green-700 dark:text-green-300 border-b border-green-200 dark:border-green-800 whitespace-nowrap">{h}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {dateCols.map((col: any) => {
                                const missingPct = col.total_count > 0 ? ((col.missing_count / col.total_count) * 100).toFixed(2) : '0.00';
                                const nonNull = col.total_count - col.missing_count;
                                return (
                                  <tr key={col.column_name} className="border-b border-green-100 dark:border-green-900 hover:bg-green-50/50 dark:hover:bg-green-900/20">
                                    <td className="px-3 py-1.5 font-medium text-gray-900 dark:text-gray-100 max-w-[120px] truncate whitespace-nowrap" title={col.column_name}>{col.column_name}</td>
                                    <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{nonNull.toLocaleString()}</td>
                                    <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{missingPct}%</td>
                                    <td className="px-3 py-1.5 text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.date_min || '-'}</td>
                                    <td className="px-3 py-1.5 text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.date_max || '-'}</td>
                                    <td className="px-3 py-1.5 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.unique_count.toLocaleString()}</td>
                                    <td className="px-3 py-1.5 text-gray-700 dark:text-gray-300 whitespace-nowrap">{col.most_frequent_date || '-'}</td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {numericalCols.length === 0 && categoricalCols.length === 0 && dateCols.length === 0 && (
                      <p className="text-sm text-gray-500 dark:text-gray-400 italic">No column statistics available.</p>
                    )}
                  </>
                );
              })()}
            </div>
          ) : (
            /* Change Heatmap View */
            <div className="space-y-4">
              {/* Summary cards — only for Heatmap */}
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-white dark:bg-[#0f1428] border border-gray-200 dark:border-gray-800 rounded-lg p-3">
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Rows</div>
                  <div className="text-base font-bold text-gray-900 dark:text-white">
                    {cd.original_shape.rows.toLocaleString()} → {cd.processed_shape.rows.toLocaleString()}
                  </div>
                  <div className={`text-xs mt-1 ${cd.summary.rows_change <= 0 ? 'text-red-600' : 'text-green-600'}`}>
                    {cd.summary.rows_change >= 0 ? '+' : ''}{cd.summary.rows_change.toLocaleString()}
                    {' '}({cd.summary.rows_change_pct != null ? `${cd.summary.rows_change_pct.toFixed(1)}%` : 'N/A'})
                  </div>
                </div>
                <div className="bg-white dark:bg-[#0f1428] border border-gray-200 dark:border-gray-800 rounded-lg p-3">
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Columns</div>
                  <div className="text-base font-bold text-gray-900 dark:text-white">
                    {cd.original_shape.columns} → {cd.processed_shape.columns}
                  </div>
                  <div className={`text-xs mt-1 ${cd.summary.total_columns_processed - cd.summary.total_columns_original >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {cd.summary.total_columns_processed - cd.summary.total_columns_original >= 0 ? '+' : ''}
                    {cd.summary.total_columns_processed - cd.summary.total_columns_original}
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between mb-2">
                <h4 className="text-sm font-semibold text-gray-800 dark:text-gray-200 flex items-center gap-1">
                  <BarChart3 className="h-4 w-4 text-orange-500" />
                  Change Heatmap
                </h4>
                <button
                  onClick={() => {
                    const metrics = ['missing','unique','mean','median','mode','std','var','min','p5','p25','p50','p75','p95','p99','max'];
                    const headers = ['Column','Status',...metrics.flatMap(m => [`${m}_original`,`${m}_processed`,`${m}_change_pct`])];
                    const csvRows = cd.changes.map((ch: any) => {
                      const row: Record<string, any> = { Column: ch.column_name, Status: ch.status };
                      metrics.forEach(m => {
                        const d = ch.changes?.[m];
                        row[`${m}_original`] = d?.original ?? '';
                        row[`${m}_processed`] = d?.processed ?? '';
                        row[`${m}_change_pct`] = d?.change_pct != null ? `${d.change_pct.toFixed(2)}%` : '';
                      });
                      return row;
                    });
                    if (csvRows.length === 0) return;
                    const csv = [
                      headers.join(','),
                      ...csvRows.map(row => headers.map(h => {
                        const val = row[h];
                        const str = val === null || val === undefined ? '' : String(val);
                        return str.includes(',') || str.includes('"') || str.includes('\n') ? `"${str.replace(/"/g, '""')}"` : str;
                      }).join(','))
                    ].join('\n');
                    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url; a.download = `change_heatmap_${datasetId || 'dataset'}.csv`; a.click();
                    URL.revokeObjectURL(url);
                  }}
                  className="inline-flex items-center space-x-1.5 px-2.5 py-1 bg-orange-600 dark:bg-[#663a29] text-white dark:text-[#ffddcc] text-xs font-medium rounded-md hover:bg-orange-700 transition-colors"
                >
                  <Download className="h-3 w-3" />
                  <span>Download CSV</span>
                </button>
              </div>
              <div className="overflow-x-auto overflow-y-auto max-h-96 border border-blue-200 dark:border-[#2b2f55] rounded-lg">
              <table className="w-full text-xs border-collapse" style={{ minWidth: '1400px' }}>
                <thead className="sticky top-0 z-20">
                  <tr className="bg-gray-100 dark:bg-[#1a1f3a] text-gray-900 dark:text-gray-200">
                    {['Column','Status','Missing','Unique','Mean','Median','Mode','Std Dev','Variance','Min','p5%','p25%','p50%','p75%','p95%','p99%','Max'].map(h => (
                      <th key={h} className="px-2 py-2 border border-gray-300 dark:border-[#2b2f55] text-center font-medium whitespace-nowrap" style={{ minWidth: h === 'Column' ? '130px' : '90px' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {cd.changes.map((change: any, idx: number) => (
                    <tr key={idx} className="hover:bg-gray-50 dark:hover:bg-[#1b2142] text-gray-900 dark:text-gray-200">
                      <td className="px-2 py-1.5 border border-gray-300 dark:border-[#2b2f55] font-medium sticky left-0 bg-white dark:bg-[#0f1428] z-10 whitespace-nowrap" style={{ minWidth: '130px' }}>
                        {change.column_name}
                      </td>
                      <td className={`px-2 py-1.5 border border-gray-300 dark:border-[#2b2f55] text-center ${getStatusColor(change.status)}`}>
                        <span className="px-1.5 py-0.5 rounded text-xs font-medium">
                          {change.status === 'added' && '✚ Added'}
                          {change.status === 'removed' && '✖ Removed'}
                          {change.status === 'modified' && '⟳ Modified'}
                          {change.status === 'unchanged' && '○ Same'}
                        </span>
                      </td>
                      {/* Missing */}
                      <td className={`px-2 py-1.5 border border-gray-300 dark:border-[#2b2f55] text-center ${getHeatmapColor(change.changes?.missing)}`} style={{ minWidth: '90px' }}>
                        {change.changes?.missing !== undefined ? (
                          <div className="font-medium">
                            <div>{change.changes.missing.processed ?? change.changes.missing.original ?? 0}</div>
                            {change.changes.missing.change !== 0 && (
                              <div className={`text-[10px] ${change.changes.missing.change_pct > 0 ? 'text-green-600' : 'text-red-600'}`}>({formatChangePct(change.changes.missing.change_pct)})</div>
                            )}
                          </div>
                        ) : <span className="text-gray-500 dark:text-gray-400">N/A</span>}
                      </td>
                      {/* Unique */}
                      <td className={`px-2 py-1.5 border border-gray-300 dark:border-[#2b2f55] text-center ${getHeatmapColor(change.changes?.unique)}`} style={{ minWidth: '90px' }}>
                        {change.changes?.unique !== undefined ? (
                          <div className="font-medium">
                            <div>{change.changes.unique.processed ?? change.changes.unique.original ?? 0}</div>
                            {change.changes.unique.change !== 0 && (
                              <div className={`text-[10px] ${change.changes.unique.change_pct > 0 ? 'text-green-600' : 'text-red-600'}`}>({formatChangePct(change.changes.unique.change_pct)})</div>
                            )}
                          </div>
                        ) : <span className="text-gray-500 dark:text-gray-400">N/A</span>}
                      </td>
                      {/* Mean */}
                      <td className={`px-2 py-1.5 border border-gray-300 dark:border-[#2b2f55] text-center ${getHeatmapColor(change.changes?.mean)}`} style={{ minWidth: '90px' }}>
                        {change.changes?.mean !== undefined && change.changes.mean.processed !== null ? (
                          <div className="font-medium">
                            <div>{change.changes.mean.processed?.toFixed(2)}</div>
                            {change.changes.mean.change !== 0 && (
                              <div className={`text-[10px] ${change.changes.mean.change_pct > 0 ? 'text-green-600' : 'text-red-600'}`}>({formatChangePct(change.changes.mean.change_pct)})</div>
                            )}
                          </div>
                        ) : <span className="text-gray-500 dark:text-gray-400">N/A</span>}
                      </td>
                      {/* Median */}
                      <td className={`px-2 py-1.5 border border-gray-300 dark:border-[#2b2f55] text-center ${getHeatmapColor(change.changes?.median)}`} style={{ minWidth: '90px' }}>
                        {change.changes?.median !== undefined && change.changes.median.processed !== null ? (
                          <div className="font-medium">
                            <div>{change.changes.median.processed?.toFixed(2)}</div>
                            {change.changes.median.change !== 0 && (
                              <div className={`text-[10px] ${change.changes.median.change_pct > 0 ? 'text-green-600' : 'text-red-600'}`}>({formatChangePct(change.changes.median.change_pct)})</div>
                            )}
                          </div>
                        ) : <span className="text-gray-500 dark:text-gray-400">N/A</span>}
                      </td>
                      {/* Mode */}
                      <td className={`px-2 py-1.5 border border-gray-300 dark:border-[#2b2f55] text-center ${getHeatmapColor(change.changes?.mode)}`} style={{ minWidth: '90px' }}>
                        {change.changes?.mode !== undefined && change.changes.mode.processed !== null ? (
                          <div className="font-medium">
                            <div>{typeof change.changes.mode.processed === 'number' ? change.changes.mode.processed?.toFixed(2) : change.changes.mode.processed}</div>
                            {change.changes.mode.change !== 0 && (
                              <div className={`text-[10px] ${change.changes.mode.change_pct > 0 ? 'text-green-600' : 'text-red-600'}`}>({formatChangePct(change.changes.mode.change_pct)})</div>
                            )}
                          </div>
                        ) : <span className="text-gray-500 dark:text-gray-400">N/A</span>}
                      </td>
                      {/* Std Dev */}
                      <td className={`px-2 py-1.5 border border-gray-300 dark:border-[#2b2f55] text-center ${getHeatmapColor(change.changes?.std)}`} style={{ minWidth: '90px' }}>
                        {change.changes?.std !== undefined && change.changes.std.processed !== null ? (
                          <div className="font-medium">
                            <div>{change.changes.std.processed?.toFixed(2)}</div>
                            {change.changes.std.change !== 0 && (
                              <div className={`text-[10px] ${change.changes.std.change_pct > 0 ? 'text-green-600' : 'text-red-600'}`}>({formatChangePct(change.changes.std.change_pct)})</div>
                            )}
                          </div>
                        ) : <span className="text-gray-500 dark:text-gray-400">N/A</span>}
                      </td>
                      {/* Variance */}
                      <td className={`px-2 py-1.5 border border-gray-300 dark:border-[#2b2f55] text-center ${getHeatmapColor(change.changes?.var)}`} style={{ minWidth: '90px' }}>
                        {change.changes?.var !== undefined && change.changes.var.processed !== null ? (
                          <div className="font-medium">
                            <div>{change.changes.var.processed?.toFixed(2)}</div>
                            {change.changes.var.change !== 0 && (
                              <div className={`text-[10px] ${change.changes.var.change_pct > 0 ? 'text-green-600' : 'text-red-600'}`}>({formatChangePct(change.changes.var.change_pct)})</div>
                            )}
                          </div>
                        ) : <span className="text-gray-500 dark:text-gray-400">N/A</span>}
                      </td>
                      {/* Min */}
                      <td className={`px-2 py-1.5 border border-gray-300 dark:border-[#2b2f55] text-center ${getHeatmapColor(change.changes?.min)}`} style={{ minWidth: '90px' }}>
                        {change.changes?.min !== undefined && change.changes.min.processed !== null ? (
                          <div className="font-medium">
                            <div>{change.changes.min.processed?.toFixed(2)}</div>
                            {change.changes.min.change !== 0 && (
                              <div className={`text-[10px] ${change.changes.min.change_pct > 0 ? 'text-green-600' : 'text-red-600'}`}>({formatChangePct(change.changes.min.change_pct)})</div>
                            )}
                          </div>
                        ) : <span className="text-gray-500 dark:text-gray-400">N/A</span>}
                      </td>
                      {/* p5% */}
                      <td className={`px-2 py-1.5 border border-gray-300 dark:border-[#2b2f55] text-center ${getHeatmapColor(change.changes?.p5)}`} style={{ minWidth: '90px' }}>
                        {change.changes?.p5 !== undefined && change.changes.p5.processed !== null ? (
                          <div className="font-medium">
                            <div>{change.changes.p5.processed?.toFixed(2)}</div>
                            {change.changes.p5.change !== 0 && (
                              <div className={`text-[10px] ${change.changes.p5.change_pct > 0 ? 'text-green-600' : 'text-red-600'}`}>({formatChangePct(change.changes.p5.change_pct)})</div>
                            )}
                          </div>
                        ) : <span className="text-gray-500 dark:text-gray-400">N/A</span>}
                      </td>
                      {/* p25% */}
                      <td className={`px-2 py-1.5 border border-gray-300 dark:border-[#2b2f55] text-center ${getHeatmapColor(change.changes?.p25)}`} style={{ minWidth: '90px' }}>
                        {change.changes?.p25 !== undefined && change.changes.p25.processed !== null ? (
                          <div className="font-medium">
                            <div>{change.changes.p25.processed?.toFixed(2)}</div>
                            {change.changes.p25.change !== 0 && (
                              <div className={`text-[10px] ${change.changes.p25.change_pct > 0 ? 'text-green-600' : 'text-red-600'}`}>({formatChangePct(change.changes.p25.change_pct)})</div>
                            )}
                          </div>
                        ) : <span className="text-gray-500 dark:text-gray-400">N/A</span>}
                      </td>
                      {/* p50% */}
                      <td className={`px-2 py-1.5 border border-gray-300 dark:border-[#2b2f55] text-center ${getHeatmapColor(change.changes?.p50)}`} style={{ minWidth: '90px' }}>
                        {change.changes?.p50 !== undefined && change.changes.p50.processed !== null ? (
                          <div className="font-medium">
                            <div>{change.changes.p50.processed?.toFixed(2)}</div>
                            {change.changes.p50.change !== 0 && (
                              <div className={`text-[10px] ${change.changes.p50.change_pct > 0 ? 'text-green-600' : 'text-red-600'}`}>({formatChangePct(change.changes.p50.change_pct)})</div>
                            )}
                          </div>
                        ) : <span className="text-gray-500 dark:text-gray-400">N/A</span>}
                      </td>
                      {/* p75% */}
                      <td className={`px-2 py-1.5 border border-gray-300 dark:border-[#2b2f55] text-center ${getHeatmapColor(change.changes?.p75)}`} style={{ minWidth: '90px' }}>
                        {change.changes?.p75 !== undefined && change.changes.p75.processed !== null ? (
                          <div className="font-medium">
                            <div>{change.changes.p75.processed?.toFixed(2)}</div>
                            {change.changes.p75.change !== 0 && (
                              <div className={`text-[10px] ${change.changes.p75.change_pct > 0 ? 'text-green-600' : 'text-red-600'}`}>({formatChangePct(change.changes.p75.change_pct)})</div>
                            )}
                          </div>
                        ) : <span className="text-gray-500 dark:text-gray-400">N/A</span>}
                      </td>
                      {/* p95% */}
                      <td className={`px-2 py-1.5 border border-gray-300 dark:border-[#2b2f55] text-center ${getHeatmapColor(change.changes?.p95)}`} style={{ minWidth: '90px' }}>
                        {change.changes?.p95 !== undefined && change.changes.p95.processed !== null ? (
                          <div className="font-medium">
                            <div>{change.changes.p95.processed?.toFixed(2)}</div>
                            {change.changes.p95.change !== 0 && (
                              <div className={`text-[10px] ${change.changes.p95.change_pct > 0 ? 'text-green-600' : 'text-red-600'}`}>({formatChangePct(change.changes.p95.change_pct)})</div>
                            )}
                          </div>
                        ) : <span className="text-gray-500 dark:text-gray-400">N/A</span>}
                      </td>
                      {/* p99% */}
                      <td className={`px-2 py-1.5 border border-gray-300 dark:border-[#2b2f55] text-center ${getHeatmapColor(change.changes?.p99)}`} style={{ minWidth: '90px' }}>
                        {change.changes?.p99 !== undefined && change.changes.p99.processed !== null ? (
                          <div className="font-medium">
                            <div>{change.changes.p99.processed?.toFixed(2)}</div>
                            {change.changes.p99.change !== 0 && (
                              <div className={`text-[10px] ${change.changes.p99.change_pct > 0 ? 'text-green-600' : 'text-red-600'}`}>({formatChangePct(change.changes.p99.change_pct)})</div>
                            )}
                          </div>
                        ) : <span className="text-gray-500 dark:text-gray-400">N/A</span>}
                      </td>
                      {/* Max */}
                      <td className={`px-2 py-1.5 border border-gray-300 dark:border-[#2b2f55] text-center ${getHeatmapColor(change.changes?.max)}`} style={{ minWidth: '90px' }}>
                        {change.changes?.max !== undefined && change.changes.max.processed !== null ? (
                          <div className="font-medium">
                            <div>{change.changes.max.processed?.toFixed(2)}</div>
                            {change.changes.max.change !== 0 && (
                              <div className={`text-[10px] ${change.changes.max.change_pct > 0 ? 'text-green-600' : 'text-red-600'}`}>({formatChangePct(change.changes.max.change_pct)})</div>
                            )}
                          </div>
                        ) : <span className="text-gray-500 dark:text-gray-400">N/A</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    );
    };

    // ── Main render ───────────────────────────────────────────────────────────
    return (
      <div className="space-y-4">
        {/* Sub-tab navigation */}
        <div className="flex items-center border-b border-gray-200 dark:border-gray-700">
          <button
            type="button"
            onClick={() => setEdaActiveTab('original')}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              edaActiveTab === 'original'
                ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
            }`}
          >
            Original EDA
          </button>
          {showEDAComparison && (
            <button
              type="button"
              onClick={() => setEdaActiveTab('comparison')}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                edaActiveTab === 'comparison'
                  ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
              }`}
            >
              EDA Comparison
            </button>
          )}
        </div>

        {edaActiveTab === 'original' ? renderOriginalEDA() : renderEDAComparison()}
      </div>
    );
  };

  const renderSegmentationTab = () => {
    const profileSegs = Array.isArray(activeSegmentationResult?.segments)
      ? activeSegmentationResult!.segments
      : [];
    const profilePooled =
      profileSegs.length >= 2 ? perSegmentWoeIvContributions(profileSegs) : [];
    const profileDisplayMetrics = profileSegs.map((s: any, idx: number) => {
      const ivB = Number(s?.iv_contribution ?? 0);
      const wB = Number(s?.woe ?? 0);
      if (Math.abs(ivB) > 1e-12 || Math.abs(wB) > 1e-12) {
        return { woe: wB, iv: ivB };
      }
      const p = profilePooled[idx];
      return { woe: p?.woe ?? 0, iv: p?.iv_contribution ?? 0 };
    });
    const profileIvTotal = profileDisplayMetrics.reduce(
      (a: number, m: { woe: number; iv: number }) => a + m.iv,
      0
    );

    const vr = activeSegmentationResult?.variable_relevance;
    const segKeysVr = Object.keys(vr?.segment_iv || {});
    const segKeysVrDisplayOrder = sortVariableRelevanceSegmentKeys(segKeysVr);
    const vrSortColumn: 'overall' | string =
      variableRelevanceSortBy === 'overall' || segKeysVr.includes(variableRelevanceSortBy)
        ? variableRelevanceSortBy
        : 'overall';
    const getVrIvForSort = (variable: string): number => {
      if (!vr) return 0;
      if (vrSortColumn === 'overall') {
        const v = vr.overall_iv?.[variable];
        return v !== undefined && v !== null && Number.isFinite(Number(v)) ? Number(v) : 0;
      }
      const x = vr.segment_iv?.[vrSortColumn]?.[variable];
      if (x === undefined || x === null) return 0;
      const n = Number(x);
      return Number.isFinite(n) ? n : 0;
    };
    const variableRelevanceVariablesSorted: string[] = vr?.variables?.length
      ? [...vr.variables].sort((a, b) => {
          const diff = getVrIvForSort(b) - getVrIvForSort(a);
          if (diff !== 0) return diff;
          return a.localeCompare(b);
        })
      : [];

    const downloadVariableRelevanceMatrixCsv = () => {
      if (!vr?.variables?.length) return;
      const segNames = sortVariableRelevanceSegmentKeys(Object.keys(vr.segment_iv || {}));
      const csvEscape = (v: unknown) => {
        if (v === null || v === undefined) return '""';
        const s = String(v).replace(/"/g, '""');
        return `"${s}"`;
      };
      const fmtIvCell = (x: unknown) => {
        if (x === undefined || x === null) return '""';
        const n = Number(x);
        if (!Number.isFinite(n)) return '""';
        if (n === 0) return '""';
        return csvEscape(n.toFixed(6));
      };
      const headers = ['Variable', 'Overall IV', ...segNames];
      const lines = [
        headers.map((h) => csvEscape(h)).join(','),
        ...variableRelevanceVariablesSorted.map((variable: string) => {
          const ov = vr.overall_iv?.[variable];
          const ovStr =
            ov === undefined || ov === null || !Number.isFinite(Number(ov))
              ? ''
              : Number(ov).toFixed(6);
          const segCells = segNames.map((sn) => {
            const x = vr.segment_iv?.[sn]?.[variable];
            return fmtIvCell(x);
          });
          return [csvEscape(variable), ovStr ? csvEscape(ovStr) : '""', ...segCells].join(',');
        }),
      ];
      const csv = lines.join('\n');
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      const url = URL.createObjectURL(blob);
      link.href = url;
      link.download = `variable_relevance_matrix_${datasetId || 'dataset'}.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    };

    return (
    <div className="space-y-6">
      {/* Results view toggle row (header text removed) */}
      <div className="flex items-center justify-end gap-2">
        <button
          className={`px-2 py-1 text-xs rounded border ${resultsView==='global'?'bg-white dark:bg-gray-800 border-blue-500 text-blue-700 dark:text-blue-400':'border-gray-200 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-white dark:hover:bg-gray-800'}`}
          onClick={() => setResultsView('global')}
        >Global</button>
        <button
          className={`px-2 py-1 text-xs rounded border ${resultsView==='segmentation'?'bg-white dark:bg-gray-800 border-purple-500 text-purple-700 dark:text-purple-400':'border-gray-200 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-white dark:hover:bg-gray-800'}`}
          onClick={() => setResultsView('segmentation')}
        >Segmentation</button>
        <button
          className={`px-2 py-1 text-xs rounded border ${resultsView==='both'?'bg-white dark:bg-gray-800 border-gray-500 text-gray-800 dark:text-gray-200':'border-gray-200 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-white dark:hover:bg-gray-800'}`}
          onClick={() => setResultsView('both')}
        >Both</button>
      </div>

      {/* Segmentation shown for Segmentation or Both */}
      {(resultsView === 'segmentation' || resultsView === 'both') && (
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
        <h4 className="font-medium text-gray-900 dark:text-gray-100 mb-4">Segmentation Summary</h4>
        {activeSegmentationResult?.success ? (
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-4">
              <div className="text-center p-3 bg-purple-50 dark:bg-purple-900/30 rounded-lg">
                <div className="text-xs text-gray-600 dark:text-gray-400">Method</div>
                <div className="text-lg font-semibold text-purple-700 dark:text-purple-400">{String(activeSegmentationResult.method || activeSegmentationResult.mode || 'N/A').toUpperCase()}</div>
              </div>
              <div className="text-center p-3 bg-blue-50 dark:bg-blue-900/30 rounded-lg">
                <div className="text-xs text-gray-600 dark:text-gray-400">Segments</div>
                <div className="text-lg font-semibold text-blue-700 dark:text-blue-400">{activeSegmentationResult.num_segments}</div>
              </div>
              <div className="text-center p-3 bg-green-50 dark:bg-green-900/30 rounded-lg">
                <div className="text-xs text-gray-600 dark:text-gray-400">Variables used</div>
                <div className="text-sm font-medium text-green-700 dark:text-green-400 truncate" title={activeSegmentationResult.variables_used?.join(', ')}>
                  {activeSegmentationResult.variables_used?.slice(0,3).join(', ')}{activeSegmentationResult.variables_used?.length>3?'…':''}
                </div>
              </div>
            </div>

            {(() => {
              const raw = activeSegmentationResult as Record<string, unknown>;
              const fromList = Array.isArray(raw.promotion_suggestions) ? (raw.promotion_suggestions as any[]) : [];
              const tertiary = raw.tertiary_promotion_suggestion as Record<string, unknown> | null | undefined;
              const items =
                fromList.length > 0
                  ? fromList
                  : tertiary
                    ? [tertiary]
                    : [];
              if (items.length === 0) return null;
              return (
                <div className="space-y-2">
                  {items.map((suggestion: any, idx: number) => {
                    const kind = suggestion.suggestion_type || suggestion.type;
                    const isPromote = kind === 'promote_tertiary';
                    return (
                      <div
                        key={idx}
                        className={`p-3 rounded-lg border text-sm ${
                          isPromote
                            ? 'bg-amber-50 dark:bg-amber-900/25 border-amber-300 dark:border-amber-700 text-amber-900 dark:text-amber-100'
                            : 'bg-amber-50/70 dark:bg-amber-900/15 border-amber-200 dark:border-amber-800 text-amber-900 dark:text-amber-200'
                        }`}
                      >
                        <div className="font-medium text-xs uppercase tracking-wide text-amber-800/80 dark:text-amber-200/90 mb-1">
                          Section 3.4 — splitter guidance
                        </div>
                        <p>{suggestion.message}</p>
                        {suggestion.suggested_variable && (
                          <p className="mt-1 text-xs text-gray-600 dark:text-gray-400">
                            Suggested variable: <strong>{String(suggestion.suggested_variable)}</strong>
                            {suggestion.suggested_p_value != null &&
                              ` (p = ${Number(suggestion.suggested_p_value).toFixed(4)})`}
                          </p>
                        )}
                      </div>
                    );
                  })}
                </div>
              );
            })()}

            {/* NEW: Validation Suite Results & Recommendation Badge */}
            {activeSegmentationResult.validation && (
              <div className="space-y-3">
                {/* Recommendation Badge */}
                <div className="flex items-center justify-between p-3 rounded-lg border" style={{
                  backgroundColor: activeSegmentationResult.validation.recommendation_category === 'strong' 
                    ? 'rgb(240 253 244)' 
                    : activeSegmentationResult.validation.recommendation_category === 'exploratory'
                    ? 'rgb(254 252 232)'
                    : 'rgb(254 242 242)',
                  borderColor: activeSegmentationResult.validation.recommendation_category === 'strong'
                    ? 'rgb(187 247 208)'
                    : activeSegmentationResult.validation.recommendation_category === 'exploratory'
                    ? 'rgb(254 240 138)'
                    : 'rgb(254 202 202)'
                }}>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-bold px-2 py-1 rounded ${
                      activeSegmentationResult.validation.recommendation_category === 'strong'
                        ? 'bg-green-600 text-white'
                        : activeSegmentationResult.validation.recommendation_category === 'exploratory'
                        ? 'bg-yellow-500 text-white'
                        : 'bg-red-500 text-white'
                    }`}>
                      {activeSegmentationResult.validation.recommendation_category?.toUpperCase() || 'N/A'}
                    </span>
                    <span className="text-sm font-medium text-gray-800">
                      Segmentation Quality
                    </span>
                  </div>
                </div>

                {/* Validation Metrics Grid */}
                <div className="grid grid-cols-2 gap-2">
                  <div className="p-2 bg-gray-50 dark:bg-gray-700/50 rounded">
                    <div className="text-xs text-gray-500 dark:text-gray-400">Total IV</div>
                    <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                      {displayTotalIv(
                        activeSegmentationResult.validation.total_iv,
                        activeSegmentationResult.segments
                      )}
                      <span className={`ml-1 text-xs ${
                        activeSegmentationResult.validation.iv_category === 'strong' ? 'text-green-600' :
                        activeSegmentationResult.validation.iv_category === 'moderate' ? 'text-blue-600' :
                        activeSegmentationResult.validation.iv_category === 'suspicious' ? 'text-red-600' :
                        'text-gray-500'
                      }`}>
                        ({activeSegmentationResult.validation.iv_category || 'N/A'})
                      </span>
                    </div>
                  </div>
                  <div className="p-2 bg-gray-50 dark:bg-gray-700/50 rounded">
                    <div className="text-xs text-gray-500 dark:text-gray-400">Chi-Squared</div>
                    <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                      {formatSegmentationChiSquaredPLabel(
                        activeSegmentationResult.validation.chi_squared_p,
                        activeSegmentationResult.validation.chi_squared_significant
                      )}
                      <span className={`ml-1 text-xs ${
                        activeSegmentationResult.validation.chi_squared_significant ? 'text-green-600' : 'text-amber-600'
                      }`}>
                        {activeSegmentationResult.validation.chi_squared_significant ? '✓ Sig.' : '⚠ Not Sig.'}
                      </span>
                    </div>
                  </div>
                  <div className="p-2 bg-gray-50 dark:bg-gray-700/50 rounded">
                    <div className="text-xs text-gray-500 dark:text-gray-400">Cramer's V</div>
                    <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                      {activeSegmentationResult.validation.cramers_v?.toFixed(3) || 'N/A'}
                      <span className={`ml-1 text-xs ${
                        activeSegmentationResult.validation.cramers_v_meaningful ? 'text-green-600' : 'text-amber-600'
                      }`}>
                        {activeSegmentationResult.validation.cramers_v_meaningful ? '✓ Meaningful' : '⚠ Weak'}
                      </span>
                    </div>
                  </div>
                  {activeSegmentationResult.validation.stability && (
                    <div className="p-2 bg-gray-50 dark:bg-gray-700/50 rounded">
                      <div className="text-xs text-gray-500 dark:text-gray-400">Stability</div>
                      <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                        {(activeSegmentationResult.validation.stability.rank_order_preservation_rate * 100).toFixed(1)}%
                        <span className={`ml-1 text-xs ${
                          activeSegmentationResult.validation.stability.rank_order_preservation_rate >= 0.9 ? 'text-green-600' :
                          activeSegmentationResult.validation.stability.rank_order_preservation_rate >= 0.7 ? 'text-amber-600' :
                          'text-red-600'
                        }`}>
                          ({activeSegmentationResult.validation.stability.bootstrap_runs} runs)
                        </span>
                      </div>
                    </div>
                  )}
                </div>

                {/* Segment Flags (warnings) */}
                {activeSegmentationResult.validation.segment_flags && activeSegmentationResult.validation.segment_flags.length > 0 && (
                  <div className="p-2 bg-amber-50 dark:bg-amber-900/20 rounded border border-amber-200 dark:border-amber-800">
                    <div className="text-xs font-medium text-amber-800 dark:text-amber-300 mb-1">Segment Warnings</div>
                    <div className="space-y-1">
                      {activeSegmentationResult.validation.segment_flags.slice(0, 3).map((flag: any, idx: number) => (
                        <div key={idx} className="text-xs text-amber-700 dark:text-amber-400 flex items-center gap-1">
                          <span className={`w-1.5 h-1.5 rounded-full ${flag.severity === 'red' ? 'bg-red-500' : 'bg-amber-500'}`}></span>
                          {flag.segment_name}: {flag.message}
                        </div>
                      ))}
                      {activeSegmentationResult.validation.segment_flags.length > 3 && (
                        <div className="text-xs text-amber-600 dark:text-amber-500">
                          +{activeSegmentationResult.validation.segment_flags.length - 3} more warnings
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Charts: bar (counts) + pie (proportions) - displayed vertically */}
            {/* Support both old viability format and new segments format */}
            {(() => {
              // Prefer `segments` for counts/rates so bars, event-rate line, and Wilson CIs share one index space.
              // (Mixing viability.segment_counts with segment-based CIs caused misaligned series.)
              const segments = activeSegmentationResult.segments || [];
              const hasSegRows = Array.isArray(segments) && segments.length > 0;
              const segmentCounts = hasSegRows
                ? segments.map((s: any) => Number(s.record_count ?? s.size ?? 0) || 0)
                : (activeSegmentationResult.viability?.segment_counts || []).map((n: number) => Number(n) || 0);
              const totalForProp = segmentCounts.reduce((a: number, b: number) => a + b, 0);
              const segmentProportions = hasSegRows
                ? segmentCounts.map((c: number) => (totalForProp > 0 ? c / totalForProp : 0))
                : activeSegmentationResult.viability?.segment_proportions ||
                  [];
              const segmentEventRates = hasSegRows
                ? segments.map((s: any) => segmentEventRateToFraction(s.event_rate))
                : activeSegmentationResult.viability?.segment_event_rates
                  ? activeSegmentationResult.viability.segment_event_rates.map((r: number) => segmentEventRateToFraction(r))
                  : [];
              
              // Calculate population average event rate for reference line
              const totalRecords = segmentCounts.reduce((sum: number, c: number) => sum + c, 0);
              const totalEvents = segmentCounts.reduce((sum: number, c: number, i: number) => {
                const s = segments[i];
                if (s && s.event_count != null && Number.isFinite(Number(s.event_count))) {
                  return sum + Number(s.event_count);
                }
                return sum + Math.round(c * (segmentEventRates[i] ?? 0));
              }, 0);
              const populationAvgEventRate = totalRecords > 0 ? totalEvents / totalRecords : 0;
              
              // Calculate 95% confidence intervals using Wilson score interval
              // Wilson interval: more accurate than normal approximation for proportions
              const z = 1.96; // 95% confidence
              const calculateWilsonCI = (n: number, p: number): { lower: number; upper: number } => {
                if (n === 0) return { lower: 0, upper: 0 };
                const denominator = 1 + z * z / n;
                const center = (p + z * z / (2 * n)) / denominator;
                const halfWidth = (z / denominator) * Math.sqrt(p * (1 - p) / n + z * z / (4 * n * n));
                return {
                  lower: Math.max(0, center - halfWidth),
                  upper: Math.min(1, center + halfWidth)
                };
              };
              
              const confidenceIntervals = segmentCounts.map((count: number, i: number) => {
                const s = segments[i];
                const n = s ? Number(s.record_count ?? s.size ?? 0) || 0 : count;
                const eventRate = s ? segmentEventRateToFraction(s.event_rate) : (segmentEventRates[i] ?? 0);
                return calculateWilsonCI(n, eventRate);
              });
              
              const ciLower = confidenceIntervals.map((ci: any) => ci.lower);
              const ciUpper = confidenceIntervals.map((ci: any) => ci.upper);
              
              // Check for overlapping confidence intervals
              const hasOverlappingCI = (() => {
                for (let i = 0; i < confidenceIntervals.length; i++) {
                  for (let j = i + 1; j < confidenceIntervals.length; j++) {
                    const ci1 = confidenceIntervals[i];
                    const ci2 = confidenceIntervals[j];
                    // Check if intervals overlap
                    if (ci1.lower <= ci2.upper && ci2.lower <= ci1.upper) {
                      return true;
                    }
                  }
                }
                return false;
              })();
              
              const hasChartData = segmentCounts.length > 0;
              
              return hasChartData ? (
                <div className="mt-6 space-y-6">
                  {/* Bar Chart - Segment Sizes */}
                  <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm">
                    <div 
                      className="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
                      onClick={() => setSegmentSizesExpanded(!segmentSizesExpanded)}
                    >
                      <h5 className="font-semibold text-gray-900 dark:text-gray-100">Segment Sizes</h5>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setExpandedChart('sizes');
                          }}
                          className="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
                          title="Expand chart"
                        >
                          <Maximize2 className="w-4 h-4 text-gray-600" />
                        </button>
                        {segmentSizesExpanded ? (
                          <ChevronUp className="w-5 h-5 text-gray-500" />
                        ) : (
                          <ChevronDown className="w-5 h-5 text-gray-500" />
                        )}
                      </div>
                    </div>
                    {segmentSizesExpanded && (
                      <div className="px-4 pb-4" style={{ height: '280px' }}>
                        <Bar
                          data={{
                            labels: segmentCounts.map((_: any, i: number) => `Segment ${i+1}`),
                            datasets: [
                              {
                                type: 'bar' as const,
                                label: 'Total',
                                data: segmentCounts,
                                backgroundColor: [
                                  'rgba(99, 102, 241, 0.8)',
                                  'rgba(59, 130, 246, 0.8)',
                                  'rgba(16, 185, 129, 0.8)',
                                  'rgba(245, 158, 11, 0.8)',
                                  'rgba(236, 72, 153, 0.8)',
                                  'rgba(239, 68, 68, 0.8)'
                                ],
                                borderColor: [
                                  'rgb(99, 102, 241)',
                                  'rgb(59, 130, 246)',
                                  'rgb(16, 185, 129)',
                                  'rgb(245, 158, 11)',
                                  'rgb(236, 72, 153)',
                                  'rgb(239, 68, 68)'
                                ],
                                borderWidth: 2,
                                borderRadius: 6,
                                yAxisID: 'y'
                              },
                              ...(segmentEventRates.length > 0 ? [{
                                type: 'line' as const,
                                label: 'Event Rate %',
                                data: segmentEventRates,
                                borderColor: 'rgb(37, 99, 235)',
                                backgroundColor: 'rgba(37, 99, 235, 0.1)',
                                borderWidth: 3,
                                yAxisID: 'y1',
                                tension: 0.4,
                                fill: false
                              }] as any : []),
                              // 95% Confidence Interval - Upper Bound
                              ...(ciUpper.length > 0 ? [{
                                type: 'line' as const,
                                label: '95% CI Upper',
                                data: ciUpper,
                                borderColor: 'rgba(37, 99, 235, 0.3)',
                                backgroundColor: 'transparent',
                                borderWidth: 1,
                                borderDash: [4, 2],
                                pointRadius: 0,
                                pointHoverRadius: 3,
                                yAxisID: 'y1',
                                tension: 0.4,
                                fill: false
                              }] as any : []),
                              // 95% Confidence Interval - Lower Bound (with fill to upper)
                              ...(ciLower.length > 0 ? [{
                                type: 'line' as const,
                                label: '95% CI Lower',
                                data: ciLower,
                                borderColor: 'rgba(37, 99, 235, 0.3)',
                                backgroundColor: 'transparent',
                                borderWidth: 1,
                                borderDash: [4, 2],
                                pointRadius: 0,
                                pointHoverRadius: 3,
                                yAxisID: 'y1',
                                tension: 0.4,
                                // No area fill: Wilson bands for small n span most of the axis and looked like a bogus second series.
                                fill: false
                              }] as any : []),
                              // Population Average Reference Line
                              ...(populationAvgEventRate > 0 ? [{
                                type: 'line' as const,
                                label: `Pop. Avg: ${(populationAvgEventRate * 100).toFixed(2)}%`,
                                data: Array(segmentCounts.length).fill(populationAvgEventRate),
                                borderColor: 'rgb(239, 68, 68)',
                                backgroundColor: 'transparent',
                                borderWidth: 2,
                                borderDash: [8, 4],
                                pointRadius: 0,
                                pointHoverRadius: 0,
                                yAxisID: 'y1',
                                tension: 0
                              }] as any : [])
                            ]
                          }}
                          options={{ 
                            responsive: true, 
                            maintainAspectRatio: false,
                            interaction: {
                              mode: 'index' as const,
                              intersect: false
                            },
                            datasets: {
                              bar: {
                                minBarLength: 6
                              }
                            },
                            plugins: { 
                              legend: { 
                                display: true,
                                position: 'top' as const,
                                labels: {
                                  padding: 10,
                                  font: {
                                    size: 11
                                  },
                                  color: isDark ? '#d1d5db' : undefined,
                                  usePointStyle: true,
                                  boxHeight: 6,
                                  // Filter out CI bounds from legend to avoid clutter
                                  filter: (item: any) => !item.text.includes('CI')
                                }
                              },
                              tooltip: {
                                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                                padding: 12,
                                titleColor: '#fff',
                                bodyColor: '#fff',
                                borderColor: 'rgba(255, 255, 255, 0.2)',
                                borderWidth: 1,
                                callbacks: {
                                  label: function(context: any) {
                                    let label = context.dataset.label || '';
                                    if (label) {
                                      label += ': ';
                                    }
                                    if (context.parsed.y !== null) {
                                      if (context.dataset.yAxisID === 'y1') {
                                        const value = context.parsed.y;
                                        if (value <= 1) {
                                          label += (value * 100).toFixed(2) + '%';
                                        } else {
                                          label += value.toFixed(2);
                                        }
                                      } else {
                                        label += context.parsed.y.toLocaleString();
                                      }
                                    }
                                    return label;
                                  }
                                }
                              }
                            },
                            scales: {
                              y: {
                                type: 'linear' as const,
                                display: true,
                                position: 'left' as const,
                                beginAtZero: true,
                                title: {
                                  display: true,
                                  text: 'Total Records',
                                  font: {
                                    size: 10
                                  }
                                },
                                grid: {
                                  color: isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.05)'
                                },
                                ticks: {
                                  font: {
                                    size: 10
                                  },
                                  color: isDark ? '#9ca3af' : undefined
                                }
                              },
                              ...(segmentEventRates.length > 0 ? {
                                y1: {
                                  type: 'linear' as const,
                                  display: true,
                                  position: 'right' as const,
                                  beginAtZero: true,
                                  title: {
                                    display: true,
                                    text: 'Event Rate %',
                                    font: {
                                      size: 10
                                    },
                                    color: isDark ? '#d1d5db' : undefined
                                  },
                                  grid: {
                                    drawOnChartArea: false
                                  },
                                  ticks: {
                                    font: {
                                      size: 10
                                    },
                                    color: isDark ? '#9ca3af' : undefined
                                  }
                                }
                              } : {}),
                              x: {
                                grid: {
                                  display: false
                                },
                                ticks: {
                                  font: {
                                    size: 10
                                  },
                                  color: isDark ? '#9ca3af' : undefined
                                }
                              }
                            }
                          }}
                        />
                      </div>
                    )}
                    
                    {/* Overlapping Confidence Intervals Warning */}
                    {hasOverlappingCI && (
                      <div className="mt-2 p-2 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg">
                        <div className="flex items-start gap-2">
                          <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
                          <div>
                            <span className="text-xs font-medium text-amber-800 dark:text-amber-300">
                              Overlapping Confidence Intervals Detected
                            </span>
                            <p className="text-xs text-amber-700 dark:text-amber-400 mt-0.5">
                              Some segments have event rates with overlapping 95% confidence intervals. 
                              This suggests they may not be statistically distinguishable - consider merging.
                            </p>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Enhanced Segment Profile Table — below Segment Sizes */}
                  {Array.isArray(activeSegmentationResult.segments) && activeSegmentationResult.segments.length > 0 && (
                    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm">
                      <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
                        <div className="flex items-center gap-2">
                          <h5 className="font-semibold text-gray-900 dark:text-gray-100">Segment Profile</h5>
                          <span className="text-xs text-gray-500 dark:text-gray-400">
                            Click the edit icon to adjust cutoffs. Merging works on one pair at a time—select exactly
                            two segments, then run merge. To combine more, merge again.
                          </span>
                        </div>
                      </div>
                      <div className="overflow-x-auto">
                        <table className="w-full min-w-max text-sm">
                          <thead className="bg-gray-50 dark:bg-gray-700/50">
                            <tr>
                              <th className="w-10 px-3 py-2 text-left"></th>
                              <th className="px-3 py-2 text-left font-medium text-gray-700 dark:text-gray-300">
                                <span className="whitespace-nowrap">Segment</span>
                              </th>
                              <th className="px-3 py-2 text-left font-medium text-gray-700 dark:text-gray-300 min-w-[8rem]">Rule</th>
                              <th className="px-3 py-2 text-right font-medium text-gray-700 dark:text-gray-300">
                                <span className="inline-block whitespace-nowrap">Records</span>
                              </th>
                              <th className="px-3 py-2 text-right font-medium text-gray-700 dark:text-gray-300">
                                <span className="inline-block whitespace-nowrap">% Pop</span>
                              </th>
                              <th className="px-3 py-2 text-right font-medium text-gray-700 dark:text-gray-300">
                                <span className="inline-block whitespace-nowrap" title="Event rate (%)">
                                  Event&nbsp;Rate&nbsp;%
                                </span>
                              </th>
                              <th className="px-3 py-2 text-right font-medium text-gray-700 dark:text-gray-300">
                                <span className="inline-block whitespace-nowrap">WoE</span>
                              </th>
                              <th className="px-3 py-2 text-right font-medium text-gray-700 dark:text-gray-300">
                                <span
                                  className="inline-block whitespace-nowrap"
                                  title="IV contribution (per segment)"
                                >
                                  IV&nbsp;Contribution
                                </span>
                              </th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                            {activeSegmentationResult.segments.map((segment: any, idx: number) => {
                              const isSelected = selectedSegmentsForMerge.includes(segment.segment_id || idx);
                              const disp = profileDisplayMetrics[idx] ?? { woe: 0, iv: 0 };
                              return (
                                <tr
                                  key={idx}
                                  className={`hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors ${isSelected ? 'bg-blue-50 dark:bg-blue-900/20' : ''}`}
                                >
                                  <td className="px-3 py-2">
                                    <input
                                      type="checkbox"
                                      checked={isSelected}
                                      onChange={(e) => {
                                        const segId = segment.segment_id || idx;
                                        if (e.target.checked) {
                                          setSelectedSegmentsForMerge(prev => [...prev, segId]);
                                        } else {
                                          setSelectedSegmentsForMerge(prev => prev.filter(id => id !== segId));
                                        }
                                      }}
                                      className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                                    />
                                  </td>
                                  <td className="px-3 py-2 font-medium text-gray-900 dark:text-gray-100">
                                    Seg {idx + 1}
                                  </td>
                                  <td className="px-3 py-2 text-gray-600 dark:text-gray-400 max-w-[200px]">
                                    <div className="flex items-center gap-2">
                                      <span className="truncate" title={segment.rule_definition || segment.rules_readable || 'All data'}>
                                        {segment.rule_definition || segment.rules_readable || (Array.isArray(segment.rules) && segment.rules.length > 0 ? segment.rules.join(' AND ') : 'All data')}
                                      </span>
                                      {(segment.rule_definition || '').match(/\w+\s*(>|>=|<|<=|==|!=)\s*[\d.]+/) && (
                                        <button
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            handleOpenCutoffEdit(segment);
                                          }}
                                          className="p-1 hover:bg-gray-200 dark:hover:bg-gray-600 rounded transition-colors flex-shrink-0"
                                          title="Edit cutoff value"
                                        >
                                          <Edit3 className="w-3 h-3 text-gray-500 hover:text-blue-600 dark:text-gray-400 dark:hover:text-blue-400" />
                                        </button>
                                      )}
                                    </div>
                                  </td>
                                  <td className="px-3 py-2 text-right text-gray-900 dark:text-gray-100">
                                    {(segment.record_count || segment.size || 0).toLocaleString()}
                                  </td>
                                  <td className="px-3 py-2 text-right text-gray-600 dark:text-gray-400">
                                    {(segment.pct_of_population || ((segment.record_count || segment.size || 0) / (activeSegmentationResult.dataset_shape || activeSegmentationResult.total_segment_records || 1) * 100)).toFixed(1)}%
                                  </td>
                                  <td className="px-3 py-2 text-right">
                                    <span className={`font-medium ${
                                      (() => {
                                        const er = segmentEventRateToFraction(segment.event_rate);
                                        return er > 0.15 ? 'text-red-600 dark:text-red-400' :
                                          er > 0.10 ? 'text-amber-600 dark:text-amber-400' :
                                          'text-green-600 dark:text-green-400';
                                      })()
                                    }`}>
                                      {(segmentEventRateToFraction(segment.event_rate) * 100).toFixed(2)}%
                                    </span>
                                  </td>
                                  <td className="px-3 py-2 text-right">
                                    <span className={`font-medium ${
                                      disp.woe > 0 ? 'text-green-600 dark:text-green-400' :
                                      disp.woe < 0 ? 'text-red-600 dark:text-red-400' :
                                      'text-gray-600 dark:text-gray-400'
                                    }`}>
                                      {disp.woe.toFixed(2)}
                                    </span>
                                  </td>
                                  <td className="px-3 py-2 text-right text-gray-900 dark:text-gray-100">
                                    {disp.iv.toFixed(3)}
                                  </td>
                                </tr>
                              );
                            })}
                            <tr className="bg-gray-100 dark:bg-gray-700/70 font-semibold">
                              <td className="px-3 py-2"></td>
                              <td className="px-3 py-2 text-gray-900 dark:text-gray-100">Total</td>
                              <td className="px-3 py-2"></td>
                              <td className="px-3 py-2 text-right text-gray-900 dark:text-gray-100">
                                {activeSegmentationResult.segments.reduce((sum: number, s: any) => sum + (s.record_count || s.size || 0), 0).toLocaleString()}
                              </td>
                              <td className="px-3 py-2 text-right text-gray-900 dark:text-gray-100">100%</td>
                              <td className="px-3 py-2 text-right text-gray-900 dark:text-gray-100">
                                {(() => {
                                  const totalRecords = activeSegmentationResult.segments.reduce((sum: number, s: any) => sum + (s.record_count || s.size || 0), 0);
                                  const totalEvents = activeSegmentationResult.segments.reduce((sum: number, s: any) => sum + ((s.event_count || 0)), 0);
                                  return totalRecords > 0 ? ((totalEvents / totalRecords) * 100).toFixed(2) + '%' : 'N/A';
                                })()}
                              </td>
                              <td className="px-3 py-2 text-right"></td>
                              <td className="px-3 py-2 text-right text-blue-600 dark:text-blue-400">
                                {profileIvTotal.toFixed(3)}
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                      <div className="p-3 border-t border-gray-200 dark:border-gray-700">
                        <div className="flex items-center gap-3">
                          {selectedSegmentsForMerge.length >= 2 && (
                            <button
                              onClick={handleMergeSegments}
                              disabled={isApplyingMerge}
                              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-orange-500 hover:bg-orange-600 rounded-lg transition-colors disabled:opacity-50"
                            >
                              {isApplyingMerge ? (
                                <Loader className="w-4 h-4 animate-spin" />
                              ) : (
                                <GitMerge className="w-4 h-4" />
                              )}
                              {isApplyingMerge ? 'Merging...' : `Merge Selected (${selectedSegmentsForMerge.length})`}
                            </button>
                          )}
                          {segmentationUndoStack.length > 0 && (
                            <button
                              onClick={handleUndoMerge}
                              disabled={isApplyingMerge}
                              className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg transition-colors disabled:opacity-50"
                            >
                              <Undo2 className="w-4 h-4" />
                              Undo
                            </button>
                          )}
                        </div>
                        {lastMergeImpact && (
                          <div className="mt-3 p-2 bg-green-50 dark:bg-green-900/20 rounded border border-green-200 dark:border-green-700">
                            <div className="flex items-center gap-2 text-sm text-green-800 dark:text-green-400">
                              <CheckCircle className="w-4 h-4" />
                              <span className="font-medium">Merged: {lastMergeImpact.merged_segment_name}</span>
                            </div>
                            <div className="mt-1 text-xs text-green-700 dark:text-green-500">
                              {lastMergeImpact.combined_records.toLocaleString()} records |
                              Event rate: {(segmentEventRateToFraction(lastMergeImpact.combined_event_rate) * 100).toFixed(2)}% |
                              IV change: {lastMergeImpact.iv_change >= 0 ? '+' : ''}{lastMergeImpact.iv_change.toFixed(4)} ({lastMergeImpact.iv_change_pct.toFixed(1)}%)
                            </div>
                            {mergeExplanation && (
                              <div className="mt-2 pt-2 border-t border-green-200 dark:border-green-600">
                                <div className="flex items-start gap-2">
                                  <Sparkles className="w-3 h-3 mt-0.5 text-green-600 dark:text-green-400 flex-shrink-0" />
                                  <p className="text-xs text-green-700 dark:text-green-400 italic">{mergeExplanation}</p>
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Merge suggestions from validation (three-condition framework) */}
                  {activeSegmentationResult.validation &&
                    Array.isArray(activeSegmentationResult.segments) &&
                    activeSegmentationResult.segments.length > 0 && (
                      <div className="mt-4 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm">
                        <div className="flex items-start gap-2 p-4 border-b border-gray-200 dark:border-gray-700">
                          <Sparkles className="w-4 h-4 text-indigo-500 shrink-0 mt-0.5" />
                          <div className="min-w-0">
                            <h5 className="font-semibold text-gray-900 dark:text-gray-100">AI recommendations</h5>
                            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                              Suggested segment pairs to consider merging, from the same validation rules as the merge
                              engine (reliability, practical separation, holdout support when available).
                            </p>
                          </div>
                        </div>
                        <div className="p-4 space-y-3">
                          {(() => {
                            const recs = activeSegmentationResult.validation?.merge_recommendations || [];
                            const segs = activeSegmentationResult.segments || [];
                            const resolveSegId = (label: string): number | undefined => {
                              const t = String(label ?? '').trim();
                              if (!t) return undefined;
                              const byName = segs.find(
                                (x: any) => String(x.segment_name ?? '').trim() === t
                              );
                              if (byName != null && byName.segment_id != null) return Number(byName.segment_id);
                              const m = /^segment\s+(\d+)$/i.exec(t);
                              if (m) {
                                const idx = parseInt(m[1], 10) - 1;
                                if (idx >= 0 && idx < segs.length) {
                                  const s = segs[idx];
                                  if (s?.segment_id != null) return Number(s.segment_id);
                                  return idx + 1;
                                }
                              }
                              return undefined;
                            };
                            if (!recs.length) {
                              return (
                                <p className="text-sm text-gray-600 dark:text-gray-400">
                                  No merge pairs are flagged for this scheme. Segments pass the current statistical
                                  checks, or there are too few segments to compare.
                                </p>
                              );
                            }
                            return recs.map((rec: any, i: number) => {
                              const idA = resolveSegId(rec.segment_a);
                              const idB = resolveSegId(rec.segment_b);
                              const canSelect = idA != null && idB != null && idA !== idB;
                              const cond = String(rec.failed_condition || 'unknown');
                              const condCls =
                                cond === 'reliability'
                                  ? 'bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-200'
                                  : cond === 'practical_separation'
                                    ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-200'
                                    : 'bg-purple-100 dark:bg-purple-900/30 text-purple-800 dark:text-purple-200';
                              return (
                                <div
                                  key={`merge-rec-${i}-${rec.segment_a}-${rec.segment_b}`}
                                  className="rounded-lg border border-gray-200 dark:border-gray-600 p-3 bg-gray-50/80 dark:bg-gray-900/40"
                                >
                                  <div className="flex flex-wrap items-center justify-between gap-2">
                                    <div className="text-sm font-medium text-gray-900 dark:text-gray-100">
                                      Merge{' '}
                                      <span className="text-indigo-600 dark:text-indigo-400">{rec.segment_a}</span>
                                      {' + '}
                                      <span className="text-indigo-600 dark:text-indigo-400">{rec.segment_b}</span>
                                    </div>
                                    <div className="flex items-center gap-2 shrink-0">
                                      <span
                                        className={`text-[10px] uppercase tracking-wide px-2 py-0.5 rounded font-medium ${condCls}`}
                                      >
                                        {cond.replace(/_/g, ' ')}
                                      </span>
                                      {rec.is_bootstrap_borderline && (
                                        <span className="text-[10px] px-2 py-0.5 rounded bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-200">
                                          Borderline
                                        </span>
                                      )}
                                    </div>
                                  </div>
                                  {rec.explanation ? (
                                    <p className="mt-2 text-xs text-gray-600 dark:text-gray-400 leading-relaxed">
                                      {formatMergeRecommendationExplanationForDisplay(
                                        rec.explanation,
                                        cond
                                      )}
                                    </p>
                                  ) : null}
                                  {canSelect ? (
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setSelectedSegmentsForMerge([idA!, idB!]);
                                      }}
                                      className="mt-2 text-xs font-medium text-indigo-600 dark:text-indigo-400 hover:underline"
                                    >
                                      Select this pair for merge
                                    </button>
                                  ) : null}
                                </div>
                              );
                            });
                          })()}
                        </div>
                      </div>
                    )}
                  
                  {/* Pie Chart - Segment Proportions */}
                  {segmentProportions.length > 0 && (
                    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm">
                      <div 
                        className="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
                        onClick={() => setSegmentProportionsExpanded(!segmentProportionsExpanded)}
                      >
                        <h5 className="font-semibold text-gray-900 dark:text-gray-100">Segment Proportions</h5>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setExpandedChart('proportions');
                            }}
                            className="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
                            title="Expand chart"
                          >
                            <Maximize2 className="w-4 h-4 text-gray-600" />
                          </button>
                          {segmentProportionsExpanded ? (
                            <ChevronUp className="w-5 h-5 text-gray-500" />
                          ) : (
                            <ChevronDown className="w-5 h-5 text-gray-500" />
                          )}
                        </div>
                      </div>
                      {segmentProportionsExpanded && (
                        <div className="px-4 pb-4" style={{ height: '280px' }}>
                          <Pie
                            data={{
                              labels: segmentProportions.map((_: any, i: number) => `Segment ${i+1}`),
                              datasets: [{
                                label: 'Proportion',
                                data: segmentProportions,
                                backgroundColor: [
                                  'rgba(99, 102, 241, 0.8)',
                                  'rgba(59, 130, 246, 0.8)',
                                  'rgba(16, 185, 129, 0.8)',
                                  'rgba(245, 158, 11, 0.8)',
                                  'rgba(236, 72, 153, 0.8)',
                                  'rgba(239, 68, 68, 0.8)'
                                ],
                                borderColor: [
                                  'rgb(99, 102, 241)',
                                  'rgb(59, 130, 246)',
                                  'rgb(16, 185, 129)',
                                  'rgb(245, 158, 11)',
                                  'rgb(236, 72, 153)',
                                  'rgb(239, 68, 68)'
                                ],
                                borderWidth: 2
                              }]
                            }}
                            options={{ 
                              responsive: true, 
                              maintainAspectRatio: false,
                              plugins: { 
                                legend: { 
                                  position: 'bottom',
                                  labels: {
                                    padding: 10,
                                    font: {
                                      size: 11
                                    },
                                    color: isDark ? '#d1d5db' : undefined,
                                    usePointStyle: true,
                                    pointStyle: 'circle',
                                    boxHeight: 8
                                  }
                                },
                                tooltip: {
                                  backgroundColor: 'rgba(0, 0, 0, 0.8)',
                                  padding: 12,
                                  titleColor: '#fff',
                                  bodyColor: '#fff',
                                  borderColor: 'rgba(255, 255, 255, 0.2)',
                                  borderWidth: 1,
                                  callbacks: {
                                    label: function(context: any) {
                                      const label = context.label || '';
                                      const value = context.parsed || 0;
                                      const percentage = (value * 100).toFixed(1);
                                      return `${label}: ${percentage}%`;
                                    }
                                  }
                                }
                              }
                            }}
                          />
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ) : null;
            })()}

            {/* AI Summary (Statistical Validation metric cards removed) */}
            {activeSegmentationResult.validation && (recommendationNarrative || isLoadingNarrative) && (
              <div className="mt-6 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                <div className="flex items-start gap-2">
                  <Sparkles className="w-4 h-4 mt-0.5 text-blue-600 dark:text-blue-400 flex-shrink-0" />
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-semibold text-gray-700 dark:text-gray-300">AI Summary</span>
                    </div>
                    {isLoadingNarrative ? (
                      <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                        <Loader className="w-3 h-3 animate-spin" />
                        Generating insights...
                      </div>
                    ) : (
                      renderRecommendationNarrativeBody(recommendationNarrative)
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Train vs Test vs Holdout Validation - Screenshot 3 Style */}
            {activeSegmentationResult.validation?.oos_validation && (
              <div className="mt-6 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                <h5 className="font-semibold text-gray-900 dark:text-gray-100 mb-1">Train vs. {activeSegmentationResult.validation.oos_validation.partition_used === 'holdout' ? 'Holdout' : 'Test'} Validation</h5>
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-4">Do segments maintain profiles out-of-sample?</p>
                
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 dark:bg-gray-700/50">
                      <tr>
                        <th className="px-3 py-2 text-left font-medium text-gray-700 dark:text-gray-300">Segment</th>
                        <th className="px-3 py-2 text-right font-medium text-gray-700 dark:text-gray-300">Train Rate</th>
                        <th className="px-3 py-2 text-right font-medium text-gray-700 dark:text-gray-300">{activeSegmentationResult.validation.oos_validation.partition_used === 'holdout' ? 'Holdout' : 'Test'} Rate</th>
                        <th className="px-3 py-2 text-right font-medium text-gray-700 dark:text-gray-300">Drift</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                      {activeSegmentationResult.validation.oos_validation.segment_comparison?.map((seg: any, idx: number) => (
                        <tr key={idx} className="hover:bg-gray-50 dark:hover:bg-gray-700/30">
                          <td className="px-3 py-2 font-medium text-gray-900 dark:text-gray-100">Seg {idx + 1}</td>
                          <td className="px-3 py-2 text-right text-gray-600 dark:text-gray-400">{formatOosEventRatePercent(seg.train_event_rate)}</td>
                          <td className="px-3 py-2 text-right text-gray-600 dark:text-gray-400">{formatOosEventRatePercent(seg.oos_event_rate)}</td>
                          <td className="px-3 py-2 text-right">
                            <span className={`font-medium ${
                              Math.abs((seg.event_rate_drift || 0)) <= 0.5 ? 'text-green-600 dark:text-green-400' :
                              Math.abs((seg.event_rate_drift || 0)) <= 1.0 ? 'text-amber-600 dark:text-amber-400' :
                              'text-red-600 dark:text-red-400'
                            }`}>
                              {formatOosEventRateDriftPp(seg.event_rate_drift)}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                
                {/* Rank Order Preserved indicator */}
                <div className={`mt-4 p-3 rounded-lg border ${
                  activeSegmentationResult.validation.oos_validation.rank_order_preserved 
                    ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-700' 
                    : 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-700'
                }`}>
                  <div className="flex items-center gap-2">
                    {activeSegmentationResult.validation.oos_validation.rank_order_preserved ? (
                      <CheckCircle className="w-5 h-5 text-green-600 dark:text-green-400" />
                    ) : (
                      <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400" />
                    )}
                    <span className={`font-semibold ${
                      activeSegmentationResult.validation.oos_validation.rank_order_preserved 
                        ? 'text-green-800 dark:text-green-400' 
                        : 'text-amber-800 dark:text-amber-400'
                    }`}>
                      {activeSegmentationResult.validation.oos_validation.rank_order_preserved 
                        ? 'Rank Order Preserved' 
                        : 'Rank Order Not Preserved'}
                    </span>
                  </div>
                  <p className={`mt-1 text-xs ${
                    activeSegmentationResult.validation.oos_validation.rank_order_preserved 
                      ? 'text-green-700 dark:text-green-300' 
                      : 'text-amber-700 dark:text-amber-300'
                  }`}>
                    {activeSegmentationResult.validation.oos_validation.rank_order_preserved 
                      ? `Event rate ordering consistent across all partitions. Chi-squared on ${activeSegmentationResult.validation.oos_validation.partition_used}: ${formatSegmentationChiSquaredPLabel(activeSegmentationResult.validation.oos_validation.chi_squared_p, activeSegmentationResult.validation.oos_validation.chi_squared_significant)}.`
                      : 'Event rate ordering differs between train and out-of-sample partitions. Consider reviewing segment stability.'}
                  </p>
                </div>
              </div>
            )}

            {/* Variable Relevance Matrix - Top 10 Variables by IV Per Segment */}
            {activeSegmentationResult.variable_relevance && 
             activeSegmentationResult.variable_relevance.variables && 
             activeSegmentationResult.variable_relevance.variables.length > 0 && (
              <div className="mt-6 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h5 className="font-semibold text-gray-900 dark:text-gray-100">Variable Relevance Matrix</h5>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      Top variables by IV per segment. Rows default to <strong>Overall IV</strong> (highest first);
                      segment columns are ordered Seg 1, Seg 2, … — click a column to sort by that column instead.
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      type="button"
                      onClick={downloadVariableRelevanceMatrixCsv}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                      title="Download matrix as CSV"
                    >
                      <Download className="w-3.5 h-3.5" />
                      Download
                    </button>
                    <span className="px-2 py-1 text-xs bg-purple-100 dark:bg-purple-900/30 text-purple-800 dark:text-purple-400 rounded-full">
                      {activeSegmentationResult.variable_relevance.variables.length} vars
                    </span>
                  </div>
                </div>
                
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead className="bg-gray-50 dark:bg-gray-700/50">
                      <tr>
                        <th className="px-2 py-2 text-left font-medium text-gray-700 dark:text-gray-300 sticky left-0 bg-gray-50 dark:bg-gray-700/50">Variable</th>
                        <th className="px-2 py-2 text-right">
                          <button
                            type="button"
                            onClick={() => setVariableRelevanceSortBy('overall')}
                            className={`w-full text-right font-medium text-gray-700 dark:text-gray-300 hover:text-purple-700 dark:hover:text-purple-300 ${
                              vrSortColumn === 'overall' ? 'underline decoration-purple-500' : ''
                            }`}
                            title="Sort by Overall IV (descending)"
                          >
                            Overall IV{vrSortColumn === 'overall' ? ' \u2193' : ''}
                          </button>
                        </th>
                        {segKeysVrDisplayOrder.map((segName) => (
                          <th key={segName} className="px-2 py-2 text-right whitespace-nowrap">
                            <button
                              type="button"
                              onClick={() => setVariableRelevanceSortBy(segName)}
                              className={`w-full text-right font-medium text-gray-700 dark:text-gray-300 hover:text-purple-700 dark:hover:text-purple-300 ${
                                vrSortColumn === segName ? 'underline decoration-purple-500' : ''
                              }`}
                              title={`Sort by ${segName} IV (descending)`}
                            >
                              {segName.replace('Segment ', 'Seg ')}
                              {vrSortColumn === segName ? ' \u2193' : ''}
                            </button>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                      {variableRelevanceVariablesSorted.map((variable: string) => {
                        const overallIV = activeSegmentationResult.variable_relevance.overall_iv[variable] || 0;
                        return (
                          <tr key={variable} className="hover:bg-gray-50 dark:hover:bg-gray-700/30">
                            <td className="px-2 py-1.5 font-medium text-gray-900 dark:text-gray-100 truncate max-w-[120px] sticky left-0 bg-white dark:bg-gray-800" title={variable}>
                              {variable.length > 15 ? variable.substring(0, 15) + '...' : variable}
                            </td>
                            <td className="px-2 py-1.5 text-right">
                              <span className={`font-medium ${
                                overallIV >= 0.3 ? 'text-green-600 dark:text-green-400' :
                                overallIV >= 0.1 ? 'text-amber-600 dark:text-amber-400' :
                                'text-gray-500 dark:text-gray-400'
                              }`}>
                                {overallIV.toFixed(3)}
                              </span>
                            </td>
                            {segKeysVrDisplayOrder.map((segName) => {
                              const segIV = Number(vr?.segment_iv?.[segName]?.[variable] ?? 0) || 0;
                              return (
                                <td key={segName} className="px-2 py-1.5 text-right">
                                  <span className={`${
                                    segIV >= 0.3 ? 'text-green-600 dark:text-green-400 font-semibold' :
                                    segIV >= 0.1 ? 'text-amber-600 dark:text-amber-400' :
                                    segIV > 0 ? 'text-gray-500 dark:text-gray-400' :
                                    'text-gray-300 dark:text-gray-600'
                                  }`}>
                                    {segIV > 0 ? segIV.toFixed(3) : '-'}
                                  </span>
                                </td>
                              );
                            })}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Add to Data / Codebook — bottom of insights, below Variable Relevance Matrix when present */}
            {activeSegmentationResult?.success && (
              <div className="mt-6 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 shadow-sm">
                <SegmentationAddToDataBar
                  onAddToData={handleSidebarAddToData}
                  onCodebook={handleSidebarSegmentationCodebook}
                  codebookLoading={segCodebookLoading}
                />
              </div>
            )}

          </div>
        ) : (
          <div className="text-center py-6 text-gray-500">
            <p className="text-sm">Run segmentation to see results here.</p>
          </div>
        )}
      </div>
      )}


    </div>
  );
  };

  const renderConfigTab = () => (
    <div className="space-y-6">
      {/* Feature Graph Section */}
      <div className="space-y-3">
        {/* Header with title and action buttons */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Network className="h-4 w-4 text-orange-500" />
            <h4 className="font-medium text-gray-900 dark:text-gray-100">Feature Graph</h4>
            {datasetId && knowledgeGraphCache.has(getKgCacheKey(datasetId)) && (
              <span className="text-xs text-green-600 font-medium">Generated</span>
            )}
          </div>
          <div className="flex items-center space-x-2">
            {/* Export button - only show when graph exists */}
            {knowledgeGraphData?.html_content && (
              <button
                onClick={downloadKnowledgeGraphCSV}
                className="p-1.5 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                title="Export feature graph as CSV"
              >
                <Download className="h-4 w-4 text-gray-600 dark:text-gray-400" />
              </button>
            )}
            {/* Generate/Refresh button */}
            <button
              onClick={() => handleGenerateKnowledgeGraph(!!knowledgeGraphData?.html_content)}
              disabled={isLoadingKnowledgeGraph}
              className="p-1.5 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              title={knowledgeGraphData?.html_content ? "Refresh feature graph" : "Generate feature graph"}
            >
              {isLoadingKnowledgeGraph ? (
                <Loader className="h-4 w-4 text-orange-500 animate-spin" />
              ) : (
                <Activity className="h-4 w-4 text-gray-600 dark:text-gray-400" />
              )}
            </button>
          </div>
        </div>

        {/* Feature Graph Content Area */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
          {!datasetId ? (
            // No dataset selected
            <div className="text-center py-8">
              <Database className="h-8 w-8 text-gray-400 mx-auto mb-2" />
              <p className="text-sm text-gray-500">No dataset available</p>
              <p className="text-xs text-gray-400 mt-1">Upload a dataset to generate the feature graph</p>
            </div>
          ) : isLoadingKnowledgeGraph ? (
            // Loading state
            <div className="text-center py-8">
              <Loader className="h-8 w-8 text-orange-500 animate-spin mx-auto mb-2" />
              <p className="text-sm text-gray-600 dark:text-gray-400">Generating feature graph...</p>
              <p className="text-xs text-gray-400 mt-1">This may take a few moments</p>
            </div>
          ) : knowledgeGraphData?.error ? (
            // Error state
            <div className="text-center py-8 px-4">
              <AlertTriangle className="h-8 w-8 text-red-400 mx-auto mb-2" />
              <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100 mb-1">Failed to Generate Feature Graph</h3>
              <p className="text-xs text-gray-600 dark:text-gray-400 mb-3">{knowledgeGraphData.error}</p>
              <button
                onClick={() => handleGenerateKnowledgeGraph(true)}
                disabled={isLoadingKnowledgeGraph}
                className="inline-flex items-center px-3 py-1.5 text-xs bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] disabled:opacity-50"
              >
                <Network className="h-3 w-3 mr-1" />
                Try Again
              </button>
            </div>
          ) : knowledgeGraphData?.html_content ? (
            // Graph is ready - show it inline
            <div>
              <iframe
                srcDoc={knowledgeGraphData.html_content}
                className="w-full border-0"
                title="Feature Graph Visualization"
                style={{ height: '400px' }}
              />
              {/* Additional info collapsed section */}
              {(knowledgeGraphData.algorithm_explanation || knowledgeGraphData.relationship_mapping || knowledgeGraphData.usage_instructions) && (
                <div className="border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 p-3 max-h-32 overflow-y-auto">
                  {knowledgeGraphData.algorithm_explanation && (
                    <div className="mb-2">
                      <h5 className="text-xs font-medium text-gray-700 dark:text-gray-300">Algorithm</h5>
                      <p className="text-xs text-gray-500 dark:text-gray-400">{knowledgeGraphData.algorithm_explanation}</p>
                    </div>
                  )}
                  {knowledgeGraphData.relationship_mapping && (
                    <div className="mb-2">
                      <h5 className="text-xs font-medium text-gray-700 dark:text-gray-300">Relationships</h5>
                      <p className="text-xs text-gray-500 dark:text-gray-400">{knowledgeGraphData.relationship_mapping}</p>
                    </div>
                  )}
                  {knowledgeGraphData.usage_instructions && (
                    <div>
                      <h5 className="text-xs font-medium text-gray-700 dark:text-gray-300">Instructions</h5>
                      <p className="text-xs text-gray-500 dark:text-gray-400">{knowledgeGraphData.usage_instructions}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : knowledgeGraphData?.processing_info?.status === 'partial' ? (
            // Processing in background
            <div className="text-center py-8">
              <Network className="h-8 w-8 text-gray-400 mx-auto mb-2" />
              <p className="text-sm text-gray-600 dark:text-gray-400">Feature Graph is being generated...</p>
              <p className="text-xs text-gray-400 mt-1">The graph will appear here once ready</p>
            </div>
          ) : (
            // Initial state - show generate prompt
            <div className="text-center py-8">
              <Network className="h-8 w-8 text-gray-400 mx-auto mb-2" />
              <p className="text-sm text-gray-600 dark:text-gray-400">Click the refresh button to generate</p>
              <p className="text-xs text-gray-400 mt-1">Visualize relationships between features</p>
              <button
                onClick={() => handleGenerateKnowledgeGraph()}
                disabled={isLoadingKnowledgeGraph}
                className="mt-3 inline-flex items-center px-3 py-1.5 text-xs bg-orange-500 text-white rounded-lg hover:bg-orange-600 disabled:opacity-50"
              >
                <Network className="h-3 w-3 mr-1" />
                Generate Feature Graph
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Segmentation Summary - Only show on step 3.5 (segmentation step) */}
      {currentStep === 3.5 && (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <h4 className="font-medium text-gray-900 dark:text-gray-100 mb-4">Segmentation Summary</h4>
          {activeSegmentationResult?.success ? (
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-4">
                <div className="text-center p-3 bg-purple-50 dark:bg-purple-900/30 rounded-lg">
                  <div className="text-xs text-gray-600 dark:text-gray-400">Method</div>
                  <div className="text-lg font-semibold text-purple-700 dark:text-purple-400">{String(activeSegmentationResult.method).toUpperCase()}</div>
                </div>
                <div className="text-center p-3 bg-blue-50 dark:bg-blue-900/30 rounded-lg">
                  <div className="text-xs text-gray-600 dark:text-gray-400">Segments</div>
                  <div className="text-lg font-semibold text-blue-700 dark:text-blue-400">{activeSegmentationResult.num_segments}</div>
                </div>
                <div className="text-center p-3 bg-green-50 dark:bg-green-900/30 rounded-lg">
                  <div className="text-xs text-gray-600 dark:text-gray-400">Variables used</div>
                  <div className="text-sm font-medium text-green-700 dark:text-green-400 truncate" title={activeSegmentationResult.variables_used?.join(', ')}>
                    {activeSegmentationResult.variables_used?.slice(0,3).join(', ')}{activeSegmentationResult.variables_used?.length>3?'…':''}
                  </div>
                </div>
              </div>


              {/* Segment Record Summation Verification */}
              {Array.isArray(activeSegmentationResult.segments) && (() => {
                console.log('🔍 Segmentation Result Keys:', Object.keys(activeSegmentationResult));
                console.log('📊 Dataset Shape:', activeSegmentationResult.dataset_shape);
                console.log('📊 Total Segment Records:', activeSegmentationResult.total_segment_records);
                console.log('📊 Records Match:', activeSegmentationResult.records_match);
                return true;
              })() && (
                <div className="mb-4 p-4 bg-gradient-to-r from-indigo-50 to-purple-50 dark:from-indigo-900/20 dark:to-purple-900/20 rounded-lg border-2 border-indigo-200 dark:border-indigo-700">
                  <h5 className="font-medium text-gray-900 dark:text-gray-100 mb-3 flex items-center gap-2">
                    <span className="text-indigo-600">📊</span>
                    Segment Records Verification
                  </h5>
                  <div className="grid grid-cols-3 gap-3 text-sm">
                    <div className="bg-white dark:bg-gray-800 rounded-lg p-3 border border-indigo-100 dark:border-indigo-800">
                      <div className="text-xs text-gray-600 dark:text-gray-400 mb-1">Sum of Segments</div>
                      <div className="text-lg font-bold text-indigo-700 dark:text-indigo-400">
                        {activeSegmentationResult.total_segment_records?.toLocaleString() || 
                         activeSegmentationResult.segments.reduce((sum: number, s: any) => sum + (s.size || 0), 0).toLocaleString()}
                      </div>
                    </div>
                    <div className="bg-white dark:bg-gray-800 rounded-lg p-3 border border-indigo-100 dark:border-indigo-800">
                      <div className="text-xs text-gray-600 dark:text-gray-400 mb-1">Dataset Shape</div>
                      <div className="text-lg font-bold text-indigo-700 dark:text-indigo-400">
                        {activeSegmentationResult.dataset_shape?.toLocaleString() || 'N/A'}
                      </div>
                    </div>
                    <div className="bg-white dark:bg-gray-800 rounded-lg p-3 border border-indigo-100 dark:border-indigo-800">
                      <div className="text-xs text-gray-600 dark:text-gray-400 mb-1">Verification</div>
                      <div className={`text-lg font-bold flex items-center gap-1 ${
                        activeSegmentationResult.records_match === true || 
                        (activeSegmentationResult.total_segment_records === activeSegmentationResult.dataset_shape)
                          ? 'text-green-600' 
                          : activeSegmentationResult.records_match === false 
                          ? 'text-red-600' 
                          : 'text-gray-500'
                      }`}>
                        {activeSegmentationResult.records_match === true || 
                         (activeSegmentationResult.total_segment_records === activeSegmentationResult.dataset_shape)
                          ? '✓ Match' 
                          : activeSegmentationResult.records_match === false
                          ? '✗ Mismatch'
                          : '- N/A'}
                      </div>
                    </div>
                  </div>
                  {(activeSegmentationResult.records_match === false || 
                    (activeSegmentationResult.total_segment_records && activeSegmentationResult.dataset_shape && 
                     activeSegmentationResult.total_segment_records !== activeSegmentationResult.dataset_shape)) && (
                    <div className="mt-3 p-2 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-700 rounded text-xs text-yellow-800 dark:text-yellow-300">
                      ⚠️ Warning: Segment sum doesn't match dataset shape. Difference: {Math.abs((activeSegmentationResult.total_segment_records || 0) - (activeSegmentationResult.dataset_shape || 0)).toLocaleString()} records
                    </div>
                  )}
                </div>
              )}

              {/* Segment sizes bar chart (simple) */}
              {Array.isArray(activeSegmentationResult.segments) && (
                <div>
                  <h5 className="font-medium text-gray-900 dark:text-gray-100 mb-2">Segment Sizes</h5>
                  {(() => {
                    const segmentSizes = activeSegmentationResult.segments.map((s: any) => s.size);
                    console.log('Segment Sizes chart data:', segmentSizes);
                    console.log('Individual segment sizes:', activeSegmentationResult.segments.map((s: any, i: number) => `Segment ${i + 1}: ${s.size}`));
                    return null;
                  })()}
                  <Bar
                    key={`segment-sizes-${theme}`}
                    data={{
                      labels: activeSegmentationResult.segments.map((_: any, i: number) => `Segment ${i + 1}`),
                      datasets: [{
                        label: 'Count',
                        data: activeSegmentationResult.segments.map((s: any) => s.size), // Same data source as Accounts column
                        backgroundColor: isDark ? 'rgba(167, 139, 250, 0.55)' : 'rgba(168, 85, 247, 0.45)',
                        borderColor: isDark ? 'rgba(221, 214, 254, 0.9)' : 'rgba(126, 34, 206, 0.65)',
                        borderWidth: 1,
                      }]
                    }}
                    options={{
                      color: chartJsDefaultFontColor(isDark),
                      responsive: true,
                      maintainAspectRatio: false,
                      plugins: {
                        legend: { display: false },
                        tooltip: { ...chartJsTooltipColors(isDark) },
                      },
                      scales: {
                        x: {
                          border: chartJsScaleBorder(isDark),
                          ticks: { color: isDark ? '#cbd5e1' : '#475569' },
                          grid: { color: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)' },
                        },
                        y: {
                          border: chartJsScaleBorder(isDark),
                          ticks: { color: isDark ? '#cbd5e1' : '#475569' },
                          grid: { color: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)' },
                        },
                      },
                    }}
                  />
                </div>
              )}

              {/* Segment Creation Rules - NEW SECTION */}
              {Array.isArray(activeSegmentationResult.segments) && (
                <div className="mt-4">
                  <h5 className="font-medium text-gray-900 dark:text-gray-100 mb-3">Segment Creation Rules</h5>
                  <div className="space-y-2">
                    {activeSegmentationResult.segments.map((s: any, idx: number) => (
                      <div key={idx} className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded border border-blue-200 dark:border-blue-800">
                        <div className="flex items-start space-x-2">
                          <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-bold flex-shrink-0 mt-0.5">
                            {idx + 1}
                          </span>
                          <div className="flex-1">
                            <div className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-1">
                              Segment {idx + 1}
                            </div>
                            <div className="text-sm text-gray-700 dark:text-gray-300">
                              {s.rules_readable || (Array.isArray(s.rules) && s.rules.length > 0 ? s.rules.join(' AND ') : 'All data')}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

            </div>
          ) : (
            <div className="text-center py-6 text-gray-500">
              <p className="text-sm">Run segmentation to see results here.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );

  if (!isVisible) return null;

  return (
    <>
      {/* Width Indicator */}
      {showWidthIndicator && (
        <div className="fixed top-20 right-4 bg-gray-900 text-white px-3 py-2 rounded-lg text-sm font-mono z-[60] pointer-events-none">
          {sidebarWidth}px
        </div>
      )}
      
      {/* Mobile overlay */}
      <div 
        className="fixed inset-0 bg-black bg-opacity-50 z-40 lg:hidden"
        onClick={onClose}
      />
      
      {/* Sidebar */}
      <aside 
        className={`fixed right-0 top-16 h-[calc(100vh-4rem)] bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-700 shadow-lg transition-all duration-300 z-50 group ${
          collapsed ? 'w-16' : ''
        } ${
          isVisible ? 'translate-x-0' : 'translate-x-full'
        }`}
                 style={{ 
           width: collapsed ? '64px' : `${sidebarWidth}px`,
           transition: isResizing ? 'none' : 'all 300ms',
           right: '12px' // Consistent gap between Model Lab and Dataset Overview
         }}
      >
        {/* Resize Handle */}
        {!collapsed && (
          <div
            ref={resizeRef}
            className="absolute left-0 top-0 w-2 h-full bg-gray-200 dark:bg-gray-700 group-hover:bg-blue-100 dark:group-hover:bg-blue-900 hover:bg-blue-400 dark:hover:bg-blue-600 cursor-col-resize z-10 transition-colors duration-200"
            onMouseDown={handleResizeStart}
            style={{ cursor: 'col-resize' }}
          >
            <div className="absolute left-1/2 top-1/2 transform -translate-x-1/2 -translate-y-1/2">
              <GripVertical className="h-4 w-4 text-gray-600 group-hover:text-blue-500 hover:text-blue-600 transition-colors" />
            </div>
          </div>
        )}
        <div className="flex flex-col h-full min-h-0 overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700 shrink-0">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 bg-gradient-to-r from-blue-500 to-teal-500 rounded-lg flex items-center justify-center">
                <Database className="h-4 w-4 text-white" />
              </div>
              {!collapsed && (
                <div>
                  <h3 className="font-semibold text-gray-900 dark:text-gray-100">{getSectionName(currentStep)}</h3>
                  <p className="text-xs text-gray-500 dark:text-gray-400">Model Builder</p>
                </div>
              )}
            </div>
            
            <div className="flex items-center space-x-1">
              <button
                onClick={() => setCollapsed(!collapsed)}
                className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              >
                {collapsed ? <ChevronLeft className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              </button>
              <button
                onClick={onClose}
                className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors lg:hidden"
                title="Close sidebar"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Tabs */}
          {!collapsed && (
            <div className="flex border-b border-gray-200 dark:border-gray-700">
              {[
                { id: 'overview', label: 'Overview', icon: BarChart3 },
                { id: 'quality', label: 'Quality', icon: CheckCircle },
                { id: 'insights', label: 'Distributions', icon: TrendingUp },
                { id: 'config', label: 'Graph', icon: Settings },
                { id: 'segmentation', label: 'Insights', icon: Users },
                { id: 'eda', label: 'EDA', icon: BarChart3 }
              ].filter(tab => {
                // Filter tabs based on restricted mode and current step
                if (restrictedMode === 'insights-only') {
                  return tab.id === 'insights';
                }
                if (currentStep === 3.5) {
                  return tab.id === 'segmentation';
                }
                // On Data Treatment page (step 2), only show the EDA tab
                if (currentStep === 2) {
                  return tab.id === 'eda';
                }
                // Hide segmentation and eda tabs for all other steps
                if (tab.id === 'segmentation' || tab.id === 'eda') {
                  return false;
                }
                return true;
              }).map((tab) => {
                const TabIcon = tab.icon;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id as any)}
                    className={`flex-1 flex items-center justify-center space-x-2 py-3 text-sm font-medium transition-colors ${
                      activeTab === tab.id
                        ? 'text-blue-600 dark:text-blue-400 border-b-2 border-blue-600 dark:border-blue-400 bg-blue-50 dark:bg-blue-900/30'
                        : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-800'
                    }`}
                  >
                    <TabIcon className="h-4 w-4" />
                    <span>{tab.label}</span>
                  </button>
                );
              })}
            </div>
          )}

          {/* View Data: shared at top for Distributions tab — column distributions (steps 1–2) + Step 3 standard/selected & auto analyses */}
          {!collapsed && activeTab === 'insights' && datasetId && (
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700 bg-gray-50/80 dark:bg-gray-900/40 shrink-0">
              <div className="flex items-center space-x-3 flex-wrap min-w-0">
                <label
                  htmlFor="insights-data-scope-select"
                  className="text-sm font-medium text-gray-700 dark:text-gray-300 whitespace-nowrap"
                >
                  View Data:
                </label>
                <select
                  id="insights-data-scope-select"
                  value={insightsDataScope}
                  disabled={isApplyingInsightsScope}
                  onChange={(e) => {
                    const v = e.target.value as DataPartitionScope;
                    void handleInsightsTabDataScopeChange(v);
                  }}
                  className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 min-w-[200px]"
                >
                  <option value="entire">Full Data (Entire)</option>
                  <option value="train">Train</option>
                  <option value="test">Test</option>
                  <option value="validation">Validation</option>
                </select>
                {isApplyingInsightsScope && (
                  <Loader className="h-4 w-4 animate-spin text-blue-500 shrink-0" aria-hidden />
                )}
              </div>
              {currentStep === 3 &&
                (selectedInsightSteps?.includes('bivariate_analysis') ||
                  selectedInsightSteps?.includes('correlation_analysis') ||
                  selectedInsightSteps?.includes('correlation_matrix') ||
                  selectedInsightSteps?.includes('iv_analysis') ||
                  selectedInsightSteps?.includes('variance_inflation_factor') ||
                  selectedInsightSteps?.includes('correlation_ratio_analysis')) && (
                  <div className="flex justify-end sm:ml-auto shrink-0">
                    <button
                      type="button"
                      onClick={() => onClearInsights && onClearInsights()}
                      className="px-3 py-1 text-xs bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 rounded-md text-gray-800 dark:text-gray-200"
                      title="Clear all analyses from right pane"
                    >
                      Clear All Analyses
                    </button>
                  </div>
                )}
            </div>
          )}

          {/* Content */}
          <div className="flex-1 min-h-0 overflow-y-auto p-4">
                         {collapsed ? (
               <div className="space-y-2">
                 {[
                   { id: 'overview', icon: BarChart3, title: 'Overview' },
                   { id: 'quality', icon: CheckCircle, title: 'Quality' },
                   { id: 'insights', icon: TrendingUp, title: 'Distributions' },
                   { id: 'config', icon: Settings, title: 'Graph' },
                   { id: 'segmentation', icon: Users, title: 'Insights' },
                   { id: 'eda', icon: BarChart3, title: 'EDA' }
                 ].filter(tab => {
                   // Filter tabs based on restricted mode and current step
                   if (restrictedMode === 'insights-only') {
                     return tab.id === 'insights';
                   }
                   if (currentStep === 3.5) {
                     return tab.id === 'segmentation';
                   }
                   // On Data Treatment page (step 2), only show the EDA tab
                   if (currentStep === 2) {
                     return tab.id === 'eda';
                   }
                   // Hide segmentation and eda tabs for all other steps
                   if (tab.id === 'segmentation' || tab.id === 'eda') {
                     return false;
                   }
                   return true;
                 }).map((tab) => {
                   const TabIcon = tab.icon;
                   return (
                                           <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id as any)}
                        className={`w-full p-2 rounded-lg transition-colors ${
                          activeTab === tab.id
                            ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400'
                            : 'hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-400'
                        }`}
                        title={tab.title}
                      >
                        <TabIcon className="h-5 w-5 mx-auto" />
                      </button>
                   );
                 })}
               </div>
            ) : (
              <div className="space-y-6">
                {shouldShowPlaceholder(currentStep) ? (
                  renderStepPlaceholder(currentStep)
                ) : (
                  <>
                {activeTab === 'overview' && renderOverviewTab()}
                {activeTab === 'quality' && renderQualityTab()}
                {activeTab === 'insights' && renderInsightsTab()}
                {activeTab === 'config' && renderConfigTab()}
                {activeTab === 'segmentation' && renderSegmentationTab()}
                {activeTab === 'eda' && renderEDAComparisonTab()}
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      </aside>

      {/* Segmentation codebook modal (Add to Data / Codebook from Insights pane) */}
      {segCodebookOpen && segCodebookData && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black bg-opacity-50 p-4"
          onClick={() => setSegCodebookOpen(false)}
        >
          <div
            className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col relative"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700 bg-gradient-to-r from-indigo-500 to-purple-600 dark:from-indigo-700 dark:to-purple-800">
              <div className="flex items-center space-x-3">
                <BookOpen className="h-6 w-6 text-white" />
                <h2 className="text-xl font-bold text-white">{segCodebookData.title}</h2>
              </div>
              <button
                type="button"
                onClick={() => setSegCodebookOpen(false)}
                className="p-1 hover:bg-white hover:bg-opacity-20 rounded-lg transition-colors"
              >
                <X className="h-6 w-6 text-white" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto px-6 py-4">
              <p className="text-gray-600 dark:text-gray-400 mb-6 italic">{segCodebookData.description}</p>
              {segCodebookData.sections.map((section, index) => (
                <div key={index} className="mb-6">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3 flex items-center">
                    <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-indigo-100 dark:bg-indigo-900/40 text-indigo-600 dark:text-indigo-400 text-sm font-bold mr-2">
                      {index + 1}
                    </span>
                    {section.title}
                  </h3>
                  <div className="bg-gray-900 rounded-lg p-4 overflow-x-auto">
                    <pre className="text-sm text-gray-100 dark:text-gray-300 font-mono whitespace-pre-wrap break-words">
                      <code>{section.content}</code>
                    </pre>
                  </div>
                </div>
              ))}
            </div>
            <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/80 flex flex-wrap justify-between items-center gap-4">
              <div className="flex items-center gap-3 flex-wrap">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Format:</span>
                  <div className="flex rounded-lg overflow-hidden border border-gray-300 dark:border-gray-600">
                    <button
                      type="button"
                      onClick={() => setSegCodebookDownloadFormat('py')}
                      className={`px-4 py-2 text-sm font-medium transition-colors ${
                        segCodebookDownloadFormat === 'py'
                          ? 'bg-green-600 dark:bg-green-700 text-white'
                          : 'bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600'
                      }`}
                    >
                      .py
                    </button>
                    <button
                      type="button"
                      onClick={() => setSegCodebookDownloadFormat('ipynb')}
                      className={`px-4 py-2 text-sm font-medium transition-colors border-l border-gray-300 dark:border-gray-600 ${
                        segCodebookDownloadFormat === 'ipynb'
                          ? 'bg-green-600 dark:bg-green-700 text-white'
                          : 'bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600'
                      }`}
                    >
                      .ipynb
                    </button>
                    <button
                      type="button"
                      onClick={() => setSegCodebookDownloadFormat('csv')}
                      className={`px-4 py-2 text-sm font-medium transition-colors border-l border-gray-300 dark:border-gray-600 ${
                        segCodebookDownloadFormat === 'csv'
                          ? 'bg-green-600 dark:bg-green-700 text-white'
                          : 'bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600'
                      }`}
                    >
                      .csv
                    </button>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={handleSegCodebookDownload}
                  className="px-6 py-2 bg-green-600 dark:bg-green-700 text-white rounded-lg hover:bg-green-700 dark:hover:bg-green-600 transition-colors flex items-center gap-2"
                >
                  <Download className="h-4 w-4" />
                  Download
                </button>
              </div>
              <button
                type="button"
                onClick={() => setSegCodebookOpen(false)}
                className="px-6 py-2 bg-gray-600 dark:bg-gray-700 text-white rounded-lg hover:bg-gray-700 dark:hover:bg-gray-600 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Raw Data Modal */}
      {showRawDataModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-[60] flex items-center justify-center p-4">
          <div className="bg-white dark:bg-gray-900 rounded-lg shadow-xl max-w-4xl w-full max-h-[80vh] overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Column Stats</h3>
              <div className="flex items-center space-x-2">
                <button
                  onClick={downloadPreviewAsCSV}
                  disabled={rawData.length === 0}
                  className="flex items-center space-x-2 px-3 py-1.5 bg-green-600 text-white text-sm font-medium rounded-md hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  title="Download previewed data as CSV"
                >
                  <Download className="h-4 w-4" />
                  <span>Download CSV</span>
                </button>
                <button
                  onClick={() => setShowRawDataModal(false)}
                  className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                  title="Close preview"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
            </div>
            <div className="overflow-auto max-h-[60vh]">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 dark:bg-gray-700 sticky top-0">
                  <tr>
                    {rawData.length > 0 && Object.keys(rawData[0]).map((column) => (
                      <th key={column} className="px-4 py-2 text-left font-medium text-gray-700 dark:text-gray-300 border-b dark:border-gray-600">
                        {column}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rawData.map((row, index) => (
                    <tr key={index} className="border-b dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50">
                      {Object.values(row).map((value, colIndex) => (
                        <td key={colIndex} className="px-4 py-2 text-gray-900 dark:text-gray-100">
                          {value === null || value === undefined ? '-' : String(value)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="p-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
              <div className="flex items-center justify-between">
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Showing {rawData.length} rows of data
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Click "Download CSV" to save these {rawData.length} rows to your computer
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Configuration Modal */}
      {showConfigModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-[60] flex items-center justify-center p-4">
          <div className="bg-white dark:bg-gray-900 rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Edit Configuration</h3>
              <button
                onClick={() => {
                  setShowConfigModal(false);
                  setDataDictionaryFile(null);
                }}
                className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="p-4 space-y-4 overflow-y-auto max-h-[calc(80vh-180px)]">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Target Variable
                </label>
                <select
                  value={configForm.target_variable}
                  onChange={(e) => setConfigForm(prev => ({ ...prev, target_variable: e.target.value }))}
                  className="w-full p-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="">Select target variable</option>
                  {datasetAnalysis?.columns.map((col) => (
                    <option key={col.name} value={col.name}>
                      {col.name}
                    </option>
                  ))}
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Target Variable Type
                </label>
                <select
                  value={configForm.target_variable_type}
                  onChange={(e) => setConfigForm(prev => ({ ...prev, target_variable_type: e.target.value as 'Numerical' | 'Categorical' }))}
                  className="w-full p-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="Numerical">Numerical</option>
                  <option value="Categorical">Categorical</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Problem Statement
                </label>
                <textarea
                  value={configForm.problem_statement}
                  onChange={(e) => setConfigForm(prev => ({ ...prev, problem_statement: e.target.value }))}
                  rows={3}
                  className="w-full p-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="Describe the problem you're trying to solve..."
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Data Dictionary (CSV File)
                </label>
                
                {!dataDictionaryFile ? (
                  <div className="relative">
                    <input
                      id="edit-config-data-dictionary-upload"
                      type="file"
                      accept=".csv"
                      onChange={handleDataDictionaryFileSelect}
                      className="hidden"
                    />
                    <label
                      htmlFor="edit-config-data-dictionary-upload"
                      className="w-full px-3 py-2 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg cursor-pointer hover:border-blue-400 dark:hover:border-blue-500 transition-colors flex items-center justify-center bg-gray-50 dark:bg-gray-800 hover:bg-blue-50 dark:hover:bg-gray-700"
                    >
                      <div className="text-center py-4">
                        <Upload className="h-5 w-5 text-gray-400 dark:text-gray-500 mx-auto mb-1" />
                        <span className="text-sm text-gray-600 dark:text-gray-400 block">Upload CSV file with column descriptions</span>
                        <span className="text-xs text-gray-500 dark:text-gray-500 block mt-1">Click to browse or drag and drop</span>
                      </div>
                    </label>
                  </div>
                ) : (
                  <div className="flex items-center justify-between p-3 border border-gray-300 dark:border-green-700 rounded-lg bg-green-50 dark:bg-green-900/20">
                    <div className="flex items-center space-x-2">
                      <FileText className="h-5 w-5 text-green-600 dark:text-green-400" />
                      <div>
                        <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{dataDictionaryFile.name}</p>
                        <p className="text-xs text-gray-500 dark:text-gray-400">{(dataDictionaryFile.size / 1024).toFixed(2)} KB</p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={handleRemoveDataDictionaryFile}
                      className="p-1 hover:bg-red-100 dark:hover:bg-red-900/30 rounded-full transition-colors"
                      title="Remove file"
                    >
                      <X className="h-4 w-4 text-red-600 dark:text-red-400" />
                    </button>
                  </div>
                )}
                
                {localDatasetConfig?.data_dictionary && !dataDictionaryFile && (
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    Current: {typeof localDatasetConfig.data_dictionary === 'string' && localDatasetConfig.data_dictionary.length > 50
                      ? localDatasetConfig.data_dictionary.substring(0, 50) + '...'
                      : localDatasetConfig.data_dictionary}
                  </p>
                )}
              </div>
            </div>
            <div className="flex items-center justify-end space-x-3 p-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
              <button
                onClick={() => {
                  setShowConfigModal(false);
                  setDataDictionaryFile(null);
                }}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveConfig}
                disabled={isLoadingConfig}
                className="px-4 py-2 text-sm font-medium text-white dark:text-[#ccccff] bg-blue-600 dark:bg-[#292966] border border-transparent rounded-md hover:bg-blue-700 dark:hover:bg-[#333380] transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
              >
                {isLoadingConfig ? (
                  <>
                    <Loader className="h-4 w-4 animate-spin" />
                    <span>Saving...</span>
                  </>
                ) : (
                  <>
                    <Save className="h-4 w-4" />
                    <span>Save Changes</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}


      {/* No Data Dictionary Modal */}
      {showNoDictionaryModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-[60] flex items-center justify-center p-4">
          <div className="bg-white dark:bg-gray-900 rounded-lg shadow-xl max-w-md w-full p-6">
            <div className="flex items-start space-x-4">
              <div className="flex-shrink-0">
                <AlertTriangle className="h-12 w-12 text-amber-500" />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">No Data Dictionary Found</h3>
                <p className="text-gray-600 dark:text-gray-400 mb-4">
                  A data dictionary is required to generate the feature graph. Please upload a data dictionary to use this feature.
                </p>
                <div className="flex justify-end">
                  <button
                    onClick={() => setShowNoDictionaryModal(false)}
                    className="px-4 py-2 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] transition-colors"
                  >
                    OK
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Configuration Update Success Modal */}
      {showConfigSuccessModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-[60] flex items-center justify-center p-4">
          <div className="bg-white dark:bg-gray-900 rounded-lg shadow-xl max-w-md w-full p-6">
            <div className="flex items-start space-x-4">
              <div className="flex-shrink-0">
                <CheckCircle className="h-12 w-12 text-green-500" />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">Configuration Updated Successfully!</h3>
                <p className="text-gray-600 dark:text-gray-400 mb-4">
                  Your dataset configuration has been saved and the changes are now active. You can now use features like Feature Graph with the uploaded data dictionary.
                </p>
                <div className="flex justify-end">
                  <button
                    onClick={() => setShowConfigSuccessModal(false)}
                    className="px-4 py-2 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] transition-colors"
                  >
                    Continue
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Fullscreen Chart Modal */}
      {expandedChart && activeSegmentationResult && (
        <div className="fixed inset-0 bg-black bg-opacity-75 z-50 flex items-center justify-center p-8">
          <div className="bg-white dark:bg-gray-900 rounded-lg shadow-2xl w-full h-full max-w-7xl max-h-[90vh] flex flex-col">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
              <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
                {expandedChart === 'sizes' ? 'Segment Sizes' : 'Segment Proportions'}
              </h3>
              <button
                onClick={() => setExpandedChart(null)}
                className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                title="Close"
              >
                <X className="w-6 h-6 text-gray-600" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="flex-1 p-6 overflow-auto">
              <div className="h-full flex items-center justify-center">
                {(() => {
                  const segments = activeSegmentationResult.segments || [];
                  const hasSegRows = Array.isArray(segments) && segments.length > 0;
                  const segmentCounts = hasSegRows
                    ? segments.map((s: any) => Number(s.record_count ?? s.size ?? 0) || 0)
                    : (activeSegmentationResult.viability?.segment_counts || []).map((n: number) => Number(n) || 0);
                  const totalForProp = segmentCounts.reduce((a: number, b: number) => a + b, 0);
                  const segmentProportions = hasSegRows
                    ? segmentCounts.map((c: number) => (totalForProp > 0 ? c / totalForProp : 0))
                    : activeSegmentationResult.viability?.segment_proportions || [];
                  const segmentEventRates = hasSegRows
                    ? segments.map((s: any) => segmentEventRateToFraction(s.event_rate))
                    : activeSegmentationResult.viability?.segment_event_rates
                      ? activeSegmentationResult.viability.segment_event_rates.map((r: number) => segmentEventRateToFraction(r))
                      : [];
                  
                  const totalRecords = segmentCounts.reduce((sum: number, c: number) => sum + c, 0);
                  const totalEvents = segmentCounts.reduce((sum: number, c: number, i: number) => {
                    const s = segments[i];
                    if (s && s.event_count != null && Number.isFinite(Number(s.event_count))) {
                      return sum + Number(s.event_count);
                    }
                    return sum + Math.round(c * (segmentEventRates[i] ?? 0));
                  }, 0);
                  const populationAvgEventRate = totalRecords > 0 ? totalEvents / totalRecords : 0;
                  
                  const z = 1.96;
                  const calculateWilsonCI = (n: number, p: number): { lower: number; upper: number } => {
                    if (n === 0) return { lower: 0, upper: 0 };
                    const denominator = 1 + z * z / n;
                    const center = (p + z * z / (2 * n)) / denominator;
                    const halfWidth = (z / denominator) * Math.sqrt(p * (1 - p) / n + z * z / (4 * n * n));
                    return { lower: Math.max(0, center - halfWidth), upper: Math.min(1, center + halfWidth) };
                  };
                  
                  const ciData = segmentCounts.map((count: number, i: number) => {
                    const s = segments[i];
                    const n = s ? Number(s.record_count ?? s.size ?? 0) || 0 : count;
                    const p = s ? segmentEventRateToFraction(s.event_rate) : (segmentEventRates[i] ?? 0);
                    return calculateWilsonCI(n, p);
                  });
                  const ciUpperExpanded = ciData.map((ci: any) => ci.upper);
                  const ciLowerExpanded = ciData.map((ci: any) => ci.lower);
                  
                  return (
                    <>
                      {expandedChart === 'sizes' && segmentCounts.length > 0 && (
                        <div style={{ width: '100%', height: '100%' }}>
                          <Bar
                            data={{
                              labels: segmentCounts.map((_: any, i: number) => `Segment ${i+1}`),
                              datasets: [
                                {
                                  type: 'bar' as const,
                                  label: 'Total',
                                  data: segmentCounts,
                                  backgroundColor: [
                                    'rgba(99, 102, 241, 0.8)',
                                    'rgba(59, 130, 246, 0.8)',
                                    'rgba(16, 185, 129, 0.8)',
                                    'rgba(245, 158, 11, 0.8)',
                                    'rgba(236, 72, 153, 0.8)',
                                    'rgba(239, 68, 68, 0.8)'
                                  ],
                                  borderColor: [
                                    'rgb(99, 102, 241)',
                                    'rgb(59, 130, 246)',
                                    'rgb(16, 185, 129)',
                                    'rgb(245, 158, 11)',
                                    'rgb(236, 72, 153)',
                                    'rgb(239, 68, 68)'
                                  ],
                                  borderWidth: 2,
                                  borderRadius: 8,
                                  yAxisID: 'y'
                                },
                                ...(segmentEventRates.length > 0 ? [{
                                  type: 'line' as const,
                                  label: 'Event Rate %',
                                  data: segmentEventRates,
                                  borderColor: 'rgb(37, 99, 235)',
                                  backgroundColor: 'rgba(37, 99, 235, 0.1)',
                                  borderWidth: 4,
                                  yAxisID: 'y1',
                                  tension: 0.4,
                                  fill: false
                                }] as any : []),
                                // 95% Confidence Interval - Upper Bound (expanded)
                                ...(ciUpperExpanded.length > 0 ? [{
                                  type: 'line' as const,
                                  label: '95% CI Upper',
                                  data: ciUpperExpanded,
                                  borderColor: 'rgba(37, 99, 235, 0.3)',
                                  backgroundColor: 'transparent',
                                  borderWidth: 1,
                                  borderDash: [4, 2],
                                  pointRadius: 0,
                                  yAxisID: 'y1',
                                  tension: 0.4,
                                  fill: false
                                }] as any : []),
                                // 95% Confidence Interval - Lower Bound (expanded)
                                ...(ciLowerExpanded.length > 0 ? [{
                                  type: 'line' as const,
                                  label: '95% CI Lower',
                                  data: ciLowerExpanded,
                                  borderColor: 'rgba(37, 99, 235, 0.3)',
                                  backgroundColor: 'transparent',
                                  borderWidth: 1,
                                  borderDash: [4, 2],
                                  pointRadius: 0,
                                  yAxisID: 'y1',
                                  tension: 0.4,
                                  fill: false
                                }] as any : []),
                                // Population Average Reference Line (expanded modal)
                                ...(populationAvgEventRate > 0 ? [{
                                  type: 'line' as const,
                                  label: `Pop. Avg: ${(populationAvgEventRate * 100).toFixed(2)}%`,
                                  data: Array(segmentCounts.length).fill(populationAvgEventRate),
                                  borderColor: 'rgb(239, 68, 68)',
                                  backgroundColor: 'transparent',
                                  borderWidth: 2,
                                  borderDash: [10, 5],
                                  pointRadius: 0,
                                  pointHoverRadius: 0,
                                  yAxisID: 'y1',
                                  tension: 0
                                }] as any : [])
                              ]
                            }}
                            options={{ 
                              responsive: true, 
                              maintainAspectRatio: false,
                              interaction: {
                                mode: 'index' as const,
                                intersect: false
                              },
                              datasets: {
                                bar: {
                                  minBarLength: 6
                                }
                              },
                              plugins: { 
                                legend: { 
                                  display: true,
                                  position: 'top' as const,
                                  labels: {
                                    padding: 20,
                                    font: {
                                      size: 14
                                    },
                                    usePointStyle: true,
                                    boxHeight: 8,
                                    // Filter out CI bounds from legend
                                    filter: (item: any) => !item.text.includes('CI')
                                  }
                                },
                                tooltip: {
                                  backgroundColor: 'rgba(0, 0, 0, 0.8)',
                                  padding: 16,
                                  titleColor: '#fff',
                                  bodyColor: '#fff',
                                  borderColor: 'rgba(255, 255, 255, 0.2)',
                                  borderWidth: 1,
                                  titleFont: {
                                    size: 14
                                  },
                                  bodyFont: {
                                    size: 13
                                  },
                                  callbacks: {
                                    label: function(context: any) {
                                      let label = context.dataset.label || '';
                                      if (label) {
                                        label += ': ';
                                      }
                                      if (context.parsed.y !== null) {
                                        if (context.dataset.yAxisID === 'y1') {
                                          const value = context.parsed.y;
                                          if (value <= 1) {
                                            label += (value * 100).toFixed(2) + '%';
                                          } else {
                                            label += value.toFixed(2);
                                          }
                                        } else {
                                          label += context.parsed.y.toLocaleString();
                                        }
                                      }
                                      return label;
                                    }
                                  }
                                }
                              },
                              scales: {
                                y: {
                                  type: 'linear' as const,
                                  display: true,
                                  position: 'left' as const,
                                  beginAtZero: true,
                                  title: {
                                    display: true,
                                    text: 'Total Records',
                                    font: {
                                      size: 14,
                                      weight: 'bold'
                                    }
                                  },
                                  grid: {
                                    color: isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.05)'
                                  },
                                  ticks: {
                                    font: {
                                      size: 12
                                    },
                                    color: isDark ? '#9ca3af' : undefined
                                  }
                                },
                                ...(segmentEventRates.length > 0 ? {
                                  y1: {
                                    type: 'linear' as const,
                                    display: true,
                                    position: 'right' as const,
                                    beginAtZero: true,
                                    title: {
                                      display: true,
                                      text: 'Event Rate %',
                                      font: {
                                        size: 14,
                                        weight: 'bold'
                                      },
                                      color: isDark ? '#d1d5db' : undefined
                                    },
                                    grid: {
                                      drawOnChartArea: false
                                    },
                                    ticks: {
                                      font: {
                                        size: 12
                                      },
                                      color: isDark ? '#9ca3af' : undefined
                                    }
                                  }
                                } : {}),
                                x: {
                                  grid: {
                                    display: false
                                  },
                                  ticks: {
                                    font: {
                                      size: 12
                                    },
                                    color: isDark ? '#9ca3af' : undefined
                                  }
                                }
                              }
                            }}
                          />
                        </div>
                      )}

                      {expandedChart === 'proportions' && segmentProportions.length > 0 && (
                        <div style={{ width: '70%', height: '100%' }}>
                          <Pie
                            data={{
                              labels: segmentProportions.map((_: any, i: number) => `Segment ${i+1}`),
                              datasets: [{
                                label: 'Proportion',
                                data: segmentProportions,
                                backgroundColor: [
                                  'rgba(99, 102, 241, 0.8)',
                                  'rgba(59, 130, 246, 0.8)',
                                  'rgba(16, 185, 129, 0.8)',
                                  'rgba(245, 158, 11, 0.8)',
                                  'rgba(236, 72, 153, 0.8)',
                                  'rgba(239, 68, 68, 0.8)'
                                ],
                                borderColor: [
                                  'rgb(99, 102, 241)',
                                  'rgb(59, 130, 246)',
                                  'rgb(16, 185, 129)',
                                  'rgb(245, 158, 11)',
                                  'rgb(236, 72, 153)',
                                  'rgb(239, 68, 68)'
                                ],
                                borderWidth: 3
                              }]
                            }}
                            options={{ 
                              responsive: true, 
                              maintainAspectRatio: false,
                              plugins: { 
                                legend: { 
                                  position: 'bottom',
                                  labels: {
                                    padding: 20,
                                    font: {
                                      size: 14
                                    },
                                    usePointStyle: true,
                                    pointStyle: 'circle',
                                    boxHeight: 12
                                  }
                                },
                                tooltip: {
                                  backgroundColor: 'rgba(0, 0, 0, 0.8)',
                                  padding: 16,
                                  titleColor: '#fff',
                                  bodyColor: '#fff',
                                  borderColor: 'rgba(255, 255, 255, 0.2)',
                                  borderWidth: 1,
                                  titleFont: {
                                    size: 14
                                  },
                                  bodyFont: {
                                    size: 13
                                  },
                                  callbacks: {
                                    label: function(context: any) {
                                      const label = context.label || '';
                                      const value = context.parsed || 0;
                                      const percentage = (value * 100).toFixed(1);
                                      return `${label}: ${percentage}%`;
                                    }
                                  }
                                }
                              }
                            }}
                          />
                        </div>
                      )}
                    </>
                  );
                })()}
              </div>
            </div>
          </div>
        </div>
      )}
      
      {/* Cutoff Edit Modal */}
      {showCutoffEditModal && editingSegment && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl max-w-lg w-full p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
                <Edit3 className="w-5 h-5 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Edit Cutoff Value</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">Segment {editingSegment.segment_id}</p>
              </div>
            </div>
            
            {/* Current Rule */}
            <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4 mb-4">
              <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Current Rule</div>
              <div className="font-mono text-sm text-gray-800 dark:text-gray-200">
                {editingSegment.rule_definition}
              </div>
            </div>
            
            {/* Edit Input */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                New value for <span className="font-mono text-blue-600 dark:text-blue-400">{editingSegment.variable}</span>
              </label>
              <div className="flex items-center gap-2">
                <span className="text-gray-600 dark:text-gray-400">{editingSegment.variable} {editingSegment.operator}</span>
                <input
                  type="number"
                  value={cutoffEditValue}
                  onChange={(e) => {
                    setCutoffEditValue(e.target.value);
                    setCutoffEditPreview(null); // Clear preview when value changes
                  }}
                  className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  step="any"
                />
                <button
                  onClick={handlePreviewCutoff}
                  disabled={isLoadingCutoffPreview}
                  className="px-4 py-2 text-sm font-medium text-blue-700 dark:text-blue-300 bg-blue-100 dark:bg-blue-900/30 hover:bg-blue-200 dark:hover:bg-blue-800/30 rounded-lg transition-colors disabled:opacity-50"
                >
                  {isLoadingCutoffPreview ? 'Loading...' : 'Preview'}
                </button>
              </div>
            </div>
            
            {/* Impact Preview */}
            {cutoffEditPreview && (
              <div className={`mb-4 p-4 rounded-lg border ${
                cutoffEditPreview.below_min_size 
                  ? 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-700' 
                  : 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-700'
              }`}>
                <div className="flex items-center gap-2 mb-3">
                  {cutoffEditPreview.below_min_size ? (
                    <AlertTriangle className="w-5 h-5 text-red-600 dark:text-red-400" />
                  ) : (
                    <CheckCircle className="w-5 h-5 text-green-600 dark:text-green-400" />
                  )}
                  <span className="font-semibold text-gray-900 dark:text-gray-100">Impact Preview</span>
                </div>
                
                {cutoffEditPreview.below_min_size && (
                  <div className="mb-3 p-2 bg-red-100 dark:bg-red-800/30 rounded text-sm text-red-800 dark:text-red-300">
                    Warning: This change would reduce the segment below the minimum size threshold!
                  </div>
                )}
                
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">Records moved out:</span>
                    <span className="ml-2 font-medium text-gray-900 dark:text-gray-100">
                      {cutoffEditPreview.records_moved_out.toLocaleString()}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">Records moved in:</span>
                    <span className="ml-2 font-medium text-gray-900 dark:text-gray-100">
                      {cutoffEditPreview.records_moved_in.toLocaleString()}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">New count:</span>
                    <span className="ml-2 font-medium text-gray-900 dark:text-gray-100">
                      {cutoffEditPreview.new_record_count.toLocaleString()}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">New event rate:</span>
                    <span className="ml-2 font-medium text-gray-900 dark:text-gray-100">
                      {(segmentEventRateToFraction(cutoffEditPreview.new_event_rate) * 100).toFixed(2)}%
                    </span>
                  </div>
                  <div className="col-span-2">
                    <span className="text-gray-500 dark:text-gray-400">IV change:</span>
                    <span className={`ml-2 font-medium ${
                      cutoffEditPreview.iv_change > 0 ? 'text-green-600 dark:text-green-400' :
                      cutoffEditPreview.iv_change < 0 ? 'text-red-600 dark:text-red-400' :
                      'text-gray-600 dark:text-gray-400'
                    }`}>
                      {cutoffEditPreview.iv_change >= 0 ? '+' : ''}{cutoffEditPreview.iv_change.toFixed(4)}
                      <span className="text-gray-500 dark:text-gray-400 ml-1">
                        ({cutoffEditPreview.iv_before.toFixed(4)} → {cutoffEditPreview.iv_after.toFixed(4)})
                      </span>
                    </span>
                  </div>
                </div>
                
                {/* New Rule Preview */}
                <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-600">
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">New Rule</div>
                  <div className="font-mono text-sm text-blue-600 dark:text-blue-400">
                    {cutoffEditPreview.new_rule}
                  </div>
                </div>
              </div>
            )}
            
            {/* Actions */}
            <div className="flex justify-end gap-3">
              <button
                onClick={() => {
                  setShowCutoffEditModal(false);
                  setEditingSegment(null);
                  setCutoffEditPreview(null);
                  setCutoffEditValue('');
                }}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleApplyCutoff}
                disabled={isLoadingCutoffPreview || !cutoffEditPreview}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Check className="w-4 h-4" />
                Apply Change
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default DatasetOverviewSidebar;

