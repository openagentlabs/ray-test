/**
 * Confusion Matrix Visualization Component
 */

import React from 'react';

interface ConfusionMatrixChartProps {
  matrix: number[][];
  classLabels?: string[];
  title?: string;
}

export const ConfusionMatrixChart: React.FC<ConfusionMatrixChartProps> = ({
  matrix,
  classLabels,
  title = 'Confusion Matrix'
}) => {
  if (!matrix || matrix.length === 0) {
    return <div className="p-4 text-gray-500">No confusion matrix data available</div>;
  }

  const numClasses = matrix.length;
  const labels = classLabels || Array.from({ length: numClasses }, (_, i) => `Class ${i}`);
  
  // Calculate total for percentages
  const total = matrix.flat().reduce((sum, val) => sum + val, 0);
  
  // Find max value for color scaling
  const maxValue = Math.max(...matrix.flat());

  // Get color intensity based on value
  const getColorIntensity = (value: number): string => {
    const intensity = maxValue > 0 ? (value / maxValue) : 0;
    
    if (intensity === 0) return 'bg-gray-100';
    if (intensity < 0.2) return 'bg-blue-100';
    if (intensity < 0.4) return 'bg-blue-200';
    if (intensity < 0.6) return 'bg-blue-300';
    if (intensity < 0.8) return 'bg-blue-400';
    return 'bg-blue-500';
  };

  const getTextColor = (value: number): string => {
    const intensity = maxValue > 0 ? (value / maxValue) : 0;
    return intensity > 0.5 ? 'text-white' : 'text-gray-900';
  };

  return (
    <div className="bg-white p-6 rounded-lg shadow">
      <h3 className="text-lg font-semibold mb-4">{title}</h3>
      
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr>
              <th className="border p-2 bg-gray-50 font-semibold" colSpan={2} rowSpan={2}>
                <div className="flex items-center justify-center h-full">
                  <div className="text-center">
                    <div className="text-xs text-gray-500">Predicted →</div>
                    <div className="text-xs text-gray-500 mt-1">Actual ↓</div>
                  </div>
                </div>
              </th>
              <th className="border p-2 bg-blue-50 text-center font-semibold" colSpan={numClasses}>
                Predicted Class
              </th>
            </tr>
            <tr>
              {labels.map((label, idx) => (
                <th key={idx} className="border p-2 bg-blue-50 text-sm font-medium min-w-[100px]">
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrix.map((row, rowIdx) => (
              <tr key={rowIdx}>
                {rowIdx === 0 && (
                  <th 
                    className="border p-2 bg-blue-50 text-sm font-semibold text-center" 
                    rowSpan={numClasses}
                    style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}
                  >
                    Actual Class
                  </th>
                )}
                <th className="border p-2 bg-blue-50 text-sm font-medium">
                  {labels[rowIdx]}
                </th>
                {row.map((value, colIdx) => {
                  const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : '0.0';
                  const isCorrect = rowIdx === colIdx;
                  
                  return (
                    <td 
                      key={colIdx} 
                      className={`border p-3 text-center cursor-default transition-all hover:scale-105 ${getColorIntensity(value)} ${getTextColor(value)}`}
                    >
                      <div className="font-semibold text-lg">{value}</div>
                      <div className={`text-xs ${getTextColor(value)} opacity-75`}>
                        ({percentage}%)
                      </div>
                      {isCorrect && (
                        <div className="text-xs mt-1 font-medium">✓ Correct</div>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="mt-4 flex items-center justify-end gap-4 text-sm">
        <span className="text-gray-600">Intensity:</span>
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 bg-gray-100 border rounded"></div>
          <span className="text-gray-500">Low</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 bg-blue-300 border rounded"></div>
          <span className="text-gray-500">Medium</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 bg-blue-500 border rounded"></div>
          <span className="text-gray-500">High</span>
        </div>
      </div>
    </div>
  );
};

export default ConfusionMatrixChart;













