import React, { useState, useEffect, useMemo } from 'react';
import { BarChart3, TrendingUp, TrendingDown, Minus, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react';

/**
 * Interface for numeric column EDA statistics
 */
export interface NumericEDAStats {
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
}

/**
 * Interface for categorical column EDA statistics
 */
export interface CategoricalEDAStats {
  column: string;
  unique_count: number;
  top_category: string;
  top_category_count: number;
  top_category_percentage: number;
  missing_count: number;
  missing_percentage: number;
  value_distribution: Record<string, number>;
}

/**
 * Interface for date column EDA statistics
 */
export interface DateEDAStats {
  column: string;
  min_date: string;
  max_date: string;
  date_range_days: number;
  unique_count: number;
  missing_count: number;
  missing_percentage: number;
  most_frequent_date: string;
  most_frequent_count: number;
}

/**
 * Complete EDA snapshot for a dataset
 */
export interface EDASnapshot {
  timestamp: string;
  totalRows: number;
  totalColumns: number;
  numericStats: NumericEDAStats[];
  categoricalStats: CategoricalEDAStats[];
  dateStats: DateEDAStats[];
  treatmentApplied?: string;
}

/**
 * Props for EDAComparisonPanel
 */
interface EDAComparisonPanelProps {
  /** Original EDA snapshot (before any treatment) */
  originalEDA: EDASnapshot | null;
  /** Current EDA snapshot (after treatment) */
  currentEDA: EDASnapshot | null;
  /** Whether data is loading */
  isLoading?: boolean;
  /** Callback to refresh EDA */
  onRefresh?: () => void;
  /** Active tab */
  activeTab: 'original' | 'comparison';
  /** Callback when tab changes */
  onTabChange: (tab: 'original' | 'comparison') => void;
  /** Whether comparison tab should be visible */
  showComparisonTab: boolean;
}

/**
 * Helper to calculate percentage change
 */
const calculateChange = (original: number, current: number): { value: number; direction: 'up' | 'down' | 'same' } => {
  if (original === 0 && current === 0) return { value: 0, direction: 'same' };
  if (original === 0) return { value: 100, direction: 'up' };
  const change = ((current - original) / original) * 100;
  if (Math.abs(change) < 0.01) return { value: 0, direction: 'same' };
  return { value: Math.abs(change), direction: change > 0 ? 'up' : 'down' };
};

/**
 * Component to display change indicator
 */
const ChangeIndicator: React.FC<{ original: number; current: number; inverse?: boolean }> = ({ 
  original, 
  current, 
  inverse = false 
}) => {
  const { value, direction } = calculateChange(original, current);
  
  if (direction === 'same') {
    return <Minus className="h-3 w-3 text-gray-400" />;
  }
  
  // For some metrics, decrease is good (e.g., missing values)
  const isPositive = inverse ? direction === 'down' : direction === 'up';
  
  return (
    <span className={`flex items-center text-xs ${isPositive ? 'text-green-600' : 'text-red-600'}`}>
      {direction === 'up' ? (
        <TrendingUp className="h-3 w-3 mr-0.5" />
      ) : (
        <TrendingDown className="h-3 w-3 mr-0.5" />
      )}
      {value.toFixed(1)}%
    </span>
  );
};

/**
 * EDAComparisonPanel - Component for displaying and comparing EDA statistics
 * 
 * Features:
 * - Original EDA tab showing baseline statistics
 * - Comparison tab showing changes after treatment
 * - Collapsible sections for numeric, categorical, and date columns
 * - Visual indicators for changes (up/down arrows with percentages)
 */
const EDAComparisonPanel: React.FC<EDAComparisonPanelProps> = ({
  originalEDA,
  currentEDA,
  isLoading = false,
  onRefresh,
  activeTab,
  onTabChange,
  showComparisonTab
}) => {
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    numeric: true,
    categorical: true,
    date: true
  });

  const toggleSection = (section: string) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  /**
   * Render numeric statistics table
   */
  const renderNumericStats = (stats: NumericEDAStats[], comparisonStats?: NumericEDAStats[]) => {
    if (!stats || stats.length === 0) {
      return (
        <p className="text-sm text-gray-500 dark:text-gray-400 italic py-2">
          No numeric columns found
        </p>
      );
    }

    const getComparisonStat = (column: string) => {
      return comparisonStats?.find(s => s.column === column);
    };

    return (
      <div className="overflow-x-auto">
        <table className="min-w-full text-xs">
          <thead>
            <tr className="bg-gray-50 dark:bg-gray-800">
              <th className="px-2 py-1.5 text-left font-medium text-gray-600 dark:text-gray-400">Column</th>
              <th className="px-2 py-1.5 text-right font-medium text-gray-600 dark:text-gray-400">Count</th>
              <th className="px-2 py-1.5 text-right font-medium text-gray-600 dark:text-gray-400">Mean</th>
              <th className="px-2 py-1.5 text-right font-medium text-gray-600 dark:text-gray-400">Std</th>
              <th className="px-2 py-1.5 text-right font-medium text-gray-600 dark:text-gray-400">Min</th>
              <th className="px-2 py-1.5 text-right font-medium text-gray-600 dark:text-gray-400">25%</th>
              <th className="px-2 py-1.5 text-right font-medium text-gray-600 dark:text-gray-400">50%</th>
              <th className="px-2 py-1.5 text-right font-medium text-gray-600 dark:text-gray-400">75%</th>
              <th className="px-2 py-1.5 text-right font-medium text-gray-600 dark:text-gray-400">Max</th>
              <th className="px-2 py-1.5 text-right font-medium text-gray-600 dark:text-gray-400">Missing %</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
            {stats.map((stat) => {
              const comparison = getComparisonStat(stat.column);
              const showComparison = activeTab === 'comparison' && comparison;
              
              return (
                <tr key={stat.column} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                  <td className="px-2 py-1.5 font-medium text-gray-900 dark:text-gray-100 truncate max-w-[120px]" title={stat.column}>
                    {stat.column}
                  </td>
                  <td className="px-2 py-1.5 text-right text-gray-700 dark:text-gray-300">
                    <div className="flex items-center justify-end space-x-1">
                      <span>{stat.count.toLocaleString()}</span>
                      {showComparison && <ChangeIndicator original={comparison.count} current={stat.count} />}
                    </div>
                  </td>
                  <td className="px-2 py-1.5 text-right text-gray-700 dark:text-gray-300">
                    {stat.mean.toFixed(2)}
                  </td>
                  <td className="px-2 py-1.5 text-right text-gray-700 dark:text-gray-300">
                    {stat.std.toFixed(2)}
                  </td>
                  <td className="px-2 py-1.5 text-right text-gray-700 dark:text-gray-300">
                    {stat.min.toFixed(2)}
                  </td>
                  <td className="px-2 py-1.5 text-right text-gray-700 dark:text-gray-300">
                    {stat.percentile_25.toFixed(2)}
                  </td>
                  <td className="px-2 py-1.5 text-right text-gray-700 dark:text-gray-300">
                    {stat.percentile_50.toFixed(2)}
                  </td>
                  <td className="px-2 py-1.5 text-right text-gray-700 dark:text-gray-300">
                    {stat.percentile_75.toFixed(2)}
                  </td>
                  <td className="px-2 py-1.5 text-right text-gray-700 dark:text-gray-300">
                    {stat.max.toFixed(2)}
                  </td>
                  <td className="px-2 py-1.5 text-right text-gray-700 dark:text-gray-300">
                    <div className="flex items-center justify-end space-x-1">
                      <span>{stat.missing_percentage.toFixed(1)}%</span>
                      {showComparison && <ChangeIndicator original={comparison.missing_percentage} current={stat.missing_percentage} inverse />}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  };

  /**
   * Render categorical statistics table
   */
  const renderCategoricalStats = (stats: CategoricalEDAStats[], comparisonStats?: CategoricalEDAStats[]) => {
    if (!stats || stats.length === 0) {
      return (
        <p className="text-sm text-gray-500 dark:text-gray-400 italic py-2">
          No categorical columns found
        </p>
      );
    }

    const getComparisonStat = (column: string) => {
      return comparisonStats?.find(s => s.column === column);
    };

    return (
      <div className="overflow-x-auto">
        <table className="min-w-full text-xs">
          <thead>
            <tr className="bg-gray-50 dark:bg-gray-800">
              <th className="px-2 py-1.5 text-left font-medium text-gray-600 dark:text-gray-400">Column</th>
              <th className="px-2 py-1.5 text-right font-medium text-gray-600 dark:text-gray-400">Unique</th>
              <th className="px-2 py-1.5 text-left font-medium text-gray-600 dark:text-gray-400">Top Category</th>
              <th className="px-2 py-1.5 text-right font-medium text-gray-600 dark:text-gray-400">Top %</th>
              <th className="px-2 py-1.5 text-right font-medium text-gray-600 dark:text-gray-400">Missing %</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
            {stats.map((stat) => {
              const comparison = getComparisonStat(stat.column);
              const showComparison = activeTab === 'comparison' && comparison;
              
              return (
                <tr key={stat.column} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                  <td className="px-2 py-1.5 font-medium text-gray-900 dark:text-gray-100 truncate max-w-[120px]" title={stat.column}>
                    {stat.column}
                  </td>
                  <td className="px-2 py-1.5 text-right text-gray-700 dark:text-gray-300">
                    <div className="flex items-center justify-end space-x-1">
                      <span>{stat.unique_count.toLocaleString()}</span>
                      {showComparison && <ChangeIndicator original={comparison.unique_count} current={stat.unique_count} />}
                    </div>
                  </td>
                  <td className="px-2 py-1.5 text-gray-700 dark:text-gray-300 truncate max-w-[100px]" title={stat.top_category}>
                    {stat.top_category || 'N/A'}
                  </td>
                  <td className="px-2 py-1.5 text-right text-gray-700 dark:text-gray-300">
                    {stat.top_category_percentage.toFixed(1)}%
                  </td>
                  <td className="px-2 py-1.5 text-right text-gray-700 dark:text-gray-300">
                    <div className="flex items-center justify-end space-x-1">
                      <span>{stat.missing_percentage.toFixed(1)}%</span>
                      {showComparison && <ChangeIndicator original={comparison.missing_percentage} current={stat.missing_percentage} inverse />}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  };

  /**
   * Render date statistics table
   */
  const renderDateStats = (stats: DateEDAStats[], comparisonStats?: DateEDAStats[]) => {
    if (!stats || stats.length === 0) {
      return (
        <p className="text-sm text-gray-500 dark:text-gray-400 italic py-2">
          No date columns found
        </p>
      );
    }

    const getComparisonStat = (column: string) => {
      return comparisonStats?.find(s => s.column === column);
    };

    return (
      <div className="overflow-x-auto">
        <table className="min-w-full text-xs">
          <thead>
            <tr className="bg-gray-50 dark:bg-gray-800">
              <th className="px-2 py-1.5 text-left font-medium text-gray-600 dark:text-gray-400">Column</th>
              <th className="px-2 py-1.5 text-left font-medium text-gray-600 dark:text-gray-400">Min Date</th>
              <th className="px-2 py-1.5 text-left font-medium text-gray-600 dark:text-gray-400">Max Date</th>
              <th className="px-2 py-1.5 text-right font-medium text-gray-600 dark:text-gray-400">Range (days)</th>
              <th className="px-2 py-1.5 text-right font-medium text-gray-600 dark:text-gray-400">Unique</th>
              <th className="px-2 py-1.5 text-right font-medium text-gray-600 dark:text-gray-400">Missing %</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
            {stats.map((stat) => {
              const comparison = getComparisonStat(stat.column);
              const showComparison = activeTab === 'comparison' && comparison;
              
              return (
                <tr key={stat.column} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                  <td className="px-2 py-1.5 font-medium text-gray-900 dark:text-gray-100 truncate max-w-[120px]" title={stat.column}>
                    {stat.column}
                  </td>
                  <td className="px-2 py-1.5 text-gray-700 dark:text-gray-300">
                    {stat.min_date || 'N/A'}
                  </td>
                  <td className="px-2 py-1.5 text-gray-700 dark:text-gray-300">
                    {stat.max_date || 'N/A'}
                  </td>
                  <td className="px-2 py-1.5 text-right text-gray-700 dark:text-gray-300">
                    {stat.date_range_days.toLocaleString()}
                  </td>
                  <td className="px-2 py-1.5 text-right text-gray-700 dark:text-gray-300">
                    {stat.unique_count.toLocaleString()}
                  </td>
                  <td className="px-2 py-1.5 text-right text-gray-700 dark:text-gray-300">
                    <div className="flex items-center justify-end space-x-1">
                      <span>{stat.missing_percentage.toFixed(1)}%</span>
                      {showComparison && <ChangeIndicator original={comparison.missing_percentage} current={stat.missing_percentage} inverse />}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  };

  // Determine which EDA to display based on active tab
  const displayEDA = activeTab === 'original' ? originalEDA : currentEDA;
  const comparisonEDA = activeTab === 'comparison' ? originalEDA : undefined;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        <span className="ml-3 text-gray-600 dark:text-gray-400">Loading EDA statistics...</span>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Tab Navigation */}
      <div className="flex items-center justify-between border-b border-gray-200 dark:border-gray-700">
        <div className="flex space-x-4">
          <button
            type="button"
            onClick={() => onTabChange('original')}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'original'
                ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
            }`}
          >
            Original EDA
          </button>
          {showComparisonTab && (
            <button
              type="button"
              onClick={() => onTabChange('comparison')}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'comparison'
                  ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
              }`}
            >
              EDA Comparison
            </button>
          )}
        </div>
        {onRefresh && (
          <button
            type="button"
            onClick={onRefresh}
            className="p-1.5 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300 transition-colors"
            title="Refresh EDA"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Summary Stats */}
      {displayEDA && (
        <div className="grid grid-cols-3 gap-4 mb-4">
          <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
              {displayEDA.totalRows.toLocaleString()}
            </div>
            <div className="text-xs text-blue-600 dark:text-blue-400">Total Rows</div>
            {activeTab === 'comparison' && comparisonEDA && (
              <ChangeIndicator original={comparisonEDA.totalRows} current={displayEDA.totalRows} />
            )}
          </div>
          <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">
              {displayEDA.totalColumns}
            </div>
            <div className="text-xs text-green-600 dark:text-green-400">Total Columns</div>
          </div>
          <div className="bg-purple-50 dark:bg-purple-900/20 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">
              {displayEDA.timestamp ? new Date(displayEDA.timestamp).toLocaleDateString() : 'N/A'}
            </div>
            <div className="text-xs text-purple-600 dark:text-purple-400">Snapshot Date</div>
          </div>
        </div>
      )}

      {/* Treatment Applied Badge */}
      {activeTab === 'comparison' && currentEDA?.treatmentApplied && (
        <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-700 rounded-lg p-3">
          <span className="text-sm text-yellow-800 dark:text-yellow-200">
            <strong>Treatment Applied:</strong> {currentEDA.treatmentApplied}
          </span>
        </div>
      )}

      {!displayEDA ? (
        <div className="text-center py-8 text-gray-500 dark:text-gray-400">
          <BarChart3 className="h-12 w-12 mx-auto mb-3 opacity-50" />
          <p>No EDA data available</p>
          <p className="text-sm mt-1">Upload a dataset to see EDA statistics</p>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Numeric Columns Section */}
          <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
            <button
              type="button"
              onClick={() => toggleSection('numeric')}
              className="w-full flex items-center justify-between px-4 py-2 bg-gray-50 dark:bg-gray-800 
                         hover:bg-gray-100 dark:hover:bg-gray-750 transition-colors"
            >
              <span className="font-medium text-gray-900 dark:text-gray-100">
                Numeric Columns ({displayEDA.numericStats?.length || 0})
              </span>
              {expandedSections.numeric ? (
                <ChevronUp className="h-4 w-4 text-gray-500" />
              ) : (
                <ChevronDown className="h-4 w-4 text-gray-500" />
              )}
            </button>
            {expandedSections.numeric && (
              <div className="p-3">
                {renderNumericStats(displayEDA.numericStats, comparisonEDA?.numericStats)}
              </div>
            )}
          </div>

          {/* Categorical Columns Section */}
          <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
            <button
              type="button"
              onClick={() => toggleSection('categorical')}
              className="w-full flex items-center justify-between px-4 py-2 bg-gray-50 dark:bg-gray-800 
                         hover:bg-gray-100 dark:hover:bg-gray-750 transition-colors"
            >
              <span className="font-medium text-gray-900 dark:text-gray-100">
                Categorical Columns ({displayEDA.categoricalStats?.length || 0})
              </span>
              {expandedSections.categorical ? (
                <ChevronUp className="h-4 w-4 text-gray-500" />
              ) : (
                <ChevronDown className="h-4 w-4 text-gray-500" />
              )}
            </button>
            {expandedSections.categorical && (
              <div className="p-3">
                {renderCategoricalStats(displayEDA.categoricalStats, comparisonEDA?.categoricalStats)}
              </div>
            )}
          </div>

          {/* Date Columns Section */}
          <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
            <button
              type="button"
              onClick={() => toggleSection('date')}
              className="w-full flex items-center justify-between px-4 py-2 bg-gray-50 dark:bg-gray-800 
                         hover:bg-gray-100 dark:hover:bg-gray-750 transition-colors"
            >
              <span className="font-medium text-gray-900 dark:text-gray-100">
                Date Columns ({displayEDA.dateStats?.length || 0})
              </span>
              {expandedSections.date ? (
                <ChevronUp className="h-4 w-4 text-gray-500" />
              ) : (
                <ChevronDown className="h-4 w-4 text-gray-500" />
              )}
            </button>
            {expandedSections.date && (
              <div className="p-3">
                {renderDateStats(displayEDA.dateStats, comparisonEDA?.dateStats)}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default EDAComparisonPanel;
