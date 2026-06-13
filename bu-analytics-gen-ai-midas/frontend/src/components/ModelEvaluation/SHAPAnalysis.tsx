/**
 * SHAP Analysis Component
 * Wrapper component combining Beeswarm and Waterfall plots
 * Independent component with its own model selector
 */

import React, { useState, useEffect } from 'react';
import { Loader2 } from 'lucide-react';
import { EvaluationModel, ModelEvaluationData } from '../../types/modelEvaluation';
import SHAPBeeswarmPlotCanvas from './SHAPBeeswarmPlotCanvas';
import SHAPWaterfallPlot from './SHAPWaterfallPlot';

interface SHAPAnalysisProps {
  models: EvaluationModel[];
  evaluationData: Record<string, ModelEvaluationData>;
  selectedModel?: string;
  onModelChange?: (modelId: string) => void;
  selectedSampleIndex?: number | null;
  selectedSampleFeatures?: Record<string, any> | null; // Actual feature values from selected sample
  onOpenRecordBrowser?: (modelId: string) => void;
  loading?: boolean; // Whether explainability data is being loaded/calculated
  recalculating?: boolean; // Whether explainability data is being recalculated
}

const SHAPAnalysis: React.FC<SHAPAnalysisProps> = ({
  models,
  evaluationData,
  selectedModel: propSelectedModel,
  onModelChange: propOnModelChange,
  selectedSampleIndex,
  selectedSampleFeatures,
  onOpenRecordBrowser,
  loading = false,
  recalculating = false,
}) => {
  // Use prop if provided, otherwise use internal state
  const [internalSelectedModel, setInternalSelectedModel] = useState<string>('');
  const selectedModel = propSelectedModel !== undefined ? propSelectedModel : internalSelectedModel;
  const setSelectedModel = propOnModelChange || setInternalSelectedModel;
  
  // State for feature count limit (shared for both beeswarm and waterfall)
  const [featureCount, setFeatureCount] = useState<number | 'all'>(10);

  // Initialize selected model - prefer one with SHAP data
  // Also update if selected model is no longer in the models list (e.g., after refresh)
  useEffect(() => {
    if (models.length > 0) {
      // Check if current selected model is still in the list
      const isSelectedModelValid = selectedModel && models.some(m => m.id === selectedModel);
      
      if (!selectedModel || !isSelectedModelValid) {
        // Find first model with SHAP data
        const modelWithSHAP = models.find(model => {
          const data = evaluationData[model.id];
          return data?.explainability_data?.some(
            d => d.data_type === 'shap_summary' && d.feature_name
          );
        });
        
        // Use model with SHAP data, or fallback to first model
        setSelectedModel(modelWithSHAP?.id || models[0].id);
      }
    }
  }, [models, selectedModel, evaluationData, setSelectedModel]);

  const currentModel = models.find(m => m.id === selectedModel);
  const modelEvalData = evaluationData[selectedModel];

  // Helper function to format model name with segment/global label and ID
  const formatModelName = (model: EvaluationModel | undefined): string => {
    if (!model) return 'Unknown Model';
    const isSegment = (model as any).is_segment_model;
    const segmentId = (model as any).segment_id;
    if (isSegment && segmentId) {
      return `${model.name} [segment = ${segmentId}] (${model.id})`;
    }
    return `${model.name} (Global) (${model.id})`;
  };

  // Extract SHAP data for beeswarm plot
  const getSHAPSummaryData = () => {
    if (!modelEvalData) {
      console.log('SHAPAnalysis: No modelEvalData');
      return [];
    }

    if (!modelEvalData.explainability_data) {
      console.log('SHAPAnalysis: No explainability_data array');
      return [];
    }

    // Debug logging
    console.log('SHAPAnalysis: explainability_data', {
      length: modelEvalData.explainability_data.length,
      dataTypes: modelEvalData.explainability_data.map(d => d.data_type),
      shapEntries: modelEvalData.explainability_data.filter(d => d.data_type === 'shap_summary').length,
      allEntries: modelEvalData.explainability_data.map(d => ({
        data_type: d.data_type,
        feature_name: d.feature_name,
        hasValues: !!d.values,
        valuesType: typeof d.values,
        valuesIsArray: Array.isArray(d.values)
      }))
    });

    // Get all shap_summary entries with feature_name (per-feature data)
    const shapEntries = modelEvalData.explainability_data.filter(
      d => d.data_type === 'shap_summary' && d.feature_name
    );

    console.log('SHAPAnalysis: Found shap_summary entries with feature_name', shapEntries.length);
    return shapEntries;
  };

  // Extract waterfall data
  const getWaterfallData = () => {
    if (!modelEvalData) {
      console.log('SHAPAnalysis: No modelEvalData for waterfall');
      return null;
    }

    if (!modelEvalData.explainability_data) {
      console.log('SHAPAnalysis: No explainability_data for waterfall');
      return null;
    }

    // If a specific sample index is selected, derive waterfall data from per-feature SHAP arrays.
    // Otherwise, fall back to any precomputed shap_waterfall entry.
    if (selectedSampleIndex !== undefined && selectedSampleIndex !== null) {
      const perFeatureEntries = modelEvalData.explainability_data.filter(
        (d) => d.data_type === 'shap_summary' && d.feature_name,
      );

      if (perFeatureEntries.length > 0) {
        const featuresForSample: { feature: string; feature_value: number; shap_value: number }[] = [];

        perFeatureEntries.forEach((entry: any) => {
          const values: number[] = Array.isArray(entry.values) ? entry.values : [];

          if (values.length === 0) {
            return;
          }

          const idx = Math.min(Math.max(selectedSampleIndex, 0), values.length - 1);
          const shapVal = values[idx];

          if (shapVal === undefined || shapVal === null) return;

          // Use actual feature value from selected sample if available, otherwise fall back to metadata
          const featureName = entry.feature_name || 'feature';
          let featVal: any;
          
          if (selectedSampleFeatures && selectedSampleFeatures[featureName] !== undefined) {
            // Use actual raw feature value from the selected sample
            featVal = selectedSampleFeatures[featureName];
          } else {
            // Fallback to feature_values from metadata (for backward compatibility)
            const featureValues: any[] = Array.isArray(entry.metadata?.feature_values)
              ? entry.metadata.feature_values
              : [];
            if (featureValues.length > 0) {
              featVal = featureValues[idx];
            } else {
              return; // Skip if no feature value available
            }
          }

          featuresForSample.push({
            feature: featureName,
            feature_value: featVal,
            shap_value: shapVal,
          });
        });

        // Get base value from the global shap_summary entry if available
        const globalShapEntry = modelEvalData.explainability_data.find(
          (d) => d.data_type === 'shap_summary' && !d.feature_name,
        );
        const baseValue = (globalShapEntry as any)?.values?.base_value ?? 0;

        console.log('SHAPAnalysis: Built waterfall from selectedSampleIndex', {
          selectedSampleIndex,
          featureCount: featuresForSample.length,
          baseValue,
        });

        return {
          values: featuresForSample,
          metadata: {
            base_value: baseValue,
          },
        };
      }
    }

    const waterfallEntry = modelEvalData.explainability_data.find(
      (d) => d.data_type === 'shap_waterfall',
    );

    console.log('SHAPAnalysis: waterfallEntry', waterfallEntry ? 'found' : 'not found');
    return waterfallEntry || null;
  };

  const shapSummaryData = getSHAPSummaryData();
  const waterfallEntry = getWaterfallData();

  // Sort SHAP summary data by mean absolute SHAP value
  const sortedSummaryData = [...shapSummaryData].sort((a: any, b: any) => {
    const meanA = Math.abs(a.metadata?.mean_abs || 0);
    const meanB = Math.abs(b.metadata?.mean_abs || 0);
    return meanB - meanA;
  });
  
  // Filter beeswarm data based on selected feature count
  const filteredBeeswarmData = featureCount === 'all' 
    ? sortedSummaryData 
    : sortedSummaryData.slice(0, featureCount);
  
  // Filter waterfall data based on selected feature count
  const filteredWaterfallData = waterfallEntry?.values 
    ? (featureCount === 'all' 
        ? waterfallEntry.values 
        : waterfallEntry.values.slice(0, featureCount))
    : null;

  if (!currentModel) {
    return (
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800 p-8">
        <div className="text-center text-gray-500 dark:text-white">No model selected</div>
      </div>
    );
  }

  // Check if current model has any SHAP data
  const hasAnySHAPData = sortedSummaryData.length > 0 || waterfallEntry !== null;

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800">
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-800">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">SHAP Model Interpret</h2>
            <p className="text-sm text-gray-600 dark:text-white mt-1">
              Comprehensive SHAP analysis for model interpretability
            </p>
          </div>

          <div className="flex items-center gap-4">
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="text-sm border border-gray-300 dark:border-gray-700 rounded px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
            >
              {models.map(model => {
                const isSegment = (model as any).is_segment_model;
                const segmentId = (model as any).segment_id;
                const label = isSegment && segmentId
                  ? `${model.name} [segment = ${segmentId}] (${model.id})`
                  : `${model.name} (Global) (${model.id})`;
                return (
                  <option key={model.id} value={model.id}>
                    {label}
                  </option>
                );
              })}
            </select>
            
            <div className="flex items-center gap-2">
              <label className="text-sm font-medium text-gray-700 dark:text-white">Features:</label>
              <select
                value={featureCount === 'all' ? 'all' : featureCount}
                onChange={(e) => setFeatureCount(e.target.value === 'all' ? 'all' : Number(e.target.value))}
                className="text-sm border border-gray-300 dark:border-gray-700 rounded px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
              >
                <option value={5}>5</option>
                <option value={10}>10</option>
                <option value={15}>15</option>
                <option value={20}>20</option>
                <option value="all">All</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {!hasAnySHAPData && (
        <div className="p-8">
          {loading || recalculating ? (
            <div className="flex items-center justify-center gap-3">
              <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
              <span className="text-gray-600">
                {recalculating ? 'Calculating SHAP data...' : 'Loading SHAP data...'}
              </span>
            </div>
          ) : (
            <div className="text-center space-y-4">
              <div className="text-gray-500">
                No SHAP data available for {formatModelName(currentModel)}
              </div>
              <div className="text-sm text-gray-400 bg-yellow-50 border border-yellow-200 rounded-lg p-4 max-w-2xl mx-auto">
                <p className="font-semibold text-yellow-800 mb-2">ℹ️ Model Needs Re-evaluation</p>
                <p className="text-yellow-700">
                  This model was evaluated before the enhanced SHAP analysis was added. 
                  Please re-train or re-evaluate the model to generate SHAP data.
                </p>
              </div>
            </div>
          )}
        </div>
      )}

      {hasAnySHAPData && (

      <div className="p-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Beeswarm Plot */}
          <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-6 border border-gray-200 dark:border-gray-700">
            <h3 className="text-base font-semibold text-gray-900 dark:text-white mb-2 text-center">SHAP Beeswarm Plot</h3>
            <p className="text-xs text-gray-600 dark:text-white text-center mb-4">
              Each dot represents a sample. Horizontal position = SHAP value, Color = feature value
            </p>
            {filteredBeeswarmData.length > 0 ? (
              <div className="relative">
                {/* Calculate global SHAP range across all features */}
                {(() => {
                  const allShapValues: number[] = [];
                  filteredBeeswarmData.forEach(item => {
                    if (item.values && Array.isArray(item.values)) {
                      allShapValues.push(...item.values);
                    }
                  });
                  
                  // Use reduce to avoid stack overflow with large arrays
                  const globalMinShap = allShapValues.length > 0 ? allShapValues.reduce((min, val) => Math.min(min, val), allShapValues[0]) : 0;
                  const globalMaxShap = allShapValues.length > 0 ? allShapValues.reduce((max, val) => Math.max(max, val), allShapValues[0]) : 0;
                  const globalMaxAbs = Math.max(Math.abs(globalMinShap), Math.abs(globalMaxShap));
                  const padding = globalMaxAbs * 0.1;
                  const globalPlotMin = -globalMaxAbs - padding;
                  const globalPlotMax = globalMaxAbs + padding;
                  
                  // Calculate the center position of the plot area
                  // Feature name (w-36 = 9rem) + gap (gap-3 = 0.75rem) + 50% of plot area (flex-1)
                  // The plot area is flex-1, so zero is at: feature name + gap + 50% of remaining space
                  // Since we can't easily calculate flex-1 width in CSS, we'll use a simpler approach:
                  // Position zero label at 50% of the entire width, accounting for fixed widths
                  const zeroLinePosition = 'calc(9rem + 0.75rem + ((100% - 9rem - 0.75rem - 7rem - 0.75rem) / 2))';
                  
                  return (
                    <div className="relative w-full">
                      {/* Zero line is now drawn in each canvas component for perfect alignment */}
                      
                      <div className="w-full flex flex-col gap-3 py-2 pb-2">
                        {filteredBeeswarmData.map((item, featureIdx) => (
                            <SHAPBeeswarmPlotCanvas
                              key={featureIdx}
                              shapData={{
                                values: item.values || [],
                                feature_values: item.metadata?.feature_values || [],
                                original_feature_values: item.metadata?.original_feature_values,  // NEW: Original values for display
                                mean_abs: item.metadata?.mean_abs,
                                original_feature_name: item.metadata?.original_feature_name  // NEW: Original feature name
                              }}
                              featureName={item.feature_name || `Feature ${featureIdx}`}
                              height={56}
                              globalPlotMin={globalPlotMin}
                              globalPlotMax={globalPlotMax}
                            />
                        ))}
                      </div>
                      
                      {/* Shared X-axis with zero label */}
                      <div className="mt-4 relative">
                        <div className="pt-2">
                          <div className="relative flex justify-between items-center border-t border-gray-300 dark:border-gray-700 pt-2" style={{ paddingLeft: '9rem', paddingRight: '7rem' }}>
                            <span className="text-xs text-gray-600 dark:text-white">{globalPlotMin.toFixed(3)}</span>
                            {/* Zero label - positioned at center of plot area (matches canvas zero line at 50%) */}
                            <div 
                              className="absolute flex flex-col items-center"
                              style={{
                                left: zeroLinePosition,
                                transform: 'translateX(-50%)',
                                top: '-0.25rem'
                              }}
                            >
                              <span className="text-xs font-semibold text-black dark:text-white">0</span>
                              <span className="text-xs font-medium text-gray-700 dark:text-white mt-1">SHAP value</span>
                            </div>
                            <span className="text-xs text-gray-600 dark:text-white">{globalPlotMax.toFixed(3)}</span>
                          </div>
                          <div className="flex justify-between items-center mt-1" style={{ paddingLeft: '9rem', paddingRight: '6rem' }}>
                            <span className="text-xs text-gray-400 dark:text-white">Negative</span>
                            <span className="text-xs text-gray-400 dark:text-white">Positive</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })()}
              </div>
            ) : (
              <div className="text-center text-gray-500 dark:text-white py-8 space-y-2">
                <div>No SHAP beeswarm data available</div>
                <div className="text-xs text-gray-400 dark:text-white">
                  Model needs re-evaluation to generate SHAP data
                </div>
              </div>
            )}
            <div className="mt-4 pt-3 border-t border-gray-300 dark:border-gray-700">
              <div className="text-sm text-gray-700 dark:text-white font-medium mb-2 text-center">SHAP value (impact on model output)</div>
              <div className="flex flex-col items-center gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-600 dark:text-white">Low</span>
                  <div 
                    className="w-40 h-4 rounded shadow-sm" 
                    style={{ 
                      background: 'linear-gradient(to right, #3b82f6 0%, #ffffff 50%, #ef4444 100%)',
                      border: '1px solid #e5e7eb'
                    }}
                  ></div>
                  <span className="text-xs text-gray-600 dark:text-white">High</span>
                </div>
                <span className="text-xs text-gray-500 dark:text-white">Feature value (hover over dots for details)</span>
              </div>
            </div>
          </div>

          {/* Waterfall Plot */}
          <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-6 border border-gray-200 dark:border-gray-700">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-base font-semibold text-gray-900 dark:text-white">SHAP Waterfall</h3>
              {onOpenRecordBrowser && selectedModel && (
                <button
                  type="button"
                  onClick={() => onOpenRecordBrowser(selectedModel)}
                  className="text-xs px-3 py-1.5 rounded border border-blue-500 text-blue-600 hover:bg-blue-50 dark:text-blue-300 dark:hover:bg-gray-800 flex items-center gap-1"
                >
                  <span>Select Sample</span>
                </button>
              )}
            </div>
            {selectedSampleIndex !== null && selectedSampleIndex !== undefined && (
              <div className="text-xs text-gray-600 dark:text-white mb-2 text-center">
                Showing waterfall for sample index: <span className="font-semibold">{selectedSampleIndex}</span>
              </div>
            )}
            {filteredWaterfallData ? (
              <div className="pb-2">
                <SHAPWaterfallPlot
                  waterfallData={filteredWaterfallData}
                  baseValue={waterfallEntry?.metadata?.base_value || 0.5}
                  modelColor={currentModel.color}
                />
              </div>
            ) : (
              <div className="text-center text-gray-500 dark:text-white py-8 space-y-2">
                <div>No waterfall data available</div>
                <div className="text-xs text-gray-400 dark:text-white">
                  Model needs re-evaluation to generate waterfall data
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
      )}

      {hasAnySHAPData && (
        <div className="px-6 py-4 bg-gray-50 dark:bg-gray-800 border-t border-gray-200 dark:border-gray-800">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs text-gray-600 dark:text-white">
            <div>
              <span className="font-semibold">Beeswarm Plot:</span> Displays SHAP value distributions across all samples for each feature. Each dot represents a single prediction. Features on Y-axis ranked by importance. Blue dots = low feature value, Red dots = high feature value. Horizontal spread shows impact on model output.
            </div>
            <div>
              <span className="font-semibold">Waterfall:</span> Explains a single prediction by showing how each feature value pushes the prediction from the base value (average model output) to the final prediction. Cyan = positive contribution, Rose = negative contribution.
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SHAPAnalysis;


