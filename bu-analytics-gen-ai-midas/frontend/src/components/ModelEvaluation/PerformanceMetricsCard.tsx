/**
 * Performance Metrics Summary Card Component - Enhanced MEEA Style
 */

import React from 'react';
import { TrendingUp, Target, Zap, BarChart3, CheckCircle2, AlertCircle } from 'lucide-react';
import { PerformanceMetrics } from '../../types/modelEvaluation';

interface PerformanceMetricsCardProps {
  metrics: PerformanceMetrics;
  taskType: 'classification' | 'regression';
}

export const PerformanceMetricsCard: React.FC<PerformanceMetricsCardProps> = ({
  metrics,
  taskType
}) => {
  if (!metrics) {
    return (
      <div className="bg-gray-50 rounded-xl p-8 text-center border-2 border-dashed border-gray-300">
        <AlertCircle className="w-12 h-12 text-gray-400 mx-auto mb-4" />
        <p className="text-gray-500 font-medium">No metrics available</p>
      </div>
    );
  }

  const getMetricColor = (value: number | undefined, threshold = 0.8): string => {
    if (value === undefined || value === null) return 'text-gray-500';
    if (value >= threshold) return 'text-green-600';
    if (value >= threshold - 0.2) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getMetricBgColor = (value: number | undefined, threshold = 0.8): string => {
    if (value === undefined || value === null) return 'bg-gray-50 border-gray-200';
    if (value >= threshold) return 'bg-green-50 border-green-200';
    if (value >= threshold - 0.2) return 'bg-yellow-50 border-yellow-200';
    return 'bg-red-50 border-red-200';
  };

  const formatValue = (value: number | undefined): string => {
    if (value === undefined || value === null) return 'N/A';
    return value.toFixed(3);
  };

  const formatPercent = (value: number | undefined): string => {
    if (value === undefined || value === null) return 'N/A';
    return `${(value * 100).toFixed(1)}%`;
  };

  return (
    <div className="space-y-6">
      {taskType === 'classification' ? (
        <>
          {/* Classification Metrics - Enhanced Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            <div className={`p-6 rounded-xl border-2 transition-all hover:shadow-lg ${getMetricBgColor(metrics.accuracy)}`}>
              <div className="flex items-center justify-between mb-3">
                <div className="text-sm font-bold text-gray-700 uppercase tracking-wide">Accuracy</div>
                <Target className={`w-5 h-5 ${getMetricColor(metrics.accuracy)}`} />
              </div>
              <div className={`text-4xl font-bold mb-2 ${getMetricColor(metrics.accuracy)}`}>
                {formatPercent(metrics.accuracy)}
              </div>
              <div className="text-xs text-gray-600 font-medium">Value: {formatValue(metrics.accuracy)}</div>
            </div>
            
            <div className={`p-6 rounded-xl border-2 transition-all hover:shadow-lg ${getMetricBgColor(metrics.precision)}`}>
              <div className="flex items-center justify-between mb-3">
                <div className="text-sm font-bold text-gray-700 uppercase tracking-wide">Precision</div>
                <TrendingUp className={`w-5 h-5 ${getMetricColor(metrics.precision)}`} />
              </div>
              <div className={`text-4xl font-bold mb-2 ${getMetricColor(metrics.precision)}`}>
                {formatPercent(metrics.precision)}
              </div>
              <div className="text-xs text-gray-600 font-medium">Value: {formatValue(metrics.precision)}</div>
            </div>
            
            <div className={`p-6 rounded-xl border-2 transition-all hover:shadow-lg ${getMetricBgColor(metrics.recall)}`}>
              <div className="flex items-center justify-between mb-3">
                <div className="text-sm font-bold text-gray-700 uppercase tracking-wide">Recall</div>
                <CheckCircle2 className={`w-5 h-5 ${getMetricColor(metrics.recall)}`} />
              </div>
              <div className={`text-4xl font-bold mb-2 ${getMetricColor(metrics.recall)}`}>
                {formatPercent(metrics.recall)}
              </div>
              <div className="text-xs text-gray-600 font-medium">Value: {formatValue(metrics.recall)}</div>
            </div>
            
            <div className={`p-6 rounded-xl border-2 transition-all hover:shadow-lg ${getMetricBgColor(metrics.f1_score)}`}>
              <div className="flex items-center justify-between mb-3">
                <div className="text-sm font-bold text-gray-700 uppercase tracking-wide">F1 Score</div>
                <Zap className={`w-5 h-5 ${getMetricColor(metrics.f1_score)}`} />
              </div>
              <div className={`text-4xl font-bold mb-2 ${getMetricColor(metrics.f1_score)}`}>
                {formatPercent(metrics.f1_score)}
              </div>
              <div className="text-xs text-gray-600 font-medium">Value: {formatValue(metrics.f1_score)}</div>
            </div>
          </div>

          {/* Additional Metrics - Enhanced */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {metrics.auc_roc !== undefined && metrics.auc_roc !== null && (
              <div className={`p-5 rounded-xl border-2 transition-all hover:shadow-lg ${getMetricBgColor(metrics.auc_roc)}`}>
                <div className="flex items-center justify-between mb-3">
                  <div className="text-sm font-bold text-gray-700 uppercase tracking-wide">AUC-ROC</div>
                  <BarChart3 className={`w-5 h-5 ${getMetricColor(metrics.auc_roc)}`} />
                </div>
                <div className={`text-3xl font-bold mb-1 ${getMetricColor(metrics.auc_roc)}`}>
                  {formatValue(metrics.auc_roc)}
                </div>
                <div className="text-xs text-gray-600">Area Under ROC Curve</div>
              </div>
            )}
            
            {metrics.auc_pr !== undefined && metrics.auc_pr !== null && (
              <div className={`p-5 rounded-xl border-2 transition-all hover:shadow-lg ${getMetricBgColor(metrics.auc_pr)}`}>
                <div className="flex items-center justify-between mb-3">
                  <div className="text-sm font-bold text-gray-700 uppercase tracking-wide">AUC-PR</div>
                  <BarChart3 className={`w-5 h-5 ${getMetricColor(metrics.auc_pr)}`} />
                </div>
                <div className={`text-3xl font-bold mb-1 ${getMetricColor(metrics.auc_pr)}`}>
                  {formatValue(metrics.auc_pr)}
                </div>
                <div className="text-xs text-gray-600">Area Under PR Curve</div>
              </div>
            )}
            
            {metrics.log_loss !== undefined && metrics.log_loss !== null && (
              <div className="p-5 rounded-xl border-2 border-gray-200 bg-gray-50 transition-all hover:shadow-lg">
                <div className="flex items-center justify-between mb-3">
                  <div className="text-sm font-bold text-gray-700 uppercase tracking-wide">Log Loss</div>
                  <AlertCircle className="w-5 h-5 text-gray-600" />
                </div>
                <div className="text-3xl font-bold mb-1 text-gray-700">
                  {formatValue(metrics.log_loss)}
                </div>
                <div className="text-xs text-gray-600">Lower is better</div>
              </div>
            )}
          </div>

          {/* Class-specific metrics - Enhanced */}
          {metrics.class_metrics && Object.keys(metrics.class_metrics).length > 0 && (
            <div className="mt-8">
              <div className="flex items-center gap-3 mb-4">
                <BarChart3 className="w-6 h-6 text-indigo-600" />
                <h4 className="text-xl font-bold text-gray-900">Class-Specific Metrics</h4>
              </div>
              <div className="overflow-x-auto rounded-xl border-2 border-gray-200 shadow-lg">
                <table className="w-full">
                  <thead className="bg-gradient-to-r from-indigo-50 to-purple-50">
                    <tr>
                      <th className="border-b-2 border-gray-200 p-4 text-left text-sm font-bold text-gray-700 uppercase tracking-wide">Class</th>
                      <th className="border-b-2 border-gray-200 p-4 text-center text-sm font-bold text-gray-700 uppercase tracking-wide">Precision</th>
                      <th className="border-b-2 border-gray-200 p-4 text-center text-sm font-bold text-gray-700 uppercase tracking-wide">Recall</th>
                      <th className="border-b-2 border-gray-200 p-4 text-center text-sm font-bold text-gray-700 uppercase tracking-wide">F1 Score</th>
                      <th className="border-b-2 border-gray-200 p-4 text-center text-sm font-bold text-gray-700 uppercase tracking-wide">Support</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {Object.entries(metrics.class_metrics).map(([className, classMetric], idx) => (
                      <tr key={className} className={`hover:bg-gray-50 transition-colors ${idx % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'}`}>
                        <td className="p-4 font-bold text-gray-900">{className}</td>
                        <td className="p-4 text-center font-semibold text-gray-700">{classMetric.precision.toFixed(3)}</td>
                        <td className="p-4 text-center font-semibold text-gray-700">{classMetric.recall.toFixed(3)}</td>
                        <td className="p-4 text-center font-semibold text-gray-700">{classMetric.f1_score.toFixed(3)}</td>
                        <td className="p-4 text-center font-semibold text-gray-600">{classMetric.support}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      ) : (
        <>
          {/* Regression Metrics - Enhanced */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
            {metrics.r2 !== undefined && (
              <div className={`p-6 rounded-xl border-2 transition-all hover:shadow-lg ${getMetricBgColor(metrics.r2)}`}>
                <div className="flex items-center justify-between mb-3">
                  <div className="text-sm font-bold text-gray-700 uppercase tracking-wide">R² Score</div>
                  <BarChart3 className={`w-5 h-5 ${getMetricColor(metrics.r2)}`} />
                </div>
                <div className={`text-4xl font-bold mb-2 ${getMetricColor(metrics.r2)}`}>
                  {formatValue(metrics.r2)}
                </div>
                <div className="text-xs text-gray-600 font-medium">Coefficient of Determination</div>
              </div>
            )}
            
            {metrics.mse !== undefined && (
              <div className="p-6 rounded-xl border-2 border-gray-200 bg-gray-50 transition-all hover:shadow-lg">
                <div className="flex items-center justify-between mb-3">
                  <div className="text-sm font-bold text-gray-700 uppercase tracking-wide">MSE</div>
                  <AlertCircle className="w-5 h-5 text-gray-600" />
                </div>
                <div className="text-4xl font-bold mb-2 text-gray-700">
                  {formatValue(metrics.mse)}
                </div>
                <div className="text-xs text-gray-600 font-medium">Lower is better</div>
              </div>
            )}
            
            {metrics.rmse !== undefined && (
              <div className="p-6 rounded-xl border-2 border-gray-200 bg-gray-50 transition-all hover:shadow-lg">
                <div className="flex items-center justify-between mb-3">
                  <div className="text-sm font-bold text-gray-700 uppercase tracking-wide">RMSE</div>
                  <AlertCircle className="w-5 h-5 text-gray-600" />
                </div>
                <div className="text-4xl font-bold mb-2 text-gray-700">
                  {formatValue(metrics.rmse)}
                </div>
                <div className="text-xs text-gray-600 font-medium">Lower is better</div>
              </div>
            )}
            
            {metrics.mae !== undefined && (
              <div className="p-6 rounded-xl border-2 border-gray-200 bg-gray-50 transition-all hover:shadow-lg">
                <div className="flex items-center justify-between mb-3">
                  <div className="text-sm font-bold text-gray-700 uppercase tracking-wide">MAE</div>
                  <AlertCircle className="w-5 h-5 text-gray-600" />
                </div>
                <div className="text-4xl font-bold mb-2 text-gray-700">
                  {formatValue(metrics.mae)}
                </div>
                <div className="text-xs text-gray-600 font-medium">Lower is better</div>
              </div>
            )}
            
            {metrics.mape !== undefined && (
              <div className="p-6 rounded-xl border-2 border-gray-200 bg-gray-50 transition-all hover:shadow-lg">
                <div className="flex items-center justify-between mb-3">
                  <div className="text-sm font-bold text-gray-700 uppercase tracking-wide">MAPE (%)</div>
                  <AlertCircle className="w-5 h-5 text-gray-600" />
                </div>
                <div className="text-4xl font-bold mb-2 text-gray-700">
                  {metrics.mape.toFixed(1)}%
                </div>
                <div className="text-xs text-gray-600 font-medium">Lower is better</div>
              </div>
            )}
            
            {metrics.max_error !== undefined && (
              <div className="p-6 rounded-xl border-2 border-gray-200 bg-gray-50 transition-all hover:shadow-lg">
                <div className="flex items-center justify-between mb-3">
                  <div className="text-sm font-bold text-gray-700 uppercase tracking-wide">Max Error</div>
                  <AlertCircle className="w-5 h-5 text-gray-600" />
                </div>
                <div className="text-4xl font-bold mb-2 text-gray-700">
                  {formatValue(metrics.max_error)}
                </div>
                <div className="text-xs text-gray-600 font-medium">Maximum prediction error</div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};

export default PerformanceMetricsCard;
