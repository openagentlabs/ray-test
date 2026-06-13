import React, { useState, useEffect, useRef } from 'react';
import { useTheme } from '../contexts/ThemeContext';
import { 
  TrendingUp, 
  Loader, 
  AlertTriangle,
  Maximize2,
  Minimize2,
  X,
  FileDown,
  BarChart3,
} from 'lucide-react';
import { 
  correlationAnalysisService, 
  CorrelationAnalysisResponse,
  CorrelationData,
  CorrelationResultDetail,
} from '../services/correlationAnalysisService';

// Import Chart.js components
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import type { Chart } from 'chart.js';
import { Bar } from 'react-chartjs-2';
import {
  chartToPngBase64,
  downloadExcelWorkbookWithCharts,
  flushChartDraw,
  type ReportCell,
} from '../utils/excelReportWithCharts';
import {
  chartJsDefaultFontColor,
  chartJsScaleBorder,
  chartJsTooltipColors,
} from '../utils/chartJsTheme';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
);

// Global cache that persists across component mounts/unmounts
interface CachedCorrelationData {
  analysisResults: CorrelationAnalysisResponse | null;
  analysisKey: string;
  timestamp: number;
}

const correlationCache = new Map<string, CachedCorrelationData>();
const CACHE_EXPIRY_MS = 10 * 60 * 1000; // 10 minutes

const getCachedCorrelationData = (key: string): CachedCorrelationData | null => {
  const cached = correlationCache.get(key);
  if (cached && (Date.now() - cached.timestamp) < CACHE_EXPIRY_MS) {
    return cached;
  }
  if (cached) {
    correlationCache.delete(key); // Remove expired data
  }
  return null;
};

const setCachedCorrelationData = (key: string, data: CachedCorrelationData) => {
  correlationCache.set(key, { ...data, timestamp: Date.now() });
};

function correlationVsTargetMethodologyAoA(threshold: number): (string | number)[][] {
  return [
    ['Section', 'Detail'],
    ['Purpose', 'Each feature is compared to the model target variable.'],
    [
      'Numeric features',
      'Pearson r: linear association on pairwise complete observations. Spearman r: rank-based (monotonic) association, more robust to outliers. The backend uses max(|Pearson|, |Spearman|) against the configured threshold for the significance flag.',
    ],
    [
      'Categorical features',
      'Chi-square test of independence between feature and target; Cramér’s V (0–1) summarizes association strength from the contingency table.',
    ],
    [
      'Significance',
      `A variable is flagged when that strength metric is ≥ ${threshold} (same threshold as the analysis request).`,
    ],
    [
      'UI charts',
      'Pearson: numeric features passing the threshold. Cramér’s V: categorical features passing the same threshold.',
    ],
    [
      'Workbook',
      'This export contains Methodology, Report info, Dataset overview, All variables, and Pearson / Cramér chart images when those charts are on screen.',
    ],
  ];
}

function buildCramersVChartRows(
  full: CorrelationResultDetail[] | undefined,
  threshold: number
): CorrelationData[] {
  if (!full?.length) return [];
  return full
    .filter(
      (r) =>
        (r.variable_type === 'categorical' || r.variable_type === 'object') &&
        r.cramers_v != null &&
        !Number.isNaN(Number(r.cramers_v)) &&
        Number(r.cramers_v) >= threshold
    )
    .map((r) => ({
      variable_name: r.variable_name,
      correlation_value: Number(r.cramers_v),
      variable_type: 'categorical' as const,
    }))
    .sort((a, b) => b.correlation_value - a.correlation_value);
}

/** All numeric features vs target (Pearson), for client-side threshold filtering. */
function buildPearsonChartRows(full: CorrelationResultDetail[] | undefined): CorrelationData[] {
  if (!full?.length) return [];
  return full
    .filter((r) => {
      const vt = (r.variable_type || '').toLowerCase();
      const isNumeric = vt === 'numeric' || vt === 'numerical';
      return (
        isNumeric &&
        r.pearson_correlation != null &&
        !Number.isNaN(Number(r.pearson_correlation))
      );
    })
    .map((r) => ({
      variable_name: r.variable_name,
      correlation_value: Number(r.pearson_correlation),
      variable_type: 'numerical' as const,
    }))
    .sort((a, b) => Math.abs(b.correlation_value) - Math.abs(a.correlation_value));
}

// Correlation Chart Component (Pearson vs target, or Cramér's V vs target for categoricals)
interface CorrelationChartProps {
  correlations: CorrelationData[];
  targetVariable: string;
  /** Pearson: |r| vs threshold. Cramér's V: values in [0,1] vs same numeric threshold. */
  mode?: 'pearson' | 'cramersV';
  significanceThreshold?: number;
  chartRef?: React.Ref<Chart<'bar'>>;
}

const CorrelationChart: React.FC<CorrelationChartProps> = ({
  correlations,
  targetVariable,
  mode = 'pearson',
  significanceThreshold = 0.05,
  chartRef,
}) => {
  const { isDark, theme } = useTheme();
  const [isExpanded, setIsExpanded] = useState(false);
  
  // Handle escape key to close expanded view
  useEffect(() => {
    const handleEscapeKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isExpanded) {
        setIsExpanded(false);
      }
    };

    if (isExpanded) {
      document.addEventListener('keydown', handleEscapeKey);
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }

    return () => {
      document.removeEventListener('keydown', handleEscapeKey);
      document.body.style.overflow = 'unset';
    };
  }, [isExpanded]);
  
  console.log('📊 CorrelationChart received data:', correlations);
  console.log('📊 CorrelationChart data type:', typeof correlations);
  console.log('📊 CorrelationChart data length:', correlations?.length);
  
  if (!correlations || correlations.length === 0) {
    console.log('❌ No correlation data available');
    return (
      <div className="text-center text-gray-500 dark:text-gray-400 py-8">
        <p>No correlation data available</p>
      </div>
    );
  }

  const isCramers = mode === 'cramersV';
  const thresholdForFilter = isCramers
    ? Math.min(1, Math.max(0, significanceThreshold))
    : Math.abs(significanceThreshold);
  const filteredCorrelations = correlations
    .filter((corr) =>
      isCramers
        ? corr.correlation_value >= thresholdForFilter
        : Math.abs(corr.correlation_value) >= thresholdForFilter
    )
    .sort((a, b) =>
      isCramers
        ? b.correlation_value - a.correlation_value
        : Math.abs(b.correlation_value) - Math.abs(a.correlation_value)
    );

  if (filteredCorrelations.length === 0) {
    return (
      <div className="text-center text-gray-500 dark:text-gray-400 py-8">
        <p>
          {isCramers
            ? `No categorical features meet Cramér's V threshold (≥ ${thresholdForFilter})`
            : `No variables meet the correlation threshold (|r| ≥ ${thresholdForFilter})`}
        </p>
      </div>
    );
  }

  const chartData = {
    labels: filteredCorrelations.map((corr) => corr.variable_name),
    datasets: [
      {
        label: isCramers ? "Cramér's V with target" : 'Pearson correlation with target',
        data: filteredCorrelations.map((corr) => corr.correlation_value),
        backgroundColor: isCramers
          ? filteredCorrelations.map(() =>
              isDark ? 'rgba(96, 165, 250, 0.55)' : 'rgba(59, 130, 246, 0.6)'
            )
          : filteredCorrelations.map((corr) =>
              corr.correlation_value >= 0
                ? isDark
                  ? 'rgba(96, 165, 250, 0.65)'
                  : 'rgba(13, 110, 253, 0.7)'
                : isDark
                  ? 'rgba(248, 113, 113, 0.6)'
                  : 'rgba(220, 53, 69, 0.7)'
            ),
        borderColor: isCramers
          ? filteredCorrelations.map(() =>
              isDark ? 'rgba(147, 197, 253, 1)' : 'rgba(59, 130, 246, 1)'
            )
          : filteredCorrelations.map((corr) =>
              corr.correlation_value >= 0
                ? isDark
                  ? 'rgba(186, 230, 253, 1)'
                  : 'rgba(13, 110, 253, 1)'
                : isDark
                  ? 'rgba(254, 202, 202, 1)'
                  : 'rgba(220, 53, 69, 1)'
            ),
        borderWidth: 1,
      },
    ],
  };

  const chartOptions = {
    color: chartJsDefaultFontColor(isDark),
    indexAxis: 'y' as const, // Horizontal bar chart
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'nearest' as const,
      intersect: true,
    },
    plugins: {
      title: {
        display: true,
        text: isCramers
          ? `Cramér's V with ${targetVariable} (≥ ${thresholdForFilter})`
          : `Pearson correlation with ${targetVariable} (|r| ≥ ${thresholdForFilter})`,
        font: {
          size: 14,
          weight: 'bold' as const,
        },
        color: isDark ? '#e5e7eb' : '#374151',
        padding: {
          bottom: 20,
        },
      },
      legend: {
        display: false, // Hide legend for cleaner look
      },
      tooltip: {
        ...chartJsTooltipColors(isDark),
        callbacks: {
          label: function (context: any) {
            const value = context.parsed.x;
            const label = context.label || '';
            return isCramers
              ? `${label}: ${value.toFixed(4)} (Cramér's V)`
              : `${label}: ${value.toFixed(4)} (Pearson)`;
          },
        },
      },
    },
    scales: {
      x: {
        border: chartJsScaleBorder(isDark),
        // Correlation values axis
        grid: {
          display: true,
          color: isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
        },
        ticks: {
          color: isDark ? '#d1d5db' : '#374151',
          font: {
            size: 11,
            weight: 'bold' as const,
          },
        },
        title: {
          display: true,
          text: isCramers ? "Cramér's V (0–1)" : 'Pearson correlation value',
          color: isDark ? '#d1d5db' : '#374151',
          font: {
            size: 12,
            weight: 'bold' as const,
          },
        },
        max: isCramers ? 1 : undefined,
        min: isCramers ? 0 : undefined,
      },
      y: {
        border: chartJsScaleBorder(isDark),
        // Variable names axis
        grid: {
          display: false,
        },
        ticks: {
          color: isDark ? '#d1d5db' : '#374151',
          font: {
            size: 11,
            weight: 'bold' as const,
          },
        },
      },
    },
  };

  const handleToggleExpand = () => {
    setIsExpanded(!isExpanded);
  };

  const chartComponent = (
    <div className={`relative bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 ${isExpanded ? 'p-6' : 'p-4'}`}>
      {/* Expand/Collapse Button */}
      <button
        onClick={handleToggleExpand}
        className="absolute top-2 right-2 z-10 p-2 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
        title={isExpanded ? "Minimize chart" : "Expand chart"}
      >
        {isExpanded ? (
          <Minimize2 className="h-4 w-4" />
        ) : (
          <Maximize2 className="h-4 w-4" />
        )}
      </button>

      {/* Chart */}
      <div className={isExpanded ? 'h-96' : 'h-80'}>
        <Bar key={theme} ref={chartRef} data={chartData} options={chartOptions} />
      </div>

      {/* Summary Stats - Hidden */}
      {/* <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
        <div className="bg-blue-50 p-3 rounded-lg">
          <div className="text-blue-800 font-medium">Variables Above Threshold</div>
          <div className="text-blue-600 text-lg font-bold">{filteredCorrelations.length}</div>
        </div>
        <div className="bg-green-50 p-3 rounded-lg">
          <div className="text-green-800 font-medium">Total Variables Analyzed</div>
          <div className="text-green-600 text-lg font-bold">{correlations.length}</div>
        </div>
      </div> */}
    </div>
  );

  if (isExpanded) {
    return (
      <>
        {/* Backdrop */}
        <div 
          className="fixed inset-0 bg-black bg-opacity-50 z-40"
          onClick={handleToggleExpand}
        />
        
        {/* Expanded Chart Modal */}
        <div className="fixed inset-4 z-50 overflow-auto">
          <div className="min-h-full flex items-center justify-center p-4">
            <div className="w-full max-w-6xl mx-auto">
              {/* Modal Header */}
              <div className="bg-white dark:bg-gray-800 rounded-t-lg border-b border-gray-200 dark:border-gray-700 px-6 py-4 flex items-center justify-between">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  {isCramers
                    ? "Cramér's V vs target — expanded view"
                    : 'Pearson correlation analysis — expanded view'}
                </h3>
                <button
                  onClick={handleToggleExpand}
                  className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                  title="Close expanded view"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
              
              {/* Expanded Chart */}
              <div className="bg-white dark:bg-gray-800 rounded-b-lg p-6">
                <div className="h-96">
                  <Bar
                    key={`${theme}-expanded`}
                    ref={chartRef}
                    data={chartData}
                    options={{
                      ...chartOptions,
                      plugins: {
                        ...chartOptions.plugins,
                        title: {
                          ...chartOptions.plugins.title,
                          display: false, // Hide title in expanded view since it's in header
                        },
                      },
                    }}
                  />
                </div>
                
                {/* Summary Stats in expanded view - Hidden */}
                {/* <div className="mt-4 grid grid-cols-3 gap-4 text-sm">
                  <div className="bg-blue-50 p-3 rounded-lg">
                    <div className="text-blue-800 font-medium">Variables Above Threshold</div>
                    <div className="text-blue-600 text-lg font-bold">{filteredCorrelations.length}</div>
                  </div>
                  <div className="bg-green-50 p-3 rounded-lg">
                    <div className="text-green-800 font-medium">Total Variables Analyzed</div>
                    <div className="text-green-600 text-lg font-bold">{correlations.length}</div>
                  </div>
                  <div className="bg-orange-50 p-3 rounded-lg">
                    <div className="text-orange-800 font-medium">Threshold</div>
                    <div className="text-orange-600 text-lg font-bold">|r| ≥ 0.05</div>
                  </div>
                </div> */}
              </div>
            </div>
          </div>
        </div>
      </>
    );
  }

  return (
    <div className="w-full">
      {chartComponent}
    </div>
  );
};

interface CorrelationAnalysisComponentProps {
  datasetId: string | null;
  targetVariable: string;
  currentStep?: number;
  onAnalysisComplete?: (results: CorrelationAnalysisResponse) => void;
  /** When true (standard/selected insights), show display threshold sliders for Pearson and Cramér charts. */
  enableDisplayThresholdControls?: boolean;
}

const CorrelationAnalysisComponent: React.FC<CorrelationAnalysisComponentProps> = ({
  datasetId,
  targetVariable,
  currentStep = 3,
  onAnalysisComplete,
  enableDisplayThresholdControls = false,
}) => {
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResults, setAnalysisResults] = useState<CorrelationAnalysisResponse | null>(null);
  const [error, setError] = useState<string>('');
  const [isExcelDownloading, setIsExcelDownloading] = useState(false);
  const [pearsonDisplayThreshold, setPearsonDisplayThreshold] = useState(0.05);
  const [cramersDisplayThreshold, setCramersDisplayThreshold] = useState(0.05);

  const mountedRef = useRef(true);
  const isRunningRef = useRef(false);
  const pearsonChartRef = useRef<Chart<'bar'> | null>(null);
  const cramersChartRef = useRef<Chart<'bar'> | null>(null);

  // Get current data scope from sessionStorage
  const getDataScope = () => {
    try {
      const cfg = sessionStorage.getItem('dataset_config');
      if (cfg) {
        const parsed = JSON.parse(cfg);
        return parsed?.data_scope || 'entire';
      }
    } catch (e) {
      console.error('Error reading data scope:', e);
    }
    return 'entire';
  };

  // Initialize component with cached data or trigger fresh load
  useEffect(() => {
    const dataScope = getDataScope();
    // Cache key excludes currentStep - data is step-independent
    const currentAnalysisKey = `${datasetId}-${targetVariable}-correlation-${dataScope}`;
    
    console.log('🔍 CorrelationAnalysisComponent mount/init:', {
      datasetId,
      targetVariable,
      currentStep,
      dataScope,
      currentAnalysisKey
    });
    
    // Always restore from cache if available (regardless of currentStep)
    const cachedData = getCachedCorrelationData(currentAnalysisKey);
    
    if (cachedData) {
      console.log('📦 Using cached correlation data for:', currentAnalysisKey);
      setAnalysisResults(cachedData.analysisResults);
      setError('');
      
      // Notify parent if callback exists
      if (cachedData.analysisResults && onAnalysisComplete) {
        onAnalysisComplete(cachedData.analysisResults);
      }
    } else if (datasetId && targetVariable) {
      // Trigger fresh fetch whenever dataset/target is available and no cache exists
      console.log('🔄 No cache found, loading fresh correlation data for:', currentAnalysisKey);
      runCorrelationAnalysis();
    }
    
    return () => {
      mountedRef.current = false;
    };
  }, [datasetId, targetVariable, currentStep]);

  useEffect(() => {
    if (!analysisResults || !enableDisplayThresholdControls) return;
    const t = Number(analysisResults.correlation_threshold);
    if (!Number.isNaN(t)) {
      setPearsonDisplayThreshold(Math.max(-1, Math.min(1, t)));
      setCramersDisplayThreshold(Math.min(1, Math.max(0, t)));
    }
  }, [
    enableDisplayThresholdControls,
    analysisResults?.correlation_threshold,
    analysisResults?.analysis_timestamp,
    datasetId,
    targetVariable,
  ]);

  // Listen for data scope changes
  useEffect(() => {
    const handleScopeChange = (event: CustomEvent) => {
      const { dataset_id, scope } = event.detail;
      
      console.log('🔄 CorrelationAnalysisComponent - Scope changed:', {
        dataset_id,
        scope,
        currentDatasetId: datasetId
      });
      
      // Only refresh if it's for the current dataset
      if (dataset_id === datasetId) {
        console.log('🔄 Refreshing correlation analysis for new scope:', scope);
        runCorrelationAnalysis(true);
      }
    };

    // Add event listener
    window.addEventListener('datasetScopeChanged', handleScopeChange as EventListener);
    
    // Cleanup
    return () => {
      window.removeEventListener('datasetScopeChanged', handleScopeChange as EventListener);
    };
  }, [datasetId, targetVariable, currentStep]);

  const downloadCorrelationReportExcel = async () => {
    if (!analysisResults || !datasetId) {
      alert('Run analysis first, then download the report.');
      return;
    }
    setIsExcelDownloading(true);
    try {
      await flushChartDraw();
      const pearsonPng = chartToPngBase64(pearsonChartRef.current);
      const cramersPng = chartToPngBase64(cramersChartRef.current);

      const infoRows: ReportCell[][] = [
        ['Field', 'Value'],
        ['Dataset ID', datasetId],
        ['Target variable', targetVariable],
        ['Exported (UTC)', new Date().toISOString()],
        ['Analysis correlation threshold', analysisResults.correlation_threshold],
        ['Total variables analyzed', analysisResults.total_variables_analyzed],
        ['Variables in chart (pass filter)', analysisResults.variables_above_threshold],
        ['Requested correlation method (API)', 'pearson (Spearman also computed for numerics)'],
      ];

      const ds = analysisResults.dataset_summary;
      const dsRows: ReportCell[][] = ds
        ? [
            ['Summary', ''],
            ['Shape (rows × cols)', ds.shape ? `${ds.shape[0]} × ${ds.shape[1]}` : '—'],
            ...(ds.numeric_columns?.length
              ? [
                  ['Numeric columns (count)', ds.numeric_columns.length],
                  [],
                  ['Numeric column names', ds.numeric_columns.join(', ')],
                ]
              : []),
            ...(ds.categorical_columns?.length
              ? [
                  [],
                  ['Categorical columns (count)', ds.categorical_columns.length],
                  ['Categorical column names', ds.categorical_columns.join(', ')],
                ]
              : []),
          ]
        : [['Note', 'No dataset summary was returned by the analysis API.']];

      let rows = analysisResults.full_correlation_results ?? [];
      if (rows.length === 0 && analysisResults.correlations.length > 0) {
        rows = analysisResults.correlations.map((c) => ({
          variable_name: c.variable_name,
          variable_type: c.variable_type === 'numerical' ? 'numeric' : 'categorical',
          pearson_correlation: c.correlation_value,
        }));
      }

      const master: ReportCell[][] = [
        [
          'Variable',
          'Type',
          'Pearson vs target',
          'Spearman vs target',
          "Cramér's V",
        ],
      ];
      for (const r of rows) {
        master.push([
          r.variable_name,
          r.variable_type,
          r.pearson_correlation ?? '',
          r.spearman_correlation ?? '',
          r.cramers_v ?? '',
        ]);
      }

      const safeDataset = datasetId.replace(/[^a-zA-Z0-9_-]/g, '_');
      const fname = `Correlation_Analysis_${safeDataset}_${new Date().toISOString().split('T')[0]}.xlsx`;

      const charts = [];
      if (pearsonPng) {
        charts.push({ sheetName: 'Pearson chart', base64Png: pearsonPng, width: 760, height: 440 });
      }
      if (cramersPng) {
        charts.push({ sheetName: 'Cramers V chart', base64Png: cramersPng, width: 760, height: 440 });
      }

      await downloadExcelWorkbookWithCharts({
        filename: fname,
        sheets: [
          {
            name: 'Methodology',
            rows: correlationVsTargetMethodologyAoA(analysisResults.correlation_threshold),
          },
          { name: 'Report info', rows: infoRows },
          { name: 'Dataset overview', rows: dsRows },
          { name: 'All variables', rows: master },
        ],
        charts: charts.length ? charts : undefined,
      });
    } catch (e) {
      console.error('Excel export failed:', e);
      alert('Could not build the Excel file. Try again after analysis finishes loading.');
    } finally {
      setIsExcelDownloading(false);
    }
  };

  const runCorrelationAnalysis = async (forceRefresh: boolean = false) => {
    if (!datasetId || !targetVariable) return;
    if (isRunningRef.current) return;
    isRunningRef.current = true;

    console.log('🔍 CorrelationAnalysisComponent - Starting analysis with:', {
      datasetId,
      targetVariable,
      currentStep,
      forceRefresh
    });

    setIsAnalyzing(true);
    setError('');

    try {
      const results = await correlationAnalysisService.analyzeCorrelations({
        dataset_id: datasetId,
        target_variable: targetVariable,
        correlation_threshold: 0.05,
        correlation_method: 'pearson'
      });

      setAnalysisResults(results);
      onAnalysisComplete?.(results);

      // Save to cache with data scope (key excludes currentStep - data is step-independent)
      const dataScope = getDataScope();
      const currentAnalysisKey = `${datasetId}-${targetVariable}-correlation-${dataScope}`;
      setCachedCorrelationData(currentAnalysisKey, {
        analysisResults: results,
        analysisKey: currentAnalysisKey,
        timestamp: Date.now()
      });

      console.log('💾 Saved correlation data to cache for key:', currentAnalysisKey);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to run correlation analysis');
    } finally {
      setIsAnalyzing(false);
      isRunningRef.current = false;
    }
  };

  if (!datasetId || !targetVariable) {
    return (
      <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-700 rounded-lg p-4">
        <div className="flex items-center space-x-2">
          <AlertTriangle className="h-5 w-5 text-yellow-600" />
          <span className="text-yellow-800 dark:text-yellow-300 font-medium">Dataset Required</span>
        </div>
        <p className="text-yellow-700 dark:text-yellow-400 text-sm mt-1">
          Please ensure a dataset is loaded and target variable is configured.
        </p>
      </div>
    );
  }

  if (isAnalyzing) {
    return (
      <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700 rounded-lg p-6 text-center">
        <Loader className="h-8 w-8 text-blue-600 animate-spin mx-auto mb-3" />
        <h3 className="font-medium text-blue-900 dark:text-blue-300 mb-2">Running Correlation Analysis</h3>
        <p className="text-blue-700 dark:text-blue-400 text-sm">
          Analyzing Pearson correlations and Cramér&apos;s V vs the target variable…
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded-lg p-4">
        <div className="flex items-center space-x-2">
          <AlertTriangle className="h-5 w-5 text-red-600" />
          <span className="text-red-800 dark:text-red-300 font-medium">Analysis Failed</span>
        </div>
        <p className="text-red-700 dark:text-red-400 text-sm mt-1">{error}</p>
        <button
          onClick={() => runCorrelationAnalysis()}
          className="mt-3 px-4 py-2 bg-red-600 dark:bg-red-700 text-white rounded-lg hover:bg-red-700 dark:hover:bg-red-600 transition-colors text-sm"
        >
          Retry Analysis
        </button>
      </div>
    );
  }

  if (!analysisResults) {
    return (
      <div className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6 text-center">
        <TrendingUp className="h-8 w-8 text-gray-400 mx-auto mb-3" />
        <h3 className="font-medium text-gray-900 dark:text-gray-100 mb-2">Pearson Correlation Analysis</h3>
        <p className="text-gray-600 dark:text-gray-400 text-sm mb-4">
          Analyze Pearson correlations between variables and your target variable.
        </p>
        <button
          type="button"
          onClick={() => runCorrelationAnalysis()}
          className="px-4 py-2 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] transition-colors"
        >
          Start Analysis
        </button>
      </div>
    );
  }

  const pearsonChartRows = enableDisplayThresholdControls
    ? buildPearsonChartRows(analysisResults.full_correlation_results)
    : analysisResults.correlations;
  const cramersChartRows = enableDisplayThresholdControls
    ? buildCramersVChartRows(analysisResults.full_correlation_results, 0)
    : buildCramersVChartRows(
        analysisResults.full_correlation_results,
        analysisResults.correlation_threshold
      );
  const pearsonSignificanceThreshold = enableDisplayThresholdControls
    ? pearsonDisplayThreshold
    : analysisResults.correlation_threshold;
  const cramersSignificanceThreshold = enableDisplayThresholdControls
    ? cramersDisplayThreshold
    : analysisResults.correlation_threshold;

  return (
    <div className="space-y-5">
      {/* Analysis Results */}
      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
          <h4 className="font-medium text-gray-900 dark:text-gray-100 flex items-center gap-2 min-w-0">
            <TrendingUp className="h-5 w-5 shrink-0 text-green-600" />
            <span>Pearson Correlation Analysis Results</span>
          </h4>
          {enableDisplayThresholdControls && (
            <div className="flex shrink-0 flex-wrap items-center gap-2 text-sm">
              <label
                htmlFor="pearson-correlation-threshold"
                className="whitespace-nowrap text-gray-600 dark:text-gray-400"
              >
                Threshold <span className="text-gray-500 dark:text-gray-500"></span>
              </label>
              <input
                id="pearson-correlation-threshold"
                type="number"
                min={-1}
                max={1}
                step={0.01}
                value={pearsonDisplayThreshold}
                onChange={(e) => {
                  const v = e.target.valueAsNumber;
                  if (Number.isNaN(v)) return;
                  setPearsonDisplayThreshold(Math.max(-1, Math.min(1, v)));
                }}
                className="w-24 rounded-md border border-gray-300 bg-white px-2 py-1 text-right tabular-nums text-gray-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100"
                aria-label="Pearson correlation display threshold, range -1 to 1"
              />
            </div>
          )}
        </div>

        {/* Chart Visualization */}
        <CorrelationChart
          correlations={pearsonChartRows}
          targetVariable={analysisResults.target_variable}
          mode="pearson"
          significanceThreshold={pearsonSignificanceThreshold}
          chartRef={pearsonChartRef}
        />
      </div>

      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
          <h4 className="font-medium text-gray-900 dark:text-gray-100 flex items-center gap-2 min-w-0">
            <BarChart3 className="h-5 w-5 shrink-0 text-violet-600" />
            <span>Cramér&apos;s V analysis vs target</span>
          </h4>
          {enableDisplayThresholdControls && (
            <div className="flex shrink-0 flex-wrap items-center gap-2 text-sm">
              <label
                htmlFor="cramers-v-threshold"
                className="whitespace-nowrap text-gray-600 dark:text-gray-400"
              >
                Threshold <span className="text-gray-500 dark:text-gray-500">(V)</span>
              </label>
              <input
                id="cramers-v-threshold"
                type="number"
                min={0}
                max={1}
                step={0.01}
                value={cramersDisplayThreshold}
                onChange={(e) => {
                  const v = e.target.valueAsNumber;
                  if (Number.isNaN(v)) return;
                  setCramersDisplayThreshold(Math.max(0, Math.min(1, v)));
                }}
                className="w-24 rounded-md border border-gray-300 bg-white px-2 py-1 text-right tabular-nums text-gray-900 shadow-sm focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100"
                aria-label="Cramér's V display threshold, range 0 to 1"
              />
            </div>
          )}
        </div>

        <CorrelationChart
          correlations={cramersChartRows}
          targetVariable={analysisResults.target_variable}
          mode="cramersV"
          significanceThreshold={cramersSignificanceThreshold}
          chartRef={cramersChartRef}
        />
      </div>

      {/* Action Buttons */}
      <div className="mt-1 pt-4 border-t border-gray-200 dark:border-gray-700 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => {
            const dataScope = getDataScope();
            const currentAnalysisKey = `${datasetId}-${targetVariable}-correlation-${dataScope}`;
            correlationCache.delete(currentAnalysisKey);
            setAnalysisResults(null);
            runCorrelationAnalysis(true);
          }}
          disabled={isAnalyzing}
          className="px-4 py-2 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] disabled:opacity-50 transition-colors text-sm"
          title="Force refresh Pearson correlation analysis data"
        >
          Refresh Analysis
        </button>
        <button
          type="button"
          onClick={() => void downloadCorrelationReportExcel()}
          disabled={isAnalyzing || isExcelDownloading}
          className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 disabled:opacity-50 transition-colors text-sm"
          title="Download Excel workbook (.xlsx)"
        >
          {isExcelDownloading ? (
            <Loader className="h-4 w-4 animate-spin shrink-0" />
          ) : (
            <FileDown className="h-4 w-4 shrink-0" />
          )}
          Download Report
        </button>
      </div>
    </div>
  );
};

export default CorrelationAnalysisComponent;
