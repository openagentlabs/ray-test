/**
 * MEEA Evaluation Inline Component
 * Shows comprehensive model evaluation after training in Step 7
 */

import React, { useState, useEffect } from 'react';
import { Target, TrendingUp, AlertTriangle, Lightbulb, ExternalLink } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import modelEvaluationService from '../../services/modelEvaluationService';
import {
  ModelEvaluationData
} from '../../types/modelEvaluation';

// Import MEEA components
import ConfusionMatrixChart from '../ModelEvaluation/ConfusionMatrixChart';
import ROCCurveChart from '../ModelEvaluation/ROCCurveChart';
import FeatureImportanceChart from '../ModelEvaluation/FeatureImportanceChart';
import PerformanceMetricsCard from '../ModelEvaluation/PerformanceMetricsCard';

interface MEEAEvaluationInlineProps {
  modelId: string;
  modelName: string;
}

export const MEEAEvaluationInline: React.FC<MEEAEvaluationInlineProps> = ({
  modelId,
  modelName
}) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [evaluationData, setEvaluationData] = useState<ModelEvaluationData | null>(null);
  const [activeView, setActiveView] = useState<'overview' | 'features' | 'errors'>('overview');

  useEffect(() => {
    let cancelled = false;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

    const fetchEvaluation = async () => {
      if (cancelled) return;
      setLoading(true);
      setError(null);

      try {
        const response = await modelEvaluationService.getModelEvaluation(modelId);
        if (!cancelled) {
          setEvaluationData(response.evaluation_data);
          setLoading(false);
        }
      } catch (err: any) {
        if (!cancelled) {
          setError(err.response?.data?.detail || 'Evaluation data not yet available');
          setLoading(false);
          // Retry every 5 seconds while MEEA is still computing in background
          retryTimer = setTimeout(fetchEvaluation, 5000);
        }
      }
    };

    fetchEvaluation();

    return () => {
      cancelled = true;
      if (retryTimer) clearTimeout(retryTimer);
    };
  }, [modelId]);

  if (loading) {
    return (
      <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl border-2 border-blue-200 p-8">
        <div className="text-center">
          <div className="relative w-12 h-12 mx-auto mb-4">
            <div className="absolute top-0 left-0 w-full h-full border-4 border-blue-200 rounded-full animate-ping"></div>
            <div className="absolute top-0 left-0 w-full h-full border-4 border-blue-600 rounded-full animate-spin border-t-transparent"></div>
          </div>
          <p className="text-gray-700 font-medium">Generating comprehensive evaluation...</p>
          <p className="text-sm text-gray-500 mt-2">Calculating metrics, feature importance, and error patterns</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-yellow-50 rounded-xl border-2 border-yellow-200 p-6">
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-6 h-6 text-yellow-600 flex-shrink-0 mt-1" />
          <div className="flex-1">
            <h4 className="font-semibold text-yellow-900 mb-2">Evaluation In Progress</h4>
            <p className="text-sm text-yellow-800 mb-3">{error}</p>
            <p className="text-xs text-yellow-700">
              The model has been trained successfully. Evaluation data will be available shortly.
              <br/>
              You can view it later from the Model Evaluation page.
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (!evaluationData) return null;

  return (
    <div className="space-y-6">
      {/* MEEA Header Banner */}
      <div 
        className="rounded-xl shadow-lg overflow-hidden"
        style={{
          background: `linear-gradient(135deg, ${evaluationData.model.color}dd, ${evaluationData.model.color})`
        }}
      >
        <div className="p-6 text-white">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <Target className="w-6 h-6" />
                <h3 className="text-2xl font-bold">Model Evaluation (MEEA)</h3>
              </div>
              <p className="text-sm opacity-90">
                Comprehensive evaluation and error analysis for {evaluationData.model.name}
              </p>
            </div>
            <div className="text-right">
              {evaluationData.performance_metrics.accuracy && (
                <>
                  <div className="text-4xl font-bold">
                    {(evaluationData.performance_metrics.accuracy * 100).toFixed(1)}%
                  </div>
                  <div className="text-sm opacity-90">Overall Accuracy</div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Quick View Tabs */}
      <div className="bg-white rounded-xl shadow-md p-2">
        <nav className="flex gap-2">
          <button
            onClick={() => setActiveView('overview')}
            className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium transition-all ${
              activeView === 'overview'
                ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white shadow-lg'
                : 'text-gray-600 hover:bg-gray-100'
            }`}
          >
            <TrendingUp className="w-5 h-5" />
            <span>Performance</span>
          </button>
          <button
            onClick={() => setActiveView('features')}
            className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium transition-all ${
              activeView === 'features'
                ? 'bg-gradient-to-r from-purple-500 to-purple-600 text-white shadow-lg'
                : 'text-gray-600 hover:bg-gray-100'
            }`}
          >
            <Target className="w-5 h-5" />
            <span>Features</span>
          </button>
          <button
            onClick={() => setActiveView('errors')}
            className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium transition-all ${
              activeView === 'errors'
                ? 'bg-gradient-to-r from-red-500 to-red-600 text-white shadow-lg'
                : 'text-gray-600 hover:bg-gray-100'
            }`}
          >
            <AlertTriangle className="w-5 h-5" />
            <span>Errors</span>
          </button>
        </nav>
      </div>

      {/* Content Area */}
      <div className="space-y-6">
        {activeView === 'overview' && (
          <>
            <PerformanceMetricsCard 
              metrics={evaluationData.performance_metrics}
              taskType={evaluationData.model.task_type}
            />
            
            {evaluationData.performance_metrics.confusion_matrix && (
              <ConfusionMatrixChart 
                matrix={evaluationData.performance_metrics.confusion_matrix}
              />
            )}

            {evaluationData.explainability_data?.find(d => d.data_type === 'roc_curve') && (
              <ROCCurveChart 
                rocData={evaluationData.explainability_data.find(d => d.data_type === 'roc_curve')!.values}
              />
            )}
          </>
        )}

        {activeView === 'features' && (
          <>
            <FeatureImportanceChart 
              features={evaluationData.feature_importance}
              topN={15}
            />
            
            {evaluationData.granular_accuracy && evaluationData.granular_accuracy.length > 0 && (
              <div className="bg-white rounded-xl shadow-md p-6">
                <h4 className="text-lg font-semibold text-gray-900 mb-4">Granular Accuracy by Segments</h4>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="py-2 px-4 text-left font-semibold text-gray-700">Variable</th>
                        <th className="py-2 px-4 text-left font-semibold text-gray-700">Segment</th>
                        <th className="py-2 px-4 text-center font-semibold text-gray-700">Accuracy</th>
                        <th className="py-2 px-4 text-center font-semibold text-gray-700">Samples</th>
                      </tr>
                    </thead>
                    <tbody>
                      {evaluationData.granular_accuracy.slice(0, 8).map((item, idx) => (
                        <tr key={idx} className={idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                          <td className="py-2 px-4 font-medium text-gray-900">{item.variable}</td>
                          <td className="py-2 px-4 text-gray-700">{item.segment}</td>
                          <td className="py-2 px-4 text-center font-semibold text-gray-900">
                            {(item.accuracy * 100).toFixed(1)}%
                          </td>
                          <td className="py-2 px-4 text-center text-gray-600">{item.sample_count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}

        {activeView === 'errors' && (
          <>
            {evaluationData.error_patterns && evaluationData.error_patterns.length > 0 && (
              <div className="bg-white rounded-xl shadow-md p-6">
                <h4 className="text-lg font-semibold text-gray-900 mb-4">Error Pattern Analysis</h4>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {evaluationData.error_patterns.map((pattern, idx) => (
                    <div key={idx} className="bg-gradient-to-br from-red-50 to-orange-50 rounded-lg p-4 border-2 border-red-200">
                      <div className="text-xs font-semibold text-red-700 uppercase tracking-wide mb-1">
                        {pattern.error_type.replace(/_/g, ' ')}
                      </div>
                      <div className="text-3xl font-bold text-red-900 mb-1">{pattern.count}</div>
                      <div className="text-sm text-gray-600">
                        {pattern.percentage.toFixed(1)}% of predictions
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {evaluationData.prediction_confidence && evaluationData.prediction_confidence.length > 0 && (
              <div className="bg-white rounded-xl shadow-md p-6">
                <h4 className="text-lg font-semibold text-gray-900 mb-4">Prediction Confidence</h4>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="py-2 px-4 text-left font-semibold text-gray-700">Range</th>
                        <th className="py-2 px-4 text-center font-semibold text-gray-700">Count</th>
                        <th className="py-2 px-4 text-center font-semibold text-gray-700">Accuracy</th>
                      </tr>
                    </thead>
                    <tbody>
                      {evaluationData.prediction_confidence.map((conf, idx) => (
                        <tr key={idx} className="border-b border-gray-200">
                          <td className="py-2 px-4 font-medium text-gray-900">
                            {conf.bin_start.toFixed(2)} - {conf.bin_end.toFixed(2)}
                          </td>
                          <td className="py-2 px-4 text-center text-gray-700">{conf.count}</td>
                          <td className="py-2 px-4 text-center">
                            <span className={`font-semibold ${conf.accuracy > 0.8 ? 'text-green-600' : conf.accuracy > 0.6 ? 'text-yellow-600' : 'text-red-600'}`}>
                              {(conf.accuracy * 100).toFixed(1)}%
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* View Full Evaluation Button */}
      <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl border-2 border-blue-200 p-6">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="font-semibold text-blue-900 mb-1">Want to see more details?</h4>
            <p className="text-sm text-blue-700">
              View the complete MEEA evaluation with all tabs, charts, and advanced analysis.
            </p>
          </div>
          <button
            onClick={() => navigate(`/model-evaluation?model_id=${modelId}`)}
            className="px-6 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-lg font-medium hover:shadow-lg transition-all flex items-center gap-2"
          >
            <Lightbulb className="w-5 h-5" />
            <span>View Full MEEA Evaluation</span>
            <ExternalLink className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default MEEAEvaluationInline;
