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
} from 'lucide-react';
import { 
  ivAnalysisService, 
  IVAnalysisResponse,
  IVVariableResult,
} from '../services/ivAnalysisService';
import {
  EXL_LIGHT_BLUE,
  EXL_MIDNIGHT,
  EXL_ORANGE,
  EXL_SLATE,
  exlRgba,
} from '../constants/exlBrandChartColors';

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
interface CachedIVData {
  analysisResults: IVAnalysisResponse | null;
  analysisKey: string;
  timestamp: number;
}

const ivCache = new Map<string, CachedIVData>();
const CACHE_EXPIRY_MS = 10 * 60 * 1000; // 10 minutes

const getCachedIVData = (key: string): CachedIVData | null => {
  const cached = ivCache.get(key);
  if (cached && (Date.now() - cached.timestamp) < CACHE_EXPIRY_MS) {
    return cached;
  }
  if (cached) {
    ivCache.delete(key); // Remove expired data
  }
  return null;
};

const setCachedIVData = (key: string, data: CachedIVData) => {
  ivCache.set(key, { ...data, timestamp: Date.now() });
};

function invalidateIvCacheForDataset(datasetId: string, targetVariable: string) {
  const prefix = `${datasetId}-${targetVariable}-iv-`;
  for (const k of [...ivCache.keys()]) {
    if (k.startsWith(prefix)) ivCache.delete(k);
  }
}

function ivBarStyle(
  strength: IVVariableResult['iv_strength'],
  isDark: boolean
): { fill: string; border: string } {
  if (isDark) {
    switch (strength) {
      case 'weak':
        return { fill: 'rgba(186, 230, 253, 0.88)', border: '#93c5fd' };
      case 'medium':
        return { fill: 'rgba(56, 189, 248, 0.55)', border: '#bae6fd' };
      case 'strong':
        return { fill: 'rgba(251, 146, 60, 0.75)', border: '#fed7aa' };
      case 'very_strong':
      default:
        return { fill: 'rgba(248, 113, 113, 0.65)', border: '#fecaca' };
    }
  }
  switch (strength) {
    case 'weak':
      return { fill: exlRgba(EXL_LIGHT_BLUE, 0.95), border: EXL_MIDNIGHT };
    case 'medium':
      return { fill: exlRgba(EXL_MIDNIGHT, 0.78), border: EXL_SLATE };
    case 'strong':
      return { fill: exlRgba(EXL_ORANGE, 0.88), border: EXL_SLATE };
    case 'very_strong':
    default:
      return { fill: exlRgba(EXL_SLATE, 0.92), border: EXL_ORANGE };
  }
}

function ivMethodologyAoA(): (string | number)[][] {
  return [
    ['Section', 'Detail'],
    ['Purpose', 'Information Value (IV) measures the predictive power of a variable by quantifying how well it separates events from non-events.'],
    [
      'Calculation',
      'IV = Sum[(%Good - %Bad) * ln(%Good/%Bad)] across all bins/groups. Higher IV indicates stronger predictive power.',
    ],
    [
      'Interpretation',
      'IV < 0.02: Weak (not useful). 0.02-0.1: Medium. 0.1-0.3: Strong. > 0.3: Very Strong (suspect overfitting).',
    ],
    [
      'Binning',
      'Numerical variables are binned (default quantile, 10 bins). Categorical variables are grouped if needed.',
    ],
    [
      'Workbook',
      'This export contains Methodology, Report info, Dataset overview, All variables, and an IV bar chart image when the chart is on screen.',
    ],
  ];
}

// IV Chart Component
interface IVChartProps {
  ivData: IVVariableResult[];
  targetVariable: string;
  ivThreshold?: number;
  chartRef?: React.Ref<Chart<'bar'>>;
}

const IVChart: React.FC<IVChartProps> = ({
  ivData,
  targetVariable,
  ivThreshold = 0.02,
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

  if (!ivData || ivData.length === 0) {
    return (
      <div className="text-center text-gray-500 dark:text-gray-400 py-8">
        <p>No IV data available</p>
      </div>
    );
  }

  // Filter variables based on IV threshold and get top results
  const thresholdForFilter = ivThreshold;
  const filteredIVData = ivData
    .filter((iv) => iv.iv_value >= thresholdForFilter)
    .sort((a, b) => b.iv_value - a.iv_value);

  if (filteredIVData.length === 0) {
    return (
      <div className="text-center text-gray-500 dark:text-gray-400 py-8">
        <p>No variables meet the IV threshold ({'>='} {thresholdForFilter})</p>
      </div>
    );
  }

  const ivStyles = filteredIVData.map((iv) => ivBarStyle(iv.iv_strength, isDark));
  const chartData = {
    labels: filteredIVData.map((iv) => iv.variable_name),
    datasets: [
      {
        label: "Information Value with target",
        data: filteredIVData.map((iv) => iv.iv_value),
        backgroundColor: ivStyles.map((s) => s.fill),
        borderColor: ivStyles.map((s) => s.border),
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
        text: `Information Value with ${targetVariable} ({'>='} ${thresholdForFilter})`,
        font: {
          size: 14,
          weight: 'bold' as const,
        },
        color: isDark ? EXL_LIGHT_BLUE : EXL_SLATE,
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
            const ivData = filteredIVData[context.dataIndex];
            const strength = ivData?.iv_strength || 'unknown';
            return [
              `${label}: ${value.toFixed(4)} (IV)`,
              `Strength: ${strength.replace('_', ' ').toUpperCase()}`,
            ];
          },
        },
      },
    },
    scales: {
      x: {
        border: chartJsScaleBorder(isDark),
        // IV values axis
        grid: {
          display: true,
          color: isDark ? exlRgba(EXL_LIGHT_BLUE, 0.14) : exlRgba(EXL_SLATE, 0.12),
        },
        ticks: {
          color: isDark ? EXL_LIGHT_BLUE : EXL_SLATE,
          font: {
            size: 11,
            weight: 'bold' as const,
          },
          callback: function(value: any) {
            return typeof value === 'number' ? value.toFixed(3) : value;
          },
        },
        title: {
          display: true,
          text: 'Information Value',
          color: isDark ? EXL_LIGHT_BLUE : EXL_MIDNIGHT,
          font: {
            size: 12,
            weight: 'bold' as const,
          },
        },
        min: 0,
      },
      y: {
        border: chartJsScaleBorder(isDark),
        // Variable names axis
        grid: {
          display: false,
        },
        ticks: {
          color: isDark ? EXL_LIGHT_BLUE : EXL_SLATE,
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

      {/* IV strength legend — matches bar colors for current theme */}
      <div className="mt-4 flex flex-wrap gap-4 text-xs">
        {(
          [
            ['weak', 'Weak'],
            ['medium', 'Medium'],
            ['strong', 'Strong'],
            ['very_strong', 'Very strong'],
          ] as const
        ).map(([strength, label]) => {
          const s = ivBarStyle(strength, isDark);
          return (
            <div key={strength} className="flex items-center gap-2">
              <div
                className="w-3 h-3 rounded"
                style={{ backgroundColor: s.fill, border: `1px solid ${s.border}` }}
              />
              <span className="text-gray-700 dark:text-gray-200">{label}</span>
            </div>
          );
        })}
      </div>
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
                  Information Value Analysis - Expanded View
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

                <div className="mt-4 flex flex-wrap gap-4 text-xs">
                  {(
                    [
                      ['weak', 'Weak'],
                      ['medium', 'Medium'],
                      ['strong', 'Strong'],
                      ['very_strong', 'Very strong'],
                    ] as const
                  ).map(([strength, label]) => {
                    const s = ivBarStyle(strength, isDark);
                    return (
                      <div key={strength} className="flex items-center gap-2">
                        <div
                          className="w-3 h-3 rounded"
                          style={{ backgroundColor: s.fill, border: `1px solid ${s.border}` }}
                        />
                        <span className="text-gray-700 dark:text-gray-200">{label}</span>
                      </div>
                    );
                  })}
                </div>
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

interface IVAnalysisComponentProps {
  datasetId: string | null;
  targetVariable: string;
  currentStep?: number;
  onAnalysisComplete?: (results: IVAnalysisResponse) => void;
}

const IVAnalysisComponent: React.FC<IVAnalysisComponentProps> = ({
  datasetId,
  targetVariable,
  currentStep = 3,
  onAnalysisComplete,
}) => {
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResults, setAnalysisResults] = useState<IVAnalysisResponse | null>(null);
  const [error, setError] = useState<string>('');
  const [isExcelDownloading, setIsExcelDownloading] = useState(false);

  const mountedRef = useRef(true);
  const isRunningRef = useRef(false);
  const ivChartRef = useRef<Chart<'bar'> | null>(null);

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
    const currentAnalysisKey = `${datasetId}-${targetVariable}-iv-${dataScope}`;

    const cachedData = getCachedIVData(currentAnalysisKey);

    if (cachedData) {
      setAnalysisResults(cachedData.analysisResults);
      setError('');

      if (cachedData.analysisResults && onAnalysisComplete) {
        onAnalysisComplete(cachedData.analysisResults);
      }
    } else if (datasetId && targetVariable) {
      void runIVAnalysis();
    }
    
    return () => {
      mountedRef.current = false;
    };
  }, [datasetId, targetVariable, currentStep]);

  // Listen for data scope changes
  useEffect(() => {
    const handleScopeChange = (event: CustomEvent) => {
      const { dataset_id } = event.detail;

      if (dataset_id === datasetId) {
        void runIVAnalysis(true);
      }
    };

    // Add event listener
    window.addEventListener('datasetScopeChanged', handleScopeChange as EventListener);
    
    // Cleanup
    return () => {
      window.removeEventListener('datasetScopeChanged', handleScopeChange as EventListener);
    };
  }, [datasetId, targetVariable, currentStep]);

  const downloadIVReportExcel = async () => {
    if (!analysisResults || !datasetId) {
      alert('Run analysis first, then download the report.');
      return;
    }
    setIsExcelDownloading(true);
    try {
      await flushChartDraw();
      const chartPng = chartToPngBase64(ivChartRef.current);

      const infoRows: ReportCell[][] = [
        ['Field', 'Value'],
        ['Dataset ID', datasetId],
        ['Target variable', targetVariable],
        ['Exported (UTC)', new Date().toISOString()],
        ['Total variables analyzed', analysisResults.total_variables_analyzed],
        ['Variables with IV > 0.02', Object.values(analysisResults.analysis_results).filter(v => v.iv_value > 0.02).length],
      ];

      const ds = analysisResults.dataset_summary;
      const dsRows: ReportCell[][] = ds
        ? [
            ['Summary', ''],
            ['Shape (rows × cols)', ds.total_rows ? `${ds.total_rows} × ${ds.total_columns}` : '---'],
            ['Memory usage (MB)', ds.memory_usage_mb || '---'],
          ]
        : [['Note', 'No dataset summary was returned by the analysis API.']];

      const master: ReportCell[][] = [
        [
          'Variable',
          'Type',
          'IV Value',
          'IV Strength',
          'Key Insight',
        ],
      ];
      for (const r of Object.values(analysisResults.analysis_results)) {
        master.push([
          r.variable_name,
          r.variable_type,
          typeof r.iv_value === 'number' ? r.iv_value.toFixed(4) : (r.iv_value || ''),
          r.iv_strength || '',
          r.summary?.key_insight || '',
        ]);
      }

      const safeDataset = datasetId.replace(/[^a-zA-Z0-9_-]/g, '_');
      const fname = `IV_Analysis_${safeDataset}_${new Date().toISOString().split('T')[0]}.xlsx`;

      await downloadExcelWorkbookWithCharts({
        filename: fname,
        sheets: [
          { name: 'Methodology', rows: ivMethodologyAoA() },
          { name: 'Report info', rows: infoRows },
          { name: 'Dataset overview', rows: dsRows },
          { name: 'All variables', rows: master },
        ],
        charts: chartPng
          ? [{ sheetName: 'IV chart', base64Png: chartPng, width: 760, height: 440 }]
          : undefined,
      });
    } catch (e) {
      console.error('Excel export failed:', e);
      alert('Could not build the Excel file. Try again after analysis finishes loading.');
    } finally {
      setIsExcelDownloading(false);
    }
  };

  const runIVAnalysis = async (forceRefresh: boolean = false) => {
    if (!datasetId || !targetVariable) return;
    if (isRunningRef.current) return;
    isRunningRef.current = true;

    if (forceRefresh) {
      invalidateIvCacheForDataset(datasetId, targetVariable);
    }

    setIsAnalyzing(true);
    setError('');

    try {
      const results = await ivAnalysisService.analyzeAllVariables({
        dataset_id: datasetId,
        target_variable: targetVariable,
        binning_method: 'quantile',
        bins: 10
      });

      setAnalysisResults(results);
      onAnalysisComplete?.(results);

      // Save to cache with data scope
      const dataScope = getDataScope();
      const currentAnalysisKey = `${datasetId}-${targetVariable}-iv-${dataScope}`;
      setCachedIVData(currentAnalysisKey, {
        analysisResults: results,
        analysisKey: currentAnalysisKey,
        timestamp: Date.now()
      });

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to run IV analysis');
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
        <h3 className="font-medium text-blue-900 dark:text-blue-300 mb-2">Running Information Value Analysis</h3>
        <p className="text-blue-700 dark:text-blue-400 text-sm">
          Analyzing predictive power of all variables against the target variable...
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
          onClick={() => runIVAnalysis()}
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
        <h3 className="font-medium text-gray-900 dark:text-gray-100 mb-2">Information Value Analysis</h3>
        <p className="text-gray-600 dark:text-gray-400 text-sm mb-4">
          Analyze the predictive power of variables using Information Value.
        </p>
        <button
          type="button"
          onClick={() => runIVAnalysis()}
          className="px-4 py-2 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] transition-colors"
        >
          Start Analysis
        </button>
      </div>
    );
  }

  // Convert analysis results to array format for chart
  const ivDataArray = Object.values(analysisResults.analysis_results).filter(result => !result.error);

  return (
    <div className="space-y-5">
      {/* Analysis Results */}
      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
          <h4 className="font-medium text-gray-900 dark:text-gray-100 flex items-center gap-2 min-w-0">
            <TrendingUp className="h-5 w-5 shrink-0 text-green-600" />
            <span>Information Value Analysis Results</span>
          </h4>
        </div>

        {/* Chart Visualization */}
        <IVChart
          ivData={ivDataArray}
          targetVariable={analysisResults.target_variable}
          ivThreshold={0.02}
          chartRef={ivChartRef}
        />

        <div className="mt-1 pt-4 border-t border-gray-200 dark:border-gray-700 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => void runIVAnalysis(true)}
            disabled={isAnalyzing}
            className="px-4 py-2 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] disabled:opacity-50 transition-colors text-sm"
            title="Refresh IV analysis from the server"
          >
            Refresh Analysis
          </button>
          <button
            type="button"
            onClick={() => void downloadIVReportExcel()}
            disabled={isAnalyzing || isExcelDownloading}
            className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 disabled:opacity-50 transition-colors text-sm"
            title="Download IV Analysis Report (.xlsx)"
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
    </div>
  );
};

export default IVAnalysisComponent;
