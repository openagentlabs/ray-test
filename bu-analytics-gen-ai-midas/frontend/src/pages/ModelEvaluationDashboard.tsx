/**
 * Model Evaluation Dashboard - Main MEEA Integration Page
 * Comprehensive model evaluation and error analysis
 */

import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import modelEvaluationService from '../services/modelEvaluationService';
import {
  ModelEvaluationData,
  EvaluationModel,
  ROCCurveData
} from '../types/modelEvaluation';

// Import MEEA components
import ConfusionMatrixChart from '../components/ModelEvaluation/ConfusionMatrixChart';
import ROCCurveChart from '../components/ModelEvaluation/ROCCurveChart';
import FeatureImportanceChart from '../components/ModelEvaluation/FeatureImportanceChart';
import PerformanceMetricsCard from '../components/ModelEvaluation/PerformanceMetricsCard';

const ModelEvaluationDashboard: React.FC = () => {
  const [searchParams] = useSearchParams();
  const modelIdFromParams = searchParams.get('model_id');
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedModelId, setSelectedModelId] = useState<string | null>(modelIdFromParams);
  const [evaluationData, setEvaluationData] = useState<ModelEvaluationData | null>(null);
  const [availableModels, setAvailableModels] = useState<EvaluationModel[]>([]);
  const [activeTab, setActiveTab] = useState<'overview' | 'features' | 'errors' | 'explainability'>('overview');

  // Fetch available models on mount
  useEffect(() => {
    const fetchModels = async () => {
      try {
        const response = await modelEvaluationService.listAllModels();
        setAvailableModels(response.models);
        
        // If no model selected but models available, select the first one
        if (!selectedModelId && response.models.length > 0) {
          setSelectedModelId(response.models[0].id);
        }
      } catch (err) {
        console.error('Error fetching models:', err);
      }
    };
    
    fetchModels();
  }, []);

  // Fetch evaluation data when model is selected
  useEffect(() => {
    if (!selectedModelId) return;

    const fetchEvaluationData = async () => {
      setLoading(true);
      setError(null);
      
      try {
        const response = await modelEvaluationService.getModelEvaluation(selectedModelId);
        setEvaluationData(response.evaluation_data);
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to fetch evaluation data');
        console.error('Error fetching evaluation data:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchEvaluationData();
  }, [selectedModelId]);

  // Extract ROC curve data
  const getROCCurveData = (): ROCCurveData | Record<string, ROCCurveData> | null => {
    if (!evaluationData?.explainability_data) return null;
    
    const rocEntry = evaluationData.explainability_data.find(
      item => item.data_type === 'roc_curve'
    );
    
    return rocEntry?.values || null;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading evaluation data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">
                Model Evaluation Dashboard
              </h1>
              <p className="mt-1 text-sm text-gray-600">
                Comprehensive model evaluation and error analysis (MEEA)
              </p>
            </div>
            
            {/* Model Selector */}
            {availableModels.length > 0 && (
              <div className="flex items-center gap-3">
                <label className="text-sm font-medium text-gray-700">Select Model:</label>
                <select
                  value={selectedModelId || ''}
                  onChange={(e) => setSelectedModelId(e.target.value)}
                  className="px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">-- Select a model --</option>
                  {availableModels.map(model => (
                    <option key={model.id} value={model.id}>
                      {model.name} ({model.id})
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Error State */}
      {error && (
        <div className="max-w-7xl mx-auto py-4 px-4 sm:px-6 lg:px-8">
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
            <strong>Error:</strong> {error}
          </div>
        </div>
      )}

      {/* No Models Available */}
      {!loading && availableModels.length === 0 && (
        <div className="max-w-7xl mx-auto py-12 px-4 sm:px-6 lg:px-8">
          <div className="text-center">
            <div className="text-6xl mb-4">📊</div>
            <h2 className="text-2xl font-semibold text-gray-700 mb-2">
              No Evaluated Models Found
            </h2>
            <p className="text-gray-600">
              Train a model using auto-training to see evaluation results here.
            </p>
          </div>
        </div>
      )}

      {/* Main Content */}
      {!loading && evaluationData && (
        <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
          {/* Model Info Banner */}
          <div 
            className="mb-6 p-4 rounded-lg text-white"
            style={{ backgroundColor: evaluationData.model.color }}
          >
            <div className="flex justify-between items-center">
              <div>
                <h2 className="text-2xl font-bold">{evaluationData.model.name}</h2>
                <p className="text-sm opacity-90 mt-1">
                  Model Type: {evaluationData.model.model_type} | 
                  Task: {evaluationData.model.task_type} | 
                  Status: {evaluationData.model.status}
                </p>
              </div>
              <div className="text-right">
                <div className="text-sm opacity-90">Model ID</div>
                <div className="font-mono text-lg">{evaluationData.model.id}</div>
              </div>
            </div>
          </div>

          {/* Tabs */}
          <div className="mb-6 border-b border-gray-200">
            <nav className="-mb-px flex space-x-8">
              {[
                { id: 'overview', label: 'Overview', icon: '📊' },
                { id: 'features', label: 'Feature Analysis', icon: '🔍' },
                { id: 'errors', label: 'Error Analysis', icon: '⚠️' },
                { id: 'explainability', label: 'Explainability', icon: '💡' }
              ].map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`
                    py-2 px-1 border-b-2 font-medium text-sm flex items-center gap-2
                    ${activeTab === tab.id
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                    }
                  `}
                >
                  <span>{tab.icon}</span>
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>

          {/* Tab Content */}
          {activeTab === 'overview' && (
            <div className="space-y-6">
              {/* Performance Metrics */}
              <PerformanceMetricsCard 
                metrics={evaluationData.performance_metrics}
                taskType={evaluationData.model.task_type}
              />

              {/* Confusion Matrix */}
              {evaluationData.performance_metrics.confusion_matrix && (
                <ConfusionMatrixChart 
                  matrix={evaluationData.performance_metrics.confusion_matrix}
                />
              )}

              {/* ROC Curve */}
              {getROCCurveData() && (
                <ROCCurveChart rocData={getROCCurveData()!} />
              )}
            </div>
          )}

          {activeTab === 'features' && (
            <div className="space-y-6">
              {/* Feature Importance */}
              <FeatureImportanceChart 
                features={evaluationData.feature_importance}
                topN={20}
              />

              {/* Granular Accuracy */}
              {evaluationData.granular_accuracy && evaluationData.granular_accuracy.length > 0 && (
                <div className="bg-white p-6 rounded-lg shadow">
                  <h3 className="text-lg font-semibold mb-4">Granular Accuracy Analysis</h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-gray-50">
                          <th className="border p-2 text-left">Variable</th>
                          <th className="border p-2 text-left">Segment</th>
                          <th className="border p-2 text-center">Accuracy</th>
                          <th className="border p-2 text-center">Precision</th>
                          <th className="border p-2 text-center">Recall</th>
                          <th className="border p-2 text-center">F1 Score</th>
                          <th className="border p-2 text-center">Samples</th>
                        </tr>
                      </thead>
                      <tbody>
                        {evaluationData.granular_accuracy.map((item, idx) => (
                          <tr key={idx} className="hover:bg-gray-50">
                            <td className="border p-2 font-medium">{item.variable}</td>
                            <td className="border p-2">{item.segment}</td>
                            <td className="border p-2 text-center">{item.accuracy.toFixed(3)}</td>
                            <td className="border p-2 text-center">{item.precision.toFixed(3)}</td>
                            <td className="border p-2 text-center">{item.recall.toFixed(3)}</td>
                            <td className="border p-2 text-center">{item.f1_score.toFixed(3)}</td>
                            <td className="border p-2 text-center">{item.sample_count}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'errors' && (
            <div className="space-y-6">
              {/* Error Patterns */}
              {evaluationData.error_patterns && evaluationData.error_patterns.length > 0 && (
                <div className="bg-white p-6 rounded-lg shadow">
                  <h3 className="text-lg font-semibold mb-4">Error Pattern Analysis</h3>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {evaluationData.error_patterns.map((pattern, idx) => (
                      <div key={idx} className="p-4 border rounded-lg">
                        <div className="text-sm text-gray-600 mb-2">
                          {pattern.error_type.replace(/_/g, ' ').toUpperCase()}
                        </div>
                        <div className="text-3xl font-bold text-gray-900">{pattern.count}</div>
                        <div className="text-sm text-gray-500 mt-1">
                          {pattern.percentage.toFixed(1)}% of predictions
                        </div>
                        {pattern.avg_confidence && (
                          <div className="text-xs text-gray-400 mt-2">
                            Avg Confidence: {pattern.avg_confidence.toFixed(3)}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Prediction Confidence */}
              {evaluationData.prediction_confidence && evaluationData.prediction_confidence.length > 0 && (
                <div className="bg-white p-6 rounded-lg shadow">
                  <h3 className="text-lg font-semibold mb-4">Prediction Confidence Analysis</h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-gray-50">
                          <th className="border p-2">Confidence Range</th>
                          <th className="border p-2 text-center">Count</th>
                          <th className="border p-2 text-center">Accuracy</th>
                          <th className="border p-2 text-center">Avg Confidence</th>
                        </tr>
                      </thead>
                      <tbody>
                        {evaluationData.prediction_confidence.map((conf, idx) => (
                          <tr key={idx} className="hover:bg-gray-50">
                            <td className="border p-2">
                              {conf.bin_start.toFixed(2)} - {conf.bin_end.toFixed(2)}
                            </td>
                            <td className="border p-2 text-center">{conf.count}</td>
                            <td className="border p-2 text-center">{conf.accuracy.toFixed(3)}</td>
                            <td className="border p-2 text-center">{conf.avg_confidence.toFixed(3)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'explainability' && (
            <div className="space-y-6">
              <div className="bg-white p-6 rounded-lg shadow">
                <h3 className="text-lg font-semibold mb-4">SHAP & Explainability</h3>
                <p className="text-gray-600">
                  SHAP values and partial dependence plots will be displayed here.
                </p>
                {evaluationData.explainability_data && evaluationData.explainability_data.length > 0 && (
                  <div className="mt-4">
                    <p className="text-sm text-gray-600">
                      {evaluationData.explainability_data.length} explainability data points available
                    </p>
                    <ul className="mt-2 space-y-1">
                      {evaluationData.explainability_data.map((item, idx) => (
                        <li key={idx} className="text-sm text-gray-700">
                          • {item.data_type}
                          {item.feature_name && ` (${item.feature_name})`}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ModelEvaluationDashboard;

