/**
 * Confusion Matrix Comparison - Multiple Models Side by Side
 */

import React from 'react';
import { useTheme } from '../../contexts/ThemeContext';
import { formatTrainTestPair } from '../../utils/displayMissingValue';

interface ModelConfusionMatrix {
  modelName: string;
  modelId: string;
  // Primary (typically TEST) confusion matrix
  matrix: number[][];
  accuracy: number;
  f1Score: number;
  // Optional TRAIN confusion matrix for displaying train / test side by side
  trainMatrix?: number[][];
  trainAccuracy?: number;
  trainF1Score?: number;
  color: string;
}

interface ConfusionMatrixComparisonProps {
  models: ModelConfusionMatrix[];
  title?: string;
}

export const ConfusionMatrixComparison: React.FC<ConfusionMatrixComparisonProps> = ({
  models,
  title = 'Confusion Matrix Comparison'
}) => {
  const { isDark } = useTheme();
  if (!models || models.length === 0) {
    return (
      <div className="bg-white rounded-2xl shadow-xl p-8 border-2 border-gray-100">
        <div className="text-center text-gray-500 py-12">
          <p className="text-lg font-medium">No confusion matrix data available for comparison</p>
        </div>
      </div>
    );
  }

  const getColorIntensity = (value: number, maxValue: number): string => {
    const intensity = maxValue > 0 ? (value / maxValue) : 0;
    if (isDark) {
      if (intensity === 0) return 'bg-slate-800';
      if (intensity < 0.2) return 'bg-blue-900/60';
      if (intensity < 0.4) return 'bg-blue-800/70';
      if (intensity < 0.6) return 'bg-blue-700/80';
      if (intensity < 0.8) return 'bg-blue-600';
      return 'bg-blue-500';
    }
    if (intensity === 0) return 'bg-gray-100';
    if (intensity < 0.2) return 'bg-blue-100';
    if (intensity < 0.4) return 'bg-blue-200';
    if (intensity < 0.6) return 'bg-blue-300';
    if (intensity < 0.8) return 'bg-blue-400';
    return 'bg-blue-500';
  };

  const getTextColor = (value: number, maxValue: number): string => {
    if (isDark) return 'text-white';
    const intensity = maxValue > 0 ? (value / maxValue) : 0;
    return intensity > 0.5 ? 'text-white' : 'text-gray-900';
  };

  const renderConfusionMatrix = (model: ModelConfusionMatrix) => {
    // Determine if test data exists (check if test metrics are defined)
    const hasTestData = model.accuracy !== undefined || model.f1Score !== undefined;
    const hasTestMatrix = hasTestData && model.matrix && Array.isArray(model.matrix) && model.matrix.length > 0;
    const hasTrainMatrix = !!model.trainMatrix && model.trainMatrix.length > 0;
    
    // Use any available matrix for calculations (for binary classification detection, etc.)
    // Prefer train matrix, fallback to test matrix if train doesn't exist
    const matrix = model.trainMatrix || (hasTestMatrix ? model.matrix : []);
    const numClasses = matrix.length;
    const total = matrix.flat().reduce((sum, val) => sum + val, 0);
    const maxValue = Math.max(...matrix.flat());
    
    // For binary classification, extract TN, FP, FN, TP
    const isBinary = numClasses === 2;
    let tn = 0, fp = 0, fn = 0, tp = 0;
    
    if (isBinary) {
      tn = matrix[0][0];
      fp = matrix[0][1];
      fn = matrix[1][0];
      tp = matrix[1][1];
    }

    const renderSingleMatrix = (matrixToUse: number[][], label: string) => {
      const localNumClasses = matrixToUse.length;
      const localTotal = matrixToUse.flat().reduce((sum, val) => sum + val, 0);
      const localMax = Math.max(...matrixToUse.flat());
      const isBinaryLocal = localNumClasses === 2;

      let tnL = 0, fpL = 0, fnL = 0, tpL = 0;
      if (isBinaryLocal) {
        tnL = matrixToUse[0][0];
        fpL = matrixToUse[0][1];
        fnL = matrixToUse[1][0];
        tpL = matrixToUse[1][1];
      }

      return (
        <div className="space-y-2">
          <div className="text-xs sm:text-sm font-semibold text-gray-700 text-center mb-1">{label}</div>
          {isBinaryLocal ? (
            <div className="grid grid-cols-2 gap-2">
              <div className={`${getColorIntensity(tnL, localMax)} ${getTextColor(tnL, localMax)} px-2 py-2 rounded-lg text-center border-2`} style={{ borderColor: model.color }}>
                <div className="text-sm sm:text-base font-bold leading-tight whitespace-nowrap">{tnL}</div>
                <div className="text-[9px] sm:text-[10px] mt-1 opacity-75">{(localTotal > 0 ? (tnL / localTotal * 100).toFixed(1) : '0.0')}%</div>
                <div className="text-[9px] sm:text-[10px] mt-1 font-semibold">TN</div>
              </div>
              <div className={`${getColorIntensity(fpL, localMax)} ${getTextColor(fpL, localMax)} px-2 py-2 rounded-lg text-center border-2`} style={{ borderColor: model.color }}>
                <div className="text-sm sm:text-base font-bold leading-tight whitespace-nowrap">{fpL}</div>
                <div className="text-[9px] sm:text-[10px] mt-1 opacity-75">{(localTotal > 0 ? (fpL / localTotal * 100).toFixed(1) : '0.0')}%</div>
                <div className="text-[9px] sm:text-[10px] mt-1 font-semibold">FP</div>
              </div>
              <div className={`${getColorIntensity(fnL, localMax)} ${getTextColor(fnL, localMax)} px-2 py-2 rounded-lg text-center border-2`} style={{ borderColor: model.color }}>
                <div className="text-sm sm:text-base font-bold leading-tight whitespace-nowrap">{fnL}</div>
                <div className="text-[9px] sm:text-[10px] mt-1 opacity-75">{(localTotal > 0 ? (fnL / localTotal * 100).toFixed(1) : '0.0')}%</div>
                <div className="text-[9px] sm:text-[10px] mt-1 font-semibold">FN</div>
              </div>
              <div className={`${getColorIntensity(tpL, localMax)} ${getTextColor(tpL, localMax)} px-2 py-2 rounded-lg text-center border-2`} style={{ borderColor: model.color }}>
                <div className="text-sm sm:text-base font-bold leading-tight whitespace-nowrap">{tpL}</div>
                <div className="text-[9px] sm:text-[10px] mt-1 opacity-75">{(localTotal > 0 ? (tpL / localTotal * 100).toFixed(1) : '0.0')}%</div>
                <div className="text-[9px] sm:text-[10px] mt-1 font-semibold">TP</div>
              </div>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse">
                <thead>
                  <tr>
                    <th className="border p-2 bg-gray-50 font-semibold text-xs" colSpan={2} rowSpan={2}>
                      <div className="text-center">
                        <div className="text-xs text-gray-500">Predicted →</div>
                        <div className="text-xs text-gray-500 mt-1">Actual ↓</div>
                      </div>
                    </th>
                    <th className="border p-2 bg-blue-50 text-center font-semibold text-xs" colSpan={localNumClasses}>
                      Predicted Class
                    </th>
                  </tr>
                  <tr>
                    {Array.from({ length: localNumClasses }, (_, i) => (
                      <th key={i} className="border p-2 bg-blue-50 text-xs font-medium">
                        Class {i}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {matrixToUse.map((row, rowIdx) => (
                    <tr key={rowIdx}>
                      {rowIdx === 0 && (
                        <th 
                          className="border p-2 bg-blue-50 text-xs font-semibold text-center" 
                          rowSpan={localNumClasses}
                        >
                          Actual Class
                        </th>
                      )}
                      <th className="border p-2 bg-blue-50 text-xs font-medium">
                        Class {rowIdx}
                      </th>
                      {row.map((value, colIdx) => {
                        const percentage = localTotal > 0 ? ((value / localTotal) * 100).toFixed(1) : '0.0';
                        return (
                          <td 
                            key={colIdx} 
                            className={`border p-1 text-center ${getColorIntensity(value, localMax)} ${getTextColor(value, localMax)}`}
                          >
                            <div className="text-xs font-semibold whitespace-nowrap">{value}</div>
                            <div className="text-[10px] opacity-75 whitespace-nowrap">({percentage}%)</div>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      );
    };

    // hasTrainMatrix and hasTestMatrix are already calculated above

    const accuracyText = formatTrainTestPair(
      model.trainAccuracy,
      model.accuracy,
      (v) => `${(v * 100).toFixed(1)}%`
    );

    const f1Text = formatTrainTestPair(
      model.trainF1Score,
      model.f1Score,
      (v) => v.toFixed(3)
    );

    return (
      <div 
        key={model.modelId}
        className="bg-white rounded-xl p-6 border-2 shadow-lg"
        style={{ borderColor: model.color }}
      >
        <div className="mb-4">
          <h4 
            className="text-xl font-bold mb-2"
            style={{ color: model.color }}
          >
            {model.modelName}
          </h4>
          <div className="flex gap-4 text-sm">
            <div>
            <span className="text-gray-600">Accuracy (train / test): </span>
            <span className="font-bold text-gray-900">{accuracyText}</span>
            </div>
            <div>
            <span className="text-gray-600">F1 Score (train / test): </span>
            <span className="font-bold text-gray-900">{f1Text}</span>
            </div>
          </div>
        </div>

        <div className={`grid gap-4 ${hasTrainMatrix && hasTestMatrix ? 'md:grid-cols-2' : 'grid-cols-1'}`}>
        {/* TRAIN confusion matrix (optional) */}
        {hasTrainMatrix && renderSingleMatrix(model.trainMatrix as number[][], 'Train')}

        {/* TEST confusion matrix (only if test data exists) */}
        {hasTestMatrix && model.matrix && renderSingleMatrix(model.matrix, hasTrainMatrix ? 'Test' : 'Test')}
        </div>

        {isBinary && (
          <div className="mt-4 text-xs text-gray-600 text-center">
            <p><strong>Legend:</strong> TN = True Negative, FP = False Positive, FN = False Negative, TP = True Positive</p>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="bg-white rounded-2xl shadow-xl p-8 border-2 border-gray-100">
      <div className="mb-6">
        <h3 className="text-2xl font-bold text-gray-900 mb-2">{title}</h3>
        <p className="text-sm text-gray-600">
          Detailed breakdown of prediction outcomes for each model
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {models.map(renderConfusionMatrix)}
      </div>
    </div>
  );
};

export default ConfusionMatrixComparison;














