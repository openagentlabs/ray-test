import React, { useState, useEffect, useRef } from 'react';
import { useTheme } from '../contexts/ThemeContext';
import { 
  BarChart3, 
  TrendingUp, 
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

interface MultiFeatureBivariateAnalysisComponentProps {
  datasetId: string | null;
  targetVariable: string;
  currentStep?: number;
  maxFeatures?: number;
}

const MultiFeatureBivariateAnalysisComponent: React.FC<MultiFeatureBivariateAnalysisComponentProps> = ({
  datasetId,
  targetVariable,
  currentStep = 3,
  maxFeatures = 4,
}) => {
  const { isDark, theme } = useTheme();
  const [isAnalyzingAll, setIsAnalyzingAll] = useState(false);
  const [allAnalysisResults, setAllAnalysisResults] = useState<BivariateAnalysisAllResponse | null>(null);
  const [selectedVariables, setSelectedVariables] = useState<string[]>([]);
  const [variableAnalysisResults, setVariableAnalysisResults] = useState<Record<string, BivariateAnalysisSingleResponse>>({});
  const [error, setError] = useState<string>('');
  const [isExcelDownloading, setIsExcelDownloading] = useState(false);

  // Multi-select functionality state
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [filteredVariables, setFilteredVariables] = useState<string[]>([]);
  
  const mountedRef = useRef(true);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const isRunningAllRef = useRef(false);

  
  // Initialize component
  useEffect(() => {
    if (datasetId && targetVariable) {
      runAllVariablesAnalysis();
    }
    
    return () => {
      mountedRef.current = false;
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

  // Helper functions for multi-select functionality
  const handleVariableSearch = (term: string) => {
    setSearchTerm(term);
    setIsDropdownOpen(true);
  };

  const handleVariableSelection = (variable: string) => {
    if (selectedVariables.includes(variable)) {
      // Remove variable
      const newSelection = selectedVariables.filter(v => v !== variable);
      setSelectedVariables(newSelection);
      // Remove from analysis results
      setVariableAnalysisResults(prev => {
        const newResults = { ...prev };
        delete newResults[variable];
        return newResults;
      });
    } else {
      // Add variable if under max limit
      if (selectedVariables.length >= maxFeatures) {
        return; // Don't add more than maxFeatures
      }
      setSelectedVariables([...selectedVariables, variable]);
      // Fetch analysis for the new variable
      runSingleVariableAnalysis(variable);
    }
    setSearchTerm(variable);
    setIsDropdownOpen(false);
  };

  const toggleDropdown = () => {
    setIsDropdownOpen(!isDropdownOpen);
  };

  const clearAllSelectedVariables = () => {
    setSelectedVariables([]);
    setVariableAnalysisResults({});
    setSearchTerm('');
  };

  const runAllVariablesAnalysis = async () => {
    if (!datasetId || !targetVariable) return;
    if (isRunningAllRef.current) return;
    isRunningAllRef.current = true;

    console.log('MultiFeatureBivariateAnalysisComponent - Starting analysis');

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
      console.log('All variables analysis completed');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to run bivariate analysis');
    } finally {
      setIsAnalyzingAll(false);
      isRunningAllRef.current = false;
    }
  };

  const runSingleVariableAnalysis = async (variableName: string) => {
    if (!datasetId || !targetVariable) return;

    try {
      const result = await bivariateAnalysisService.getVariableAnalysis(
        datasetId,
        variableName,
        targetVariable
      );

      setVariableAnalysisResults(prev => ({
        ...prev,
        [variableName]: result
      }));
      console.log(`Analysis completed for variable: ${variableName}`);
    } catch (err) {
      console.error(`Failed to analyze variable ${variableName}:`, err);
    }
  };

  // Multi-Feature Bivariate Chart Component
  const MultiFeatureBivariateChart: React.FC<{ variables: string[] }> = ({ variables }) => {
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

    if (variables.length === 0) {
      return (
        <div className="text-center text-gray-500 dark:text-gray-400 py-8">
          <p>No variables selected for analysis</p>
        </div>
      );
    }

    // Prepare data for multi-variable chart
    const chartData = {
      labels: variables,
      datasets: [
        {
          type: 'bar' as const,
          label: 'Correlation with Target',
          data: variables.map(variable => {
            const result = variableAnalysisResults[variable];
            return result?.analysis_result?.summary?.correlation || 0;
          }),
          backgroundColor: variables.map((_, index) => {
            const colors = isDark
              ? [
                  'rgba(96, 165, 250, 0.6)',
                  'rgba(52, 211, 153, 0.55)',
                  'rgba(251, 191, 36, 0.55)',
                  'rgba(167, 139, 250, 0.55)',
                ]
              : [
                  'rgba(13, 110, 253, 0.7)',
                  'rgba(25, 135, 84, 0.7)',
                  'rgba(255, 193, 7, 0.7)',
                  'rgba(102, 16, 242, 0.7)',
                ];
            return colors[index % colors.length];
          }),
          borderColor: variables.map((_, index) => {
            const colors = isDark
              ? [
                  'rgba(186, 230, 253, 1)',
                  'rgba(167, 243, 208, 1)',
                  'rgba(253, 230, 138, 1)',
                  'rgba(221, 214, 254, 1)',
                ]
              : [
                  'rgba(13, 110, 253, 1)',
                  'rgba(25, 135, 84, 1)',
                  'rgba(255, 193, 7, 1)',
                  'rgba(102, 16, 242, 1)',
                ];
            return colors[index % colors.length];
          }),
          borderWidth: 1,
        },
      ],
    };

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
          text: `Multi-Variable Bivariate Analysis vs ${targetVariable}`,
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
          display: true,
          position: 'bottom' as const,
          labels: {
            usePointStyle: true,
            padding: 15,
            color: isDark ? '#d1d5db' : '#374151',
            font: {
              size: 12,
            },
          },
        },
        tooltip: {
          ...chartJsTooltipColors(isDark),
          callbacks: {
            label: function(context: any) {
              const value = context.parsed.y;
              const variable = variables[context.dataIndex];
              const result = variableAnalysisResults[variable];
              return [
                `${variable}: ${value.toFixed(4)}`,
                `Type: ${result?.analysis_result?.variable_type || 'unknown'}`,
                `Insight: ${result?.analysis_result?.summary?.key_insight || 'No insight available'}`,
              ];
            },
          },
        },
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
              size: 11,
              weight: 'bold' as const,
            },
          },
          title: {
            display: true,
            text: 'Variables',
            color: isDark ? '#d1d5db' : '#374151',
            font: {
              size: 12,
              weight: 'bold' as const,
            },
          },
        },
        y: {
          border: chartJsScaleBorder(isDark),
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
            text: 'Correlation with Target',
            color: isDark ? '#d1d5db' : '#374151',
            font: {
              size: 12,
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
          <Bar key={theme} data={chartData} options={chartOptions} />
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
                    Multi-Variable Bivariate Analysis - Expanded View
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
                      data={chartData}
                      options={{
                        ...chartOptions,
                        plugins: {
                          ...chartOptions.plugins,
                          title: {
                            ...chartOptions.plugins.title,
                            display: false,
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

  const downloadMultiFeatureReportExcel = async () => {
    if (selectedVariables.length === 0 || !datasetId) {
      alert('Select variables first, then download the report.');
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
        ['Selected variables', selectedVariables.length],
        ['Max variables allowed', maxFeatures],
      ];
      XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(infoAoa), 'Report info');

      const overviewHeader = ['Variable', 'Type', 'Correlation', 'Key Insight'];
      const overviewRows: (string | number)[][] = [overviewHeader];
      selectedVariables.forEach(variable => {
        const result = variableAnalysisResults[variable];
        if (result) {
          overviewRows.push([
            variable,
            result.analysis_result.variable_type,
            result.analysis_result.summary?.correlation || '',
            result.analysis_result.summary?.key_insight || '',
          ]);
        }
      });
      XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(overviewRows), 'Selected Variables');

      const safeDataset = datasetId.replace(/[^a-zA-Z0-9_-]/g, '_');
      const fname = `Multi_Feature_Bivariate_Analysis_${safeDataset}_${new Date().toISOString().split('T')[0]}.xlsx`;
      XLSX.writeFile(wb, fname);
    } catch (e) {
      console.error('Excel export failed:', e);
      alert('Could not build the Excel file. Try again after analysis finishes loading.');
    } finally {
      setIsExcelDownloading(false);
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

  if (isAnalyzingAll) {
    return (
      <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700 rounded-lg p-6 text-center">
        <Loader className="h-8 w-8 text-blue-600 animate-spin mx-auto mb-3" />
        <h3 className="font-medium text-blue-900 dark:text-blue-300 mb-2">Analyzing Variables</h3>
        <p className="text-blue-700 dark:text-blue-400 text-sm">
          Preparing bivariate analysis for all variables...
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
        <h3 className="font-medium text-gray-900 dark:text-gray-100 mb-2">Multi-Feature Bivariate Analysis</h3>
        <p className="text-gray-600 dark:text-gray-400 text-sm mb-4">
          Select up to {maxFeatures} variables to analyze their relationship with the target variable.
        </p>
        <button
          type="button"
          onClick={() => runAllVariablesAnalysis()}
          className="px-4 py-2 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] transition-colors"
        >
          Start Analysis
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Multi-Variable Selection */}
      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
          <h4 className="font-medium text-gray-900 dark:text-gray-100 flex items-center gap-2 min-w-0">
            <BarChart3 className="h-5 w-5 shrink-0 text-blue-600" />
            <span>Select Variables to Analyze (Max {maxFeatures})</span>
          </h4>
          
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-500 dark:text-gray-400">
              {selectedVariables.length}/{maxFeatures} selected
            </span>
            {selectedVariables.length > 0 && (
              <button
                onClick={clearAllSelectedVariables}
                className="text-sm text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-300"
              >
                Clear all
              </button>
            )}
          </div>
        </div>

        {/* Multi-Select Dropdown */}
        <div className="space-y-2">
          <div className="relative" ref={dropdownRef}>
            <div className="relative">
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => handleVariableSearch(e.target.value)}
                onFocus={() => setIsDropdownOpen(true)}
                placeholder={`Select up to ${maxFeatures} variables...`}
                className="w-full px-3 py-2 pr-10 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500"
              />
              <div className="absolute inset-y-0 right-0 flex items-center pr-3">
                <Search className="h-4 w-4 text-gray-400 mr-1" />
                <button
                  type="button"
                  onClick={toggleDropdown}
                  className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
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
              <div className="absolute z-10 w-full mt-1 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg shadow-lg max-h-60 overflow-y-auto">
                {filteredVariables.length === 0 ? (
                  <div className="px-3 py-2 text-gray-500 dark:text-gray-400 text-sm">
                    {searchTerm ? 'No variables match your search' : 'No variables available'}
                  </div>
                ) : (
                  filteredVariables.map((variable) => {
                    const isSelected = selectedVariables.includes(variable);
                    const varData = allAnalysisResults?.analysis_results[variable];
                    const displayType = varData?.variable_type || 'unknown';
                    
                    return (
                      <div
                        key={variable}
                        className="flex items-center px-3 py-2 hover:bg-gray-50 dark:hover:bg-gray-600/60"
                      >
                        <label className="flex items-center cursor-pointer w-full">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => handleVariableSelection(variable)}
                            disabled={!isSelected && selectedVariables.length >= maxFeatures}
                            className="mr-2 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 dark:border-gray-500 rounded bg-white dark:bg-gray-700 disabled:opacity-50"
                          />
                          <span className="text-sm text-gray-900 dark:text-gray-100">
                            {variable} <span className="text-gray-500 dark:text-gray-400">({displayType})</span>
                          </span>
                        </label>
                      </div>
                    );
                  })
                )}
              </div>
            )}
          </div>
        </div>

        {/* Selected Variables Display */}
        {selectedVariables.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {selectedVariables.map((variable) => (
              <span
                key={variable}
                className="inline-flex items-center gap-1 px-2 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300 rounded-full text-sm"
              >
                {variable}
                <button
                  onClick={() => handleVariableSelection(variable)}
                  className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-200"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Multi-Feature Chart */}
      {selectedVariables.length > 0 && (
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
            <h4 className="font-medium text-gray-900 dark:text-gray-100 flex items-center gap-2 min-w-0">
              <TrendingUp className="h-5 w-5 shrink-0 text-green-600" />
              <span>Multi-Variable Analysis Results</span>
            </h4>
            
            <button
              onClick={downloadMultiFeatureReportExcel}
              disabled={isExcelDownloading}
              className="flex items-center gap-2 px-3 py-1.5 text-sm bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white rounded-lg transition-colors"
              title="Download Multi-Feature Analysis Report"
            >
              <FileDown className="h-4 w-4" />
              {isExcelDownloading ? 'Downloading...' : 'Download Report'}
            </button>
          </div>

          <MultiFeatureBivariateChart variables={selectedVariables} />
        </div>
      )}
    </div>
  );
};

export default MultiFeatureBivariateAnalysisComponent;
