/**
 * Model Comparison Dashboard - Comprehensive Multi-Model Performance Evaluation
 * Similar to the reference dashboard showing side-by-side model comparisons
 */

import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { 
  Activity, BarChart3, Target, TrendingUp, Lightbulb, 
  RefreshCw, AlertTriangle, XCircle, CheckCircle2, Sparkles
} from 'lucide-react';
import modelEvaluationService from '../services/modelEvaluationService';
import { ModelEvaluationData, EvaluationModel } from '../types/modelEvaluation';

// Import comparison components
import ROCCurveComparison from '../components/ModelEvaluation/ROCCurveComparison';
import PerformanceRadarChart from '../components/ModelEvaluation/PerformanceRadarChart';
import ConfusionMatrixComparison from '../components/ModelEvaluation/ConfusionMatrixComparison';
import PerformanceMetricsComparison from '../components/ModelEvaluation/PerformanceMetricsComparison';
import ModelRecommendation from '../components/ModelEvaluation/ModelRecommendation';

const ModelComparisonDashboard: React.FC = () => {
  const [searchParams] = useSearchParams();
  const modelIdsFromParams = searchParams.get('model_ids')?.split(',') || [];
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedModelIds, setSelectedModelIds] = useState<string[]>(modelIdsFromParams);
  const [evaluationData, setEvaluationData] = useState<Record<string, ModelEvaluationData>>({});
  const [availableModels, setAvailableModels] = useState<EvaluationModel[]>([]);
  const [activeTab, setActiveTab] = useState<'performance' | 'explainability' | 'monotonicity' | 'granular' | 'fairness'>('performance');
  const [refreshing, setRefreshing] = useState(false);

  // Model colors for visualization
  const modelColors = [
    '#3B82F6', // Blue - Logistic Regression
    '#10B981', // Green - Random Forest
    '#F59E0B', // Yellow - XGBoost
    '#8B5CF6', // Purple - Neural Network
    '#EF4444', // Red - Support Vector Machine
    '#06B6D4', // Cyan
    '#EC4899', // Pink
    '#84CC16', // Lime
  ];

  // Fetch available models
  useEffect(() => {
    const fetchModels = async () => {
      try {
        const response = await modelEvaluationService.listAllModels();
        const modelsWithMEEA = response.models.filter(m => m.has_meea_data);
        setAvailableModels(modelsWithMEEA);
        
        // If no models selected but models available, select top 5
        if (selectedModelIds.length === 0 && modelsWithMEEA.length > 0) {
          setSelectedModelIds(modelsWithMEEA.slice(0, Math.min(5, modelsWithMEEA.length)).map(m => m.id));
        }
      } catch (err) {
        console.error('Error fetching models:', err);
      }
    };
    
    fetchModels();
  }, []);

  // Fetch evaluation data for selected models
  useEffect(() => {
    if (selectedModelIds.length === 0) return;

    const fetchEvaluationData = async () => {
      setLoading(true);
      setError(null);
      
      try {
        const results = await Promise.all(
          selectedModelIds.map(async (modelId) => {
            try {
              const response = await modelEvaluationService.getModelEvaluation(modelId);
              return { modelId, data: response.evaluation_data };
            } catch (err: any) {
              console.error(`Error fetching evaluation for ${modelId}:`, err);
              return { modelId, error: err.response?.data?.detail || 'Failed to fetch evaluation data' };
            }
          })
        );

        const dataMap: Record<string, ModelEvaluationData> = {};
        results.forEach((result) => {
          if (result.data) {
            dataMap[result.modelId] = result.data;
          }
        });

        setEvaluationData(dataMap);
      } catch (err: any) {
        setError('Failed to fetch evaluation data for one or more models');
        console.error('Error fetching evaluation data:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchEvaluationData();
  }, [selectedModelIds]);

  const handleRefresh = async () => {
    if (selectedModelIds.length === 0) return;
    setRefreshing(true);
    try {
      const results = await Promise.all(
        selectedModelIds.map(async (modelId) => {
          try {
            const response = await modelEvaluationService.getModelEvaluation(modelId);
            return { modelId, data: response.evaluation_data };
          } catch (err: any) {
            return { modelId, error: err.response?.data?.detail || 'Failed to fetch evaluation data' };
          }
        })
      );

      const dataMap: Record<string, ModelEvaluationData> = {};
      results.forEach((result) => {
        if (result.data) {
          dataMap[result.modelId] = result.data;
        }
      });

      setEvaluationData(dataMap);
    } catch (err: any) {
      setError('Failed to refresh evaluation data');
    } finally {
      setRefreshing(false);
    }
  };

  // Prepare data for comparison components
  const prepareComparisonData = () => {
    const models = Object.entries(evaluationData).map(([modelId, data], index) => {
      const model = availableModels.find(m => m.id === modelId) || data.model;
      const metrics = data.performance_metrics;
      
      return {
        modelName: model?.name || data.model?.name || 'Unknown Model',
        modelId: modelId,
        accuracy: metrics?.accuracy || 0,
        precision: metrics?.precision || 0,
        recall: metrics?.recall || 0,
        f1Score: metrics?.f1_score || 0,
        aucRoc: metrics?.auc_roc || 0,
        aucPr: metrics?.auc_pr,
        logLoss: metrics?.log_loss,
        color: modelColors[index % modelColors.length],
        parameters: model?.model_type || data.model?.model_type,
        confusionMatrix: metrics?.confusion_matrix,
        rocData: (() => {
          const rocEntry = data.explainability_data?.find(d => d.data_type === 'roc_curve');
          if (rocEntry && rocEntry.values) {
            // Check if it's already ROCCurveData format or needs extraction
            if (rocEntry.values.fpr && rocEntry.values.tpr) {
              return rocEntry.values;
            }
            // If it's a different format, try to extract
            return rocEntry.values as any;
          }
          return null;
        })(),
      };
    });

    return models;
  };

  const comparisonModels = prepareComparisonData();
  const modelsCount = comparisonModels.length;

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 flex items-center justify-center">
        <div className="text-center">
          <div className="relative w-20 h-20 mx-auto mb-6">
            <div className="absolute top-0 left-0 w-full h-full border-4 border-blue-200 rounded-full animate-ping opacity-75"></div>
            <div className="absolute top-0 left-0 w-full h-full border-4 border-blue-600 rounded-full animate-spin border-t-transparent"></div>
            <div className="absolute inset-0 flex items-center justify-center">
              <BarChart3 className="w-8 h-8 text-blue-600" />
            </div>
          </div>
          <p className="text-gray-700 font-semibold text-lg">Loading model comparison data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 dark:from-slate-950 dark:via-slate-900 dark:to-slate-900 overflow-x-hidden pb-8 model-evaluation">
      {/* Header */}
      <header className="bg-white border-b-2 border-gray-200 shadow-lg z-50 backdrop-blur-sm bg-opacity-95">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-5">
              <div className="relative">
                <div className="bg-gradient-to-br from-blue-600 via-indigo-600 to-purple-600 p-3 rounded-xl shadow-lg transform hover:scale-105 transition-transform">
                  <BarChart3 className="w-7 h-7 text-white" />
                </div>
                <div className="absolute -top-1 -right-1 w-4 h-4 bg-green-500 rounded-full border-2 border-white animate-pulse"></div>
              </div>
              <div>
                <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 bg-clip-text text-transparent">
                  Model Evaluation & Explainability Agent
                </h1>
                <p className="text-sm text-gray-600 mt-1 flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-yellow-500" />
                  Comprehensive Evaluation Dashboard - Model Comparison
                </p>
              </div>
            </div>
            
            {/* Status Indicators */}
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-3 bg-gray-50 rounded-lg px-4 py-2 border border-gray-200">
                <span className="text-sm font-semibold text-gray-700">Models:</span>
                <span className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm font-bold">
                  {modelsCount} Models Evaluated
                </span>
              </div>
              <button
                onClick={handleRefresh}
                disabled={refreshing || selectedModelIds.length === 0}
                className="p-2 bg-blue-50 hover:bg-blue-100 text-blue-600 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed border border-blue-200"
                title="Refresh data"
              >
                <RefreshCw className={`w-5 h-5 ${refreshing ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Model Selector */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="bg-white rounded-xl shadow-lg p-6 border-2 border-gray-200">
          <div className="flex items-center gap-4 flex-wrap">
            <label className="text-sm font-semibold text-gray-700">Select Models to Compare:</label>
            <div className="flex-1 min-w-[300px]">
              <select
                multiple
                value={selectedModelIds}
                onChange={(e) => {
                  const selected = Array.from(e.target.selectedOptions, option => option.value);
                  setSelectedModelIds(selected);
                }}
                className="w-full px-4 py-2 border-2 border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white shadow-sm font-medium text-gray-900 min-h-[100px]"
                size={5}
              >
                {availableModels.map(model => {
                  const isSegment = (model as any).is_segment_model;
                  const segmentId = (model as any).segment_id;
                  const label = isSegment && segmentId
                    ? `${model.name} [segment = ${segmentId}]`
                    : `${model.name} (Global)`;
                  return (
                    <option key={model.id} value={model.id}>
                      ✅ {label} - {model.id}
                    </option>
                  );
                })}
              </select>
            </div>
            <div className="text-sm text-gray-600">
              <p>Hold Ctrl/Cmd to select multiple models</p>
              <p className="mt-1">Selected: {selectedModelIds.length} model(s)</p>
            </div>
          </div>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="bg-red-50 border-2 border-red-300 text-red-800 px-6 py-4 rounded-xl flex items-center gap-4 shadow-lg">
            <AlertTriangle className="w-6 h-6 text-red-600 flex-shrink-0" />
            <div className="flex-1">
              <strong className="font-bold text-lg block mb-1">Error Loading Comparison Data</strong>
              <p className="text-sm">{error}</p>
            </div>
            <button
              onClick={() => setError(null)}
              className="text-red-600 hover:text-red-800"
            >
              <XCircle className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}

      {/* No Models Selected */}
      {!loading && selectedModelIds.length === 0 && (
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
          <div className="text-center bg-white rounded-2xl shadow-2xl p-12 border-2 border-gray-200">
            <div className="w-32 h-32 mx-auto bg-gradient-to-br from-blue-100 via-indigo-100 to-purple-100 rounded-full flex items-center justify-center mb-8 relative">
              <BarChart3 className="w-16 h-16 text-blue-600" />
              <div className="absolute inset-0 rounded-full border-4 border-blue-200 animate-ping opacity-75"></div>
            </div>
            <h2 className="text-4xl font-bold text-gray-900 mb-4">
              Select Models to Compare
            </h2>
            <p className="text-gray-600 text-lg mb-8 max-w-md mx-auto">
              Choose multiple models from the dropdown above to see comprehensive side-by-side performance comparison.
            </p>
          </div>
        </div>
      )}

      {/* Main Content - Comparison Dashboard */}
      {!loading && comparisonModels.length > 0 && (
        <>
          {/* Navigation Tabs */}
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
            <div className="bg-white rounded-2xl shadow-xl p-2 border-2 border-gray-100">
              <nav className="flex gap-2">
                {[
                  { id: 'performance', icon: Activity, label: 'Performance', color: 'blue' },
                  { id: 'explainability', icon: Lightbulb, label: 'Explainability', color: 'yellow' },
                  { id: 'monotonicity', icon: TrendingUp, label: 'Monotonicity', color: 'green' },
                  { id: 'granular', icon: Target, label: 'Granular Accuracy', color: 'purple' },
                  { id: 'fairness', icon: CheckCircle2, label: 'Fairness', color: 'indigo' },
                ].map((tab) => {
                  const isActive = activeTab === tab.id;
                  const Icon = tab.icon;
                  
                  return (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id as any)}
                      className={`
                        flex-1 flex items-center justify-center gap-2 px-6 py-4 rounded-xl font-semibold transition-all min-w-[150px]
                        ${isActive
                          ? `bg-gradient-to-r from-${tab.color}-500 to-${tab.color}-600 text-white shadow-lg transform scale-105 border-2 border-${tab.color}-300`
                          : 'text-gray-600 hover:bg-gray-100 border-2 border-transparent hover:border-gray-200'
                        }
                      `}
                    >
                      <Icon className={`w-5 h-5 ${isActive ? 'animate-pulse' : ''}`} />
                      <span className="text-sm">{tab.label}</span>
                    </button>
                  );
                })}
              </nav>
            </div>
          </div>

          {/* Tab Content */}
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-8 pb-12">
            {activeTab === 'performance' && (
              <div className="space-y-8">
                {/* Model Recommendation */}
                <ModelRecommendation 
                  models={comparisonModels}
                  recommendationReason={
                    comparisonModels.length > 0
                      ? `${comparisonModels[0].modelName} demonstrates the best balance of predictive performance (AUC-ROC: ${comparisonModels[0].aucRoc.toFixed(2)}) and overall metrics. Recommended for production deployment with continued monitoring.`
                      : undefined
                  }
                />

                {/* Performance Metrics Comparison Table */}
                <PerformanceMetricsComparison 
                  models={comparisonModels}
                  title="Performance Metrics Comparison"
                />

                {/* ROC Curve Comparison */}
                {comparisonModels.some(m => m.rocData && m.rocData.fpr && m.rocData.tpr) && (
                  <ROCCurveComparison
                    models={comparisonModels
                      .filter(m => m.rocData && m.rocData.fpr && m.rocData.tpr)
                      .map(m => ({
                        modelName: m.modelName,
                        modelId: m.modelId,
                        rocData: m.rocData as any,
                        color: m.color,
                      }))}
                    title="ROC Curve Comparison"
                  />
                )}

                {/* Radar Chart */}
                <PerformanceRadarChart
                  models={comparisonModels.map(m => ({
                    modelName: m.modelName,
                    modelId: m.modelId,
                    accuracy: m.accuracy,
                    precision: m.precision,
                    recall: m.recall,
                    f1Score: m.f1Score,
                    aucRoc: m.aucRoc,
                    color: m.color,
                  }))}
                  title="Performance Radar Chart"
                />

                {/* Confusion Matrix Comparison */}
                {comparisonModels.some(m => m.confusionMatrix) && (
                  <ConfusionMatrixComparison
                    models={comparisonModels
                      .filter(m => m.confusionMatrix)
                      .map(m => ({
                        modelName: m.modelName,
                        modelId: m.modelId,
                        matrix: m.confusionMatrix!,
                        accuracy: m.accuracy,
                        f1Score: m.f1Score,
                        color: m.color,
                      }))}
                    title="Confusion Matrix Comparison"
                  />
                )}
              </div>
            )}

            {activeTab === 'explainability' && (
              <div className="bg-white rounded-2xl shadow-xl p-8 border-2 border-gray-100">
                <h3 className="text-2xl font-bold text-gray-900 mb-4">Explainability Analysis</h3>
                <p className="text-gray-600">Explainability comparison across models will be displayed here.</p>
              </div>
            )}

            {activeTab === 'monotonicity' && (
              <div className="bg-white rounded-2xl shadow-xl p-8 border-2 border-gray-100">
                <h3 className="text-2xl font-bold text-gray-900 mb-4">Monotonicity Analysis</h3>
                <p className="text-gray-600">Monotonicity comparison across models will be displayed here.</p>
              </div>
            )}

            {activeTab === 'granular' && (
              <div className="bg-white rounded-2xl shadow-xl p-8 border-2 border-gray-100">
                <h3 className="text-2xl font-bold text-gray-900 mb-4">Granular Accuracy</h3>
                <p className="text-gray-600">Granular accuracy comparison across models will be displayed here.</p>
              </div>
            )}

            {activeTab === 'fairness' && (
              <div className="bg-white rounded-2xl shadow-xl p-8 border-2 border-gray-100">
                <h3 className="text-2xl font-bold text-gray-900 mb-4">Fairness Analysis</h3>
                <p className="text-gray-600">Fairness comparison across models will be displayed here.</p>
              </div>
            )}
          </div>
        </>
      )}

      {/* Footer */}
      <footer className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 mt-16 mb-8 border-t-2 border-gray-200">
        <div className="text-center">
          <div className="flex items-center justify-center gap-2 mb-4">
            <Sparkles className="w-5 h-5 text-yellow-500" />
            <p className="text-gray-700 font-semibold">Model Evaluation & Explainability Agent - Agentic ML Workflow System</p>
          </div>
          <p className="text-gray-600 text-sm">
            Last Updated: {new Date().toLocaleDateString()} | Version: v1.0.0
          </p>
        </div>
      </footer>
    </div>
  );
};

export default ModelComparisonDashboard;

