/**
 * SHAP Feature Importance Chart Component
 * Displays SHAP feature importance as horizontal bar chart
 * Independent component with its own model selector
 */

import React, { useState, useEffect } from 'react';
import { Loader2 } from 'lucide-react';
import { EvaluationModel, ModelEvaluationData } from '../../types/modelEvaluation';

interface SHAPFeatureImportanceChartProps {
  models: EvaluationModel[];
  evaluationData: Record<string, ModelEvaluationData>;
  selectedModel?: string;
  onModelChange?: (modelId: string) => void;
  loading?: boolean; // Whether explainability data is being loaded/calculated
  recalculating?: boolean; // Whether explainability data is being recalculated
}

const SHAPFeatureImportanceChart: React.FC<SHAPFeatureImportanceChartProps> = ({
  models,
  evaluationData,
  selectedModel: propSelectedModel,
  onModelChange: propOnModelChange,
  loading = false,
  recalculating = false,
}) => {
  // Use prop if provided, otherwise use internal state
  const [internalSelectedModel, setInternalSelectedModel] = useState<string>('');
  const selectedModel = propSelectedModel !== undefined ? propSelectedModel : internalSelectedModel;
  const setSelectedModel = propOnModelChange || setInternalSelectedModel;
  
  const [topN, setTopN] = useState<number | 'all'>(10);

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
            d => d.data_type === 'shap_summary'
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

  // Extract SHAP feature importance from evaluation data
  const getSHAPFeatureImportance = () => {
    if (!modelEvalData) {
      console.log('SHAPFeatureImportanceChart: No modelEvalData');
      return [];
    }

    // Debug logging
    console.log('SHAPFeatureImportanceChart: modelEvalData', {
      hasExplainabilityData: !!modelEvalData.explainability_data,
      explainabilityDataLength: modelEvalData.explainability_data?.length || 0,
      hasFeatureImportance: !!modelEvalData.feature_importance,
      featureImportanceLength: modelEvalData.feature_importance?.length || 0,
      explainabilityDataTypes: modelEvalData.explainability_data?.map(d => d.data_type) || [],
      explainabilityData: modelEvalData.explainability_data || []
    });

    if (!modelEvalData.explainability_data) {
      console.log('SHAPFeatureImportanceChart: No explainability_data array');
      // Fallback: try feature_importance from evaluation data
      if (modelEvalData.feature_importance && Array.isArray(modelEvalData.feature_importance)) {
        console.log('SHAPFeatureImportanceChart: Using feature_importance fallback');
        return modelEvalData.feature_importance
          .filter(f => f.shap_importance && f.shap_importance > 0)
          .map(f => ({
            feature_name: f.feature_name,
            importance: f.shap_importance || 0
          }));
      }
      return [];
    }

    // Try to get from shap_analysis in explainability_data
    const shapEntry = modelEvalData.explainability_data.find(
      d => d.data_type === 'shap_summary' && !d.feature_name
    );

    console.log('SHAPFeatureImportanceChart: shapEntry', shapEntry);

    if (shapEntry && shapEntry.values) {
      const shapData = shapEntry.values;
      console.log('SHAPFeatureImportanceChart: shapData', {
        hasFeatureImportance: !!shapData.feature_importance,
        isArray: Array.isArray(shapData.feature_importance),
        length: Array.isArray(shapData.feature_importance) ? shapData.feature_importance.length : 0
      });
      
      if (shapData.feature_importance && Array.isArray(shapData.feature_importance)) {
        return shapData.feature_importance;
      }
    }

    // Fallback: try feature_importance from evaluation data
    if (modelEvalData.feature_importance && Array.isArray(modelEvalData.feature_importance)) {
      console.log('SHAPFeatureImportanceChart: Using feature_importance fallback');
      return modelEvalData.feature_importance
        .filter(f => f.shap_importance && f.shap_importance > 0)
        .map(f => ({
          feature_name: f.feature_name,
          importance: f.shap_importance || 0
        }));
    }

    console.log('SHAPFeatureImportanceChart: No SHAP data found');
    return [];
  };

  const shapFeatures = getSHAPFeatureImportance();

  // Deduplicate features (keep highest importance)
  const uniqueFeatures = Array.from(
    shapFeatures.reduce((map, feature) => {
      // Normalize importance to a finite number (fallback to 0)
      const importance = Number(feature.importance ?? 0);
      const existing = map.get(feature.feature_name);
      if (!existing || importance > Number(existing.importance ?? 0)) {
        map.set(feature.feature_name, { feature_name: feature.feature_name, importance });
      }
      return map;
    }, new Map<string, { feature_name: string; importance: number }>()).values()
  );

  // Sort by importance and take top N (or all if topN is 'all')
  const sortedFeatures = uniqueFeatures
    .sort((a, b) => b.importance - a.importance)
    .slice(0, topN === 'all' ? uniqueFeatures.length : topN);

  // Use reduce to avoid stack overflow with large feature lists
  const maxValue = sortedFeatures.length > 0
    ? sortedFeatures.reduce((max, f) => Math.max(max, Number(f.importance ?? 0)), Number(sortedFeatures[0].importance ?? 0))
    : 0.1;

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
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Feature Importance - SHAP Values</h2>
              <p className="text-sm text-gray-600 dark:text-white mt-1">
                Mean absolute SHAP values showing feature contributions to predictions
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
              {recalculating ? 'Calculating SHAP feature importance...' : 'Loading SHAP feature importance...'}
            </span>
          </div>
        </div>
      </div>
    );
  }

  // Show dropdown and message if no data, but keep the UI structure
  if (sortedFeatures.length === 0) {
    return (
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800">
        <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-800">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Feature Importance - SHAP Values</h2>
              <p className="text-sm text-gray-600 dark:text-white mt-1">
                Mean absolute SHAP values showing feature contributions to predictions
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
          <div className="text-center space-y-4">
            <div className="text-gray-500 dark:text-white">
              No SHAP feature importance data available for {formatModelName(currentModel)}
            </div>
            <div className="text-sm text-gray-400 dark:text-white bg-yellow-50 border border-yellow-200 rounded-lg p-4 max-w-2xl mx-auto">
              <p className="font-semibold text-yellow-800 dark:text-white mb-2">ℹ️ Model Needs Re-evaluation</p>
              <p className="text-yellow-700 dark:text-white">
                This model was evaluated before the enhanced SHAP analysis was added. 
                Please re-train or re-evaluate the model to generate SHAP feature importance data.
              </p>
            </div>
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
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Feature Importance - SHAP Values</h2>
            <p className="text-sm text-gray-600 dark:text-white mt-1">
              Mean absolute SHAP values showing feature contributions to predictions
            </p>
          </div>

          <div className="flex items-center gap-4">
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
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
                value={topN === 'all' ? 'all' : topN}
                onChange={(e) => setTopN(e.target.value === 'all' ? 'all' : Number(e.target.value))}
                className="text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value={5}>5</option>
                <option value={8}>8</option>
                <option value={10}>10</option>
                <option value={15}>15</option>
                <option value={20}>20</option>
                <option value="all">All</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      <div className="p-8">
        <div className="space-y-1">
          {sortedFeatures.map((feature) => {
            // Coerce importance to a safe numeric value for rendering
            let value = Number(feature.importance ?? 0);
            if (!isFinite(value)) value = 0;
            const percentage = maxValue > 0 ? (value / maxValue) * 100 : 0;

            return (
              <div key={feature.feature_name} className="flex items-center gap-4 py-2">
                <div className="w-40 text-right">
                  <span className="text-sm text-gray-700 dark:text-white">
                    {feature.feature_name.replace(/_/g, ' ')}
                  </span>
                </div>

                <div className="flex-1 relative h-8">
                  <div className="absolute left-0 top-0 h-full w-px bg-gray-300"></div>

                  <div
                    className="absolute left-0 top-0 h-full rounded-r transition-all duration-300"
                    style={{
                      width: `${percentage}%`,
                      background: 'linear-gradient(90deg, #60a5fa 0%, #3b82f6 100%)'
                    }}
                  ></div>
                </div>

                <div className="w-16 text-left">
                    <span className="text-sm font-semibold text-blue-600 dark:text-white">
                      {Number.isFinite(value) ? `+${value.toFixed(2)}` : '-'}
                    </span>
                </div>
              </div>
            );
          })}
        </div>

        <div className="mt-6 pt-4 border-t border-gray-200 dark:border-gray-800">
          <div className="text-center text-sm text-gray-600 dark:text-white">
            mean(|SHAP value|)
          </div>
        </div>
      </div>

      <div className="px-6 py-4 bg-gray-50 dark:bg-gray-800 border-t border-gray-200 dark:border-gray-800">
        <div className="text-sm text-gray-600 dark:text-white">
          <span className="font-semibold">Interpretation:</span> SHAP (SHapley Additive exPlanations) values represent the average magnitude of each feature's contribution to model predictions. Higher values indicate greater importance.
        </div>
      </div>
    </div>
  );
};

export default SHAPFeatureImportanceChart;



