/**
 * ROC Curve Visualization Component
 */

import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { ROCCurveData } from '../../types/modelEvaluation';

interface ROCCurveChartProps {
  rocData: ROCCurveData | Record<string, ROCCurveData>;
  title?: string;
}

export const ROCCurveChart: React.FC<ROCCurveChartProps> = ({
  rocData,
  title = 'ROC Curve'
}) => {
  if (!rocData) {
    return <div className="p-4 text-gray-500">No ROC curve data available</div>;
  }

  // Check if multi-class (object with class keys) or binary (direct ROCCurveData)
  const isMultiClass = 'fpr' in rocData ? false : true;

  const prepareChartData = () => {
    if (!isMultiClass) {
      // Binary classification
      const data = rocData as ROCCurveData;
      return data.fpr.map((fpr, idx) => ({
        fpr,
        tpr: data.tpr[idx]
      }));
    } else {
      // Multi-class: combine all classes
      const classData = rocData as Record<string, ROCCurveData>;
      const allData: any[] = [];
      const maxLength = Math.max(
        ...Object.values(classData).map(d => d.fpr.length)
      );

      for (let i = 0; i < maxLength; i++) {
        const point: any = { fpr: i / (maxLength - 1) }; // Normalized FPR
        
        Object.entries(classData).forEach(([className, data]) => {
          if (i < data.fpr.length) {
            point[`${className}_tpr`] = data.tpr[i];
          }
        });
        
        allData.push(point);
      }
      
      return allData;
    }
  };

  const chartData = prepareChartData();
  const colors = ['#3B82F6', '#EF4444', '#10B981', '#F59E0B', '#8B5CF6'];

  // Get AUC value(s)
  const getAUCDisplay = () => {
    if (!isMultiClass) {
      const data = rocData as ROCCurveData;
      return (
        <div className="text-sm text-gray-600">
          AUC = <span className="font-semibold text-blue-600">{data.auc.toFixed(3)}</span>
        </div>
      );
    } else {
      const classData = rocData as Record<string, ROCCurveData>;
      return (
        <div className="space-y-1">
          {Object.entries(classData).map(([className, data], idx) => (
            <div key={className} className="text-sm text-gray-600 flex items-center gap-2">
              <div 
                className="w-3 h-3 rounded-full" 
                style={{ backgroundColor: colors[idx % colors.length] }}
              />
              {className}: AUC = <span className="font-semibold">{data.auc.toFixed(3)}</span>
            </div>
          ))}
        </div>
      );
    }
  };

  return (
    <div className="bg-white p-6 rounded-lg shadow">
      <div className="flex justify-between items-start mb-4">
        <h3 className="text-lg font-semibold">{title}</h3>
        {getAUCDisplay()}
      </div>
      
      <ResponsiveContainer width="100%" height={400}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
          <XAxis 
            dataKey="fpr" 
            label={{ value: 'False Positive Rate', position: 'insideBottom', offset: -5 }}
            domain={[0, 1]}
          />
          <YAxis 
            label={{ value: 'True Positive Rate', angle: -90, position: 'insideLeft' }}
            domain={[0, 1]}
          />
          <Tooltip 
            formatter={(value: any) => value.toFixed(3)}
            labelFormatter={(value: any) => `FPR: ${parseFloat(value).toFixed(3)}`}
          />
          <Legend />
          
          {/* Diagonal reference line (random classifier) */}
          <Line 
            dataKey="fpr" 
            stroke="#ccc" 
            strokeDasharray="5 5" 
            dot={false}
            name="Random (AUC=0.5)"
            strokeWidth={1}
          />
          
          {!isMultiClass ? (
            // Binary classification
            <Line 
              type="monotone" 
              dataKey="tpr" 
              stroke="#3B82F6" 
              strokeWidth={2}
              dot={false}
              name="ROC Curve"
            />
          ) : (
            // Multi-class
            Object.keys(rocData as Record<string, ROCCurveData>).map((className, idx) => (
              <Line 
                key={className}
                type="monotone" 
                dataKey={`${className}_tpr`} 
                stroke={colors[idx % colors.length]} 
                strokeWidth={2}
                dot={false}
                name={`${className}`}
              />
            ))
          )}
        </LineChart>
      </ResponsiveContainer>

      <div className="mt-4 text-sm text-gray-500 text-center">
        The ROC curve shows the trade-off between TPR and FPR at various thresholds.
        {' '}AUC closer to 1.0 indicates better model performance.
      </div>
    </div>
  );
};

export default ROCCurveChart;













