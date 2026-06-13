import React, { useState, useEffect, useRef } from 'react';
import { useTheme } from '../contexts/ThemeContext';
import { 
  BarChart3, 
  TrendingUp, 
  Activity, 
  Loader, 
  AlertTriangle,
  Maximize2,
  Minimize2,
  X,
  Search,
  ChevronDown,
  ChevronUp,
  FileDown,
} from 'lucide-react';
import { 
  bivariateAnalysisService, 
  BivariateAnalysisAllResponse, 
  BivariateAnalysisSingleResponse
} from '../services/bivariateAnalysisService';

// Import Chart.js components
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
} from 'chart.js';
import { Bar } from 'react-chartjs-2';
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
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend
);

// Global cache that persists across component mounts/unmounts
interface CachedAnalysisData {
  allResults: BivariateAnalysisAllResponse | null;
  selectedVariable: string;
  singleResult: BivariateAnalysisSingleResponse | null;
  analysisKey: string;
  timestamp: number;
}

const analysisCache = new Map<string, CachedAnalysisData>();
const CACHE_EXPIRY_MS = 10 * 60 * 1000; // 10 minutes

const getCachedData = (key: string): CachedAnalysisData | null => {
  const cached = analysisCache.get(key);
  if (cached && (Date.now() - cached.timestamp) < CACHE_EXPIRY_MS) {
    return cached;
  }
  if (cached) {
    analysisCache.delete(key); // Remove expired data
  }
  return null;
};

const setCachedData = (key: string, data: CachedAnalysisData) => {
  analysisCache.set(key, { ...data, timestamp: Date.now() });
};

function getBivariateSegmentRows(single: BivariateAnalysisSingleResponse | null): Array<Record<string, unknown>> {
  const inner = single?.analysis_result?.analysis_result as Record<string, unknown> | undefined;
  if (!inner?.analysis_result || typeof inner.analysis_result !== 'object') return [];
  const ar = inner.analysis_result as { analysis_data?: unknown[] };
  if (ar?.analysis_data && Array.isArray(ar.analysis_data)) {
    return ar.analysis_data as Array<Record<string, unknown>>;
  }
  return [];
}

function formatBivariateAvg(rate: unknown): string {
  const r = Number(rate);
  if (Number.isNaN(r)) return '—';
  return r.toFixed(4);
}

function formatBivariateRate(rate: unknown): string {
  const r = Number(rate);
  if (Number.isNaN(r)) return '—';
  const pct = r <= 1 ? r * 100 : r;
  return `${pct.toFixed(1)}%`;
}

function sanitizeExcelSheetName(name: string): string {
  const cleaned = name.replace(/[:\\/?*[\]]/g, '_').trim();
  return (cleaned || 'Detail').slice(0, 31);
}

// Combination Chart Component
interface CombinationChartProps {
  data: any;
  variableName: string;
  variableType: 'categorical' | 'numerical';
  /**
   * default — tall chart for single-variable / sidebar view.
   * grid — fixed-height tile so multiple charts in a grid keep a consistent aspect and do not overflow cells.
   */
  layout?: 'default' | 'grid';
}

const CombinationChart: React.FC<CombinationChartProps> = ({
  data,
  variableName,
  variableType,
  layout = 'default',
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
      // Prevent body scroll when modal is open
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }

    return () => {
      document.removeEventListener('keydown', handleEscapeKey);
      document.body.style.overflow = 'unset';
    };
  }, [isExpanded]);

  if (!data || !data.data) {
    return (
      <div className="text-center text-gray-500 dark:text-gray-400 py-8">
        <p>No chart data available</p>
        <p className="text-xs mt-2">Data: {JSON.stringify(data)}</p>
      </div>
    );
  }

  const { categories, bar_data, line_data } = data.data;
  
  // Prepare data for Chart.js combination chart
  const barFill = isDark ? 'rgba(96, 165, 250, 0.55)' : 'rgba(59, 130, 246, 0.6)';
  const barStroke = isDark ? 'rgba(147, 197, 253, 1)' : 'rgba(59, 130, 246, 1)';
  const lineStroke = isDark ? 'rgba(186, 230, 253, 1)' : 'rgba(59, 130, 246, 1)';
  const pointBorder = isDark ? '#1f2937' : '#ffffff';

  const chartData: any = {
    labels: categories,
    datasets: [
      {
        type: 'bar' as const,
        label: bar_data.label || 'Total',
        data: bar_data.values,
        backgroundColor: barFill,
        borderColor: barStroke,
        borderWidth: 1,
        yAxisID: 'y-left',
        order: 2,
      },
      {
        type: 'line' as const,
        label: line_data.label || 'Event Rate',
        data: line_data.values,
        borderColor: lineStroke,
        backgroundColor: isDark ? 'rgba(186, 230, 253, 0.12)' : 'rgba(59, 130, 246, 0.1)',
        borderWidth: 2,
        pointBackgroundColor: lineStroke,
        pointBorderColor: pointBorder,
        pointBorderWidth: 2,
        pointRadius: 4,
        pointHoverRadius: 6,
        yAxisID: 'y-right',
        order: 1,
        tension: 0.3, // Smooth line
      }
    ]
  };

  const isGridLayout = layout === 'grid';

  const chartOptions = {
    color: chartJsDefaultFontColor(isDark),
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'nearest' as const,
      intersect: true,
    },
    plugins: {
      title: {
        display: true,
        text: data.chart_title || `${variableName} Analysis`,
        font: {
          size: isGridLayout ? 11 : 14,
          weight: 'bold' as const,
        },
        color: isDark ? '#e5e7eb' : '#374151',
        padding: {
          bottom: isGridLayout ? 6 : 20,
        },
      },
      legend: {
        display: true,
        position: 'bottom' as const,
        labels: {
          usePointStyle: true,
          padding: isGridLayout ? 6 : 15,
          color: isDark ? '#d1d5db' : '#374151',
          font: {
            size: isGridLayout ? 10 : 12,
          },
        },
      },
      tooltip: {
        ...chartJsTooltipColors(isDark),
        callbacks: {
          label: function(context: any) {
            const datasetLabel = context.dataset.label || '';
            const value = context.parsed.y;
            
            if (context.datasetIndex === 0) {
              // Bar chart tooltip - show exact correlation value
              return `${datasetLabel}: ${value.toFixed(4)}`;
            } else {
              // Line chart tooltip - show exact percentage value
              return `${datasetLabel}: ${(value * 100).toFixed(4)}%`;
            }
          }
        }
      }
    },
    scales: {
      x: {
        border: chartJsScaleBorder(isDark),
        grid: {
          display: true,
          color: isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
        },
        ticks: {
          color: isDark ? '#d1d5db' : '#374151',
          font: {
            size: isGridLayout ? 9 : 11,
            weight: 'bold' as const,
          },
          maxRotation: categories.length > 3 ? 45 : 0,
          callback: function(_tickValue: any, index: number) {
            const label = categories[index];
            return label.length > 10 ? label.substring(0, 10) + '...' : label;
          }
        },
        title: {
          display: true,
          text: variableType === 'categorical' ? 'Category' : 'Range',
          color: isDark ? '#d1d5db' : '#374151',
          font: {
            size: isGridLayout ? 10 : 12,
            weight: 'bold' as const,
          },
        },
      },
      'y-left': {
        type: 'linear' as const,
        display: true,
        position: 'left' as const,
        border: chartJsScaleBorder(isDark),
        grid: {
          display: true,
          color: isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
        },
        ticks: {
          color: isDark ? '#d1d5db' : '#374151',
          font: {
            size: isGridLayout ? 9 : 11,
            weight: 'bold' as const,
          },
          callback: function(tickValue: any) {
            return tickValue.toLocaleString();
          }
        },
        title: {
          display: true,
          text: 'Total',
          color: isDark ? '#d1d5db' : '#374151',
          font: {
            size: isGridLayout ? 10 : 12,
            weight: 'bold' as const,
          },
        },
      },
      'y-right': {
        type: 'linear' as const,
        display: true,
        position: 'right' as const,
        border: chartJsScaleBorder(isDark),
        grid: {
          drawOnChartArea: false,
        },
        ticks: {
          color: isDark ? '#d1d5db' : '#374151',
          font: {
            size: isGridLayout ? 9 : 11,
            weight: 'bold' as const,
          },
          callback: function(tickValue: any) {
            return (tickValue * 100).toFixed(1) + '%';
          }
        },
        title: {
          display: true,
          text: 'Event Rate',
          color: isDark ? '#d1d5db' : '#374151',
          font: {
            size: isGridLayout ? 10 : 12,
            weight: 'bold' as const,
          },
        },
      },
    },
  };

  const handleToggleExpand = () => {
    setIsExpanded(!isExpanded);
  };

  /** Grid tiles: shorter fixed height so 2×2 layouts stay balanced; single view keeps a taller chart. */
  const chartHeightClass = isGridLayout
    ? 'h-[200px] w-full min-w-0 sm:h-[220px] md:h-[240px]'
    : isExpanded
      ? 'h-96'
      : 'h-80';

  const chartComponent = (
    <div
      className={`relative bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-600 ${
        isExpanded ? 'p-6' : isGridLayout ? 'p-2 sm:p-3' : 'p-4'
      }`}
    >
      {/* Expand/Collapse — hidden in compact grid tiles */}
      {!isGridLayout && (
        <button
          type="button"
          onClick={handleToggleExpand}
          className="absolute top-2 right-2 z-10 p-2 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
          title={isExpanded ? 'Minimize chart' : 'Expand chart'}
        >
          {isExpanded ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
        </button>
      )}

      <div className={`${chartHeightClass} ${!isGridLayout ? 'pt-1' : ''}`}>
        <Bar key={`${theme}-${layout}`} data={chartData} options={chartOptions} />
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
              <div className="bg-white dark:bg-gray-900 rounded-t-lg border-b border-gray-200 dark:border-gray-700 px-6 py-4 flex items-center justify-between">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  {data.chart_title || `${variableName} Analysis`} - Expanded View
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
              <div className="bg-white dark:bg-gray-900 rounded-b-lg p-6">
                <div className="h-96">
                  <Bar
                    key={`${theme}-expanded`}
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

interface BivariateAnalysisComponentProps {
  datasetId: string | null;
  targetVariable: string;
  currentStep?: number;
  onAnalysisComplete?: (results: BivariateAnalysisAllResponse) => void;
  /** When false, coarse binning / category grouping controls are hidden (e.g. auto insights). Sidebar enables this only for standard/selected insights. Default true. */
  allowBinningCustomization?: boolean;
}

const BivariateAnalysisComponent: React.FC<BivariateAnalysisComponentProps> = ({
  datasetId,
  targetVariable,
  currentStep = 3,
  onAnalysisComplete,
  allowBinningCustomization = true,
}) => {
  const [isAnalyzingAll, setIsAnalyzingAll] = useState(false);
  const [isAnalyzingSingle, setIsAnalyzingSingle] = useState(false);
  const [allAnalysisResults, setAllAnalysisResults] = useState<BivariateAnalysisAllResponse | null>(null);
  const [selectedVariable, setSelectedVariable] = useState<string>('');
  const [selectedVariables, setSelectedVariables] = useState<string[]>([]); // Multi-select (max 4)
  const [singleAnalysisResult, setSingleAnalysisResult] = useState<BivariateAnalysisSingleResponse | null>(null);
  const [multiAnalysisResults, setMultiAnalysisResults] = useState<Record<string, BivariateAnalysisSingleResponse>>({});
  const [error, setError] = useState<string>('');
  const [coarseBinsInput, setCoarseBinsInput] = useState('');
  const [categoryGroupsInput, setCategoryGroupsInput] = useState('');
  const [isExcelDownloading, setIsExcelDownloading] = useState(false);

  // Search functionality state
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [filteredVariables, setFilteredVariables] = useState<string[]>([]);
  
  const MAX_SELECTED_VARIABLES = 4;
  
  const mountedRef = useRef(true);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const isRunningAllRef = useRef(false);

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
    // Cache key does NOT include currentStep - data is the same regardless of which step the user is on
    const currentAnalysisKey = `${datasetId}-${targetVariable}-${dataScope}`;

    console.log('🔍 BivariateAnalysisComponent mount/init:', {
      datasetId,
      targetVariable,
      currentStep,
      dataScope,
      currentAnalysisKey
    });

    // Always restore from cache if available (regardless of currentStep)
    const cachedData = getCachedData(currentAnalysisKey);

    if (cachedData) {
      console.log('📦 Using cached data for:', currentAnalysisKey);
      setAllAnalysisResults(cachedData.allResults);
      setSelectedVariable(cachedData.selectedVariable);
      setSingleAnalysisResult(cachedData.singleResult);
      setError('');

      // Notify parent if callback exists
      if (cachedData.allResults && onAnalysisComplete) {
        onAnalysisComplete(cachedData.allResults);
      }
    } else if (datasetId && targetVariable) {
      // Trigger fresh fetch whenever dataset/target is available and no cache exists
      console.log('🔄 No cache found, loading fresh data for:', currentAnalysisKey);
      runAllVariablesAnalysis();
    }

    return () => {
      mountedRef.current = false;
    };
  }, [datasetId, targetVariable, currentStep]);

  // Listen for data scope changes
  useEffect(() => {
    const handleScopeChange = (event: CustomEvent) => {
      const { dataset_id, scope } = event.detail;
      
      console.log('🔄 BivariateAnalysisComponent - Scope changed:', {
        dataset_id,
        scope,
        currentDatasetId: datasetId
      });
      
      // Only refresh if it's for the current dataset
      if (dataset_id === datasetId) {
        console.log('🔄 Refreshing bivariate analysis for new scope:', scope);
        runAllVariablesAnalysis(true);
      }
    };

    // Add event listener
    window.addEventListener('datasetScopeChanged', handleScopeChange as EventListener);
    
    // Cleanup
    return () => {
      window.removeEventListener('datasetScopeChanged', handleScopeChange as EventListener);
    };
  }, [datasetId, targetVariable, currentStep]);

  // Update filtered variables when search term or available variables change
  useEffect(() => {
    if (!allAnalysisResults) {
      setFilteredVariables([]);
      return;
    }

    const availableVariables = bivariateAnalysisService.getAvailableVariables(allAnalysisResults.analysis_results);
    
    if (!searchTerm.trim()) {
      setFilteredVariables(availableVariables);
    } else {
      const filtered = availableVariables.filter(variable =>
        variable.toLowerCase().includes(searchTerm.toLowerCase())
      );
      setFilteredVariables(filtered);
    }
  }, [searchTerm, allAnalysisResults]);

  useEffect(() => {
    setCoarseBinsInput('');
    setCategoryGroupsInput('');
  }, [selectedVariable]);

  // Handle multi-variable selection (max 4)
  const handleMultiVariableToggle = (variableName: string) => {
    setSelectedVariables(prev => {
      const isSelected = prev.includes(variableName);
      if (isSelected) {
        const newSelection = prev.filter(v => v !== variableName);
        setMultiAnalysisResults(prevResults => {
          const newResults = { ...prevResults };
          delete newResults[variableName];
          return newResults;
        });
        return newSelection;
      } else {
        if (prev.length >= MAX_SELECTED_VARIABLES) {
          return prev;
        }
        void runSingleVariableAnalysis(variableName);
        return [...prev, variableName];
      }
    });
  };

  /** Remove one variable from the multi-select set (chips or card dismiss). */
  const removeSelectedVariable = (variableName: string) => {
    setSelectedVariables((prev) => prev.filter((v) => v !== variableName));
    setMultiAnalysisResults((prevResults) => {
      const next = { ...prevResults };
      delete next[variableName];
      return next;
    });
  };

  // Clear all selected variables
  const clearAllSelectedVariables = () => {
    setSelectedVariables([]);
    setMultiAnalysisResults({});
  };

  useEffect(() => {
    const inner = singleAnalysisResult?.analysis_result?.analysis_result as Record<string, unknown> | undefined;
    const vtype = singleAnalysisResult?.analysis_result?.variable_type;
    if (!inner || !vtype) return;
    if (vtype === 'numerical') {
      setCoarseBinsInput(
        typeof inner.coarse_bins_spec === 'string' ? inner.coarse_bins_spec : ''
      );
    }
    if (vtype === 'categorical') {
      setCategoryGroupsInput(
        typeof inner.category_groups_spec === 'string' ? inner.category_groups_spec : ''
      );
    }
  }, [singleAnalysisResult]);

  // Handle click outside dropdown to close it
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  // Sync search term with selected variable (clear search when variable is cleared)
  useEffect(() => {
    if (!selectedVariable) {
      setSearchTerm('');
    }
  }, [selectedVariable]);

  // Helper functions for search functionality
  const handleVariableSearch = (term: string) => {
    setSearchTerm(term);
    setIsDropdownOpen(true);
  };

  const toggleDropdown = () => {
    setIsDropdownOpen(!isDropdownOpen);
  };

  const runAllVariablesAnalysis = async (forceRefresh: boolean = false) => {
    if (!datasetId || !targetVariable) return;
    if (isRunningAllRef.current) return;
    isRunningAllRef.current = true;

    console.log('🔍 BivariateAnalysisComponent - Starting analysis with:', {
      datasetId,
      targetVariable,
      currentStep,
      forceRefresh
    });

    setIsAnalyzingAll(true);
    setError('');

    try {
      const results = await bivariateAnalysisService.analyzeAllVariables({
        dataset_id: datasetId,
        target_variable: targetVariable,
        binning_method: 'quantile',
        top_categories: 10,
        bins: 10
      });

      setAllAnalysisResults(results);
      onAnalysisComplete?.(results);

      // Auto-select first variable if available
      const availableVariables = bivariateAnalysisService.getAvailableVariables(results.analysis_results);
      let firstVariable = '';
      let firstVariableResult: BivariateAnalysisSingleResponse | null = null;

      if (availableVariables.length > 0) {
        firstVariable = availableVariables[0];
        setSelectedVariable(firstVariable);
        firstVariableResult = await runSingleVariableAnalysis(firstVariable);
      }

      // Save to cache with data scope (key excludes currentStep - data is step-independent)
      const dataScope = getDataScope();
      const currentAnalysisKey = `${datasetId}-${targetVariable}-${dataScope}`;
      setCachedData(currentAnalysisKey, {
        allResults: results,
        selectedVariable: firstVariable,
        singleResult: firstVariableResult,
        analysisKey: currentAnalysisKey,
        timestamp: Date.now()
      });

      console.log('💾 Saved data to cache for key:', currentAnalysisKey);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to run bivariate analysis');
    } finally {
      setIsAnalyzingAll(false);
      isRunningAllRef.current = false;
    }
  };

  const runSingleVariableAnalysis = async (
    variableName: string,
    options?: { coarse_bins?: string | null; category_groups?: string | null }
  ): Promise<BivariateAnalysisSingleResponse | null> => {
    if (!datasetId || !targetVariable) return null;

    setIsAnalyzingSingle(true);
    setError('');

    try {
      const result = await bivariateAnalysisService.getVariableAnalysis(
        datasetId,
        variableName,
        targetVariable,
        options
      );

      setSingleAnalysisResult(result);
      // Also store in multi-analysis results for multi-variable display
      setMultiAnalysisResults(prev => ({
        ...prev,
        [variableName]: result
      }));
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to get variable analysis');
      return null;
    } finally {
      setIsAnalyzingSingle(false);
    }
  };

  const handleVariableSelect = async (variableName: string) => {
    if (!datasetId || !targetVariable) return;

    setSelectedVariable(variableName);
    
    // Clear single analysis result if no variable selected
    if (!variableName) {
      setSingleAnalysisResult(null);
      return;
    }
    
    await runSingleVariableAnalysis(variableName);
  };

  const downloadBivariateReportExcel = async () => {
    if (!allAnalysisResults || !datasetId) {
      alert('Run analysis first, then download the report.');
      return;
    }
    setIsExcelDownloading(true);
    try {
      const XLSX = await import('xlsx');
      const wb = XLSX.utils.book_new();

      const infoAoa: (string | number)[][] = [
        ['Dataset ID', datasetId],
        ['Target variable', targetVariable],
        ['Exported (UTC)', new Date().toISOString()],
        ['Total rows', allAnalysisResults.dataset_summary?.total_rows ?? '—'],
        ['Total columns', allAnalysisResults.dataset_summary?.total_columns ?? '—'],
        ['Variables analyzed', allAnalysisResults.total_variables_analyzed ?? '—'],
      ];
      XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(infoAoa), 'Report info');

      const overviewHeader = ['Variable', 'Type', 'Key insight', 'Correlation'];
      const overviewRows: (string | number)[][] = [overviewHeader];
      Object.entries(allAnalysisResults.analysis_results).forEach(([name, vr]) => {
        if (vr.error) {
          overviewRows.push([name, 'error', String(vr.error ?? ''), '']);
          return;
        }
        const corr = vr.summary?.correlation;
        overviewRows.push([
          name,
          vr.variable_type,
          vr.summary?.key_insight ?? '',
          corr !== undefined && corr !== null && !Number.isNaN(Number(corr)) ? Number(corr) : '',
        ]);
      });
      XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(overviewRows), 'All variables');

      if (singleAnalysisResult) {
        const vtype = singleAnalysisResult.analysis_result.variable_type;
        const rows = getBivariateSegmentRows(singleAnalysisResult);
        const labelCol = vtype === 'numerical' ? 'Range' : 'Category';
        const header = [labelCol, 'Observations', 'Avg', 'Rate'];
        const dataRows = rows.map((row) => {
          const label =
            vtype === 'numerical' ? String(row.Bin_Range_Decile ?? '') : String(row.Category ?? '');
          return [
            label,
            row.Total as string | number,
            formatBivariateAvg(row.Default_Rate),
            formatBivariateRate(row.Default_Rate),
          ];
        });
        const detailAoa = [header, ...dataRows];
        const vn = singleAnalysisResult.variable_name;
        XLSX.utils.book_append_sheet(
          wb,
          XLSX.utils.aoa_to_sheet(detailAoa),
          sanitizeExcelSheetName(`${vn}_segments`)
        );

        const inner = singleAnalysisResult.analysis_result.analysis_result as
          | { insights?: string[] }
          | undefined;
        const insights = inner?.insights;
        if (insights && insights.length > 0) {
          const insAoa: (string | number)[][] = [['#', 'Insight']];
          insights.forEach((t, i) => insAoa.push([i + 1, t]));
          XLSX.utils.book_append_sheet(
            wb,
            XLSX.utils.aoa_to_sheet(insAoa),
            sanitizeExcelSheetName(`${vn}_insights`)
          );
        }
      }

      const safeDataset = datasetId.replace(/[^a-zA-Z0-9_-]/g, '_');
      const fname = `Bivariate_Analysis_${safeDataset}_${new Date().toISOString().split('T')[0]}.xlsx`;
      XLSX.writeFile(wb, fname);
    } catch (e) {
      console.error('Excel export failed:', e);
      alert('Could not build the Excel file. Try again after analysis finishes loading.');
    } finally {
      setIsExcelDownloading(false);
    }
  };

  // Check if we're on the correct step
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

  if (isAnalyzingAll) {
    return (
      <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700 rounded-lg p-6 text-center">
        <Loader className="h-8 w-8 text-blue-600 animate-spin mx-auto mb-3" />
        <h3 className="font-medium text-blue-900 dark:text-blue-300 mb-2">Running Bivariate Analysis</h3>
        <p className="text-blue-700 dark:text-blue-400 text-sm">
          Analyzing relationships between all variables and target variable...
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
          onClick={() => runAllVariablesAnalysis()}
          className="mt-3 px-4 py-2 bg-red-600 dark:bg-red-700 text-white rounded-lg hover:bg-red-700 dark:hover:bg-red-600 transition-colors text-sm"
        >
          Retry Analysis
        </button>
      </div>
    );
  }

  if (!allAnalysisResults) {
    return (
      <div className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6 text-center">
        <BarChart3 className="h-8 w-8 text-gray-400 mx-auto mb-3" />
        <h3 className="font-medium text-gray-900 dark:text-gray-100 mb-2">Variable Analysis</h3>
        <p className="text-gray-600 dark:text-gray-400 text-sm mb-4">
          Analyze relationships between variables and your target variable.
        </p>
        <button
          onClick={() => runAllVariablesAnalysis()}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          Start Analysis
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Variable Analysis */}
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100 flex items-center space-x-2">
            <TrendingUp className="h-5 w-5 text-blue-600 shrink-0" />
            <span>Bivariate Analysis</span>
          </h3>
        </div>

        {/* Variable Selection */}
        <div className="space-y-3">
          <h4 className="font-medium text-gray-900 dark:text-gray-100">Select Variable to Analyze</h4>
          <div className="space-y-2">
            {/* Searchable Dropdown */}
            <div className="relative" ref={dropdownRef}>
              <div className="relative">
                <input
                  type="text"
                  value={searchTerm}
                  onChange={(e) => handleVariableSearch(e.target.value)}
                  onFocus={() => setIsDropdownOpen(true)}
                  placeholder={selectedVariable || "Search and select a variable..."}
                  className="w-full px-3 py-2 pr-10 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-transparent bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-gray-500"
                />
                <div className="absolute inset-y-0 right-0 flex items-center pr-2">
                  <Search className="h-4 w-4 text-gray-500 dark:text-gray-400 mr-1 pointer-events-none shrink-0" />
                  <button
                    type="button"
                    onClick={toggleDropdown}
                    className="rounded p-1 text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-100 dark:hover:bg-gray-800"
                    aria-expanded={isDropdownOpen}
                  >
                    {isDropdownOpen ? (
                      <ChevronUp className="h-4 w-4" />
                    ) : (
                      <ChevronDown className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </div>

              {/* Dropdown Options */}
              {isDropdownOpen && (
                <div className="absolute z-10 w-full mt-1 bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded-lg shadow-lg dark:shadow-black/40 max-h-60 overflow-y-auto">
                  {filteredVariables.length === 0 ? (
                    <div className="px-3 py-2 text-gray-500 dark:text-gray-400 text-sm">
                      {searchTerm ? 'No variables match your search' : 'No variables available'}
                    </div>
                  ) : (
                    <>
                      {/* Group by variable type for better organization */}
                      {(() => {
                        const categoricalVars = filteredVariables.filter(variable => {
                          const varData = allAnalysisResults?.analysis_results[variable];
                          return varData?.variable_type === 'categorical';
                        });
                        
                        const numericalVars = filteredVariables.filter(variable => {
                          const varData = allAnalysisResults?.analysis_results[variable];
                          return varData?.variable_type === 'numerical';
                        });

                        return (
                          <>
                            {/* Categorical Variables */}
                            {categoricalVars.length > 0 && (
                              <>
                                <div className="px-3 py-1 bg-gray-50 dark:bg-gray-800 text-xs font-medium text-gray-600 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                                  Categorical Variables
                                </div>
                                {categoricalVars.map((variable) => (
                                  <button
                                    key={`cat-${variable}`}
                                    type="button"
                                    onClick={() => handleMultiVariableToggle(variable)}
                                    className={`w-full text-left px-3 py-2 flex items-center space-x-2 ${
                                      selectedVariables.includes(variable)
                                        ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-200'
                                        : 'text-gray-900 dark:text-gray-100 hover:bg-blue-50 dark:hover:bg-gray-800'
                                    }`}
                                  >
                                    <input
                                      type="checkbox"
                                      checked={selectedVariables.includes(variable)}
                                      onChange={() => handleMultiVariableToggle(variable)}
                                      className="mr-2 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 dark:border-gray-500 dark:bg-gray-900 rounded"
                                      onClick={(e) => e.stopPropagation()}
                                    />
                                    <BarChart3 className="h-4 w-4 text-blue-500" />
                                    <span>{variable}</span>
                                  </button>
                                ))}
                              </>
                            )}

                            {/* Numerical Variables */}
                            {numericalVars.length > 0 && (
                              <>
                                {categoricalVars.length > 0 && (
                                  <div className="border-t border-gray-200 dark:border-gray-700" />
                                )}
                                <div className="px-3 py-1 bg-gray-50 dark:bg-gray-800 text-xs font-medium text-gray-600 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                                  Numerical Variables
                                </div>
                                {numericalVars.map((variable) => (
                                  <button
                                    key={`num-${variable}`}
                                    type="button"
                                    onClick={() => handleMultiVariableToggle(variable)}
                                    className={`w-full text-left px-3 py-2 flex items-center space-x-2 ${
                                      selectedVariables.includes(variable)
                                        ? 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-200'
                                        : 'text-gray-900 dark:text-gray-100 hover:bg-green-50 dark:hover:bg-gray-800'
                                    }`}
                                  >
                                    <input
                                      type="checkbox"
                                      checked={selectedVariables.includes(variable)}
                                      onChange={() => handleMultiVariableToggle(variable)}
                                      className="mr-2 h-4 w-4 text-green-600 focus:ring-green-500 border-gray-300 dark:border-gray-500 dark:bg-gray-900 rounded"
                                      onClick={(e) => e.stopPropagation()}
                                    />
                                    <TrendingUp className="h-4 w-4 text-green-500" />
                                    <span>{variable}</span>
                                  </button>
                                ))}
                              </>
                            )}
                          </>
                        );
                      })()}
                    </>
                  )}
                </div>
              )}
            </div>

            {/* Selection count, removable chips, clear all */}
            {selectedVariables.length > 0 && (
              <div className="space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                  <span className="text-gray-600 dark:text-gray-400">
                    {selectedVariables.length} of {MAX_SELECTED_VARIABLES} variables selected
                  </span>
                  <button
                    type="button"
                    onClick={clearAllSelectedVariables}
                    className="text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 text-sm font-medium shrink-0"
                  >
                    Clear all
                  </button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {selectedVariables.map((name) => (
                    <span
                      key={name}
                      className="inline-flex max-w-full items-center gap-1 rounded-full border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-800/80 pl-2.5 pr-1 py-0.5 text-xs text-gray-800 dark:text-gray-200"
                    >
                      <span className="truncate" title={name}>
                        {name}
                      </span>
                      <button
                        type="button"
                        onClick={() => removeSelectedVariable(name)}
                        className="shrink-0 rounded-full p-0.5 text-gray-500 hover:bg-gray-200 hover:text-gray-800 dark:hover:bg-gray-700 dark:hover:text-gray-100"
                        title={`Remove ${name}`}
                        aria-label={`Remove ${name} from selection`}
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </span>
                  ))}
                </div>
              </div>
            )}
            
            {/* Variable Type Indicator */}
            {selectedVariable && singleAnalysisResult && (
              <div className="flex items-center space-x-2 text-sm text-gray-600 dark:text-gray-400">
                {singleAnalysisResult.analysis_result.variable_type === 'categorical' ? (
                  <>
                    <BarChart3 className="h-4 w-4 text-blue-500" />
                    <span>Categorical Variable</span>
                  </>
                ) : (
                  <>
                    <Activity className="h-4 w-4 text-green-500" />
                    <span>Numerical Variable</span>
                  </>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Selected Variable Analysis */}
        {selectedVariable && selectedVariables.length === 0 && (
          <div className="space-y-4">
            {isAnalyzingSingle ? (
              <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4 text-center">
                <Loader className="h-6 w-6 text-blue-600 dark:text-blue-400 animate-spin mx-auto mb-2" />
                <p className="text-blue-700 dark:text-blue-200 text-sm">Analyzing {selectedVariable}...</p>
              </div>
            ) : singleAnalysisResult ? (
              <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                <h4 className="font-medium text-gray-900 dark:text-gray-100 mb-3">
                  Analysis: {singleAnalysisResult.variable_name}
                  <span className={`ml-2 px-2 py-1 rounded-full text-xs font-medium ${
                    singleAnalysisResult.analysis_result.variable_type === 'categorical'
                      ? 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-200'
                      : 'bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-200'
                  }`}>
                    {singleAnalysisResult.analysis_result.variable_type}
                  </span>
                </h4>


                 {/* Chart Visualization */}
                 {(() => {
                   const vizData = singleAnalysisResult.analysis_result.analysis_result?.visualization_data;
                   
                   return vizData ? (
                     <div className="mt-4">
                       <h5 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Visualization</h5>
                       <div className="rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 overflow-hidden">
                         <CombinationChart 
                           data={vizData}
                           variableName={singleAnalysisResult.variable_name}
                           variableType={singleAnalysisResult.analysis_result.variable_type as 'categorical' | 'numerical'}
                         />
                       </div>
                     </div>
                   ) : (
                     <div className="mt-4">
                       <h5 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Visualization</h5>
                       <div className="rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 p-6 text-center text-gray-500 dark:text-gray-400">
                         <p>No visualization data available</p>
                       </div>
                     </div>
                   );
                 })()}

                {(() => {
                  const vtype = singleAnalysisResult.analysis_result.variable_type;
                  // Auto Data Insights: chart only — omit Summary table (and binning block is already off)
                  if (!allowBinningCustomization) return null;
                  return (
                    <div className="mt-4 space-y-4">
                      {allowBinningCustomization && vtype === 'numerical' && (
                        <div className="rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-900/90 p-3 space-y-2">
                          <div>
                            <h6 className="text-sm font-medium text-gray-900 dark:text-gray-100">Coarse binning</h6>
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                              Enter cutpoints to match the value ranges above (e.g. same numbers as Range:{' '}
                              <span className="font-mono text-gray-700 dark:text-gray-300">0-20, 20-40, 40+</span>).
                            </p>
                          </div>
                          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                            <input
                              type="text"
                              value={coarseBinsInput}
                              onChange={(e) => setCoarseBinsInput(e.target.value)}
                              placeholder="e.g., 0-20, 20-40"
                              className="flex-1 px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100 placeholder:text-gray-500 dark:placeholder:text-gray-500"
                            />
                            <button
                              type="button"
                              disabled={isAnalyzingSingle || !selectedVariable}
                              onClick={() =>
                                void runSingleVariableAnalysis(
                                  selectedVariable,
                                  coarseBinsInput.trim()
                                    ? { coarse_bins: coarseBinsInput.trim() }
                                    : undefined
                                )
                              }
                              className="px-3 py-2 text-sm font-medium rounded-lg bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] hover:bg-blue-700 dark:hover:bg-[#333380] disabled:opacity-50"
                            >
                              Re-generate
                            </button>
                          </div>
                        </div>
                      )}

                      {allowBinningCustomization && vtype === 'categorical' && (
                        <div className="rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-900/90 p-3 space-y-2">
                          <div>
                            <h6 className="text-sm font-medium text-gray-900 dark:text-gray-100">Category grouping</h6>
                            <p className="text-xs text-gray-500 dark:text-gray-400">Group categories for refined analysis</p>
                          </div>
                          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                            <input
                              type="text"
                              value={categoryGroupsInput}
                              onChange={(e) => setCategoryGroupsInput(e.target.value)}
                              placeholder="e.g., Sales + RN, Driver + Manager"
                              className="flex-1 px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100 placeholder:text-gray-500 dark:placeholder:text-gray-500"
                            />
                            <button
                              type="button"
                              disabled={isAnalyzingSingle || !selectedVariable}
                              onClick={() =>
                                void runSingleVariableAnalysis(
                                  selectedVariable,
                                  categoryGroupsInput.trim()
                                    ? { category_groups: categoryGroupsInput.trim() }
                                    : undefined
                                )
                              }
                              className="px-3 py-2 text-sm font-medium rounded-lg bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] hover:bg-blue-700 dark:hover:bg-[#333380] disabled:opacity-50"
                            >
                              Re-generate
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })()}

              </div>
            ) : (
              <div className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
                <p className="text-gray-600 dark:text-gray-400 text-sm">Select a variable to see detailed analysis</p>
              </div>
            )}
          </div>
        )}

        {/* Multi-variable grid: consistent tile height, removable variables */}
        {selectedVariables.length > 0 && (
          <div className="space-y-4">
            <h4 className="font-medium text-gray-900 dark:text-gray-100">Selected variables</h4>
            <div
              className={`grid gap-3 sm:gap-4 min-w-0 ${
                selectedVariables.length === 1
                  ? 'grid-cols-1'
                  : 'grid-cols-1 sm:grid-cols-2'
              }`}
            >
              {selectedVariables.map((variableName) => {
                const analysisResult = multiAnalysisResults[variableName];
                const isLoading = !analysisResult;

                return (
                  <div
                    key={variableName}
                    className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-3 flex flex-col min-w-0 min-h-0 overflow-hidden"
                  >
                    {isLoading ? (
                      <div className="flex flex-1 items-center justify-center py-12">
                        <div className="text-center">
                          <Loader className="h-6 w-6 text-blue-500 animate-spin mx-auto mb-2" />
                          <p className="text-xs text-gray-500 dark:text-gray-400">Loading…</p>
                        </div>
                      </div>
                    ) : analysisResult ? (
                      <div className="flex min-h-0 flex-1 flex-col gap-2">
                        <div className="flex min-w-0 items-start justify-between gap-2">
                          <h5 className="font-medium text-gray-900 dark:text-gray-100 text-sm truncate min-w-0 pr-1">
                            {variableName}
                          </h5>
                          <div className="flex shrink-0 items-center gap-1">
                            <span
                              className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                                analysisResult.analysis_result.variable_type === 'categorical'
                                  ? 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-200'
                                  : 'bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-200'
                              }`}
                            >
                              {analysisResult.analysis_result.variable_type}
                            </span>
                            <button
                              type="button"
                              onClick={() => removeSelectedVariable(variableName)}
                              className="rounded-lg p-1 text-gray-500 hover:bg-gray-100 hover:text-gray-800 dark:hover:bg-gray-700 dark:hover:text-gray-100"
                              title={`Remove ${variableName}`}
                              aria-label={`Remove ${variableName}`}
                            >
                              <X className="h-4 w-4" />
                            </button>
                          </div>
                        </div>
                        {(() => {
                          const vizData = analysisResult.analysis_result.analysis_result?.visualization_data;
                          if (!vizData || !vizData.data) {
                            return (
                              <div className="flex flex-1 items-center justify-center py-10 text-center text-gray-500 dark:text-gray-400 text-sm">
                                No chart data available
                              </div>
                            );
                          }
                          return (
                            <div className="w-full min-w-0 min-h-0 shrink-0">
                              <CombinationChart
                                data={vizData}
                                variableName={variableName}
                                variableType={analysisResult.analysis_result.variable_type}
                                layout="grid"
                              />
                            </div>
                          );
                        })()}
                      </div>
                    ) : (
                      <div className="flex flex-1 items-center justify-center py-10 text-gray-500 dark:text-gray-400 text-sm">
                        Failed to load analysis
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Action Buttons */}
      <div className="mt-1 pt-4 border-t border-gray-200 dark:border-gray-700 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => {
            const dataScope = getDataScope();
            const currentAnalysisKey = `${datasetId}-${targetVariable}-${dataScope}`;
            analysisCache.delete(currentAnalysisKey);
            setAllAnalysisResults(null);
            setSingleAnalysisResult(null);
            setSelectedVariable('');
            runAllVariablesAnalysis(true);
          }}
          disabled={isAnalyzingAll}
          className="px-4 py-2 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] disabled:opacity-50 transition-colors text-sm"
          title="Force refresh all analysis data"
        >
          Refresh All Analysis
        </button>
        <button
          type="button"
          onClick={() => setSelectedVariable('')}
          disabled={isAnalyzingAll}
          className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 disabled:opacity-50 transition-colors text-sm"
        >
          Clear Selection
        </button>
        <button
          type="button"
          onClick={() => void downloadBivariateReportExcel()}
          disabled={isAnalyzingAll || isExcelDownloading}
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

export default BivariateAnalysisComponent;
