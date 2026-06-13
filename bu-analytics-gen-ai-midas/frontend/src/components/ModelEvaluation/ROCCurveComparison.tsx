/**
 * ROC Curve Comparison Chart - Multiple Models
 */

import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine } from 'recharts';
import { ROCCurveData } from '../../types/modelEvaluation';
import { useTheme } from '../../contexts/ThemeContext';

interface ModelROCCurve {
  modelName: string;
  modelId: string;
  rocData: ROCCurveData;
  color: string;
}

interface ROCCurveComparisonProps {
  models: ModelROCCurve[];
  title?: string;
}

export const ROCCurveComparison: React.FC<ROCCurveComparisonProps> = ({
  models,
  title = 'ROC Curve Comparison'
}) => {
  const { isDark } = useTheme();
  const colors = {
    container: 'bg-white dark:bg-gray-900 border-gray-100 dark:border-gray-800',
    title: 'text-gray-900 dark:text-white',
    text: 'text-gray-600 dark:text-gray-300',
    emptyText: 'text-gray-500 dark:text-gray-200',
    emptySubText: 'text-gray-400 dark:text-gray-300',
    grid: isDark ? '#2b2f36' : '#e0e0e0',
    tick: isDark ? '#e5e7eb' : '#6B7280',
    axisLabel: isDark ? '#e5e7eb' : '#374151',
    tooltipBg: isDark ? '#111827' : 'white',
    tooltipBorder: isDark ? '#374151' : '#e5e7eb',
    tooltipText: isDark ? '#f9fafb' : '#111827',
    interpretationBg: 'bg-blue-50 border-blue-200 dark:bg-gray-800 dark:border-gray-700',
    interpretationText: 'text-gray-700 dark:text-gray-200',
    aucCard: 'bg-gray-50 border-gray-200 dark:bg-gray-800 dark:border-gray-700',
    aucText: 'text-gray-700 dark:text-gray-100',
    aucLabel: 'text-gray-600 dark:text-gray-300',
  };

  // Filter out models with invalid or missing ROC data
  const validModels = models?.filter(m => 
    m && 
    m.rocData && 
    Array.isArray(m.rocData.fpr) && 
    Array.isArray(m.rocData.tpr) && 
    m.rocData.fpr.length > 0 && 
    m.rocData.tpr.length > 0 &&
    m.rocData.fpr.length === m.rocData.tpr.length
  ) || [];

  if (validModels.length === 0) {
    return (
      <div className={`rounded-2xl shadow-xl p-8 border-2 ${colors.container}`}>
        <div className={`text-center py-12 ${colors.emptyText}`}>
          <p className={`text-lg font-medium ${colors.title}`}>No ROC curve data available for comparison</p>
          <p className={`text-sm mt-2 ${colors.emptySubText}`}>
            {models && models.length > 0 
              ? `${models.length} model(s) provided but no valid ROC data found`
              : 'No models provided'}
          </p>
        </div>
      </div>
    );
  }

  // Prepare chart data - combine all models
  // Use actual FPR values from all models for better accuracy
  const prepareChartData = () => {
    // Collect all unique FPR values from all models
    const allFprValues = new Set<number>();
    validModels.forEach(model => {
      model.rocData.fpr.forEach(fpr => allFprValues.add(fpr));
    });
    // Ensure full diagonal line for random classifier
    allFprValues.add(0);
    allFprValues.add(1);
    
    // Sort FPR values
    const sortedFpr = Array.from(allFprValues).sort((a, b) => a - b);
    
    // For each FPR point, interpolate TPR values for each model
    const chartData: any[] = [];
    
    sortedFpr.forEach(fpr => {
      const point: any = { fpr, random: fpr };
      
      validModels.forEach(model => {
        const fprArray = model.rocData.fpr;
        const tprArray = model.rocData.tpr;
        
        // Find the closest FPR indices for interpolation
        let lowerIdx = 0;
        let upperIdx = fprArray.length - 1;
        
        for (let i = 0; i < fprArray.length - 1; i++) {
          if (fprArray[i] <= fpr && fprArray[i + 1] >= fpr) {
            lowerIdx = i;
            upperIdx = i + 1;
            break;
          }
        }
        
        // If exact match or at boundaries
        if (fpr <= fprArray[0]) {
          point[`${model.modelId}_tpr`] = tprArray[0];
        } else if (fpr >= fprArray[fprArray.length - 1]) {
          point[`${model.modelId}_tpr`] = tprArray[tprArray.length - 1];
        } else {
          // Linear interpolation
          const fprLower = fprArray[lowerIdx];
          const fprUpper = fprArray[upperIdx];
          const tprLower = tprArray[lowerIdx];
          const tprUpper = tprArray[upperIdx];
          
          if (fprUpper === fprLower) {
            point[`${model.modelId}_tpr`] = tprLower;
          } else {
            const ratio = (fpr - fprLower) / (fprUpper - fprLower);
            point[`${model.modelId}_tpr`] = tprLower + ratio * (tprUpper - tprLower);
          }
        }
      });
      
      chartData.push(point);
    });

    return chartData;
  };

  const chartData = prepareChartData();

  return (
    <div className={`rounded-2xl shadow-xl p-8 border-2 ${colors.container}`}>
      <div className="mb-6">
        <h3 className={`text-2xl font-bold mb-2 ${colors.title}`}>{title}</h3>
        <p className={`text-sm ${colors.text}`}>
          Receiver Operating Characteristic curves showing true positive rate vs false positive rate
        </p>
      </div>

      <div className="w-full overflow-x-auto min-h-[500px] min-w-0">
        <div className="min-w-[600px] w-full h-[500px] min-h-[480px]">
          <ResponsiveContainer width="100%" height="100%" minWidth={0} debounce={50}>
        <LineChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} />
          <XAxis 
            dataKey="fpr" 
            label={{ value: 'False Positive Rate', position: 'insideBottom', offset: -5, fill: colors.axisLabel }}
            domain={[0, 1]}
            tick={{ fill: colors.tick }}
          />
          <YAxis 
            label={{ value: 'True Positive Rate', angle: -90, position: 'insideLeft', fill: colors.axisLabel }}
            domain={[0, 1]}
            tick={{ fill: colors.tick }}
          />
          <Tooltip 
            formatter={(value: any) => value ? value.toFixed(3) : 'N/A'}
            labelFormatter={(value: any) => `FPR: ${parseFloat(value).toFixed(3)}`}
            contentStyle={{ backgroundColor: colors.tooltipBg, border: `1px solid ${colors.tooltipBorder}`, borderRadius: '8px', color: colors.tooltipText }}
          />
          <Legend 
            wrapperStyle={{ paddingTop: '20px', color: colors.tick }}
            iconType="line"
          />
          
          {/* Diagonal reference line (random classifier) */}
          <ReferenceLine
            segment={[
              { x: 0, y: 0 },
              { x: 1, y: 1 }
            ]}
            stroke="#9CA3AF"
            strokeDasharray="5 5"
            strokeWidth={1.5}
            ifOverflow="extendDomain"
          />
          
          {/* Model ROC curves - all models in one chart */}
          {validModels.map((model) => (
            <Line 
              key={model.modelId}
              type="monotone" 
              dataKey={`${model.modelId}_tpr`}
              stroke={model.color} 
              strokeWidth={2.5}
              dot={false}
              name={`${model.modelName} (AUC: ${model.rocData.auc?.toFixed(4) || 'N/A'})`}
              activeDot={{ r: 6 }}
            />
          ))}
        </LineChart>
        </ResponsiveContainer>
        </div>
      </div>

      <div className={`mt-6 p-4 rounded-lg border ${colors.interpretationBg}`}>
        <p className={`text-sm ${colors.interpretationText}`}>
          <strong>Interpretation:</strong> The ROC curve plots the trade-off between true positive rate and false positive rate. 
          A model with perfect discrimination has AUC = 1.0, while random guessing has AUC = 0.5 (diagonal line). 
          Curves closer to the top-left corner indicate better performance.
        </p>
      </div>

      {/* AUC Scores Display */}
      <div className="mt-6 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        {validModels.map((model) => (
          <div 
            key={model.modelId}
            className={`rounded-lg p-4 border-2 text-center ${colors.aucCard}`}
          >
            <div className={`text-sm font-semibold mb-2 ${colors.aucText}`}>{model.modelName}</div>
            <div 
              className="text-2xl font-bold mb-1"
              style={{ color: model.color }}
            >
              {model.rocData.auc?.toFixed(4) || 'N/A'}
            </div>
            <div className={`text-xs ${colors.aucLabel}`}>AUC-ROC</div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ROCCurveComparison;

