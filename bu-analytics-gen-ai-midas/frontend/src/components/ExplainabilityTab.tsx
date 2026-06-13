import React, { useState, useEffect } from 'react';
import { AlertTriangle, Loader2, X } from 'lucide-react';

import { ModelEvaluationData, EvaluationModel } from '../types/modelEvaluation';
import SHAPFeatureImportanceChart from './ModelEvaluation/SHAPFeatureImportanceChart';
import SHAPAnalysis from './ModelEvaluation/SHAPAnalysis';
import PDPICEPlot from './ModelEvaluation/PDPICEPlot';

interface ExplainabilityTabProps {
  availableModels: EvaluationModel[];
  selectedModelIds: string[];
  evaluationData: Record<string, ModelEvaluationData>;
  explainabilityDataSource: 'train' | 'test';
  recalculatingExplainability: Record<string, 'train' | 'test'>;
  loadingExplainability: boolean;
  initialLoading?: boolean; // Loading state from parent (initial fetch)
  samples: Array<{
    sample_index: number;
    row_index: number | string;
    id_value?: string | number | null;
    target?: string | number | null;
    features: Record<string, any>;
  }>;
  samplesTotal: number;
  samplesLoading: boolean;
  selectedSampleIndex: number | null;
  onSelectSample: (sampleIndex: number) => void;
  samplesPage: number;
  samplesPageSize: number;
  onChangeSamplesPage: (page: number) => void;
  initialSearchQuery: string;
  onApplySearch: (query: string) => void;
  samplesError?: string | null;
  onModelSelectedForSamples?: (modelId: string) => void;
  selectedWaterfallModel?: string; // Currently selected model in waterfall (for initial samples fetch)
  onWaterfallModelChange?: (modelId: string | null) => void; // Callback when waterfall model changes
  samplesModelId?: string | null; // The model ID that the current samples belong to
  samplesTargetColumn?: string | null; // The target column name for the samples
  viewMode?: 'shap' | 'pdp'; // Which explainability view to show (Shap or PDP/ICE)
}

const ExplainabilityTab: React.FC<ExplainabilityTabProps> = ({
  availableModels,
  selectedModelIds,
  evaluationData,
  explainabilityDataSource,
  recalculatingExplainability,
  loadingExplainability,
  initialLoading = false,
  samples,
  samplesTotal,
  samplesLoading,
  selectedSampleIndex,
  onSelectSample,
  samplesPage,
  samplesPageSize,
  onChangeSamplesPage,
  initialSearchQuery,
  onApplySearch,
  samplesError,
  onModelSelectedForSamples,
  selectedWaterfallModel,
  onWaterfallModelChange,
  samplesModelId,
  samplesTargetColumn,
  viewMode = 'shap',
}) => {
  // Local selection state for SHAP / PDP models (per data source)
  const [selectedSHAPFeatureModel, setSelectedSHAPFeatureModel] = useState<Record<'test' | 'train', string>>({
    test: '',
    train: '',
  });
  const [selectedSHAPAnalysisModel, setSelectedSHAPAnalysisModel] = useState<Record<'test' | 'train', string>>({
    test: '',
    train: '',
  });
  const [selectedPDPModel, setSelectedPDPModel] = useState<Record<'test' | 'train', string>>({
    test: '',
    train: '',
  });
  // Local search input (applied to backend only when user clicks Search)
  const [searchInput, setSearchInput] = useState<string>(initialSearchQuery || '');
  // Modal state for record browser
  const [isRecordBrowserOpen, setIsRecordBrowserOpen] = useState<boolean>(false);
  // Selected model ID for filtering columns
  const [selectedModelForBrowser, setSelectedModelForBrowser] = useState<string | null>(null);
  // Loading state for each analysis component
  const [loadingAnalyses, setLoadingAnalyses] = useState<Set<'shap_importance' | 'shap_analysis' | 'pdp'>>(new Set());

  // Calculate derived values before early returns (needed for useEffect dependencies)
  const selectedModels = availableModels.filter((m) => selectedModelIds.includes(m.id));
  const baseModels = selectedModels.length > 0 ? selectedModels : availableModels;
  // Include all selected models, even if evaluationData doesn't exist yet (for newly trained models)
  // This ensures new models appear in dropdowns while data is loading
  const modelsWithData = baseModels.filter((m) => {
    // Include model if it has evaluationData OR if it's in selectedModelIds (might be loading)
    return evaluationData[m.id] || selectedModelIds.includes(m.id);
  });

  const filterExplainabilityData = (data: ModelEvaluationData) => {
    if (!data?.explainability_data) return data;
    const filtered = data.explainability_data.filter((d: any) => {
      let dataSource = d.data_source;
      if (dataSource === null || dataSource === undefined || dataSource === 'null' || dataSource === '') {
        dataSource = 'test';
      }
      dataSource = String(dataSource).trim().toLowerCase();
      const targetSource = String(explainabilityDataSource).trim().toLowerCase();
      return dataSource === targetSource;
    });
    return {
      ...data,
      explainability_data: filtered,
    };
  };

  const filteredEvaluationData: Record<string, ModelEvaluationData> = {};
  modelsWithData.forEach((m) => {
    // Only filter if evaluationData exists (new models might not have it yet)
    if (evaluationData[m.id]) {
      filteredEvaluationData[m.id] = filterExplainabilityData(evaluationData[m.id]);
    }
  });

  const isRecalculatingCurrentSource = Object.values(recalculatingExplainability).some(
    (v) => v === explainabilityDataSource,
  );

  const hasFilteredData = Object.values(filteredEvaluationData).some(
    (data) => data?.explainability_data && data.explainability_data.length > 0,
  );

  // Update selected models when new models are added (e.g., after retraining)
  // This ensures new models appear in dropdowns and are selected if they have data
  useEffect(() => {
    if (modelsWithData.length === 0) return;

    // Update SHAP Feature Importance model selection
    const currentSHAPFeatureModel = selectedSHAPFeatureModel[explainabilityDataSource];
    const isCurrentSHAPValid = currentSHAPFeatureModel && modelsWithData.some(m => m.id === currentSHAPFeatureModel);
    
    if (!isCurrentSHAPValid) {
      // Find first model with SHAP data, or fallback to first available model
      const modelWithSHAP = modelsWithData.find(m => {
        const data = filteredEvaluationData[m.id];
        return data?.explainability_data?.some((d: any) => d.data_type === 'shap_summary');
      });
      const modelToSelect = modelWithSHAP || modelsWithData[0];
      if (modelToSelect) {
        setSelectedSHAPFeatureModel((prev) => ({
          ...prev,
          [explainabilityDataSource]: modelToSelect.id,
        }));
      }
    }

    // Update SHAP Analysis model selection
    const currentSHAPAnalysisModel = selectedSHAPAnalysisModel[explainabilityDataSource];
    const isCurrentSHAPAnalysisValid = currentSHAPAnalysisModel && modelsWithData.some(m => m.id === currentSHAPAnalysisModel);
    
    if (!isCurrentSHAPAnalysisValid) {
      const modelWithSHAP = modelsWithData.find(m => {
        const data = filteredEvaluationData[m.id];
        return data?.explainability_data?.some((d: any) => d.data_type === 'shap_summary' && d.feature_name);
      });
      const modelToSelect = modelWithSHAP || modelsWithData[0];
      if (modelToSelect) {
        setSelectedSHAPAnalysisModel((prev) => ({
          ...prev,
          [explainabilityDataSource]: modelToSelect.id,
        }));
      }
    }

    // Update PDP model selection
    const currentPDPModel = selectedPDPModel[explainabilityDataSource];
    const isCurrentPDPValid = currentPDPModel && modelsWithData.some(m => m.id === currentPDPModel);
    
    if (!isCurrentPDPValid) {
      const modelWithPDP = modelsWithData.find(m => {
        const data = filteredEvaluationData[m.id];
        return data?.explainability_data?.some((d: any) => d.data_type === 'pdp');
      });
      const modelToSelect = modelWithPDP || modelsWithData[0];
      if (modelToSelect) {
        setSelectedPDPModel((prev) => ({
          ...prev,
          [explainabilityDataSource]: modelToSelect.id,
        }));
      }
    }
  }, [availableModels, selectedModelIds, modelsWithData, explainabilityDataSource, filteredEvaluationData, selectedSHAPFeatureModel, selectedSHAPAnalysisModel, selectedPDPModel]);

  // Clear loading states when explainability recalculation completes
  // IMPORTANT: This hook must be called before any early returns to maintain hook order
  useEffect(() => {
    // Only clear loading states if:
    // 1. No models are currently being recalculated for the current data source
    // 2. We're not in the initial loading state
    // 3. Loading states are actually set
    if (!isRecalculatingCurrentSource && !loadingExplainability && loadingAnalyses.size > 0) {
      // Small delay to ensure data has been updated
      const timer = setTimeout(() => {
        setLoadingAnalyses(new Set());
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [isRecalculatingCurrentSource, loadingExplainability, loadingAnalyses.size]);

  // Check if we're waiting for evaluation data (have models but no evaluation data yet)
  const waitingForEvaluationData = modelsWithData.length > 0 && 
    selectedModelIds.length > 0 && 
    selectedModelIds.some(id => !evaluationData[id]);

  // Show loading screen on initial load when explainability data is being fetched
  // Don't hide content if we're just refreshing (loadingAnalyses is set)
  if ((initialLoading || loadingExplainability || waitingForEvaluationData) && loadingAnalyses.size === 0 && !hasFilteredData) {
    return (
      <div className="flex items-center justify-center py-6">
        <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
        <span className="ml-2 text-sm text-gray-600 dark:text-white">
          {waitingForEvaluationData ? 'Loading evaluation data...' : 
           initialLoading ? 'Loading models and evaluation data...' : 
           'Loading explainability data...'}
        </span>
      </div>
    );
  }

  // If we have no data yet but calculations are running in the background for this source,
  // show only a spinner/info message (no "no data" warning yet).
  if (!hasFilteredData && modelsWithData.length > 0 && isRecalculatingCurrentSource) {
    return (
      <div className="flex items-center justify-center py-6">
        <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
        <span className="ml-2 text-sm text-gray-600 dark:text-white">
          Calculating {explainabilityDataSource} explainability data for selected models...
        </span>
      </div>
    );
  }

  // Only show a "no data" warning when there is truly no data and nothing is currently
  // being calculated for this source.
  if (!hasFilteredData && modelsWithData.length > 0 && !isRecalculatingCurrentSource) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 dark:bg-yellow-900/20 dark:border-yellow-800 rounded-lg p-4 text-center">
        <AlertTriangle className="w-5 h-5 text-yellow-600 mx-auto mb-2" />
        <p className="text-sm text-yellow-800 dark:text-yellow-200">
          No explainability data found for <strong>{explainabilityDataSource}</strong> data. The analysis may still be
          calculating or has not been generated yet.
        </p>
      </div>
    );
  }

  const modelsWithSHAPData = modelsWithData.filter((m) => {
    const data = filteredEvaluationData[m.id];
    return data?.explainability_data?.some((d: any) => d.data_type === 'shap_summary') ?? false;
  });

  const modelsWithPDPData = modelsWithData.filter((m) => {
    const data = filteredEvaluationData[m.id];
    return data?.explainability_data?.some((d: any) => d.data_type === 'pdp') ?? false;
  });

  // Derive feature columns to show based on selected model's used_features
  // Ordered to match the waterfall plot (sorted by absolute SHAP value, descending)
  const featureColumns: string[] = (() => {
    if (!samples || samples.length === 0) return [];
    const first = samples[0];
    if (!first || !first.features) return [];
    
    // Get all available features from the samples (API returns all features used in training)
    const allAvailableFeatures = Object.keys(first.features);
    
    // Only use selectedModelForBrowser if samples match that model
    // This prevents showing wrong columns when samples are still loading for a different model
    const modelToUse = selectedModelForBrowser && samplesModelId === selectedModelForBrowser 
      ? selectedModelForBrowser 
      : samplesModelId || selectedModelForBrowser;
    
    // If a model is selected, try to filter/sort based on used_features and SHAP data
    if (modelToUse) {
      // Use filteredEvaluationData to ensure we only get SHAP entries for current data source (test/train)
      const modelData = filteredEvaluationData[modelToUse] || evaluationData[modelToUse];
      
      // If used_features exists and has items, use it to filter and order
      if (modelData?.used_features && Array.isArray(modelData.used_features) && modelData.used_features.length > 0) {
        const usedFeatureSet = new Set(modelData.used_features);
        
        // Filter to only features that exist in samples and are in used_features
        const filteredFeatures = allAvailableFeatures.filter((col) => usedFeatureSet.has(col));
        
        // If filtering resulted in features, use them; otherwise use all available
        const featuresToShow = filteredFeatures.length > 0 ? filteredFeatures : allAvailableFeatures;
        
        // Get SHAP summary data to sort by importance (matching waterfall order)
        // Use filteredEvaluationData to avoid duplicates from both test and train
        const filteredModelData = filteredEvaluationData[modelToUse];
        if (filteredModelData?.explainability_data) {
          const shapEntries = filteredModelData.explainability_data.filter(
            (d: any) => d.data_type === 'shap_summary' && d.feature_name,
          );
          
          if (shapEntries.length > 0) {
            // Sort by mean absolute SHAP value (descending) - same as waterfall
            const sortedShapEntries = [...shapEntries].sort((a: any, b: any) => {
              const meanA = Math.abs(a.metadata?.mean_abs || 0);
              const meanB = Math.abs(b.metadata?.mean_abs || 0);
              return meanB - meanA;
            });
            
            // Extract feature names in waterfall order (deduplicate to prevent duplicates)
            const waterfallOrder = Array.from(
              new Set(
                sortedShapEntries
                  .map((entry: any) => entry.feature_name)
                  .filter((name: string) => name && featuresToShow.includes(name))
              )
            );
            
            // Combine: waterfall-ordered features first, then any remaining features
            // Use Set to ensure no duplicates
            const orderedFeaturesSet = new Set(waterfallOrder);
            const remainingFeatures = featuresToShow.filter((f) => !orderedFeaturesSet.has(f));
            const orderedFeatures = [...waterfallOrder, ...remainingFeatures];
            
            return orderedFeatures;
          }
        }
        
        return featuresToShow;
      }
    }
    
    // Fallback: show all available features from samples (API returns correct features)
    return allAvailableFeatures;
  })();

  return (
    <>
      {/* SHAP content (Feature Importance + Analysis + Record Browser) */}
      {viewMode === 'shap' && (
        <>
          {/* SHAP Feature Importance Chart with loading overlay */}
          <div className="relative min-h-[200px]">
            {loadingAnalyses.has('shap_importance') && (
              <div className="absolute inset-0 bg-white dark:bg-gray-900 bg-opacity-90 dark:bg-opacity-95 flex items-center justify-center z-50 rounded-lg border border-gray-200 dark:border-gray-800">
                <div className="flex flex-col items-center gap-2">
                  <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
                  <span className="text-sm font-medium text-gray-700 dark:text-white">Refreshing SHAP Feature Importance...</span>
                </div>
              </div>
            )}
            <SHAPFeatureImportanceChart
              models={modelsWithData}
              evaluationData={filteredEvaluationData}
              selectedModel={selectedSHAPFeatureModel[explainabilityDataSource]}
              onModelChange={(modelId) => {
                setSelectedSHAPFeatureModel((prev) => ({
                  ...prev,
                  [explainabilityDataSource]: modelId,
                }));
              }}
              loading={loadingExplainability}
              recalculating={
                selectedSHAPFeatureModel[explainabilityDataSource]
                  ? recalculatingExplainability[selectedSHAPFeatureModel[explainabilityDataSource]] ===
                    explainabilityDataSource
                  : false
              }
            />
          </div>

          {/* SHAP Analysis (Beeswarm + Waterfall) with loading overlay */}
          <div className="relative min-h-[400px]">
            {loadingAnalyses.has('shap_analysis') && (
              <div className="absolute inset-0 bg-white dark:bg-gray-900 bg-opacity-90 dark:bg-opacity-95 flex items-center justify-center z-50 rounded-lg border border-gray-200 dark:border-gray-800">
                <div className="flex flex-col items-center gap-2">
                  <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
                  <span className="text-sm font-medium text-gray-700 dark:text-white">Refreshing SHAP Analysis...</span>
                </div>
              </div>
            )}
            <SHAPAnalysis
              models={modelsWithData}
              evaluationData={filteredEvaluationData}
              selectedModel={selectedSHAPAnalysisModel[explainabilityDataSource]}
              selectedSampleIndex={selectedSampleIndex}
              selectedSampleFeatures={
                selectedSampleIndex !== null && samples.length > 0
                  ? samples.find((s) => s.sample_index === selectedSampleIndex)?.features || null
                  : null
              }
              onModelChange={(modelId) => {
                setSelectedSHAPAnalysisModel((prev) => ({
                  ...prev,
                  [explainabilityDataSource]: modelId,
                }));
                // Notify parent of waterfall model change so samples can be fetched for correct model
                if (onWaterfallModelChange) {
                  onWaterfallModelChange(modelId);
                }
              }}
              onOpenRecordBrowser={(modelId) => {
                setSelectedModelForBrowser(modelId);
                setIsRecordBrowserOpen(true);
                // Notify parent to fetch samples for this specific model
                // This ensures samples are fetched for the correct model when opening record browser
                if (onModelSelectedForSamples) {
                  onModelSelectedForSamples(modelId);
                }
              }}
              loading={loadingExplainability}
              recalculating={
                selectedSHAPAnalysisModel[explainabilityDataSource]
                  ? recalculatingExplainability[selectedSHAPAnalysisModel[explainabilityDataSource]] ===
                    explainabilityDataSource
                  : false
              }
            />
          </div>

          {/* Record Browser Modal */}
          {isRecordBrowserOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="bg-white dark:bg-gray-900 rounded-lg shadow-xl w-[90vw] max-w-6xl max-h-[90vh] flex flex-col">
            {/* Show loading indicator if samples are loading or don't match selected model */}
            {samplesLoading || (selectedModelForBrowser && samplesModelId !== selectedModelForBrowser) ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
                <span className="ml-2 text-sm text-gray-600 dark:text-white">Loading samples...</span>
              </div>
            ) : null}
            {/* Modal Header */}
            <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-800">
              <div className="flex flex-col">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Select Sample for Waterfall</h2>
                <div className="text-xs text-gray-500 dark:text-white mt-1">
                  {samplesLoading
                    ? 'Loading records…'
                    : samplesError
                    ? samplesError
                    : samples.length > 0
                    ? `Showing ${samples.length} of ${samplesTotal} records (${explainabilityDataSource} data)`
                    : 'No records available for this split'}
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsRecordBrowserOpen(false)}
                className="text-gray-400 hover:text-gray-600 dark:text-white dark:hover:text-gray-200"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body - Record Browser */}
            <div className="flex-1 overflow-hidden flex flex-col p-4">
              {/* Search Controls */}
              <div className="flex items-center gap-2 mb-4">
                <input
                  type="text"
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      onApplySearch(searchInput);
                    }
                  }}
                  placeholder="Search target or features…"
                  className="flex-1 text-sm border border-gray-300 dark:border-gray-700 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                />
                <button
                  type="button"
                  onClick={() => onApplySearch(searchInput)}
                  className="text-sm px-4 py-2 rounded border border-blue-500 text-blue-600 hover:bg-blue-50 dark:text-blue-300 dark:hover:bg-gray-800"
                >
                  Search
                </button>
                {initialSearchQuery && (
                  <button
                    type="button"
                    onClick={() => {
                      setSearchInput('');
                      onApplySearch('');
                    }}
                    className="text-sm px-4 py-2 rounded border border-gray-300 dark:border-gray-700 text-gray-600 dark:text-white hover:bg-gray-50 dark:hover:bg-gray-800"
                  >
                    Clear
                  </button>
                )}
              </div>

              {/* Error Message */}
              {samplesError && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 dark:bg-red-900/30 dark:border-red-800 rounded-md">
                  <div className="flex items-start">
                    <AlertTriangle className="w-5 h-5 text-red-600 mt-0.5 mr-2 flex-shrink-0" />
                    <div className="flex-1">
                      <p className="text-sm font-medium text-red-800 dark:text-red-200">Error loading samples</p>
                      <p className="text-xs text-red-600 dark:text-red-300 mt-1">{samplesError}</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Table - Only show if samples match selected model or no model is selected */}
              {samples.length > 0 && (!selectedModelForBrowser || samplesModelId === selectedModelForBrowser) && (
                <div className="flex-1 overflow-auto border border-gray-200 dark:border-gray-800 rounded-md">
                  <table className="min-w-full text-sm border-collapse">
                    <thead className="bg-gray-50 dark:bg-gray-800 sticky top-0">
                      <tr>
                        <th className="px-3 py-2 text-left font-semibold text-gray-700 dark:text-white">#</th>
                        {featureColumns.map((col) => (
                          <th key={col} className="px-3 py-2 text-left font-semibold text-gray-700 dark:text-white">
                            {col}
                          </th>
                        ))}
                        <th className="px-3 py-2 text-left font-semibold text-gray-700 dark:text-white">
                          {samplesTargetColumn ? `${samplesTargetColumn} (Target)` : 'Target'}
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {samples.map((sample) => {
                        const isSelected = selectedSampleIndex === sample.sample_index;
                        return (
                          <tr
                            key={sample.sample_index}
                            className={`cursor-pointer border-b border-gray-100 hover:bg-blue-50 ${
                              isSelected ? 'bg-blue-100' : ''
                            }`}
                            onClick={() => {
                              onSelectSample(sample.sample_index);
                              setIsRecordBrowserOpen(false);
                            }}
                          >
                            <td className="px-3 py-2 text-gray-500">{sample.sample_index}</td>
                            {featureColumns.map((col) => (
                              <td key={col} className="px-3 py-2 text-gray-700">
                                {sample.features[col] !== undefined && sample.features[col] !== null
                                  ? String(sample.features[col])
                                  : '-'}
                              </td>
                            ))}
                            <td className="px-3 py-2 text-gray-800">
                              {sample.target !== undefined && sample.target !== null ? String(sample.target) : '-'}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Pagination */}
              <div className="mt-4 flex items-center justify-between text-sm text-gray-600 pt-4 border-t border-gray-200">
                <div>
                  Page <span className="font-semibold">{samplesPage + 1}</span>{' '}
                  {samplesTotal > 0 && (
                    <span>
                      of <span className="font-semibold">{Math.ceil(samplesTotal / samplesPageSize)}</span>
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    disabled={samplesPage === 0 || samplesLoading}
                    onClick={() => onChangeSamplesPage(Math.max(0, samplesPage - 1))}
                    className={`px-3 py-1.5 rounded border text-sm ${
                      samplesPage === 0 || samplesLoading
                        ? 'border-gray-200 text-gray-300 cursor-not-allowed'
                        : 'border-gray-300 text-gray-700 hover:bg-gray-50'
                    }`}
                  >
                    Prev
                  </button>
                  <button
                    type="button"
                    disabled={(samplesPage + 1) * samplesPageSize >= samplesTotal || samplesLoading}
                    onClick={() =>
                      onChangeSamplesPage(
                        (samplesPage + 1) * samplesPageSize >= samplesTotal ? samplesPage : samplesPage + 1,
                      )
                    }
                    className={`px-3 py-1.5 rounded border text-sm ${
                      (samplesPage + 1) * samplesPageSize >= samplesTotal || samplesLoading
                        ? 'border-gray-200 text-gray-300 cursor-not-allowed'
                        : 'border-gray-300 text-gray-700 hover:bg-gray-50'
                    }`}
                  >
                    Next
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
          )}
        </>
      )}

      {/* PDP/ICE Plot with loading overlay */}
      {viewMode === 'pdp' && (
        <div className="relative min-h-[400px]">
          {loadingAnalyses.has('pdp') && (
            <div className="absolute inset-0 bg-white dark:bg-gray-900 bg-opacity-90 dark:bg-opacity-95 flex items-center justify-center z-50 rounded-lg border border-gray-200 dark:border-gray-800">
              <div className="flex flex-col items-center gap-2">
                <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
                <span className="text-sm font-medium text-gray-700 dark:text-white">Refreshing PDP/ICE Plots...</span>
              </div>
            </div>
          )}
          <PDPICEPlot
            models={modelsWithData}
            evaluationData={filteredEvaluationData}
            explainabilityDataSource={explainabilityDataSource}
            selectedModel={selectedPDPModel[explainabilityDataSource]}
            onModelChange={(modelId) => {
              setSelectedPDPModel((prev) => ({
                ...prev,
                [explainabilityDataSource]: modelId,
              }));
            }}
            loading={loadingExplainability}
            recalculating={
              selectedPDPModel[explainabilityDataSource]
                ? recalculatingExplainability[selectedPDPModel[explainabilityDataSource]] ===
                  explainabilityDataSource
                : false
            }
          />
        </div>
      )}
    </>
  );
};

export default ExplainabilityTab;



