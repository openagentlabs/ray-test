/**
 * Performance Metrics Comparison Table - Side-by-side comparison of all models
 */

import React from 'react';
import { TrendingUp, Award, Target, BarChart3 } from 'lucide-react';
import { formatAsPercent, formatAsDecimal, formatTrainTestPair, parseNumericValue } from '../../utils/displayMissingValue';

interface ModelMetrics {
  modelName: string;
  modelId: string;
  // Primary (typically TEST) metrics
  accuracy: number;
  precision: number;
  recall: number;
  f1Score: number;
  aucRoc: number;
  aucPr?: number;
  logLoss?: number;

  // Optional train/test split metrics for display as "train / test"
  trainAccuracy?: number;
  testAccuracy?: number;
  trainPrecision?: number;
  testPrecision?: number;
  trainRecall?: number;
  testRecall?: number;
  trainF1Score?: number;
  testF1Score?: number;
  trainAucRoc?: number;
  testAucRoc?: number;
  trainAucPr?: number;
  testAucPr?: number;
  trainLogLoss?: number;
  testLogLoss?: number;

  color: string;
}

interface PerformanceMetricsComparisonProps {
  models: ModelMetrics[];
  title?: string;
}

export const PerformanceMetricsComparison: React.FC<PerformanceMetricsComparisonProps> = ({
  models,
  title = 'Performance Metrics Comparison'
}) => {
  if (!models || models.length === 0) {
    return (
      <div className="bg-white rounded-2xl shadow-xl p-8 border-2 border-gray-100">
        <div className="text-center text-gray-500 py-12">
          <p className="text-lg font-medium">No performance metrics available for comparison</p>
        </div>
      </div>
    );
  }

  // Find best model for each metric
  const findBestModel = (metric: keyof ModelMetrics, higherIsBetter: boolean = true): string | null => {
    if (models.length === 0) return null;
    
    let bestModel: ModelMetrics | null = null;
    let bestValue: number | null = null;
    
    for (const model of models) {
      const value = model[metric] as number;
      if (value === undefined || value === null) continue;
      
      if (bestValue === null) {
        bestValue = value;
        bestModel = model;
        continue;
      }
      
      if (higherIsBetter) {
        if (value > bestValue) {
          bestValue = value;
          bestModel = model;
        }
      } else {
        if (value < bestValue) {
          bestValue = value;
          bestModel = model;
        }
      }
    }
    
    return bestModel ? bestModel.modelId : null;
  };

  const bestAccuracy = findBestModel('accuracy');
  const bestPrecision = findBestModel('precision');
  const bestRecall = findBestModel('recall');
  const bestF1 = findBestModel('f1Score');
  const bestAucRoc = findBestModel('aucRoc');
  const bestAucPr = findBestModel('aucPr');
  const bestLogLoss = findBestModel('logLoss', false);

  const isBest = (modelId: string, bestId: string | null): boolean => {
    return bestId === modelId;
  };

  const metrics = [
    {
      label: 'Accuracy (train / test)',
      key: 'accuracy' as keyof ModelMetrics,
      trainKey: 'trainAccuracy' as keyof ModelMetrics,
      testKey: 'testAccuracy' as keyof ModelMetrics,
      formatter: (value: number | string | undefined | null) => formatAsPercent(value),
      best: bestAccuracy,
      icon: Target
    },
    {
      label: 'Precision (train / test)',
      key: 'precision' as keyof ModelMetrics,
      trainKey: 'trainPrecision' as keyof ModelMetrics,
      testKey: 'testPrecision' as keyof ModelMetrics,
      formatter: (value: number | string | undefined | null) => formatAsPercent(value),
      best: bestPrecision,
      icon: TrendingUp
    },
    {
      label: 'Recall (train / test)',
      key: 'recall' as keyof ModelMetrics,
      trainKey: 'trainRecall' as keyof ModelMetrics,
      testKey: 'testRecall' as keyof ModelMetrics,
      formatter: (value: number | string | undefined | null) => formatAsPercent(value),
      best: bestRecall,
      icon: Target
    },
    {
      label: 'F1 Score (train / test)',
      key: 'f1Score' as keyof ModelMetrics,
      trainKey: 'trainF1Score' as keyof ModelMetrics,
      testKey: 'testF1Score' as keyof ModelMetrics,
      formatter: (value: number | string | undefined | null) => formatAsDecimal(value),
      best: bestF1,
      icon: Award
    },
    {
      label: 'AUC-ROC (train / test)',
      key: 'aucRoc' as keyof ModelMetrics,
      trainKey: 'trainAucRoc' as keyof ModelMetrics,
      testKey: 'testAucRoc' as keyof ModelMetrics,
      formatter: (value: number | string | undefined | null) => formatAsDecimal(value),
      best: bestAucRoc,
      icon: BarChart3
    },
    {
      label: 'AUC-PR (train / test)',
      key: 'aucPr' as keyof ModelMetrics,
      trainKey: 'trainAucPr' as keyof ModelMetrics,
      testKey: 'testAucPr' as keyof ModelMetrics,
      formatter: (value: number | string | undefined | null) => formatAsDecimal(value),
      best: bestAucPr,
      icon: BarChart3
    },
    {
      label: 'Log Loss (train / test)',
      key: 'logLoss' as keyof ModelMetrics,
      trainKey: 'trainLogLoss' as keyof ModelMetrics,
      testKey: 'testLogLoss' as keyof ModelMetrics,
      formatter: (value: number | string | undefined | null) => formatAsDecimal(value, 4),
      best: bestLogLoss,
      icon: BarChart3,
      lowerIsBetter: true
    },
  ];

  return (
    <div className="bg-white rounded-2xl shadow-xl p-8 border-2 border-gray-100 dark:border-gray-800 dark:bg-gray-900">
      <div className="mb-6">
        <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">{title}</h3>
        <p className="text-sm text-gray-600 dark:text-gray-300">
          Side-by-side comparison of key performance indicators across all models
        </p>
      </div>

      <div className="overflow-x-auto rounded-xl border-2 border-gray-200 dark:border-gray-800" style={{ maxWidth: '100%' }}>
        <table className="w-full" style={{ minWidth: '600px' }}>
          <thead className="bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-slate-900 dark:to-slate-800">
            <tr>
              <th className="text-left py-4 px-6 text-sm font-bold text-gray-700 dark:text-gray-200 uppercase tracking-wide border-b-2 border-gray-300 dark:border-slate-700">
                METRIC
              </th>
              {models.map((model) => (
                <th 
                  key={model.modelId}
                  className="text-center py-4 px-6 text-sm font-bold text-gray-700 dark:text-gray-200 uppercase tracking-wide border-b-2 border-gray-300 dark:border-slate-700"
                >
                  {model.modelName.toUpperCase()}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-slate-800">
            {metrics.map((metric, idx) => {
              const Icon = metric.icon;
              return (
                <tr 
                  key={metric.key}
                  className={`hover:bg-gray-50 dark:hover:bg-slate-800 transition-colors ${idx % 2 === 0 ? 'bg-white dark:bg-slate-950' : 'bg-gray-50/50 dark:bg-slate-900/60'}`}
                >
                  <td className="py-4 px-6 font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                    <Icon className="w-4 h-4 text-gray-600 dark:text-gray-300" />
                    {metric.label}
                  </td>
                  {models.map((model) => {
                    const value = model[metric.key] as number | string | undefined | null;
                    const numericValue = parseNumericValue(value);
                    const isBestValue = isBest(model.modelId, metric.best);
                    const hasValue = numericValue !== undefined;

                    const trainVal = (metric as any).trainKey
                      ? (model[(metric as any).trainKey as keyof ModelMetrics] as number | string | undefined | null)
                      : undefined;
                    const testVal = (metric as any).testKey
                      ? (model[(metric as any).testKey as keyof ModelMetrics] as number | string | undefined | null)
                      : value;

                    const displayValue =
                      (metric as any).trainKey
                        ? formatTrainTestPair(
                            trainVal,
                            testVal,
                            (numericValue) => metric.formatter(numericValue)
                          )
                        : metric.formatter(value);
                    
                    return (
                      <td 
                        key={model.modelId}
                        className={`py-4 px-6 text-center font-semibold ${
                          isBestValue && hasValue
                            ? 'bg-green-50 text-green-700 border-2 border-green-300 dark:bg-emerald-900/30 dark:text-emerald-200 dark:border-emerald-700'
                            : 'text-gray-700 dark:text-gray-200'
                        }`}
                      >
                        <div className="flex items-center justify-center gap-2">
                          <span>{displayValue}</span>
                          {isBestValue && hasValue && (
                            <span className="text-xs font-bold text-green-600 bg-green-100 px-2 py-1 rounded">
                              Best
                            </span>
                          )}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="mt-4 text-sm text-gray-600 dark:text-gray-300 italic">
        <p>
          <strong>Note:</strong> Metrics are shown as <code>train / test</code> where both values are available. Best performing
          values are highlighted in bold and labeled. Lower is better for Log Loss; higher is better for all other metrics.
        </p>
      </div>
    </div>
  );
};

export default PerformanceMetricsComparison;

