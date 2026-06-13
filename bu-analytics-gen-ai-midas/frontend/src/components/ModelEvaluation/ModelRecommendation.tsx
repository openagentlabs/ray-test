/**
 * Model Recommendation and Category Leaders Component
 */

import React from 'react';
import { Award, TrendingUp, Target, Shield, Bookmark } from 'lucide-react';
import { formatAsDecimal, formatTrainTestPair } from '../../utils/displayMissingValue';

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
  parameters?: string;
}

interface ModelRecommendationProps {
  models: ModelMetrics[];
  recommendedModelId?: string;
  recommendationReason?: string;
}

export const ModelRecommendation: React.FC<ModelRecommendationProps> = ({
  models,
  recommendedModelId,
  recommendationReason
}) => {
  if (!models || models.length === 0) {
    return null;
  }

  // Find best model for each metric
  const findBestModel = (metric: keyof ModelMetrics, higherIsBetter: boolean = true): ModelMetrics | null => {
    if (models.length === 0) return null;
    
    let bestModel = models[0];
    let bestValue = bestModel[metric] as number;
    
    for (const model of models) {
      const value = model[metric] as number;
      if (value === undefined || value === null) continue;
      
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
    
    return bestModel;
  };

  const bestAucRoc = findBestModel('aucRoc');
  const bestF1 = findBestModel('f1Score');
  const bestPrecision = findBestModel('precision');
  const bestRecall = findBestModel('recall');

  // Determine recommended model (use provided or find best overall)
  const recommendedModel = recommendedModelId 
    ? models.find(m => m.modelId === recommendedModelId) || bestAucRoc
    : bestAucRoc;

  const formatMetricTrainTest = (
    trainValue: number | string | undefined | null,
    testValue: number | string | undefined | null
  ): string => formatTrainTestPair(trainValue, testValue, (value) => formatAsDecimal(value, 4));

  return (
    <div className="space-y-6">
      {/* Model Comparison Summary - Recommended Model */}
      {recommendedModel && (
        <div className="bg-white rounded-2xl shadow-xl p-8 border-2 border-gray-100">
          <div className="mb-4">
            <h3 className="text-xl font-bold text-gray-900 mb-2">Model Comparison Summary</h3>
            <p className="text-sm text-gray-600">Executive summary with recommended model for deployment</p>
          </div>

          <div 
            className="rounded-xl p-6 border-2 shadow-lg relative overflow-hidden"
            style={{ 
              backgroundColor: `${recommendedModel.color}15`,
              borderColor: recommendedModel.color
            }}
          >
            <div className="absolute top-0 right-0 bg-red-500 text-white px-4 py-1 rounded-bl-lg text-xs font-bold flex items-center gap-1">
              <Bookmark className="w-3 h-3" />
              RECOMMENDED
            </div>

            <div className="flex items-start justify-between mt-2">
              <div className="flex-1">
                <h4 
                  className="text-2xl font-bold mb-2 flex items-center gap-2"
                  style={{ color: recommendedModel.color }}
                >
                  {recommendedModel.modelName}
                </h4>
                {recommendedModel.parameters && (
                  <p className="text-sm text-gray-600 mb-4">{recommendedModel.parameters}</p>
                )}
                
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
                  <div className="bg-white/50 dark:bg-slate-900/70 rounded-lg p-3 border border-gray-200 dark:border-slate-700">
                    <div className="text-xs text-gray-600 dark:text-gray-300 mb-1">AUC-ROC (train / test)</div>
                    <div className="text-xl font-bold text-gray-900 dark:text-white">
                      {formatMetricTrainTest(recommendedModel.trainAucRoc, recommendedModel.testAucRoc)}
                    </div>
                  </div>
                  <div className="bg-white/50 dark:bg-slate-900/70 rounded-lg p-3 border border-gray-200 dark:border-slate-700">
                    <div className="text-xs text-gray-600 dark:text-gray-300 mb-1">F1 Score (train / test)</div>
                    <div className="text-xl font-bold text-gray-900 dark:text-white">
                      {formatMetricTrainTest(recommendedModel.trainF1Score, recommendedModel.testF1Score)}
                    </div>
                  </div>
                  <div className="bg-white/50 dark:bg-slate-900/70 rounded-lg p-3 border border-gray-200 dark:border-slate-700">
                    <div className="text-xs text-gray-600 dark:text-gray-300 mb-1">Precision (train / test)</div>
                    <div className="text-xl font-bold text-gray-900 dark:text-white">
                      {formatMetricTrainTest(recommendedModel.trainPrecision, recommendedModel.testPrecision)}
                    </div>
                  </div>
                  <div className="bg-white/50 dark:bg-slate-900/70 rounded-lg p-3 border border-gray-200 dark:border-slate-700">
                    <div className="text-xs text-gray-600 dark:text-gray-300 mb-1">Recall (train / test)</div>
                    <div className="text-xl font-bold text-gray-900 dark:text-white">
                      {formatMetricTrainTest(recommendedModel.trainRecall, recommendedModel.testRecall)}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {recommendationReason && (
              <div className="mt-4 p-3 bg-blue-50 dark:bg-slate-900/70 rounded-lg border border-blue-200 dark:border-slate-700">
                <p className="text-sm text-gray-700 dark:text-gray-200">{recommendationReason}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Category Leaders */}
      <div className="bg-white rounded-2xl shadow-xl p-8 border-2 border-gray-100">
        <div className="mb-4">
          <h3 className="text-xl font-bold text-gray-900 mb-2">Category Leaders</h3>
          <p className="text-sm text-gray-600">Best performing model for individual metrics</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {bestAucRoc && (
            <div className="bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-slate-900 dark:to-slate-800 rounded-xl p-4 border-2 border-blue-200 dark:border-slate-700">
              <div className="flex items-center gap-2 mb-2">
                <TrendingUp className="w-5 h-5 text-blue-600" />
                <span className="text-sm font-semibold text-gray-700 dark:text-gray-200">Best AUC-ROC (train / test)</span>
              </div>
              <div className="text-lg font-bold text-gray-900 dark:text-white mb-1">{bestAucRoc.modelName}</div>
              <div className="text-2xl font-bold text-blue-600">
                {formatMetricTrainTest(bestAucRoc.trainAucRoc, bestAucRoc.testAucRoc)}
              </div>
            </div>
          )}

          {bestF1 && (
            <div className="bg-gradient-to-br from-green-50 to-emerald-50 dark:from-slate-900 dark:to-slate-800 rounded-xl p-4 border-2 border-green-200 dark:border-slate-700">
              <div className="flex items-center gap-2 mb-2">
                <Target className="w-5 h-5 text-green-600" />
                <span className="text-sm font-semibold text-gray-700 dark:text-gray-200">Best F1 Score (train / test)</span>
              </div>
              <div className="text-lg font-bold text-gray-900 dark:text-white mb-1">{bestF1.modelName}</div>
              <div className="text-2xl font-bold text-green-600">
                {formatMetricTrainTest(bestF1.trainF1Score, bestF1.testF1Score)}
              </div>
            </div>
          )}

          {bestPrecision && (
            <div className="bg-gradient-to-br from-purple-50 to-pink-50 dark:from-slate-900 dark:to-slate-800 rounded-xl p-4 border-2 border-purple-200 dark:border-slate-700">
              <div className="flex items-center gap-2 mb-2">
                <Shield className="w-5 h-5 text-purple-600" />
                <span className="text-sm font-semibold text-gray-700 dark:text-gray-200">Best Precision (train / test)</span>
              </div>
              <div className="text-lg font-bold text-gray-900 dark:text-white mb-1">{bestPrecision.modelName}</div>
              <div className="text-2xl font-bold text-purple-600">
                {formatMetricTrainTest(bestPrecision.trainPrecision, bestPrecision.testPrecision)}
              </div>
            </div>
          )}

          {bestRecall && (
            <div className="bg-gradient-to-br from-orange-50 to-amber-50 dark:from-slate-900 dark:to-slate-800 rounded-xl p-4 border-2 border-orange-200 dark:border-slate-700">
              <div className="flex items-center gap-2 mb-2">
                <Target className="w-5 h-5 text-orange-600" />
                <span className="text-sm font-semibold text-gray-700 dark:text-gray-200">Best Recall (train / test)</span>
              </div>
              <div className="text-lg font-bold text-gray-900 dark:text-white mb-1">{bestRecall.modelName}</div>
              <div className="text-2xl font-bold text-orange-600">
                {formatMetricTrainTest(bestRecall.trainRecall, bestRecall.testRecall)}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ModelRecommendation;














