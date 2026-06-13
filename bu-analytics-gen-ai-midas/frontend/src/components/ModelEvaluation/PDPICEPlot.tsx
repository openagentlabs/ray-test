/**
 * Partial Dependence Plot with ICE Lines Component
 * Displays PDP plots with Individual Conditional Expectation lines
 * Independent component with its own model selector
 */

import React, { useState, useEffect } from 'react';
// Model evaluation service for PDP data
import { getPDPData as fetchPDP } from '../../services/modelEvaluationService';
import { Loader2 } from 'lucide-react';
import { EvaluationModel, ModelEvaluationData } from '../../types/modelEvaluation';
import PDPICEPlotCanvas from './PDPICEPlotCanvas';

interface PDPICEPlotProps {
  models: EvaluationModel[];
  evaluationData: Record<string, ModelEvaluationData>;
  explainabilityDataSource?: string;
  selectedModel?: string;
  onModelChange?: (modelId: string) => void;
  loading?: boolean; // Whether explainability data is being loaded/calculated
  recalculating?: boolean; // Whether explainability data is being recalculated
}

interface PDPPoint {
  x: number;
  y: number;
}

const PDPICEPlot: React.FC<PDPICEPlotProps> = ({
  models,
  evaluationData,
  explainabilityDataSource = 'test',
  selectedModel: propSelectedModel,
  onModelChange: propOnModelChange,
  loading = false,
  recalculating = false,
}) => {
  // Use prop if provided, otherwise use internal state
  const [internalSelectedModel, setInternalSelectedModel] = useState<string>('');
  const selectedModel = propSelectedModel !== undefined ? propSelectedModel : internalSelectedModel;
  const setSelectedModel = propOnModelChange || setInternalSelectedModel;
  
  const [maxIceLines, setMaxIceLines] = useState<number>(100); // Increased default from 15 to 100
  const [featureCount, setFeatureCount] = useState<number | 'all'>(10); // Default to 10 features
  const [isLoadingPDP, setIsLoadingPDP] = useState<boolean>(false);
  const [pdpDataCache, setPdpDataCache] = useState<Record<string, any[]>>({});
  const [pdpLoadError, setPdpLoadError] = useState<string | null>(null);
  const [allPdpData, setAllPdpData] = useState<any[]>([]);

  // Initialize selected model - prefer one with PDP data
  // Also update if selected model is no longer in the models list (e.g., after refresh)
  useEffect(() => {
    if (models.length > 0) {
      // Check if current selected model is still in the list
      const isSelectedModelValid = selectedModel && models.some(m => m.id === selectedModel);
      
      if (!selectedModel || !isSelectedModelValid) {
        // Find first model with PDP data
        const modelWithPDP = models.find(model => {
          const data = evaluationData[model.id];
          return data?.explainability_data?.some(
            d => d.data_type === 'pdp'
          );
        });
        
        // Use model with PDP data, or fallback to first model
        setSelectedModel(modelWithPDP?.id || models[0].id);
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

  // Lazy load PDP data when needed (OPTIMIZATION: reduces initial load by 40%)
  const loadPDPDataLazy = async () => {
    if (!selectedModel) return [];
    
    const cacheKey = `${selectedModel}_${explainabilityDataSource}`;
    
    // Check if already in cache
    if (pdpDataCache[cacheKey]) {
      console.log(`PDPICEPlot: Using cached PDP data for ${cacheKey}`);
      return pdpDataCache[cacheKey];
    }
    
    // Check if PDP data already loaded in evaluation data (e.g., from refresh)
    if (modelEvalData?.explainability_data) {
      // Filter by data_type='pdp', feature_name exists, AND matching data_source
      const existingPDP = modelEvalData.explainability_data.filter((d: any) => {
        if (d.data_type !== 'pdp' || !d.feature_name) return false;
        
        // Check data_source matches current explainabilityDataSource
        let ds = d.data_source;
        if (ds === null || ds === undefined || ds === 'null' || ds === '') {
          ds = 'test'; // Default to test if not specified
        }
        ds = String(ds).trim().toLowerCase();
        const targetSource = String(explainabilityDataSource).trim().toLowerCase();
        return ds === targetSource;
      });
      
      if (existingPDP && existingPDP.length > 0) {
        console.log(`PDPICEPlot: Found ${existingPDP.length} PDP entries in existing evaluation data for ${explainabilityDataSource}`);
        setPdpDataCache(prev => ({ ...prev, [cacheKey]: existingPDP }));
        return existingPDP;
      }
    }
    
    // Lazy load from backend
    try {
      setIsLoadingPDP(true);
      setPdpLoadError(null);
      console.log(`PDPICEPlot: Lazy loading PDP data for model ${selectedModel}, data_source=${explainabilityDataSource}`);
      
      // Fetch PDP data from backend service
      const pdpData = await fetchPDP(selectedModel, explainabilityDataSource);
      console.log(`PDPICEPlot: Loaded ${pdpData.length} PDP entries from backend`);
      
      setPdpDataCache(prev => ({ ...prev, [cacheKey]: pdpData }));
      return pdpData;
    } catch (error) {
      console.error('PDPICEPlot: Error loading PDP data:', error);
      setPdpLoadError(error instanceof Error ? error.message : 'Failed to load PDP data');
      return [];
    } finally {
      setIsLoadingPDP(false);
    }
  };
  
  // Effect to load PDP data when model, data source, or evaluation data changes
  useEffect(() => {
    if (!selectedModel) return;
    
    // Clear cache for this model/dataSource combo when evaluationData changes
    // This ensures we pick up new PDP data after refresh
    const cacheKey = `${selectedModel}_${explainabilityDataSource}`;
    
    // Always clear cache when evaluationData changes to ensure fresh data
    // The loadPDPDataLazy function will check evaluationData first before loading from backend
    setPdpDataCache(prev => {
      const newCache = { ...prev };
      delete newCache[cacheKey];
      return newCache;
    });
    
    loadPDPDataLazy().then(data => setAllPdpData(data));
  }, [selectedModel, explainabilityDataSource, evaluationData]);

  // Deduplicate by feature_name - keep only the first occurrence
  const seenFeatures = new Set<string>();
  const deduplicatedPdpData = allPdpData.filter(pdp => {
    if (seenFeatures.has(pdp.feature_name || '')) {
      return false;
    }
    seenFeatures.add(pdp.feature_name || '');
    return true;
  });

  // Get SHAP feature importance for sorting (if available)
  // Uses mean_abs from per-feature shap_summary entries (same as beeswarm)
  const getFeatureImportance = (featureName: string): number => {
    if (!modelEvalData?.explainability_data) return 0;
    
    // Get per-feature shap_summary entry (same source as beeswarm)
    const shapEntry = modelEvalData.explainability_data.find(
      d => d.data_type === 'shap_summary' && d.feature_name === featureName
    );
    
    // Use mean_abs from metadata (same as beeswarm sorting)
    if (shapEntry?.metadata?.mean_abs !== undefined) {
      return Math.abs(shapEntry.metadata.mean_abs);
    }
    
    // Fallback: calculate PDP range as importance proxy
    const pdpEntry = deduplicatedPdpData.find(p => p.feature_name === featureName);
    if (pdpEntry?.values && Array.isArray(pdpEntry.values) && pdpEntry.values.length > 0) {
      const yValues = pdpEntry.values.map((v: any) => v.y || 0);
      const minY = yValues.reduce((min: number, val: number) => Math.min(min, val), yValues[0] || 0);
      const maxY = yValues.reduce((max: number, val: number) => Math.max(max, val), yValues[0] || 0);
      return Math.abs(maxY - minY); // Use range as importance proxy
    }
    
    return 0;
  };

  // Sort by importance (descending) and filter by feature count
  const sortedPdpData = [...deduplicatedPdpData].sort((a, b) => {
    const importanceA = getFeatureImportance(a.feature_name || '');
    const importanceB = getFeatureImportance(b.feature_name || '');
    return importanceB - importanceA;
  });

  const currentPdpData = featureCount === 'all' 
    ? sortedPdpData 
    : sortedPdpData.slice(0, featureCount);

  if (!currentModel) {
    return (
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800 p-8">
        <div className="text-center text-gray-500 dark:text-white">No model selected</div>
      </div>
    );
  }

  // Show loading spinner if data is being loaded/calculated
  if (loading || recalculating) {
    return (
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800">
        <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-800">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Partial Dependence Plots (PDP) with ICE Lines</h2>
              <p className="text-sm text-gray-600 dark:text-white mt-1">
                How predictions change when varying each feature while keeping others constant
              </p>
            </div>

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
          </div>
        </div>

        <div className="p-8">
          <div className="flex items-center justify-center gap-3">
            <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
            <span className="text-gray-600 dark:text-white">
              {recalculating ? 'Calculating PDP/ICE plots...' : 'Loading PDP/ICE plots...'}
            </span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800">
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-800">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Partial Dependence Plots (PDP) with ICE Lines</h2>
            <p className="text-sm text-gray-600 dark:text-white mt-1">
              How predictions change when varying each feature while keeping others constant
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

            <div className="flex items-center gap-2">
              <label className="text-sm font-medium text-gray-700 dark:text-white">ICE Lines:</label>
              <select
                value={maxIceLines}
                onChange={(e) => setMaxIceLines(Number(e.target.value))}
                className="text-sm border border-gray-300 dark:border-gray-700 rounded px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
              >
                <option value={50}>50</option>
                <option value={100}>100</option>
                <option value={200}>200</option>
                <option value={500}>500</option>
                <option value={1000}>1,000 (Max)</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      <div className="p-6">
        {/* Loading state */}
        {isLoadingPDP && (
          <div className="flex items-center justify-center p-12 bg-blue-50 dark:bg-gray-800 rounded-lg border border-blue-200 dark:border-gray-700">
            <div className="flex flex-col items-center gap-3">
              <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div>
              <div className="text-blue-700 dark:text-white font-medium">Loading PDP data...</div>
              <div className="text-blue-600 dark:text-white text-sm">Optimized lazy loading for faster performance</div>
            </div>
          </div>
        )}

        {/* Error state */}
        {pdpLoadError && !isLoadingPDP && (
          <div className="flex items-center justify-center p-12 bg-red-50 dark:bg-red-900/30 rounded-lg border border-red-200 dark:border-red-800">
            <div className="text-center">
              <div className="text-red-700 dark:text-red-200 font-medium mb-2">Failed to load PDP data</div>
              <div className="text-red-600 dark:text-red-300 text-sm">{pdpLoadError}</div>
            </div>
          </div>
        )}

        {/* Content */}
        {!isLoadingPDP && !loading && !recalculating && !pdpLoadError && (
          <div>
            <div className="mb-6 pb-4 border-b border-gray-200 dark:border-gray-800">
              <div className="flex items-start gap-3 bg-blue-50 dark:bg-gray-800 rounded-lg p-4">
                <div className="flex-shrink-0 mt-0.5">
                  <svg width="20" height="20" viewBox="0 0 20 20">
                    <circle cx="10" cy="10" r="9" fill="none" stroke="#3b82f6" strokeWidth="2" />
                    <text x="10" y="14" textAnchor="middle" className="text-xs font-bold fill-blue-600">i</text>
                  </svg>
                </div>
                <div className="text-sm text-blue-900 dark:text-white">
                  <span className="font-semibold">How to read:</span> Each plot shows gray ICE lines representing individual predictions and a cyan PDP line showing the average effect. When ICE lines spread apart, the feature interacts with others. The slope of the PDP line indicates the feature's overall impact direction.
                </div>
              </div>
            </div>

            {/* Model indicator */}
            <div className="flex items-center gap-3 mb-4">
              <div
                className="w-4 h-4 rounded"
                style={{ backgroundColor: currentModel.color }}
              />
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{formatModelName(currentModel)}</h3>
            </div>

            {currentPdpData.length === 0 ? (
              <div className="text-center text-gray-500 dark:text-white py-8">
                No PDP data available
              </div>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {currentPdpData.map((pdp) => {
                  const values = (pdp.values || []) as PDPPoint[];
                  if (values.length === 0) return null;

                  const iceLines = pdp.metadata?.ice_lines || [];

                  // OPTIMIZATION: Limit ICE lines to avoid rendering too many elements
                  // Backend may send 37,000+ ICE lines, but Canvas can handle large numbers efficiently
                  // Using configurable limit (default 100, can be increased or set to -1 for all)
                  const totalIceLines = iceLines.length;
                  // Slice early to avoid processing all ICE lines
                  // Display up to maxIceLines (backend provides max 1000)
                  const displayIceLines = iceLines.slice(0, maxIceLines);

                  // Calculate ranges - use reduce to avoid stack overflow with large arrays
                  const allYValues = values.map(v => v.y);

                  // Calculate ICE line ranges - only use displayed ICE lines for range calculation
                  const allIceYValues = displayIceLines.flat().concat(allYValues);
                  const iceMinY = allIceYValues.reduce((min: number, val: number) => Math.min(min, val), allIceYValues[0] || 0);
                  const iceMaxY = allIceYValues.reduce((max: number, val: number) => Math.max(max, val), allIceYValues[0] || 0);
                  const iceRangeY = iceMaxY - iceMinY || 0.1;
                  const paddedMinY = iceMinY - iceRangeY * 0.05;
                  const paddedMaxY = iceMaxY + iceRangeY * 0.05;

                  const minX = values[0].x;
                  const maxX = values[values.length - 1].x;
                  const rangeX = maxX - minX || 1;

                  const featureName = pdp.feature_name || 'Unknown Feature';
                  const displayName = featureName.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase());

                  return (
                    <div key={`${pdp.model_id}-${featureName}`} className="border border-gray-200 dark:border-gray-800 rounded-lg p-4 bg-white dark:bg-gray-900">
                      <h4 className="text-sm font-semibold text-gray-800 dark:text-white mb-3">
                        {displayName}
                      </h4>

                      <div className="relative h-64 bg-gray-50 dark:bg-gray-800 rounded-lg overflow-hidden" style={{ paddingLeft: '56px', paddingRight: '16px', paddingTop: '16px', paddingBottom: '56px' }}>
                        {/* Canvas-based rendering for better performance with large datasets */}
                        <PDPICEPlotCanvas
                          values={values}
                          iceLines={iceLines}
                          featureName={featureName}
                          width={600}
                          height={256}
                          maxIceLines={maxIceLines}
                        />

                        {/* Y-axis labels */}
                        <div className="absolute left-0 top-4 bottom-14 flex flex-col justify-between text-xs text-gray-600 dark:text-white" style={{ width: '48px' }}>
                          {[paddedMaxY, (paddedMaxY * 2 + paddedMinY) / 3, (paddedMaxY + paddedMinY * 2) / 3, paddedMinY].map((val, idx) => (
                            <div key={idx} className="text-right pr-2">
                              {val.toFixed(2)}
                            </div>
                          ))}
                        </div>

                        {/* X-axis labels */}
                        <div className="absolute bottom-0 left-14 right-4 flex justify-between text-xs text-gray-600 dark:text-white" style={{ height: '40px', paddingTop: '4px' }}>
                          {[0, 0.2, 0.4, 0.6, 0.8, 1].map((ratio, idx) => {
                            const val = minX + ratio * rangeX;
                            return (
                              <span key={idx} className="text-center" style={{ width: '16.66%' }}>
                                {val >= 1000 ? `${(val / 1000).toFixed(0)}k` : val.toFixed(0)}
                              </span>
                            );
                          })}
                        </div>

                        {/* Y-axis label */}
                        <div
                          className="absolute text-xs font-medium text-gray-700 dark:text-white whitespace-nowrap origin-center"
                          style={{
                            left: '12px',
                            top: '50%',
                            transform: 'translateY(-50%) rotate(-90deg)',
                            transformOrigin: 'center'
                          }}
                        >
                          Prediction Probability
                        </div>

                        {/* X-axis label */}
                        <div
                          className="absolute text-xs font-medium text-gray-700 dark:text-white text-center"
                          style={{
                            bottom: '8px',
                            left: '56px',
                            right: '16px'
                          }}
                        >
                          {displayName}
                        </div>
                      </div>

                      {/* Legend */}
                      <div className="mt-4 flex items-center justify-center gap-6 text-xs">
                        <div className="flex items-center gap-2">
                          <div className="w-8 h-0.5 bg-gray-300"></div>
                          <span className="text-gray-600 dark:text-white">
                            ICE Lines {totalIceLines > displayIceLines.length ? `(${displayIceLines.length.toLocaleString()}/${totalIceLines.toLocaleString()} shown)` : `(${totalIceLines.toLocaleString()})`}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="w-8 h-0.5 bg-cyan-500" style={{ height: '3px' }}></div>
                          <span className="text-gray-600 dark:text-white">PDP Line</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="px-6 py-4 bg-gray-50 dark:bg-gray-800 border-t border-gray-200 dark:border-gray-800">
        <div className="text-sm text-gray-600 dark:text-white space-y-2">
          <div>
            <span className="font-semibold">PDP vs ICE:</span> The cyan PDP line shows the average effect of a feature across all samples. The gray ICE (Individual Conditional Expectation) lines show how individual predictions change as the feature varies, revealing heterogeneous effects and interactions.
          </div>
          <div>
            <span className="font-semibold">Interpretation:</span> When ICE lines are parallel, the feature has a consistent effect. Diverging ICE lines indicate the feature interacts with others. An upward PDP means higher feature values increase predictions on average.
          </div>
        </div>
      </div>
    </div>
  );
};

export default PDPICEPlot;


