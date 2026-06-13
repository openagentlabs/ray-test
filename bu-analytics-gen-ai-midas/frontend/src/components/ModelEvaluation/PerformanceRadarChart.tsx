/**
 * Performance Radar Chart - Multi-dimensional Performance Comparison
 */

import React from 'react';
import { RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, Legend, ResponsiveContainer, Tooltip } from 'recharts';
import { useTheme } from '../../contexts/ThemeContext';

interface ModelMetrics {
  modelName: string;
  modelId: string;
  accuracy: number;
  precision: number;
  recall: number;
  f1Score: number;
  aucRoc: number;
  color: string;
}

interface PerformanceRadarChartProps {
  models: ModelMetrics[];
  title?: string;
}

export const PerformanceRadarChart: React.FC<PerformanceRadarChartProps> = ({
  models,
  title = 'Performance Radar Chart'
}) => {
  const { isDark } = useTheme();
  const colors = {
    container: 'bg-white dark:bg-gray-900 border-gray-100 dark:border-gray-800',
    title: 'text-gray-900 dark:text-white',
    text: 'text-gray-600 dark:text-gray-300',
    emptyText: 'text-gray-500 dark:text-gray-200',
    grid: isDark ? '#2b2f36' : '#e0e0e0',
    tick: isDark ? '#e5e7eb' : '#6B7280',
    tickMuted: isDark ? '#cbd5e1' : '#9CA3AF',
    tooltipBg: isDark ? '#111827' : 'white',
    tooltipBorder: isDark ? '#374151' : '#e5e7eb',
    tooltipText: isDark ? '#f9fafb' : '#111827',
  };

  if (!models || models.length === 0) {
    return (
      <div className={`rounded-2xl shadow-xl p-8 border-2 ${colors.container}`}>
        <div className={`text-center py-12 ${colors.emptyText}`}>
          <p className={`text-lg font-medium ${colors.title}`}>No performance data available for comparison</p>
        </div>
      </div>
    );
  }

  // Prepare data for radar chart
  const prepareRadarData = () => {
    const metrics = [
      { name: 'Accuracy', key: 'accuracy', max: 1.0 },
      { name: 'Precision', key: 'precision', max: 1.0 },
      { name: 'Recall', key: 'recall', max: 1.0 },
      { name: 'F1 Score', key: 'f1Score', max: 1.0 },
      { name: 'AUC-ROC', key: 'aucRoc', max: 1.0 },
    ];

    return metrics.map(metric => {
      const dataPoint: any = { metric: metric.name };
      
      models.forEach(model => {
        const value = model[metric.key as keyof ModelMetrics] as number;
        dataPoint[model.modelId] = value;
      });
      
      return dataPoint;
    });
  };

  const radarData = prepareRadarData();

  return (
    <div className={`rounded-2xl shadow-xl p-8 border-2 ${colors.container}`}>
      <div className="mb-6">
        <h3 className={`text-2xl font-bold mb-2 ${colors.title}`}>{title}</h3>
        <p className={`text-sm ${colors.text}`}>
          Multi-dimensional performance comparison across key metrics
        </p>
      </div>

      <div className="w-full overflow-x-auto min-h-[500px] min-w-0">
        <div className="min-w-[600px] w-full h-[500px] min-h-[480px]">
          <ResponsiveContainer width="100%" height="100%" minWidth={0} debounce={50}>
            <RadarChart
              data={radarData}
              margin={{ top: 20, right: 30, bottom: 20, left: 20 }}
              style={{ background: 'transparent' }}
            >
              <PolarGrid stroke={colors.grid} />
              <PolarAngleAxis dataKey="metric" tick={{ fill: colors.tick, fontSize: 12 }} />
              <PolarRadiusAxis angle={90} domain={[0, 1]} tick={{ fill: colors.tickMuted, fontSize: 10 }} />
              <Tooltip
                formatter={(value: any) => value.toFixed(3)}
                contentStyle={{
                  backgroundColor: colors.tooltipBg,
                  border: `1px solid ${colors.tooltipBorder}`,
                  borderRadius: '8px',
                  color: colors.tooltipText,
                }}
              />
              <Legend wrapperStyle={{ paddingTop: '20px', color: colors.tick }} />

              {models.map((model) => (
                <Radar
                  key={model.modelId}
                  name={model.modelName}
                  dataKey={model.modelId}
                  stroke={model.color}
                  fill="transparent"
                  fillOpacity={0}
                  strokeWidth={2}
                />
              ))}
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>

    </div>
  );
};

export default PerformanceRadarChart;

