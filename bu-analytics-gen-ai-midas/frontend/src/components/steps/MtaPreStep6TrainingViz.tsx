import React from "react";
import { Filter, Settings, BarChart3, TrendingUp } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  LineChart,
  Line,
} from "recharts";
import { getSoleBestIterationIndexForDisplay, MTA_THEAD } from "./modelTrainingMtaUi";

type OptimizedHpInfo = {
  entries: [string, unknown][];
  optimization_method?: string | null;
};

function formatHpEntries(hp: unknown): [string, unknown][] {
  if (!hp || typeof hp !== "object") return [];
  return Object.entries(hp as Record<string, unknown>).filter(
    ([k]) => !["random_state", "verbose", "n_jobs"].includes(k)
  );
}

/** Hyperparameters from the best iteration (or model-level) for the selected algorithm / segment. */
function pickBestIterationHyperparameters(
  viz: any,
  selectedAlgorithm: string,
  selectedSegment: string
): OptimizedHpInfo {
  if (!viz || !selectedAlgorithm) return { entries: [] };

  if (viz.segment_results) {
    const segmentIds =
      selectedSegment === "all"
        ? viz.segments?.length
          ? [String(viz.segments[0])]
          : []
        : [String(selectedSegment)];
    for (const segmentId of segmentIds) {
      const segmentResult = viz.segment_results[`segment_${segmentId}`];
      const algorithmResult = segmentResult?.results?.find((r: any) => r.algorithm === selectedAlgorithm);
      if (!algorithmResult) continue;
      const hist = algorithmResult.iteration_history;
      if (Array.isArray(hist) && hist.length > 0) {
        const idx = getSoleBestIterationIndexForDisplay(hist);
        const iter = idx !== null ? hist[idx] : hist[hist.length - 1];
        return {
          entries: formatHpEntries(iter?.hyperparameters),
          optimization_method:
            algorithmResult?.optimization_method ??
            segmentResult?.best_model_selection?.best_model?.optimization_method ??
            null,
        };
      }
      return {
        entries: formatHpEntries(algorithmResult.hyperparameters),
        optimization_method: algorithmResult?.optimization_method ?? null,
      };
    }
    return { entries: [] };
  }

  const selectedResult = viz.results?.find((r: any) => r.algorithm === selectedAlgorithm);
  if (!selectedResult) return { entries: [] };
  const hist = selectedResult.iteration_history;
  if (Array.isArray(hist) && hist.length > 0) {
    const idx = getSoleBestIterationIndexForDisplay(hist);
    const iter = idx !== null ? hist[idx] : hist[hist.length - 1];
    return {
      entries: formatHpEntries(iter?.hyperparameters),
      optimization_method:
        selectedResult?.optimization_method ?? viz.best_model_selection?.best_model?.optimization_method ?? null,
    };
  }
  return {
    entries: formatHpEntries(selectedResult.hyperparameters),
    optimization_method:
      selectedResult?.optimization_method ?? viz.best_model_selection?.best_model?.optimization_method ?? null,
  };
}

export interface MtaPreStep6TrainingVizProps {
  viz: any;
  isDarkMode: boolean;
  targetMetricManual: string;
  selectedAlgorithmForHistory: string;
  setSelectedAlgorithmForHistory: (v: string) => void;
  selectedSegmentForHistory: string;
  setSelectedSegmentForHistory: (v: string) => void;
  comparisonTab: "score" | "history";
  setComparisonTab: (v: "score" | "history") => void;
  comparisonAlgorithmFilter: string;
  setComparisonAlgorithmFilter: (v: string) => void;
  comparisonSegmentFilter: string;
  setComparisonSegmentFilter: (v: string) => void;
  selectedAlgorithmsForComparison: string[];
  setSelectedAlgorithmsForComparison: React.Dispatch<React.SetStateAction<string[]>>;
  getAvailableMetrics: () => string[];
  getScoreComparisonData: () => any[];
  getTrainingHistoryData: () => any[];
  getSelectedAlgorithms: () => string[];
  getPrimaryMetricKey: (problemType: string, targetMetric?: string) => string;
  getMetricDisplayName: (metricKey: string) => string;
  getBestScoreFromHistory: (result: any, targetMetric?: string) => number;
}

export const MtaPreStep6TrainingViz: React.FC<MtaPreStep6TrainingVizProps> = (props) => {
  const {
    viz,
    isDarkMode,
    targetMetricManual,
    selectedAlgorithmForHistory,
    setSelectedAlgorithmForHistory,
    selectedSegmentForHistory,
    setSelectedSegmentForHistory,
    comparisonTab,
    setComparisonTab,
    comparisonAlgorithmFilter,
    setComparisonAlgorithmFilter,
    comparisonSegmentFilter,
    setComparisonSegmentFilter,
    selectedAlgorithmsForComparison,
    setSelectedAlgorithmsForComparison,
    getAvailableMetrics,
    getScoreComparisonData,
    getTrainingHistoryData,
    getSelectedAlgorithms,
    getPrimaryMetricKey,
    getMetricDisplayName,
    getBestScoreFromHistory,
  } = props;

  const optimizedHpInfo = React.useMemo(
    () => pickBestIterationHyperparameters(viz, selectedAlgorithmForHistory, selectedSegmentForHistory),
    [viz, selectedAlgorithmForHistory, selectedSegmentForHistory]
  );

  const segmentTrainingBestAlgorithm = React.useMemo(() => {
    if (!viz?.segment_results) return "";
    const sid = selectedSegmentForHistory === "all" ? viz.segments?.[0] : selectedSegmentForHistory;
    if (sid == null || sid === "") return "";
    const sr = viz.segment_results[`segment_${sid}`];
    const b = sr?.best_model_selection?.best_algorithm;
    return typeof b === "string" ? b : "";
  }, [viz, selectedSegmentForHistory]);

  const flatBestAlgorithm = React.useMemo(() => {
    if (!viz || viz.segment_results) return "";
    const b = viz.best_model_selection?.best_algorithm;
    return typeof b === "string" ? b : "";
  }, [viz]);

  if (!viz) return null;
  const hasFlat = Array.isArray(viz.results) && viz.results.length > 0;
  const hasSeg = !!(viz.segment_results && Object.keys(viz.segment_results).length > 0);
  if (!hasFlat && !hasSeg) return null;

  return (
    <>
                  {/* Segment and Algorithm Selection Dropdowns - moved above Iteration History */}
                  <div className="mb-6">
                      {/* Check if this is segment training */}
                      {viz.segment_results ? (
                        /* Segment Training - Show both Algorithm and Segment filters */
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">Selected Algorithm</label>
                            <select
                              value={selectedAlgorithmForHistory}
                              onChange={(e) => setSelectedAlgorithmForHistory(e.target.value)}
                              className="w-full px-3 py-2 border border-gray-300 dark:border-slate-700 rounded-lg dark:bg-slate-900 dark:text-white"
                            >
                              <option value="">Select algorithm to view details</option>
                              {Array.from(new Set(
                                Object.values(viz.segment_results || {})
                                  .flatMap((segResult: any) => 
                                    segResult.results?.map((r: any) => r.algorithm) || []
                                  )
                              )).map((algorithm: any) => (
                                <option key={algorithm} value={algorithm}>
                                  {algorithm.toUpperCase()}
                                  {segmentTrainingBestAlgorithm && algorithm === segmentTrainingBestAlgorithm
                                    ? " — Best"
                                    : ""}
                                </option>
                              ))}
                            </select>
                          </div>
                          
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">Selected Segment</label>
                            <select
                              value={selectedSegmentForHistory}
                              onChange={(e) => setSelectedSegmentForHistory(e.target.value)}
                              className="w-full px-3 py-2 border border-gray-300 dark:border-slate-700 rounded-lg dark:bg-slate-900 dark:text-white"
                            >
                              <option value="all">All Segments</option>
                              {viz.segments?.map((seg: string) => (
                                <option key={seg} value={seg}>
                                  Segment: {seg}
                                </option>
                              ))}
                            </select>
                          </div>
                        </div>
                      ) : (
                        /* Regular Training - Show only Algorithm filter */
                        <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">Selected Algorithm</label>
                      <select
                        value={selectedAlgorithmForHistory}
                        onChange={(e) => setSelectedAlgorithmForHistory(e.target.value)}
                        className="px-3 py-2 border border-gray-300 dark:border-slate-700 rounded-lg dark:bg-slate-900 dark:text-white"
                      >
                        <option value="">
                          {(() => {
                            // Determine which results to use (manual or auto training)
                            const results = viz;
                            return results?.results?.length > 1
                              ? `Select algorithm to view details (${results.results.length} trained)`
                              : 'Select algorithm to view details';
                          })()}
                        </option>
                        {(() => {
                          // Determine which results to use (manual or auto training)
                          const results = viz;
                          return results.results?.map((result: any) => {
                            const pt = results.problem_type;
                            const scoreKey = getPrimaryMetricKey(pt, targetMetricManual);
                            const bestScore = getBestScoreFromHistory(result, targetMetricManual);
                          const scoreLabel = getMetricDisplayName(scoreKey);

                          const isBestOpt =
                            (typeof result.model_id === "string" &&
                              result.model_id === viz.best_model_selection?.best_model_id) ||
                            result.algorithm === flatBestAlgorithm;
                          return (
                            <option key={result.algorithm} value={result.algorithm}>
                              {result.algorithm.toUpperCase()} @ {scoreLabel}: {bestScore.toFixed(4)}
                              {isBestOpt ? " — Best" : ""}
                            </option>
                          );
                        });
                        })()}
                      </select>
                        </div>
                      )}
                    </div>

                  {selectedAlgorithmForHistory && optimizedHpInfo.entries.length > 0 && (
                    <div className="mb-6 rounded-lg border border-gray-200 dark:border-slate-700 bg-gray-50 dark:bg-slate-900/80 p-4">
                      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                        <h4 className="text-sm font-semibold text-gray-900 dark:text-white">
                          Optimized hyperparameters (best iteration)
                        </h4>
                        {optimizedHpInfo.optimization_method && (
                          <span className="text-[11px] px-2 py-1 rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200 font-medium">
                            {optimizedHpInfo.optimization_method === "bayesian_optimization"
                              ? "Bayesian optimization"
                              : optimizedHpInfo.optimization_method === "random_search"
                                ? "Random search"
                                : String(optimizedHpInfo.optimization_method)}
                          </span>
                        )}
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                        {optimizedHpInfo.entries.map(([key, value]) => (
                          <div
                            key={key}
                            className="rounded-lg border border-gray-200 dark:border-slate-600 bg-white dark:bg-slate-950 p-3"
                          >
                            <div className="text-[11px] text-gray-500 dark:text-gray-400 mb-1 capitalize">
                              {key.replace(/_/g, " ")}
                            </div>
                            <div className="text-sm font-semibold text-gray-900 dark:text-white break-all">
                              {typeof value === "number"
                                ? Number.isInteger(value)
                                  ? value
                                  : (value as number).toFixed(4)
                                : String(value ?? "—")}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Iteration History Table */}
                  {selectedAlgorithmForHistory && (
                    <div className="mt-8 border border-gray-200 dark:border-slate-700 rounded-lg p-6 bg-white dark:bg-slate-900/70">
                      <h4 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">
                        Iteration History - {selectedAlgorithmForHistory.toUpperCase()}
                        {viz?.segment_results && selectedSegmentForHistory !== 'all' && (
                          <span className="text-sm font-normal text-purple-600 dark:text-purple-300 ml-2">
                            (Segment: {selectedSegmentForHistory})
                          </span>
                        )}
                      </h4>
                      <div className="text-sm text-gray-600 dark:text-gray-400 mb-4">Detailed score progression throughout training</div>

                      <div className="overflow-x-auto">
                        <table className="w-full mta-iteration-history-table">
                          <thead className={MTA_THEAD}>
                            <tr>
                              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:!text-white/90">Iteration</th>
                                {(() => {
                                  // Determine which results to use (manual or auto training)
                                  const results = viz;
                                
                                // Enhanced problem type detection for segment training
                                let pt = results.problem_type;
                                
                                // If problem_type is not set at top level, try to infer from segment results
                                if (!pt && results.segment_results) {
                                  // Look at the first available segment result to determine problem type
                                  const firstSegmentResult = Object.values(results.segment_results)[0] as any;
                                  if (firstSegmentResult && firstSegmentResult.results && firstSegmentResult.results.length > 0) {
                                    const firstModel = firstSegmentResult.results[0];
                                    if (firstModel.metrics) {
                                      // Check if it has classification metrics
                                      if (firstModel.metrics.auc !== undefined || firstModel.metrics.precision !== undefined || firstModel.metrics.recall !== undefined) {
                                        pt = 'classification';
                                      } else if (firstModel.metrics.r2 !== undefined || firstModel.metrics.rmse !== undefined) {
                                        pt = 'regression';
                                      }
                                    }
                                  }
                                }
                                
                                // Default to classification if still not determined
                                if (!pt) {
                                  pt = 'classification';
                                }
                                
                                // Define columns based on problem type
                                const getColumnConfig = (problemType: string) => {
                                  if (problemType === 'classification') {
                                    return {
                                      primary: 'auc',
                                      secondary: ['accuracy', 'precision', 'recall', 'f1', 'ks_statistic'],
                                      loss: 'log_loss',
                                      showLogLoss: true
                                    };
                                  } else {
                                    return {
                                      primary: 'r2',
                                      secondary: ['rmse', 'mae', 'mse', 'mape'],
                                      loss: null,
                                      showLogLoss: false
                                    };
                                  }
                                };
                                
                                const config = getColumnConfig(pt);
                                const allMetrics = [config.primary, ...config.secondary];
                                
                                return allMetrics.map(metric => (
                                  <th key={metric} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:!text-white/90">
                                    {getMetricDisplayName(metric)}
                                  </th>
                                ));
                              })()}
                              {(() => {
                                // Add Log Loss column only for classification
                                const results = viz;
                                
                                // Enhanced problem type detection for segment training (same logic as above)
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
                                
                                if (pt === 'classification') {
                                  return (
                                    <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:!text-white/90">
                                      Log Loss
                                    </th>
                                  );
                                }
                                return null;
                              })()}
                              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:!text-white/90">Improvement</th>
                              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:!text-white/90">Status</th>
                            </tr>
                          </thead>
                          <tbody className="bg-white dark:bg-slate-950 divide-y divide-gray-200 dark:divide-slate-700">
                            {(() => {
                              // Determine which results to use (manual or auto training)
                              const results = viz;
                              
                              // Enhanced problem type detection for segment training
                              let pt = results.problem_type;
                              
                              // If problem_type is not set at top level, try to infer from segment results
                              if (!pt && results.segment_results) {
                                // Look at the first available segment result to determine problem type
                                const firstSegmentResult = Object.values(results.segment_results)[0] as any;
                                if (firstSegmentResult && firstSegmentResult.results && firstSegmentResult.results.length > 0) {
                                  const firstModel = firstSegmentResult.results[0];
                                  if (firstModel.metrics) {
                                    // Check if it has classification metrics
                                    if (firstModel.metrics.auc !== undefined || firstModel.metrics.precision !== undefined || firstModel.metrics.recall !== undefined) {
                                      pt = 'classification';
                                    } else if (firstModel.metrics.r2 !== undefined || firstModel.metrics.rmse !== undefined) {
                                      pt = 'regression';
                                    }
                                  }
                                }
                              }
                              
                              // Default to classification if still not determined
                              if (!pt) {
                                pt = 'classification';
                              }
                              
                              // Define column configuration based on problem type
                              const getColumnConfig = (problemType: string) => {
                                if (problemType === 'classification') {
                                  return {
                                    primary: 'auc',
                                    secondary: ['accuracy', 'precision', 'recall', 'f1', 'ks_statistic'],
                                    loss: 'log_loss',
                                    showLogLoss: true
                                  };
                                } else {
                                  return {
                                    primary: 'r2',
                                    secondary: ['rmse', 'mae', 'mse', 'mape'],
                                    loss: null,
                                    showLogLoss: false
                                  };
                                }
                              };
                              
                              const config = getColumnConfig(pt);
                              const allMetrics = [config.primary, ...config.secondary];
                              
                              // Handle segment training vs regular training
                              let iterationData = [];
                              
                              if (results.segment_results) {
                                // Segment training - filter by both algorithm and segment
                                const segmentsToProcess = selectedSegmentForHistory === 'all' 
                                  ? results.segments || []
                                  : [selectedSegmentForHistory];
                                
                                for (const segmentId of segmentsToProcess) {
                                  const segmentKey = `segment_${segmentId}`;
                                  const segmentResult = results.segment_results[segmentKey];
                                  
                                  if (segmentResult && segmentResult.results) {
                                    const algorithmResult = segmentResult.results.find((r: any) => r.algorithm === selectedAlgorithmForHistory);
                                    if (algorithmResult && algorithmResult.iteration_history) {
                                      // Add segment info to each iteration
                                      const segmentIterations = algorithmResult.iteration_history.map((iter: any) => ({
                                        ...iter,
                                        segment_id: segmentId,
                                        model_id: algorithmResult.model_id
                                      }));
                                      iterationData.push(...segmentIterations);
                                    }
                                  }
                                }
                              } else {
                                // Regular training - use existing logic
                              const selectedResult = results.results?.find((r: any) => r.algorithm === selectedAlgorithmForHistory);
                                if (selectedResult && selectedResult.iteration_history) {
                                  iterationData = selectedResult.iteration_history;
                                }
                              }
                              
                              if (iterationData.length === 0) {
                                const totalColumns = 1 + allMetrics.length + (config.showLogLoss ? 1 : 0) + 2; // Iteration + metrics + log_loss + improvement + status
                                return (
                                  <tr>
                                    <td colSpan={totalColumns} className="px-4 py-8 text-center text-gray-500 dark:text-gray-400">
                                      No iteration history available for {selectedAlgorithmForHistory.toUpperCase()}
                                      {results.segment_results && selectedSegmentForHistory !== 'all' && ` in segment ${selectedSegmentForHistory}`}
                                    </td>
                                  </tr>
                                );
                              }

                              const soleBestIdx = getSoleBestIterationIndexForDisplay(iterationData);

                              return iterationData.map((iteration: any, index: number) => {
                                const showAsBest = soleBestIdx !== null && index === soleBestIdx;
                                return (
                                <tr
                                  key={`${iteration.segment_id || 'default'}_${index}`}
                                  className="transition-colors hover:bg-gray-50 dark:hover:bg-slate-700/95"
                                >
                                  <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900 dark:!text-slate-100">
                                    <div className="flex items-center space-x-2">
                                      <span>{iteration.iteration}</span>
                                      {iteration.segment_id && (
                                        <span className="text-xs bg-purple-100 text-purple-800 px-2 py-1 rounded-full">
                                          {iteration.segment_id}
                                        </span>
                                      )}
                                    </div>
                                  </td>
                                  
                                  {/* Dynamic metric columns */}
                                  {allMetrics.map(metric => (
                                      <td key={metric} className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 dark:!text-slate-100">
                                        {iteration.metrics?.[metric]?.toFixed(4) || 'N/A'}
                                      </td>
                                  ))}
                                  
                                  {/* Log Loss column (only for classification) */}
                                  {config.showLogLoss && (
                                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 dark:!text-slate-100">
                                      {iteration.metrics?.log_loss?.toFixed(4) || 'N/A'}
                                  </td>
                                  )}
                                  
                                  {/* Improvement column */}
                                  <td className="px-4 py-3 whitespace-nowrap text-sm">
                                    <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                                      iteration.improvement > 0
                                        ? 'bg-green-100 text-green-800'
                                        : iteration.improvement < 0
                                        ? 'bg-red-100 text-red-800'
                                        : 'bg-gray-100 text-gray-800'
                                    }`}>
                                      {iteration.improvement > 0 ? '+' : ''}{iteration.improvement?.toFixed(4) || '0.0000'}
                                    </span>
                                  </td>
                                  
                                  {/* Status column — only one "Best Score" row (last backend-tagged best); rest Completed */}
                                  <td className="px-4 py-3 whitespace-nowrap">
                                    <span
                                      className={`px-2 py-1 text-xs font-medium rounded-full ${
                                        showAsBest
                                          ? 'bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-200'
                                          : 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200'
                                      }`}
                                    >
                                      {showAsBest ? 'Best Score' : 'Completed'}
                                    </span>
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

                  {/* Interactive Algorithm Comparison (hidden per product request) */}
                  {false && viz && (
                    <div className="mt-8 border rounded-lg p-6">
                      <div className="flex items-center justify-between mb-4">
                        <h4 className="text-xl font-semibold">Interactive Algorithm Comparison</h4>
                        <div className="text-sm text-gray-600">Click on chart elements to select an algorithm for detailed analysis</div>
                      </div>

                      {/* Tabs for Score Comparison and Training History */}
                      <div className="mb-4">
                        <div className="border-b border-gray-200">
                          <nav className="-mb-px flex space-x-8">
                            <button
                              onClick={() => setComparisonTab('score')}
                              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                                comparisonTab === 'score'
                                  ? 'border-blue-500 text-blue-600'
                                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                              }`}
                            >
                              Score Comparison
                            </button>
                            <button
                              onClick={() => setComparisonTab('history')}
                              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                                comparisonTab === 'history'
                                  ? 'border-blue-500 text-blue-600'
                                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                              }`}
                            >
                              Training History
                            </button>
                          </nav>
                        </div>
                      </div>

                      {/* Comparison Filters */}
                      {viz.segment_results && (
                        <div className="mb-6 bg-white border border-blue-200 rounded-lg p-4">
                          <div className="flex items-center space-x-2 mb-3">
                            <Filter className="h-4 w-4 text-blue-600" />
                            <h5 className="font-medium text-gray-900">Filter Comparison Data</h5>
                          </div>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {/* Algorithm Filter */}
                            <div>
                              <label className="text-sm font-medium text-gray-900 flex items-center space-x-2 mb-2">
                                <Settings className="h-4 w-4 text-blue-600" />
                                <span>Filter by Algorithm:</span>
                              </label>
                              <select
                                value={comparisonAlgorithmFilter}
                                onChange={(e) => setComparisonAlgorithmFilter(e.target.value)}
                                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 bg-white"
                              >
                                <option value="all">🔧 All Algorithms</option>
                                {Array.from(new Set(
                                  Object.values(viz.segment_results || {})
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
                                <Filter className="h-4 w-4 text-blue-600" />
                                <span>Filter by Segment:</span>
                              </label>
                              <select
                                value={comparisonSegmentFilter}
                                onChange={(e) => setComparisonSegmentFilter(e.target.value)}
                                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 bg-white"
                              >
                                <option value="all">📊 All Segments</option>
                                {viz.segments?.map((seg: string) => (
                                  <option key={seg} value={seg}>
                                    🎯 Segment: {seg}
                                  </option>
                                ))}
                              </select>
                            </div>
                          </div>
                          
                          <div className="text-xs text-gray-600 mt-3 p-2 bg-gray-50 rounded">
                            {comparisonAlgorithmFilter === 'all' && comparisonSegmentFilter === 'all' 
                              ? 'Showing comparison data for all algorithms across all segments'
                              : `Showing ${comparisonAlgorithmFilter === 'all' ? 'all algorithms' : comparisonAlgorithmFilter.toUpperCase()} 
                                 for ${comparisonSegmentFilter === 'all' ? 'all segments' : `segment ${comparisonSegmentFilter}`}`
                            }
                          </div>
                        </div>
                      )}

                      {comparisonTab === 'score' && (
                        <div className="mb-4">
                          <div className="bg-blue-50 border border-blue-200 dark:bg-slate-900/70 dark:border-slate-700 rounded-lg p-4 mb-4">
                            <div className="flex items-center space-x-2 flex-wrap">
                              {getAvailableMetrics().map((metric, index) => {
                                const colors = ['#3B82F6', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899', '#F97316'];
                                const color = colors[index % colors.length];

                                return (
                                  <React.Fragment key={metric}>
                                    <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }}></div>
                                    <span className="text-sm font-medium" style={{ color }}>
                                      {metric === 'auc' ? 'AUC-ROC' :
                                       metric === 'f1' ? 'F1 Score' :
                                       metric === 'accuracy' ? 'Accuracy' :
                                       metric === 'ks_statistic' ? 'KS Statistic' :
                                       metric === 'r2' ? 'R²' :
                                       metric === 'adjusted_r2' ? 'Adjusted R²' :
                                       metric === 'mae' ? 'MAE' :
                                       metric === 'mse' ? 'MSE' :
                                       metric === 'rmse' ? 'RMSE' :
                                       metric.toUpperCase()}
                                    </span>
                                  </React.Fragment>
                                );
                              })}
                            </div>
                          </div>

                          <div className="h-64 w-full min-h-[256px] min-w-0">
                            {getScoreComparisonData().length > 0 ? (
                              <ResponsiveContainer width="100%" height="100%" minWidth={0} debounce={50}>
                                <BarChart
                                  data={getScoreComparisonData()}
                                  margin={{
                                    top: 35,
                                    right: 140,
                                    left: 20,
                                    bottom: 5,
                                  }}
                                  onClick={(data) => {
                                    if (data && data.activeLabel) {
                                      setSelectedAlgorithmForHistory(data.activeLabel.toLowerCase());
                                    }
                                  }}
                                >
                                  <CartesianGrid strokeDasharray="3 3" />
                                  <XAxis
                                    dataKey="algorithm"
                                    tick={{ fontSize: 12 }}
                                  />
                                  <YAxis
                                    tick={{ fontSize: 12 }}
                                    domain={viz?.problem_type === 'regression' ? ['auto', 'auto'] : [0, 1]}
                                    label={{ value: 'Score', angle: -90, position: 'insideLeft' }}
                                  />
                                  <Tooltip
                                    formatter={(value: number, name: string) => [
                                      value.toFixed(4),
                                      name
                                    ]}
                                    labelFormatter={(label) => `Algorithm: ${label}`}
                                    cursor={isDarkMode ? { fill: 'rgba(15, 23, 42, 0.4)' } : { fill: 'rgba(0, 0, 0, 0.05)' }}
                                    contentStyle={{
                                      backgroundColor: isDarkMode ? 'rgba(15, 23, 42, 0.95)' : 'rgba(255, 255, 255, 0.95)',
                                      border: isDarkMode ? '1px solid #334155' : '1px solid #ccc',
                                      borderRadius: '8px',
                                      color: isDarkMode ? '#e2e8f0' : '#111827'
                                    }}
                                    labelStyle={{ color: isDarkMode ? '#e2e8f0' : '#111827' }}
                                    itemStyle={{ color: isDarkMode ? '#e2e8f0' : '#111827' }}
                                  />
                                  <Legend layout="vertical" align="right" verticalAlign="middle" wrapperStyle={{ right: 6 }} />
                                  {getAvailableMetrics().map((metric, index) => {
                                    const colors = ['#3B82F6', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899', '#F97316'];
                                    const color = colors[index % colors.length];

                                    return (
                                      <Bar
                                        key={metric}
                                        dataKey={metric}
                                        fill={color}
                                        name={
                                          metric === 'auc' ? 'AUC-ROC' :
                                          metric === 'f1' ? 'F1 Score' :
                                          metric === 'accuracy' ? 'Accuracy' :
                                          metric === 'ks_statistic' ? 'KS Statistic' :
                                          metric === 'r2' ? 'R²' :
                                          metric === 'adjusted_r2' ? 'Adjusted R²' :
                                          metric === 'mae' ? 'MAE' :
                                          metric === 'mse' ? 'MSE' :
                                          metric === 'rmse' ? 'RMSE' :
                                          metric.toUpperCase()
                                        }
                                      />
                                    );
                                  })}
                                </BarChart>
                              </ResponsiveContainer>
                            ) : (
                              <div className="h-full flex items-center justify-center text-gray-500">
                                <div className="text-center">
                                  <BarChart3 className="h-8 w-8 mx-auto mb-2 opacity-50" />
                                  <p className="text-sm">No training results available</p>
                                  <p className="text-xs mt-1">
                                    Train models to see {getAvailableMetrics().length > 0 ?
                                      getAvailableMetrics().map(m => m === 'auc' ? 'AUC-ROC' : m === 'f1' ? 'F1' : m === 'accuracy' ? 'Accuracy' : m === 'ks_statistic' ? 'KS Statistic' : m === 'r2' ? 'R²' : m === 'adjusted_r2' ? 'Adjusted R²' : m === 'mae' ? 'MAE' : m === 'mse' ? 'MSE' : m === 'rmse' ? 'RMSE' : m.toUpperCase()).join(', ') :
                                      'metrics'} comparison
                                  </p>
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      )}

                      {comparisonTab === 'history' && (
                        <div className="mb-4">
                          {/* Toggle algorithms section hidden - replaced by filter dropdowns above */}
                          {false && (
                          <div className="mb-4">
                            <label className="block text-sm font-medium text-gray-700 mb-2">Toggle algorithms:</label>
                            <div className="flex flex-wrap gap-2">
                              {(() => {
                                // Determine which results to use (manual or auto training)
                                const results = viz;
                                return results.results?.map((result: any) => (
                                  <label key={result.algorithm} className="inline-flex items-center">
                                    <input
                                      type="checkbox"
                                      checked={selectedAlgorithmsForComparison.includes(result.algorithm)}
                                      onChange={(e) => {
                                        if (e.target.checked) {
                                          setSelectedAlgorithmsForComparison([...selectedAlgorithmsForComparison, result.algorithm]);
                                        } else {
                                          setSelectedAlgorithmsForComparison(selectedAlgorithmsForComparison.filter(a => a !== result.algorithm));
                                        }
                                      }}
                                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                                    />
                                    <span className="ml-2 text-sm text-gray-700">{result.algorithm.toUpperCase()}</span>
                                  </label>
                                ));
                              })()}
                            </div>
                          </div>
                          )}

                          <div className="h-80 w-full min-h-[320px] min-w-0">
                            {getTrainingHistoryData().length > 0 && getSelectedAlgorithms().length > 0 ? (
                              <ResponsiveContainer width="100%" height="100%" minWidth={0} debounce={50}>
                                  <LineChart
                                    data={getTrainingHistoryData()}
                                    margin={{
                                      top: 35,
                                      right: 40,
                                      left: 30,
                                      bottom: 20,
                                    }}
                                  >
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis
                                      dataKey="iteration"
                                      tick={{ fontSize: 12 }}
                                      label={{ value: 'Iteration', position: 'insideBottom', offset: -10 }}
                                    />
                                    <YAxis
                                      tick={{ fontSize: 12 }}
                                      domain={[0, 1]}
                                      label={{
                                        value: (() => {
                                          const pt = viz.problem_type;
                                          const scoreKey = getPrimaryMetricKey(pt, targetMetricManual);
                                          return getMetricDisplayName(scoreKey);
                                        })(),
                                        angle: -90,
                                        position: 'insideLeft'
                                      }}
                                    />
                                    <Tooltip
                                      formatter={(value: number, name: string) => [
                                        value ? value.toFixed(4) : 'N/A',
                                        `${name} Score`
                                      ]}
                                      labelFormatter={(label) => `Iteration: ${label}`}
                                      contentStyle={{
                                        backgroundColor: isDarkMode ? 'rgba(15, 23, 42, 0.95)' : 'rgba(255, 255, 255, 0.95)',
                                        border: isDarkMode ? '1px solid #334155' : '1px solid #ccc',
                                        borderRadius: '8px',
                                        color: isDarkMode ? '#e2e8f0' : '#111827'
                                      }}
                                      labelStyle={{ color: isDarkMode ? '#e2e8f0' : '#111827' }}
                                      itemStyle={{ color: isDarkMode ? '#e2e8f0' : '#111827' }}
                                    />
                                    <Legend verticalAlign="top" align="center" wrapperStyle={{ paddingBottom: 8 }} />
                                    {/* Render lines for selected algorithms only */}
                                    {getSelectedAlgorithms().map((algorithm) => (
                                      <Line
                                        key={algorithm}
                                        type="monotone"
                                        dataKey={algorithm}
                                        stroke={
                                          algorithm === 'XGBOOST' ? '#3B82F6' :
                                          algorithm === 'LOGISTIC' ? '#10B981' :
                                          algorithm === 'RANDOM_FOREST' ? '#F59E0B' :
                                          algorithm === 'GRADIENT_BOOSTING' ? '#8B5CF6' :
                                          algorithm === 'CATBOOST' ? '#EC4899' :
                                          algorithm === 'LIGHTGBM' ? '#F97316' :
                                          '#6B7280'
                                        }
                                        strokeWidth={2}
                                        dot={{ r: 4, strokeWidth: 2 }}
                                        name={algorithm}
                                        connectNulls={false}
                                      />
                                    ))}
                                  </LineChart>
                              </ResponsiveContainer>
                            ) : (
                              <div className="h-full flex items-center justify-center text-gray-500">
                                <div className="text-center">
                                  <TrendingUp className="h-8 w-8 mx-auto mb-2 opacity-50" />
                                  <p className="text-sm">No training history available</p>
                                  <p className="text-xs mt-1">Select algorithms to view training progression</p>
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
    </>
  );
};
